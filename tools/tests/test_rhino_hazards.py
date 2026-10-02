"""Lint the KubeJS scripts for constructs the pack's Rhino (rhino-2101.2.7-build.85.jar, under KubeJS 2101.7.2) gets wrong
at RUNTIME, while node's V8 (and so the node harnesses) accepts them.

1. A `const` or `let` declared anywhere lexically inside a `try`, `catch` or `finally` body (test_no_const_directly_inside_try;
   the name is Task 3's, the check is wider since Task 8b). Rhino raises `TypeError: redeclaration of var <name>` when the
   block runs, not when the script loads: the Task 9 spec review read it in javap of that jar (Interpreter.doSetConstVar,
   ScriptableObject.putConstImpl and redefineProperty raise it; Parser.defineSymbol raises it at compile time only for a
   `var` redeclared in one scope; the fork has no bytecode compiler, so every function body is interpreted). A boot therefore
   proves only top-level code, and a surrounding `catch` hides the error: dump.js once exported all 18880 recipes without
   their JSON that way (plan Task 2 Step 4 "Correction"; the comment above dump.js's `let j = null`). This lint is the only
   check before the in-game probe for code inside handlers.
   Task 8b's probe on that jar (a Java harness calling Context.evaluateString) showed: a `const` directly in a try, in an
   `if`, a plain block, a labelled block or a loop body inside a try, and in a catch that runs twice in one call, all throw;
   `let` in the same places runs. The lint still flags `let` as well as `const`, as plan Task 8b asks: one rule ("declare
   before the try") is simpler to keep than a list of which forms Rhino gets right.
   Not flagged:
   - A declaration inside a function or arrow-function body inside the try: a new function is a new scope (the probe: a
     `const` in an arrow or a function expression inside a try runs).
   - A `for (let i …)` / `for (const x of …)` head inside a try. Decision: the head does not count. The probe ran each form
     inside a try, and inside a try re-entered by an outer loop, and all of them ran with the right values (Rhino's parser
     gives a for loop its own scope for its head declarations). The loop's BODY does count.
2. A `const` declared inside a loop body (test_no_const_in_a_loop_body, Task 8b). Rhino keeps its first value: the probe's
   `for (let i = 0; i < 3; i++) { const b = i; out += b }` gives '000', not '012', and while, for-of and a switch inside a
   loop do the same, with no error at all. A `const` in a function called from the loop (forEach's arrow) is fine. The pack
   has no loop statements today; use `let`, or forEach.
   A loop body must be a block (`{ ... }`) for this check to see into it: `for (;;) if (x) { const v = 1 }` labels that
   `{` 'block', not 'loop'. So the same test also fails any for, while or do whose body is not a block ("loop body must be
   a block"), except an empty statement (`while (x);`, which declares nothing) and the `while (...)` that ends a do-while.
   Rhino's own `for each (x in xs)` loop (javap of Parser.forLoop: it reads the word "each" and calls
   ForInLoop.setIsForEach) is read as a loop too; V8 rejects it, but the lint also scans startup and client scripts, which
   no node harness loads.

The scanner is tools/tests/jslex.py's tokenizer plus a bracket stack: each `{` is labelled 'try' (the body of try, catch or
finally), 'loop' (the body of for, while or do), 'fn' (a function, arrow-function or method body), 'object' (an object
literal), 'class' (a class body) or 'block' (anything else: if/else, switch, a plain block), and a declaration is judged by
the labels between it and the nearest enclosing 'fn'. A `name(...) {` is a method only directly inside an object literal
or a class body; anywhere else that `{` starts a plain block (after ASI: `f()` then a block on the next line). An object
literal is a `{` where an expression starts: after `(`, `,`, `=`, `[`, an operator or `return` (and the like), and after a
ternary's `:`; after a case's or a label's `:` it is a block. Each `?` is matched to the next `:` at the same bracket depth
before anything else, even inside an object literal or a class body (`{ a: c ? 1 : 2 }`, a class field `x = c ? 1 : 2`),
and a count left over when its bracket closes is dropped, so no `?` can claim a later case's or label's `:` (round 4).
`?.` is optional chaining and `??` is not a ternary, but `?.5` is `? .5`. Directly inside an object literal or a class body,
any name (for, while, catch, do included), a string or number key, or `[key]` before `(` is a method name, and a `class`
there starts a class body only in a value position (after a key's ':', a ternary's '?' or a field's '='; Task 8c: a class
field named `class` is a name). `let` not followed by a name, `[` or `{` is a plain name, not a declaration; `const` always
declares (jslex reads a name that starts with a Unicode letter or a \\u escape, Task 8c). `for await (` is a loop head like
`for (`. Checked against acorn's parse (node's bundled copy) on tens of thousands of
generated programs (Task 8b rounds 3 and 4).
Limits, each a self-test case: in `do f(); while (y) { const v = 1 }` the `while` is read as a loop head, so the block after
it is flagged as a loop body; the bare `do` body is flagged as well, so such a file fails either way. The code inside a
template's ${ ... } is not linted (jslex reads it only to find its end); a template or /* comment that never closes fails
the file (scan_pack) rather than hide the rest of it.
"""
import pytest

