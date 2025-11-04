import os
import time
from collections import defaultdict
from typing import Dict, Any, List
import logging

from .utils import iter_source_files, read_text, count_lines, aggregate_by_ext
from .complexity import analyze_python_complexity, heuristic_complexity
from .deps import analyze_dependencies

logger = logging.getLogger(__name__)


def scan_codebase(base_path: str) -> Dict[str, Any]:
    try:
        base_path = os.path.abspath(base_path)
        start = time.time()

        files_info: List[Dict[str, Any]] = []
        py_complexity_files: List[Dict[str, Any]] = []

        total_lines = 0

        for f in iter_source_files(base_path):
            try:
                content = read_text(f)
                ext = os.path.splitext(f)[1].lower()
                lines, non_empty = count_lines(content)
                total_lines += lines
                fi = {
                    "path": os.path.relpath(f, base_path),
                    "extension": ext,
                    "lines": lines,
                    "non_empty": non_empty,
                }
                files_info.append(fi)
                if ext == ".py":
                    try:
                        comp = analyze_python_complexity(content, f)
                        comp_entry = {
                            "path": fi["path"],
                            "functions": comp["functions"],
                            "avg_cc": comp["avg_cc"],
                            "max_cc": comp["max_cc"],
                            "most_complex": comp["most_complex"],
                            "tool": comp["tool"],
                            "items": comp.get("items", []),
                        }
                        py_complexity_files.append(comp_entry)
                    except Exception as e:
                        logger.error(f"Error analyzing Python complexity for {f}: {e}")
                elif ext in {".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rb", ".php", ".c", ".cpp", ".cc", ".cs", ".h"}:
                    try:
                        comp = heuristic_complexity(content, f, ext)
                        # We won't include non-Python files in complexity summary tallies, but could be extended
                        pass
                    except Exception as e:
                        logger.error(f"Error analyzing heuristic complexity for {f}: {e}")
            except Exception as e:
                logger.error(f"Error processing file {f}: {e}")
                continue

        files_info.sort(key=lambda x: x["lines"], reverse=True)

        langs = aggregate_by_ext(files_info)

        total_files = len(files_info)

        # Complexity summary (Python only)
        total_functions = sum(f["functions"] for f in py_complexity_files)
        total_cc = sum(f["avg_cc"] * max(1, f["functions"]) for f in py_complexity_files)
        avg_cc = (total_cc / max(1, total_functions)) if total_functions else 0.0

        top_complex_functions = []
        for f in py_complexity_files:
            for it in f.get("items", []):
                try:
                    top_complex_functions.append({
                        "path": f["path"],
                        "name": it.get("name"),
                        "cc": float(it.get("cc", 0)),
                        "lineno": int(it.get("lineno", 0)),
                    })
                except (ValueError, TypeError) as e:
                    logger.error(f"Error processing complexity item in {f['path']}: {e}")
                    continue
        top_complex_functions.sort(key=lambda i: i["cc"], reverse=True)

        # Dependencies (Python)
        try:
            deps = analyze_dependencies(base_path)
        except Exception as e:
            logger.error(f"Error analyzing dependencies: {e}")
            deps = {"imports": [], "external_packages": [], "internal_modules": []}

        duration = time.time() - start

        result = {
            "base_path": base_path,
            "generated_at": int(time.time()),
            "duration_seconds": duration,
            "summary": {
                "total_files": total_files,
                "total_lines": total_lines,
                "avg_lines_per_file": (total_lines / total_files) if total_files else 0,
                "languages": langs,
                "top_files_by_lines": files_info[:20],
                "complexity": {
                    "total_functions": total_functions,
                    "avg_cyclomatic_complexity": avg_cc,
                    "top_complex_functions": top_complex_functions[:20],
                },
                "dependencies": deps,
            },
            "files": files_info,
            "complexity_details": py_complexity_files,
        }

        return result
    except Exception as e:
        logger.error(f"Fatal error scanning codebase at {base_path}: {e}")
        return {
            "base_path": base_path,
            "generated_at": int(time.time()),
            "duration_seconds": 0,
            "error": str(e),
            "summary": {
                "total_files": 0,
                "total_lines": 0,
                "avg_lines_per_file": 0,
                "languages": {},
                "top_files_by_lines": [],
                "complexity": {
                    "total_functions": 0,
                    "avg_cyclomatic_complexity": 0.0,
                    "top_complex_functions": [],
                },
                "dependencies": {"imports": [], "external_packages": [], "internal_modules": []},
            },
            "files": [],
            "complexity_details": [],
        }