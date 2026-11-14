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


## SQLite transactions

SQLite connections require Django 5.1+ and use Django's `OPTIONS["transaction_mode"] = "IMMEDIATE"`.
Atomic blocks acquire their write lock before admin validation reads, allowing
overlapping writers to wait and then detect a stale revision. This applies to
SQLite only; other database backends keep their existing options. Keep atomic
blocks short: SQLite still allows only one writer, and its normal lock timeout
can be exhausted. Test settings use the same transaction mode.

## Admin logo upload budget

Admin service logos are limited to **1 MiB (1,048,576 bytes)** per file.
The form rejects a declared oversize before reading the upload, then counts
actual chunks and stops before accepting an excess chunk. A bounded in-memory
snapshot supplies the save; misleading upload size metadata cannot bypass the
limit. A field error leaves the stored service, revision and previous logo intact.
The storage copy also checks the actual total before every write; if copying
fails after reserving a name, the existing allocation cleanup removes the new
partial file. Existing and shared logos retain their normal ownership rules.

This is an admin upload limit, not Django's memory-spooling threshold or a
request-body limit. Django may already have spooled the incoming request before
form validation; configure a request-body limit at the HTTP server if needed.
Direct ORM/storage writes and built-in seed assets do not pass through this form.

## Media revalidation

Django serves media from verified opened regular-file descriptors with `nosniff`
and a sandbox Content Security Policy, including conditional responses. Each
response carries `Last-Modified` and an opaque weak `ETag` derived from the opened
file's device, inode, size and nanosecond modification/change timestamps. The tag
identifies a filesystem generation rather than a content digest; replacing a file
or updating it within one second invalidates its previous tag without reading the
whole media file. It relies on the filesystem updating this metadata normally.
An already-open response continues to serve its opened generation after atomic
path replacement.

`If-None-Match` uses standard weak comparison, tag lists and `*`; matching GET/HEAD
requests return 304 with the same validators and hardening headers as 200.
`If-None-Match` takes precedence over `If-Modified-Since`. Date-only requests
conservatively receive the full response: second-resolution HTTP dates cannot
prove that the cached generation is current. Invalid or stale tags also receive
200. These guarantees apply to Django's media view; any separate media server
needs its own equivalent cache and security policy.
