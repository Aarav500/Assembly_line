import os
from typing import Dict, Any, List, Tuple

BEGIN_PK = "-----BEGIN"
END_PK = "-----END"


def apply_redactions(findings: List[Dict[str, Any]], base_path: str = ".", placeholder: str = "<REDACTED>") -> Tuple[List[str], List[Dict[str, Any]]]:
    by_file: Dict[str, List[Dict[str, Any]]] = {}
    for f in findings:
        by_file.setdefault(f["file"], []).append(f)

    changed_files: List[str] = []
    change_details: List[Dict[str, Any]] = []

    for rel, items in by_file.items():
        abs_path = os.path.join(base_path, rel)
        if not os.path.exists(abs_path):
            continue
        try:
            with open(abs_path, 'r', encoding='utf-8', errors='replace') as fh:
                lines = fh.read().splitlines()
        except Exception:
            continue

        # Sort findings bottom-up so indexes remain valid per line
        items_sorted = sorted(items, key=lambda x: (x.get("line", 0), x.get("col", 0)), reverse=True)
        file_changed = False
        edits_for_file: List[Dict[str, Any]] = []

        # Track private key blocks already redacted to avoid duplicate work
        redacted_ranges = set()

        for it in items_sorted:
            line_no = int(it.get("line", 0))
            col = int(it.get("col", 1))
            end_col = int(it.get("end_col", col))
            rule = it.get("rule", "")

            if line_no <= 0 or line_no > len(lines):
                continue

            # Private key block handling
            if "Private Key" in rule and BEGIN_PK in lines[line_no - 1]:
                # find end line for this key block
                start_idx = line_no - 1
                if (start_idx, "pk") in redacted_ranges:
                    continue
                end_idx = start_idx
                while end_idx < len(lines):
                    if END_PK in lines[end_idx] and "PRIVATE KEY" in lines[end_idx]:
                        break
                    end_idx += 1
                # Replace block with placeholder
                lines[start_idx:end_idx + 1] = [f"{placeholder}_PRIVATE_KEY"]
                file_changed = True
                edits_for_file.append({
                    "rule": rule,
                    "start_line": start_idx + 1,
                    "end_line": end_idx + 1,
                    "replacement": f"{placeholder}_PRIVATE_KEY"
                })
                redacted_ranges.add((start_idx, "pk"))
                continue

            # Regular single-line replacement
            idx = line_no - 1
            line = lines[idx]
            # Ensure slice idxs within bounds
            c0 = max(0, col - 1)
            c1 = max(c0, min(len(line), end_col))
            # Validate that matched substring exists
            new_line = line[:c0] + placeholder + line[c1:]
            if new_line != line:
                lines[idx] = new_line
                file_changed = True
                edits_for_file.append({
                    "rule": rule,
                    "line": line_no,
                    "col": col,
                    "end_col": end_col,
                    "replacement": placeholder
                })

        if file_changed:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, 'w', encoding='utf-8', errors='replace') as fh:
                fh.write("\n".join(lines) + ("" if (len(lines) and lines[-1] == "") else "\n"))
            changed_files.append(rel)
            change_details.append({"file": rel, "edits": edits_for_file})

    return changed_files, change_details

