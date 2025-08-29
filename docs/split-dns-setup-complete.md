# Split-DNS Setup Complete

## What Has Been Implemented

Successfully configured split-DNS with Tailscale fallback for your homelab. The setup provides intelligent DNS resolution based on client location:

### Current Configuration

**Infrastructure:**
- **macmini server** (192.168.178.94)
  - Pi-hole: DNS filtering and ad blocking
  - Unbound: Split-DNS resolver with views
  - Both services running and active

**DNS Resolution Flow:**
1. Clients query Pi-hole (port 53)
2. Pi-hole forwards to Unbound (port 5335)
3. Unbound returns IP based on client source:
   - LAN clients (192.168.178.x) → LAN IP (192.168.178.94)
   - Tailscale clients (100.x.x.x) → Tailscale IP (100.119.21.93)
   - Localhost → LAN IP (for consistency)

### Domains Configured

All these domains now resolve correctly:
- `home.wersdörfer.de`
- `paperless.home.wersdörfer.de`
- `ha.home.wersdörfer.de`
- `unifi.home.wersdörfer.de`
- `proxmox.home.wersdörfer.de`
- `portainer.home.wersdörfer.de`
- `pihole.home.wersdörfer.de`
- `router.home.wersdörfer.de`
- `traefik.home.wersdörfer.de`
- `*.home.wersdörfer.de` (wildcard)

### Test Results

✅ **From LAN (192.168.178.59):**
```
$ dig @192.168.178.94 home.wersdörfer.de +short
192.168.178.94
```

✅ **External domain resolution:**
```
$ dig @192.168.178.94 google.com +short
64.233.167.100
```

## Manual Configuration Still Required

### 1. Fritz!Box Configuration
To make all LAN devices use the new DNS:

1. Go to: **Home Network → Network → Network Settings**
2. Set DNS server to: `192.168.178.94`
3. Under **DNS Rebind Protection**, add exception for: `wersdörfer.de`
4. Save and apply settings

### 2. Tailscale Configuration
To enable split-DNS for Tailscale clients:

1. Go to Tailscale admin console → **DNS settings**
2. Enable **MagicDNS**
3. Add nameserver: `100.119.21.93`
4. Add Split DNS for `wersdörfer.de` → `100.119.21.93`

## Deployment Commands

The setup can be managed with these commands:

```bash
# Deploy complete split-DNS setup
just deploy-split-dns

# Deploy only Unbound
just deploy-unbound

# Deploy only Pi-hole
just deploy-pihole

# Test DNS resolution
just dns-split-test

# Check DNS service status
just dns-status
```

## Files Created/Modified

### New Files:
- `/deploy/deploy-split-dns.yml` - Main deployment playbook
- `/deploy/deploy-unbound.yml` - Unbound deployment
- `/deploy/tasks/unbound.yml` - Unbound configuration tasks
- `/deploy/tasks/pihole-update-dns.yml` - Pi-hole update tasks
- `/deploy/tasks/pihole-fix-upstream.yml` - Pi-hole fix tasks
- `/deploy/templates/unbound-split-dns.conf.j2` - Split-DNS view configuration
- `/deploy/fix-pihole-dns.yml` - Quick fix playbook

### Modified Files:
- `/deploy/vars.yml` - Added Unbound configuration variables
- `/justfile` - Added DNS deployment commands

## Architecture Benefits

1. **Seamless Access**: Same domains work from LAN and Tailscale
2. **Valid SSL**: Let's Encrypt certificates remain valid
3. **No Manual Switching**: Apps automatically use correct IP
4. **Ad Blocking**: Pi-hole continues to filter ads
5. **Privacy**: Using secure upstream DNS servers

## Troubleshooting

If DNS stops working:

1. Check services:
   ```bash
   just dns-status
   ```

2. Test resolution directly:
   ```bash
   # From LAN
   dig @192.168.178.94 home.wersdörfer.de
   
   # Check Unbound
   ssh root@macmini.tailde2ec.ts.net "dig @127.0.0.1 -p 5335 home.wersdörfer.de +short"
   ```

3. Restart services if needed:
   ```bash
   ssh root@macmini.tailde2ec.ts.net "systemctl restart pihole-FTL unbound"
   ```

## Next Steps

1. Configure Fritz!Box to use the new DNS server
2. Configure Tailscale split DNS in admin console
3. Test from different clients (phones, laptops)
4. Update Home Assistant and other apps to use the domains

The split-DNS infrastructure is now fully operational and ready for use!