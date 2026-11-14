# Changelog

## Unreleased

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
