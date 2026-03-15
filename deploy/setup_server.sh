#!/bin/bash
# TiOLi AI Transact Exchange — Server Setup Script
# Run this on a fresh Ubuntu 22.04 DigitalOcean droplet as root
# Usage: bash setup_server.sh

set -e

echo "============================================"
echo "  TiOLi AI Transact Exchange — Server Setup"
echo "============================================"

# 1. Update system
echo "[1/8] Updating system packages..."
apt update && apt upgrade -y

# 2. Install Python 3.11+ and dependencies
echo "[2/8] Installing Python and system dependencies..."
apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git ufw

# 3. Create app user
echo "[3/8] Creating application user..."
useradd -m -s /bin/bash tioli || true
mkdir -p /home/tioli/app
chown -R tioli:tioli /home/tioli

# 4. Set up firewall
echo "[4/8] Configuring firewall..."
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

# 5. Clone/copy the application
echo "[5/8] Setting up application..."
cd /home/tioli/app

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Create requirements.txt
cat > requirements.txt << 'REQEOF'
fastapi==0.115.6
uvicorn[standard]==0.34.0
jinja2==3.1.4
python-multipart==0.0.18
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
pydantic==2.10.3
pydantic-settings==2.7.0
sqlalchemy==2.0.36
aiosqlite==0.20.0
httpx==0.28.1
cryptography==44.0.0
websockets==14.1
gunicorn==23.0.0
REQEOF

pip install -r requirements.txt

# 6. Create .env file
echo "[6/8] Creating environment configuration..."
cat > .env << 'ENVEOF'
# TiOLi AI Transact Exchange — Production Configuration
SECRET_KEY=CHANGE_ME_TO_A_RANDOM_64_CHAR_STRING
OWNER_EMAIL=sendersby@tioli.onmicrosoft.com
OWNER_PHONE=+270827090435
DATABASE_URL=sqlite+aiosqlite:///./tioli_exchange.db
FOUNDER_COMMISSION_RATE=0.12
CHARITY_FEE_RATE=0.10
PLATFORM_NAME=TiOLi AI Transact Exchange
DEBUG=false
AGENTBROKER_ENABLED=false
PAYPAL_ENABLED=false
PAYPAL_SANDBOX=true
ENVEOF

echo ">>> IMPORTANT: Edit .env and set a strong SECRET_KEY <<<"

# 7. Configure Nginx reverse proxy
echo "[7/8] Configuring Nginx..."
cat > /etc/nginx/sites-available/tioli-exchange << 'NGINXEOF'
server {
    listen 80;
    server_name exchange.tioli.co.za;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120;
        proxy_connect_timeout 120;
    }

    location /static {
        alias /home/tioli/app/static;
        expires 7d;
    }
}
NGINXEOF

ln -sf /etc/nginx/sites-available/tioli-exchange /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

# 8. Create systemd service
echo "[8/8] Creating systemd service..."
cat > /etc/systemd/system/tioli-exchange.service << 'SVCEOF'
[Unit]
Description=TiOLi AI Transact Exchange
After=network.target

[Service]
Type=simple
User=tioli
WorkingDirectory=/home/tioli/app
Environment=PATH=/home/tioli/app/.venv/bin:/usr/bin
ExecStart=/home/tioli/app/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable tioli-exchange

echo ""
echo "============================================"
echo "  Server setup complete!"
echo ""
echo "  Next steps:"
echo "  1. Upload your app code to /home/tioli/app/"
echo "  2. Edit /home/tioli/app/.env with a strong SECRET_KEY"
echo "  3. Run: systemctl start tioli-exchange"
echo "  4. Run: certbot --nginx -d exchange.tioli.co.za"
echo "  5. Visit: https://exchange.tioli.co.za"
echo "============================================"