from jslex import tokens
from kjs import ROOT

SCRIPT_DIRS = ("kubejs/server_scripts", "kubejs/startup_scripts", "kubejs/client_scripts")
# Words after which '(' is not a call or a method's parameter list.
KEYWORDS = {"if", "for", "while", "switch", "with", "catch", "function", "return", "typeof", "new", "delete", "void",
            "throw", "instanceof", "in", "of", "do", "else", "case", "yield", "await", "let", "const", "var"}
# A '{' after one of these starts an object literal (an expression is expected there); ':' is decided case by case.
OBJECT_AFTER = set("(,=[!&|?+-*%<>~^") | {"return", "typeof", "in", "of", "new", "delete", "void", "throw", "instanceof",
                                          "yield", "await"}


def _paren_kind(prev, prev2, prev3, do_tail, in_object):
    word = prev.text if prev is not None and prev.kind == "ident" else None
    if prev2 is not None and prev2.text == ".":
        word = "call" if word else None   # obj.for(...), obj.catch(...): a method call, not a keyword
    if in_object and (word or (prev is not None and (prev.text == "]" or prev.kind in ("str", "num")))):
        return "call"            # name(...), 'name'(...), 1(...) or [key](...) directly in an object or class body: a method
    if word == "catch":
        return "catch"
    if word == "while" and do_tail:
        return "dotail"          # the `while (...)` that ends a do-while: no body follows
    if word in ("for", "while") or (word in ("each", "await") and prev2 is not None and prev2.text == "for"):
        return "loophead"        # for, while, for await, and Rhino's for each (... in ...)
    after_function = prev2 is not None and (prev2.text == "function" or (
        prev2.text == "*" and prev3 is not None and prev3.text == "function"))
    if word == "function" or (word and after_function) or (
            prev is not None and prev.text == "*" and prev2 is not None and prev2.text == "function"):
        return "fn"              # function (, function name(, function* (, function* name(; any name, even `of`
    if word and word not in KEYWORDS:
        return "call"            # a call, or a method's parameters when a '{' follows the ')' inside an object
    return "group"


def _brace_kind(prev, closed, in_object, colon):
    word = prev.text if prev is not None and prev.kind == "ident" else None
    if word in ("try", "catch", "finally"):
        return "try"
    if word == "do":
        return "loop"
    if prev is None:
        return "block"
    if prev.text == "=>":
        return "fn"
    if prev.text == ")":
        if closed == "call":
            return "fn" if in_object else "block"   # a method's body, or a plain block after a call (ASI)
        return {"catch": "try", "loophead": "loop", "fn": "fn"}.get(closed, "block")
    if prev.text == ":":
        return colon
    if prev.text in OBJECT_AFTER:
        return "object"
    return "block"


# In an object or class body, the punctuation a key or member name follows; after any other punctuation a `class` is a value.
# ')', ']', '++' and '--' are here because no expression goes on from them with `class` (and `++class {}` is no valid
# target): after them, `class` is a class member named class on the next line, after ASI (`a = f()\n class = 1`).
_KEY_BEFORE = {"{", ",", ";", "}", "*", ")", "]", "++", "--"}
# The operator words after which a `class` is a value (`{ a: new class {} }`).
_VALUE_OPS = {"new", "typeof", "void", "delete", "yield", "await", "instanceof", "in"}


