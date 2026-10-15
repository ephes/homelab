# Traefik Basic Authentication

Traefik and its configuration for homelab are managed by ops-control (see
[deployment](deployment.md)). The ops-library `homelab_deploy` role renders
`/etc/traefik/dynamic/homelab.yml` on macmini.

## How it works

The config uses the dual router pattern:

- **Internal router** (higher priority): requests from LAN and Tailscale ranges
  reach the app without basic auth.
- **External router**: every other request needs the shared `*.home`
  basic-auth credentials (user `admin`, bcrypt hash in the config).

The same credentials protect the other `*.home` services on macmini.

## Credentials and rotation

The password is stored in ops-control `secrets/prod/traefik.yml`
(`basic_auth_password`, SOPS-encrypted). To rotate it, set a new value there
and run, in ops-control:

```bash
just rotate-traefik-basic-auth
```

That refreshes the hash in every deployed service config that uses the shared
password. ops-control `docs/TRAEFIK_SECURITY.md` lists the covered services.

## Testing

```bash
# Public request without credentials: 401
curl -I https://home.xn--wersdrfer-47a.de/

# With credentials: 200 (enter the password when curl prompts for it)
curl -I -u admin https://home.xn--wersdrfer-47a.de/

# Deployed configuration
ssh root@macmini.tailde2ec.ts.net 'cat /etc/traefik/dynamic/homelab.yml'
```

### Client IP on the Connection Info page
`/connection-info/` shows the client address and a Tailscale/Local/Public badge. The app runs behind a
single Traefik hop, so it reads the **rightmost** `X-Forwarded-For` entry, the one Traefik appends for the
connection it received, and falls back to `REMOTE_ADDR` when the header is missing or that entry is not an
IP address. Entries further left are sent by the client and can be spoofed, so they are ignored. If another
proxy is ever added in front of Traefik, this rule must change. The page is for display only; any future
application-level auth bypass must likewise trust only the proxy-appended entry.
