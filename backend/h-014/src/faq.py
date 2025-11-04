import re
from typing import List, Dict

import config


class FAQGenerator:
    def __init__(self):
        # map common headings to question templates
        self.heading_templates = {
            'installation': 'How do I install {project}?',
            'install': 'How do I install {project}?',
            'setup': 'How do I set up {project}?',
            'getting started': 'How do I get started with {project}?',
            'usage': 'How do I use {project}?',
            'configure': 'How do I configure {project}?',
            'configuration': 'How do I configure {project}?',
            'build': 'How do I build {project}?',
            'run': 'How do I run {project}?',
            'test': 'How do I run tests for {project}?',
            'troubleshooting': 'How can I troubleshoot issues in {project}?',
            'faq': 'Frequently asked questions about {project}',
        }

    def _normalize(self, s: str) -> str:
        return re.sub(r'\s+', ' ', (s or '').strip())

    def _guess_project_name(self, documents: List[Dict], fallback: str) -> str:
        # Prefer README top heading
        for d in documents:
            if d.get('type') == 'doc-section' and d.get('source_file', '').lower().startswith('readme') and d.get('title'):
                title = d.get('title').strip()
                if title:
                    return title
        return fallback

    def _select_section_faqs(self, documents: List[Dict], project_name: str) -> List[Dict]:
        items: List[Dict] = []
        seen_heading = set()
        for d in documents:
            if d.get('type') != 'doc-section':
                continue
            heading = (d.get('title') or '').strip()
            if not heading or heading.lower() in seen_heading:
                continue
            key = heading.lower()
            seen_heading.add(key)
            template = None
            # find matching template by keyword
            for k, t in self.heading_templates.items():
                if k in key:
                    template = t
                    break
            if not template:
                # generic question from heading
                normalized = heading.rstrip('?')
                q = f"How do I {normalized.lower()}?"
            else:
                q = template.format(project=project_name)
            answer = d.get('content', '')[:config.MAX_FAQ_ANSWER_CHARS]
            if answer:
                items.append({
                    'question': self._normalize(q),
                    'answer': self._normalize(answer),
                    'source_file': d.get('source_file'),
                    'section': heading
                })
        return items

    def _select_function_faqs(self, documents: List[Dict]) -> List[Dict]:
        items: List[Dict] = []
        count = 0
        for d in documents:
            if d.get('type') in ('docstring-function', 'docstring-class'):
                name = d.get('title') or 'this'
                q = f"What does {name} do?"
                answer = d.get('content', '').split('\n\n')[0]
                if not answer:
                    continue
                items.append({
                    'question': self._normalize(q),
                    'answer': self._normalize(answer[:config.MAX_FAQ_ANSWER_CHARS]),
                    'source_file': d.get('source_file'),
                    'section': name
                })
                count += 1
                if count >= config.MAX_FUNCTION_FAQS:
                    break
        return items

    def generate(self, documents: List[Dict], project_name: str) -> List[Dict]:
        proj = self._guess_project_name(documents, project_name)
        faqs = []
        faqs.extend(self._select_section_faqs(documents, proj))
        faqs.extend(self._select_function_faqs(documents))
        # Deduplicate by question text
        seen = set()
        unique = []
        for f in faqs:
            key = f['question'].lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(f)
        # Limit
        return unique[:config.MAX_FAQS]

