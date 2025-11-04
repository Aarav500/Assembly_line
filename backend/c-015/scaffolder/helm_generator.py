import os
from .utils import render_to_file, sanitize_name, ensure_dir

class HelmGenerator:
    def generate(self, out_dir: str, manifest: dict):
        project = manifest.get('project', {})
        k8s = manifest.get('k8s', {})
        helm = manifest.get('helm', {})

        chart_name = sanitize_name(helm.get('chart', {}).get('name') or project.get('name') or 'app')
        version = helm.get('chart', {}).get('version', '0.1.0')
        app_version = helm.get('chart', {}).get('appVersion', '1.0.0')

        chart_dir = os.path.join(out_dir, 'helm', chart_name)
        ensure_dir(chart_dir)

        # Build values from manifest
        dpls = k8s.get('deployments', [])
        svc = None
        if k8s.get('services'):
            svc = k8s['services'][0]
        ingress = k8s.get('ingress', {}) or {}

        primary_image = None
        primary_env = {}
        primary_ports = []
        primary_resources = {}
        replica_count = 1
        if dpls:
            d0 = dpls[0]
            primary_image = d0.get('image', 'nginx:latest')
            primary_env = d0.get('env') or {}
            primary_ports = d0.get('ports') or []
            primary_resources = d0.get('resources') or {}
            replica_count = int(d0.get('replicas') or 1)

        values_ctx = {
            'name_override': helm.get('values', {}).get('nameOverride', ''),
            'fullname_override': helm.get('values', {}).get('fullnameOverride', ''),
            'replicaCount': replica_count,
            'image_repository': (primary_image or 'nginx:latest').split(':')[0],
            'image_tag': (primary_image.split(':')[1] if ':' in (primary_image or '') else 'latest'),
            'image_pull_policy': helm.get('values', {}).get('image', {}).get('pullPolicy', 'IfNotPresent'),
            'service_type': (svc or {}).get('type', 'ClusterIP'),
            'service_port': (svc or {}).get('port', 80),
            'service_target_port': (svc or {}).get('targetPort', None) or ((primary_ports or [80])[0]),
            'env': primary_env,
            'resources': primary_resources or {},
            'ingress': ingress or {},
            'podAnnotations': helm.get('values', {}).get('podAnnotations', {}),
            'podLabels': helm.get('values', {}).get('podLabels', {}),
            'nodeSelector': helm.get('values', {}).get('nodeSelector', {}),
            'tolerations': helm.get('values', {}).get('tolerations', []),
            'affinity': helm.get('values', {}).get('affinity', {}),
        }

        # Chart.yaml
        render_to_file(
            'helm/Chart.yaml.j2',
            os.path.join(chart_dir, 'Chart.yaml'),
            {'chart_name': chart_name, 'version': version, 'app_version': app_version}
        )
        # _helpers.tpl
        render_to_file(
            'helm/templates/_helpers.tpl.j2',
            os.path.join(chart_dir, 'templates', '_helpers.tpl'),
            {'chart_name': chart_name}
        )
        # values.yaml
        render_to_file(
            'helm/values.yaml.j2',
            os.path.join(chart_dir, 'values.yaml'),
            values_ctx
        )
        # templates
        render_to_file(
            'helm/templates/deployment.yaml.j2',
            os.path.join(chart_dir, 'templates', 'deployment.yaml'),
            {'chart_name': chart_name}
        )
        render_to_file(
            'helm/templates/service.yaml.j2',
            os.path.join(chart_dir, 'templates', 'service.yaml'),
            {'chart_name': chart_name}
        )
        render_to_file(
            'helm/templates/ingress.yaml.j2',
            os.path.join(chart_dir, 'templates', 'ingress.yaml'),
            {'chart_name': chart_name}
        )