def declarations(src, bare=None):
    """(decls, open) for JS source `src`. decls lists every const/let declaration outside a for head as (line, keyword,
    kinds), where kinds are the labels of the enclosing '{' blocks from the innermost out, up to the nearest function body.
    open counts the brackets still open at the end, plus each template or /* comment that never closes (jslex's
    'unterminated' token, which hides the rest of the file); it is 0 for a file the scanner read correctly. When `bare` is a list, the
    line of each loop whose body is not a block is appended to it (module docstring, item 2)."""
    toks = tokens(src)
    stack, decls, closed, do_tail = [], [], None, False
    colon, case_at, class_at = "object", None, None   # the last ':''s kind; the depth of a pending case or class
    questions = {}   # depth -> the ternary '?'s at that depth still waiting for their ':'

    def check_body(k, line):
        nxt = toks[k + 1] if k + 1 < len(toks) else None
        if bare is not None and nxt is not None and nxt.text not in ("{", ";"):
            bare.append(line)

    for k, t in enumerate(toks):
        prev = toks[k - 1] if k else None
        prev2 = toks[k - 2] if k > 1 else None
        prev3 = toks[k - 3] if k > 2 else None
        nxt = toks[k + 1] if k + 1 < len(toks) else None
        in_object = bool(stack) and stack[-1][0] == "{" and stack[-1][1] in ("object", "class")
        after_do_block, do_tail = do_tail, False
        dot = prev is not None and prev.text == "."
        if t.kind == "ident" and t.text == "class" and not dot and in_object and prev is not None and (
                (prev.kind == "punct" and prev.text not in _KEY_BEFORE) or (prev.kind == "ident" and prev.text in _VALUE_OPS)) \
                and nxt is not None and (nxt.kind == "ident" or nxt.text == "{"):
            # a class expression in a value position directly in an object or class body: after an operator (a key's ':', a
            # ternary's '?', a class field's '=', '=>', '...', '||') or an operator word (`new class {}`). After _KEY_BEFORE's
            # marks, or a modifier (static, get, async), `class` is a key, a method or a field name (`{ class: 1 }`,
            # `class() {}`, `class C { class = 1; m() {} }`), and no class body follows (Task 8c). And a class expression goes
            # on with a name, `extends` or its '{', so a `class` followed by '=', ';', '(' or '}' is a member name, whatever
            # came before it.
            class_at = len(stack)
        if t.kind == "ident" and not dot and not in_object and not (nxt is not None and nxt.text == ":"):
            if t.text == "do":
                check_body(k, t.line)
            elif t.text in ("case", "default"):
                case_at = len(stack)      # the next ':' at this depth ends the case label
            elif t.text == "class":
                class_at = len(stack)     # the next '{' at this depth is the class body
        if t.kind == "ident" and t.text == "default" and not dot and not in_object and nxt is not None and nxt.text == ":":
            case_at = len(stack)
        if t.kind == "ident" and t.text == "while" and after_do_block:
            do_tail = True   # carried to the '(' that follows
        adjacent = lambda a, b: a is not None and b is not None and a.end == b.start   # noqa: E731
        nxt2 = toks[k + 2] if k + 2 < len(toks) else None
        chain = nxt is not None and nxt.text == "." and adjacent(t, nxt) and not (nxt2 is not None and nxt2.kind == "num"
                                                                                 and adjacent(nxt, nxt2))   # ?. but not ?.5
        if t.kind == "punct" and t.text == "?" and not chain and not (nxt is not None and nxt.text == "?" and adjacent(t, nxt)) \
                and not (prev is not None and prev.text == "?" and adjacent(prev, t)):
            questions[len(stack)] = questions.get(len(stack), 0) + 1   # a ternary's '?', not ?? or ?.
        if t.kind == "punct" and t.text == ":":
            # A pending ternary at this depth owns the ':' first, even inside an object (`{ a: c ? 1 : 2 }`) or a class
            # body (`x = c ? 1 : 2`); otherwise the count would outlive its ':' and take a later case's or label's.
            if questions.get(len(stack)):
                colon = "object"          # a ternary's
                questions[len(stack)] -= 1
            elif in_object:
                colon = "object"          # a key's value
            elif case_at == len(stack):
                colon, case_at = "block", None
            else:
                colon = "block"           # a label
        if t.kind == "punct" and t.text == "(":
            stack.append(("(", _paren_kind(prev, prev2, prev3, after_do_block, in_object), t.line))
        elif t.kind == "punct" and t.text == "[":
            stack.append(("[", None, t.line))
        elif t.kind == "punct" and t.text == "{":
            if class_at == len(stack):
                kind, class_at = "class", None
            elif prev is not None and prev.text == "do" and not in_object:
                kind = "doloop"
            else:
                kind = _brace_kind(prev, closed, in_object, colon)
            stack.append(("{", kind, t.line))
        elif t.kind == "punct" and t.text in ")]}":
            if stack:
                questions.pop(len(stack), None)   # no '?' outlives its bracket
                case_at = None if case_at is not None and case_at >= len(stack) else case_at
                class_at = None if class_at is not None and class_at >= len(stack) else class_at
                opener = stack.pop()
                if t.text == ")":
                    closed = opener[1]
                    if closed == "loophead":
                        check_body(k, opener[2])
                if t.text == "}" and opener[1] == "doloop":
                    do_tail = True   # a `while` right after this `}` ends the do-while
        elif t.kind == "ident" and t.text in ("const", "let"):
            nxt = toks[k + 1] if k + 1 < len(toks) else None
            if (prev is not None and prev.text == ".") or (nxt is not None and nxt.text == ":"):
                continue         # a property or key named const/let
            if t.text == "let" and (nxt is None or not (nxt.kind == "ident" or nxt.text in ("[", "{"))):
                continue         # `let` as a plain name (`let = 1`, `f(let)`): a declaration names a binding next.
                                 # `const` is a reserved word, never a name, so a const is always a declaration.
            if prev is not None and prev.text == "(" and stack and stack[-1][:2] == ("(", "loophead"):
                continue         # a for head: see the module docstring
            kinds = []
            for opener, kind, _ in reversed(stack):
                if opener == "{":
                    if kind == "fn":
                        break
                    kinds.append("loop" if kind == "doloop" else kind)
            decls.append((t.line, t.text, kinds))
    return decls, len(stack) + sum(1 for t in toks if t.kind == "unterminated")


