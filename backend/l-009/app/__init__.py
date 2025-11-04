import os
from flask import Flask
from .config import load_config
from .services.storage import LocalStorage
from .services.backup_service import BackupService
from .services.restore_service import RestoreService
from .services.retention import RetentionService
from .services.scheduler import SchedulerService
from .routes import api_bp


class ServiceContainer:
    def __init__(self, storage, backup, restore, retention, scheduler):
        self.storage = storage
        self.backup = backup
        self.restore = restore
        self.retention = retention
        self.scheduler = scheduler


def create_app(config_path: str | None = None) -> Flask:
    app = Flask(__name__)

    cfg = load_config(config_path)

    app.config.update(
        SECRET_KEY=cfg.get("app", {}).get("secret_key", os.environ.get("SECRET_KEY", "change-me")),
        HOST=cfg.get("app", {}).get("host", "0.0.0.0"),
        PORT=cfg.get("app", {}).get("port", 5000),
        APP_CONFIG=cfg,
    )

    # Storage
    storage_cfg = cfg.get("storage", {})
    backend = storage_cfg.get("backend", "local")
    if backend != "local":
        raise ValueError("Only local storage backend is supported in this build")
    base_path = storage_cfg.get("local", {}).get("base_path", "./data/backups")
    storage = LocalStorage(base_path)

    # Services
    backup = BackupService(storage=storage, backup_cfg=cfg.get("backup", {}))
    restore = RestoreService(storage=storage)
    retention = RetentionService(storage=storage, policy_cfg=cfg.get("retention", {}))

    # Scheduler
    scheduler = SchedulerService(backup=backup, retention=retention, storage=storage, drill_cfg=cfg.get("drill", {}), backup_cfg=cfg.get("backup", {}), retention_cfg=cfg.get("retention", {}))
    scheduler.start()

    services = ServiceContainer(storage=storage, backup=backup, restore=restore, retention=retention, scheduler=scheduler)
    app.extensions["services"] = services

    app.register_blueprint(api_bp, url_prefix="/api")

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        # Ensure scheduler stops on app teardown
        try:
            services.scheduler.shutdown()
        except Exception:
            pass

    return app

