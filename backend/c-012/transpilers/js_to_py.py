import re
from typing import List, Tuple


def _strip_trailing_semicolon(s: str) -> str:
    return s[:-1] if s.endswith(';') else s


def _replace_bool_null(expr: str) -> str:
    expr = re.sub(r'\btrue\b', 'True', expr)
    expr = re.sub(r'\bfalse\b', 'False', expr)
    expr = re.sub(r'\bnull\b', 'None', expr)
    return expr


def _replace_logical_ops(expr: str) -> str:
    expr = re.sub(r'===', '==', expr)
    expr = re.sub(r'!==', '!=', expr)
    expr = re.sub(r'\b&&\b', 'and', expr)
    expr = re.sub(r'\b\|\|\b', 'or', expr)
    # '!' unary -> 'not ' (best-effort)
    expr = re.sub(r'!\s*', 'not ', expr)
    return expr


def _collapse_parens(s: str) -> str:
    s = s.strip()
    if s.startswith('(') and s.endswith(')'):
        # remove one layer if balanced
        depth = 0
        for i, ch in enumerate(s):
            if ch == '(': depth += 1
            elif ch == ')': depth -= 1
            if depth == 0 and i != len(s) - 1:
                return s  # extra stuff outside, don't strip
        return s[1:-1].strip()
    return s


def _convert_inline_comment(line: str) -> str:
    if '//' in line:
        parts = line.split('//', 1)
        code = parts[0].rstrip()
        comment = parts[1]
        if code:
            return f"{code} # {comment}"
        else:
            return f"# {comment}"
    return line


def _parse_for_header(header: str) -> Tuple[str, str]:
    # Try classic counter for: for (let i = 0; i < N; i++)
    m = re.match(r'^\s*(?:let|var|const)?\s*([A-Za-z_]\w*)\s*=\s*([^;]+);\s*\1\s*([<>=!]+)\s*([^;]+);\s*\1\s*([+\-]{2}|[+\-]=\s*[^\)]+)\s*$', header)
    if m:
        var = m.group(1)
        start = m.group(2).strip()
        op = m.group(3).strip()
        end = m.group(4).strip()
        step_token = m.group(5).strip()
        # Determine step
        if step_token in ('++', '+= 1', '+=1'):
            step = '1'
        elif step_token in ('--', '-= 1', '-=1'):
            step = '-1'
        else:
            step = step_token.replace('+=', '').replace('-=', '-').strip()
        # Range end handling for <= or >=
        inclusive = op in ('<=', '>=')
        direction_negative = step.startswith('-')
        # Build pythonic range
        start_py = _replace_logical_ops(_replace_bool_null(start))
        end_py = _replace_logical_ops(_replace_bool_null(end))
        if inclusive:
            end_py = f"({end_py}) + 1" if not direction_negative else f"({end_py}) - 1"
        if direction_negative:
            return var, f"range({start_py}, {end_py}, {step})"
        else:
            # For op like '>' reverse? We'll still emit as-is
            return var, f"range({start_py}, {end_py}, {step})" if step != '1' else f"range({start_py}, {end_py})"

    # for (const x of iterable)
    m = re.match(r'^\s*(?:const|let|var)?\s*([A-Za-z_]\w*)\s+of\s+(.+)$', header)
    if m:
        var = m.group(1)
        it = m.group(2).strip()
        it_py = _replace_logical_ops(_replace_bool_null(it))
        return var, it_py  # indicates for-in style

    return '', ''


