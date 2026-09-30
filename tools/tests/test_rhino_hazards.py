"""Lint the KubeJS scripts for a construct Rhino 2101 rejects at runtime but node's V8 (and so the node harnesses) accepts.

On the pack's Rhino (rhino-2101.2.7-build.85.jar, under KubeJS 2101.7.2) a `const` declared as a direct statement of a
`try { … }` block throws `TypeError: redeclaration of var <name>` when the block runs. A surrounding `catch` hides it:
dump.js once exported all 18880 recipes without their JSON that way. Sources: docs/superpowers/plans/
2026-09-25-v0.3-tiers-5-6.md, Task 2 Step 4 "Correction (execution, session 13)", whose standalone harness on that jar
showed `let` inside `try` works and `const` does not; kubejs/server_scripts/dump.js (the comment above `let j = null`);
tools/tests/test_check_recipes.py::test_rows_without_a_json_body_fail_and_are_named. So `let` is not flagged.

The scanner is a small tokenizer: it skips comments, string and template literals and regex literals, tracks `{ ( [`
nesting, and flags a `const` whose innermost opener is the `{` of a `try`. A `const` in a nested function or block inside
the try, or in a `for (const …)` head, is not a direct statement of the try block and is not flagged.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIRS = ("kubejs/server_scripts", "kubejs/startup_scripts", "kubejs/client_scripts")
IDENT = re.compile(r"[A-Za-z_$][\w$]*")
NUMBER = re.compile(r"\d[\w.]*")
# After one of these, a '/' starts a regex literal; after anything else (an identifier, number, ')' or ']') it divides.
REGEX_AFTER_WORDS = {"return", "typeof", "case", "do", "else", "in", "of", "new", "delete", "void", "throw", "instanceof"}


def const_in_try(src):
    """(lines, open) for JS source `src`: the line of each `const` that is a direct statement of a `try { … }` block, and
    how many `{ ( [` are still open at the end (0 for a file the tokenizer read correctly)."""
    hits, stack = [], []     # stack of openers: '{try', '{', '(', '['
    prev = None               # the previous significant token
    i, line, n = 0, 1, len(src)
    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
        elif c.isspace():
            i += 1
        elif src.startswith("//", i):
            i = src.find("\n", i)
            i = n if i < 0 else i
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            line += src.count("\n", i, j)
            i = j
        elif c in "'\"`":
            j = i + 1
            depth = 0         # ${ … } nesting inside a template literal
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if c == "`" and src.startswith("${", j):
                    depth += 1
                    j += 2
                    continue
                if c == "`" and depth and src[j] == "}":
                    depth -= 1
                elif src[j] == c and not depth:
                    break
                elif src[j] == "\n" and c != "`":
                    break     # an unterminated quote: stop at the line end rather than swallow the file
                j += 1
            line += src.count("\n", i, j)
            i = j if j < n and src[j] == "\n" and c != "`" else j + 1
            prev = "str"
        elif c == "/" and (prev is None or prev in REGEX_AFTER_WORDS or (len(prev) == 1 and prev in "(,=:[!&|?{};+-*%<>~^")):
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
            m = IDENT.match(src, j + 1)   # flags
            i = m.end() if m else j + 1
            prev = "regex"
        elif IDENT.match(src, i):
            word = IDENT.match(src, i).group()
            if word == "const" and stack and stack[-1] == "{try":
                hits.append(line)
            i += len(word)
            prev = word
        elif NUMBER.match(src, i):
            i = NUMBER.match(src, i).end()
            prev = "num"
        else:
            if c == "{":
                stack.append("{try" if prev == "try" else "{")
            elif c in "([":
                stack.append(c)
            elif c in "})]" and stack:
                stack.pop()
            i += 1
            prev = c
    return hits, len(stack)


def test_no_const_directly_inside_try(tmp_path):
    found, scanned = [], 0
    for d in SCRIPT_DIRS:
        for js in sorted((ROOT / d).rglob("*.js")):
            lines, still_open = const_in_try(js.read_text(encoding="utf-8"))
            assert still_open == 0, f"{js.relative_to(ROOT)}: {still_open} unclosed brackets; the scanner misread the file"
            found += [f"{js.relative_to(ROOT)}:{ln}" for ln in lines]
            scanned += 1
    assert scanned > 0, "no .js files found under " + ", ".join(SCRIPT_DIRS)
    assert found == [], "const declared directly inside try (Rhino 2101: 'redeclaration of var'); use let: " + ", ".join(found)
    # The red case: the scanner does flag the construct, with its line; `let`, a comment and a string are not flagged.
    bad = tmp_path / "bad.js"
    bad.write_text("// try { const a = 1 }\nlet s = 'try { const b = 2 }'\ntry { let c = 3 } catch (e) {}\n"
                   "try { const x = 1 } catch (e) {}\n")
    assert const_in_try(bad.read_text()) == ([4], 0)