def lexical_in_try(src):
    """(lines, open): the line of each const/let inside a try, catch or finally body (outside nested functions)."""
    decls, still_open = declarations(src)
    return [line for line, _, kinds in decls if "try" in kinds], still_open


def const_in_loop(src):
    """(lines, open): the line of each const inside a loop body (outside nested functions)."""
    decls, still_open = declarations(src)
    return [line for line, word, kinds in decls if word == "const" and "loop" in kinds], still_open


def bare_loop_bodies(src):
    """(lines, open): the line of each for, while or do whose body is not a block, so const_in_loop cannot see into it."""
    bare = []
    _, still_open = declarations(src, bare)
    return bare, still_open


def scan_pack(check, root=ROOT):
    found, scanned = [], 0
    for d in SCRIPT_DIRS:
        for js in sorted((root / d).rglob("*.js")):
            text = js.read_text(encoding="utf-8")
            stray = [t.line for t in tokens(text) if t.kind == "unterminated"]
            assert stray == [], (f"{js.relative_to(root)}:{stray[0]}: a template or /* comment that never closes runs to the "
                                 f"end of the file, and the lint cannot see past it")
            lines, still_open = check(text)
            assert still_open == 0, f"{js.relative_to(root)}: {still_open} unclosed brackets; the scanner misread the file"
            found += [f"{js.relative_to(root)}:{ln}" for ln in lines]
            scanned += 1
    assert scanned > 0, "no .js files found under " + ", ".join(SCRIPT_DIRS)
    return found


def test_no_const_directly_inside_try(tmp_path):
    found = scan_pack(lexical_in_try)
    assert found == [], ("const or let inside a try, catch or finally body (Rhino 2101: 'redeclaration of var' when it runs); "
                         "declare it before the try: " + ", ".join(found))
    # Task 3's red case: a const directly in a try is flagged, with its line, and a comment and a string are not. Since Task
    # 8b a let in a try is flagged too (line 3).
    bad = tmp_path / "bad.js"
    bad.write_text("// try { const a = 1 }\nlet s = 'try { const b = 2 }'\ntry { let c = 3 } catch (e) {}\n"
                   "try { const x = 1 } catch (e) {}\n")
    assert lexical_in_try(bad.read_text()) == ([3, 4], 0)


