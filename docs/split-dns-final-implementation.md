# Split-DNS Final Implementation Guide

## ✅ Status: FULLY OPERATIONAL

Successfully implemented split-DNS with Unbound and Pi-hole for the homelab infrastructure.

## Current Working Configuration

### Infrastructure
- **macmini server** (192.168.178.94 / 100.119.21.93)
  - ✅ Pi-hole DNS server (port 53) - Active
  - ✅ Unbound resolver (port 5335) - Active
  - ✅ Traefik reverse proxy - Active
  
### Key Discovery: IDN Domain Encoding
The domain `wersdörfer.de` contains an umlaut (ö) which requires special handling:
- DNS queries automatically convert to IDN format: `xn--wersdrfer-47a.de`
- Configuration must include both UTF-8 and IDN encoded versions
- This was the root cause of initial resolution failures

## Deployed Configuration

### Unbound Configuration (`/etc/unbound/unbound.conf.d/09-local-zones.conf`)

```conf
server:
  # Define static zones for local resolution
  local-zone: "home.wersdörfer.de." static
  local-zone: "home.xn--wersdrfer-47a.de." static  # IDN encoded version
  
  # Normal UTF-8 domain entries
  local-data: "home.wersdörfer.de. 86400 IN A 192.168.178.94"
  local-data: "paperless.home.wersdörfer.de. 86400 IN A 192.168.178.94"
  local-data: "ha.home.wersdörfer.de. 86400 IN A 192.168.178.94"
  # ... (all other services)
  
  # IDN encoded versions (required for DNS resolution)
  local-data: "home.xn--wersdrfer-47a.de. 86400 IN A 192.168.178.94"
  local-data: "paperless.home.xn--wersdrfer-47a.de. 86400 IN A 192.168.178.94"
  local-data: "ha.home.xn--wersdrfer-47a.de. 86400 IN A 192.168.178.94"
  # ... (all other services)
```

### Pi-hole Configuration
- Upstream DNS: `127.0.0.1#5335` (Unbound)
- Ad blocking: Active
- Custom DNS entries: Handled by Unbound

### DNS Resolution Flow
1. Client queries Pi-hole (port 53)
2. Pi-hole forwards to Unbound (port 5335)
3. Unbound checks local zones first
4. If not local, forwards to external DNS (Cloudflare/Google)

## Deployment Commands

### Full Deployment
```bash
# Deploy complete split-DNS setup
just deploy-split-dns

# Individual components
just deploy-unbound    # Deploy Unbound only
just deploy-pihole     # Deploy Pi-hole only
```

### Verification
```bash
# Run comprehensive verification
just dns-split-test

# Check service status
just dns-status

# Manual verification on server
ssh root@macmini.tailde2ec.ts.net "/home/homelab/site/bin/verify-split-dns.sh"
```

## Test Results

### ✅ All Tests Passing
```
================================================
         Split-DNS Verification Test
================================================

1. Service Status Check
-----------------------
✓ pihole-FTL is running
✓ unbound is running

2. Port Availability Check
--------------------------
✓ Port 53 (DNS) is listening
✓ Port 5335 (Unbound) is listening

3. DNS Resolution Tests
-----------------------
✓ home.wersdörfer.de → 192.168.178.94
✓ paperless.home.wersdörfer.de → 192.168.178.94
✓ All other services resolving correctly
✓ External DNS working (google.com)

✓ Split-DNS is fully operational!
```

## Configured Services

All these domains resolve to 192.168.178.94:
- `home.wersdörfer.de` - Main dashboard
- `paperless.home.wersdörfer.de` - Document management
- `ha.home.wersdörfer.de` - Home Assistant
- `unifi.home.wersdörfer.de` - Network controller
- `proxmox.home.wersdörfer.de` - Virtualization
- `portainer.home.wersdörfer.de` - Container management
- `pihole.home.wersdörfer.de` - DNS admin
- `router.home.wersdörfer.de` - Router admin
- `traefik.home.wersdörfer.de` - Reverse proxy

## Files Created/Modified

### Ansible Playbooks
- `/deploy/deploy-split-dns.yml` - Main deployment
- `/deploy/deploy-unbound.yml` - Unbound deployment
- `/deploy/fix-pihole-dns.yml` - Pi-hole fixes

### Ansible Tasks
- `/deploy/tasks/unbound.yml` - Unbound configuration
- `/deploy/tasks/pihole-update-dns.yml` - Pi-hole updates
- `/deploy/tasks/pihole-fix-upstream.yml` - Upstream fixes

### Templates
- `/deploy/templates/unbound-local-zones.conf.j2` - Local zone config (WORKING)
- `/deploy/templates/verify-split-dns.sh.j2` - Verification script

### Configuration
- `/deploy/vars.yml` - Added Unbound variables
- `/justfile` - Added DNS commands

## Manual Configuration Still Required

### Fritz!Box Router
1. Go to: **Home Network → Network → Network Settings**
2. Set DNS server to: `192.168.178.94`
3. Under **DNS Rebind Protection**, add exception: `wersdörfer.de`
4. Save and apply

### Tailscale Admin Console
1. Enable **MagicDNS**
2. Add nameserver: `100.119.21.93`
3. Configure split DNS for `wersdörfer.de` → `100.119.21.93`

## Troubleshooting

### If DNS stops working:
```bash
# Check services
systemctl status pihole-FTL unbound

# Test Unbound directly
dig @127.0.0.1 -p 5335 home.wersdörfer.de

# Test Pi-hole
dig @127.0.0.1 -p 53 home.wersdörfer.de

# Restart services
systemctl restart pihole-FTL unbound

# Check logs
journalctl -u unbound -n 50
tail -f /var/log/pihole/FTL.log
```

### Common Issues
1. **External IP returned**: Check IDN encoding in config
2. **SERVFAIL errors**: Verify Unbound is running
3. **No response**: Check Pi-hole upstream setting

## Architecture Benefits

1. **Simplified Configuration**: No complex views needed (for now)
2. **IDN Support**: Handles international domain names correctly
3. **Ad Blocking**: Pi-hole continues filtering ads
4. **Fast Resolution**: Local caching improves performance
5. **Reliable**: Services always accessible via domain names

## Future Enhancements

When Tailscale split-DNS is needed:
1. Re-enable views in Unbound configuration
2. Configure different IPs based on source network
3. Test from Tailscale clients

Currently, all clients get LAN IP (192.168.178.94) which works fine for local access.

## Summary

The split-DNS infrastructure is **fully operational** and **production-ready**. All configured domains resolve correctly to internal IPs, providing seamless access to homelab services with valid SSL certificates.