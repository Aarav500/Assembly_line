import os
import re
import ast
import hashlib
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Set, Any
from utils.fs import iter_code_files, read_text_file, find_requirements
from utils.text import tokenize_code, make_shingles, jaccard
from config import SUPPORTED_EXTENSIONS, SHINGLE_SIZE, NEAR_DUP_THRESHOLD, MAX_FILES_FOR_NEAR_DUP, IGNORE_DIRS


@dataclass
class FileRecord:
    project_id: str
    project_name: str
    abs_path: str
    rel_path: str
    ext: str
    size: int
    sha256: str
    token_count: int
    shingles: Set[int]
    imports: List[str]


class DSU:
    def __init__(self):
        self.parent = {}
        self.rank = {}

    def find(self, x):
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0
            return x
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return ra
        if self.rank[ra] < self.rank[rb]:
            self.parent[ra] = rb
            return rb
        elif self.rank[ra] > self.rank[rb]:
            self.parent[rb] = ra
            return ra
        else:
            self.parent[rb] = ra
            self.rank[ra] += 1
            return ra


class Analyzer:
    def __init__(self):
        pass

    def _hash_content(self, content: str) -> str:
        h = hashlib.sha256()
        h.update(content.encode('utf-8', errors='ignore'))
        return h.hexdigest()

    def _parse_imports_py(self, content: str) -> List[str]:
        mods = []
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for n in node.names:
                        if n.name:
                            mods.append(n.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        mods.append(node.module.split('.')[0])
        except Exception:
            pass
        return mods

    def _extract_imports(self, ext: str, content: str) -> List[str]:
        if ext == '.py':
            return self._parse_imports_py(content)
        # naive for JS/TS
        if ext in ('.js', '.jsx', '.ts', '.tsx'):
            mods = re.findall(r"(?:from|require\()\s*['\"]([^'\"]+)['\"]", content)
            # exclude relative imports
            return [m.split('/')[0] for m in mods if not m.startswith('.')]
        return []

    def _scan_single_project(self, project: Dict[str, Any]) -> Tuple[List[FileRecord], Set[str]]:
        root = project['path']
        files: List[FileRecord] = []
        dependencies: Set[str] = set()

        # read dependencies from requirements.txt
        req_path = find_requirements(root)
        if req_path and os.path.isfile(req_path):
            for line in read_text_file(req_path).splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                pkg = re.split(r"[<>=!~]", line)[0].strip()
                if pkg:
                    dependencies.add(pkg.lower())

        for abs_path, rel_path in iter_code_files(root, SUPPORTED_EXTENSIONS, IGNORE_DIRS):
            try:
                content = read_text_file(abs_path)
            except Exception:
                continue
            ext = os.path.splitext(abs_path)[1].lower()
            sha = self._hash_content(content)
            tokens = tokenize_code(content)
            shingles = make_shingles(tokens, SHINGLE_SIZE)
            imports = self._extract_imports(ext, content)
            files.append(FileRecord(
                project_id=project['id'],
                project_name=project['name'],
                abs_path=abs_path,
                rel_path=rel_path,
                ext=ext,
                size=len(content.encode('utf-8', errors='ignore')),
                sha256=sha,
                token_count=len(tokens),
                shingles=shingles,
                imports=imports
            ))
        return files, dependencies

    def scan_projects(self, projects: List[Dict[str, Any]], mode: str = "full") -> Dict[str, Any]:
        # Gather file records and per-project metadata
        all_files: List[FileRecord] = []
        project_meta: Dict[str, Dict[str, Any]] = {}
        for p in projects:
            files, deps = self._scan_single_project(p)
            project_meta[p['id']] = {
                'id': p['id'],
                'name': p['name'],
                'path': p['path'],
                'file_count': len(files),
                'dependencies': sorted(list(deps)),
            }
            all_files.extend(files)

        # Exact duplicates by sha256
        exact_groups = self._group_exact_duplicates(all_files)

        # Near duplicates using shingles and jaccard
        near_clusters = []
        if mode != 'fast':
            near_clusters = self._near_duplicate_clusters(all_files)

        # Shared components
        shared = self._shared_components(all_files, project_meta)

        total_files = len(all_files)
        report = {
            'projects': list(project_meta.values()),
            'stats': {
                'total_projects': len(projects),
                'total_files': total_files,
                'total_exact_duplicate_groups': len(exact_groups),
                'total_near_duplicate_clusters': len(near_clusters),
                'total_shared_relpaths': len(shared.get('by_relpath', [])),
                'total_shared_packages': len(shared.get('shared_packages', [])),
            },
            'exact_duplicates': exact_groups,
            'near_duplicate_clusters': near_clusters,
            'shared_components': shared,
        }
        return report

    def _group_exact_duplicates(self, all_files: List[FileRecord]) -> List[Dict[str, Any]]:
        by_hash: Dict[str, List[FileRecord]] = defaultdict(list)
        for f in all_files:
            by_hash[f.sha256].append(f)
        groups = []
        for h, files in by_hash.items():
            proj_set = {f.project_id for f in files}
            if len(proj_set) < 2:
                continue
            files_sorted = sorted(files, key=lambda x: (x.project_name, x.rel_path))
            groups.append({
                'hash': h,
                'count': len(files_sorted),
                'projects': sorted(list({f.project_name for f in files_sorted})),
                'files': [
                    {
                        'project_id': f.project_id,
                        'project_name': f.project_name,
                        'rel_path': f.rel_path,
                        'ext': f.ext,
                        'size': f.size,
                    }
                    for f in files_sorted
                ]
            })
        groups.sort(key=lambda g: (-len(g['projects']), -g['count']))
        return groups

    def _near_duplicate_clusters(self, all_files: List[FileRecord]) -> List[Dict[str, Any]]:
        # Limit comparisons for performance
        candidates = [f for f in all_files if f.token_count >= SHINGLE_SIZE]
        if len(candidates) > MAX_FILES_FOR_NEAR_DUP:
            # Heuristic: keep largest files across projects
            candidates.sort(key=lambda f: (-f.token_count, f.ext))
            candidates = candidates[:MAX_FILES_FOR_NEAR_DUP]

        # Bucket by extension to reduce comparisons
        buckets: Dict[str, List[FileRecord]] = defaultdict(list)
        for f in candidates:
            buckets[f.ext].append(f)

        dsu = DSU()
        sim_map: Dict[Tuple[int, int], float] = {}
        index_map: Dict[FileRecord, int] = {}
        files_list: List[FileRecord] = []

        # assign indices
        for ext, lst in buckets.items():
            for f in lst:
                index_map[f] = len(files_list)
                files_list.append(f)

        # compare within each ext bucket
        for ext, lst in buckets.items():
            lst.sort(key=lambda f: f.token_count)
            for i in range(len(lst)):
                fi = lst[i]
                for j in range(i + 1, len(lst)):
                    fj = lst[j]
                    # across different projects only
                    if fi.project_id == fj.project_id:
                        continue
                    # size filter: within 40% length difference
                    if fj.token_count > 0 and abs(fi.token_count - fj.token_count) / max(fi.token_count, fj.token_count) > 0.4:
                        continue
                    sim = jaccard(fi.shingles, fj.shingles)
                    if sim >= NEAR_DUP_THRESHOLD:
                        ii = index_map[fi]
                        jj = index_map[fj]
                        dsu.union(ii, jj)
                        sim_map[(min(ii, jj), max(ii, jj))] = sim

        # build clusters
        clusters: Dict[int, List[int]] = defaultdict(list)
        for i in range(len(files_list)):
            root = dsu.find(i)
            clusters[root].append(i)

        result = []
        cid = 1
        for root, idxs in clusters.items():
            if len(idxs) < 2:
                continue
            # collect files and similarity stats
            files = [files_list[i] for i in idxs]
            # Only keep clusters that span multiple projects
            proj_set = {f.project_id for f in files}
            if len(proj_set) < 2:
                continue
            # compute min/max/avg similarity based on pair entries
            sims = []
            for i in range(len(idxs)):
                for j in range(i + 1, len(idxs)):
                    a, b = min(idxs[i], idxs[j]), max(idxs[i], idxs[j])
                    if (a, b) in sim_map:
                        sims.append(sim_map[(a, b)])
            if not sims:
                continue
            result.append({
                'cluster_id': cid,
                'files': [
                    {
                        'project_id': f.project_id,
                        'project_name': f.project_name,
                        'rel_path': f.rel_path,
                        'ext': f.ext,
                        'size': f.size,
                        'token_count': f.token_count
                    }
                    for f in sorted(files, key=lambda x: (x.project_name, x.rel_path))
                ],
                'similarity_min': min(sims),
                'similarity_max': max(sims),
                'similarity_avg': sum(sims) / len(sims)
            })
            cid += 1

        # Sort clusters by avg similarity and size
        result.sort(key=lambda c: (-c['similarity_avg'], -len(c['files'])))
        return result

    def _shared_components(self, all_files: List[FileRecord], project_meta: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        # Shared by relative path name across projects
        by_rel: Dict[str, List[FileRecord]] = defaultdict(list)
        for f in all_files:
            key = f.rel_path.replace('\\', '/').lower()
            by_rel[key].append(f)

        shared_rel = []
        for rel, files in by_rel.items():
            proj_set = {f.project_id for f in files}
            if len(proj_set) < 2:
                continue
            # compute whether identical and avg similarity
            is_exact = len({f.sha256 for f in files}) == 1
            sims = []
            for i in range(len(files)):
                for j in range(i + 1, len(files)):
                    if files[i].project_id == files[j].project_id:
                        continue
                    sims.append(jaccard(files[i].shingles, files[j].shingles))
            avg_sim = sum(sims) / len(sims) if sims else 0.0
            shared_rel.append({
                'rel_path': rel,
                'projects': sorted(list({f.project_name for f in files})),
                'file_instances': [
                    {
                        'project_id': f.project_id,
                        'project_name': f.project_name,
                        'rel_path': f.rel_path,
                        'ext': f.ext,
                        'size': f.size,
                    }
                    for f in sorted(files, key=lambda x: (x.project_name, x.rel_path))
                ],
                'is_exact': is_exact,
                'similarity_avg': avg_sim,
            })

        shared_rel.sort(key=lambda x: (-len(x['projects']), -x['similarity_avg']))

        # Shared dependencies across projects
        pkg_projects: Dict[str, Set[str]] = defaultdict(set)
        for p in project_meta.values():
            for pkg in p.get('dependencies', []):
                pkg_projects[pkg].add(p['name'])
        shared_pkgs = [
            {
                'package': pkg,
                'projects': sorted(list(projs)),
                'count': len(projs)
            }
            for pkg, projs in pkg_projects.items() if len(projs) > 1
        ]
        shared_pkgs.sort(key=lambda x: (-x['count'], x['package']))

        # Shared import names (e.g., common internal module names) across projects
        import_projects: Dict[str, Set[str]] = defaultdict(set)
        for f in all_files:
            for mod in f.imports:
                import_projects[mod].add(f.project_name)
        shared_imports = [
            {
                'module': m,
                'projects': sorted(list(ps)),
                'count': len(ps)
            }
            for m, ps in import_projects.items() if len(ps) > 1
        ]
        shared_imports.sort(key=lambda x: (-x['count'], x['module']))

        return {
            'by_relpath': shared_rel,
            'shared_packages': shared_pkgs,
            'shared_imports': shared_imports,
        }