@pytest.mark.parametrize("src", [
    "const s = `abc ${ f(\ntry {\n  const z = 1\n} catch (e) {}\n",
    "const s = `abc\ntry {\n  const z = 1\n} catch (e) {}\n",
    "/* a comment\ntry {\n  const z = 1\n} catch (e) {}\n",
])
def test_an_unterminated_template_or_comment_fails(tmp_path, src):
    """Round 4 R10: a template or /* comment that never closes would hide the rest of the file from the lint; the file fails
    instead (scan_pack names it), and the open count is not 0."""
    js = tmp_path / "kubejs" / "server_scripts" / "a.js"
    js.parent.mkdir(parents=True)
    js.write_text(src, encoding="utf-8")
    with pytest.raises(AssertionError, match="a.js:1: a template or /. comment that never closes"):
        scan_pack(lexical_in_try, root=tmp_path)
    assert lexical_in_try(src)[1] > 0


# Each snippet -> the lines lexical_in_try flags. The Rhino probe's results for the same forms are in the module docstring.
TRY_CASES = {
    "const in catch": ("try { f() } catch (e) {\n  const a = 1\n}\n", [2]),
    "const in finally": ("try { f() } finally {\n  const a = 1\n}\n", [2]),
    "const in an if inside try": ("try {\n  if (x) {\n    const a = 1\n  }\n} catch (e) {}\n", [3]),
    "let in a plain block inside try": ("try {\n  {\n    let a = 1\n  }\n} catch (e) {}\n", [3]),
    "const in catch with no binding": ("try { f() } catch {\n  const a = 1\n}\n", [2]),
    "const in a loop body inside try": ("try {\n  for (let i = 0; i < 2; i++) {\n    const a = i\n  }\n} catch (e) {}\n", [3]),
    "for (let i ...) head inside try": ("try {\n  for (let i = 0; i < 2; i++) { f(i) }\n} catch (e) {}\n", []),
    "for (const x of ...) head inside try": ("try {\n  for (const x of xs) { f(x) }\n} catch (e) {}\n", []),
    "const in an arrow inside try": ("try {\n  xs.forEach(x => {\n    const a = x\n  })\n} catch (e) {}\n", []),
    "const in a function expression inside try": ("try {\n  g(function (x) {\n    const a = x\n  })\n} catch (e) {}\n", []),
    "const in a method inside try": ("try {\n  const o = { m(x) {\n    const a = x\n  } }\n} catch (e) {}\n", [2]),
    "const at handler top level": ("ServerEvents.recipes(event => {\n  const a = 1\n  try { f(a) } catch (e) {}\n})\n", []),
    "a handler's own try": ("ServerEvents.recipes(event => {\n  let a = null\n  try {\n    let b = 2\n  } catch (e) {}\n})\n", [4]),
    "try inside a function inside try": ("try {\n  g(() => {\n    try { const a = 1 } catch (e) {}\n  })\n} catch (e) {}\n", [3]),
    "names that only look like declarations": ("try {\n  o.const = 1\n  f({ let: 2 })\n} catch (e) {}\n", []),
    # Task 8b round 3 (L-a): a '{' after a call's ')' is a method body only inside an object literal or class body; after
    # ASI it is a plain block, and its declarations count.
    "a block after a call, in try": ("try {\n  f()\n  {\n    const a = 1\n  }\n} catch (e) {}\n", [4]),
    "a block after a call, in catch": ("try { f() } catch (e) {\n  g(e)\n  {\n    let a = 1\n  }\n}\n", [4]),
    "a block after a call, in finally": ("try { f() } finally {\n  x = g(1)\n  { const a = 1 }\n}\n", [3]),
    "a labelled block after a call": ("try {\n  f()\n  lbl: {\n    const a = 1\n  }\n} catch (e) {}\n", [4]),
    "a ternary of objects": ("try {\n  x = c ? { a: 1 } : { b: 2 }\n  const a = 1\n} catch (e) {}\n", [3]),
    # a ternary's ':' starts an expression (an object literal with a method), not a label's block
    "a method in an object after a ternary's colon": ("try {\n  x = c ? 1 : { m() {\n    const a = 1\n  } }\n} catch (e) {}\n",
                                                     []),
    "nested ternaries": ("try {\n  x = a ? b ? 1 : 2 : { m() {\n    const a = 1\n  } }\n} catch (e) {}\n", []),
    # round 4 R1: a ternary's ':' inside an object literal or a class body is the ternary's, not a key's, so its '?' cannot
    # outlive it and turn a later case's, default's or label's block into an object (whose if/for/catch would read as methods)
    "a ternary in an object, then a case block (worldgen style)": (
        "try {\n  const p = f()\n  o = { size: p.size, discard: p.discard === undefined ? 0.0 : p.discard }\n"
        "  switch (o.size) {\n    case 1: {\n      if (o.discard) {\n        g()\n        const d = 1\n      }\n    }\n  }\n"
        "} catch (e) {}\n", [2, 8]),
    "a ternary in an object, then a default block": (
        "try {\n  o = { a: c ? 1 : 2 }\n  switch (x) {\n    default: {\n      if (z) {\n        const d = 1\n      }\n    }\n"
        "  }\n} catch (e) {}\n", [6]),
    "a ternary in an object, then a catch in a case block": (
        "try {\n  o = { a: c ? 1 : 2 }\n  switch (x) {\n    case 1: {\n      try { f() } catch (e) {\n        const d = 1\n"
        "      }\n    }\n  }\n} catch (e) {}\n", [6]),
    "a ternary in an object, then a label block at its depth": (
        "try {\n  o = { a: c ? 1 : 2 }\n  if (z) {\n    lbl: {\n      for (;;) {\n        let d = 1\n      }\n    }\n  }\n"
        "} catch (e) {}\n", [6]),
    "a class field's ternary, then a label block at its depth": (
        "try {\n  class C { x = c ? 1 : 2 }\n  if (z) {\n    lbl: {\n      if (y) {\n        const d = 1\n      }\n    }\n  }\n"
        "} catch (e) {}\n", [6]),
    "?.5 is a ternary, not optional chaining": ("try {\n  x = a?.5:{ m() {\n    const q = 1\n  } }\n} catch (e) {}\n", []),
    # round 4 R12: more method and name forms
    "string- and number-named methods": ("try {\n  o = { 'm'(x) {\n    const a = 1\n  }, 1(y) { const b = 2 } }\n"
                                         "} catch (e) {}\n", []),
    "a class expression as an object value": ("try {\n  o = { k: class extends B { m() {\n    const a = 1\n  } }, class: 1, "
                                              "class() { const c = 1 } }\n} catch (e) {}\n", []),
    "let as a plain name": ("try {\n  let = 1\n  f(let)\n  x = let + 1\n} catch (e) {}\n", []),
    "a case's block": ("try {\n  switch (x) { case 1: { const a = 1 } default: { let b = 2 } }\n} catch (e) {}\n", [2, 2]),
    # L-c: function and method forms whose bodies are function scopes
    "a method named for, while, catch or do": ("try {\n  o = { for(x) {\n    const a = 1\n  }, while() { const b = 1 }, "
                                               "catch(e) { const c = 1 }, do() { const d = 1 } }\n} catch (e) {}\n", []),
    "a method in a class body": ("try {\n  class C { m(x) {\n    const a = 1\n  } static for() { const b = 1 } }\n"
                                 "} catch (e) {}\n", []),
    "a computed method name": ("try {\n  o = { [k](x) {\n    const a = 1\n  } }\n} catch (e) {}\n", []),
    "an anonymous generator": ("try {\n  g(function* (y) {\n    const a = 1\n  })\n} catch (e) {}\n", []),
    "a function named of": ("try {\n  function of(a) {\n    const b = 1\n  }\n} catch (e) {}\n", []),
    "a getter and a nested object's method": ("try {\n  x = { a: { m() { const b = 1 } }, get v() { const c = 1 } }\n"
                                             "} catch (e) {}\n", []),
    # Task 8c (8b follow-ups): a const or let whose name starts with a non-ASCII letter or a \\u escape is a declaration (const
    # is never a plain name; jslex's IDENT reads Unicode letters and \\u escapes)
    "a const with a non-ASCII name": ("try {\n  const \u00e9 = 1\n  let \u00fc = 2\n} catch (e) {}\n", [2, 3]),
    "a const named with a \\u escape": ("try {\n  const \\u0061 = 1\n} catch (e) {}\n", [2]),
    # U+2118 (℘) starts a JS identifier (Other_ID_Start) but is no Python \\w, so jslex reads it as punctuation; the
    # const is still a declaration, because only `let` can be a plain name (spec-review S1)
    "a const whose name jslex reads as punctuation": ("try {\n  const \u2118 = 1\n} catch (e) {}\n", [2]),
    # a class field named `class` is a name, not a class expression: the method after it has a function body
    "a class field named class": ("try {\n  class C { class = 1; m() {\n    const a = 1\n  } }\n} catch (e) {}\n", []),
    "a class field named class, no semicolon": ("try {\n  class C { class\n  m() { const a = 1 } }\n} catch (e) {}\n", []),
    "a class expression as a class field's value": ("try {\n  class C { k = class { m() {\n    const a = 1\n  } } }\n"
                                                    "} catch (e) {}\n", []),
    # ... also on the line after a call, an index or a postfix ++ (ASI), and before '=', ';', '(' or a name (spec-review S2;
    # each checked against acorn)
    "a class field named class after a call (ASI)": ("try { class C { a = f()\n class = 1\n m() {\n const x = 1 } } }"
                                                     " catch (e) {}", []),
    "a class field named class after an index, then a method": ("try { class C { a = b[0]\n class;\n m() {\n"
                                                               " const x = 1 } } } catch (e) {}", []),
    "a bare class field named class after a call": ("try { class C { a = f()\n class\n m() {\n const x = 1 } } }"
                                                    " catch (e) {}", []),
    "a method named class after a postfix ++": ("try { class C { a = x++\n class() {\n const x = 1 } } } catch (e) {}",
                                                []),
    "a class expression after a ternary's ?": ("try { class C { a = c ? class {\n m() {\n const x = 1 } } : 1 } }"
                                               " catch (e) {}", []),
    "a const after a class field named class": ("try { class C { a = f()\n class = 1 }\n const y = 2 } catch (e) {}",
                                                [3]),
    # `await` is a plain name in a script, so it can end a field's value: only the '=' or '(' after `class` tells
    "a class field and a method named class after await as a name": (
        "try { class C { a = await\n class = 1\n b = await\n class() {\n const x = 1 } } } catch (e) {}", []),
    # the '?' of a misread regex (`if (s) /a?b/` divides, jslex's documented limit) is dropped when its bracket closes, so it
    # cannot take the later case's or label's ':' (the verifier's demo; acorn flags line 4)
    "a '?' in a case block does not outlive its bracket": (
        "try {\n  switch (x) {\n    case 1: { if (s) /a?b/.test(t) }\n    case 2: { lbl: { if (y) { const q = 1 } } }\n  }\n"
        "} catch (e) {}\n", [4]),
}


