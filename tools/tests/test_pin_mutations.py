"""A lasting mutation corpus for the recipe, tag and Other-gate pins (v0.3 Task 8b).

Each review of Tasks 4–9 proved a gap by mutating a server script and watching which test failed. CASES keeps those
mutations, so a later refactor of a test cannot quietly stop catching one. A case is (name, file, edit, expected, jar):
  file      a server-script path under kubejs/server_scripts/, or a tuple of them (one edit each)
  edit      text appended to the file (a whole handler: ServerEvents.recipes(event => { ... }) or
            ServerEvents.tags('block', event => { ... }), so the edit stays valid as the file grows), or an exact
            (old, new) replacement, where `old` must occur exactly once
  expected  the tests that must fail, as '<module>.py::<test>' (every parameter of it counts) or '<module>.py::<test>[<id>]'
  jar       (optional) more tests that must fail, each one that reads a mod jar through kjs.pinned_jar. Such a test skips in a
            clone with no .run/server/mods (no server booted there), so it can fail only when BOOTED; `expected` must name
            none of them and `jar` only them (test_jar_reading_tests_are_listed_under_jar finds the set by running the
            cases' modules once with kjs.MODS pointing at a missing directory and listing what skips for it).
A stale (old, new) edit, whose `old` no longer occurs exactly once after a script changed, fails that case alone, with a
"stale edit" message; the other cases still run.

How a case runs. The case copies kubejs/server_scripts to a temporary directory, applies the edit there (never to the pack),
and runs pytest on the expected tests' modules in a subprocess with CONFLUENCE_SCRIPTS_ROOT pointing at the copy. kjs.run and
kjs.scripts_root read that root and warn that they did (the runner also says so on stderr). The case passes when every
expected test failed, each failure is an assertion (AssertionError or pytest.fail, not a crash such as a TypeError), and
pytest exited 1. SANITY is the same run over every target module with no edit: it must exit 0, which shows the
copy-and-run path itself is green. The child runs with --color=no and its summary is read with any ANSI codes stripped, so
PY_COLORS=1 or FORCE_COLOR=1 in this run cannot hide a failure from the summary match.

What the corpus proves is narrower than "the whole suite catches it": a case runs only its expected tests' modules, against
a mutated copy of kubejs/server_scripts only (kubejs/data, kubejs/startup_scripts and the rest are the pack's own). A test
that reads ROOT/kubejs directly rather than through kjs (test_other_gate.py does) sees the pack, not the mutant.

Why a subprocess rather than calling the test functions in-process with a `recorded` built from the copy: the subprocess
runs the real modules with their real fixtures, parametrisation and jar pins, so a test cannot pass here and fail in the
suite (or the reverse), and nothing in this file has to know how any test builds its data. The cases run in parallel
threads, one pytest process each, inside the module fixture `results`.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from kjs import DEFAULT_SCRIPTS, JAR_SKIP, MODS, MODS_ENV, ROOT, SCRIPTS_ENV

Case = namedtuple("Case", "name file edit expected jar", defaults=(frozenset(),))
BOOTED = MODS.is_dir()   # kjs.pinned_jar skips every jar-reading test without it

T1, T2, T3, T5, T6 = "tiers/tier1.js", "tiers/tier2.js", "tiers/tier3.js", "tiers/tier5.js", "tiers/tier6.js"
BYPASS, EVENTS, DUMP = "bypass.js", "events.js", "dump.js"
MEK, SPACE, AE2 = "test_mek_tier5.py", "test_tier6_space_recipes.py", "test_ae2_recipes.py"
BYP, PACKWIDE, GATE = "test_bypass_v03.py", "test_recipe_scripts.py", "test_other_gate_events.py"
BYPASS_END = "  IDS.tierOres.smeltingRecipes.forEach(id => gate.remove(event, { id: id }))\n})\n"


def recipes(*lines):
    return "\nServerEvents.recipes(event => {\n" + "".join(f"  {line}\n" for line in lines) + "})\n"


def block_tags(*lines):
    return "\nServerEvents.tags('block', event => {\n" + "".join(f"  {line}\n" for line in lines) + "})\n"


def in_bypass_handler(line):
    """An (old, new) edit that adds `line` as the last statement of bypass.js's own handler, so the handler count stays 1."""
    return (BYPASS_END, BYPASS_END[:-3] + "\n  " + line + "\n})\n")


