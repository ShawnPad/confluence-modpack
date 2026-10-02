"""The runtime recipe bodies equal the spec (v0.3 Task 8c; replaces the one-off body checks of plan Tasks 4-8, Step 6/7).

For every recipe the four migrated recipe-script tests pin through their spec tables, compare the body the server actually
loaded, the `json` column of .run/server/kubejs/exported/recipes.json (dump.js), with the expected body, exactly. The tables
are imported, never copied:
  - test_mek_tier5: REWRITES + DEFAULTS (the six D113 rewrites and the Digital Miner, as view() tuples), T51_VIEW, KEY_VIEW,
    and CUSTOM_BODIES (M5.1, X5.1);
  - test_tier6_space_recipes: SHAPED (the five Space machines) and CUSTOM (Etrium ingot and plate, Astral Focus);
  - test_ae2_recipes: EXPECTED (the ten AE2 recipes) and CONVERSIONS (AE2's own pattern-provider conversions, kept);
  - test_bypass_v03: UNOB_BODIES (the X2.2 combining recipes).
Not covered: the three v0.2 QIO recipes (test_mek_tier5 pins only their elite-circuit count, not a whole body).

A custom body (event.custom, or a datapack file) must equal its table entry after the KubeJS bookkeeping keys are stripped
(_kubejs_changed_marker, written by KubeRecipe.serializeChanges for a new or changed recipe; see dump.js). A crafting-grid
row is compared as the recipe the server builds from it, which takes three facts:
  1. A gate.shaped row loads as type `kubejs:shaped`, not `minecraft:crafting_shaped` (spec §14, second row;
     research/phase7-v0.3-test-log.md, section "Mekanism tier 5"); the tables already say so (test_mek_tier5.LOADED_AS).
  2. An omitted `category` is MISC: kubejs-neoforge-2101.7.2-build.377.jar ShapedKubeJSRecipe$SerializerKJS reads
     CraftingBookCategory.CODEC.fieldOf("category").orElse(CraftingBookCategory.MISC) (javap -c, offsets 21-34), and the
     shaped schema (data/minecraft/kubejs/recipe_schema/shaped.json) declares `category` optional "misc", excluded, so the
     dump body leaves it out. Every pinned grid recipe is MISC (the jar defaults and the tables' mek_data rows say "misc").
  3. The pattern is trimmed by vanilla's shrink: the same serializer reads the pattern with ShapedRecipePattern.MAP_CODEC
     (offset 45), whose unpack calls ShapedRecipePattern.shrink(List) first (server-1.21.1-20240808.144430-srg.jar, javap -c,
     unpack offset 4; shrink trims all-space leading and trailing rows and columns). So a body's pattern and the table's
     are both shrunk before they are compared, for kubejs:shaped and minecraft:crafting_shaped (the two types whose codec was
     read); any other type is compared as written.
A grid body may hold no other key (no `kubejs:mirror`, no `show_notification`, no `group`): each would change the recipe.

The dump must be this tree's: when any file under kubejs/, mods/ or config/ that a boot reads has an mtime newer than the
dump's, the test fails with "stale dump: boot first". Those files are git's list (`git ls-files --cached --others
--exclude-standard -- kubejs/ mods/ config/`: tracked, plus untracked files that are not ignored; every file under those
directories when the tree is not a git checkout), less kubejs/exported/ (what a boot writes, not what it reads). Only mtimes count: a commit leaves them alone, so committing
the files a boot already read keeps the dump fresh, while a checkout or an edit moves them and makes it stale. A file
deleted since the boot is not seen. The test skips only when the dump file does not exist (no server has been booted from
this clone). $CONFLUENCE_RECIPE_DUMP points it at another dump (a doctored copy, for a red run).
"""
import json
import os
import subprocess
from pathlib import Path

import pytest

import test_ae2_recipes as ae2
import test_bypass_v03 as bypass
import test_mek_tier5 as mek
import test_tier6_space_recipes as space
from kjs import ROOT, ingredient

DUMP_ENV = "CONFLUENCE_RECIPE_DUMP"
DUMP = Path(os.environ[DUMP_ENV]).resolve() if os.environ.get(DUMP_ENV) else (
    ROOT / ".run" / "server" / "kubejs" / "exported" / "recipes.json")
KUBEJS = ROOT / "kubejs"

BOOKKEEPING = "_kubejs"                                   # key prefix KubeJS adds to a body it serialised
GRID_KEYS = {"type", "category", "pattern", "key", "result"}
SHRUNK_TYPES = {"kubejs:shaped", "minecraft:crafting_shaped"}   # fact 3: codecs read, both through ShapedRecipePattern


