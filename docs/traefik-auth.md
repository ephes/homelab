# Traefik Basic Authentication

This document describes the basic authentication setup for the homelab Traefik reverse proxy.

## Overview

The Traefik configuration implements basic authentication that:
- **Requires authentication** for all access to the homelab site
- **Applies to all users** including those on Tailscale VPN
- **Uses bcrypt** for secure password hashing

## Configuration Files

### `deploy/vars.yml`
```yaml
# Basic auth configuration
traefik_basic_auth_user: "admin"
# Password is stored in secrets.yml (encrypted with ansible-vault)

# Tailscale IP range (reserved for future conditional auth)
tailscale_ip_range: "100.64.0.0/10"
```

### `deploy/secrets.yml` (Encrypted)
```yaml
traefik_basic_auth_password: "YOUR_SECURE_PASSWORD"
```

### `deploy/templates/homelab.traefik.yml.j2`
Contains the router configuration with:
- `basic-auth` middleware for access control
- Security headers and compression

## Setup Instructions

### 1. Set Your Password

Edit the encrypted secrets file:
```bash
cd deploy
ansible-vault edit secrets.yml
```

Replace `CHANGE_ME_SECURE_PASSWORD_123` with your actual password.

### 2. Deploy the Configuration

```bash
ansible-playbook -i inventory/hosts.yml deploy-traefik.yml --ask-vault-pass
```

### 3. Test the Setup

```bash
# Should return 401 Unauthorized
curl -I https://home.wersdörfer.de

# Should return 200 OK with valid credentials
curl -I -u admin:YOUR_PASSWORD https://home.wersdörfer.de
```

## Security Considerations

1. **Password Storage**: Passwords are encrypted using Ansible Vault
2. **Password Hashing**: Uses bcrypt hashing (most secure option for basic auth)
3. **HTTPS Only**: Authentication only happens over encrypted connections
4. **Universal Protection**: All access requires authentication

## Troubleshooting

### Authentication Not Working
- Check if the password was correctly set in `secrets.yml`
- Verify the Traefik configuration was deployed: `ssh macmini.fritz.box 'cat /etc/traefik/dynamic/homelab.yml'`
- Check Traefik logs: `ssh macmini.fritz.box 'sudo journalctl -u traefik -f'`

### Testing Authentication
Use the provided test script:
```bash
./deploy/test-auth.sh
```

### Viewing Current Configuration
```bash
# On the macmini server
sudo cat /etc/traefik/dynamic/homelab.yml
```

## Known Limitations

### Conditional Authentication
The initial plan to bypass authentication for Tailscale IPs while requiring it for external IPs encountered Traefik limitations:
- The `ClientIP` matcher in router rules returns 403 Forbidden for non-matching IPs rather than falling through to other routers
- Traefik doesn't support OR logic between routers for conditional middleware application

### Future Options for Conditional Auth
If you want to implement Tailscale bypass in the future:
1. **ForwardAuth Service**: Create a small service that checks IPs and returns 200 for Tailscale, 401 for others
2. **Traefik Plugin**: Use or develop a plugin for conditional authentication
3. **Application Level**: Handle auth bypass in your Django application based on client IP

## Changing Credentials

To change the username or password:
1. Update `traefik_basic_auth_user` in `deploy/vars.yml` for username changes
2. Update `traefik_basic_auth_password` in `deploy/secrets.yml` for password changes
3. Redeploy with `ansible-playbook -i inventory/hosts.yml deploy-traefik.yml --ask-vault-pass`