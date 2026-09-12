// Verified registry ids and tags (research/phase6-tier0-2-ids.md §A). Keep alphabetical by mod.
const IDS = {
  // zanite: the only zanite gem tag in any installed jar is aether-1.21.1-1.5.10-neoforge.jar!data/aether/tags/
  // item/gems/zanite.json ({"values":["aether:zanite_gemstone"]}) = tag id aether:gems/zanite. No jar ships
  // data/c/tags/item/gems/zanite.json, so the c: form phase6-tier0-2-ids.md line 77 lists is an empty tag.
  aether: { zanite: '#aether:gems/zanite' },
  allthemodium: { ingot: '#c:ingots/allthemodium', nugget: '#c:nuggets/allthemodium', ore: 'allthemodium:allthemodium_ore', slateOre: 'allthemodium:allthemodium_slate_ore', teleportPad: 'allthemodium:teleport_pad' },
  ars: { sourceGem: 'ars_nouveau:source_gem', sourceGemBlock: 'ars_nouveau:source_gem_block', apparatus: 'ars_nouveau:enchanting_apparatus', sourcestone: 'ars_nouveau:sourcestone',
         essences: ['ars_nouveau:air_essence', 'ars_nouveau:earth_essence', 'ars_nouveau:fire_essence', 'ars_nouveau:water_essence'], essenceTag: '#confluence:ars_essences' },
  cataclysm: { monstrousHorn: 'cataclysm:monstrous_horn' },
  fs: { controller: 'functionalstorage:storage_controller', netheriteUpgrade: 'functionalstorage:netherite_upgrade' },
  ifg: { pityFrame: 'industrialforegoing:machine_frame_pity', simpleFrame: 'industrialforegoing:machine_frame_simple', simpleFrameTag: '#industrialforegoing:machine_frame/simple',
         pityFrameTag: '#industrialforegoing:machine_frame/pity', dissolutionChamber: 'industrialforegoing:dissolution_chamber', plastics: '#c:plastics', latex: 'industrialforegoing:latex' },
  irons: { arcaneAnvil: 'irons_spellbooks:arcane_anvil', upgradeOrb: 'irons_spellbooks:upgrade_orb', arcaneEssence: 'irons_spellbooks:arcane_essence' },
  mek: { osmiumIngot: '#c:ingots/osmium', osmiumIngotItem: 'mekanism:ingot_osmium', redstoneDust: '#c:dusts/redstone', infuser: 'mekanism:metallurgic_infuser',
         basicCircuit: '#c:circuits/basic', advancedCircuit: 'mekanism:advanced_control_circuit', heatGenerator: 'mekanismgenerators:heat_generator' },
  powah: { energizedSteel: 'powah:steel_energized', spirited: 'powah:crystal_spirited', nitro: 'powah:crystal_nitro', uraninite: 'powah:uraninite',
           uraniniteOre: 'powah:uraninite_ore', uraniniteOrePoor: 'powah:uraninite_ore_poor', uraniniteOreDense: 'powah:uraninite_ore_dense',
           deepslateUraniniteOre: 'powah:deepslate_uraninite_ore', deepslateUraniniteOrePoor: 'powah:deepslate_uraninite_ore_poor', deepslateUraniniteOreDense: 'powah:deepslate_uraninite_ore_dense' },
  soph: { chest: 'sophisticatedstorage:chest' },
  toms: { storageTerminal: 'toms_storage:storage_terminal', craftingTerminal: 'toms_storage:crafting_terminal', inventoryConnector: 'toms_storage:inventory_connector' },
  twilight: { uncraftingTable: 'twilightforest:uncrafting_table', knightmetal: '#c:ingots/knightmetal', activatorTag: 'twilightforest:portal/activator' },
  vanilla: { flintAndSteel: 'minecraft:flint_and_steel', fireCharge: 'minecraft:fire_charge', ruinedPortalLoot: 'minecraft:chests/ruined_portal', netherite: 'minecraft:netherite_ingot', enderPearl: 'minecraft:ender_pearl' },
  pack: { twilightKey: 'kubejs:twilight_key', otherKey: 'kubejs:other_key', endFocus: 'kubejs:end_focus', astralFocus: 'kubejs:astral_focus', catalyst: 'kubejs:confluence_catalyst', coin: 'kubejs:coin' },
}

// Task 11 additions. Every line cites research/phase6-tier0-2-ids-2.md unless a jar path is given.
// §A1: the Allthemodium-tier smithing template (allthemodium-3.0.1_mc_1.21.1.jar!data/allthemodium/recipe/smithing/allthemodium_upgrade_smithing_template.json).
IDS.allthemodium.template = 'allthemodium:allthemodium_upgrade_smithing_template'
// §A2: raw ore item (tag c:raw_materials/allthemodium).
IDS.allthemodium.rawOre = 'allthemodium:raw_allthemodium'
// Session 10 (issue #1 C10): Allthemodium's two template loot sources outside their tier dimensions, both read from
// allthemodium-3.0.1_mc_1.21.1.jar: data/minecraft/worldgen/processor_list/ancient_city_generic_degradation.json turns
// polished basalt (p 0.009) into allthemodium:suspicious_clay with append_loot `allthemodium:arch` (the Allthemodium
// template, data/allthemodium/loot_table/arch.json), and treasure_rooms.json (bastions) turns blackstone (p 0.007) into
// allthemodium:suspicious_soul_sand with `allthemodium:arch2` (the Vibranium template). Emptied in loot.js ([D2.3] note).
IDS.allthemodium.strayTemplateTables = ['allthemodium:arch', 'allthemodium:arch2']
// §A3 crystal row (processing/allthemodium/crystal/from_slurry.json output).
IDS.allthemodium.crystal = 'allthemodium:allthemodium_crystal'
// Jar check for this task: data/c/tags/item/ingots/vibranium.json exists in allthemodium-3.0.1_mc_1.21.1.jar
// ({"values":["allthemodium:vibranium_ingot"]}), so the tag form is used. Raw recipe JSON drops the leading '#'.
IDS.allthemodium.vibraniumIngotTag = '#c:ingots/vibranium'
// §A3: the three 5x-chain entry recipes (type mekanism:dissolution, registered by Allthemodium itself under
// data/allthemodium/recipe/processing/allthemodium/). Removed and replaced by mekanism:combining in bypass.js (D62).
IDS.mek.allthemodiumChain = {
  slurryDirtyFromOre: 'allthemodium:processing/allthemodium/slurry/dirty/from_ore',
  slurryDirtyFromRawOre: 'allthemodium:processing/allthemodium/slurry/dirty/from_raw_ore',
  slurryDirtyFromRawBlock: 'allthemodium:processing/allthemodium/slurry/dirty/from_raw_block',
}
// §Q2: dimension id (not the dimension_type) and the Cataclysm boss entity id.
IDS.aether.dimension = 'aether:the_aether'
IDS.cataclysm.monstrosity = 'cataclysm:netherite_monstrosity'
// §M5 names the spirited-crystal RECIPE (not the item powah:crystal_spirited), but derives its id as
// 'powah:spirited_crystal'; the live recipe id is 'powah:energizing/spirited_crystal' — the namespace + path-under-
// recipe/ rule §M5 itself states, applied to Powah-6.2.10.jar!data/powah/recipe/energizing/spirited_crystal.json, and
// the id that appears in the Task 10 dump (.run/server/kubejs/exported/recipes.json).
IDS.powah.spiritedRecipe = 'powah:energizing/spirited_crystal'