CASES = [
    # ---- Task 4 (Mekanism, test_mek_tier5.py)
    Case("t4 remove a MOVED_TO_TIER5 id", T5, recipes("event.remove({ id: 'mekanism:meka_tool' })"),
         {f"{MEK}::test_defaults_removed_by_id"}),
    Case("t4 remove {output: ultimate circuit}", T5, recipes("event.remove({ output: 'mekanism:ultimate_control_circuit' })"),
         {f"{MEK}::test_defaults_removed_by_id"}),
    Case("t4 remove {input: '#c:circuits/ultimate'}", T5, recipes("event.remove({ input: '#c:circuits/ultimate' })"),
         {f"{MEK}::test_defaults_removed_by_id"}),
    Case("t4 remove {output: Item.of(circuit)}", T5, recipes("event.remove({ output: Item.of('mekanism:ultimate_control_circuit') })"),
         {f"{MEK}::test_defaults_removed_by_id"}),
    Case("t4 tier3 recipe asks for an ultimate circuit", T3,
         recipes("gate.shaped(event, 'confluence:tier3/ultimate_stick', 'minecraft:stick', ['A'], { A: '#c:circuits/ultimate' })"),
         {f"{MEK}::test_tier3_asks_for_no_ultimate_circuit"}),
    Case("t4 regex id removal", T5, recipes("event.remove({ id: /mekanism:meka_tool/ })"),
         {f"{MEK}::test_defaults_removed_by_id"}),
    # ---- Task 5 (the Key and the alloys)
    Case("t5 second handler re-makes the key (same id)", T5,
         recipes("gate.shaped(event, 'confluence:tier5/other_key', 'kubejs:other_key', ['A'], { A: 'minecraft:stick' })"),
         {f"{MEK}::test_d51_key_to_the_other", f"{MEK}::test_task5_block_is_add_only"}),
    Case("t5 second handler makes an alloy (new id)", T5,
         recipes("gate.custom(event, 'confluence:tier5/cheap_alloy', { type: 'x:y', result: { count: 1, "
                 "id: 'allthemodium:vibranium_allthemodium_alloy_ingot' } })"),
         {f"{MEK}::test_x51_vibranium_allthemodium_alloy",
          f"{PACKWIDE}::test_pinned_output_has_only_its_own_makers[allthemodium:vibranium_allthemodium_alloy_ingot]"}),
    # ---- Task 6 (Space, test_tier6_space_recipes.py)
    Case("t6 remove {mod: 'ad_astra'}", T6, recipes("event.remove({ mod: 'ad_astra' })"),
         {f"{SPACE}::test_space_removals_are_the_five_defaults_only"}),
    Case("t6 remove {type: 'ad_astra:alloying'}", T6, recipes("event.remove({ type: 'ad_astra:alloying' })"),
         {f"{SPACE}::test_space_removals_are_the_five_defaults_only"}),
    Case("t6 remove {input: '#ad_astra:steel_plates'}", T6, recipes("event.remove({ input: '#ad_astra:steel_plates' })"),
         {f"{SPACE}::test_space_removals_are_the_five_defaults_only"}),
    Case("t6 regex removal in tier6.js", T6, recipes("event.remove({ id: /ad_astra:.*_rocket/ })"),
         {f"{SPACE}::test_space_removals_are_the_five_defaults_only"}),
    Case("t6 second shaped maker of a machine", T6,
         recipes("gate.shaped(event, 'confluence:tier6/space_suit_twin', 'ad_astra:space_suit', ['A'], { A: 'minecraft:stick' })"),
         {f"{SPACE}::test_space_shaped_rows", f"{PACKWIDE}::test_pinned_output_has_only_its_own_makers[ad_astra:space_suit]"}),
    Case("t6 second shapeless maker of a machine", T6,
         recipes("gate.shapeless(event, 'confluence:tier6/oxygen_loader_twin', 'ad_astra:oxygen_loader', ['minecraft:stick'])"),
         {f"{SPACE}::test_space_shaped_rows"}),
    Case("t6 custom maker of a machine", T6,
         recipes("event.custom({ type: 'x:y', result: { count: 1, id: 'ad_astra:fuel_refinery' } }).id('confluence:tier6/fuel_twin')"),
         {f"{SPACE}::test_space_shaped_rows"}),
    Case("t6 Item.of(spaceSuit, 2)", T6,
         ("gate.replaceShaped(event, 'confluence:tier6/space_suit', IDS.adastra.spaceSuit,",
          "gate.replaceShaped(event, 'confluence:tier6/space_suit', Item.of(IDS.adastra.spaceSuit, 2),"),
         {f"{SPACE}::test_space_shaped_rows", f"{SPACE}::test_space_removals_are_the_five_defaults_only"},
         {f"{SPACE}::test_space_machine_is_the_jar_default_plus_spec_slots[confluence:tier6/space_suit]"}),
    # ---- Task 7 (AE2, test_ae2_recipes.py): the seven removal shapes, then the one-maker cases
    *[Case(f"t7 remove {label}", T6, recipes(f"gate.remove(event, {filt})"), {f"{AE2}::test_ae2_defaults_removed_by_id_only"})
      for label, filt in [
          ("{mod: 'ae2'}", "{ mod: 'ae2' }"),
          ("regex /pattern_providers_interface/", "{ id: /pattern_providers_interface/ }"),
          ("{id: 'ae2:network/wireless_access_point'}", "{ id: 'ae2:network/wireless_access_point' }"),
          ("{input: 'ae2:crafting_unit'}", "{ input: 'ae2:crafting_unit' }"),
          ("{type: 'minecraft:crafting_shapeless'}", "{ type: 'minecraft:crafting_shapeless' }"),
          ("{output: '#ae2:illuminated_panel'}", "{ output: '#ae2:illuminated_panel' }"),
          ("bare string _alt id", "'ae2:network/blocks/pattern_providers_interface_alt'"),
      ]],
    Case("t7 second shaped inscriber", T5,
         recipes("gate.shaped(event, 'confluence:tier5/inscriber_twin', IDS.ae2.inscriber, ['A'], { A: IDS.vanilla.piston })"),
         {f"{AE2}::test_ae2_recipe_matches_spec[confluence:tier5/inscriber]"}),
    Case("t7 custom maker of ae2:controller", T5,
         recipes("gate.custom(event, 'confluence:tier5/controller_twin', { type: 'x:y', result: { count: 1, id: IDS.ae2.controller } })"),
         {f"{AE2}::test_ae2_recipe_matches_spec[confluence:tier5/controller]"}),
    Case("t7 results maker of ae2:drive", T5,
         recipes("gate.custom(event, 'confluence:tier5/drive_twin', { type: 'x:y', results: [{ count: 1, id: IDS.ae2.drive }] })"),
         {f"{AE2}::test_ae2_recipe_matches_spec[confluence:tier5/drive]"}),
    # ---- Task 8 (bypass, test_bypass_v03.py)
    Case("t8 remove {mod: 'allthemodium'}", BYPASS, recipes("event.remove({ mod: 'allthemodium' })"),
         {f"{BYP}::test_bypass_removes_exactly_these"}),
    Case("t8 remove {output: 'allthemodium:vibranium_ingot'}", BYPASS,
         recipes("event.remove({ output: 'allthemodium:vibranium_ingot' })"), {f"{BYP}::test_bypass_removes_exactly_these"}),
    Case("t8 remove {type: 'minecraft:smelting'}", BYPASS, recipes("event.remove({ type: 'minecraft:smelting' })"),
         {f"{BYP}::test_bypass_removes_exactly_these"}),
    Case("t8 dust-smelting regex removal", BYPASS, recipes("event.remove({ id: /allthemodium:.*_ingot_from_d.st_smelting/ })"),
         {f"{BYP}::test_bypass_removes_exactly_these"}),
    Case("t8 gate.custom with a 4th (output) argument", BYPASS,
         ("    output: { count: 5, id: IDS.allthemodium.unobtainiumCrystal },\n  })\n",
          "    output: { count: 5, id: IDS.allthemodium.unobtainiumCrystal },\n  }, IDS.allthemodium.unobtainiumCrystal)\n"),
         {f"{BYP}::test_bypass_removes_exactly_these"}),
    Case("t8 cheap_crystal custom maker", BYPASS,
         recipes("gate.custom(event, 'confluence:bypass/cheap_crystal', { type: 'mekanism:crystallizing', input: { amount: 1, "
                 "chemical: 'allthemodium:clean_unobtainium' }, output: { count: 1, id: IDS.allthemodium.unobtainiumCrystal } })"),
         {f"{BYP}::test_bypass_adds_exactly_the_nine_crystal_recipes",
          f"{PACKWIDE}::test_pinned_output_has_only_its_own_makers[allthemodium:unobtainium_crystal]"}),
    Case("t8 dissolution remake of dirty_unobtainium", BYPASS,
         recipes("event.custom({ type: 'mekanism:dissolution', item_input: { count: 1, tag: 'c:ores/unobtainium' }, "
                 "chemical_input: { amount: 1, tag: 'mekanism:sulfuric_acid' }, output: { id: 'allthemodium:dirty_unobtainium', "
                 "amount: 1000 } }).id('allthemodium:processing/unobtainium/slurry/dirty/from_ore')"),
         {f"{BYP}::test_bypass_adds_exactly_the_nine_crystal_recipes"}),
    Case("t8 event.remove('minecraft:wither_immune', ore)", EVENTS,
         block_tags("event.remove('minecraft:wither_immune', 'allthemodium:unobtainium_ore')"),
         {f"{BYP}::test_tier_ores_immune_to_the_wither_and_four_cataclysm_bosses"}),
    Case("t8 removeAll on a deny tag", EVENTS, block_tags("event.removeAll('mekanism:incorrect_for_meka_tool')"),
         {f"{BYP}::test_nine_empty_deny_tags_get_atms_netherite_set"}),
    Case("t8 get('minecraft:wither_immune').removeAll()", EVENTS, block_tags("event.get('minecraft:wither_immune').removeAll()"),
         {f"{BYP}::test_tier_ores_immune_to_the_wither_and_four_cataclysm_bosses"}),
    Case("t8 event.add('c:needs_allthemodium_tool', ore)", EVENTS,
         block_tags("event.add('c:needs_allthemodium_tool', 'allthemodium:unobtainium_ore')"),
         {f"{BYP}::test_block_tag_edits_touch_only_the_fourteen_tags"}),
    Case("t8 event.remove('c:needs_vibranium_tool', ore)", EVENTS,
         block_tags("event.remove('c:needs_vibranium_tool', 'allthemodium:unobtainium_ore')"),
         {f"{BYP}::test_block_tag_edits_touch_only_the_fourteen_tags"}),
    Case("t8 load error appended to events.js", EVENTS, "\nconst BROKEN = IDS.nope.x\n",
         {f"{BYP}::test_block_tag_handler_registered_and_runs", f"{PACKWIDE}::test_every_server_script_loads_and_runs"}),
    # ---- New in Task 8b
    Case("8b second maker of a gated output in another file", "tiers/tier2.js",
         recipes("gate.shaped(event, 'confluence:tier2/cheap_controller', 'ae2:controller', ['A'], { A: 'minecraft:stick' })"),
         {f"{PACKWIDE}::test_pinned_output_has_only_its_own_makers[ae2:controller]"}),
    Case("8b id-less event.custom makes a gated output", BYPASS,
         in_bypass_handler("event.custom({ type: 'mekanism:crystallizing', input: { amount: 1, chemical: "
                           "'allthemodium:clean_unobtainium' }, output: { count: 1, id: IDS.allthemodium.unobtainiumCrystal } })"),
         {f"{BYP}::test_bypass_adds_exactly_the_nine_crystal_recipes",
          f"{PACKWIDE}::test_pinned_output_has_only_its_own_makers[allthemodium:unobtainium_crystal]"}),
    Case("8b id-less event.custom makes a Space machine", T6,
         recipes("event.custom({ type: 'x:y', result: { count: 1, id: 'ad_astra:fuel_refinery' } })"),
         {f"{SPACE}::test_space_shaped_rows", f"{PACKWIDE}::test_pinned_output_has_only_its_own_makers[ad_astra:fuel_refinery]"}),
    Case("8b shaped recipe in bypass.js makes an Unobtainium crystal", BYPASS,
         in_bypass_handler("gate.shaped(event, 'confluence:bypass/crystal_shaped', IDS.allthemodium.unobtainiumCrystal, ['A'], "
                           "{ A: 'minecraft:stick' })"),
         {f"{BYP}::test_bypass_adds_exactly_the_nine_crystal_recipes",
          f"{PACKWIDE}::test_pinned_output_has_only_its_own_makers[allthemodium:unobtainium_crystal]"}),
    Case("8b replaceInput call in bypass.js", BYPASS,
         in_bypass_handler("event.replaceInput({ id: 'allthemodium:allthemodium_ingot_from_dust_smelting' }, "
                           "'#c:dusts/allthemodium', 'minecraft:dirt')"),
         {f"{BYP}::test_bypass_loads_and_runs_cleanly", f"{BYP}::test_bypass_adds_exactly_the_nine_crystal_recipes",
          f"{PACKWIDE}::test_every_server_script_loads_and_runs"}),
    # ---- Task 8b review: an item string's count prefix or components patch (ItemWrapper.wrapResult / read), and a
    # dump.js callback that edits the recipes it walks
    Case("8b review '2x ae2:drive' as event.shaped's output", "tiers/tier2.js",
         recipes("event.shaped('2x ae2:drive', ['A'], { A: 'minecraft:stick' }).id('confluence:tier2/cheap_drive')"),
         {f"{PACKWIDE}::test_pinned_output_has_only_its_own_makers[ae2:drive]"}),
    Case("8b review '2x ae2:drive' through gate.shaped", "tiers/tier2.js",
         recipes("gate.shaped(event, 'confluence:tier2/cheap_drive', '2x ae2:drive', ['A'], { A: 'minecraft:stick' })"),
         {f"{PACKWIDE}::test_pinned_output_has_only_its_own_makers[ae2:drive]"}),
    Case("8b review 'ae2:terminal[...]' through gate.shaped", "tiers/tier1.js",
         recipes("gate.shaped(event, 'confluence:tier1/term2', 'ae2:terminal[minecraft:rarity=\"epic\"]', ['A'], "
                 "{ A: 'minecraft:stick' })"),
         {f"{PACKWIDE}::test_pinned_output_has_only_its_own_makers[ae2:terminal]"}),
    Case("8b review replaceInput inside dump.js's forEachRecipe callback", DUMP,
         ("  event.forEachRecipe({}, r => rows.push(row(r)))\n",
          "  event.forEachRecipe({}, r => { r.replaceInput('minecraft:stick', 'minecraft:dirt'); rows.push(row(r)) })\n"),
         {f"{PACKWIDE}::test_dump_callbacks_only_read_each_recipe"}),
    # ---- Task 8b round 3: a raw string output read as KubeJS reads it (V1, V2, M-c), removals outside the owner tests'
    # lists (V4), and edits dump.js could hide (N1 a chained call, N4 a branch the probe never takes, V4 a removal)
    Case("8b r3 '2x 2x ae2:drive' as event.shaped's raw output", T2,
         recipes("event.shaped('2x 2x ae2:drive', ['A'], { A: 'minecraft:stick' }).id('confluence:tier2/hidden_drive')"),
         {f"{PACKWIDE}::test_pinned_output_has_only_its_own_makers[ae2:drive]"}),
    Case("8b r3 '\\u0001ae2:drive' as event.shaped's raw output", T2,
         recipes("event.shaped('\\u0001ae2:drive', ['A'], { A: 'minecraft:stick' }).id('confluence:tier2/hidden_drive')"),
         {f"{PACKWIDE}::test_pinned_output_has_only_its_own_makers[ae2:drive]"}),
    Case("8b r3 '\\u{2000}ae2:drive' through gate.shaped", T2,
         recipes("gate.shaped(event, 'confluence:tier2/hidden_drive', '\\u{2000}ae2:drive', ['A'], { A: 'minecraft:stick' })"),
         {f"{PACKWIDE}::test_pinned_output_has_only_its_own_makers[ae2:drive]"}),
    Case("8b r3 '#c:ingots/iron' as a raw output (no item)", T2,
         recipes("event.shaped('#c:ingots/iron', ['A'], { A: 'minecraft:stick' }).id('confluence:tier2/tag_output')"),
         {f"{PACKWIDE}::test_every_server_script_loads_and_runs"}),
    Case("8b r3 remove {output: 'mekanism:steel_ingot'} in tier1.js", T1,
         recipes("event.remove({ output: 'mekanism:steel_ingot' })"),
         {f"{PACKWIDE}::test_every_removal_is_an_owner_tests_removal"}),
    Case("8b r3 remove {mod: 'ae2'} in tier2.js", T2, recipes("event.remove({ mod: 'ae2' })"),
         {f"{PACKWIDE}::test_every_removal_is_an_owner_tests_removal"}),
    Case("8b r3 a second copy of a pinned AE2 removal in tier2.js", T2,
         recipes("event.remove({ id: 'ae2:network/blocks/controller' })"),
         {f"{PACKWIDE}::test_every_removal_is_an_owner_tests_removal"}),
    Case("8b r3 event.remove inside dump.js's row(r)", DUMP,
         ("    let out = ''\n", "    let out = ''\n    event.remove({ id: r.getOrCreateId() })\n"),
         {f"{PACKWIDE}::test_dump_adds_removes_and_tags_nothing", f"{PACKWIDE}::test_every_removal_is_an_owner_tests_removal",
          f"{PACKWIDE}::test_dump_source_names_only_allowed_members"}),
    Case("8b r3 a call chained on r.get('result') in dump.js", DUMP,
         ("    let out = ''\n", "    let out = ''\n    r.get('result').setCount(64)\n"),
         {f"{PACKWIDE}::test_dump_callbacks_only_read_each_recipe"}),
    Case("8b r3 an edit behind a branch on the recipe's id in dump.js", DUMP,
         ("  event.forEachRecipe({}, r => rows.push(row(r)))\n",
          "  event.forEachRecipe({}, r => { if (String(r.getOrCreateId()).startsWith('ae2:')) "
          "r.replaceInput('ae2:fluix_crystal', 'minecraft:dirt'); rows.push(row(r)) })\n"),
         {f"{PACKWIDE}::test_dump_source_names_only_allowed_members"}),
    # ---- Task 8b round 4: Item.of of an unmodelled ItemLike (R2: a real maker in game, once a silent '<inert>' row), an id
    # removal that wrote the legacy string of an output removal (R4, W2), and a Rhino builder function in dump.js (R3)
    Case("8b r4 Item.of(Item.getItem('ae2:drive'), 1) as event.shaped's output", T2,
         recipes("event.shaped(Item.of(Item.getItem('ae2:drive'), 1), ['A'], { A: 'minecraft:stick' })"
                 ".id('confluence:tier2/hidden_drive')"),
         {f"{PACKWIDE}::test_every_server_script_loads_and_runs"}),
    Case("8b r4 Item.of(Ingredient.of('ae2:controller').first, 1) through gate.shaped", T2,
         recipes("gate.shaped(event, 'confluence:tier2/hidden_controller', Item.of(Ingredient.of('ae2:controller').first, 1), "
                 "['A'], { A: 'minecraft:stick' })"),
         {f"{PACKWIDE}::test_every_server_script_loads_and_runs"}),
    Case("8b r4 Item.of(Ingredient.of(unobtainium crystal).first, 2) as event.shapeless's output", T2,
         recipes("event.shapeless(Item.of(Ingredient.of('allthemodium:unobtainium_crystal').first, 2), ['minecraft:stick'])"),
         {f"{PACKWIDE}::test_every_server_script_loads_and_runs"}),
    Case("8b r4 Item.of(Item.getItem('ae2:drive')) with no count", T2,
         recipes("event.shaped(Item.of(Item.getItem('ae2:drive')), ['A'], { A: 'minecraft:stick' })"
                 ".id('confluence:tier2/hidden_drive')"),
         {f"{PACKWIDE}::test_every_server_script_loads_and_runs"}),
    # Task 8c: an unreadable output fails test_every_recipe_output_is_readable once; the per-output pin skips such a row
    # (until 8c round 2 this case's stand-in was Item.getItem('ae2:drive'); R5 made every Item member but Item.of throw)
    Case("8b r4 Ingredient.of('ae2:drive').first as event.shaped's raw output", T2,
         recipes("event.shaped(Ingredient.of('ae2:drive').first, ['A'], { A: 'minecraft:stick' })"
                 ".id('confluence:tier2/hidden_drive')"),
         {f"{PACKWIDE}::test_every_recipe_output_is_readable"}),
    Case("8c r2 Item.getItem('ae2:drive') as event.shaped's raw output", T2,
         recipes("event.shaped(Item.getItem('ae2:drive'), ['A'], { A: 'minecraft:stick' }).id('confluence:tier2/hidden_drive')"),
         {f"{PACKWIDE}::test_every_server_script_loads_and_runs"}),
    Case("8b r4 W2 flint's output removal written as { id: 'output:...' }", T1,
         ("  gate.replaceShaped(event, 'confluence:tier1/flint_and_steel', IDS.vanilla.flintAndSteel,\n",
          "  event.remove({ id: 'output:minecraft:flint_and_steel' })\n"
          "  gate.shaped(event, 'confluence:tier1/flint_and_steel', IDS.vanilla.flintAndSteel,\n"),
         {f"{PACKWIDE}::test_every_removal_is_an_owner_tests_removal"}),
    Case("8b r4 a builder function behind a branch in dump.js", DUMP,
         ("  event.forEachRecipe({}, r => rows.push(row(r)))\n",
          "  event.forEachRecipe({}, r => { if (String(r.getOrCreateId()) === 'ae2:network/blocks/controller') "
          "r.result('ae2:drive'); rows.push(row(r)) })\n"),
         {f"{PACKWIDE}::test_dump_source_names_only_allowed_members"}),
    # ---- Task 8c (the 8b follow-ups): a stand-in in a custom recipe's output, and a dump.js that reads a member it does not
    # name or pushes to a list a recipe hands out
    Case("8c event.custom's result is Ingredient.of(id).first", T2,
         recipes("event.custom({ type: 'ae2:inscriber', mode: 'press', ingredients: { middle: { item: 'minecraft:stick' } }, "
                 "result: Ingredient.of('ae2:drive').first }).id('confluence:tier2/hidden_drive')"),
         {f"{PACKWIDE}::test_every_recipe_output_is_readable"}),
    Case("8c event.custom's output id is Ingredient.of(id).first.id", T2,
         recipes("event.custom({ type: 'ae2:inscriber', mode: 'press', ingredients: { middle: { item: 'minecraft:stick' } }, "
                 "output: { id: Ingredient.of('ae2:drive').first.id, count: 1 } }).id('confluence:tier2/hidden_drive')"),
         {f"{PACKWIDE}::test_every_recipe_output_is_readable"}),
    # 8c round 2, R5: an Item.exists guard on the D132 removes. In game Item.exists is false for the three dead ids, so this
    # removes nothing; under the old runner the guard was a truthy stand-in, every remove was recorded and both item-tag tests
    # passed. The runner throws for any Item member but Item.of now.
    Case("8c r2 Item.exists guard around the D132 removes", EVENTS,
         ("IDS.allthemodium.unregisteredTagEntries.forEach(e => event.remove(tagId(e.tag), e.id))",
          "IDS.allthemodium.unregisteredTagEntries.forEach(e => { if (Item.exists(e.id)) { event.remove(tagId(e.tag), e.id) } })"),
         {"test_item_tags.py::test_item_tag_handler_registered_and_runs",
          "test_item_tags.py::test_item_tag_edits_are_exactly_the_twilight_swap_and_the_six_atm_removes",
          f"{PACKWIDE}::test_every_server_script_loads_and_runs"}),
    Case("8c a computed member read in dump.js", DUMP,
         ("  event.addedRecipes.forEach(r => rows.push(row(r)))\n",
          "  event.addedRecipes.forEach(r => rows.push(row(r)))\n"
          "  event.addedRecipes.forEach(r => { const f = r['res' + 'ult']; if (f) { f('ae2:drive') } })\n"),
         {f"{PACKWIDE}::test_dump_source_names_only_allowed_members"}),
    Case("8c push on a list a recipe hands out, in dump.js", DUMP,
         ("  event.addedRecipes.forEach(r => rows.push(row(r)))\n",
          "  event.addedRecipes.forEach(r => rows.push(row(r)))\n"
          "  event.addedRecipes.forEach(r => { r.get('ingredients').push('minecraft:dirt') })\n"),
         {f"{PACKWIDE}::test_dump_source_names_only_allowed_members"}),
    # ---- Task 9 (The Other gate wiring, test_other_gate_events.py): the quality review's mutants its fixed tests kill
    Case("t9 h1 creative through the pad (wiring)", EVENTS,
         ("    player = event.getPlayer()\n", "    player = event.getPlayer()\n    if (player.isCreative()) return\n"),
         {f"{GATE}::test_pad_cancels_once_after_its_own_code[creative-gets-no-pad-exemption]"}),
    Case("t9 h1b creative through the pad (wiring and lib)", (EVENTS, "lib/other_gate.js"),
         (("      held: () => {\n", "      exempt: () => OTHER_GATE_MC.exempt(player),\n      held: () => {\n"),
          ("    if (!main) return OTHER_GATE.padAction(true, false, null, null, null)\n",
           "    if (c.exempt()) return OTHER_GATE.padAction(false, false, null, null, null)\n"
           "    if (!main) return OTHER_GATE.padAction(true, false, null, null, null)\n")),
         {f"{GATE}::test_pad_cancels_once_after_its_own_code[creative-gets-no-pad-exemption]"}),
    Case("t9 h4 arrival exempts creative only", EVENTS,
         ("        exempt: () => OTHER_GATE_MC.exempt(player),\n        team: () => OTHER_GATE_MC.lookup(player),",
          "        exempt: () => player.isCreative(),\n        team: () => OTHER_GATE_MC.lookup(player),"),
         {f"{GATE}::test_arrival_listener[spectator-exempt]"}),
    Case("t9 p1 lookup passes a UUID", EVENTS,
         ("api.getManager().getTeamForPlayer(player)", "api.getManager().getTeamForPlayer(player.getUuid())"),
         {f"{GATE}::test_arrival_listener[tp-did-nothing-retried-once-then-gives-up]"}),
    Case("t9 p2 pad lookup passes the event", EVENTS,
         ("        found = OTHER_GATE_MC.lookup(player)\n", "        found = OTHER_GATE_MC.lookup(event)\n"),
         {f"{GATE}::test_pad_cancels_once_after_its_own_code[creative-gets-no-pad-exemption]"}),
    Case("t9 p3 travel lookup passes the event", EVENTS,
         ("      team: () => OTHER_GATE_MC.lookup(entity),", "      team: () => OTHER_GATE_MC.lookup(event),"),
         {f"{GATE}::test_travel_listener[other-unlocked-team]"}),
    Case("t9 p4 getPlayer by a string UUID", EVENTS,
         ("server.getPlayerList().getPlayer(uuid)", "server.getPlayerList().getPlayer(String(uuid))"),
         {f"{GATE}::test_arrival_listener[command-error-retried-once-then-gives-up]"}),
    Case("t9 x8 lookup gets an Optional without isPresent", EVENTS,
         ("    if (!opt.isPresent()) return { found: false, unlocked: false, team: null }\n", ""),
         {f"{GATE}::test_travel_listener[other-no-team]"}),
    Case("t9 m3 still-there check reads the stale player", EVENTS,
         ("String(p.getLevel().getDimension()) !== dest", "String(player.getLevel().getDimension()) !== dest"),
         {f"{GATE}::test_arrival_listener[already-left-not-moved]"}),
    Case("last round: the arrival retry is not bounded", EVENTS,
         ("OTHER_GATE_MC.moveNextTick(server, uuid, dest, message, retries - 1)", "OTHER_GATE_MC.moveNextTick(server, uuid, dest, message, retries)"),
         {f"{GATE}::test_arrival_listener[tp-did-nothing-retried-once-then-gives-up]"}),
    Case("last round: the login check compares a ResourceLocation, not a string", EVENTS,
         ("e => String(e.getEntity().getLevel().getDimension())", "e => e.getEntity().getLevel().getDimension()"),
         {f"{GATE}::test_login_listener[locked-in-other-moved]"}),
]
def must_fail(case):
    """The tests that must fail for `case` here: its `expected`, plus its `jar` tests when a server has been booted."""
    return set(case.expected) | (set(case.jar) if BOOTED else set())


