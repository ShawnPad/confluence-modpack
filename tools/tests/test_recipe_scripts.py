"""Pack-wide checks over every server script at once (v0.3 Task 8b).

The recipe tests (test_mek_tier5.py, test_tier6_space_recipes.py, test_ae2_recipes.py, test_bypass_v03.py) each run only the
scripts they pin, so a second maker of a pinned output in another file is invisible to them. Here the shared runner
(tools/tests/run_server_scripts.js, through kjs.run) loads every server script, as the boot does: every tiers/*.js,
bypass.js, events.js, loot.js, worldgen.js, dump.js, tagcheck.js and lib/*.js, in KubeJS's load order. Then:
  - every script loads and every handler runs with no error, and the only recipes-event calls outside shaped, shapeless,
    custom and remove are dump.js's two (DUMP_CALLS);
  - the callbacks dump.js passes to those two calls only read each recipe (DUMP_RECIPE_CALLS): the runner calls each
    callback once with a recording recipe probe, so an edit made inside one (r.replaceInput, r.json.add, a call chained on
    a read such as r.get('result').setCount(64)) is seen. One probe takes one side of a branch on what it reads, so dump.js's
    source is also linted: it may name only the members in DUMP_MEMBERS (an allowlist, round 4), wherever they sit;
  - dump.js adds, removes and tags nothing: no recipe, custom, removal or tag row names it, from its handler or from a
    callback inside it;
  - every removal in the pack is one an owner test pins (PACK_REMOVALS): the four recipe tests' own removal lists, plus the
    v0.1-v0.2 removals in tiers/tier1.js-tier4.js that no owner test reads, written out here. So a removal in a file whose
    test does not run it (event.remove({ mod: 'ae2' }) in tier2.js), or a second copy of a pinned one, fails. Removals are
    compared by form and value (removal_key), so { id: 'output:<x>' } cannot pass as an output removal;
  - each output the four files pin is made by exactly the recipe ids they name for it, in any ServerEvents.recipes handler
    of any server script, with or without an id. The ids are imported from each file's SOLE_MAKERS, which is built from its
    own EXPECTED or spec tables, not copied;
  - no two recipes share an id.
Not covered here: recipes that never pass through a recipes handler, that is datapack JSON (kubejs/data/**/recipe/, and every
mod's own data) and anything a script adds with generateData or highPriorityData. Those are left to plan Task 8c's dump-based
sole_producers check, which reads the post-boot recipe dump.
node runs V8, not the pack's Rhino (run_server_scripts.js header), so this pins what the scripts ask KubeJS to do; the boot is
the load proof.
"""
import json
from collections import Counter

import pytest

import test_ae2_recipes
import test_bypass_v03
import test_mek_tier5
import test_tier6_space_recipes
from jslex import tokens
from kjs import SCRIPTS_ENV, SCRIPTS_PREFIX, all_rows, output_problem, products, run, scripts_root

SOURCES = (test_mek_tier5, test_tier6_space_recipes, test_ae2_recipes, test_bypass_v03)
SOLE_MAKERS = {}
for _module in SOURCES:
    for _output, _ids in _module.SOLE_MAKERS.items():
        SOLE_MAKERS.setdefault(_output, {})[_module.__name__] = _ids
DUMP = "kubejs/server_scripts/dump.js"
# dump.js walks the recipes (research/phase6-recipe-dump-and-fire-charge.md §1): the runner records both calls and runs each
# callback once with a recording recipe probe (`callbacks`).
DUMP_CALLS = [
    {"member": "forEachRecipe", "args": [{}, "<function>"], "file": DUMP},
    {"member": "addedRecipes.forEach", "args": ["<function>"], "file": DUMP},
]
# What dump.js's row(r) does to each recipe it walks (read from dump.js): r.get('result') (and r.get('output') only when that
# is empty, which the probe's inert return never is), r.serializeChanges() (which KubeJS repeats itself, dump.js header) and
# r.getOrCreateId(). String(r) coerces the probe and records nothing. Anything else, an edit above all, fails.
DUMP_RECIPE_CALLS = sorted((call, "call", member) for call in ("forEachRecipe", "addedRecipes.forEach")
                           for member in ("get", "serializeChanges", "getOrCreateId"))