def shrink(pattern):
    """Vanilla ShapedRecipePattern.shrink: drop the all-space rows above and below, and the all-space columns left and
    right, of the pattern."""
    rows = [i for i, row in enumerate(pattern) if row.strip(" ")]
    if not rows:
        return []
    cols = [c for row in pattern for c, ch in enumerate(row) if ch != " "]
    lo, hi = min(cols), max(cols) + 1
    return [row[lo:hi] for row in pattern[rows[0]:rows[-1] + 1]]


def strip(body):
    return {k: v for k, v in body.items() if not k.startswith(BOOKKEEPING)}


def grid_view(body):
    """(type, category, pattern, key, (result id, count)) of a crafting-grid body, as the server builds the recipe (facts 1-3
    in the docstring). Keys are read strictly ({item} or {tag} only) and a result may hold only id and count."""
    body = strip(body)
    assert set(body) <= GRID_KEYS and {"type", "pattern", "key", "result"} <= set(body), sorted(body)
    typ = body["type"]
    pattern = shrink(body["pattern"]) if typ in SHRUNK_TYPES else body["pattern"]
    result = body["result"]
    assert set(result) <= {"id", "count"}, result
    return (typ, body.get("category", "misc"), pattern, {k: ingredient(v, json_only=True) for k, v in body["key"].items()},
            (result["id"], result.get("count", 1)))


def spec_view(typ, pattern, key, result):
    return (typ, "misc", shrink(pattern) if typ in SHRUNK_TYPES else pattern, key, tuple(result))


def _grid_specs():
    specs = {}
    for rid, (name, letter, circuit) in mek.REWRITES.items():
        typ, pattern, key, result = mek.DEFAULTS[name]
        specs[rid] = spec_view(mek.LOADED_AS.get(typ, typ), pattern, {**key, letter: circuit}, result)
    specs[mek.T51] = spec_view(*mek.T51_VIEW)
    specs[mek.KEY] = spec_view(*mek.KEY_VIEW)
    for rid, (output, pattern, keys) in space.SHAPED.items():
        specs[rid] = spec_view("kubejs:shaped", pattern, keys, (output, 1))
    for rid, (output, pattern, keys) in ae2.EXPECTED.items():
        specs[rid] = spec_view("kubejs:shaped", pattern, keys, (output, 1))
    return specs


GRID = _grid_specs()
CUSTOM = {**mek.CUSTOM_BODIES, **space.CUSTOM, **ae2.CONVERSIONS, **bypass.UNOB_BODIES}
assert not set(GRID) & set(CUSTOM), sorted(set(GRID) & set(CUSTOM))


EXPORTED = "kubejs/exported/"   # what a boot writes under kubejs/ (in the run directory), never an input
# What a boot reads from the pack: the scripts and data (kubejs/), the mod pins packwiz installs from (mods/*.pw.toml) and the
# shipped configs (config/). Round 2, minor 12 added mods/ and config/.
BOOT_INPUTS = ("kubejs/", "mods/", "config/")


def kubejs_files(root=ROOT):
    """The paths (relative to `root`, posix) of the files under BOOT_INPUTS that a boot reads: git's tracked and untracked but
    not ignored files there, or, when `root` is not in a git checkout, every file there; never kubejs/exported/."""
    res = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", *BOOT_INPUTS], cwd=root,
                         capture_output=True)
    if res.returncode == 0:
        rels = [r for r in res.stdout.decode("utf-8").split("\0") if r]
    else:
        rels = [f.relative_to(root).as_posix() for d in BOOT_INPUTS for f in (root / d).rglob("*") if f.is_file()]
    return sorted(r for r in rels if not r.startswith(EXPORTED))


def newest_kubejs_file(root=ROOT):
    """(mtime, path) of the newest of kubejs_files(root), or (0.0, None); a listed file missing on disk is skipped."""
    newest = (0.0, None)
    for rel in kubejs_files(root):
        try:
            mtime = (root / rel).stat().st_mtime
        except FileNotFoundError:
            continue
        if mtime > newest[0]:
            newest = (mtime, rel)
    return newest


def staleness(dump_mtime, newest_file):
    """None when the dump is at least as new as the newest kubejs file, else the 'stale dump: boot first' message."""
    file_time, rel = newest_file
    if dump_mtime < file_time:
        return f"stale dump: boot first ({DUMP} is older than {rel})"
    return None


@pytest.fixture(scope="module")
def dump():
    if not DUMP.is_file():
        pytest.skip(f"{DUMP} does not exist (no server has been booted from this clone)")
    stale = staleness(DUMP.stat().st_mtime, newest_kubejs_file())
    if stale:
        pytest.fail(stale)
    rows = json.loads(DUMP.read_text())
    by = {}
    for r in rows:
        assert r["id"] not in by, f"two dump rows with id {r['id']}"
        by[r["id"]] = r
    return by


def body_of(dump, rid):
    assert rid in dump, f"{rid} is not in the dump"
    assert dump[rid].get("json"), f"{rid} has no `json` body in the dump"
    return json.loads(dump[rid]["json"])


