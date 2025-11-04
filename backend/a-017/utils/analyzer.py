import os
import ast
from pathlib import Path
from typing import Dict, List, Set, Any


class CodebaseAnalyzer:
    def __init__(self, root_path: str, exclude_patterns: List[str] = None):
        self.root_path = Path(root_path)
        self.exclude_patterns = exclude_patterns or []
        self.modules = {}
        self.dependencies = []

    def _should_exclude(self, path: Path) -> bool:
        """Check if path should be excluded based on patterns"""
        parts = path.parts
        for pattern in self.exclude_patterns:
            if pattern in parts or path.name == pattern:
                return True
        return False

    def _find_python_files(self) -> List[Path]:
        """Find all Python files in the root path"""
        python_files = []
        for py_file in self.root_path.rglob('*.py'):
            if not self._should_exclude(py_file):
                python_files.append(py_file)
        return python_files

    def _extract_imports(self, file_path: Path) -> List[str]:
        """Extract import statements from a Python file"""
        imports = []
        try:
            content = file_path.read_text(encoding='utf-8')
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
        except Exception:
            pass
        return imports

    def _get_module_name(self, file_path: Path) -> str:
        """Get module name from file path relative to root"""
        try:
            rel_path = file_path.relative_to(self.root_path)
            parts = list(rel_path.parts[:-1])
            if rel_path.name != '__init__.py':
                parts.append(rel_path.stem)
            return '.'.join(parts) if parts else rel_path.stem
        except ValueError:
            return file_path.stem

    def analyze(self, include_externals: bool = False) -> Dict[str, Any]:
        """Analyze the codebase and return dependency information"""
        python_files = self._find_python_files()
        
        # Build module map
        module_map = {}
        for py_file in python_files:
            module_name = self._get_module_name(py_file)
            imports = self._extract_imports(py_file)
            module_map[module_name] = {
                'file': str(py_file.relative_to(self.root_path)),
                'imports': imports
            }

        # Build dependency graph
        nodes = []
        edges = []
        node_set = set()

        for module_name, module_info in module_map.items():
            if module_name and module_name not in node_set:
                nodes.append({
                    'id': module_name,
                    'label': module_name,
                    'file': module_info['file']
                })
                node_set.add(module_name)

            for imp in module_info['imports']:
                # Check if import is internal
                is_internal = False
                target_module = None
                
                for mod in module_map.keys():
                    if imp.startswith(mod) or mod.startswith(imp):
                        is_internal = True
                        target_module = mod
                        break

                if is_internal and target_module:
                    if target_module not in node_set:
                        nodes.append({
                            'id': target_module,
                            'label': target_module,
                            'file': module_map[target_module]['file']
                        })
                        node_set.add(target_module)
                    
                    edges.append({
                        'from': module_name,
                        'to': target_module,
                        'label': 'imports'
                    })
                elif include_externals:
                    # Add external dependency
                    ext_name = imp.split('.')[0]
                    if ext_name not in node_set:
                        nodes.append({
                            'id': ext_name,
                            'label': ext_name,
                            'external': True
                        })
                        node_set.add(ext_name)
                    
                    edges.append({
                        'from': module_name,
                        'to': ext_name,
                        'label': 'imports'
                    })

        return {
            'nodes': nodes,
            'edges': edges,
            'modules': module_map
        }
