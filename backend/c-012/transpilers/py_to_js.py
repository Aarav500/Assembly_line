import re
from typing import List, Tuple


def _detect_indent_size(lines: List[str]) -> int:
    sizes = []
    for ln in lines:
        if not ln.strip():
            continue
        leading = len(ln) - len(ln.lstrip(' '))
        if leading > 0:
            sizes.append(leading)
    if not sizes:
        return 4
    smallest = min(sizes)
    # Try to find gcd-like common indent size
    for size in (2, 4, smallest):
        if all((s % size == 0) for s in sizes):
            return size
    return smallest or 4


def _replace_bool_none(expr: str) -> str:
    expr = re.sub(r'\bTrue\b', 'true', expr)
    expr = re.sub(r'\bFalse\b', 'false', expr)
    expr = re.sub(r'\bNone\b', 'null', expr)
    return expr


def _replace_logical_ops(expr: str) -> str:
    # is None / is not None first
    expr = re.sub(r'\bis\s+None\b', '=== null', expr)
    expr = re.sub(r'\bis\s+not\s+None\b', '!== null', expr)
    # not, and, or
    expr = re.sub(r'\bnot\b\s*', '!', expr)
    expr = re.sub(r'\band\b', '&&', expr)
    expr = re.sub(r'\bor\b', '||', expr)
    return expr


def _convert_inline_comment(line: str) -> str:
    # Convert python '#' to JS '//' if '#' not in string (best-effort)
    if '#' in line:
        # naive split at first '#'
        parts = line.split('#', 1)
        code = parts[0].rstrip()
        comment = parts[1]
        if code:
            return f"{code} //{comment}"
        else:
            return f"//{comment}"
    return line


def _transform_expr(expr: str) -> str:
    return _replace_logical_ops(_replace_bool_none(expr))


def _transform_print(line: str) -> str:
    # print(a, b) -> console.log(a, b)
    return re.sub(r'\bprint\s*\(', 'console.log(', line)


def _transform_assignment(line: str) -> str:
    # Best-effort: just pass through, booleans and None replaced
    return _transform_expr(line)


def _transform_for(line: str, warnings: List[str]) -> str:
    # for i in range(...):
    m = re.match(r'^for\s+([A-Za-z_]\w*)\s+in\s+range\((.*?)\)\s*:\s*$', line)
    if m:
        var = m.group(1)
        args = [a.strip() for a in m.group(2).split(',') if a.strip()]
        if len(args) == 1:
            start, end, step = '0', args[0], '1'
        elif len(args) == 2:
            start, end = args
            step = '1'
        elif len(args) >= 3:
            start, end, step = args[0], args[1], args[2]
        else:
            start, end, step = '0', '0', '1'
        # Determine comparison based on step
        comp = '<' if not step.strip().startswith('-') else '>'
        return f"for (let {var} = {_transform_expr(start)}; {var} {comp} {_transform_expr(end)}; {var} += {_transform_expr(step)}) {{"

    # for x in iterable:
    m = re.match(r'^for\s+(.+?)\s+in\s+(.+?)\s*:\s*$', line)
    if m:
        var = m.group(1).strip()
        it = m.group(2).strip()
        return f"for (const {var} of {_transform_expr(it)}) {{"

    warnings.append('Unrecognized for-loop, emitted as comment.')
    return f"// [UNSUPPORTED for-loop] {line}"


def _transform_if_elif_else(line: str) -> Tuple[str, str]:
    stripped = line.strip()
    # returns (kind, js_line) kind in {'if','elif','else'}
    m = re.match(r'^if\s+(.*?):\s*$', stripped)
    if m:
        cond = _transform_expr(m.group(1).strip())
        return 'if', f"if ({cond}) {{"
    m = re.match(r'^elif\s+(.*?):\s*$', stripped)
    if m:
        cond = _transform_expr(m.group(1).strip())
        return 'elif', f"else if ({cond}) {{"
    m = re.match(r'^else\s*:\s*$', stripped)
    if m:
        return 'else', "else {"
    return '', ''