# Every removal in the pack, with the owner list that pins it, in the runner's legacy `removed` form ('<id>', '/regex/flags',
# 'output:<item>'; removal_key reads each back to its form). The four recipe tests' lists are imported, so a change there
# moves this too. Each removal belongs to exactly one owner list: a removal two lists pin counts twice here, so it shows up
# as "missing" (the scripts make it once). A new task that removes recipes adds its owner test's list to PACK_REMOVALS.
# EARLY_TIER_REMOVALS covers v0.1-v0.2 only: the removals in tiers/tier1.js-tier4.js that have no owner pytest, written out
# from those files as they stand (61f1a11); each matches a tools/gates.yaml `removed:` row the boot asserts absent, except
# output:kubejs:twilight_key (replaceShaped of the pack's own item, which has no default recipe).
EARLY_TIER_REMOVALS = [
    # tiers/tier1.js
    "output:minecraft:flint_and_steel", "output:mekanism:metallurgic_infuser", "output:ars_nouveau:enchanting_apparatus",
    "minecraft:fire_charge", "ars_nouveau:fire_essence_to_charge",
    # tiers/tier2.js
    "output:kubejs:twilight_key", "output:irons_spellbooks:arcane_anvil", "output:toms_storage:storage_terminal",
    "output:toms_storage:inventory_connector", "powah:energizing/spirited_crystal",
    # tiers/tier3.js (v0.2; the D113 swaps are test_mek_tier5.py's)
    "output:undergarden:catalyst", "powah:energizing/nitro_crystal", "mekanism:control_circuit/elite",
    "mekanism:control_circuit/infused_elite", "mekanism:processing/refined_obsidian/ingot/from_dust",
    "output:ars_nouveau:ritual_brazier", "output:irons_spellbooks:lightning_upgrade_orb", "output:mekanism:qio_dashboard",
    "mekanism:qio_drive_array", "output:mekanism:qio_importer", "output:mekanism:qio_exporter",
    # tiers/tier4.js
    "output:minecraft:ender_eye", "ars_nouveau:planarium",
]
PACK_REMOVALS = {
    "test_bypass_v03.REMOVED_ALL": list(test_bypass_v03.REMOVED_ALL),
    "test_mek_tier5.REMOVED_BY_ID": list(test_mek_tier5.REMOVED_BY_ID),
    "test_ae2_recipes.REMOVED_BY_ID": list(test_ae2_recipes.REMOVED_BY_ID),
    "test_tier6_space_recipes.SHAPED outputs": ["output:" + v[0] for v in test_tier6_space_recipes.SHAPED.values()],
    "EARLY_TIER_REMOVALS": EARLY_TIER_REMOVALS,
}
# The members dump.js may name (round 4 R3), read from dump.js as it stands: an allowlist, not a ban list. Under Rhino the
# recipe `r` a forEachRecipe or addedRecipes.forEach callback receives is a RecipeFunction (KubeRecipe.convertJavaToJs), and
# RecipeFunction.get falls back to its builderFunctions: a setter for every name RecipeKey.getValidFunctionNames() gives
# (r.result(x), r.ingredient(x), r.pattern(x), r.key(x), r.xp(x), r.cookingTime(x), ...) plus each schema's own functions
# (r.noMirror(), ...), which differ per recipe type and per mod. No ban list can name them all, so any member not listed here
# fails, on any receiver (the lint does not know which name is `r`). A member dump.js starts to need goes here, with the
# reason it only reads.
DUMP_MEMBERS = {
    "get", "serializeChanges", "json", "getOrCreateId",   # on each recipe (row(r); the dump.js header says why each only reads)
    "slice", "lastIndexOf", "length",                      # on String(r)
    "forEachRecipe", "addedRecipes", "forEach", "push",     # the walk (DUMP_CALLS) and the rows array
    "recipes", "write", "log",                             # ServerEvents.recipes, JsonIO.write, console.log
}
# Where three of them may stand (Task 8c, 8b follow-up F3): push only on dump.js's own `rows`, forEach only on
# event.addedRecipes, and write only as JsonIO.write('kubejs/exported/recipes.json', ...). So `r.get('result').push(x)` or
# `.forEach(...)` on a list a recipe hands out (which would edit it) fails, as does a write anywhere else.
DUMP_RECEIVERS = {"push": ("rows",), "forEach": ("event", "addedRecipes"), "write": ("JsonIO",)}
DUMP_PATH = "kubejs/exported/recipes.json"
# Names that never join DUMP_MEMBERS (Task 8c, 8b follow-up F4): the recipe-editing calls and fields of the 8b round-3 ban
# list (DUMP_EDIT_CALLS and DUMP_EDIT_FIELDS in that tree, less `json`, which dump.js reads through serializeChanges()), plus
# id, type, group, set, add and remove. test_dump_never_is_disjoint_from_dump_members holds the line.
DUMP_NEVER = {
    # round 3 DUMP_EDIT_CALLS
    "setValue", "replaceInput", "replaceOutput", "group", "id", "ingredientAction", "merge", "set", "stage",
    "consumeIngredient", "customIngredientAction", "damageIngredient", "keepIngredient", "modifyResult", "replaceIngredient",
    "remove", "save", "afterLoaded", "deserialize", "initValues", "serialize", "validate", "kjs$setGroup", "setGroup",
    "addRecipe", "custom", "shaped", "shapeless", "smelting", "blasting", "smoking", "campfireCooking", "stonecutting",
    "smithing", "smithingTrim", "vanillaShaped", "vanillaShapeless", "applyChanges", "discoverRecipes", "finishEvent", "post",
    "postEvent", "takeId", "handleFailedRecipe", "add", "addProperty", "addAll", "clear", "put", "putAll", "putIfAbsent",
    "removeAll", "removeIf", "retainAll", "replaceAll", "compute", "computeIfAbsent", "computeIfPresent",
    # round 3 DUMP_EDIT_FIELDS, less json
    "changed", "creationError", "newRecipe", "removed", "originalJson", "type", "sourceLine",
}
ASSIGN_OPS = {"=", "+=", "-=", "*=", "/=", "%=", "**=", "<<=", ">>=", ">>>=", "&=", "|=", "^=", "&&=", "||=", "??="}
# A '[' right after one of these is a member access (x[k], f()[k], a[0][1]); after anything else it starts an array literal.
_NOT_A_RECEIVER = {"return", "typeof", "in", "of", "new", "delete", "void", "throw", "instanceof", "yield", "await", "case",
                   "do", "else", "const", "let", "var"}


