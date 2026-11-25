"""tools/route_sources.py (v1.0 plan Task 14; spec §6.1 route_sources.yaml sections, A18)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from route_sources import ROUTE_SOURCES, SECTIONS, Rule, RouteSourceError, load, needs_groups, parse  # noqa: E402

GOOD = """# comment
base:
  - {"id": "minecraft:stick", "cite": "vanilla"}
  - {"tag": "c:ingots/iron", "cite": "vanilla"}

dimensions:
  # the Overworld is open from the start
  - {"id": "minecraft:overworld", "tier": 0, "from": null, "enter": [[]], "cite": "tree tier overview"}
  - {"id": "minecraft:the_nether", "tier": 1, "from": "minecraft:overworld", "enter": [["minecraft:flint_and_steel"]], "cite": "t"}
biome_dimensions:
  - {"biome": "#c:is_overworld", "dimension": "minecraft:overworld", "cite": "t"}
sources:
  - {"key": "blaze", "item": "minecraft:blaze_rod", "dimension": "minecraft:the_nether", "kind": "mob", "needs": [], "cite": "t"}
  - {"key": "q:D0.1", "item": null, "dimension": "minecraft:overworld", "kind": "quest", "needs": [], "node": "D0.1", "cite": "t"}
machines:
  - {"type": "minecraft:crafting_shaped", "needs": [["minecraft:crafting_table", "minecraft:crafter"]], "cite": "t"}
ignored_types:
  - {"type": "chipped:workbench", "cite": "t"}
accepted:
  - {"node": ["D1.2", "D1.3"], "code": "SKIPPABLE", "route": ["blaze"], "decision": "D127"}
soft_refs:
  - {"node": "D1.1", "ref": "D0.1", "cite": "t"}
