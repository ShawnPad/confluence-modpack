"""Shared helpers for the tests that run the pack's KubeJS server scripts or read mod jars (v0.3 Task 8b).

Import: `from kjs import run, ...` in a test module under tools/tests. It needs no conftest.py and no __init__.py. pytest's
default import mode, prepend, puts a test module's own directory (tools/tests, which has no __init__.py) at the front of
sys.path before it imports the module, so `kjs` resolves to this file. The corpus in test_pin_mutations.py runs pytest in a
subprocess with the same mode. Other tools/ modules are imported the older way, by putting tools/ on sys.path (see
test_check_tags.py); this file lives beside the tests because only tests use it.

What is here:
  run(*scripts, all_scripts=False)  runs tools/tests/run_server_scripts.js (the shared runner; its header is the stdout
      contract) and returns its JSON. By default it reads pack/kubejs/server_scripts. With CONFLUENCE_SCRIPTS_ROOT set it
      reads that directory instead (the mutation corpus does this with a mutated copy): the runner says so on stderr, and
      run() issues a warning, which pytest lists in its warnings summary, naming the directory.
  node_fixture                      a module-scoped fixture named `node`: `from kjs import node_fixture` in a test module
      provides it. It asserts node is on PATH and never skips; so does run().
  all_rows, products, one_maker     the recipes a run records, what each makes, and who makes an output.
  json_item_id                      the item id a string inside custom recipe JSON names, read generously
      (check_recipes.json_item_id). Not for a script's output string: the runner reads that as KubeJS does and records it as
      the row's outputStack.
  one                               the one recorded recipe with a given id, with nothing chained on it and no extra arguments.
  ingredient, grid, cell_diff, EMPTY  one strict reading of a recipe ingredient and of a shaped grid.
  pinned_jar, jar_json              the jar pins: the jar a test reads is exactly the one mods/<mod>.pw.toml ships.
      MODS, the booted server's mods directory, is pack/.run/server/mods, or $CONFLUENCE_MODS_DIR when that is set (the
      mutation corpus points it at a missing directory to list the tests that read a jar).

tools/tests/worldgen_harness.js (worldgen events) and the harnesses inside test_other_gate.py and test_other_gate_events.py
(native listeners) are separate and do not use this module: they model other events.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tools" / "tests" / "run_server_scripts.js"
SCRIPTS_ENV = "CONFLUENCE_SCRIPTS_ROOT"
DEFAULT_SCRIPTS = ROOT / "kubejs" / "server_scripts"
SCRIPTS_PREFIX = "kubejs/server_scripts/"  # how run()'s arguments and the runner's `file` fields name a script
MODS_ENV = "CONFLUENCE_MODS_DIR"
# the booted server's jars; $CONFLUENCE_MODS_DIR overrides it (relative to the working directory, as any path)
MODS = Path(os.environ[MODS_ENV]).resolve() if os.environ.get(MODS_ENV) else ROOT / ".run" / "server" / "mods"
PW_MODS = ROOT / "mods"                    # packwiz's mods/<mod>.pw.toml
EMPTY = None                               # a ' ' cell of a shaped pattern


def _root():
    override = os.environ.get(SCRIPTS_ENV)
    return Path(override).resolve() if override else DEFAULT_SCRIPTS


def scripts_root():
    """The server-scripts directory run() reads: $CONFLUENCE_SCRIPTS_ROOT if set, else pack/kubejs/server_scripts. When it is
    set, this warns (pytest lists the warning in its summary), so a run that read another root says so."""
    root = _root()
    if root != DEFAULT_SCRIPTS:
        warnings.warn(f"{SCRIPTS_ENV} is set: server scripts are read from {root}, not {DEFAULT_SCRIPTS}")
    return root


def node_path():
    node = shutil.which("node")
    assert node, "node is not on PATH; `node --version` must print a version (v22.3.0 was used when these tests were written)"
    return node


@pytest.fixture(scope="module", name="node")
def node_fixture():
    return node_path()


def run(*scripts, all_scripts=False):
    """The runner's JSON for every lib/*.js plus `scripts` (each written kubejs/server_scripts/<path>), or, with
    all_scripts=True, for every server script."""
    assert bool(scripts) != all_scripts, "run() takes script paths or all_scripts=True, not both and not neither"
    args = ["--all"] if all_scripts else list(scripts)
    env = dict(os.environ)
    if env.get(SCRIPTS_ENV):
        env[SCRIPTS_ENV] = str(_root())   # absolute, so the runner (cwd pack/) reads the directory this process means
    res = subprocess.run([node_path(), str(RUNNER), *args], cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, f"{RUNNER.name} {' '.join(args)} exited {res.returncode}:\n{res.stderr}"
    out = json.loads(res.stdout)
    # One warning per run that read another root, naming the directory the runner itself reports.
    if Path(out["scriptsRoot"]) != DEFAULT_SCRIPTS:
        warnings.warn(f"the runner read server scripts from {out['scriptsRoot']}, not {DEFAULT_SCRIPTS} ({SCRIPTS_ENV} is set)")
    return out


def all_rows(recorded):
    """Every recipe a run records: the shaped/shapeless rows, then the event.custom rows with kind 'custom'."""
    return recorded["recipes"] + [{"kind": "custom", **c} for c in recorded["customs"]]


# The keys of a custom recipe's JSON that name what it makes. `result`, `output` and `results` are the common ones; any other
# top-level key with "result" or "output" in its name counts too (Mekanism's main_output / secondary_output, IF's
# outputFluid), so a maker cannot hide behind a mod's own key name.
# One producer rule (Task 8c round 2, minor 7): a custom recipe's products are tools/check_recipes.py's, the rule the boot's
# sole-producer check reads the dump with. json_item_id is its string reader (an optional count, then the first run of
# resource-location characters): each mod's own codec reads its JSON, and none is modelled, so it only makes sure a maker is
# not missed. A script's shaped/shapeless output string is NOT read with it: the runner reads that as KubeJS does
# (ItemWrapper.wrap) and records the result as the row's outputStack, which products() uses.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_recipes  # noqa: E402

json_item_id = check_recipes.json_item_id


# A shaped or shapeless product's id: a resource location (namespace, ':', path), no '#'.
ITEM_ID = re.compile(r"[a-z0-9_.-]+:[a-z0-9_./-]+")

# A runner stand-in label ('<inert>', '<undefined>', '<function>', '<NaN>', '<recipe>', '<unserialisable: ...>'): a value the
# runner could not record as KubeJS would serialise it (see run_server_scripts.js, "Every recorded value").
STAND_IN = re.compile(r"<.*>", re.S)


def _stand_ins(v, path):
    """(path, label) for each stand-in string anywhere inside v."""
    if isinstance(v, str):
        if STAND_IN.fullmatch(v):
            yield path, v
    elif isinstance(v, dict):
        for k, x in v.items():
            yield from _stand_ins(x, f"{path}.{k}")
    elif isinstance(v, list):
        for i, x in enumerate(v):
            yield from _stand_ins(x, f"{path}[{i}]")


def products(r):
    """The ids a recorded recipe (or a raw recipe JSON) makes. A shaped or shapeless row: the stack the runner read from a
    string output (`outputStack`, as KubeJS reads it), else the output itself (an Item.of stack {id, count}), and its id
    must be a resource location: an output that is a stand-in ('<inert>', from an unmodelled global such as
    Ingredient.of), '<undefined>', a tag or anything else the runner could not read fails here (Task 8b round 4). A custom row
    (from all_rows, or straight from a run's `customs`) or raw JSON: check_recipes.made_by's items, then its chemicals and
    fluids, then '#<tag>' for each tag product, then the JSON of each product value of a shape it does not read (one producer
    rule, Task 8c round 2: the product keys and shapes are its module docstring's). A custom product holding a runner
    stand-in anywhere inside it fails (Task 8c, 8b follow-up F1): event.custom({ result: Ingredient.of(id).first }) is a real
    maker in game, as KubeJS serialises the object, but would read here as the id '<inert>', which no output matches."""
    if r.get("kind") in ("shaped", "shapeless"):
        out = r["output"]
        stack = r.get("outputStack") if isinstance(out, str) else out
        assert isinstance(stack, dict) and isinstance(stack.get("id"), str) and ITEM_ID.fullmatch(stack["id"]), (
            f"{r.get('file')} recipes handler {r.get('handler')}: event.{r['kind']}'s output {out!r} (read as "
            f"{r.get('outputStack')!r}) is not an item stack with a resource-location id. '<inert>' is a stand-in for an "
            f"unmodelled global (Ingredient.of(...).first, Fluid.of(...), ...) and '<undefined>' a missing value; pass an item "
            f"string or Item.of(<item string>[, count]), which the runner reads as KubeJS does")
        return [stack["id"]]
    # A recorded custom row carries its recipe under `json` (with `kind` from all_rows, or `file` straight from `customs`);
    # anything else is taken as the recipe JSON itself.
    j = r["json"] if "json" in r and ("kind" in r or "file" in r) else r
    if not isinstance(j, dict):
        return []
    for k, v in check_recipes.product_values(j):
        bad = list(_stand_ins(v, k))
        assert not bad, (
            f"{r.get('file')} recipes handler {r.get('handler')}: custom recipe {r.get('id')!r} has a runner stand-in "
            f"in its product, {', '.join(f'{p} = {x!r}' for p, x in bad)}. An unmodelled global (Ingredient.of(...)"
            f".first, Ingredient.of(...).first.id, ...) makes a real maker in game that no test can read; write the id as a "
            f"string")
    made = check_recipes.made_by(j)
    return (made.items + made.chemicals + ["#" + t for t, _ in made.tags]
            + [json.dumps(v, sort_keys=True) for _, v in made.unknown])


def output_problem(r):
    """None when products(r) reads r's outputs, else its failure message (an unreadable output: a stand-in, a tag, ...)."""
    try:
        products(r)
    except AssertionError as e:
        return str(e)
    return None


def one_maker(recorded, output):
    """The ids (None for an id-less recipe) of every recorded recipe that makes `output`. Fails on the first recipe whose
    output products() cannot read."""
    return [r["id"] for r in all_rows(recorded) if output in products(r)]


def one(recorded, rid):
    """The one recipe (all_rows) recorded with id `rid`, with nothing chained on it (.keepIngredient and the like) and no extra
    arguments. Two rows with the same id fail here, where a dict keyed by id would keep only the last."""
    hits = [r for r in all_rows(recorded) if r["id"] == rid]
    assert len(hits) == 1, f"{rid}: {len(hits)} recipes recorded; script errors: {recorded['errors']}"
    r = hits[0]
    assert r["chain"] == [] and r.get("extra", []) == [], (rid, r["chain"], r.get("extra"))
    return r


RESOURCE = re.compile(r"#?[a-z0-9_.-]+:[a-z0-9_./-]+")


def ingredient(v, json_only=False):
    """One ingredient as '#tag' or an item id. Recipe JSON must be exactly {"item": id} or {"tag": id}. A script may also write
    the string itself ('#tag' or an id), unless json_only (for jar and datapack JSON, which never holds a bare string). An
    empty, '<undefined>' or '<inert>' string, or anything else, fails: it would load as an empty ingredient or not at all."""
    if isinstance(v, dict):
        assert set(v) in ({"item"}, {"tag"}) and all(isinstance(x, str) for x in v.values()), v
        return "#" + v["tag"] if "tag" in v else v["item"]
    assert not json_only, f"a bare string where recipe JSON needs {{item}} or {{tag}}: {v!r}"
    assert isinstance(v, str) and RESOURCE.fullmatch(v), f"not '#tag' or an item id: {v!r}"
    return v


def grid(pattern, key, shape=(3, 3), json_only=False):
    """{(row, col): cell} of a shaped pattern, each cell an ingredient(v, json_only) or EMPTY. It asserts what vanilla's
    ShapedRecipePattern accepts (1–3 rows of one width, 1–3 columns; ' ' is not a key; every pattern symbol is in the key and
    every key symbol is used: "Key defines symbols that aren't used in pattern", ShapedRecipePattern.unpack,
    server-1.21.1-20240808.144430-srg.jar) and, unless shape is None, that the pattern is exactly shape (rows, columns).
    Pass json_only=True for a jar's or datapack's recipe JSON."""
    assert 1 <= len(pattern) <= 3 and len({len(row) for row in pattern}) == 1 and 1 <= len(pattern[0]) <= 3, pattern
    if shape is not None:
        assert (len(pattern), len(pattern[0])) == tuple(shape), (pattern, shape)
    assert " " not in key, key
    assert set("".join(pattern)) - {" "} == set(key), (pattern, sorted(key))
    return {(r, c): EMPTY if ch == " " else ingredient(key[ch], json_only) for r, row in enumerate(pattern)
            for c, ch in enumerate(row)}


def cell_diff(a, b):
    """{cell: (a's, b's)} for every cell where two grids of the same shape differ."""
    assert set(a) == set(b), (sorted(a), sorted(b))
    return {cell: (a[cell], b[cell]) for cell in sorted(a) if a[cell] != b[cell]}


# The end of pinned_jar's skip reason; test_pin_mutations.py finds every jar-reading test by it.
JAR_SKIP = "does not exist (no server has been booted from this clone)"


def pinned_jar(prefix, expected_name, pw_toml):
    """The path of the jar a test reads, after three checks. mods/<pw_toml>'s `filename` must be expected_name, so a packwiz
    update fails here before any boot. Then the test skips only when MODS (.run/server/mods, or $CONFLUENCE_MODS_DIR) does
    not exist (no server has been booted from this clone), and fails unless the glob <prefix>*.jar there matches exactly
    expected_name. Write the prefix with its trailing hyphen ('Mekanism-'), so an add-on jar with a longer name does not
    match. With $CONFLUENCE_MODS_DIR set this warns, as scripts_root() does for its own override."""
    toml = PW_MODS / pw_toml
    assert toml.is_file(), f"{toml} does not exist; the jar pin for {expected_name} names the wrong .pw.toml"
    m = re.search(r'^filename\s*=\s*"([^"]*)"\s*$', toml.read_text(encoding="utf-8"), re.M)
    assert m and m.group(1) == expected_name, (
        f"{toml.relative_to(ROOT)} ships {m.group(1) if m else '(no filename line)'}, but this test was written against "
        f"{expected_name}; re-read the jar and update the test's tables by hand")
    if os.environ.get(MODS_ENV):
        warnings.warn(f"{MODS_ENV} is set: mod jars are read from {MODS}")
    if not MODS.is_dir():
        pytest.skip(f"{MODS} {JAR_SKIP}")
    found = sorted(p.name for p in MODS.glob(prefix + "*.jar"))
    assert found == [expected_name], f"this test was written against {expected_name}; {MODS} holds {found} for {prefix}*.jar"
    return MODS / expected_name


def jar_json(jar, entry, what):
    """The parsed JSON of `entry` in an open zipfile.ZipFile; fails with "id moved" when the jar has no such entry."""
    try:
        return json.loads(jar.read(entry))
    except KeyError:
        pytest.fail(f"id moved: {Path(jar.filename).name} has no {entry}, so {what}")