def _assignment(op):
    """The assignment operator ('=', '+=', '++', ...) a run of adjacent punctuation right after a member starts with, or None
    when it compares ('==', '<=', '!=') or is an arrow ('=>')."""
    if op.startswith(("++", "--")):
        return op[:2]
    a = next((a for a in sorted(ASSIGN_OPS, key=len, reverse=True) if op.startswith(a)), None)
    return None if a is None or (a == "=" and op[1:2] in ("=", ">")) else a


def _at_its_receiver(toks, i):
    """Whether the member token toks[i] (push, forEach or write, after a '.') stands on its DUMP_RECEIVERS chain, which
    starts a member chain (no '.' before it), and a write takes the DUMP_PATH literal and then a ','."""
    chain = DUMP_RECEIVERS[toks[i].text]
    start = i - 2 * len(chain)
    if start < 0 or (start > 0 and toks[start - 1].text == "."):
        return False
    for n, name in enumerate(chain):
        if toks[start + 2 * n].kind != "ident" or toks[start + 2 * n].text != name or toks[start + 2 * n + 1].text != ".":
            return False
    if toks[i].text == "write":
        arg = toks[i + 1:i + 4]
        return (len(arg) == 3 and arg[0].text == "(" and arg[1].kind == "str" and arg[1].text[0] in "'\""
                and arg[1].text[1:-1] == DUMP_PATH and arg[2].text == ",")
    return True


