FROM php:8.3-apache AS server

LABEL org.opencontainers.image.description="Creates a environment to serve PHP files for the Remote Client API."

WORKDIR /var/www/html

USER root

RUN apt-get update -y -qq && \
  a2enmod rewrite && \
  a2enmod headers

# gd and its image library dependencies
RUN apt-get install -y -qq libpng-dev libjpeg62-turbo-dev libfreetype6-dev libonig-dev && \
  docker-php-ext-configure gd --with-jpeg --with-freetype && \
  docker-php-ext-install -j"$(nproc)" gd mbstring && \
  rm -rf /var/lib/apt/lists/*

# The security policy must be enabled at server scope: .htaccess runs too late
# for paths normalized outside this directory. The source tree is mounted at
# /var/www/html by Compose; never run it without the included policy.
COPY apache/remote-security.conf /etc/apache2/remote-security.conf
RUN printf 'Define RC_BASE /\nDefine RC_DIR "/var/www/html"\nInclude /etc/apache2/remote-security.conf\n' > /etc/apache2/conf-available/remote-security.conf \
  && sed -i '/<\/VirtualHost>/i\    Include /etc/apache2/conf-available/remote-security.conf' /etc/apache2/sites-available/000-default.conf

EXPOSE 80

USER www-data
