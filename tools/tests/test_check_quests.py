from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_quests import tree_nodes, quests_in_lang, forbidden_in_table

TREE = """
### Tier 1 — Nether
- [D1.1] Nether key — vanilla
  - gate: [T0.2] Mekanism osmium ingot (recipe); [M0.1] Ars source gem (recipe)
- [X1.1] Netherite — vanilla
  - gate: [D1.1] the Nether (dimension)
### Tier 2 — Twilight Forest
- [D2.1] Twilight key
  - gate: [X1.1] netherite ingot (recipe)
"""

def test_tree_nodes_and_gates():
    nodes = tree_nodes(TREE, tiers={1})
    assert set(nodes) == {"D1.1", "X1.1"}
    assert nodes["D1.1"] == ["T0.2", "M0.1"]

def test_lang_nodes():
    lang = '{\n\tquest.ABCDEF0123456789.quest_desc: ["[D1.1]", "text"]\n}'
    assert quests_in_lang(lang) == {"D1.1": "ABCDEF0123456789"}

def test_forbidden():
    table = 'item: { count: 1, id: "kubejs:twilight_key" }\nitem: { count: 1, id: "minecraft:bread" }'
    assert forbidden_in_table(table) == ["kubejs:twilight_key"]

def test_gate_refs_ignore_citations():
    # combined-tree.md L175: a cross-pack citation "(recipe, ozone [T4.2] pattern)" is not a hard gate
    tree = "### Tier 1 — Nether\n- [T1.1] x\n  - gate: [M0.1] Ars source gem (recipe) `[design]`; [T0.2] osmium ingot (recipe, ozone [T4.2] pattern)\n"
    assert tree_nodes(tree, tiers={1})["T1.1"] == ["M0.1", "T0.2"]


def test_lang_nodes_multiline_list():
    # research/phase6-tooling-worldgen-quests.md §4.7 L509-512: FTB Quests writes a multi-entry quest_desc
    # one entry per line ("quest_desc: [" newline, tab-indented entries, "]"), not the scaffolder's inline form.
    lang = '{\n\tquest.ABCDEF0123456789.quest_desc: [\n\t\t"[D1.1]"\n\t\t"text"\n\t]\n}'
    assert quests_in_lang(lang) == {"D1.1": "ABCDEF0123456789"}
