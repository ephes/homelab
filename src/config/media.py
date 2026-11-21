"""
Hardened media file serving.

Homelab serves ``MEDIA_ROOT`` from Django in every environment (low traffic,
no separate media server). Uploaded files such as SVG service logos would
otherwise be rendered same-origin when opened directly, so every media
response is locked down:

- ``X-Content-Type-Options: nosniff`` stops browsers from guessing a more
  dangerous content type.
- ``Content-Security-Policy: sandbox; default-src 'none'; ...`` makes a media
  document opened directly (for example an SVG with embedded script) run in an
  opaque origin with scripts and outbound loads disabled. Embedding the files
  via ``<img>`` (how logos are shown on the dashboard) is unaffected.

Paths resolving outside ``MEDIA_ROOT`` are rejected; internal symlinks are
supported by resolving them once, then walking the canonical path without
following links. Only the verified opened regular file is streamed, and only
if it has exactly one hard link: a second name could make a file from outside
``MEDIA_ROOT`` look like media without any symlink to resolve.

Every descriptor acquired while opening has exactly one owner at a time and is
retired at most once. ``close()`` may release a descriptor even when it reports
an error, so a failed close is never retried; on a failure path, cleanup errors
never replace the original failure.
"""

import mimetypes
import os
import posixpath
import stat
from hashlib import sha256
from io import BufferedReader, FileIO
from pathlib import Path

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404, HttpResponseNotModified
from django.utils.http import http_date, parse_etags

MEDIA_CONTENT_SECURITY_POLICY = "sandbox; default-src 'none'; img-src data:; style-src 'unsafe-inline'"


_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK


def _retire_descriptor(descriptor):
    """Close a descriptor once on a failure path, keeping the caller's error."""
    try:
        os.close(descriptor)
    except OSError:
        # The number may already be released; retrying could close a reused fd.
        pass


def _retire_file(owner):
    """Close a file object once on a failure path, keeping the caller's error."""
    try:
        owner.close()
    except OSError:
        # FileIO marks itself closed before close(2), so it never retries.
        pass


def _open_raw_file(path):
    """Return a ``FileIO`` owning ``path``, opened without following links."""
    # Walk from the filesystem anchor, including MEDIA_ROOT's ancestors, so
    # O_NOFOLLOW protects every component rather than just the final filename.
    directory = os.open(path.anchor, _DIRECTORY_FLAGS)
    try:
        for part in path.parts[1:-1]:
            child = os.open(part, _DIRECTORY_FLAGS, dir_fd=directory)
            # Transfer ownership before retiring the parent: if close() fails,
            # the parent is gone either way and only the child remains ours.
            parent, directory = directory, child
            os.close(parent)
        descriptor = os.open(path.name, _FILE_FLAGS, dir_fd=directory)
        try:
            raw = FileIO(descriptor, "rb")
        except BaseException:
            # FileIO leaves a supplied descriptor open if construction fails.
            _retire_descriptor(descriptor)
            raise
    except BaseException:
        _retire_descriptor(directory)
        raise
    try:
        os.close(directory)
    except BaseException:
        # The directory close was attempted once; only the file is still ours.
        _retire_file(raw)
        raise
    return raw


def _open_regular_file(path):
    """Open a canonical single-link regular file without following replacement links (POSIX)."""
    expected = path.stat()
    if not stat.S_ISREG(expected.st_mode):
        raise Http404("Media path is not a regular file")
    raw = _open_raw_file(path)
    try:
        source = BufferedReader(raw)
    except BaseException:
        # A wrapper may already have closed raw during failed construction;
        # closing the owning object again is safe even if the fd was reused.
        _retire_file(raw)
        raise
    try:
        opened = os.fstat(source.fileno())
        if not stat.S_ISREG(opened.st_mode) or not os.path.samestat(expected, opened):
            raise Http404("Media file changed while opening")
        # Admit only files whose sole name is the verified media path: another
        # hard link may live outside MEDIA_ROOT without any symlink to resolve.
        if opened.st_nlink != 1:
            raise Http404("Media file has additional hard links")
    except BaseException:
        _retire_file(source)
        raise
    return source, opened


def _if_none_match_hits(request, etag: str) -> bool:
    """Weak If-None-Match comparison (RFC 9110 13.1.2) for GET/HEAD."""
    if request.method not in ("GET", "HEAD"):
        return False
    header = request.META.get("HTTP_IF_NONE_MATCH")
    if not header:
        return False
    tags = parse_etags(header)
    if "*" in tags:
        return True
    opaque = etag.removeprefix("W/")
    return any(tag.removeprefix("W/") == opaque for tag in tags)


def serve_media(request, path):
    """Serve a file from ``MEDIA_ROOT`` with hardening headers."""
    # Match Django's static path normalization, then check symlink targets.
    normalized_path = posixpath.normpath(path).lstrip("/")
    if ".." in Path(normalized_path).parts:
        raise SuspiciousFileOperation("Media path traversal")
    try:
        root = Path(settings.MEDIA_ROOT).resolve()
        resolved_path = (root / normalized_path).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise Http404("Invalid media path") from exc
    if not resolved_path.is_relative_to(root):
        raise Http404("Media path outside root")
    try:
        source, opened = _open_regular_file(resolved_path)
    except (OSError, ValueError) as exc:
        raise Http404("Media file unavailable") from exc
    try:
        # Bind a weak validator to the verified descriptor's generation, without
        # exposing raw filesystem identifiers or hashing unbounded media bytes.
        generation = (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns)
        etag = f'W/"{sha256(str(generation).encode("ascii")).hexdigest()}"'
        headers = {
            "ETag": etag,
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": MEDIA_CONTENT_SECURITY_POLICY,
        }
        try:
            headers["Last-Modified"] = http_date(opened.st_mtime)
        except (OverflowError, OSError, ValueError):
            # The timestamp can fall outside the HTTP-date formatter's range.
            pass
        # Only If-None-Match is evaluated: an HTTP date cannot distinguish
        # generations within the same second, and a weak validator cannot
        # satisfy If-Match, so other preconditions keep serving full content.
        if _if_none_match_hits(request, etag):
            response = HttpResponseNotModified(headers=headers)
        else:
            content_type, encoding = mimetypes.guess_type(normalized_path)
            if encoding:
                headers["Content-Encoding"] = encoding
            return FileResponse(
                source,
                content_type=content_type or "application/octet-stream",
                filename=normalized_path,
                headers=headers,
            )
    except BaseException:
        _retire_file(source)
        raise
    source.close()
    return response