def dump_lint(src):
    """(line, what) for each thing in src that could edit a recipe: a member not in DUMP_MEMBERS (`.name`, on any receiver,
    called or not, and `['name']`), an assignment, ++ or -- on any member, a computed member called or assigned (`x[k](`,
    `x[k] =`), `delete`, and a template or comment that never closes (jslex: it would hide the rest of the file). Comments
    and strings are skipped (jslex), so only code counts. Not seen: a member reached without '.' or '[' (destructuring
    `const { result } = r`, Rhino's `with (r)`), and code inside a template's ${...}; dump.js uses neither.
    Task 8c (8b follow-ups F3): any computed access whose key is not a quoted string literal naming a DUMP_MEMBERS member
    (`x[k]`, `x[0]`, x[`get`], `x?.[k]`), read or not, since a key computed at run time can name anything; a '\\' right
    after '.' (a member written with an escape, `r.\\u0067et`, is matched by no name here); and push, forEach and write
    away from their DUMP_RECEIVERS (write only with the DUMP_PATH literal as its first argument)."""
    toks = tokens(src)
    at = lambda k: toks[k] if 0 <= k < len(toks) else None   # noqa: E731
    hits = []

    def op_after(j):   # the run of adjacent punctuation starting at token j
        op, k = "", j
        while at(k) is not None and at(k).kind == "punct" and (k == j or at(k).start == at(k - 1).end):
            op += at(k).text
            k += 1
        return op

    for i, t in enumerate(toks):
        prev = at(i - 1)
        if t.kind == "unterminated":
            hits.append((t.line, "unterminated template or comment"))
        elif t.kind == "ident" and t.text == "delete" and not (prev is not None and prev.text == "."):
            hits.append((t.line, "delete"))
        elif t.kind == "punct" and t.text.startswith("\\") and prev is not None and prev.text == ".":
            hits.append((t.line, ".\\"))
        elif t.kind == "ident" and prev is not None and prev.text == ".":
            if t.text not in DUMP_MEMBERS or "\\" in t.text:
                hits.append((t.line, f".{t.text}"))
            elif _assignment(op_after(i + 1)):
                hits.append((t.line, f".{t.text} {_assignment(op_after(i + 1))}"))
            elif t.text in DUMP_RECEIVERS and not _at_its_receiver(toks, i):
                hits.append((t.line, f".{t.text}"))
        elif t.kind == "punct" and t.text in ("++", "--"):   # a prefix ++ / -- on a member: ++a.b, --a[k]
            j = i + 1
            if at(j) is not None and at(j).kind == "ident":
                while at(j + 1) is not None and at(j + 1).text in (".", "["):
                    if at(j + 1).text == "[":
                        depth, j = 1, j + 2
                        while at(j) is not None and depth:
                            depth += {"[": 1, "]": -1}.get(at(j).text, 0)
                            j += 1
                        j -= 1
                    elif at(j + 2) is not None and at(j + 2).kind == "ident":
                        j += 2
                    else:
                        break
                if j > i + 1 and (at(j + 1) is None or at(j + 1).text not in ("(",)):
                    hits.append((at(j).line, f"{t.text}{'.' + at(j).text if at(j).kind == 'ident' else '[...]'}"))
        elif t.kind == "punct" and t.text == "[" and prev is not None and (
                (prev.kind in ("ident", "str") and prev.text not in _NOT_A_RECEIVER) or prev.text in (")", "]")
                or (prev.text == "." and at(i - 2) is not None and at(i - 2).text == "?")):   # x?.[k]
            depth, j = 1, i + 1   # a member access: find its ']'
            while at(j) is not None and depth:
                depth += {"[": 1, "]": -1}.get(at(j).text, 0)
                j += 1
            key = toks[i + 1] if j == i + 3 and toks[i + 1].kind == "str" and toks[i + 1].text[0] in "'\"" else None
            nxt, op = at(j), op_after(j)
            called = nxt is not None and (nxt.text == "(" or (
                nxt.text == "?" and at(j + 1) is not None and at(j + 1).text == "." and at(j + 2) is not None
                and at(j + 2).text == "("))
            if key is not None:   # x['name'] is x.name
                if key.text[1:-1] not in DUMP_MEMBERS:
                    hits.append((t.line, f"[{key.text}]"))
                elif _assignment(op):
                    hits.append((t.line, f"[{key.text}] {_assignment(op)}"))
            elif called:
                hits.append((t.line, "[...]("))
            elif _assignment(op):
                hits.append((t.line, f"[...] {_assignment(op)}"))
            else:
                hits.append((t.line, "[...]"))   # a computed key, read: it can name anything at run time
    return hits


