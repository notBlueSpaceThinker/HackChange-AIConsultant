FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html /usr/share/nginx/html/index.html
COPY logo.svg /usr/share/nginx/html/logo.svg
COPY fonts /usr/share/nginx/html/fonts
COPY src /usr/share/nginx/html/src

EXPOSE 80
