# Configuration

## Environment Variables

Copy `.env.example` to `.env` in the repository root (the directory that holds
`manage.py`) and adjust:

```bash
# Essential Settings
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1 # Read by the production settings
DATABASE_URL=sqlite:///db.sqlite3        # SQLite default

# Production Only
DJANGO_ADMIN_URL=secret-admin/           # Change from default
DJANGO_CACHE_LOCATION=/var/cache/homelab # Cache directory
```

### Where the dotenv file is read from

The settings read exactly one dotenv file: `<repository root>/.env`. In a
deployment that is `<site path>/.env`, next to `manage.py` and `pyproject.toml`.
The location does not depend on the working directory.

- Variables that are already exported in the process environment (a shell
  `export`, systemd's `EnvironmentFile`, CI variables) take precedence over
  the file. The file only fills in what is not set.
- `src/.env` is **not** read. Earlier versions read that file instead of the
  documented root file. If you still have a `src/.env`, move its contents to
  the root `.env`; the settings print a `RuntimeWarning` while it exists.
- After moving a previously ignored root `.env` into effect, check its
  `DATABASE_URL`, `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS`: they are used
  now.

### Debug mode and settings modules

Debug mode is chosen by the settings module, not by an environment variable:

| Settings module | `DEBUG` | Selected by |
|-----------------|---------|-------------|
| `config.settings.local` | `True` | `manage.py` (default), `just dev` |
| `config.settings.production` | `False` | `src/config/wsgi.py` (default) |
| `config.settings.test` | `False` | pytest |

There is no `DEBUG` or `DJANGO_DEBUG` variable; setting one has no effect. To
change the mode, export `DJANGO_SETTINGS_MODULE` in the process environment.
`DJANGO_SETTINGS_MODULE` in the dotenv file comes too late to select the
module, because the file is read by the settings module itself.

## Service Management

Add services via admin panel with:
- **Name**: Service display name
- **URL**: Full URL (include https://)
- **Icon**: Font Awesome class (e.g., `fas fa-cloud`)
- **Order**: Display position (lower = first)

Common icons:
- `fas fa-cloud` - Cloud storage
- `fas fa-server` - Generic server
- `fas fa-shield-alt` - Security
- `fas fa-home` - Home automation
- `fab fa-docker` - Docker

## Production Security

The production settings (`config.settings.production`) read these variables:

```bash
DJANGO_SECRET_KEY=<generate-new-key>
DJANGO_ALLOWED_HOSTS=yourdomain.com
DJANGO_SECURE_SSL_REDIRECT=True
```

- `DJANGO_SECRET_KEY` is required; production refuses to start without it.
- `DJANGO_ALLOWED_HOSTS` is a comma-separated list.
- `DJANGO_SECURE_SSL_REDIRECT` defaults to `True`.
- `DEBUG` is always `False` in production and cannot be switched on through
  the environment.

Unprefixed names such as `SECRET_KEY`, `ALLOWED_HOSTS` or
`SECURE_SSL_REDIRECT` are Django setting names, not environment variables;
exporting them has no effect.

Serve the application from `src.config.wsgi:application` (started in the
repository root). The older `homelab.wsgi:application` and
`homelab.asgi:application` paths still work and select the same production
configuration; the old `homelab.settings` module is retired and raises an
error when selected.

Run security check:
```bash
just manage check --deploy
```
