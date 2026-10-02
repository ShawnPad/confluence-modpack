"""Self-tests of the shared runner (tools/tests/run_server_scripts.js) and of kjs.py's readers (v0.3 Task 8b review).

Each runner test writes a scratch server_scripts directory (a lib/ directory plus the scripts under test), points
CONFLUENCE_SCRIPTS_ROOT at it and runs the runner through kjs.run, which warns that it read another root (expected here).
The behaviour pinned is the runner header's, each part read from kubejs-neoforge-2101.7.2-build.377.jar with javap:
  - ScriptFile.skipLoading returns the first reason that applies, so a file already skipped (ignored, client only, pack mode)
    never reaches the mod check: the runner reports its `requires: <mod>` line only on a file it loads;
  - an item string (Item.of, and so gate.shaped's output, and a shaped or shapeless recipe's raw string output) is read as
    ItemWrapper.wrapResult and read() read it: a count prefix, the id, a components patch, with Java's trim, whitespace,
    digits and Mth.ceil (each compared with the JDK or the jar, Task 8b round 3). A raw output KubeJS cannot read is an
    error the handler survives (RecipeTypeFunction.call catches it); Item.of's stops the handler;
  - a callback passed to an unmodelled recipes-event member runs once with a recording recipe probe, and a call chained on a
    recorded call's result is recorded too.
"""
import json

import pytest

import kjs
from kjs import SCRIPTS_ENV, json_item_id, products, run


def scripts(tmp_path, monkeypatch, files):
    root = tmp_path / "server_scripts"
    (root / "lib").mkdir(parents=True)
    for rel, text in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    monkeypatch.setenv(SCRIPTS_ENV, str(root))
    with pytest.warns(UserWarning, match="read server scripts from"):
        return run(all_scripts=True)


# ---- per-file properties: `requires` on a skipped file (review minor 1)

def test_a_skipped_file_gets_no_requires_error(tmp_path, monkeypatch):
    out = scripts(tmp_path, monkeypatch, {
        "a_ignored.js": "// ignored: true\n// requires: somemod\nthrow new Error('a ran')\n",
        "b_client.js": "// requires: client\n// requires: somemod\nthrow new Error('b ran')\n",
        "c_packmode.js": "// packmode: no_such_mode\n// requires: somemod\nthrow new Error('c ran')\n",
        "d_loaded.js": "// requires: somemod\n",
    })
    prefix = kjs.SCRIPTS_PREFIX
    assert out["skipped"] == [{"file": prefix + "a_ignored.js", "reason": "Ignored"},
                              {"file": prefix + "b_client.js", "reason": "Client only"},
                              {"file": prefix + "c_packmode.js", "reason": "Pack mode mismatch"}]
    assert out["loaded"] == [prefix + "d_loaded.js"]
    assert out["errors"] == [prefix + "d_loaded.js load: requires somemod, and the mod list is not modelled "
                                      "(run_server_scripts.js header)"]


# ---- item strings (review I2; round 3 V1, V2, M-a, M-b, M-c): ItemWrapper.wrapResult, parseString and read

