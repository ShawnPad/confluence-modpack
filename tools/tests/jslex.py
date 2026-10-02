"""A small JavaScript lexer shared by the script lints (v0.3 Task 8b): test_rhino_hazards.py (Rhino traps) and
test_other_gate.py's top-level-name scan.

It is not a parser. It reads the pack's KubeJS scripts well enough to find declarations and brackets: it skips comments,
reads string, template and regex literals as single tokens, and emits identifiers, numbers and punctuation (each
punctuation mark one token, except '=>', '++' and '--', each read whole, '++' and '--' greedily from the left as JS does).
Its limits, each checked by a self-test (test_jslex.py, and the callers' own):
  - A '/' starts a regex literal after nothing, after one of REGEX_AFTER's punctuation marks, or after one of its keywords;
    after anything else (a name, a number, ')', ']', '++' or '--') it is division. So `f(x) / 2` and `i++ / 2` divide, and
    `if (x) /re/.test(s)` is misread as division. '}' is in REGEX_AFTER (a block's end: `}\n/re/.test(s)`), so a '/' after
    an object literal or a function expression, `x = {} / 2` or `function () {} / 2`, is misread as a regex. The pack writes
    none of these. tools/check_tags.py's comment stripper applies the same rule (test_check_tags.py checks they agree).
  - A '...' or '"' string stops at the end of its line even when unterminated, so one stray quote cannot swallow the file.
  - A template literal is one token. Each ${ ... } in it is read as code, recursively: its strings, comments, regex literals,
    nested templates and balanced braces are read as such, and the first '}' outside them ends it. So `${ '}' }`,
    `${ '${' }` and `${ { a: 1 }.a }` end where JS ends them. The code inside a ${ ... } is read only to find its end: its
    tokens are not emitted, so the lints do not see into it (a `try { const z = 1 }` in an arrow inside a substitution is
    not flagged). The pack's substitutions are plain names and member reads.
  - A template that never closes (its own backtick or one of its ${ ... }), and a /* comment with no */, would run to the end
    of the file and hide everything after it. Each becomes one 'unterminated' token instead, and every caller fails on it:
    test_rhino_hazards.py (its open count), test_recipe_scripts.py's dump lint, and blank(), which raises.
  - A regex literal ends at its line's end at the latest.
"""
import re
from collections import namedtuple

Token = namedtuple("Token", "kind text line start end")   # kind: 'ident', 'num', 'str', 'regex', 'punct' or 'unterminated'

# A name: it starts with a Unicode letter, '_', '$' or a \u escape (\uXXXX or \u{X...}), and goes on with those, digits and
# the joiners U+200C/U+200D (Task 8c: `const \u00e9 = 1`, an e-acute written as such or as the escape, is a declaration the
# Rhino lint must see). Not every Unicode ID_Start is a letter here (Python's \w is close, not equal); the pack's names are
# ASCII.
_ESCAPE = r"\\u(?:[0-9A-Fa-f]{4}|\{[0-9A-Fa-f]+\})"
IDENT = re.compile(r"(?:[^\W\d]|\$|" + _ESCAPE + r")(?:[\w$\u200c\u200d]|" + _ESCAPE + r")*")
NUMBER = re.compile(r"\d[\w.]*")
# After one of these, a '/' starts a regex literal; after anything else (a name, number, ')' or ']') it divides.
REGEX_AFTER = set("(,=:[!&|?{};+-*%<>~^") | {"=>", "return", "typeof", "case", "do", "else", "in", "of", "new", "delete",
                                             "void", "throw", "instanceof", "yield", "await"}


def scan(src):
    """(tokens, comments): every token of `src` in order, and the (start, end) span of every comment."""
    toks, comments, _ = _scan(src, 0, False)
    return toks, comments


