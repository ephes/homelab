"""Limit failed logins through Django authentication (the admin login is the only login form).

Two budgets apply to every username/password attempt, each over a fixed window:

- ``HOMELAB_LOGIN_FAILURE_LIMIT`` failures per username and client address;
- ``HOMELAB_LOGIN_ADDRESS_FAILURE_LIMIT`` failures per client address, for all usernames.

An attempt is charged against both budgets before the password is checked, in one
SQLite write transaction, so concurrent workers cannot exceed a budget. A successful
login refunds its charge and clears the username/address budget. An attempt that is
over a budget is refused without checking the password.

The client address is the last ``X-Forwarded-For`` entry: Traefik, the only proxy in
front of the app, appends the address it received the connection from; entries to its
left are client-supplied and ignored. Without the header (direct access to the
loopback port) ``REMOTE_ADDR`` is used. IPv6 addresses count per /64 network, since one
client usually owns a whole /64; IPv4-mapped IPv6 addresses count as their IPv4 address.
"""

import hashlib
import ipaddress
import time

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import PermissionDenied
from django.db import router, transaction
from django.db.models import F

from .models import LoginThrottleBucket

MAX_USERNAME = 150  # longer names are cut for the key; they cannot belong to an account
IPV6_BUCKET_PREFIX = 64
EXPIRED_ROWS_PER_ATTEMPT = 100


def client_address(request) -> str:
    """The address Traefik saw, or the socket address without a usable header."""
    candidate = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[-1].strip()
    if candidate:
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            pass
    return request.META.get("REMOTE_ADDR") or "unknown"


def throttle_bucket(address: str) -> str:
    """The budget an address counts against: IPv4 itself, IPv6 its /64."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return address
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return str(ip.ipv4_mapped)
        return str(ipaddress.IPv6Network((ip, IPV6_BUCKET_PREFIX), strict=False))
    return str(ip)


def _keys(request, username: str) -> tuple[str, str]:
    """The (username + address, address) bucket keys; values are hashed, never stored."""
    address = throttle_bucket(client_address(request))
    name = username[:MAX_USERNAME].casefold()
    pair = hashlib.sha256(f"{name}\x00{address}".encode()).hexdigest()
    return f"pair:{pair}", f"addr:{hashlib.sha256(address.encode()).hexdigest()}"


def _charge(request, username: str) -> tuple[str, tuple[tuple[str, float], ...]]:
    """Charge one attempt against both budgets, or refuse it; all or nothing."""
    alias = router.db_for_write(LoginThrottleBucket)
    buckets = LoginThrottleBucket.objects.using(alias)
    pair, address = _keys(request, username)
    limits = {pair: settings.HOMELAB_LOGIN_FAILURE_LIMIT, address: settings.HOMELAB_LOGIN_ADDRESS_FAILURE_LIMIT}
    charged = []
    # The settings open SQLite transactions IMMEDIATE: the write lock is held from
    # here to the end of the block, so the clock below is read after admission.
    with transaction.atomic(using=alias):
        now = time.time()
        expired = buckets.filter(expires_at__lte=now).values("pk")[:EXPIRED_ROWS_PER_ATTEMPT]
        buckets.filter(pk__in=expired).delete()
        # The address budget first: a refused address cannot create username rows.
        for key in (address, pair):
            buckets.filter(key=key, expires_at__lte=now).delete()
            bucket, _ = buckets.get_or_create(
                key=key, defaults={"expires_at": now + settings.HOMELAB_LOGIN_FAILURE_WINDOW_SECONDS}
            )
            if not buckets.filter(key=key, failures__lt=limits[key]).update(failures=F("failures") + 1):
                # Rolls back the charges made earlier in this transaction.
                raise PermissionDenied("Too many failed login attempts.")
            charged.append((key, bucket.expires_at))
    return alias, tuple(charged)


def _refund(charge, pair: str) -> None:
    """Undo a successful attempt's charge and clear its username/address budget."""
    alias, charged = charge
    buckets = LoginThrottleBucket.objects.using(alias)
    with transaction.atomic(using=alias):
        for key, expires_at in charged:
            # Only the window that was charged: a newer window owes nothing.
            window = buckets.filter(key=key, expires_at=expires_at, failures__gt=0)
            window.update(failures=0 if key == pair else F("failures") - 1)


class LoginThrottleBackend(ModelBackend):
    """``ModelBackend`` with failed-login budgets.

    ``ModelBackend`` stays configured after this backend so sessions created before
    the throttle remain valid. Every failed or refused attempt raises
    ``PermissionDenied``, so ``ModelBackend`` never checks the same password again
    without a charge.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(get_user_model().USERNAME_FIELD)
        if (
            request is None
            or not isinstance(username, str)
            or password is None
            or settings.HOMELAB_LOGIN_FAILURE_LIMIT <= 0
        ):
            return super().authenticate(request, username, password, **kwargs)
        charge = _charge(request, username)
        user = super().authenticate(request, username, password, **kwargs)
        if user is None:
            raise PermissionDenied("Invalid login.")
        _refund(charge, _keys(request, username)[0])
        return user

    async def aauthenticate(self, request, username=None, password=None, **kwargs):
        # ModelBackend's own async implementation would bypass the budgets.
        return await sync_to_async(self.authenticate)(request, username, password, **kwargs)
