import os
import shutil
import subprocess
import sys
from datetime import datetime
from typing import Dict, List, Optional
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization, hashes
from cryptography import x509
from cryptography.x509.oid import NameOID
from .config import Config
from .utils import ensure_dir, write_file


class AcmeService:
    def obtain_certificate(self, domains: List[str], provider_env: Dict[str, str]) -> Dict[str, bytes]:
        raise NotImplementedError


class SelfSignedService(AcmeService):
    def __init__(self, storage_dir: str) -> None:
        self.storage_dir = storage_dir

    def obtain_certificate(self, domains: List[str], provider_env: Dict[str, str]) -> Dict[str, bytes]:
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        key_pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )

        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Dev CA"),
            x509.NameAttribute(NameOID.COMMON_NAME, domains[0]),
        ])
        san = x509.SubjectAlternativeName([x509.DNSName(d) for d in domains])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow())
            .not_valid_after(datetime.utcnow().replace(microsecond=0) + timedelta(days=90))
            .add_extension(san, critical=False)
            .sign(key, hashes.SHA256())
        )
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        chain_pem = cert_pem
        fullchain_pem = cert_pem

        return {
            "private_key_pem": key_pem,
            "cert_pem": cert_pem,
            "chain_pem": chain_pem,
            "fullchain_pem": fullchain_pem,
        }


class CertbotManualDNSService(AcmeService):
    def __init__(self, config: Config) -> None:
        self.cfg = config

    def _ensure_certbot(self) -> None:
        if shutil.which(self.cfg.CERTBOT_BIN) is None:
            raise RuntimeError(
                f"'{self.cfg.CERTBOT_BIN}' not found. Please install certbot (https://certbot.eff.org/) or set CERTBOT_BIN."
            )

    def obtain_certificate(self, domains: List[str], provider_env: Dict[str, str]) -> Dict[str, bytes]:
        self._ensure_certbot()
        if not domains:
            raise ValueError("At least one domain is required")

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        hooks_dir = os.path.join(base_dir, "hooks")
        python_exe = sys.executable

        certbot_dirs = {
            "config": os.path.join(self.cfg.STORAGE_DIR, "certbot"),
            "work": os.path.join(self.cfg.STORAGE_DIR, "certbot", "work"),
            "logs": os.path.join(self.cfg.STORAGE_DIR, "certbot", "logs"),
        }
        for d in certbot_dirs.values():
            os.makedirs(d, exist_ok=True)

        cmd = [
            self.cfg.CERTBOT_BIN,
            "certonly",
            "--manual",
            "--preferred-challenges",
            "dns",
            "--manual-auth-hook",
            f"{python_exe} {os.path.join(hooks_dir, 'dns_auth.py')}",
            "--manual-cleanup-hook",
            f"{python_exe} {os.path.join(hooks_dir, 'dns_cleanup.py')}",
            "--agree-tos",
            "--email",
            self.cfg.ACME_EMAIL,
            "--server",
            self.cfg.ACME_DIRECTORY_URL,
            "--non-interactive",
            "--manual-public-ip-logging-ok",
            "--config-dir",
            certbot_dirs["config"],
            "--work-dir",
            certbot_dirs["work"],
            "--logs-dir",
            certbot_dirs["logs"],
        ]
        for d in domains:
            cmd.extend(["-d", d])

        env = os.environ.copy()
        env.update(provider_env)
        # Ensure our project path is importable by hooks
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        env["PYTHONPATH"] = f"{project_root}:{env.get('PYTHONPATH', '')}"
        # Pass DNS TTL and propagation settings to hooks
        env.setdefault("DNS_TTL", str(self.cfg.DNS_TTL))
        env.setdefault("DNS_PROPAGATION_TIMEOUT", str(self.cfg.DNS_PROPAGATION_TIMEOUT))
        env.setdefault("DNS_PROPAGATION_CHECK_INTERVAL", str(self.cfg.DNS_PROPAGATION_CHECK_INTERVAL))

        proc = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"Certbot failed: {proc.stderr or proc.stdout}")

        live_dir = os.path.join(certbot_dirs["config"], "live", domains[0])
        cert_path = os.path.join(live_dir, "cert.pem")
        chain_path = os.path.join(live_dir, "chain.pem")
        fullchain_path = os.path.join(live_dir, "fullchain.pem")
        key_path = os.path.join(live_dir, "privkey.pem")

        files = {}
        for key, path in (
            ("cert_pem", cert_path),
            ("chain_pem", chain_path),
            ("fullchain_pem", fullchain_path),
            ("private_key_pem", key_path),
        ):
            with open(path, "rb") as f:
                files[key] = f.read()
        return files


# For SelfSigned Service: missing timedelta import
from datetime import timedelta  # noqa: E402

