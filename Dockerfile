FROM php:8.3-apache AS server

LABEL org.opencontainers.image.description="Creates a environment to serve PHP files for the Remote Client API."

WORKDIR /var/www/html

USER root

RUN apt-get update -y -qq && \
  a2enmod rewrite && \
  a2enmod headers

# gd and its image library dependencies
RUN apt-get install -y -qq libpng-dev libjpeg62-turbo-dev libfreetype6-dev && \
  docker-php-ext-configure gd --with-jpeg --with-freetype && \
  docker-php-ext-install -j"$(nproc)" gd && \
  rm -rf /var/lib/apt/lists/*

EXPOSE 80

USER www-data