MODULES = sorted({e.split("::")[0] for c in CASES for e in must_fail(c)})
CASE_MODULES = sorted({e.split("::")[0] for c in CASES for e in (*c.expected, *c.jar)})   # booted or not
SANITY = Case("sanity: no edit", (), (), set())
SUMMARY = re.compile(r"^(FAILED|ERROR) tools/tests/(\S+?)(?: - (.*))?$")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
# The child pytest must not inherit options meant for this run: PYTEST_ADDOPTS=-x would stop it at the first failure (so a
# case's later expected test never runs), and PYTEST_PLUGINS could load anything.
CHILD_ENV_DROP = ("PYTEST_ADDOPTS", "PYTEST_PLUGINS")
# --color=no: pytest colours its summary under PY_COLORS=1 or FORCE_COLOR=1 even into a pipe, and SUMMARY would then miss
# every line; the flag overrides both. COLUMNS: pytest cuts each short-summary line to the terminal width; the id and the
# start of the reason must fit.
CHILD_PYTEST = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--color=no", "--tb=no", "-W",
                "ignore::UserWarning"]


def child_env(**extra):
    """This run's environment for a child pytest. A $CONFLUENCE_MODS_DIR set here is passed on as the absolute directory kjs
    resolved it to (kjs.MODS), so a relative value means the same directory in the child, whose cwd is pack/ (round 4 R7)."""
    env = {k: v for k, v in os.environ.items() if k not in CHILD_ENV_DROP}
    if os.environ.get(MODS_ENV):
        env[MODS_ENV] = str(MODS)
    env.update({"PYTHONDONTWRITEBYTECODE": "1", "COLUMNS": "400", **extra})
    return env