@pytest.fixture(scope="module")
def everything():
    return run(all_scripts=True)


def test_every_server_script_loads_and_runs(everything):
    assert everything["errors"] == []
    assert everything["skipped"] == []
    on_disk = sorted(SCRIPTS_PREFIX + p.relative_to(scripts_root()).as_posix() for p in scripts_root().rglob("*.js"))
    assert sorted(everything["loaded"]) == on_disk
    assert [{k: o[k] for k in ("member", "args", "file")} for o in everything["other"]] == DUMP_CALLS


def test_dump_callbacks_only_read_each_recipe(everything):
    rows = everything["callbacks"]
    assert {c["file"] for c in rows} == {DUMP}, rows
    assert sorted({(c["call"], c["op"], c["member"]) for c in rows}) == DUMP_RECIPE_CALLS, rows


def test_dump_adds_removes_and_tags_nothing(everything):
    """Round 3 V4: dump.js's handler, and every callback inside it (the runner names a callback's rows after the handler's
    file), records no recipe, custom, removal or tag edit. event.remove({ id: r.getOrCreateId() }) in a callback fails here."""
    made = {key: [r for r in everything[key] if r["file"] == DUMP] for key in ("recipes", "customs", "filters", "tagEvents")}
    assert {k: v for k, v in made.items() if v} == {}


def test_dump_source_names_only_allowed_members():
    """Round 3 N4, round 4 R3: the probe takes one side of a branch on what it reads, so an edit behind
    `if (String(r.getOrCreateId()).startsWith('ae2:'))` never runs here. dump.js's source names only DUMP_MEMBERS, run or
    not, and assigns, deletes and increments none."""
    src = (scripts_root() / DUMP.removeprefix(SCRIPTS_PREFIX)).read_text(encoding="utf-8")
    assert dump_lint(src) == [], (
        "dump.js names a member outside DUMP_MEMBERS, or assigns, deletes or increments one (line, what). The lint matches "
        "member names on any receiver, not only the recipe `r`: under Rhino any builder function (r.result(x), "
        "r.ingredient(x), r.noMirror(), ...) edits the recipe. If dump.js needs a new member that only reads, add it to "
        "DUMP_MEMBERS in tools/tests/test_recipe_scripts.py with the reason it only reads.")


