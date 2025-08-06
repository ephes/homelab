# Deployment

## Overview

The homelab deployment consists of multiple components that can be deployed together or separately:
- **Django Application** - The main homelab dashboard
- **Traefik** - Reverse proxy with SSL and basic authentication
- **Pi-hole** - DNS server for local network (optional)
- **Dynamic DNS** - Automatic IP updates for home.wersdörfer.de (optional)

## Quick Deploy

```bash
# Deploy everything
just deploy-all

# Deploy individual components
just deploy        # Django app only (default)
just deploy-app    # Django app only
just deploy-traefik  # Traefik proxy
just deploy-pihole   # Pi-hole DNS
just deploy-dyndns   # Dynamic DNS
```

## Initial Setup

### 1. Configure Inventory

Edit `deploy/inventory/hosts.yml`:
```yaml
all:
  hosts:
    macmini:
      ansible_host: macmini.fritz.box
      # Or use Tailscale hostname:
      # ansible_host: macmini.tailde2ec.ts.net
```

### 2. Configure Vault Password

Create `deploy/.vault_password` with your Ansible Vault password:
```bash
echo "your-vault-password" > deploy/.vault_password
chmod 600 deploy/.vault_password
```

This file is automatically used by Ansible (configured in `ansible.cfg`) and should be gitignored.

### 3. Set Secrets

Edit the encrypted `deploy/secrets.yml`:
```bash
ansible-vault edit deploy/secrets.yml
```

Set these values:
```yaml
---
# Django secret key
django_secret_key: "generate-a-long-random-key"

# Gandi API token for Dynamic DNS
gandi_api_token: "your-gandi-api-token"

# Traefik basic auth password
traefik_basic_auth_password: "your-secure-password"
```

### 4. Configure Variables

Review and adjust `deploy/vars.yml`:
```yaml
# Application settings
app_port: 10010
django_settings_module: "config.settings.production"

# Traefik settings
traefik_basic_auth_user: "admin"
traefik_domain: "home.wersdörfer.de"

# DNS settings (if using Pi-hole)
dns_server_enabled: true
macmini_internal_ip: "192.168.178.50"
```

## Components

### Django Application

- **Location**: `/home/homelab/site`
- **Service**: `homelab.service`
- **Port**: 10010 (internal)
- **Server**: Granian ASGI/WSGI
- **Database**: SQLite with automated backups

### Traefik Reverse Proxy

- **Version**: 3.3.5
- **Features**:
  - Automatic SSL certificates via Let's Encrypt
  - Basic authentication for all access
  - Gzip compression
  - Security headers
- **Configuration**: `/etc/traefik/`
- **Access**: https://home.wersdörfer.de

### Basic Authentication

- **Username**: `admin` (configurable in vars.yml)
- **Password**: Set in secrets.yml
- **Applies to**: All users (including Tailscale)

To change password:
```bash
ansible-vault edit deploy/secrets.yml
# Update traefik_basic_auth_password
just deploy-traefik
```

### Pi-hole DNS Server (Optional)

- **Purpose**: Local DNS resolution and ad blocking
- **Configuration**: `/etc/pihole/`
- **Features**:
  - Tailscale IP resolution for local services
  - Custom DNS entries for *.home.wersdörfer.de

### Dynamic DNS (Optional)

- **Provider**: Gandi
- **Domain**: home.wersdörfer.de
- **Update interval**: Every 5 minutes
- **Service**: `ddns-home.timer`

## Management Commands

### Service Control
```bash
# Application
sudo systemctl status homelab
sudo systemctl restart homelab
sudo journalctl -u homelab -f

# Traefik
sudo systemctl status traefik
sudo systemctl restart traefik
sudo journalctl -u traefik -f

# Dynamic DNS
sudo systemctl status ddns-home.timer
sudo systemctl list-timers
```

### Database Management
```bash
# Create backup
just backup

# Django shell
just shell

# Run migrations
just manage migrate
```

### Deployment
```bash
# Full deployment
just deploy

# Quick app update (code only)
cd deploy && ansible-playbook deploy-app.yml --tags code
```

## Testing

### Check Services
```bash
# Test basic auth
curl -I https://home.wersdörfer.de
# Should return 401 Unauthorized

curl -I -u admin:yourpassword https://home.wersdörfer.de
# Should return 200 OK

# Test from server
ssh macmini.fritz.box
curl -I http://localhost:10010  # Should work
```

### View Logs
```bash
# Application logs
ssh macmini.fritz.box 'sudo journalctl -u homelab -n 50'

# Traefik access logs
ssh macmini.fritz.box 'sudo tail -f /var/log/traefik/access.log'

# Check configurations
ssh macmini.fritz.box 'cat /etc/traefik/dynamic/homelab.yml'
```

## Network Access

### External Access
- URL: https://home.wersdörfer.de
- Requires basic authentication
- SSL certificate from Let's Encrypt

### Tailscale Access
- URL: https://home.wersdörfer.de or https://macmini.tailde2ec.ts.net
- Also requires basic authentication (no bypass currently)
- Can use internal Tailscale IP if needed

### Local Network
- Direct access: http://192.168.178.50:10010 (no auth, internal only)
- Through Traefik: https://home.wersdörfer.de (requires auth)

## Security Checklist

- [x] Basic authentication enabled on Traefik
- [x] HTTPS with valid SSL certificates
- [x] Security headers configured
- [x] Django `DEBUG = False` in production
- [x] Secrets encrypted with Ansible Vault
- [x] `ALLOWED_HOSTS` properly configured
- [ ] Consider implementing fail2ban for brute force protection
- [ ] Regular security updates via `apt upgrade`

## Troubleshooting

### Authentication Issues
- Verify password in secrets.yml
- Check Traefik configuration: `/etc/traefik/dynamic/homelab.yml`
- Review Traefik logs: `journalctl -u traefik -f`

### Certificate Issues
- Check acme.json permissions: `ls -la /etc/traefik/acme/`
- Verify DNS is resolving correctly
- Check Traefik logs for Let's Encrypt errors

### Application Not Responding
- Check service status: `systemctl status homelab`
- Verify port 10010 is listening: `ss -tlnp | grep 10010`
- Check Django logs: `journalctl -u homelab -n 100`

## Backup and Recovery

### Automated Backups
Database backups are created automatically. To manually backup:
```bash
just backup
```

### Restore from Backup
```bash
# Copy backup to server
scp backup.sql.gz macmini.fritz.box:/tmp/

# Restore
ssh macmini.fritz.box
cd /home/homelab/site
gunzip -c /tmp/backup.sql.gz | sqlite3 db.sqlite3
```