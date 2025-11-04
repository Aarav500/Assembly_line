import hashlib
import difflib


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def diff_text(old: str, new: str):
    old_lines = old.splitlines()
    new_lines = new.splitlines()

    # Unified diff for quick view
    unified = "\n".join(
        difflib.unified_diff(old_lines, new_lines, lineterm='', fromfile='previous', tofile='current')
    )

    # HTML diff for rich view
    html_diff = difflib.HtmlDiff(wrapcolumn=80).make_table(old_lines, new_lines, 'previous', 'current', context=True, numlines=2)

    # Counts
    sm = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    added = removed = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'insert':
            added += (j2 - j1)
        elif tag == 'delete':
            removed += (i2 - i1)
        elif tag == 'replace':
            removed += (i2 - i1)
            added += (j2 - j1)

    return unified, html_diff, added, removed