@pytest.mark.parametrize("src,hits", [
    # dump.js's own reads
    ("r.get('result'); r.serializeChanges().json; String(r.getOrCreateId()); rows.push(x); event.forEachRecipe({}, f)", []),
    ("const s = String(r)\nreturn s.slice(s.lastIndexOf('[') + 1, s.length - 1)\nevent.addedRecipes.forEach(f)", []),
    ("ServerEvents.recipes(e => {})\nJsonIO.write('kubejs/exported/recipes.json', rows)\nconsole.log('x')\nconst rows = []\n"
     "for (const k of [1, 2]) f(k)", []),
    # adapted round 3 cases: every member outside the allowlist, called or not
    ("if (String(r.getOrCreateId()).startsWith('ae2:')) r.replaceInput('a', 'b')", [(1, ".startsWith"), (1, ".replaceInput")]),
    ("r.get('result').setCount(64)", [(1, ".setCount")]),
    ("r.json.add('x', 1)\nr.json.addProperty('y', 2)", [(1, ".add"), (2, ".addProperty")]),
    ("r['remove']()\nr[\"id\"]('a:b')\nr[k](1)\nr['get']('result')\nr['json'] = 1",
     [(1, "['remove']"), (2, '["id"]'), (3, "[...]("), (5, "['json'] =")]),
    ("r.id = 'a:b'\nr.group += 'x'\nr.changed++\n--r.removed\nr.json=(x)\nr.json<<=1\nrows.length++\n++r.json\nr[k] = 1", [
        (1, ".id"), (2, ".group"), (3, ".changed"), (4, "--.removed"), (4, ".removed"), (5, ".json ="), (6, ".json <<="),
        (7, ".length ++"), (8, "++.json"), (9, "[...] =")]),
    ("if (r.json <= 1 || r.json >= 2 || r.json != 3 || r.json !== 4) z()\nif (r.json == 'a') x()\nconst f = r.json => 1", []),
    ("event.recipes.kubejs.shaped('a', ['A'], {})", [(1, ".kubejs"), (1, ".shaped")]),
    ("// r.remove()\nconst s = 'r.replaceInput(x)'\nconst t = `${'r.remove()'}`", []),
    ("event.addedRecipes.clear()\nevent.remove({ id: x })\ndelete r.json", [(1, ".clear"), (2, ".remove"), (3, "delete")]),
    # round 4 R3: Rhino's builder functions on a RecipeFunction, behind a branch the probe does not take
    ("if (String(r.getOrCreateId()) === 'a:b') r.result('ae2:drive')", [(1, ".result")]),
    ("if (r.json == null) r.ingredient('minecraft:dirt')", [(1, ".ingredient")]),
    ("if (out === '') { r.noMirror() }\nconst g = r.xp\ng(1)", [(1, ".noMirror"), (2, ".xp")]),
    ("r?.cookingTime?.(5)", [(1, ".cookingTime")]),
    ("const s = `${x}\nr.remove()", [(1, "unterminated template or comment")]),
    # Task 8c (8b follow-up F3): every computed member access whose key is not a DUMP_MEMBERS string literal, read or not
    ("const g = r[k]\ng()\nr?.[k]?.()\nr[0]\nr[`get`]('result')\nrows['length']",
     [(1, "[...]"), (3, "[...]("), (4, "[...]"), (5, "[...](")]),
    # a '\\' right after '.': a member written with an escape (r.\\u0067et is r.get) is never matched by name
    ("r.\\u0067et('result')\nr.\\x72()", [(1, ".\\u0067et"), (2, ".\\")]),
    # push only on dump.js's own `rows`, forEach only on event.addedRecipes; never chained after .get(...)
    ("rows.push(x)\nevent.addedRecipes.forEach(f)\nr.get('result').forEach(f)\nout.push(x)\na.rows.push(x)\n"
     "event.forEachRecipe({}, f).forEach(g)\nr.get('x').push(1)\nevent.addedRecipes.push(r)",
     [(3, ".forEach"), (4, ".push"), (5, ".rows"), (5, ".push"), (6, ".forEach"), (7, ".push"), (8, ".push")]),
    # JsonIO.write's first argument is the dump path, as a literal
    ("JsonIO.write('kubejs/exported/recipes.json', rows)\nJsonIO.write(\"kubejs/exported/recipes.json\", rows)\n"
     "JsonIO.write('kubejs/exported/other.json', rows)\nJsonIO.write(path, rows)\nx.write('kubejs/exported/recipes.json', rows)\n"
     "JsonIO.write('kubejs/exported/recipes.json' + s, rows)",
     [(3, ".write"), (4, ".write"), (5, ".write"), (6, ".write")]),
])
def test_dump_lint(src, hits):
    assert dump_lint(src) == hits


def test_dump_never_is_disjoint_from_dump_members():
    """Task 8c (8b follow-up F4): the recipe-editing names of the round-3 ban list, plus id, type, group, set, add and remove,
    can never be allowlisted for dump.js."""
    assert DUMP_NEVER & DUMP_MEMBERS == set()


def test_dump_never_names_each_member_once():
    """Round 2, minor 13: the set literal repeats no name (a repeat reads as a second, different ban)."""
    import ast
    with open(__file__, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    literal = next(node.value for node in ast.walk(tree) if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "DUMP_NEVER" for t in node.targets))
    names = [elt.value for elt in literal.elts]
    assert sorted({n for n in names if names.count(n) > 1}) == []
    assert {"id", "type", "group", "set", "add", "remove", "replaceInput", "setValue", "addProperty"} <= DUMP_NEVER


