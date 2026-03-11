#!/bin/sh
# Lightline Panel — Nginx entrypoint
# Automatically enables HTTPS if SSL certificates are found

SSL_CERT="/etc/nginx/ssl/fullchain.pem"
SSL_KEY="/etc/nginx/ssl/privkey.pem"

if [ -f "$SSL_CERT" ] && [ -f "$SSL_KEY" ]; then
    echo "[Lightline] SSL certificates found — enabling HTTPS"
    cat > /etc/nginx/conf.d/default.conf <<'NGINX'
# HTTP → HTTPS redirect
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name _;

    ssl_certificate     /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_read_timeout 300s;
        proxy_connect_timeout 10s;
    }

    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript image/svg+xml;
    gzip_min_length 256;
}
NGINX
else
    echo "[Lightline] No SSL certificates — running HTTP only"
    echo "[Lightline] To enable HTTPS, mount certbot certs:"
    echo "  /etc/letsencrypt/live/YOUR_DOMAIN/fullchain.pem -> /etc/nginx/ssl/fullchain.pem"
    echo "  /etc/letsencrypt/live/YOUR_DOMAIN/privkey.pem   -> /etc/nginx/ssl/privkey.pem"
fi

exec "$@"
