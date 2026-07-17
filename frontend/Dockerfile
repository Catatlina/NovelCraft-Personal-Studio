FROM nginx:1.27-alpine
COPY proto.html /usr/share/nginx/html/index.html
COPY public/ /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