def _transform_while(line: str) -> str:
    m = re.match(r'^while\s+(.*?):\s*$', line.strip())
    if m:
        cond = _transform_expr(m.group(1).strip())
        return f"while ({cond}) {{"
    return ''


def _transform_def(line: str, warnings: List[str]) -> str:
    m = re.match(r'^def\s+([A-Za-z_]\w*)\s*\((.*?)\)\s*:\s*$', line.strip())
    if m:
        name = m.group(1)
        params = m.group(2).strip()
        return f"function {name}({params}) {{"
    return ''


def _transform_class(line: str, warnings: List[str]) -> str:
    m = re.match(r'^class\s+([A-Za-z_]\w*)\s*(\(.*?\))?\s*:\s*$', line.strip())
    if m:
        name = m.group(1)
        warnings.append(f"Class '{name}' converted to a bare JS class without methods mapping.")
        return f"class {name} {{"
    return ''


def transpile(code: str) -> Tuple[str, List[str]]:
    lines = code.splitlines()
    indent_size = _detect_indent_size(lines) or 4
    js_lines: List[str] = []
    warnings: List[str] = []

    prev_indent = 0

    for raw in lines:
        line = raw.rstrip('\n').rstrip('\r')
        if not line.strip():
            js_lines.append('')
            continue

        leading_spaces = len(line) - len(line.lstrip(' '))
        cur_indent = leading_spaces // indent_size if indent_size else 0
        stripped = line.strip()

        is_elif = re.match(r'^elif\b', stripped) is not None
        is_else = re.match(r'^else\b', stripped) is not None

        # Close blocks if dedenting
        if cur_indent < prev_indent:
            for i in range(prev_indent - cur_indent):
                js_lines.append('  ' * (prev_indent - i - 1) + '}')
        elif (is_elif or is_else) and cur_indent == prev_indent and js_lines:
            # Close the previous block for else/elif chain at same level
            js_lines.append('  ' * cur_indent + '}')

        # Transform line
        out_line = ''
        kind, block_line = _transform_if_elif_else(line)
        if block_line:
            out_line = block_line
            js_lines.append('  ' * cur_indent + out_line)
            prev_indent = cur_indent + 1
            continue

        block_line = _transform_def(line, warnings)
        if block_line:
            js_lines.append('  ' * cur_indent + block_line)
            prev_indent = cur_indent + 1
            continue

        block_line = _transform_class(line, warnings)
        if block_line:
            js_lines.append('  ' * cur_indent + block_line)
            prev_indent = cur_indent + 1
            continue

        block_line = _transform_while(line)
        if block_line:
            js_lines.append('  ' * cur_indent + block_line)
            prev_indent = cur_indent + 1
            continue

        if re.match(r'^for\b', stripped):
            js_line = _transform_for(stripped, warnings)
            js_lines.append('  ' * cur_indent + js_line)
            prev_indent = cur_indent + (1 if js_line.strip().endswith('{') else 0)
            continue

        # Comments only
        if stripped.startswith('#'):
            js_lines.append('  ' * cur_indent + '//' + stripped[1:])
            prev_indent = cur_indent
            continue

        # Statements
        stmt = line.strip()
        # print -> console.log
        stmt = _transform_print(stmt)
        # Replace bool/None and logical ops in expressions
        stmt = _transform_assignment(stmt)

        # Return
        if re.match(r'^return\b', stmt):
            js_lines.append('  ' * cur_indent + stmt + ';')
            prev_indent = cur_indent
            continue

        # Simple assignment or expression
        stmt = _convert_inline_comment(stmt)
        # Avoid adding semicolon to lines already ending with '}' or '{'
        if not stmt.endswith(';') and not stmt.endswith('{') and not stmt.endswith('}'):
            stmt = stmt + ';'
        js_lines.append('  ' * cur_indent + stmt)
        prev_indent = cur_indent

    # Close remaining blocks
    if prev_indent > 0:
        for i in range(prev_indent):
            js_lines.append('  ' * (prev_indent - i - 1) + '}')

    return '\n'.join(js_lines), warnings

