#!/usr/bin/env python3
"""Run the standalone Apache image against disposable filesystem fixtures."""
import http.client
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.parse
import uuid

repo = Path(__file__).resolve().parents[1]
image = sys.argv[1] if len(sys.argv) > 1 else 'robrowser-php-standalone-test:local'
name = 'remote-apache-test-' + uuid.uuid4().hex[:12]
with tempfile.TemporaryDirectory(prefix='remote-standalone-test-') as temp:
    root = Path(temp)
    root.chmod(0o755)
    for d in ('data', 'System', 'SystemEN', 'AI', 'BGM', 'resources'):
        (root / d).mkdir(mode=0o755)
    for path, data in {'System/itemInfo.lua': b'system-original\n', 'SystemEN/itemInfo.lua': b'systemen\n',
                       'data/utf8-한글.lua': b'utf8\n', 'AI/Util.lua': b'ai\n'}.items():
        (root / path).write_bytes(data)
    cpname = '한국어.lua'.encode('cp949')
    with open(os.fsencode(root / 'data') + b'/' + cpname, 'wb') as f:
        f.write(b'cp949\n')
    (root / 'data' / 'escape.txt').symlink_to('/etc/passwd')
    command = ['docker', 'run', '-d', '--name', name, '-p', '127.0.0.1::80',
               '-v', f'{repo}:/var/www/html:ro', '-v', f'{root}:/fixtures:ro',
               '-e', 'CLIENT_AUTOEXTRACT=false', '-e', 'CLIENT_ENABLESEARCH=false',
               '-e', 'MISSING_LOG_ENABLED=false', '-e', 'DATA_OVERRIDE_PATH=/fixtures/data',
               '-e', 'SYSTEM_PATH=/fixtures/System', '-e', 'SYSTEMEN_PATH=/fixtures/SystemEN',
               '-e', 'AI_PATH=/fixtures/AI', '-e', 'BGM_PATH=/fixtures/BGM',
               '-e', 'SYSTEM_ALIAS_SYSTEMEN=true', image]
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
        port = int(subprocess.check_output(['docker', 'port', name, '80'], text=True).strip().rsplit(':', 1)[1])
        def request(url):
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=15)
            conn.request('GET', '/' + url)
            response = conn.getresponse()
            result = response.status, response.read(), response.getheader('Access-Control-Allow-Origin')
            conn.close()
            return result
        for _ in range(30):
            try:
                if request('System/itemInfo.lua')[0] == 200: break
            except OSError: pass
            time.sleep(1)
        for path, expected in [('System/itemInfo.lua', b'system-original\n'),
                               ('SystemEN/itemInfo.lua', b'systemen\n'), ('AI/Util.lua', b'ai\n'),
                               ('data/' + urllib.parse.quote('utf8-한글.lua'), b'utf8\n'),
                               ('data/' + urllib.parse.quote('한국어.lua'), b'cp949\n'),
                               ('data/' + urllib.parse.quote_from_bytes(cpname), b'cp949\n')]:
            status, content, cors = request(path)
            assert (status, content, cors) == (200, expected, '*'), (path, status, content[:80], cors)
        for path in ('configs.php', 'Client.php', 'resources/DATA.INI', 'data/escape.txt',
                     'data/missing.lua', 'data/../configs.php', 'data/%2e%2e/configs.php',
                     'data/%252e%252e/configs.php', 'data/%2e%2e', 'data/..'):
            status, _, _ = request(path)
            assert status in (403, 404), (path, status)
        print('PASS standalone Apache: routed roots, CP949/UTF-8, precedence, CORS, source/GRF denial, symlink and traversal')
    finally:
        subprocess.run(['docker', 'stop', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['docker', 'rm', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# Document the failure mode when the server-wide policy is missing. The
# deliberately unsafe configuration is confined to a disposable container.
for override, expected in [('All', 403), ('None', 200)]:
    name = 'remote-apache-unconfigured-' + uuid.uuid4().hex[:12]
    shell = ("sed -i '/Include .*remote-security.conf/d' /etc/apache2/sites-available/000-default.conf; "
             "printf '\\n<Directory /var/www/html>\\nAllowOverride " + override +
             "\\nRequire all granted\\n</Directory>\\n' >> /etc/apache2/apache2.conf; "
             "exec apache2-foreground")
    try:
        subprocess.run(['docker', 'run', '-d', '--name', name, '--user', 'root',
                        '-p', '127.0.0.1::80', '-v', f'{repo}:/var/www/html:ro',
                        '--entrypoint', 'sh', image, '-c', shell], check=True, stdout=subprocess.DEVNULL)
        port = int(subprocess.check_output(['docker', 'port', name, '80'], text=True).strip().rsplit(':', 1)[1])
        for _ in range(30):
            try:
                conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
                conn.request('GET', '/data/add-data-folder-files-here.txt')
                response = conn.getresponse()
                status = response.status
                response.read()
                conn.close()
                break
            except OSError:
                time.sleep(1)
        else: raise RuntimeError('unconfigured Apache did not start')
        assert status == expected, (override, status)
        print(f'PASS missing policy with AllowOverride {override}: HTTP {status}' +
              (' (insecure: do not expose)' if override == 'None' else ' (denied)'))
    finally:
        subprocess.run(['docker', 'stop', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['docker', 'rm', name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
