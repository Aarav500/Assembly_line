from bs4 import BeautifulSoup
import markdown as md

def html_to_markdown(html: str) -> str:
    if not html:
        return ''
    soup = BeautifulSoup(html, 'html.parser')

    def process(node, prefix=''):
        out = []
        for child in node.children:
            if getattr(child, 'name', None) is None:
                text = str(child)
                if text:
                    out.append(text)
                continue
            name = child.name.lower()
            if name in ['h1','h2','h3','h4','h5','h6']:
                level = int(name[1])
                out.append('\n' + ('#' * level) + ' ' + child.get_text(strip=True) + '\n\n')
            elif name == 'p':
                out.append(child.get_text(strip=False) + '\n\n')
            elif name in ['strong', 'b']:
                out.append('**' + child.get_text(strip=True) + '**')
            elif name in ['em', 'i']:
                out.append('*' + child.get_text(strip=True) + '*')
            elif name == 'code' and child.parent and child.parent.name != 'pre':
                out.append('`' + child.get_text(strip=True) + '`')
            elif name == 'pre':
                out.append('\n```\n' + child.get_text() + '\n```\n\n')
            elif name == 'ul':
                for li in child.find_all('li', recursive=False):
                    out.append('- ' + li.get_text(strip=True) + '\n')
                out.append('\n')
            elif name == 'ol':
                i = 1
                for li in child.find_all('li', recursive=False):
                    out.append(f"{i}. " + li.get_text(strip=True) + '\n')
                    i += 1
                out.append('\n')
            elif name == 'br':
                out.append('  \n')
            elif name == 'blockquote':
                lines = child.get_text().splitlines()
                out.append('\n' + '\n'.join('> ' + l for l in lines) + '\n\n')
            elif name == 'hr':
                out.append('\n---\n\n')
            else:
                out.append(child.get_text())
        return ''.join(out)

    md_text = process(soup)
    # Normalize spacing
    return md_text.strip() + '\n'


def markdown_to_html(markdown_text: str) -> str:
    if not markdown_text:
        return ''
    return md.markdown(markdown_text, extensions=['extra'])

