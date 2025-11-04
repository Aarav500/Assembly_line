import os
from .utils import render_to_file, ensure_dir

SUPPORTED_CLOUDS = {'aws', 'gcp', 'azure'}

class TerraformGenerator:
    def generate(self, out_dir: str, manifest: dict):
        project = manifest.get('project', {})
        tf = manifest.get('terraform', {})
        cloud = (project.get('cloud') or 'aws').lower()
        if cloud not in SUPPORTED_CLOUDS:
            cloud = 'aws'
        region = project.get('region', 'us-east-1')

        tf_dir = os.path.join(out_dir, 'terraform', cloud)
        ensure_dir(tf_dir)

        # versions.tf
        render_to_file(
            'terraform/common/versions.tf.j2',
            os.path.join(tf_dir, 'versions.tf'),
            {}
        )

        backend = (tf.get('backend') or {})
        backend_ctx = { 'backend': backend, 'region': region }
        # backend.tf
        render_to_file(
            f'terraform/{cloud}/backend.tf.j2',
            os.path.join(tf_dir, 'backend.tf'),
            backend_ctx
        )

        # providers.tf
        providers_ctx = { 'region': region, 'project': project }
        render_to_file(
            f'terraform/{cloud}/providers.tf.j2',
            os.path.join(tf_dir, 'providers.tf'),
            providers_ctx
        )

        # variables.tf
        variables_ctx = { 'project': project }
        render_to_file(
            f'terraform/{cloud}/variables.tf.j2',
            os.path.join(tf_dir, 'variables.tf'),
            variables_ctx
        )

        # main.tf
        render_to_file(
            f'terraform/{cloud}/main.tf.j2',
            os.path.join(tf_dir, 'main.tf'),
            { 'project': project }
        )

