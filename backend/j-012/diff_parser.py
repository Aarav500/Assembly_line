from unidiff import PatchSet
from io import StringIO

def parse_unified_diff(diff_text: str):
    patch = PatchSet(StringIO(diff_text), encoding='utf-8', errors='replace')

    files = []
    total_adds = 0
    total_dels = 0

    for f in patch:
        file_obj = {
            "old_path": f.source_file,
            "new_path": f.target_file,
            "is_new": f.is_added_file,
            "is_deleted": f.is_removed_file,
            "is_rename": f.is_rename,
            "hunks": [],
            "stats": {"additions": 0, "deletions": 0}
        }
        file_adds = 0
        file_dels = 0
        for h in f:
            hunk_obj = {
                "old_start": h.source_start,
                "old_lines": h.source_length,
                "new_start": h.target_start,
                "new_lines": h.target_length,
                "lines": []
            }
            for line in h:
                if line.is_added:
                    kind = 'add'
                    file_adds += 1
                elif line.is_removed:
                    kind = 'del'
                    file_dels += 1
                else:
                    kind = 'context'
                # Remove trailing newlines for cleaner rendering
                content = line.value.rstrip('\n').rstrip('\r')
                hunk_obj["lines"].append({
                    "type": kind,
                    "old_lineno": line.source_line_no,
                    "new_lineno": line.target_line_no,
                    "content": content
                })
            file_obj["hunks"].append(hunk_obj)
        file_obj["stats"]["additions"] = file_adds
        file_obj["stats"]["deletions"] = file_dels
        total_adds += file_adds
        total_dels += file_dels
        files.append(file_obj)

    return {
        "files": files,
        "stats": {"files": len(files), "additions": total_adds, "deletions": total_dels}
    }