def summary(stdout):
    """{failed test id: reason} from a pytest -rfE short summary, with any ANSI colour codes stripped first."""
    failed = {}
    for line in stdout.splitlines():
        m = SUMMARY.match(ANSI.sub("", line))
        if m:
            failed[m.group(2)] = m.group(3) or ""
    return failed


class StaleEdit(Exception):
    pass


def apply(root, case):
    files = case.file if isinstance(case.file, tuple) else (case.file,)
    edits = case.edit if isinstance(case.file, tuple) else (case.edit,)
    for rel, edit in zip(files, edits):
        p = root / rel
        src = p.read_text(encoding="utf-8")
        if isinstance(edit, tuple):
            old, new = edit
            if src.count(old) != 1:
                raise StaleEdit(f"stale edit: {old!r} not found once in kubejs/server_scripts/{rel} (it occurs "
                                f"{src.count(old)} times); update the case to the script's current text")
            src = src.replace(old, new)
        else:
            src += edit
        p.write_text(src, encoding="utf-8")


def run_case(case, modules):
    """(pytest's exit code, {failed test id: reason}, output tail) for one case; exit code None when the case could not run
    (a stale edit, or the subprocess itself failed), with the reason in place of the tail."""
    try:
        with tempfile.TemporaryDirectory(prefix="confluence-mutant-") as tmp:
            root = Path(tmp) / "server_scripts"
            shutil.copytree(DEFAULT_SCRIPTS, root)
            apply(root, case)
            cmd = [*CHILD_PYTEST, "-rfE", *[f"tools/tests/{m}" for m in modules]]
            res = subprocess.run(cmd, cwd=ROOT, env=child_env(**{SCRIPTS_ENV: str(root)}), capture_output=True, text=True,
                                 timeout=300)
    except StaleEdit as e:
        return None, {}, f"{case.name}: {e}"
    except Exception as e:   # noqa: BLE001  (reported as this case's failure, so the other cases still run)
        return None, {}, f"{case.name}: the case could not run: {type(e).__name__}: {e}"
    return res.returncode, summary(res.stdout), res.stdout[-3000:] + res.stderr[-2000:]