def test_every_recipe_output_is_readable(everything):
    """Task 8c (8b follow-up): every recipe the scripts make names its products in a form kjs.products reads, so one bad
    output fails here once, instead of once per pinned output in test_pinned_output_has_only_its_own_makers (which skips an
    unreadable row, since this test covers it). A stand-in ('<inert>' from Item.getItem or Ingredient.of(...).first,
    '<undefined>') in a shaped, shapeless or custom output is a maker no test could see."""
    bad = [(r.get("file"), r.get("id"), output_problem(r)) for r in all_rows(everything) if output_problem(r)]
    assert bad == []


def removal_key(row):
    """(form, value) for one recorded event.remove (a `filters` row): ('id', '<id>'), ('id-regex', '/source/flags'),
    ('output', '<item>', or its JSON for a stack) or ('filter', <its JSON>) for anything else. Unlike the runner's legacy
    `removed` string, no form can pass as another: { id: 'output:minecraft:flint_and_steel' } is an id removal, not the
    output removal its `removed` string reads as (round 4 R4). The form comes from the runner's `kind` (Task 8c), not from
    the recorded JSON, so { id: { RegExp: '/x/' } }, an object literal, is a filter and not a regex. A string id of 3 or more
    characters that starts with '/' is a regex, as KubeJS reads it (kubejs-neoforge-2101.7.2-build.377.jar, javap -c:
    RecipeFilter.of passes an `id` value to RegExpKJS.wrap, offsets 402-450, which for a CharSequence calls ofString, and
    ofString returns null, so an IDFilter, unless length >= 3 and charAt(0) == '/', offsets 0-31)."""
    filt, kind = row["filter"], row["kind"]
    if kind == "id-regex":
        return ("id-regex", filt["id"]["RegExp"])
    if kind == "id":
        v = filt["id"]
        return ("id-regex", v) if len(v) >= 3 and v.startswith("/") else ("id", v)
    if kind == "output":
        v = filt["output"]
        return ("output", v if isinstance(v, str) else json.dumps(v, sort_keys=True))
    assert kind == "filter", row
    return ("filter", json.dumps(filt, sort_keys=True))


def owned_key(removed):
    """removal_key for an owner list's entry, written in the legacy `removed` form. Owner lists are written by hand, so an
    'output:' prefix there always means an output removal; they hold no 'filter:' entries and no stack outputs."""
    assert not removed.startswith(("filter:", "output:{", "output:[")), removed
    if removed.startswith("output:"):
        return ("output", removed.removeprefix("output:"))
    if len(removed) >= 3 and removed.startswith("/"):   # RegExpKJS.ofString's test (removal_key)
        return ("id-regex", removed)
    return ("id", removed)


def test_every_removal_is_an_owner_tests_removal(everything):
    """Round 3 V4, round 4 R4: the pack's removals, from every file and handler, are exactly PACK_REMOVALS, counted with
    multiplicity and compared by form and value (removal_key). A removal outside the owner tests' lists
    (event.remove({ mod: 'ae2' }) in tier2.js, { output: 'mekanism:steel_ingot' } in tier1.js, any removal in dump.js), a
    second copy of a listed one, or a listed output removal written as an id ({ id: 'output:<item>' }), fails, with the file
    that made it."""
    want = Counter(owned_key(x) for owned in PACK_REMOVALS.values() for x in owned)
    got = Counter(removal_key(row) for row in everything["filters"])
    by_file = {}
    for row in everything["filters"]:
        by_file.setdefault(removal_key(row), []).append(row["file"])
    extra = {f"{k[0]} {k[1]}": by_file[k] for k in sorted(got - want)}
    missing = sorted(f"{k[0]} {k[1]}" for k in want - got)
    assert (extra, missing) == ({}, []), (
        "extra: removal -> the files that made it; missing: listed in PACK_REMOVALS but not made (or listed by two owner "
        "lists: each removal belongs to exactly one). A new task that removes recipes adds its owner test's removal list to "
        "PACK_REMOVALS in tools/tests/test_recipe_scripts.py; EARLY_TIER_REMOVALS covers v0.1-v0.2 only.")