"""


def test_good_text_loads_every_section():
    got = parse(GOOD)
    assert set(got) == set(SECTIONS)
    assert got["base"][1] == {"tag": "c:ingots/iron", "cite": "vanilla"}
    assert got["sources"][1]["node"] == "D0.1" and got["sources"][1]["item"] is None
    assert got["accepted"][0]["node"] == ["D1.2", "D1.3"]


def test_the_shipped_file_loads():
    got = load(ROUTE_SOURCES)
    assert [d["id"] for d in got["dimensions"] if d["from"] is None] == ["minecraft:overworld"]


@pytest.mark.parametrize("old, new, words", [
    ("base:", "bases:", "unknown section"),
    ('  - {"id": "minecraft:stick", "cite": "vanilla"}', '  - {"id": "minecraft:stick"}', "missing cite"),
    ('  - {"id": "minecraft:stick", "cite": "vanilla"}', '  - {"id": "minecraft:stick", "cite": "v", "x": 1}', "unknown key x"),
    ('  - {"id": "minecraft:stick", "cite": "vanilla"}', '  - {"id": "minecraft:stick", "cite": "vanilla"', "not JSON"),
    ('  - {"id": "minecraft:stick", "cite": "vanilla"}', '  - {"id": "minecraft:stick", "tag": "c:x", "cite": "v"}', "id or tag"),
    ('"key": "q:D0.1"', '"key": "blaze"', "duplicate key blaze"),
    ('"kind": "mob"', '"kind": "boat"', "kind boat"),
    ('"code": "SKIPPABLE"', '"code": "MAYBE"', "code MAYBE"),
    ('"decision": "D127"', '"decision": "127"', "decision"),
    ('"tier": 1,', '"tier": "1",', "tier"),
    ('"enter": [["minecraft:flint_and_steel"]]', '"enter": ["minecraft:flint_and_steel"]', "enter"),
    ('"needs": [["minecraft:crafting_table", "minecraft:crafter"]]', '"needs": [[]]', "needs"),
    (', "node": "D0.1"', "", "item null needs node"),
    ('  - {"type": "chipped:workbench", "cite": "t"}', '  - {"type": "minecraft:crafting_shaped", "cite": "t"}',
     "both machine and ignored"),
    ("# comment", "comment", "not a header, entry or comment"),
])
def test_each_error_names_its_line(old, new, words):
    assert GOOD.count(old) == 1, old
    with pytest.raises(RouteSourceError) as e:
        parse(GOOD.replace(old, new))
    assert "line " in str(e.value) and words in str(e.value), str(e.value)


def test_needs_groups():
    assert needs_groups(["a:b", ["c:d", "e:f"]]) == (frozenset({"a:b"}), frozenset({"c:d", "e:f"}))
    assert Rule("u", ("x:y",), ()).outputs == ("x:y",)


# Hardening after the Task 14 review: id-like fields are type-checked, blanks and duplicate JSON keys are rejected, and
# parse() cross-checks dimensions and the quest kind. Each still names its line.
@pytest.mark.parametrize("old, new, words", [
    ('"type": "minecraft:crafting_shaped"', '"type": ["minecraft:crafting_shaped"]', "type must be"),
    ('"type": "chipped:workbench"', '"type": 5', "type must be"),
    ('"id": "minecraft:the_nether"', '"id": {"a": 1}', "id must be"),
    ('"from": "minecraft:overworld"', '"from": 3', "from must be"),
    ('"biome": "#c:is_overworld"', '"biome": null', "biome must be"),
    ('"dimension": "minecraft:overworld", "cite"', '"dimension": ["minecraft:overworld"], "cite"', "dimension must be"),
    ('"ref": "D0.1"', '"ref": 1', "ref must be"),
    ('{"node": "D1.1"', '{"node": ["D1.1"]', "node must be"),
    ('"decision": "D127"}', '"decision": "D127", "note": 5}', "note must be"),
    ('"item": "minecraft:blaze_rod"', '"item": 7', "item must be"),
    ('"key": "blaze"', '"key": "  "', "key"),
    ('{"id": "minecraft:stick", "cite": "vanilla"}', '{"id": "minecraft:stick", "cite": " "}', "missing cite"),
    ('{"id": "minecraft:stick", "cite": "vanilla"}', '{"id": " ", "cite": "vanilla"}', "id or tag"),
    ('"key": "blaze",', '"key": "blaze", "key": "b2",', "duplicate JSON key key"),
    ('"tier": 1,', '"tier": NaN,', "not JSON"),
    ('"tier": 1,', '"tier": Infinity,', "not JSON"),
    ('"tier": 1,', '"tier": 8,', "tier"),
    ('"tier": 1,', '"tier": -1,', "tier"),
    ('"tier": 1,', '"tier": true,', "tier"),
    ('"kind": "mob", "needs": []', '"kind": "mob", "needs": [true]', "needs"),
    ('  - {"type": "chipped:workbench", "cite": "t"}', '  - ["chipped:workbench"]', "not JSON object"),
    ("# comment", '  - {"id": "minecraft:stick", "cite": "t"}', "not a header, entry or comment"),
    ('"from": "minecraft:overworld"', '"from": null', "second root dimension"),
    ('"from": null, "enter": [[]]', '"from": "minecraft:the_nether", "enter": [[]]', "no root dimension"),
    ('"from": "minecraft:overworld"', '"from": "x:nowhere"', "unknown dimension x:nowhere"),
    ('"dimension": "minecraft:the_nether", "kind"', '"dimension": "x:end", "kind"', "unknown dimension x:end"),
    ('"item": null, "dimension": "minecraft:overworld", "kind": "quest"',
     '"item": "x:y", "dimension": "minecraft:overworld", "kind": "quest"', "kind quest needs item null"),
    ('"key": "blaze", "item": "minecraft:blaze_rod"', '"key": "blaze", "item": null, "node": "D1.2"',
     "item null needs kind quest"),
])
def test_hardened_errors_name_their_line(old, new, words):
    assert GOOD.count(old) == 1, old
    with pytest.raises(RouteSourceError) as e:
        parse(GOOD.replace(old, new))
    assert "line " in str(e.value) and words in str(e.value), str(e.value)


def test_machine_and_ignored_names_the_ignored_line():
    new = '  - {"type": "minecraft:crafting_shaped", "cite": "t"}'
    text = GOOD.replace('  - {"type": "chipped:workbench", "cite": "t"}', new)
    n = text.splitlines().index(new) + 1
    with pytest.raises(RouteSourceError, match=rf"line {n}: minecraft:crafting_shaped is both machine and ignored"):
        parse(text)


def test_an_empty_accepted_route_still_loads():
    """QUEST_ORDER entries carry route: [] (task 17's ACCEPTED_UNUSED flags an empty route on SKIPPABLE/EARLY)."""
    got = parse(GOOD.replace('"route": ["blaze"]', '"route": []'))
    assert got["accepted"][0]["route"] == []


def test_c6_biome_dimensions_name_a_listed_dimension():
    """Task 18 review C6: biome_dimensions.dimension is cross-checked like dimensions.from and sources.dimension."""
    text = GOOD.replace('"dimension": "minecraft:overworld", "cite": "t"}', '"dimension": "x:nowhere", "cite": "t"}')
    assert text != GOOD
    with pytest.raises(RouteSourceError, match=r"line 11: unknown dimension x:nowhere"):
        parse(text)
