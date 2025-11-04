from __future__ import annotations
import os
import pathlib
from typing import Any, Dict, Optional

try:
    import mlflow
except Exception:  # pragma: no cover - optional import handling
    mlflow = None

try:
    import wandb
except Exception:  # pragma: no cover
    wandb = None


class ExperimentTracker:
    def start_run(self, experiment_name: str, run_name: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> str:
        raise NotImplementedError

    def log_params(self, params: Dict[str, Any]) -> None:
        raise NotImplementedError

    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None) -> None:
        raise NotImplementedError

    def log_artifact(self, path: str, name: Optional[str] = None) -> None:
        raise NotImplementedError

    def end_run(self) -> None:
        raise NotImplementedError

    def get_run_url(self) -> Optional[str]:
        return None


class NoOpTracker(ExperimentTracker):
    def __init__(self):
        self._run_id = "noop"

    def start_run(self, experiment_name: str, run_name: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> str:
        return self._run_id

    def log_params(self, params: Dict[str, Any]) -> None:
        pass

    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None) -> None:
        pass

    def log_artifact(self, path: str, name: Optional[str] = None) -> None:
        pass

    def end_run(self) -> None:
        pass


class MLflowTracker(ExperimentTracker):
    def __init__(self):
        if mlflow is None:
            raise RuntimeError("mlflow is not installed")
        self._run = None

    def start_run(self, experiment_name: str, run_name: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> str:
        mlflow.set_experiment(experiment_name)
        self._run = mlflow.start_run(run_name=run_name)
        run_id = self._run.info.run_id
        if params:
            mlflow.log_params(_stringify_params(params))
        return run_id

    def log_params(self, params: Dict[str, Any]) -> None:
        mlflow.log_params(_stringify_params(params))

    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None) -> None:
        mlflow.log_metrics(metrics, step=step)

    def log_artifact(self, path: str, name: Optional[str] = None) -> None:
        p = pathlib.Path(path)
        if p.is_dir():
            mlflow.log_artifacts(str(p), artifact_path=name)
        else:
            mlflow.log_artifact(str(p), artifact_path=name)

    def end_run(self) -> None:
        mlflow.end_run()
        self._run = None

    def get_run_url(self) -> Optional[str]:
        if self._run is None:
            return None
        tracking_uri = mlflow.get_tracking_uri()
        run_id = self._run.info.run_id
        try:
            if tracking_uri and tracking_uri.startswith("http"):
                return f"{tracking_uri.rstrip('/')}/#/experiments/{self._run.info.experiment_id}/runs/{run_id}"
        except Exception:
            return None
        return None


class WandbTracker(ExperimentTracker):
    def __init__(self):
        if wandb is None:
            raise RuntimeError("wandb is not installed")
        self._run = None

    def start_run(self, experiment_name: str, run_name: Optional[str] = None, params: Optional[Dict[str, Any]] = None) -> str:
        # experiment_name is mapped to project in W&B
        self._run = wandb.init(project=experiment_name, name=run_name, config=params or {}, settings=wandb.Settings(silent=True))
        return self._run.id

    def log_params(self, params: Dict[str, Any]) -> None:
        if self._run is None:
            return
        # Update config; allow new keys
        self._run.config.update(params, allow_val_change=True)

    def log_metrics(self, metrics: Dict[str, float], step: Optional[int] = None) -> None:
        if self._run is None:
            return
        if step is not None:
            wandb.log(metrics, step=step)
        else:
            wandb.log(metrics)

    def log_artifact(self, path: str, name: Optional[str] = None) -> None:
        if self._run is None:
            return
        p = pathlib.Path(path)
        art_name = name or p.stem
        artifact = wandb.Artifact(name=art_name, type="artifact")
        if p.is_dir():
            artifact.add_dir(str(p))
        else:
            artifact.add_file(str(p))
        self._run.log_artifact(artifact)

    def end_run(self) -> None:
        if self._run is not None:
            wandb.finish()
            self._run = None

    def get_run_url(self) -> Optional[str]:
        try:
            return self._run.url if self._run is not None else None
        except Exception:
            return None


def get_tracker(name: str) -> ExperimentTracker:
    name = (name or "").lower().strip()
    if name in ("mlflow", "mlf"):
        return MLflowTracker()
    if name in ("wandb", "weightsandbiases", "weights_biases"):
        return WandbTracker()
    if name in ("none", "noop", "no-op"):
        return NoOpTracker()
    raise ValueError(f"Unknown tracker: {name}")


def _stringify_params(params: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for k, v in params.items():
        try:
            out[k] = str(v)
        except Exception:
            out[k] = repr(v)
    return out

