import os
import re
import json
from datetime import datetime
from typing import Dict, List, Optional
from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound as JinjaTemplateNotFound


class TemplateNotFound(Exception):
    pass


class InvalidRequest(Exception):
    pass


class TemplateManager:
    def __init__(self, templates_root: str, metadata_path: str):
        self.templates_root = templates_root
        self.metadata_path = metadata_path
        self._metadata = self._load_metadata()

        self.env = Environment(
            loader=FileSystemLoader(self.templates_root),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
        )
        # Jinja helpers
        self.env.filters['slugify'] = self._slugify

    def _load_metadata(self) -> Dict:
        if not os.path.exists(self.metadata_path):
            raise FileNotFoundError(f"Metadata not found at {self.metadata_path}")
        with open(self.metadata_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # validate minimal structure
        if 'templates' not in data or not isinstance(data['templates'], list):
            raise ValueError('Invalid metadata: missing templates list')
        return data

    def list_templates(self) -> List[Dict]:
        res = []
        for t in self._metadata['templates']:
            res.append({
                'key': t['key'],
                'name': t['name'],
                'category': t.get('category'),
                'description': t.get('description'),
                'tags': t.get('tags', [])
            })
        return res

    def get_template(self, key: str) -> Dict:
        tpl = next((t for t in self._metadata['templates'] if t['key'] == key), None)
        if not tpl:
            raise TemplateNotFound(f"Template '{key}' not found")
        # discover available components by listing .j2 files
        dir_path = os.path.join(self.templates_root, key)
        if not os.path.isdir(dir_path):
            raise TemplateNotFound(f"Template directory for '{key}' not found")
        components = self._discover_components(dir_path)
        tpl = dict(tpl)  # shallow copy
        tpl['components'] = components
        return tpl

    def render_template(self, key: str, params: Optional[Dict] = None, include: Optional[List[str]] = None) -> Dict[str, str]:
        if not key:
            raise InvalidRequest("Missing 'template' key")
        tpl_meta = self.get_template(key)  # validates key exists
        dir_path = os.path.join(self.templates_root, key)

        # normalize/merge params
        merged_params = self._apply_defaults(tpl_meta, params or {})
        context = self._build_context(key, merged_params)

        # discover files to render
        components = self._discover_components(dir_path)
        selected = include or [c['id'] for c in components]
        selected_set = set(selected)

        files_to_render = []
        for comp in components:
            if comp['id'] in selected_set:
                files_to_render.append(comp)

        if not files_to_render:
            raise InvalidRequest('No components selected to render')

        rendered: Dict[str, str] = {}
        for comp in files_to_render:
            for j2_rel in comp['templates']:
                out_rel = self._output_path_from_template(j2_rel)
                try:
                    template = self.env.get_template(os.path.join(key, j2_rel))
                except JinjaTemplateNotFound as e:
                    raise TemplateNotFound(f"Missing template file: {e}")
                content = template.render(params=context['params'], meta=context['meta'])
                rendered[out_rel] = content
        return rendered

    def _discover_components(self, dir_path: str) -> List[Dict]:
        # map recognized component ids -> file name prefixes
        mapping = {
            'docker-compose': ['docker-compose.j2'],
            'k8s': ['k8s-deployment.j2'],
            'terraform': ['terraform-main.j2'],
            'docs': ['README.j2']
        }
        components = []
        all_files = set(os.listdir(dir_path)) if os.path.isdir(dir_path) else set()
        for comp_id, expected in mapping.items():
            templates_found = [f for f in expected if f in all_files]
            if templates_found:
                components.append({
                    'id': comp_id,
                    'name': comp_id.title(),
                    'templates': templates_found
                })
        return components

    def _apply_defaults(self, tpl_meta: Dict, user_params: Dict) -> Dict:
        # build default dictionary from metadata "parameters"
        defaults = {}
        for p in tpl_meta.get('parameters', []):
            defaults[p['name']] = p.get('default')
        merged = {**defaults, **user_params}
        # basic required check
        missing_required = [p['name'] for p in tpl_meta.get('parameters', []) if p.get('required') and merged.get(p['name']) in (None, '')]
        if missing_required:
            raise InvalidRequest(f"Missing required parameters: {', '.join(missing_required)}")
        return merged

    def _build_context(self, key: str, params: Dict) -> Dict:
        project_name = params.get('project_name') or key
        slug = self._slugify(params.get('project_slug') or project_name)
        now = datetime.utcnow().isoformat() + 'Z'
        meta = {
            'template_key': key,
            'generated_at': now,
            'project_slug': slug,
            'namespace': params.get('namespace') or slug,
        }
        # derived values
        params = dict(params)
        params.setdefault('project_name', project_name)
        params.setdefault('project_slug', slug)
        params.setdefault('namespace', meta['namespace'])
        params.setdefault('replicas', 2)
        params.setdefault('region', params.get('region') or 'us-east-1')
        return {'params': params, 'meta': meta}

    def _output_path_from_template(self, j2_rel: str) -> str:
        base = os.path.basename(j2_rel)
        name = base.replace('.j2', '')
        # map specific names
        if name == 'docker-compose':
            return 'docker/docker-compose.simple.yml'
        if name == 'k8s-deployment':
            return 'k8s/deployment.yaml'
        if name == 'terraform-main':
            return 'terraform/main.tf'
        if name.upper() == 'README':
            return 'README.md'
        # default yaml
        return name + '.yaml'

    def _slugify(self, value: str) -> str:
        if not value:
            return ''
        value = value.lower().strip()
        value = re.sub(r'[^a-z0-9\-]+', '-', value)
        value = re.sub(r'-{2,}', '-', value)
        return value.strip('-')

