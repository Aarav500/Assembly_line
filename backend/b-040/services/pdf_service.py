import os
import time
from typing import Dict, Any
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted
from reportlab.lib.styles import getSampleStyleSheet
from utils.path_utils import ensure_dir, safe_filename


def export_to_pdf(title: str, content: str, options: Dict[str, Any], settings) -> str:
    out_dir = options.get('output_dir') or settings.EXPORT_OUTPUT_DIR
    ensure_dir(out_dir)
    timestamp = time.strftime('%Y%m%d-%H%M%S')
    fname = f"{safe_filename(title or 'Untitled')}-{timestamp}.pdf"
    fpath = os.path.join(out_dir, fname)

    doc = SimpleDocTemplate(fpath, pagesize=letter, title=title or 'Untitled')
    styles = getSampleStyleSheet()

    elements = []
    elements.append(Paragraph(title or 'Untitled', styles['Title']))
    elements.append(Spacer(1, 12))
    elements.append(Preformatted(content or '', styles['Code']))

    doc.build(elements)

    return fpath

