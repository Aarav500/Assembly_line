import os
import time
from typing import Dict, Any
from utils.path_utils import ensure_dir, safe_filename


def export_to_markdown(title: str, content: str, options: Dict[str, Any], settings) -> str:
    out_dir = options.get('output_dir') or settings.EXPORT_OUTPUT_DIR
    ensure_dir(out_dir)
    timestamp = time.strftime('%Y%m%d-%H%M%S')
    fname = f"{safe_filename(title or 'Untitled')}-{timestamp}.md"
    fpath = os.path.join(out_dir, fname)

    md = f"# {title or 'Untitled'}\n\n{content or ''}\n"
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(md)

    return fpath