@pytest.mark.parametrize("filt,kind,key", [
    ({"id": "mekanism:digital_miner"}, "id", ("id", "mekanism:digital_miner")),
    ({"id": "output:minecraft:flint_and_steel"}, "id", ("id", "output:minecraft:flint_and_steel")),
    ({"output": "minecraft:flint_and_steel"}, "output", ("output", "minecraft:flint_and_steel")),
    ({"id": {"RegExp": "/^a:.*$/"}}, "id-regex", ("id-regex", "/^a:.*$/")),
    ({"output": {"id": "ae2:drive", "count": 1}}, "output", ("output", '{"count": 1, "id": "ae2:drive"}')),
    ({"mod": "ae2"}, "filter", ("filter", '{"mod": "ae2"}')),
    ({"id": "a:b", "output": "c:d"}, "filter", ("filter", '{"id": "a:b", "output": "c:d"}')),
    # Task 8c (8b follow-up): a string id of 3 or more chars that starts with '/' is a regex (RegExpKJS.ofString), and an
    # object literal shaped like the runner's RegExp record is not one: the runner's `kind` says what the filter was
    ({"id": "/^a:.*$/"}, "id", ("id-regex", "/^a:.*$/")),
    ({"id": "//"}, "id", ("id", "//")),
    ({"id": {"RegExp": "/^a:.*$/"}}, "filter", ("filter", '{"id": {"RegExp": "/^a:.*$/"}}')),
])
def test_removal_key_tells_the_forms_apart(filt, kind, key):
    assert removal_key({"filter": filt, "kind": kind}) == key


def test_the_runner_records_each_removals_kind(tmp_path, monkeypatch):
    """A real RegExp, a string id, an output and an object literal that only looks like the runner's RegExp record."""
    root = tmp_path / "server_scripts"
    (root / "lib").mkdir(parents=True)
    (root / "r.js").write_text("ServerEvents.recipes(event => {\n  event.remove({ id: /^a:.*$/ })\n  event.remove({ id: '/^b:.*$/' })\n"
                               "  event.remove({ id: { RegExp: '/^c:.*$/' } })\n  event.remove({ output: 'd:e' })\n"
                               "  event.remove({ mod: 'f' })\n})\n", encoding="utf-8")
    monkeypatch.setenv(SCRIPTS_ENV, str(root))
    with pytest.warns(UserWarning):
        out = run(all_scripts=True)
    assert [(r["kind"], removal_key(r)) for r in out["filters"]] == [
        ("id-regex", ("id-regex", "/^a:.*$/")), ("id", ("id-regex", "/^b:.*$/")),
        ("filter", ("filter", '{"id": {"RegExp": "/^c:.*$/"}}')), ("output", ("output", "d:e")),
        ("filter", ("filter", '{"mod": "f"}'))]


@pytest.mark.parametrize("removed,key", [
    ("mekanism:digital_miner", ("id", "mekanism:digital_miner")),
    ("output:minecraft:flint_and_steel", ("output", "minecraft:flint_and_steel")),
    ("/^deeperdarker:.*gloomslate_.*_ore$/", ("id-regex", "/^deeperdarker:.*gloomslate_.*_ore$/")),
])
def test_owned_key_reads_an_owner_lists_entry(removed, key):
    assert owned_key(removed) == key


def test_sole_makers_agree_across_files():
    """Two files that pin the same output name the same makers for it."""
    assert {o: by for o, by in SOLE_MAKERS.items() if len({json.dumps(ids) for ids in by.values()}) > 1} == {}


@pytest.mark.parametrize("output", sorted(SOLE_MAKERS))
def test_pinned_output_has_only_its_own_makers(everything, output):
    """Unreadable rows are left to test_every_recipe_output_is_readable (one failure, not one per output here)."""
    want = next(iter(SOLE_MAKERS[output].values()))
    got = [r["id"] for r in all_rows(everything) if output_problem(r) is None and output in products(r)]
    assert sorted(got, key=json.dumps) == sorted(want), f"{output} is made by {got}; {sorted(SOLE_MAKERS[output])} pin {want}"


def test_no_two_recipes_share_an_id(everything):
    ids = Counter(json.dumps(r["id"]) for r in all_rows(everything) if r["id"] is not None)
    assert sorted(i for i, n in ids.items() if n > 1) == []
