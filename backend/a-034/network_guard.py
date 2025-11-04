import os
import socket
from ipaddress import ip_address
from typing import Tuple


_original_socket_connect = None
_original_create_connection = None
_guard_enabled = False


def _is_local_host(host: str) -> bool:
    if not host:
        return False
    host_l = host.lower()
    if host_l in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        ip = ip_address(host_l)
        return ip.is_loopback
    except ValueError:
        # Hostname that's not literal IP; deny to avoid DNS and outbound
        return False


def _normalize_addr(address) -> Tuple[str, int]:
    # address may be (host, port) for IPv4 or (host, port, flowinfo, scopeid) for IPv6
    if isinstance(address, tuple):
        if len(address) >= 2:
            return (address[0], int(address[1]))
    return (str(address), 0)


def _guarded_connect(self, address):
    host, _ = _normalize_addr(address)
    if not _is_local_host(host):
        raise RuntimeError(f'Outbound network access is disabled by privacy mode: attempted to connect to {host}')
    return _original_socket_connect(self, address)


def _guarded_create_connection(address, timeout=None, source_address=None):
    host, _ = _normalize_addr(address)
    if not _is_local_host(host):
        raise RuntimeError(f'Outbound network access is disabled by privacy mode: attempted to connect to {host}')
    return _original_create_connection(address, timeout, source_address)


def activate_privacy_mode():
    global _original_socket_connect, _original_create_connection, _guard_enabled
    if _guard_enabled:
        return

    # Clear proxy env vars to avoid accidental proxying
    for k in [
        'HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'https_proxy',
        'ALL_PROXY', 'all_proxy', 'FTP_PROXY', 'ftp_proxy']:
        os.environ.pop(k, None)
    # Ensure local no-proxy
    existing_no_proxy = os.environ.get('NO_PROXY') or os.environ.get('no_proxy') or ''
    no_proxy_hosts = set([h.strip() for h in existing_no_proxy.split(',') if h.strip()])
    no_proxy_hosts.update({'localhost', '127.0.0.1', '::1'})
    os.environ['NO_PROXY'] = ','.join(sorted(no_proxy_hosts))

    # Patch socket connect methods
    if _original_socket_connect is None:
        _original_socket_connect = socket.socket.connect
    if _original_create_connection is None:
        _original_create_connection = socket.create_connection

    socket.socket.connect = _guarded_connect  # type: ignore
    socket.create_connection = _guarded_create_connection  # type: ignore

    _guard_enabled = True


def privacy_mode_active() -> bool:
    return _guard_enabled