def transpile(code: str):
    lines = code.splitlines()
    py_lines: List[str] = []
    warnings: List[str] = []
    indent = 0
    indent_unit = '    '

    # Preprocess to normalize lines like "} else {" on the same line
    normalized: List[str] = []
    for raw in lines:
        s = raw.rstrip('\n').rstrip('\r')
        s = s.replace('}\n', '}\n')
        # split specific patterns to ease parsing
        s = s.replace('} else if', '}\nelse if')
        s = s.replace('} else {', '}\nelse {')
        parts = s.split('\n')
        for p in parts:
            normalized.append(p)

    for raw in normalized:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            py_lines.append('')
            continue

        # Handle starting closing braces
        while stripped.startswith('}'):
            indent = max(0, indent - 1)
            stripped = stripped[1:].lstrip()

        # Comments only
        if stripped.startswith('//'):
            py_lines.append(indent_unit * indent + '#' + stripped[2:])
            continue

        # else if
        m = re.match(r'^else\s+if\s*\((.*)\)\s*\{?\s*$', stripped)
        if m:
            cond = _collapse_parens(m.group(1).strip())
            cond = _replace_logical_ops(_replace_bool_null(cond))
            py_lines.append(indent_unit * indent + f"elif {cond}:")
            indent += 1
            continue

        # else
        m = re.match(r'^else\s*\{?\s*$', stripped)
        if m:
            py_lines.append(indent_unit * indent + 'else:')
            indent += 1
            continue

        # if
        m = re.match(r'^if\s*\((.*)\)\s*\{?\s*$', stripped)
        if m:
            cond = _collapse_parens(m.group(1).strip())
            cond = _replace_logical_ops(_replace_bool_null(cond))
            py_lines.append(indent_unit * indent + f"if {cond}:")
            indent += 1
            continue

        # while
        m = re.match(r'^while\s*\((.*)\)\s*\{?\s*$', stripped)
        if m:
            cond = _collapse_parens(m.group(1).strip())
            cond = _replace_logical_ops(_replace_bool_null(cond))
            py_lines.append(indent_unit * indent + f"while {cond}:")
            indent += 1
            continue

        # function
        m = re.match(r'^function\s+([A-Za-z_]\w*)\s*\((.*?)\)\s*\{?\s*$', stripped)
        if m:
            name = m.group(1)
            params = m.group(2).strip()
            py_lines.append(indent_unit * indent + f"def {name}({params}):")
            indent += 1
            continue

        # class
        m = re.match(r'^class\s+([A-Za-z_]\w*)\s*\{\s*$', stripped)
        if m:
            name = m.group(1)
            py_lines.append(indent_unit * indent + f"class {name}:")
            indent += 1
            continue

        # for header
        m = re.match(r'^for\s*\((.*)\)\s*\{?\s*$', stripped)
        if m:
            header = m.group(1).strip()
            var, spec = _parse_for_header(header)
            if var and spec:
                if spec.startswith('range('):
                    py_lines.append(indent_unit * indent + f"for {var} in {spec}:")
                else:
                    py_lines.append(indent_unit * indent + f"for {var} in {spec}:")
                indent += 1
                continue
            else:
                warnings.append(f"Unrecognized for-loop header: {header}")
                py_lines.append(indent_unit * indent + f"# [UNSUPPORTED for-loop] for ({header})")
                indent += 1
                continue

        # remove trailing '{' that indicates block start
        if stripped.endswith('{'):
            body = stripped[:-1].rstrip()
            if body:
                # Try to convert known patterns in body line
                # If we reach here, we didn't match a known block opener; treat as comment
                py_lines.append(indent_unit * indent + f"# [UNSUPPORTED block] {body}")
            else:
                py_lines.append(indent_unit * indent + f"# [UNSUPPORTED block]")
            indent += 1
            continue

        # Simple statements
        s = stripped
        # Convert variable declarations
        s = re.sub(r'^\s*(?:let|var|const)\s+', '', s)
        # console.log -> print
        s = re.sub(r'\bconsole\s*\.\s*log\s*\(', 'print(', s)
        # Comments inline
        s = _convert_inline_comment(s)
        # Strip semicolon
        s = _strip_trailing_semicolon(s)
        # Logical ops and booleans/null
        s = _replace_logical_ops(_replace_bool_null(s))

        py_lines.append(indent_unit * indent + s)

        # Handle lines that end with '}' after code (rare given earlier splits)
        if stripped.endswith('}'):
            indent = max(0, indent - 1)

    # No need to explicitly close blocks in Python; but we can add pass for empty classes/functions if last line is a header.
    # Post-process: ensure blocks are not empty? Skipped for simplicity.

    return '\n'.join(py_lines), warnings