@pytest.fixture(scope="module")
def results():
    jobs = [(c, sorted({e.split("::")[0] for e in must_fail(c)})) for c in CASES] + [(SANITY, MODULES)]
    with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 2)) as pool:
        done = pool.map(lambda job: run_case(*job), jobs)
        return {job[0].name: r for job, r in zip(jobs, done)}


def matches(expected, failed_id):
    return failed_id == expected or ("[" not in expected and failed_id.startswith(expected + "["))


def test_sanity_copy_is_green(results):
    code, failed, tail = results[SANITY.name]
    assert (code, failed) == (0, {}), tail


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_mutant_is_caught(results, case):
    code, failed, tail = results[case.name]
    assert code is not None, tail
    missed = sorted(e for e in must_fail(case) if not any(matches(e, f) for f in failed))
    assert missed == [], f"{case.name}: these tests did not fail: {missed}; failed: {sorted(failed)}\n{tail}"
    # The short summary gives a bare assert as 'assert ...', an assert with a message as 'AssertionError: ...' and pytest.fail
    # as 'Failed: ...'; anything else (TypeError, KeyError, ...) is a test that crashed on the mutant.
    crashed = {f: why for f, why in failed.items() if not why.startswith(("assert ", "AssertionError", "Failed:"))}
    assert crashed == {}, f"{case.name}: a test failed by crashing, not by an assertion: {crashed}"
    assert code == 1, f"{case.name}: pytest exited {code}\n{tail}"