AIR = {"id": "minecraft:air", "count": 0}
# (the arguments as JS source, the stack recorded, or the start of the error). A case with one argument also runs as a raw
# output, event.shaped(<it>, ...), which KubeJS reads the same way (ItemWrapper.wrap). JS's \u{...} escapes put each
# non-ASCII character into the script without putting it in this file.
ITEM_STRINGS = [
    ("'ae2:drive'", {"id": "ae2:drive", "count": 1}),
    ("'2x ae2:drive'", {"id": "ae2:drive", "count": 2}),
    ("'10x ae2:drive'", {"id": "ae2:drive", "count": 10}),
    ("'  4x  ae2:drive  '", {"id": "ae2:drive", "count": 4}),
    # wrapResult's prefix needs the first ' ' at index >= 2 with the first 'x' just before it; otherwise read() takes the count
    # and the final kjs$withCount(1) resets it to 1.
    ("'2 x ae2:drive'", {"id": "ae2:drive", "count": 1}),
    ("'3xae2:drive'", {"id": "ae2:drive", "count": 1}),
    # the prefix takes the first count; read() reads and drops the second
    ("'2x 2x ae2:drive'", {"id": "ae2:drive", "count": 2}),
    ("'2x 3xae2:drive'", {"id": "ae2:drive", "count": 2}),
    ("'+2x ae2:drive'", {"id": "ae2:drive", "count": 2}),
    ("'-2x ae2:drive'", AIR),
    ("'ae2:terminal[minecraft:rarity=\"epic\"]'", {"id": "ae2:terminal", "count": 1, "components": '[minecraft:rarity="epic"]'}),
    ("'2x ae2:terminal[minecraft:rarity=\"epic\"]'",
     {"id": "ae2:terminal", "count": 2, "components": '[minecraft:rarity="epic"]'}),
    ("'ae2:drive{foo:1b}'", {"id": "ae2:drive", "count": 1, "components": "{foo:1b}"}),
    ("'ae2:drive trailing words'", {"id": "ae2:drive", "count": 1}),
    ("'stick'", {"id": "minecraft:stick", "count": 1}),
    ("':ae2drive'", {"id": "minecraft:ae2drive", "count": 1}),   # ResourceLocation.read: an empty namespace is minecraft
    ("'-'", AIR),
    ("'air'", AIR),
    ("'0x ae2:drive'", AIR),
    # String.trim strips every char <= U+0020, U+0001 included; read() skips Character.isWhitespace, U+2000 and U+2028
    # included, but not the no-break spaces U+00A0 and U+2007
    ("'\\u0001ae2:drive'", {"id": "ae2:drive", "count": 1}),
    ("'\\u{2000}ae2:drive'", {"id": "ae2:drive", "count": 1}),
    ("'\\u{3000}ae2:drive'", {"id": "ae2:drive", "count": 1}),
    ("'2x\\u{2028}ae2:drive'", {"id": "ae2:drive", "count": 1}),
    ("'\\u{a0}ae2:drive'", "Error: item string '" + chr(0xa0) + "ae2:drive': Item with ID minecraft: does not exist!"),
    ("'\\u{2007}ae2:drive'", "Error: item string '" + chr(0x2007) + "ae2:drive': Item with ID minecraft: does not exist!"),
    # Integer.parseInt reads any Unicode decimal digit: fullwidth and Arabic-Indic three
    ("'\\u{ff13}x ae2:drive'", {"id": "ae2:drive", "count": 3}),
    ("'\\u{663}x ae2:drive'", {"id": "ae2:drive", "count": 3}),
    ("'2147483647xae2:drive'", {"id": "ae2:drive", "count": 1}),
    ("'2x ae2:drive', 3", {"id": "ae2:drive", "count": 3}),
    ("'ae2:terminal[minecraft:rarity=\"epic\"]', 5",
     {"id": "ae2:terminal", "count": 5, "components": '[minecraft:rarity="epic"]'}),
    ("'ae2:drive', 0", AIR),
    ("'2.5x ae2:drive'", "Error: item string '2.5x ae2:drive': NumberFormatException"),
    ("'99999999999x ae2:drive'", "Error: item string '99999999999x ae2:drive': NumberFormatException"),
    ("'2 ae2:drive'", "Error: item string '2 ae2:drive': CommandSyntaxException: Expected 'x'"),
    ("'0 x ae2:drive'", "Error: item string '0 x ae2:drive': Item count smaller than 1 is not allowed!"),
    # Mth.ceil wraps above 2^31 - 1 to -2^31, which fails the >= 1 check
    ("'2147483648xae2:drive'", "Error: item string '2147483648xae2:drive': Item count smaller than 1 is not allowed!"),
    ("'2147483647.5xae2:drive'", "Error: item string '2147483647.5xae2:drive': Item count smaller than 1 is not allowed!"),
    ("'a:b:c'", "Error: item string 'a:b:c': invalid resource location 'a:b:c'"),
    # an empty path: ItemWrapper.findItem finds no item ("Item with ID <id> does not exist!")
    ("'#c:ingots/iron'", "Error: item string '#c:ingots/iron': Item with ID minecraft: does not exist!"),
    ("'AE2:Drive'", "Error: item string 'AE2:Drive': Item with ID minecraft: does not exist!"),
    ("'ae2:'", "Error: item string 'ae2:': Item with ID ae2: does not exist!"),
    # round 4 R2: an argument that is neither an item string nor a stack the runner made. KubeJS wraps an ItemLike (an Item,
    # an Ingredient's .first) into a real stack, which is not modelled, so Item.of throws rather than record '<inert>'.
    ("Item.getItem('ae2:drive'), 1", 'Error: Item.of("<inert>", 1): the argument is not an item string or a stack'),
    ("Ingredient.of('ae2:controller').first, 1", 'Error: Item.of("<inert>", 1): the argument is not an item string'),
    ("Ingredient.of('allthemodium:unobtainium_crystal').first, 2", 'Error: Item.of("<inert>", 2): the argument is not'),
    ("Item.getItem('ae2:drive')", 'Error: Item.of("<inert>"): the argument is not an item string or a stack'),
    ("undefined, 2", 'Error: Item.of("<undefined>", 2): the argument is not an item string or a stack'),
    ("Item.of('ae2:drive'), 3", {"id": "ae2:drive", "count": 3}),   # a stack the runner made: kjs$withCount
]
RAW = [i for i, (args, _) in enumerate(ITEM_STRINGS) if args.endswith("'")]   # the one-argument cases


