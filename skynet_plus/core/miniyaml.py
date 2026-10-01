"""A small YAML subset reader and writer, so the core needs no third-party parser.

Supported: nested mappings by two-space indent, block lists (`- item`), list items that
are mappings, one-line flow mappings `{key: value, ...}` and flow lists `[a, b]` (nested
too), quoted and plain scalars, ints, floats, booleans, null, and `#` comments. Anything
else — anchors, tags, block scalars, multi-line flow — raises an error that names the
line, rather than guessing.
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


def _plain(s: str) -> Any:
    if s == "" or s in ("~", "null", "Null", "NULL"):
        return None
    if s in ("true", "True", "TRUE"):
        return True
    if s in ("false", "False", "FALSE"):
        return False
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


class _Flow:
    """Parses `{...}` and `[...]` one character at a time."""

    def __init__(self, text: str, lineno: int) -> None:
        self.s, self.i, self.lineno = text, 0, lineno

    def error(self, msg: str) -> YAMLError:
        return YAMLError(f"line {self.lineno}: {msg}")

    def skip(self) -> None:
        while self.i < len(self.s) and self.s[self.i] in " \t":
            self.i += 1

    def value(self) -> Any:
        self.skip()
        if self.i >= len(self.s):
            raise self.error("unexpected end of flow value")
        ch = self.s[self.i]
        if ch == "{":
            return self.mapping()
        if ch == "[":
            return self.sequence()
        if ch in ("'", '"'):
            return self.quoted()
        return self.plain(stop=",}]")

    def quoted(self) -> str:
        quote = self.s[self.i]
        j = self.s.find(quote, self.i + 1)
        if j < 0:
            raise self.error("unterminated quoted string")
        out = self.s[self.i + 1:j]
        self.i = j + 1
        return out

    def plain(self, stop: str) -> Any:
        start = self.i
        while self.i < len(self.s):
            ch = self.s[self.i]
            if ch == "$" and self.s.startswith("${", self.i):      # ${VAR:default} is one token
                end = self.s.find("}", self.i)
                if end < 0:
                    raise self.error("unterminated ${...}")
                self.i = end + 1
                continue
            if ch in stop:
                break
            self.i += 1
        return _plain(self.s[start:self.i].strip())

    def key(self) -> str:
        self.skip()
        if self.i < len(self.s) and self.s[self.i] in ("'", '"'):
            k = self.quoted()
        else:
            start = self.i
            while self.i < len(self.s) and self.s[self.i] not in ":,}":
                self.i += 1
            k = self.s[start:self.i].strip()
        self.skip()
        if self.i >= len(self.s) or self.s[self.i] != ":":
            raise self.error(f"expected ':' after key {k!r} in flow mapping")
        self.i += 1
        return k

    def mapping(self) -> dict:
        self.i += 1
        out: dict[str, Any] = {}
        while True:
            self.skip()
            if self.i >= len(self.s):
                raise self.error("unterminated '{'")
            if self.s[self.i] == "}":
                self.i += 1
                return out
            k = self.key()
            out[k] = self.value()
            self.skip()
            if self.i < len(self.s) and self.s[self.i] == ",":
                self.i += 1

    def sequence(self) -> list:
        self.i += 1
        out: list[Any] = []
        while True:
            self.skip()
            if self.i >= len(self.s):
                raise self.error("unterminated '['")
            if self.s[self.i] == "]":
                self.i += 1
                return out
            out.append(self.value())
            self.skip()
            if self.i < len(self.s) and self.s[self.i] == ",":
                self.i += 1

    def done(self) -> None:
        self.skip()
        if self.i != len(self.s):
            raise self.error(f"unexpected text after flow value: {self.s[self.i:]!r}")


def _scalar(text: str, lineno: int = 0) -> Any:
    s = text.strip()
    if s and s[0] in "&*!|>":
        raise YAMLError(f"line {lineno}: unsupported YAML ({s[0]!r}); use plain values, "
                        f"quoted strings, {{key: value}} or [a, b]")
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        return s[1:-1]
    if s.startswith(("{", "[")):
        flow = _Flow(s, lineno)
        value = flow.value()
        flow.done()
        return value
    return _plain(s)


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
    lines: list[tuple[int, str, int]] = []       # (indent, content, line number)
    for n, raw in enumerate(text.splitlines(), start=1):
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise YAMLError(f"line {n}: tabs are not allowed for indentation")
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        lines.append((indent, stripped.strip(), n))
    if not lines:
        return {}
    value, i = _parse_block(lines, 0, lines[0][0])
    if i != len(lines):
        raise YAMLError(f"line {lines[i][2]}: unexpected content: {lines[i][1]!r}")
    return value


def _parse_block(lines, i, indent):
    if lines[i][1].startswith("- ") or lines[i][1] == "-":
        return _parse_list(lines, i, indent)
    return _parse_map(lines, i, indent)


def _parse_map(lines, i, indent):
    result: dict[str, Any] = {}
    while i < len(lines) and lines[i][0] == indent:
        content, lineno = lines[i][1], lines[i][2]
        if content.startswith("- "):
            break
        kv = _split_key(content)
        if kv is None:
            raise YAMLError(f"line {lineno}: expected 'key: value', got {content!r}")
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
            result[key] = _scalar(rest, lineno)
    if i < len(lines) and lines[i][0] > indent:
        raise YAMLError(f"line {lines[i][2]}: bad indentation: {lines[i][1]!r}")
    return result, i


def _parse_list(lines, i, indent):
    result: list[Any] = []
    while i < len(lines) and lines[i][0] == indent and (lines[i][1].startswith("- ") or lines[i][1] == "-"):
        item, lineno = lines[i][1][1:].strip(), lines[i][2]
        if item == "":
            i += 1
            if i < len(lines) and lines[i][0] > indent:
                value, i = _parse_block(lines, i, lines[i][0])
                result.append(value)
            else:
                result.append(None)
            continue
        kv = _split_key(item)
        if kv is not None and not item.startswith(("{", "[", "'", '"')):
            lines[i] = (indent + 2, item, lineno)
            value, i = _parse_map(lines, i, indent + 2)
            result.append(value)
        else:
            result.append(_scalar(item, lineno))
            i += 1
    return result, i


# -- writing --------------------------------------------------------------------------------
def dumps(value: Any, indent: int = 0) -> str:
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
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {_fmt(x)}" for k, x in v.items()) + "}"
    s = str(v)
    needs_quote = (s == "" or s.strip() != s or s[0] in "[{'\"#&*!|>%@`-" or ": " in s
                   or " #" in s or s.endswith(":") or any(c in s for c in ",]}")
                   or s.lower() in ("true", "false", "null", "~") or _looks_numeric(s))
    return '"' + s.replace('"', '\\"') + '"' if needs_quote else s


def _looks_numeric(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def set_key(text: str, section: str, key: str, value: Any) -> str:
    """Set `section.key` in the file text, touching only that value.

    Comments, order and every other key survive. Handles the block form, the one-line
    `{key: value}` form, the `section: provider` shorthand, and a missing section.
    """
    lines = text.splitlines()
    for n, raw in enumerate(lines):
        kv = _split_key(_strip_comment(raw).strip()) if not raw.startswith((" ", "\t")) else None
        if kv is None or kv[0] != section:
            continue
        rest = kv[1]
        comment = raw[len(_strip_comment(raw)):]
        if rest.startswith("{"):
            flow = _scalar(rest, n + 1)
            flow[key] = value
            lines[n] = f"{section}: {_fmt(flow)}{comment}"
            return "\n".join(lines) + "\n"
        if rest != "":                                   # `section: provider` shorthand
            lines[n] = f"{section}:{comment}"
            lines.insert(n + 1, f"  {key}: {_fmt(value)}")
            if key != "provider":
                lines.insert(n + 1, f"  provider: {_fmt(_scalar(rest, n + 1))}")
            return "\n".join(lines) + "\n"
        m = n + 1
        while m < len(lines) and (not lines[m].strip() or lines[m].startswith((" ", "\t"))):
            inner = _strip_comment(lines[m]).strip()
            ikv = _split_key(inner) if inner else None
            if ikv and ikv[0] == key:
                indent = lines[m][: len(lines[m]) - len(lines[m].lstrip())]
                c = lines[m][len(_strip_comment(lines[m])):]
                lines[m] = f"{indent}{key}: {_fmt(value)}{c}"
                return "\n".join(lines) + "\n"
            m += 1
        lines.insert(n + 1, f"  {key}: {_fmt(value)}")
        return "\n".join(lines) + "\n"
    if lines and lines[-1].strip():
        lines.append("")
    lines += [f"{section}:", f"  {key}: {_fmt(value)}"]
    return "\n".join(lines) + "\n"
