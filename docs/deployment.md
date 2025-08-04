# Deployment

## Quick Deploy

```bash
# First time setup
cd deploy
ansible-playbook deploy.yml --limit production --ask-vault-pass

# Updates
just deploy
```

## Configuration

1. Edit `deploy/inventory/hosts.yml`:
```yaml
all:
  hosts:
    production:
      ansible_host: macmini.fritz.box
      ansible_user: your-username
```

2. Create and encrypt secrets:
```bash
# deploy/secrets.yml
django_secret_key: "generate-a-long-random-key"

# Encrypt
ansible-vault encrypt deploy/secrets.yml
```

## What Gets Deployed

- Application code to `/home/homelab/site`
- Systemd service as `homelab.service`
- Granian WSGI server on port 8001
- SQLite database with automated backups

## Reverse Proxy

### Nginx
```nginx
server {
    listen 443 ssl;
    server_name home.wersdoerfer.de;
    
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /static/ {
        alias /home/homelab/site/staticfiles/;
    }
}
```

### Caddy
```text
home.wersdoerfer.de {
    reverse_proxy localhost:8001
    handle_path /static/* {
        root * /home/homelab/site/staticfiles
        file_server
    }
}
```

## Management

```bash
# Service control
sudo systemctl status homelab
sudo systemctl restart homelab
sudo journalctl -u homelab -f

# Backup database
just backup

# Update application
just deploy
```

## Security Checklist

- [ ] Set strong `DJANGO_SECRET_KEY`
- [ ] `DEBUG = False` in production
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Use HTTPS only
- [ ] Change admin URL from default
- [ ] Enable firewall