"""A small YAML subset reader and writer, so the core needs no third-party parser.

Supported: nested mappings by two-space indent, block lists (`- item`), list items that are
mappings, quoted and plain scalars, ints, floats, booleans, null, `#` comments, and flow
lists of scalars (`[a, b]`). That covers every `skynet.yaml` this project writes. Anything
else raises a clear error rather than guessing.
"""
from __future__ import annotations

from typing import Any


class YAMLError(ValueError):
    pass


def _strip_comment(line: str) -> str:
    out, quote = [], None
    for i, ch in enumerate(line):
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
            out.append(ch)
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            break
        else:
            out.append(ch)
    return "".join(out).rstrip()


def _scalar(text: str) -> Any:
    s = text.strip()
    if s == "" or s in ("~", "null", "Null", "NULL"):
        return None
    if s in ("true", "True", "TRUE"):
        return True
    if s in ("false", "False", "FALSE"):
        return False
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        return [] if not inner else [_scalar(p) for p in inner.split(",")]
    if s in ("{}",):
        return {}
    try:
        return int(s)
    except ValueError:
        pass
    try:
        if any(c in s for c in ".eE") and not s.startswith("0x"):
            return float(s)
    except ValueError:
        pass
    return s


def _split_key(content: str) -> tuple[str, str] | None:
    """`key: value` or `key:` → (key, value-text). None if the line is not a mapping entry."""
    quote = None
    for i, ch in enumerate(content):
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == ":" and (i + 1 == len(content) or content[i + 1] in " \t"):
            key = content[:i].strip()
            if len(key) >= 2 and key[0] == key[-1] and key[0] in ("'", '"'):
                key = key[1:-1]
            return key, content[i + 1:].strip()
    return None


def loads(text: str) -> Any:
    lines: list[tuple[int, str]] = []
    for raw in text.splitlines():
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise YAMLError("tabs are not allowed for indentation")
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        lines.append((indent, stripped.strip()))
    if not lines:
        return {}
    value, i = _parse_block(lines, 0, lines[0][0])
    if i != len(lines):
        raise YAMLError(f"unexpected content at line {i + 1}: {lines[i][1]!r}")
    return value


def _parse_block(lines: list[tuple[int, str]], i: int, indent: int) -> tuple[Any, int]:
    if lines[i][1].startswith("- ") or lines[i][1] == "-":
        return _parse_list(lines, i, indent)
    return _parse_map(lines, i, indent)


def _parse_map(lines, i, indent):
    result: dict[str, Any] = {}
    while i < len(lines) and lines[i][0] == indent:
        content = lines[i][1]
        if content.startswith("- "):
            break
        kv = _split_key(content)
        if kv is None:
            raise YAMLError(f"expected 'key: value' at line {i + 1}: {content!r}")
        key, rest = kv
        i += 1
        if rest == "":
            if i < len(lines) and lines[i][0] > indent:
                result[key], i = _parse_block(lines, i, lines[i][0])
            elif i < len(lines) and lines[i][0] == indent and lines[i][1].startswith("- "):
                result[key], i = _parse_list(lines, i, indent)
            else:
                result[key] = None
        else:
            result[key] = _scalar(rest)
    if i < len(lines) and lines[i][0] > indent:
        raise YAMLError(f"bad indentation at line {i + 1}: {lines[i][1]!r}")
    return result, i


def _parse_list(lines, i, indent):
    result: list[Any] = []
    while i < len(lines) and lines[i][0] == indent and (lines[i][1].startswith("- ") or lines[i][1] == "-"):
        item = lines[i][1][1:].strip()
        if item == "":
            i += 1
            if i < len(lines) and lines[i][0] > indent:
                value, i = _parse_block(lines, i, lines[i][0])
                result.append(value)
            else:
                result.append(None)
            continue
        kv = _split_key(item)
        if kv is not None and not (item.startswith(("'", '"')) and kv[0] == item[1:-1]):
            # a mapping that starts on the dash line; its siblings sit at indent+2
            lines[i] = (indent + 2, item)
            value, i = _parse_map(lines, i, indent + 2)
            result.append(value)
        else:
            result.append(_scalar(item))
            i += 1
    return result, i


def dumps(value: Any, indent: int = 0) -> str:
    """Write back the same subset. Strings that could be misread are quoted."""
    pad = " " * indent
    if isinstance(value, dict):
        if not value:
            return pad + "{}\n"
        out = []
        for k, v in value.items():
            if isinstance(v, (dict, list)) and v:
                out.append(f"{pad}{k}:\n{dumps(v, indent + 2)}")
            else:
                out.append(f"{pad}{k}: {_fmt(v)}\n")
        return "".join(out)
    if isinstance(value, list):
        out = []
        for v in value:
            if isinstance(v, dict) and v:
                body = dumps(v, indent + 2)
                first, _, rest = body.partition("\n")
                out.append(f"{pad}- {first.strip()}\n{rest}" if rest else f"{pad}- {first.strip()}\n")
            else:
                out.append(f"{pad}- {_fmt(v)}\n")
        return "".join(out)
    return pad + _fmt(value) + "\n"


def _fmt(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, list):
        return "[" + ", ".join(_fmt(x) for x in v) + "]"
    if isinstance(v, dict) and not v:
        return "{}"
    s = str(v)
    needs_quote = (s == "" or s.strip() != s or s[0] in "[{'\"#&*!|>%@`-" or ": " in s
                   or s.endswith(":") or s.lower() in ("true", "false", "null", "~")
                   or _looks_numeric(s))
    return '"' + s.replace('"', '\\"') + '"' if needs_quote else s


def _looks_numeric(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False