@pytest.fixture(scope="module")
def item_strings(tmp_path_factory):
    """One handler per case through Item.of (id t:<i>, handler i), then one per one-argument case as a raw shaped output
    (id raw:<i>), each raw call followed by a plain recipe (id after:<i>) that shows the handler went on."""
    root = tmp_path_factory.mktemp("items") / "server_scripts"
    (root / "lib").mkdir(parents=True)
    handlers = [f"ServerEvents.recipes(event => {{ event.shaped(Item.of({args}), ['A'], {{ A: 'minecraft:stick' }}).id('t:{i}') }})\n"
                for i, (args, _) in enumerate(ITEM_STRINGS)]
    handlers += [f"ServerEvents.recipes(event => {{ event.shaped({ITEM_STRINGS[i][0]}, ['A'], {{ A: 'minecraft:stick' }}).id('raw:{i}'); "
                 f"event.shapeless('minecraft:stick', ['minecraft:dirt']).id('after:{i}') }})\n" for i in RAW]
    (root / "items.js").write_text("".join(handlers), encoding="utf-8")
    mp = pytest.MonkeyPatch()
    mp.setenv(SCRIPTS_ENV, str(root))
    try:
        with pytest.warns(UserWarning):
            return run(all_scripts=True)
    finally:
        mp.undo()


def handler_errors(recorded, h):
    return [e.split(" recipes handler ")[1].split(": ", 1)[1] for e in recorded["errors"] if f" recipes handler {h}: " in e]


@pytest.mark.parametrize("i", range(len(ITEM_STRINGS)), ids=[a for a, _ in ITEM_STRINGS])
def test_item_string(item_strings, i):
    """Item.of(<args>): the stack, or an error that stops the handler (no row)."""
    args, want = ITEM_STRINGS[i]
    rows = [r for r in item_strings["recipes"] if r["id"] == f"t:{i}"]
    errors = handler_errors(item_strings, i)
    if isinstance(want, dict):
        assert (errors, [(r["output"], r["outputStack"]) for r in rows]) == ([], [(want, None)])
    else:
        assert rows == [] and len(errors) == 1 and errors[0].startswith(want), errors


@pytest.mark.parametrize("i", RAW, ids=[ITEM_STRINGS[i][0] for i in RAW])
def test_raw_string_output(item_strings, i):
    """event.shaped('<string>', ...) (round 3 V1): the raw string under `output`, the stack KubeJS reads from it under
    `outputStack`; or an 'event.shaped output' error, no row, and the handler goes on (RecipeTypeFunction.call catches it)."""
    args, want = ITEM_STRINGS[i]
    h = len(ITEM_STRINGS) + RAW.index(i)
    rows = [r for r in item_strings["recipes"] if r["id"] == f"raw:{i}"]
    after = [r["id"] for r in item_strings["recipes"] if r["handler"] == h and r["id"] == f"after:{i}"]
    errors = handler_errors(item_strings, h)
    assert after == [f"after:{i}"], errors
    if isinstance(want, dict):
        assert errors == [] and len(rows) == 1 and rows[0]["outputStack"] == want, (errors, rows)
        assert isinstance(rows[0]["output"], str)
        assert products(rows[0]) == [want["id"]]
    else:
        assert rows == [] and len(errors) == 1 and errors[0].startswith("event.shaped output: " + want), errors


@pytest.mark.parametrize("s,want", [
    ("ae2:drive", "ae2:drive"), ("2x ae2:drive", "ae2:drive"), ("2 x ae2:drive", "ae2:drive"), ("3xae2:drive", "ae2:drive"),
    ("1.5x ae2:drive", "ae2:drive"), ('ae2:terminal[minecraft:rarity="epic"]', "ae2:terminal"),
    ("ae2:drive{foo:1b}", "ae2:drive"), ("  4x  ae2:drive  junk", "ae2:drive"), ("stick", "minecraft:stick"),
    ("-", "-"), ("", ""), ("<inert>", "<inert>"),
])
def test_json_item_id_reads_a_json_string_generously(s, want):
    assert json_item_id(s) == want


def test_raw_stand_in_output_fails_in_products(tmp_path, monkeypatch):
    """Round 4 R2: event.shaped(Item.getItem(id), ...) is recorded as given ('<inert>'), and products() names it."""
    out = scripts(tmp_path, monkeypatch, {"a.js": (
        "ServerEvents.recipes(event => { event.shaped(Item.getItem('ae2:drive'), ['A'], { A: 'minecraft:stick' }).id('t:a') })\n")})
    row = next(r for r in out["recipes"] if r["id"] == "t:a")
    assert (out["errors"], row["output"], row["outputStack"]) == ([], "<inert>", None)
    with pytest.raises(AssertionError, match="is not an item stack with a resource-location id. '<inert>' is a stand-in"):
        products(row)