def skipped_for_jars(paths, cwd=ROOT, **env):
    """(exit code, the tests that read a mod jar, output tail): the test files `paths` run once with kjs.MODS at a missing
    directory ($CONFLUENCE_MODS_DIR), and every test that skips with kjs.pinned_jar's reason, read from a JUnit XML report as
    '<module>.py::<test>[<id>]'. Run rather than read from the source, so every way a test reaches pinned_jar counts: called
    as kjs.pinned_jar or under an alias, through a fixture of any name, a helper, or request.getfixturevalue."""
    with tempfile.TemporaryDirectory(prefix="confluence-nomods-") as tmp:
        report = Path(tmp) / "report.xml"
        cmd = [*CHILD_PYTEST, f"--junitxml={report}", *map(str, paths)]
        res = subprocess.run(cmd, cwd=cwd, env=child_env(**{MODS_ENV: str(Path(tmp) / "no-mods")}, **env),
                             capture_output=True, text=True, timeout=600)
        found = set()
        for tc in ET.parse(report).iter("testcase"):
            skipped = tc.find("skipped")
            if skipped is not None and JAR_SKIP in (skipped.get("message") or ""):
                found.add(junit_id(tc.get("classname"), tc.get("name")))
    return res.returncode, found, res.stdout[-3000:] + res.stderr[-2000:]