@pytest.mark.parametrize("rid", sorted(GRID))
def test_grid_recipe_body_matches_spec(dump, rid):
    assert grid_view(body_of(dump, rid)) == GRID[rid], dump[rid]["json"]


@pytest.mark.parametrize("rid", sorted(CUSTOM))
def test_custom_recipe_body_matches_spec(dump, rid):
    assert strip(body_of(dump, rid)) == CUSTOM[rid], dump[rid]["json"]


# ---- self-tests of the model (no dump needed) ----

def test_shrink_is_vanillas():
    assert shrink(["   ", " A ", "   "]) == ["A"]
    assert shrink([" A ", " B ", "CDC"]) == [" A ", " B ", "CDC"]
    assert shrink(["ABA", "A  ", "ABA"]) == ["ABA", "A  ", "ABA"]
    assert shrink(["A  ", "B  "]) == ["A", "B"]
    assert shrink(["   "]) == []


def test_grid_view_models_the_three_facts():
    body = {"type": "kubejs:shaped", "pattern": ["   ", " A ", "   "], "key": {"A": {"tag": "c:x"}},
            "result": {"id": "m:o", "count": 2}, "_kubejs_changed_marker": {"line": 6}}
    assert grid_view(body) == ("kubejs:shaped", "misc", ["A"], {"A": "#c:x"}, ("m:o", 2))
    assert grid_view(body) == spec_view("kubejs:shaped", ["A"], {"A": "#c:x"}, ("m:o", 2))
    # The category is read when written; any key outside the grid keys fails.
    assert grid_view({**body, "category": "building"})[1] == "building"
    for extra in ({"kubejs:mirror": False}, {"show_notification": False}, {"group": "g"}):
        with pytest.raises(AssertionError):
            grid_view({**body, **extra})
    # A non-shrunk type is compared as written.
    mek_data = {**body, "type": "mekanism:mek_data"}
    assert grid_view(mek_data)[2] == ["   ", " A ", "   "]


def _tree(tmp_path, files):
    """A tmp pack root (no git repo, so kubejs_files walks it) holding `files`, {path under the root: mtime}, and a dump at
    mtime 1000."""
    for rel, mtime in files.items():
        f = tmp_path / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("x")
        os.utime(f, (mtime, mtime))
    dump_file = tmp_path / "recipes.json"
    dump_file.write_text("[]")
    os.utime(dump_file, (1000, 1000))
    return staleness(dump_file.stat().st_mtime, newest_kubejs_file(tmp_path))


def test_a_kubejs_file_newer_than_the_dump_makes_it_stale(tmp_path):
    stale = _tree(tmp_path, {"kubejs/server_scripts/a.js": 2000, "kubejs/data/b.json": 500})
    assert stale is not None and stale.startswith("stale dump: boot first") and "kubejs/server_scripts/a.js" in stale


def test_kubejs_files_older_than_the_dump_leave_it_fresh(tmp_path):
    assert _tree(tmp_path, {"kubejs/server_scripts/a.js": 900, "kubejs/data/b.json": 1000}) is None


def test_a_newer_file_under_kubejs_exported_is_ignored(tmp_path):
    """kubejs/exported/ is what a boot writes (the dump itself), not what it reads."""
    assert _tree(tmp_path, {"kubejs/server_scripts/a.js": 500, "kubejs/exported/recipes.json": 3000,
                            "kubejs/exported/tags.json": 3000}) is None


@pytest.mark.parametrize("rel", ["mods/ae2.pw.toml", "config/ftbquests/quests/chapters/aether.snbt"])
def test_a_newer_mods_or_config_file_makes_it_stale(tmp_path, rel):
    """Round 2, minor 12: a boot reads mods/ (the .pw.toml pins, so the jars) and config/ too, not only kubejs/."""
    stale = _tree(tmp_path, {"kubejs/server_scripts/a.js": 500, rel: 2000})
    assert stale is not None and stale.endswith(f"is older than {rel})")


def test_boot_inputs_include_the_repos_mods_and_config_files():
    files = kubejs_files(ROOT)
    assert "mods/allthemodium.pw.toml" in files and "config/ftbquests/quests/chapter_groups.snbt" in files


def test_kubejs_files_lists_the_repos_tracked_and_unignored_files():
    """In the pack repo the list is git's (tracked, plus untracked files that are not ignored), never kubejs/exported/."""
    files = kubejs_files(ROOT)
    assert "kubejs/server_scripts/dump.js" in files and "kubejs/server_scripts/lib/ids.js" in files
    assert not [f for f in files if f.startswith("kubejs/exported/")]
    assert all((ROOT / f).is_relative_to(KUBEJS) or f.startswith(("mods/", "config/")) for f in files)
