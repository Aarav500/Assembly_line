import os
import shutil
import subprocess
from typing import Dict, Optional

try:
    import clamd  # type: ignore
except Exception:  # pragma: no cover
    clamd = None


class VirusScanner:
    def __init__(
        self,
        mode: str = "clamscan",
        clamd_unix_socket: Optional[str] = None,
        clamd_host: Optional[str] = None,
        clamd_port: Optional[int] = None,
        clamscan_path: str = "/usr/bin/clamscan",
    ) -> None:
        self.mode = mode
        self._clamd_client = None
        self._clamscan_path = clamscan_path
        self._clamd_unix_socket = clamd_unix_socket
        self._clamd_host = clamd_host
        self._clamd_port = clamd_port

        if self.mode not in {"clamscan", "clamd", "auto"}:
            self.mode = "clamscan"

        if self.mode == "auto":
            if self._init_clamd():
                self.mode = "clamd"
            elif shutil.which(self._clamscan_path) or shutil.which("clamscan"):
                self.mode = "clamscan"
            else:
                self.mode = "clamscan"  # default fallback
        elif self.mode == "clamd":
            if not self._init_clamd():
                self.mode = "clamscan"

    def _init_clamd(self) -> bool:
        if clamd is None:
            return False
        try:
            if self._clamd_unix_socket and os.path.exists(self._clamd_unix_socket):
                self._clamd_client = clamd.ClamdUnixSocket(self._clamd_unix_socket)  # type: ignore
                self._clamd_client.ping()
                return True
            if self._clamd_host and self._clamd_port:
                self._clamd_client = clamd.ClamdNetworkSocket(self._clamd_host, self._clamd_port)  # type: ignore
                self._clamd_client.ping()
                return True
        except Exception:
            self._clamd_client = None
        return False

    def scan_file(self, path: str, timeout: int = 60) -> Dict[str, str]:
        if self.mode == "clamd" and self._clamd_client is not None:
            try:
                res = self._clamd_client.scan(path)
                # res format: {'/path/file': ('FOUND', 'Signature')} or ('OK', None)
                if not res or path not in res:
                    return {"status": "error", "signature": "no_result"}
                status, sig = res[path]
                if status == "FOUND":
                    return {"status": "infected", "signature": sig or "malware"}
                return {"status": "clean", "signature": "OK"}
            except Exception:
                return {"status": "error", "signature": "clamd_exception"}

        # Fallback to clamscan CLI
        exe = self._clamscan_path if shutil.which(self._clamscan_path) else shutil.which("clamscan") or "clamscan"
        try:
            proc = subprocess.run(
                [exe, "--no-summary", "--infected", path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
                text=True,
            )
            # Return codes: 0 = no virus found, 1 = virus found, 2 = error
            if proc.returncode == 0:
                return {"status": "clean", "signature": "OK"}
            if proc.returncode == 1:
                signature = "malware"
                # Try to parse signature from stdout (format: path: Threat FOUND)
                out = proc.stdout.strip().splitlines()
                if out:
                    last = out[-1]
                    if ":" in last and " FOUND" in last:
                        try:
                            signature = last.split(":", 1)[1].strip().removesuffix(" FOUND").strip()
                        except Exception:
                            pass
                return {"status": "infected", "signature": signature}
            return {"status": "error", "signature": "scan_failed"}
        except subprocess.TimeoutExpired:
            return {"status": "error", "signature": "timeout"}
        except Exception:
            return {"status": "error", "signature": "exception"}