def junit_id(classname, name):
    """'<module>.py::[<Class>::]<test>[<id>]' from a JUnit testcase's classname ('tools.tests.test_x' or
    'tools.tests.test_x.TestY') and name (round 4 R6). The module is the segment just before the first class segment (one
    that starts with 'Test', pytest's default python_classes), or the last segment when there is no class, and the segments
    after it are classes. A directory named test_* before it is a directory (Task 8c, 8b follow-up F5). A module not named
    test_* raises ValueError (it was a bare StopIteration)."""
    parts = classname.split(".")
    i = next((k - 1 for k, part in enumerate(parts) if part.startswith("Test")), len(parts) - 1)
    if i < 0 or not parts[i].startswith("test_"):
        raise ValueError(f"JUnit classname {classname!r}: no test_* module (the segment before the first Test* class, or the "
                         f"last segment)")
    return "::".join([parts[i] + ".py", *parts[i + 1:], name])


@pytest.fixture(scope="module")
def jar_reading_tests():
    return skipped_for_jars([f"tools/tests/{m}" for m in CASE_MODULES])


def test_jar_reading_tests_are_listed_under_jar(jar_reading_tests):
    """Task 8b review I1 (round 3 V5): a jar-reading test skips in a clone with no .run/server/mods, so a case that expects it
    under `expected` fails there. Each such expectation belongs under `jar`, and `jar` holds nothing else. The same run shows
    the case modules are green with no mods directory at all (a fresh clone)."""
    code, jar_tests, tail = jar_reading_tests
    assert code == 0, tail
    assert jar_tests, f"no test skipped for want of mods; kjs.pinned_jar's reason is no longer {JAR_SKIP!r}?\n{tail}"
    misplaced = {c.name: sorted(e for e in c.expected if any(matches(e, j) for j in jar_tests)) for c in CASES}
    assert {k: v for k, v in misplaced.items() if v} == {}
    not_jar = {c.name: sorted(e for e in c.jar if not any(matches(e, j) for j in jar_tests)) for c in CASES}
    assert {k: v for k, v in not_jar.items() if v} == {}


