# Changelog

## Unreleased

- Preserve owner edits and competing logos made while default-service logos are
  copied; attach only the missing logo and revision and retire unused allocations.
- Return a controlled media 404 when resolving the media root fails.
- Serve media from a verified regular-file descriptor; refuse replacement
  symlinks and changed file identities while preserving internal links,
  conditional requests and hardening headers.
- Protect existing admin logo ownership and rollback/commit behavior with a
  local-only routed, two-database test lane (`just test-admin-logos`).
