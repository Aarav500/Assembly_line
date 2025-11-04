import datetime
from typing import Dict

LATEX_PREAMBLE = r"""\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{hyperref}
\usepackage{setspace}
\usepackage{lmodern}
\usepackage{titlesec}
\setlength{\parskip}{0.6em}
\setlength{\parindent}{0pt}
\titleformat{\section}{\bfseries\Large}{}{0em}{}
\titleformat{\subsection}{\bfseries\large}{}{0em}{}
"""

LATEX_BEGIN = r"""\begin{document}
\maketitle
\begin{abstract}
ABSTRACT_PLACEHOLDER
\end{abstract}
"""

LATEX_END = r"""\end{document}
"""


def latex_escape(s: str) -> str:
    if s is None:
        return ''
    # Minimal escaping
    replacements = {
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}',
        '\\': r'\textbackslash{}',
    }
    out = []
    for ch in s:
        out.append(replacements.get(ch, ch))
    return ''.join(out)


def paper_to_latex(paper: Dict) -> str:
    title = paper.get('title', 'Untitled').strip() or 'Untitled'
    authors = paper.get('authors', 'Automated Researcher')
    abstract = paper.get('abstract', '')
    sections = paper.get('sections', [])
    references = paper.get('references', [])

    header = LATEX_PREAMBLE + f"\\title{{{latex_escape(title)}}}\n" + f"\\author{{{latex_escape(authors)}}}\n" + f"\\date{{{datetime.date.today().isoformat()}}}\n"

    doc = [header, LATEX_BEGIN.replace('ABSTRACT_PLACEHOLDER', latex_escape(abstract))]

    # Sections
    for sec in sections:
        stitle = latex_escape(sec.get('title', ''))
        scontent = sec.get('content', '')
        # we keep numeric citation markers [1] as-is; optionally could map to \cite
        doc.append(f"\\section{{{stitle}}}\n{latex_escape(scontent)}\n")

    # References
    doc.append('\\section*{References}\n')
    doc.append('\\begin{thebibliography}{99}\n')
    for ref in references:
        rid = ref.get('id')
        authors = latex_escape(ref.get('authors', ''))
        year = latex_escape(ref.get('year', ''))
        title = latex_escape(ref.get('title', ''))
        venue = latex_escape(ref.get('venue', ''))
        doc.append(f"\\bibitem{{ref{rid}}} {authors} ({year}). {title}. {venue}.\n")
    doc.append('\\end{thebibliography}\n')

    doc.append(LATEX_END)
    return '\n'.join(doc)