def test_a_stale_edit_fails_only_its_own_case(tmp_path):
    """Task 8b review minor 5: an (old, new) edit whose old text is gone is reported as that case's result."""
    case = Case("stale", "dump.js", ("this text is in no script\n", "x"), {f"{PACKWIDE}::test_no_two_recipes_share_an_id"})
    code, failed, tail = run_case(case, [PACKWIDE])
    assert (code, failed) == (None, {}), tail
    assert tail == ("stale: stale edit: 'this text is in no script\\n' not found once in kubejs/server_scripts/dump.js (it "
                    "occurs 0 times); update the case to the script's current text")


def test_child_pytest_drops_this_runs_options(monkeypatch):
    """Task 8b review minor 4: PYTEST_ADDOPTS=-x in this run would stop a case's pytest at its first failure."""
    monkeypatch.setenv("PYTEST_ADDOPTS", "-x")
    monkeypatch.setenv("PYTEST_PLUGINS", "no_such_plugin_module")
    case = next(c for c in CASES if c.name == "t5 second handler re-makes the key (same id)")
    code, failed, tail = run_case(case, sorted({e.split("::")[0] for e in must_fail(case)}))
    assert code == 1 and all(any(matches(e, f) for f in failed) for e in must_fail(case)), tail


@pytest.mark.parametrize("var", ["PY_COLORS", "FORCE_COLOR"])
def test_a_coloured_run_still_reads_the_summary(monkeypatch, var):
    """Round 3 V3: with PY_COLORS=1 or FORCE_COLOR=1 in this run, a case is still read. Two layers keep it so: the child
    runs --color=no, and summary() strips ANSI codes as well; this test fails only when both go (the red check), and
    test_summary_strips_ansi_codes pins the strip on its own."""
    monkeypatch.setenv(var, "1")
    case = next(c for c in CASES if c.name == "t8 remove {mod: 'allthemodium'}")
    code, failed, tail = run_case(case, [BYP])
    assert code == 1 and all(any(matches(e, f) for f in failed) for e in must_fail(case)), tail


def test_summary_strips_ansi_codes():
    line = "\x1b[31mFAILED\x1b[0m tools/tests/x.py::test_y[a] - \x1b[1mAssertionError: z\x1b[0m"
    assert summary("noise\n" + line + "\n") == {"x.py::test_y[a]": "AssertionError: z"}


def test_skipped_for_jars_finds_every_way_to_reach_pinned_jar(tmp_path):
    """Round 3 V5: the forms a source scan for the name `pinned_jar` missed, each found by running them."""
    (tmp_path / "test_reach.py").write_text(
        "import pytest\n"
        "import kjs\n"
        "from kjs import pinned_jar as _pj\n"
        "from test_mek_tier5 import MEK_JAR\n"
        "MEK = ('Mekanism-', MEK_JAR, 'mekanism.pw.toml')\n"
        "def helper():\n    return kjs.pinned_jar(*MEK)\n"
        "@pytest.fixture(name='jar')\ndef some_other_name():\n    return _pj(*MEK)\n"
        "def test_attribute():\n    kjs.pinned_jar(*MEK)\n"
        "def test_alias():\n    _pj(*MEK)\n"
        "def test_renamed_fixture(jar):\n    pass\n"
        "def test_helper():\n    helper()\n"
        "def test_getfixturevalue(request):\n    request.getfixturevalue('jar')\n"
        "@pytest.mark.parametrize('x', [1, 2])\ndef test_param(x):\n    helper()\n"
        "class TestJar:\n    def test_in_a_class(self):\n        helper()\n"
        "    class TestInner:\n        def test_nested(self, jar):\n            pass\n"
        "def test_no_jar():\n    pass\n", encoding="utf-8")
    code, found, tail = skipped_for_jars([tmp_path / "test_reach.py"], cwd=tmp_path, PYTHONPATH=str(ROOT / "tools" / "tests"))
    assert code == 0, tail
    assert found == {f"test_reach.py::{t}" for t in ("test_attribute", "test_alias", "test_renamed_fixture", "test_helper",
                                                     "test_getfixturevalue", "test_param[1]", "test_param[2]",
                                                     "TestJar::test_in_a_class", "TestJar::TestInner::test_nested")}, tail


@pytest.mark.parametrize("classname,name,want", [
    ("tools.tests.test_mek_tier5", "test_x[a-b]", "test_mek_tier5.py::test_x[a-b]"),
    ("tools.tests.test_mek_tier5.TestJar", "test_x", "test_mek_tier5.py::TestJar::test_x"),
    ("test_reach.TestJar.TestInner", "test_y", "test_reach.py::TestJar::TestInner::test_y"),
])
def test_junit_id(classname, name, want):
    """Round 4 R6: a test inside a class once came out as 'TestJar.py::test_x'."""
    assert junit_id(classname, name) == want


@pytest.mark.parametrize("classname,name,want", [
    ("tools.test_dir.tests.test_mek_tier5", "test_x", "test_mek_tier5.py::test_x"),
    ("test_a.test_b.TestJar", "test_y", "test_b.py::TestJar::test_y"),
    ("test_a.test_b", "test_y", "test_b.py::test_y"),
])
def test_junit_id_ignores_test_directories(classname, name, want):
    """Task 8c (8b follow-up F5): a directory named test_* before the module is a directory, not the module."""
    assert junit_id(classname, name) == want


@pytest.mark.parametrize("classname", ["tools.tests.conftest", "tools.tests.helper.TestJar", ""])
def test_junit_id_fails_clearly_on_a_module_not_named_test(classname):
    """Task 8c (8b follow-up F5): once a bare StopIteration from next()."""
    with pytest.raises(ValueError, match="no test_\\* module"):
        junit_id(classname, "test_x")


def test_child_env_passes_the_mods_dir_absolute(monkeypatch):
    """Round 4 R7: kjs resolved $CONFLUENCE_MODS_DIR against this run's cwd; the child, whose cwd is pack/, gets that
    absolute directory, not the raw (maybe relative) value."""
    monkeypatch.setenv(MODS_ENV, "some/relative/dir")
    assert child_env()[MODS_ENV] == str(MODS) and Path(child_env()[MODS_ENV]).is_absolute()
    assert child_env(**{MODS_ENV: "/x"})[MODS_ENV] == "/x"   # an explicit value (skipped_for_jars) still wins
