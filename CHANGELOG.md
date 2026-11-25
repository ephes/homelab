# Changelog

## Unreleased

- Report the committed database and service total when seed output fails,
  preserving the committed logos.

- Use a single write-database snapshot for all batched service logo inventory
  lookups.

- Add a bounded, read-only `inventory_service_logos` command for finding files
  without a Service reference on the write database, including allocations
  left by an interrupted worker.

- Preserve HTTP 304 responses and their validators when closing the unused
  media reader raises an OS error.

- Update the development-only `virtualenv` lock entry (pulled in by
  pre-commit) to 21.14.13 for PYSEC-2026-4402, keeping the locked dependency
  audit clean.

- Continue retiring unreferenced admin logos when logging a failed reference
  lookup or file deletion raises.

- Reject incomplete admin logo uploads before allocating storage and preserve
  the previous logo.

- Preserve the original admin save error and continue logo cleanup when logging
  a failed upload cleanup raises.

- Require autocommit on the Service write database before seeding defaults and
  allocating logos.

- Delete individually confirmed services and retire their logos on the database
  bound to the admin confirmation.

- Validate service names, save new rows and handle logo uploads on the writer
  database for admin add and save-as-new submissions.

- Use the writer database for single-service edit submissions, including row
  lookup, validation, saving and logo cleanup.
- Show the usual admin login error when the throttle budget cannot be reserved.
  Refuse the attempt before checking the password.
- Verify the size and generation of packaged logos before attaching them and
  roll back seeding if a source changes during copying.
- Keep media streaming and ETag revalidation working when the modification
  timestamp cannot be formatted for Last-Modified.
- Limit the connection diagnostics' forwarded-header preview to 256 characters
  while keeping client address selection and classification intact.
- Keep quick-edit row selection, revision checks and saves on the writer
  database while routing ordinary list views as reads.
- Skip nonregular packaged service logos before allocating storage and keep the
  tile's icon fallback.
- Refuse admin login with the usual form error when the throttle refund fails
  after a correct password, even if logging the database error also fails.
  Keep the attempt charged in every budget.
- Keep bounded cleanup of expired login budgets when a full budget refuses an
  attempt and its charges are rolled back.
- Capture the default-service total inside the seed transaction so deferred
  output reflects that run and a count failure rolls back the seed.
- Check pending seed logo references in one query and retain the files if the
  lookup fails.
- Index stored service logo names for exact and bulk cleanup lookups. Apply
  migration `0021_service_logo_file_index` to add the index.
- Roll back default-service seeding when storage reports a short logo write and
  remove the partial file.
- Reject admin logo uploads when storage reports a short write, preserving the
  old logo and removing the partial file.
- Keep committed admin logo uploads when a callback fails after the writer
  transaction commits.
- Check shared logo references in one post-commit query after bulk admin deletion.

- Cover quick-edit retries after validation errors to ensure stale revisions
  still prevent the entire batch from saving.

- Warn when a default service falls back to its icon because the packaged logo is missing. FastDeploy
  no longer names a logo that was never packaged, so a default seed run stays quiet.

- Continue cleaning up unused seed logos and preserve the original seed error if stderr fails.

- Show the Tailscale badge for tailnet IPv6 and IPv4-mapped tailnet addresses in connection diagnostics.

- Keep newer login charges when an earlier successful password check clears its username/address budget.
  Migration `0020_login_throttle_charge_sequence` gives the new counter a database default, so
  workers still running the previous code during a deploy (or after a rollback) keep recording failures.

- Mark connection diagnostics private and no-store so each request gets its own report.

- Report default-service and logo seed results only after the database commits.

- Limit failed admin logins within 15 minutes: 5 per username and client
  address, 30 per client address and 100 per network (IPv4 /24, IPv6 /64;
  Tailscale addresses excepted) (`apps.core.login_throttle`, migration
  `0019_login_throttle_bucket`). LAN and Tailscale clients reach the admin login
  without Traefik basic auth, so password guessing was unlimited. Attempts are
  charged atomically before the password check; the client address is the one
  Traefik appended to `X-Forwarded-For`. A used-up network budget refuses every
  address in that network (Tailscale logins still work). Existing sessions
  stay valid.
- Production trusts no extra CSRF origins: the `https://*.home.wersdoerfer.de`
  wildcard (and its host entry) is gone; same-origin requests never needed it.
- Pin the Font Awesome stylesheet from cdnjs with Subresource Integrity
  (`crossorigin="anonymous"`, `referrerpolicy="no-referrer"`), so a changed CDN
  file cannot restyle pages or read the logout form's CSRF token.

- Replace the retired MinIO tile with RustFS: the default services offer `RustFS`
  (RustFS logo, no link because RustFS has no web console; the description names
  the S3 API `s3.home…`), and migration `0018_replace_minio_with_rustfs` turns an
  installed MinIO tile that still links to the MinIO console into it, keeping
  owner edits, active status and order. The unused `minio.png` seed logo is gone.

- Refuse media files with more than one hard link (404, also for conditional
  requests), so a second name inside `MEDIA_ROOT` cannot expose an outside file.
- Retire every directory and file descriptor exactly once when a `close()` fails
  while opening media; never retry a released number and keep the original error.

- Bind bulk admin deletion to one signed set of at most 500 displayed service
  revisions on the writer database; refuse the whole batch on changed/missing
  rows or altered selections before audit entries or logo cleanup.

- Bind single-service admin deletion to a signed, expiring displayed revision;
  refuse stale or invalid confirmations before audit entries and logo cleanup.

- Update the documentation parser lock to SoupSieve 4.1 and BeautifulSoup 4.15.0
  for the SoupSieve denial-of-service advisories, including CVE-2026-126190.
  The existing Python 3.12 minimum satisfies SoupSieve's Python 3.11.5 floor.

- Revalidate media with opaque opened-file generation ETags, preserving validators
  and hardening headers on 200/304; date-only requests conservatively return 200,
  and `If-Match`/`If-Unmodified-Since` are ignored instead of answering 412.
- Limit admin logo uploads to 1 MiB using declared and actual byte checks;
  preserve existing rows/logos on refusal and compensate partial storage copies.

- Docs: the OpsGate tile is inactive in production since OpsGate's retirement
  (2026-11-10); `add_default_services` keeps that status on later deploys.
- Close raw media descriptors when file-wrapper construction fails.
- Cover valid admin quick-edit batches with a second-save database failure,
  full row/revision and cleanup-callback rollback, and a successful retry.
- Preserve owner edits and competing logos made while default-service logos are
  copied; attach only the missing logo and revision and retire unused allocations.
- Return a controlled media 404 when resolving the media root fails.
- Serve media from a verified regular-file descriptor; refuse replacement
  symlinks and changed file identities while preserving internal links,
  conditional requests and hardening headers.
- Protect existing admin logo ownership and rollback/commit behavior with a
  local-only routed, two-database test lane (`just test-admin-logos`).
