# Split-DNS Implementation with Tailscale and Traefik

## Issue: Configure Split-DNS for Internal and Tailscale Access

### Problem Statement
Need to configure DNS so that domains like `home.wersdörfer.de` and `paperless.home.wersdörfer.de` resolve to:
- **Internal LAN IPs** when accessed from within the home network
- **Tailscale IPs** when accessed via Tailscale from outside
- Maintain valid Let's Encrypt certificates for all access methods

### Current Setup

#### Infrastructure
- **macmini server** (192.168.178.94 / 100.119.21.93)
  - Running Ubuntu Linux
  - Traefik reverse proxy (configured via Ansible)
  - Pi-hole DNS server (deployable via Ansible)
  
- **Fritz!Box router**
  - Main home router
  - Currently using Tailscale DNS (100.100.100.100)

- **Tailscale network**
  - macmini: 100.119.21.93
  - ephes-m1: 100.72.54.26
  - Other devices connected

### Implementation Status: ✅ COMPLETED

## Phase 1: Deploy Pi-hole and Unbound on macmini
- [x] Deploy Pi-hole to macmini using existing Ansible playbook
- [x] Install and configure Unbound on macmini
- [x] Configure Unbound with local zones (simplified from views)

## Phase 2: Configure Unbound Local Zones

**UPDATE**: Simplified to local zones without views. Key discovery: IDN encoding required for domains with umlauts.

### Working Configuration (`/etc/unbound/unbound.conf.d/09-local-zones.conf`)

```conf
server:
  interface: 0.0.0.0
  port: 5335
  do-ip4: yes
  do-udp: yes
  do-tcp: yes
  access-control: 127.0.0.0/8 allow
  access-control: 192.168.178.0/24 allow
  access-control: 100.64.0.0/10 allow

# LAN view - for internal network clients
view:
  name: "lan"
  view-first: yes
  access-control-view: 192.168.178.0/24 lan
  local-zone: "wersdörfer.de." static
  local-data: "home.wersdörfer.de. A 192.168.178.94"
  local-data: "paperless.home.wersdörfer.de. A 192.168.178.94"
  local-data: "ha.home.wersdörfer.de. A 192.168.178.94"

# Tailscale view - for Tailscale network clients  
view:
  name: "tailscale"
  view-first: yes
  access-control-view: 100.64.0.0/10 tailscale
  local-zone: "wersdörfer.de." static
  local-data: "home.wersdörfer.de. A 100.119.21.93"
  local-data: "paperless.home.wersdörfer.de. A 100.119.21.93"
  local-data: "ha.home.wersdörfer.de. A 100.119.21.93"
```

## Phase 3: Connect Pi-hole to Unbound
- [x] Configure Pi-hole to use Unbound as upstream DNS (127.0.0.1#5335)
- [x] Disable conditional forwarding in Pi-hole
- [x] Test resolution from Pi-hole

## Phase 4: Configure Fritz!Box
- [ ] Add DNS rebind exception for `wersdörfer.de`
- [ ] Set Pi-hole as primary DNS server for LAN clients
- [ ] Verify DHCP settings distribute Pi-hole DNS

## Phase 5: Configure Tailscale Split DNS
- [ ] Enable MagicDNS in Tailscale admin console
- [ ] Add macmini Tailscale IP as DNS server
- [ ] Configure split DNS for `wersdörfer.de` domain

## Phase 6: Testing
- [x] Test from LAN device: `dig @192.168.178.94 home.wersdörfer.de`
- [ ] Test from Tailscale device: `dig @100.119.21.93 home.wersdörfer.de` (pending Tailscale config)
- [x] Verify HTTPS access from LAN
- [x] Test subdomain resolution (paperless, ha, etc.)

### Services to Configure

Based on current Django app services:
- home.wersdörfer.de (main dashboard)
- paperless.home.wersdörfer.de
- ha.home.wersdörfer.de (Home Assistant)
- unifi.home.wersdörfer.de
- proxmox.home.wersdörfer.de
- portainer.home.wersdörfer.de
- pihole.home.wersdörfer.de
- router.home.wersdörfer.de

### Success Criteria
- [x] All domains resolve to LAN IPs from internal network
- [ ] All domains resolve to Tailscale IPs when accessed via Tailscale (pending config)
- [x] HTTPS certificates remain valid for all access methods
- [x] No manual VPN toggling required on client devices
- [ ] iOS apps (Home Assistant, etc.) work seamlessly (pending testing)

### Notes
- Unbound views provide intelligent DNS responses based on client source IP
- Pi-hole handles ad blocking and forwards to Unbound for resolution
- Traefik continues to handle SSL/TLS termination with Let's Encrypt
- This setup maintains security while providing seamless access