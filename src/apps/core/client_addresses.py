"""Client address selection and classification shared by login and diagnostics."""

import ipaddress

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
TAILSCALE_NETWORKS = (ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("fd7a:115c:a1e0::/48"))


def client_address(request, *, unknown: str = "unknown") -> str:
    """Use Traefik's rightmost forwarded entry, or fall back to the socket address."""
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    candidate = forwarded_for[forwarded_for.rfind(",") + 1 :].strip()
    if candidate:
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            pass
    return request.META.get("REMOTE_ADDR") or unknown


def canonical_ip(address: str) -> IPAddress | None:
    """Parse an address, treating IPv4-mapped IPv6 as IPv4."""
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def is_tailscale(ip: IPAddress) -> bool:
    return any(ip in network for network in TAILSCALE_NETWORKS)
