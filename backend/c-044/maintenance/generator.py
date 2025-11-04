import os
import re
import json
from dataclasses import dataclass
from typing import Dict, Any, List
from jinja2 import Environment, FileSystemLoader, StrictUndefined


class ValidationError(Exception):
    def __init__(self, message: str, details: Dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


def _is_abs(path: str) -> bool:
    try:
        return os.path.isabs(path)
    except Exception:
        return False


def _sanitize_job_name(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9_-]+", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    if not name:
        raise ValidationError("Invalid job_name after sanitization")
    return name


def _parse_schedule_to_cron(schedule: str) -> tuple[int, int]:
    # schedule in HH:MM 24h
    m = re.match(r"^(\d{2}):(\d{2})$", schedule)
    if not m:
        raise ValidationError("schedule must be HH:MM (24-hour)")
    hh, mm = int(m.group(1)), int(m.group(2))
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValidationError("schedule hour/minute out of range")
    return mm, hh


@dataclass
class GeneratorConfig:
    job_name: str
    schedule: str
    db: Dict[str, Any]
    backup: Dict[str, Any]
    vacuum: Dict[str, Any]
    logs: Dict[str, Any]


class MaintenanceGenerator:
    def __init__(self, base_output_dir: str):
        self.base_output_dir = base_output_dir
        tpl_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'scripts')
        self.env = Environment(
            loader=FileSystemLoader(tpl_dir),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=StrictUndefined,
        )

    def _validate(self, cfg: Dict[str, Any]) -> GeneratorConfig:
        errors: Dict[str, str] = {}
        job_name = cfg.get('job_name') or cfg.get('name') or 'eod-maintenance'
        try:
            job_name = _sanitize_job_name(str(job_name))
        except ValidationError as e:
            errors['job_name'] = str(e)

        schedule = cfg.get('schedule', '23:00')
        try:
            _parse_schedule_to_cron(schedule)
        except ValidationError as e:
            errors['schedule'] = str(e)

        db = cfg.get('db') or {}
        db_type = str(db.get('type', 'postgres')).lower()
        if db_type not in ('postgres', 'sqlite'):
            errors['db.type'] = 'supported types: postgres, sqlite'
        # minimal checks by type
        if db_type == 'postgres':
            for k in ('host', 'user', 'database'):
                if not db.get(k):
                    errors[f'db.{k}'] = 'required for postgres'
            db.setdefault('port', 5432)
        elif db_type == 'sqlite':
            if not db.get('sqlite_path'):
                errors['db.sqlite_path'] = 'required for sqlite'

        backup = cfg.get('backup') or {}
        backup.setdefault('output_dir', './backups')
        backup.setdefault('retention_days', 7)
        if not isinstance(backup['retention_days'], int) or backup['retention_days'] < 1:
            errors['backup.retention_days'] = 'must be int >= 1'

        vacuum = cfg.get('vacuum') or {}
        vacuum.setdefault('enabled', True)
        vacuum.setdefault('analyze', True)
        vacuum.setdefault('verbose', False)

        logs = cfg.get('logs') or {}
        logs.setdefault('enabled', True)
        logs.setdefault('directories', [])
        logs.setdefault('retention_days', 7)
        logs.setdefault('compress', True)
        if logs['enabled'] and not isinstance(logs['directories'], list):
            errors['logs.directories'] = 'must be a list of directories'

        if errors:
            raise ValidationError('Invalid configuration', errors)

        return GeneratorConfig(
            job_name=job_name,
            schedule=schedule,
            db=db,
            backup=backup,
            vacuum=vacuum,
            logs=logs,
        )

    def _write(self, path: str, content: str, mode: int | None = None):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        if mode is not None:
            os.chmod(path, mode)

    def _render(self, tpl_name: str, context: Dict[str, Any]) -> str:
        return self.env.get_template(tpl_name).render(**context)

    def _build_env_content(self, cfg: GeneratorConfig) -> str:
        lines: List[str] = []
        lines.append(f"DB_TYPE={cfg.db.get('type')}")
        if cfg.db.get('type') == 'postgres':
            lines.append(f"PGHOST={cfg.db.get('host')}")
            lines.append(f"PGPORT={cfg.db.get('port', 5432)}")
            lines.append(f"PGUSER={cfg.db.get('user')}")
            # Password may be optional if using .pgpass or peer auth; still include placeholder
            pgpass = cfg.db.get('password', '')
            # Escape any newlines
            pgpass = str(pgpass).replace('\n', '')
            lines.append(f"PGPASSWORD={pgpass}")
            lines.append(f"PGDATABASE={cfg.db.get('database')}")
        elif cfg.db.get('type') == 'sqlite':
            lines.append(f"SQLITE_PATH={cfg.db.get('sqlite_path')}")
        return "\n".join(lines) + "\n"

    def generate(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        validated = self._validate(cfg)
        mm, hh = _parse_schedule_to_cron(validated.schedule)
        job_dir = os.path.join(self.base_output_dir, validated.job_name)
        os.makedirs(job_dir, exist_ok=True)

        # Ensure standard subdirs exist
        os.makedirs(os.path.join(job_dir, 'logs'), exist_ok=True)
        os.makedirs(os.path.join(job_dir, 'backups'), exist_ok=True)

        # Build context for templates
        ctx = {
            'job_name': validated.job_name,
            'schedule': validated.schedule,
            'cron_minute': mm,
            'cron_hour': hh,
            'db': validated.db,
            'backup': validated.backup,
            'vacuum': validated.vacuum,
            'logs': validated.logs,
            'job_dir': job_dir,
        }

        # Render files
        maint_name = f"maintenance_{validated.job_name}.sh"
        install_name = f"install_cron_{validated.job_name}.sh"
        uninstall_name = f"uninstall_cron_{validated.job_name}.sh"

        maintenance_sh = self._render('maintenance.sh.j2', ctx)
        install_cron_sh = self._render('install_cron.sh.j2', ctx)
        uninstall_cron_sh = self._render('uninstall_cron.sh.j2', ctx)
        env_content = self._build_env_content(validated)

        # Write files
        maint_path = os.path.join(job_dir, maint_name)
        install_path = os.path.join(job_dir, install_name)
        uninstall_path = os.path.join(job_dir, uninstall_name)
        env_path = os.path.join(job_dir, '.env')

        self._write(maint_path, maintenance_sh, 0o750)
        self._write(install_path, install_cron_sh, 0o750)
        self._write(uninstall_path, uninstall_cron_sh, 0o750)
        self._write(env_path, env_content, 0o600)

        files = [
            {"path": maint_path, "content": maintenance_sh},
            {"path": install_path, "content": install_cron_sh},
            {"path": uninstall_path, "content": uninstall_cron_sh},
            {"path": env_path, "content": env_content},
        ]

        return {
            'job_name': validated.job_name,
            'output_dir': job_dir,
            'files': files,
        }