def _template_end(src, i):
    """(end, closed) for the template literal that starts with the '`' at src[i]: the index just past its closing '`', or
    len(src) and False when it never closes. Each ${ ... } is scanned as code (_scan with stop=True), so a quote, comment,
    regex, nested template or balanced brace inside it cannot end the substitution early or late."""
    j, n = i + 1, len(src)
    while j < n:
        if src[j] == "\\":
            j += 2
        elif src[j] == "`":
            return j + 1, True
        elif src.startswith("${", j):
            j = _scan(src, j + 2, True)[2] + 1   # just past the substitution's closing '}' (past len(src) if none)
        else:
            j += 1
    return n, False


def _scan(src, i, stop):
    """(tokens, comments, end) from src[i:]. With stop, the scan is a template substitution's code: it ends at the first
    '}' that closes no '{' of its own, and `end` is that '}''s index (len(src) if there is none)."""
    toks, comments = [], []
    prev = None               # the previous token's text ('str' / 'regex' / 'num' for literals)
    line, n, depth = 1 + src.count("\n", 0, i), len(src), 0
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
        elif c.isspace():
            i += 1
        elif src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
            comments.append((i, j))
            i = j
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            if j < 0:
                toks.append(Token("unterminated", src[i:], line, i, n))
            j = n if j < 0 else j + 2
            comments.append((i, j))
            line += src.count("\n", i, j)
            i = j
        elif c == "`":
            end, closed = _template_end(src, i)
            toks.append(Token("str" if closed else "unterminated", src[i:end], line, i, end))
            line += src.count("\n", i, end)
            i, prev = end, "str"
        elif c in "'\"":
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == c:
                    break
                if src[j] == "\n":
                    break         # an unterminated quote: stop at the line end rather than swallow the file
                j += 1
            end = j if j < n and src[j] == "\n" else min(j + 1, n)
            toks.append(Token("str", src[i:end], line, i, end))
            line += src.count("\n", i, end)
            i, prev = end, "str"
        elif c == "/" and (prev is None or prev in REGEX_AFTER):
            j, in_class = i + 1, False
            while j < n and src[j] != "\n":
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "[":
                    in_class = True
                elif src[j] == "]":
                    in_class = False
                elif src[j] == "/" and not in_class:
                    break
                j += 1
            m = IDENT.match(src, j + 1) if j < n and src[j] == "/" else None   # flags
            end = m.end() if m else min(j + 1, n) if j < n and src[j] == "/" else j
            toks.append(Token("regex", src[i:end], line, i, end))
            i, prev = end, "regex"
        elif IDENT.match(src, i):
            m = IDENT.match(src, i)
            toks.append(Token("ident", m.group(), line, i, m.end()))
            i, prev = m.end(), m.group()
        elif NUMBER.match(src, i):
            m = NUMBER.match(src, i)
            toks.append(Token("num", m.group(), line, i, m.end()))
            i, prev = m.end(), "num"
        else:
            text = next((op for op in ("=>", "++", "--") if src.startswith(op, i)), c)
            if stop and text == "}":
                if depth == 0:
                    return toks, comments, i
                depth -= 1
            elif stop and text == "{":
                depth += 1
            toks.append(Token("punct", text, line, i, i + len(text)))
            i, prev = i + len(text), text
    return toks, comments, n


def tokens(src):
    return scan(src)[0]


def blank(src):
    """src with every comment, and the inside of every string, template and regex literal, turned into spaces (newlines
    kept), so what is left is code at its own line and column. A '/*' inside a line comment (a path such as data/*/recipe)
    therefore opens nothing."""
    toks, comments = scan(src)
    stray = next((t for t in toks if t.kind == "unterminated"), None)
    if stray is not None:
        raise ValueError(f"line {stray.line}: an unterminated template or /* comment runs to the end of the file")
    out = list(src)

    def wipe(a, b):
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    for a, b in comments:
        wipe(a, b)
    for t in toks:
        if t.kind == "str":
            closed = len(t.text) > 1 and t.text[-1] == t.text[0]
            wipe(t.start + 1, t.end - 1 if closed else t.end)
        elif t.kind == "regex":
            close = t.text.rfind("/")
            wipe(t.start + 1, t.start + close if close > 0 else t.end)
    return "".join(out)
