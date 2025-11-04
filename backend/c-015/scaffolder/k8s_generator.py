import os
from .utils import render_to_file, ensure_dir, sanitize_name

class K8sGenerator:
    def generate(self, out_dir: str, manifest: dict):
        k8s = manifest.get('k8s', {})
        ns = sanitize_name(k8s.get('namespace') or manifest.get('project', {}).get('name') or 'default')
        k8s_dir = os.path.join(out_dir, 'k8s')
        ensure_dir(k8s_dir)

        # namespace
        render_to_file(
            'k8s/namespace.yaml.j2',
            os.path.join(k8s_dir, '00-namespace.yaml'),
            {'namespace': ns}
        )

        # deployments
        for i, d in enumerate(k8s.get('deployments', []) or []):
            ctx = {
                'namespace': ns,
                'deployment': d,
                'name': sanitize_name(d.get('name') or f'app-{i+1}')
            }
            render_to_file(
                'k8s/deployment.yaml.j2',
                os.path.join(k8s_dir, f"10-deployment-{ctx['name']}.yaml"),
                ctx
            )

        # services
        for i, s in enumerate(k8s.get('services', []) or []):
            ctx = {
                'namespace': ns,
                'service': s,
                'name': sanitize_name(s.get('name') or f'svc-{i+1}')
            }
            render_to_file(
                'k8s/service.yaml.j2',
                os.path.join(k8s_dir, f"20-service-{ctx['name']}.yaml"),
                ctx
            )

        # ingress
        if (k8s.get('ingress') or {}).get('enabled'):
            render_to_file(
                'k8s/ingress.yaml.j2',
                os.path.join(k8s_dir, '30-ingress.yaml'),
                {'namespace': ns, 'ingress': k8s['ingress']}
            )