@pytest.mark.parametrize("output,stack", [
    ("ae2:drive", None),                         # a string output with no outputStack
    ("<inert>", None), ("<undefined>", None),     # a stand-in or a missing value, recorded as given
    ({"id": "<inert>", "count": 1}, None),        # what Item.of(<stand-in>, 1) recorded before round 4
    ({"id": "#c:ingots/iron", "count": 1}, None), ({"count": 1}, None), ([], None),
    ("2x ae2:drive", {"id": "<inert>", "count": 2}),
])
def test_products_rejects_an_output_with_no_item_id(output, stack):
    """Round 4 R2 (and the review's M1: an undefined output once failed as 'a string output with no outputStack')."""
    with pytest.raises(AssertionError, match="is not an item stack with a resource-location id"):
        products({"kind": "shaped", "id": "t:c", "output": output, "outputStack": stack, "file": "f.js", "handler": 0})


def test_products_reads_every_output_form():
    """A shaped row's string output is read through the runner's outputStack, never the raw string (round 3 V1: '2x 2x
    ae2:drive' is ae2:drive). A custom row taken straight from a run's `customs` (no `kind`) is read through its `json`, not
    as recipe JSON with no result (review minor 6). A shaped row whose output names no item fails (the test above)."""
    shaped = {"kind": "shaped", "id": "t:a", "output": "2x 2x ae2:drive", "outputStack": {"id": "ae2:drive", "count": 2}}
    stack = {"kind": "shapeless", "id": "t:s", "output": {"id": "ae2:drive", "count": 1}, "outputStack": None}
    custom = {"id": "t:b", "json": {"type": "x:y", "result": {"count": 1, "id": "ae2:drive"}}, "file": "f", "handler": 0,
              "chain": []}
    raw = {"type": "x:y", "results": [{"id": "ae2:drive"}, {"item": "ae2:controller"}], "main_output": "3x ae2:charger"}
    assert products(shaped) == ["ae2:drive"]
    assert products(stack) == ["ae2:drive"]
    assert products(custom) == ["ae2:drive"]
    assert products({"kind": "custom", **custom}) == ["ae2:drive"]
    assert products(raw) == ["ae2:drive", "ae2:controller", "ae2:charger"]


# ---- callbacks (review minor 3; round 3 N1: calls chained on a call's result)

def test_a_callback_runs_once_with_a_recording_probe(tmp_path, monkeypatch):
    out = scripts(tmp_path, monkeypatch, {"walk.js": (
        "ServerEvents.recipes(event => {\n"
        "  event.forEachRecipe({}, r => { r.get('result'); r.json.add('x', 1); r.id = 'y'; String(r) })\n"
        "  event.addedRecipes.forEach(r => { r.replaceInput('a:b', 'c:d') })\n"
        "  event.forEachRecipe({}, r => { throw new Error('boom') })\n"
        "  event.foo.bar = 2\n"
        "  event.forEachRecipe({}, r => { r.get('result').setCount(64); r.serializeChanges().json.count = 3 })\n"
        "  event.findRecipes({}).forEach(r => r.remove())\n"
        "})\n")})
    rows = [(c["call"], c["op"], c["member"], c["args"]) for c in out["callbacks"]]
    assert rows == [("forEachRecipe", "call", "get", ["result"]), ("forEachRecipe", "call", "json.add", ["x", 1]),
                    ("forEachRecipe", "set", "id", ["y"]), ("addedRecipes.forEach", "call", "replaceInput", ["a:b", "c:d"]),
                    ("forEachRecipe", "call", "get", ["result"]), ("forEachRecipe", "call", "get().setCount", [64]),
                    ("forEachRecipe", "call", "serializeChanges", []),
                    ("forEachRecipe", "set", "serializeChanges().json.count", [3]),
                    ("findRecipes().forEach", "call", "remove", [])]
    assert [(o["member"], o.get("op")) for o in out["other"]] == [
        ("forEachRecipe", None), ("addedRecipes.forEach", None), ("forEachRecipe", None), ("foo.bar", "set"),
        ("forEachRecipe", None), ("findRecipes", None), ("findRecipes().forEach", None)]
    assert len(out["errors"]) == 1 and out["errors"][0].startswith(
        kjs.SCRIPTS_PREFIX + "walk.js recipes handler 0: forEachRecipe callback: Error: boom"), out["errors"]
    assert json.dumps(out)   # everything recorded serialised
