"""Self-tests of tools/tests/jslex.py, the tokenizer test_rhino_hazards.py, test_other_gate.py and test_recipe_scripts.py lint
with (v0.3 Task 8b round 3).

A template literal is one 'str' token, and each ${ ... } inside it is read as code: a string, comment, regex, nested template
or balanced brace there cannot end the substitution early (and so end the template early) or late (and so swallow the code
after it). The documented limits in jslex's docstring are pinned as such, so a change to them shows up here.
"""
import pytest

from jslex import blank, tokens
from test_rhino_hazards import lexical_in_try


def kinds(src):
    return [(t.kind, t.text) for t in tokens(src)]


# Each source -> its tokens after the template, which must be read as code: `after` is the text of the first token past the
# template (so a template that ended early or late fails), and the template's own text.
TEMPLATES = {
    "an object literal in a substitution": ("x = `a ${ { b: 1 }.b } c`; after", "`a ${ { b: 1 }.b } c`"),
    "a '}' string in a substitution": ("x = `a ${ '}' } c`; after", "`a ${ '}' } c`"),
    "a '${' string in a substitution": ("x = `a ${ '${' } c`; after", "`a ${ '${' } c`"),
    "a nested template": ("x = `a ${ `b ${ c } d` } e`; after", "`a ${ `b ${ c } d` } e`"),
    "a nested template holding a backtick string": ("x = `a ${ `b ${ '`' } d` } e`; after", "`a ${ `b ${ '`' } d` } e`"),
    "a comment holding '}' in a substitution": ("x = `a ${ /* } */ b } c`; after", "`a ${ /* } */ b } c`"),
    "a regex holding '}' in a substitution": ("x = `a ${ /}/.source } c`; after", "`a ${ /}/.source } c`"),
    "an escaped backtick and ${": ("x = `a \\` \\${ b`; after", "`a \\` \\${ b`"),
    "a multi-line substitution": ("x = `a ${\n  f({\n    k: '}'\n  })\n} c`\nafter", "`a ${\n  f({\n    k: '}'\n  })\n} c`"),
}


@pytest.mark.parametrize("name", list(TEMPLATES))
def test_template_substitution_is_read_as_code(name):
    src, template = TEMPLATES[name]
    toks = tokens(src)
    i = next(k for k, t in enumerate(toks) if t.kind == "str")
    assert toks[i].text == template
    assert toks[i + 1:] and toks[-1].text == "after", kinds(src)
    assert toks[-1].line == src.count("\n", 0, src.rindex("after")) + 1   # lines still counted through the template


def test_a_template_cannot_hide_a_try_const():
    """Round 3 J-a: counting only '${' and '}' read the '${' string as a second substitution, so the template ran on to the
    last backtick and hid the try body."""
    src = "const s = `${ '${' }`\ntry {\n const z = 1\n} catch (e) {}\nconst w = `}`\n"
    assert lexical_in_try(src) == ([3], 0)


def test_blank_wipes_a_template_with_substitutions_whole():
    src = "x = `a ${ '}' } b`; y = 1 // c\n"
    assert blank(src) == "x = `" + " " * (len("`a ${ '}' } b`") - 2) + "`; y = 1     \n"


@pytest.mark.parametrize("src,stray", [
    ("x = `a ${ b", "`a ${ b"),                                     # a substitution that never closes
    ("x = `abc\ny = 1\n", "`abc\ny = 1\n"),                         # a template that never closes
    ("x = `a ${ f({ k: 1 }) } b\n", "`a ${ f({ k: 1 }) } b\n"),      # closed substitution, open template
    ("x = `a ${ `b ${ c } d` } e", "`a ${ `b ${ c } d` } e"),        # the nested one closes, the outer does not
    ("x = `a ${ /* b } c` */ d", "`a ${ /* b } c` */ d"),             # a comment hides the substitution's '}' and '`'
    ("x = 1 /* never closed\ny = 2\n", "/* never closed\ny = 2\n"),
])
def test_unterminated_input_is_one_unterminated_token(src, stray):
    """Round 4 R10: what never closes runs to the end of the file as one 'unterminated' token, so a caller can fail on it
    instead of silently skipping the rest of the file."""
    toks = tokens(src)
    assert [t.text for t in toks if t.kind == "unterminated"] == [stray]
    assert toks[-1].kind == "unterminated" and toks[-1].end == len(src)
    with pytest.raises(ValueError, match="unterminated template or /. comment runs to the end of the file"):
        blank(src)


def test_code_inside_a_substitution_is_not_linted():
    """The documented limit (jslex docstring): a substitution's code is read only to find its end, so a try inside an arrow
    inside a ${ ... } is not seen by the lint (acorn: line 1)."""
    assert lexical_in_try("s = `${ (() => { try { const z = 1 } catch (e) {} })() }`\n") == ([], 0)


# The documented limits (jslex docstring): a '/' after '}' starts a regex, so these two divisions are misread. The pack
# writes neither; tools/check_tags.py shares the rule (test_check_tags.py pins its side).
@pytest.mark.parametrize("src,regex", [
    ("x = {} / 2 / 3", "/ 2 /"),
    ("y = function () {} / 2 / 3", "/ 2 /"),
])
def test_documented_limit_slash_after_a_brace(src, regex):
    assert [t.text for t in tokens(src) if t.kind == "regex"] == [regex]
