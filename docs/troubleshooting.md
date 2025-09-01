# Troubleshooting

## Common Issues

### Port Already in Use
```bash
lsof -ti:8000 | xargs kill -9
# Or use different port
just manage runserver 8001
```

### Database Errors
```bash
# Missing tables
just db-migrate

# Database locked
rm db.sqlite3
just db-migrate
just createsuperuser
```

### Static Files Not Loading
```bash
# Development
DEBUG=True  # in .env

# Production
just collectstatic
```

### Module Not Found
```bash
just install
# Or
uv sync
```

## Production Issues

### Service Won't Start
```bash
sudo systemctl status homelab
sudo journalctl -u homelab -n 50

# Test manually
cd /home/homelab/site
.venv/bin/python manage.py runserver
```

### 500 Errors
1. Check logs: `sudo journalctl -u homelab -f`
2. Verify `ALLOWED_HOSTS` includes your domain
3. Ensure `DEBUG=False` in production
4. Run `just manage check --deploy`

### Database Locked
```bash
# Enable WAL mode
sqlite3 db.sqlite3 "PRAGMA journal_mode=WAL;"
```

## Admin Issues

### Can't Login
```bash
just manage shell
>>> from django.contrib.auth.models import User
>>> u = User.objects.get(username='admin')
>>> u.is_staff = True
>>> u.is_superuser = True
>>> u.save()
```

### Missing Styles
```bash
just collectstatic
# Check nginx/caddy serves /static/
```

## Quick Fixes

| Issue | Solution |
|-------|----------|
| Import errors | `export PYTHONPATH=$PYTHONPATH:$(pwd)/src` |
| CSRF token missing | Add `{% csrf_token %}` to forms |
| Permission denied | `sudo chown -R homelab:homelab /home/homelab/site` |
| High memory | Reduce Granian workers in systemd |

## DNS Issues

### Fritz!Box and Umlaut Domains (IDN) in DNS-Rebind Protection

#### The Problem
When using a Fritz!Box as DNS proxy in the home network, it enforces **DNS-Rebind protection**.  
This means DNS responses that resolve to **private IP addresses** (e.g. 192.168.x.x) are suppressed unless explicitly allowed.

If you use domains with **umlauts (IDN / Internationalized Domain Names)** such as:
```
paperless.home.wersdörfer.de
```

the Fritz!Box **cannot match these domains directly** in the DNS-Rebind exception list.  
That is because DNS queries are transmitted internally in **punycode** form, not in UTF-8.

#### Example
Querying with punycode works:
```bash
$ host paperless.home.xn--wersdrfer-47a.de 192.168.178.1
paperless.home.xn--wersdrfer-47a.de has address 192.168.178.94
```

Querying with umlauts fails:
```bash
$ host paperless.home.wersdörfer.de 192.168.178.1
;; no response
```

#### Solution
Always configure **punycode versions** of your domains in the Fritz!Box
under **Heimnetz → Netzwerk → Netzwerkeinstellungen → DNS-Rebind-Schutz**.

For example, instead of:
- `home.wersdörfer.de`
- `*.home.wersdörfer.de`

use:
- `home.xn--wersdrfer-47a.de`
- `*.home.xn--wersdrfer-47a.de`

#### Notes
- Applications and browsers can still use the **umlaut domain** – they automatically convert it to punycode before doing DNS lookups
- Traefik and Let's Encrypt certificates work fine with the umlaut form
- The Fritz!Box requires punycode exceptions to allow DNS answers pointing to internal IPs
- To convert domains to punycode: `echo "wersdörfer.de" | idn2`

## Getting Help

1. Check logs: `just logs`
2. Run tests: `just test`
3. Django check: `just check`
4. Debug mode: Use `breakpoint()`