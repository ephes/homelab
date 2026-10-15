# Deployment

Homelab is deployed to macmini (`home.wersdörfer.de`) by
[ops-control](https://github.com/ephes/ops-control) with the `homelab_deploy`
role from [ops-library](https://github.com/ephes/ops-library). This repository
holds only the application; it contains no playbooks, inventory or secrets.

| What | Where |
|------|-------|
| Playbook | ops-control `playbooks/deploy-homelab.yml` |
| Role | ops-library `roles/homelab_deploy` |
| Django secret key | ops-control `secrets/prod/homelab.yml` (SOPS) |
| Shared basic-auth credentials | ops-control `secrets/prod/traefik.yml` (SOPS) |
| Backup, restore, removal | ops-control `playbooks/homelab/` |

The legacy Ansible setup that used to live in `deploy/` (playbooks, an
Ansible Vault `secrets.yml` and its password file) was removed. None of the
values that were in that vault are in use: production reads its Django secret
key and the basic-auth password from ops-control, and the old Gandi token was
retired. Never commit a vault password or any other secret here; `.gitignore`
blocks the usual vault password file names.

## Deploy

The recipes expect ops-control checked out next to this repository
(`../ops-control`). ops-control in turn reads the homelab source from
`$PROJECTS_ROOT/homelab` (by default the directory that contains ops-control):

```bash
just deploy    # cd ../ops-control && just deploy-one homelab
just remove    # cd ../ops-control && just remove-one homelab
```

Backups and restores also go through ops-control:

```bash
cd ../ops-control
just backup homelab
just restore homelab
```

## Components on macmini

- **Application**: `/home/homelab/site`, `homelab.service`, gunicorn on
  `127.0.0.1:10010`, SQLite database, environment in `/home/homelab/site/.env`
  (rendered by the role; see [configuration](configuration.md)).
- **Traefik**: the shared reverse proxy, deployed by ops-control. The role
  writes `/etc/traefik/dynamic/homelab.yml`.
- **DNS** (Unbound split DNS) and **dynamic DNS** (`ddns-update`, RFC 2136):
  ops-control, `just deploy-one dns` and `playbooks/deploy-dns.yml`.

## Basic authentication

Traefik uses the dual router pattern: requests from LAN and Tailscale ranges
reach the app without basic auth, public requests need the shared `*.home`
credentials. See [Traefik authentication](traefik-auth.md).

## Checks

```bash
# Public request without credentials: 401
curl -I https://home.xn--wersdrfer-47a.de/

# Service state on macmini
ssh root@macmini.tailde2ec.ts.net 'systemctl status homelab --no-pager'
ssh root@macmini.tailde2ec.ts.net 'journalctl -u homelab -n 50 --no-pager'
```

## Troubleshooting

- **401 from a public address**: the shared basic-auth password is required
  there. Check the credential, then `/etc/traefik/dynamic/homelab.yml` and
  `journalctl -u traefik`.
- **Application not responding**: `systemctl status homelab`,
  `ss -tlnp | grep 10010`, `journalctl -u homelab -n 100`.
- **Certificate issues**: certificates come from ops-control's certbot and
  Traefik setup; check the Traefik logs.
