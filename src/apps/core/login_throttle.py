"""Limit failed logins through Django authentication (the admin login is the only login form).

These budgets apply to every username/password attempt, each over a fixed window:

- ``HOMELAB_LOGIN_FAILURE_LIMIT`` failures per username and client address;
- ``HOMELAB_LOGIN_ADDRESS_FAILURE_LIMIT`` failures per client address, for all usernames;
- ``HOMELAB_LOGIN_NETWORK_FAILURE_LIMIT`` failures per IPv4 /24 or IPv6 /64 network, for
  all addresses in it, except Tailscale addresses (100.64.0.0/10, fd7a:115c:a1e0::/48).

An attempt is charged against every budget before the password is checked, in one
SQLite write transaction, so concurrent workers cannot exceed a budget. A successful
login refunds its charge and clears the username/address budget through its own
reservation, preserving later charges. An attempt that is
over a budget is refused without checking the password.

The client address is the last ``X-Forwarded-For`` entry: Traefik, the only proxy in
front of the app, appends the address it received the connection from; entries to its
left are client-supplied and ignored. Without the header (direct access to the
loopback port) ``REMOTE_ADDR`` is used. IPv4-mapped IPv6 addresses count as their IPv4
address.

The username and address budgets use the exact address, so a few failures on one LAN
device do not lock out the others. One client can however take many addresses in its
network (IPv4 aliases in the /24, any number of IPv6 addresses in its /64); the higher
network budget bounds that, and once it is used up every address in that network is
refused until the window ends. Tailscale assigns each node one address that WireGuard
authenticates, so tailnet addresses get no network budget and stay usable.
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
from django.db.models.functions import Least

from .models import LoginThrottleBucket

MAX_USERNAME = 150  # longer names are cut for the key; they cannot belong to an account
NETWORK_PREFIX = {4: 24, 6: 64}
TAILSCALE_NETWORKS = (ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("fd7a:115c:a1e0::/48"))
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


def throttle_address(address: str) -> str:
    """The address a client is counted as: IPv4-mapped IPv6 as its IPv4 address."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return address
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return str(ip.ipv4_mapped)
    return str(ip)


def throttle_network(address: str) -> str | None:
    """The /24 (IPv4) or /64 (IPv6) whose budget a non-Tailscale address shares, else None."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return None
    if any(ip in network for network in TAILSCALE_NETWORKS):
        return None
    return str(ipaddress.ip_network((ip, NETWORK_PREFIX[ip.version]), strict=False))


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _budgets(request, username: str) -> dict[str, int]:
    """Bucket key -> limit, coarsest first; keys are hashed, addresses never stored."""
    address = throttle_address(client_address(request))
    name = username[:MAX_USERNAME].casefold()
    budgets = {}
    network = throttle_network(address)
    if network is not None:
        budgets[f"net:{_digest(network)}"] = settings.HOMELAB_LOGIN_NETWORK_FAILURE_LIMIT
    budgets[f"addr:{_digest(address)}"] = settings.HOMELAB_LOGIN_ADDRESS_FAILURE_LIMIT
    pair = f"{name}\x00{address}"
    budgets[f"pair:{_digest(pair)}"] = settings.HOMELAB_LOGIN_FAILURE_LIMIT
    return budgets


def _charge(request, username: str) -> tuple[str, tuple[tuple[int, bool, int], ...]]:
    """Charge one attempt against every budget, or refuse it; all or nothing."""
    alias = router.db_for_write(LoginThrottleBucket)
    buckets = LoginThrottleBucket.objects.using(alias)
    limits = _budgets(request, username)
    charged = []
    # The settings open SQLite transactions IMMEDIATE: the write lock is held from
    # here to the end of the block, so the clock below is read after admission.
    with transaction.atomic(using=alias):
        now = time.time()
        expired = buckets.filter(expires_at__lte=now).values("pk")[:EXPIRED_ROWS_PER_ATTEMPT]
        buckets.filter(pk__in=expired).delete()
        # Coarsest budget first: a refused address cannot create username rows.
        for key, limit in limits.items():
            buckets.filter(key=key, expires_at__lte=now).delete()
            bucket, _ = buckets.get_or_create(
                key=key, defaults={"expires_at": now + settings.HOMELAB_LOGIN_FAILURE_WINDOW_SECONDS}
            )
            if not buckets.filter(pk=bucket.pk, failures__lt=limit).update(
                failures=F("failures") + 1, charge_sequence=F("charge_sequence") + 1
            ):
                # Rolls back the charges made earlier in this transaction.
                raise PermissionDenied("Too many failed login attempts.")
            charged.append((bucket.pk, key.startswith("pair:"), bucket.charge_sequence + 1))
    return alias, tuple(charged)


def _refund(charge) -> None:
    """Refund a success, clearing pair charges only through its reservation."""
    alias, charged = charge
    buckets = LoginThrottleBucket.objects.using(alias)
    with transaction.atomic(using=alias):
        for bucket_id, is_pair, sequence in charged:
            # A new window gets a new row and owes nothing to the old one.
            window = buckets.filter(pk=bucket_id, failures__gt=0)
            if is_pair:
                # The pair count covers the suffix since the newest successful
                # reservation. A later success may already have shortened it.
                window.update(failures=Least(F("failures"), F("charge_sequence") - sequence))
            else:
                window.update(failures=F("failures") - 1)


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
        _refund(charge)
        return user

    async def aauthenticate(self, request, username=None, password=None, **kwargs):
        # ModelBackend's own async implementation would bypass the budgets.
        return await sync_to_async(self.authenticate)(request, username, password, **kwargs)
