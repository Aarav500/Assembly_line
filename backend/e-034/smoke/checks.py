import time
import socket
import platform
import subprocess
from urllib.parse import urlparse

import requests

from .utils import ensure_host_allowed, unique, resolve_host_addrs
from config import HTTP_TIMEOUT, TCP_CONNECT_TIMEOUT, HTTP_VERIFY_TLS, HTTP_ALLOWED_SCHEMES, HTTP_USER_AGENT


def check_dns(host: str, timeout: float = 2.0) -> dict:
    t0 = time.perf_counter()
    try:
        ensure_host_allowed(host)
        addrs = resolve_host_addrs(host, timeout=timeout)
        elapsed = (time.perf_counter() - t0) * 1000.0
        return {
            "ok": True if addrs else False,
            "type": "dns",
            "host": host,
            "addresses": addrs,
            "elapsed_ms": round(elapsed, 2),
            "error": None if addrs else "no addresses resolved",
        }
    except Exception as e:
        elapsed = (time.perf_counter() - t0) * 1000.0
        return {
            "ok": False,
            "type": "dns",
            "host": host,
            "addresses": [],
            "elapsed_ms": round(elapsed, 2),
            "error": str(e),
        }


def check_tcp(host: str, port: int, timeout: float = TCP_CONNECT_TIMEOUT) -> dict:
    t0 = time.perf_counter()
    s = None
    peer_ip = None
    try:
        ensure_host_allowed(host)
        s = socket.create_connection((host, int(port)), float(timeout))
        try:
            peer = s.getpeername()
            if isinstance(peer, tuple):
                peer_ip = peer[0]
            else:
                peer_ip = str(peer)
        except Exception:
            peer_ip = None
        ok = True
        err = None
    except Exception as e:
        ok = False
        err = str(e)
    finally:
        if s:
            try:
                s.close()
            except Exception:
                pass
    elapsed = (time.perf_counter() - t0) * 1000.0
    return {
        "ok": ok,
        "type": "tcp",
        "host": host,
        "port": int(port),
        "resolved_ip": peer_ip,
        "elapsed_ms": round(elapsed, 2),
        "error": err,
    }


def check_http(url: str, method: str = "HEAD", timeout: float = HTTP_TIMEOUT, expect_status: int | None = None, allow_redirects: bool = True) -> dict:
    t0 = time.perf_counter()
    method = (method or "HEAD").upper()

    try:
        parsed = urlparse(url)
        if parsed.scheme not in HTTP_ALLOWED_SCHEMES:
            raise ValueError(f"scheme not allowed: {parsed.scheme}")
        host = parsed.hostname or ""
        if not host:
            raise ValueError("invalid URL: missing host")
        ensure_host_allowed(host)

        headers = {"User-Agent": HTTP_USER_AGENT}
        func = requests.request
        resp = func(method, url, timeout=float(timeout), allow_redirects=bool(allow_redirects), verify=HTTP_VERIFY_TLS, headers=headers)
        ok = (200 <= resp.status_code < 400)
        if expect_status is not None:
            ok = ok and (resp.status_code == expect_status)
        err = None if ok else f"unexpected status: {resp.status_code}"
        status_code = resp.status_code
    except Exception as e:
        status_code = None
        ok = False
        err = str(e)
    elapsed = (time.perf_counter() - t0) * 1000.0
    return {
        "ok": ok,
        "type": "http",
        "url": url,
        "method": method,
        "status_code": status_code,
        "elapsed_ms": round(elapsed, 2),
        "error": err,
    }


def check_icmp(host: str, timeout: float = 2.0, count: int = 1) -> dict:
    t0 = time.perf_counter()
    try:
        ensure_host_allowed(host)
        system = platform.system().lower()
        if system == "windows":
            # -n count, -w timeout in ms
            cmd = ["ping", "-n", str(int(count)), "-w", str(int(timeout * 1000)), host]
        else:
            # -c count, -W timeout in seconds (per reply)
            cmd = ["ping", "-c", str(int(count)), "-W", str(int(timeout)), host]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        ok = proc.returncode == 0
        err = None if ok else (proc.stderr.strip() or proc.stdout.strip() or "ping failed")
    except FileNotFoundError:
        ok = False
        err = "ping command not found on system"
    except Exception as e:
        ok = False
        err = str(e)
    elapsed = (time.perf_counter() - t0) * 1000.0
    return {
        "ok": ok,
        "type": "icmp",
        "host": host,
        "count": int(count),
        "elapsed_ms": round(elapsed, 2),
        "error": err,
    }