@pytest.mark.parametrize("name", list(TRY_CASES))
def test_lexical_in_try_cases(name):
    src, lines = TRY_CASES[name]
    assert lexical_in_try(src) == (lines, 0)


def test_no_const_in_a_loop_body():
    found = scan_pack(const_in_loop)
    assert found == [], ("const inside a loop body (Rhino 2101 keeps its first value on every pass, silently); use let or "
                         "forEach: " + ", ".join(found))
    bare = scan_pack(bare_loop_bodies)
    assert bare == [], "loop body must be a block (the lint cannot see into it): " + ", ".join(bare)


# Each snippet -> (the lines const_in_loop flags, the lines bare_loop_bodies flags).
LOOP_CASES = {
    "const in a for body": ("for (let i = 0; i < 3; i++) {\n  const b = i\n}\n", [2], []),
    "const in a while body": ("while (x) {\n  const b = f()\n}\n", [2], []),
    "const in a do body": ("do {\n  const b = f()\n} while (x)\n", [2], []),
    "const in a switch inside a for-of body": ("for (const x of xs) {\n  switch (x) { default: { const b = x } }\n}\n", [2], []),
    "let in a for body": ("for (let i = 0; i < 3; i++) {\n  let b = i\n}\n", [], []),
    "const in a for head": ("for (const x of xs) { f(x) }\n", [], []),
    "const in forEach's arrow": ("xs.forEach(x => {\n  const b = x\n})\n", [], []),
    "const after a loop": ("for (let i = 0; i < 3; i++) { f(i) }\nconst b = 1\n", [], []),
    # Task 8b review: a body that is not a block hides its declarations from const_in_loop, so the loop itself is flagged.
    "for body is an if": ("for (;;) if (x) { const v = 1 }\n", [], [1]),
    "while body is a switch": ("while (x) switch (y) { default: { const v = 1 } }\n", [], [1]),
    "do body is an if": ("do if (x) { const v = 1 } while (y)\n", [], [1]),
    "for body on the next line": ("for (const x of xs)\n  f(x)\n", [], [1]),
    "empty loop body": ("while (f());\nconst b = 1\n", [], []),
    "do-while then a const": ("do {\n  f()\n} while (x)\nconst b = 1\n", [], []),
    "methods named like loops": ("o.for(1)\nconst a = o.while(2)\np.do(3)\n", [], []),
    # Task 8b round 3: a block after a call (ASI) inside a loop body is still in the loop (L-a)
    "a block after a call in a loop body": ("for (;;) {\n  f()\n  {\n    const b = 1\n  }\n}\n", [4], []),
    # a label after a statement that ended by ASI: its block is a block (so `g(y)` then `{` is a call and a block, not a
    # method), and ?. and ?? are no ternary's '?'
    "a label after an ASI statement": ("while (x) {\n  y = f(1)\n  lbl: {\n    g(y)\n    {\n      const a = 1\n    }\n  }\n}\n",
                                       [6], []),
    "a label after ?. and ??": ("while (x) {\n  y = a?.b ?? c\n  lbl: {\n    g(y)\n    {\n      const a = 1\n    }\n  }\n}\n",
                                [6], []),
    "a label after a ternary": ("while (x) {\n  y = a ? f({ k: 1 }) : 2\n  lbl: {\n    g(y)\n    {\n      const a = 1\n    }\n"
                                "  }\n}\n", [6], []),
    # Rhino's for each (L-b): a loop head, and its body a loop body
    "Rhino for each": ("for each (const x in xs) {\n  const b = x\n}\n", [2], []),
    "Rhino for each with a bare body": ("for each (x in xs) f(x)\n", [], [1]),
    "for await": ("async function g() {\n  for await (const x of xs) {\n    const d = 1\n  }\n  for await (const x of xs) f(x)\n}\n",
                  [3], [5]),
    # round 4 R1, in a loop: the ternary in the object does not turn the label's block into an object
    "a ternary in an object, then a label block in a loop": (
        "while (x) { o = { n: c ? 1 : 2 }; if (z) { lbl: { for (;;) { const a = 1 } } } }\n", [1], []),
    "a ternary in an object, then a for in a case block": (
        "for (const x of xs) {\n  o = { k: c ? 1 : 2 }\n  switch (x) {\n    case 1: {\n      for (;;) { const a = 1 }\n    }\n"
        "  }\n}\n", [5], []),
    # names that are keywords elsewhere (L-c)
    "an object key named do": ("const o = { do: 1, while: 2 }\nwhile (x) { f(o.do) }\n", [], []),
    "methods named like loops in an object": ("o = { do() { const a = 1 }, for(x) { const b = 1 } }\n", [], []),
    # Task 8c (8b follow-ups): a non-ASCII const name in a loop body, and a class field named `class` before a method
    "a const with a non-ASCII name in a loop": ("for (;;) {\n  const \u00e9 = 1\n}\n", [2], []),
    "a class field named class in a loop": ("while (x) {\n  class C { class = 1; m() { const a = 1 } }\n}\n", [], []),
    "a class field named class, then a loop in the method": (
        "class C { class; m() {\n  for (;;) {\n    const a = 1\n  }\n} }\n", [3], []),
    # spec-review S2: the same after ASI following a call or an index
    "a class field named class after a call, in a loop": (
        "for (;;) { class C { a = f()\n class = 1\n m() {\n const x = 1 } } }", [], []),
    "a method named class after an index, in a loop": ("while (x) { class C { a = g[1]\n class() {\n const x = 1 } } }",
                                                         [], []),
    # the documented limit: a bare do's `while` read as a loop head
    "limit: a block after a bare do's while": ("do f(); while (y)\n{\n  const v = 1\n}\n", [3], [1]),
}


@pytest.mark.parametrize("name", list(LOOP_CASES))
def test_const_in_loop_cases(name):
    src, lines, bare = LOOP_CASES[name]
    assert const_in_loop(src) == (lines, 0)
    assert bare_loop_bodies(src) == (bare, 0)
