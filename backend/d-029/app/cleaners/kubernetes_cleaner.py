import logging

from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes.client.exceptions import ApiException

from .base import BaseCleaner, CleanupResult

logger = logging.getLogger(__name__)


class KubernetesNamespaceCleaner(BaseCleaner):
    def __init__(self, settings):
        super().__init__(settings, name="kubernetes-namespace")
        self.namespace_template = settings.k8s_namespace_template
        self.k8s_context = settings.k8s_context
        self._api = None

    def _ensure_client(self):
        if self._api is not None:
            return
        try:
            # Try in-cluster first
            k8s_config.load_incluster_config()
        except Exception:
            # Fallback to kubeconfig
            if self.k8s_context:
                k8s_config.load_kube_config(context=self.k8s_context)
            else:
                k8s_config.load_kube_config()
        self._api = k8s_client.CoreV1Api()

    def cleanup(self, ctx: dict) -> CleanupResult:
        ns = self.settings.format_template(self.namespace_template, ctx)
        self._ensure_client()
        if self.dry_run:
            logger.info("[dry-run] Would delete Kubernetes namespace %s", ns)
            return {
                "name": self.name,
                "ok": True,
                "details": {"namespace": ns, "dry_run": True},
            }
        try:
            self._api.delete_namespace(name=ns)
            return {"name": self.name, "ok": True, "details": {"namespace": ns}}
        except ApiException as e:
            if e.status == 404:
                logger.info("Namespace %s does not exist; nothing to delete", ns)
                return {"name": self.name, "ok": True, "details": {"namespace": ns, "skipped": "not_found"}}
            return {"name": self.name, "ok": False, "error": f"{e.status} {e.reason}"}

