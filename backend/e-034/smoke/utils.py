import re
import socket
import ipaddress
import time
from concurrent.futures import ThreadPoolExecutor

from config import ALLOWLIST_HOST_PATTERN, BLOCK_PRIVATE_IPS


def parse_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    s = str(val).strip().lower()
    return s in ("1", "true", "yes", "y", "on")


def is_ip_private(ip: str) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip)
        return (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_link_local
            or ip_obj.is_reserved
            or ip_obj.is_multicast
        )
    except ValueError:
        return False


def ensure_host_allowed(host: str):
    if not ALLOWLIST_HOST_PATTERN.search(host):
        raise ValueError("host not allowed by allowlist policy")
    if BLOCK_PRIVATE_IPS:
        # If host is an IP, check directly. If hostname, resolve quickly and check.
        try:
            ipaddress.ip_address(host)
            ips = [host]
        except ValueError:
            try:
                ips = resolve_host_addrs(host, timeout=2.0)
            except Exception:
                # If cannot resolve, let the underlying check raise the original error later
                ips = []
        for ip in ips:
            if is_ip_private(ip):
                raise ValueError("connection to private or loopback IPs blocked by policy")


def unique(seq):
    seen = set()
    out = []
    for x in seq:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def resolve_host_addrs(host: str, timeout: float = 2.0) -> list[str]:
    # Run getaddrinfo in a thread to implement timeout
    def _resolve():
        infos = socket.getaddrinfo(host, None)
        addrs = []
        for info in infos:
            sockaddr = info[4]
            addr = sockaddr[0] if isinstance(sockaddr, tuple) else None
            if addr:
                addrs.append(addr)
        return unique(addrs)

    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_resolve)
        return fut.result(timeout=timeout)

