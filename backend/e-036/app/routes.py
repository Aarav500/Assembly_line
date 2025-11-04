import json
import os
from typing import List
from flask import Blueprint, current_app, request
from . import db
from .models import Domain
from .tasks import task_manager
from .acme_service import SelfSignedService, CertbotManualDNSService
from .dns_providers import provider_from_env
from .utils import ensure_dir, write_file, sanitize_domain_folder
from cryptography import x509


api_bp = Blueprint("api", __name__)


@api_bp.post("/domains")
def create_domain():
    data = request.get_json(force=True, silent=True) or {}
    name = data.get("name")
    if not name:
        return {"error": "name is required"}, 400

    provider_spec = data.get("provider") or {}
    provider_name = provider_spec.get("name")
    provider_config = provider_spec.get("config") or {}

    if Domain.query.filter_by(name=name).first():
        return {"error": "domain already exists"}, 409

    domain = Domain(name=name, provider_name=provider_name, provider_config=provider_config, status="new")
    db.session.add(domain)
    db.session.commit()
    return domain.to_dict(), 201


@api_bp.get("/domains")
def list_domains():
    return {"domains": [d.to_dict() for d in Domain.query.order_by(Domain.created_at.desc()).all()]}


@api_bp.get("/domains/<int:domain_id>")
def get_domain(domain_id: int):
    domain = Domain.query.get_or_404(domain_id)
    return domain.to_dict()


def _issue_cert_task(app, domain_id: int, alt_names: List[str]):
    with app.app_context():
        domain = Domain.query.get(domain_id)
        if not domain:
            raise RuntimeError("Domain not found")

        names = [domain.name] + [n for n in (alt_names or []) if n and n != domain.name]

        # Build provider env to be consumed by hook scripts
        provider_env = {
            "DNS_PROVIDER": (domain.provider_name or current_app.config["DNS_PROVIDER"]).lower(),
            "PROVIDER_CONFIG_JSON": json.dumps(domain.provider_config or {}),
            "CLOUDFLARE_API_TOKEN": (domain.provider_config or {}).get("api_token") or current_app.config.get("CLOUDFLARE_API_TOKEN", ""),
        }

        if current_app.config.get("ENABLE_SELF_SIGNED"):
            svc = SelfSignedService(current_app.config["STORAGE_DIR"])  # type: ignore[arg-type]
        else:
            svc = CertbotManualDNSService(current_app.config)  # type: ignore[arg-type]

        try:
            domain.status = "provisioning"
            domain.last_error = None
            db.session.commit()

            # Ensure DNS provider construction succeeds early
            provider_from_env(default_name=provider_env["DNS_PROVIDER"], config=domain.provider_config)

            result = svc.obtain_certificate(names, provider_env)

            storage_dir = os.path.join(current_app.config["STORAGE_DIR"], "certs", sanitize_domain_folder(domain.name))
            ensure_dir(storage_dir)
            key_path = os.path.join(storage_dir, "privkey.pem")
            cert_path = os.path.join(storage_dir, "cert.pem")
            chain_path = os.path.join(storage_dir, "chain.pem")
            fullchain_path = os.path.join(storage_dir, "fullchain.pem")

            write_file(key_path, result["private_key_pem"], 0o600)
            write_file(cert_path, result["cert_pem"], 0o644)
            write_file(chain_path, result.get("chain_pem", b""), 0o644)
            write_file(fullchain_path, result.get("fullchain_pem", b""), 0o644)

            # Parse expiration
            try:
                cert = x509.load_pem_x509_certificate(result["cert_pem"])
                not_after = cert.not_valid_after.replace(tzinfo=None)
            except Exception:  # noqa: BLE001
                not_after = None

            domain.cert_path = cert_path
            domain.key_path = key_path
            domain.chain_path = chain_path
            domain.fullchain_path = fullchain_path
            domain.status = "ready"
            domain.not_after = not_after
            db.session.commit()
            return {"domain_id": domain.id, "status": domain.status, "paths": {
                "cert": cert_path,
                "key": key_path,
                "chain": chain_path,
                "fullchain": fullchain_path,
            }}
        except Exception as e:  # noqa: BLE001
            domain.status = "error"
            domain.last_error = str(e)
            db.session.commit()
            raise


@api_bp.post("/domains/<int:domain_id>/issue_cert")
def issue_cert(domain_id: int):
    domain = Domain.query.get_or_404(domain_id)
    data = request.get_json(force=True, silent=True) or {}
    alt_names = data.get("alt_names", [])

    job_id = task_manager.submit(_issue_cert_task, current_app._get_current_object(), domain.id, alt_names)  # type: ignore[arg-type]
    return {"job_id": job_id, "message": "certificate issuance started"}, 202


@api_bp.get("/jobs/<job_id>")
def get_job(job_id: str):
    return task_manager.get(job_id)

