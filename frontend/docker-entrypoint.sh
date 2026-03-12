#!/bin/sh
# Lightline Panel — Nginx entrypoint
# Automatically enables HTTPS if certbot certificates are found.
# Like Marzban: run certbot on host, mount /etc/letsencrypt into container.

# Find SSL cert: check PANEL_DOMAIN first, then scan all live dirs
SSL_CERT=""
SSL_KEY=""

if [ -n "$PANEL_DOMAIN" ] && [ -f "/etc/letsencrypt/live/$PANEL_DOMAIN/fullchain.pem" ]; then
    SSL_CERT="/etc/letsencrypt/live/$PANEL_DOMAIN/fullchain.pem"
    SSL_KEY="/etc/letsencrypt/live/$PANEL_DOMAIN/privkey.pem"
    echo "[Lightline] Found certbot cert for $PANEL_DOMAIN"
else
    # Auto-detect: find first valid cert in /etc/letsencrypt/live/
    for dir in /etc/letsencrypt/live/*/; do
        if [ -f "${dir}fullchain.pem" ] && [ -f "${dir}privkey.pem" ]; then
            SSL_CERT="${dir}fullchain.pem"
            SSL_KEY="${dir}privkey.pem"
            echo "[Lightline] Auto-detected cert in $dir"
            break
        fi
    done
fi

if [ -n "$SSL_CERT" ] && [ -n "$SSL_KEY" ]; then
    echo "[Lightline] HTTPS enabled — $SSL_CERT"
    cat > /etc/nginx/conf.d/default.conf <<NGINX
# HTTP → HTTPS redirect
server {
    listen 80;
    server_name _;
    return 301 https://\$host\$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name _;

    ssl_certificate     $SSL_CERT;
    ssl_certificate_key $SSL_KEY;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
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
    echo "[Lightline] No SSL certificates found — running HTTP only"
    echo "[Lightline] To enable HTTPS:"
    echo "  1. Run: certbot certonly --standalone -d YOUR_DOMAIN"
    echo "  2. Set PANEL_DOMAIN=YOUR_DOMAIN in .env"
    echo "  3. Restart: docker compose up -d"
fi

exec "$@"
