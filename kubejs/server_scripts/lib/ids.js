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

// ---- v0.2 (tiers 3–4). Citations: research/phase7-tier3-ids.md (§ numbers "t3"), phase7-tier4-ids.md ("t4"),
// phase7-undergarden-worldgen-loot.md ("ug"). Tags keep the leading '#'; raw-JSON call sites slice(1).
// t3 §1: The_Undergarden-1.21.1-0.9.6.jar data/undergarden/{recipe/catalyst.json, dimension/undergarden.json,
// recipe/forgotten_nugget_to_ingot.json, loot_table/entities/forgotten_guardian.json}.
IDS.undergarden = { catalyst: 'undergarden:catalyst', dimension: 'undergarden:undergarden', forgottenIngot: 'undergarden:forgotten_ingot',
  forgottenGuardian: 'undergarden:forgotten_guardian', catacombsChest: 'undergarden:chests/catacombs',
  // ug §2: the three base-stone ore-replaceable tags (depthrock everywhere, shiverstone in the frost biomes, dreadrock in the depths).
  depthrockReplaceables: '#undergarden:depthrock_ore_replaceables', shiverstoneReplaceables: '#undergarden:shiverstone_ore_replaceables',
  dreadrockReplaceables: '#undergarden:dreadrock_ore_replaceables', biomes: '#undergarden:is_undergarden' }
// t3 §2: allthemodium-3.0.1_mc_1.21.1.jar data/allthemodium/recipe/{smithing/vibranium_upgrade_smithing_template.json,
// processing/vibranium/slurry/dirty/*.json, processing/vibranium/crystal/from_slurry.json}; data/c/tags/item/{ores,raw_materials}/vibranium.json.
IDS.allthemodium.vibraniumOre = 'allthemodium:vibranium_ore'
IDS.allthemodium.otherVibraniumOre = 'allthemodium:other_vibranium_ore'   // the only other Vibranium ore block; no *_slate_ore exists
IDS.allthemodium.rawVibranium = 'allthemodium:raw_vibranium'
IDS.allthemodium.vibraniumTemplate = 'allthemodium:vibranium_upgrade_smithing_template'
IDS.allthemodium.vibraniumCrystal = 'allthemodium:vibranium_crystal'
IDS.allthemodium.unobtainiumIngotTag = '#c:ingots/unobtainium'   // checked in Task 5 Step 1 against the jar
IDS.mek.vibraniumChain = {
  slurryDirtyFromOre: 'allthemodium:processing/vibranium/slurry/dirty/from_ore',
  slurryDirtyFromRawOre: 'allthemodium:processing/vibranium/slurry/dirty/from_raw_ore',
  slurryDirtyFromRawBlock: 'allthemodium:processing/vibranium/slurry/dirty/from_raw_block',
}
// t3 §3: Powah-6.2.10.jar data/powah/recipe/energizing/nitro_crystal.json (item powah:crystal_nitro, 20,000,000 FE, 16 out).
IDS.powah.nitroRecipe = 'powah:energizing/nitro_crystal'
IDS.powah.blazingCrystalBlock = 'powah:blazing_crystal_block'
// t3 §4: Mekanism-1.21.1-10.7.19.85.jar data/mekanism/recipe/{control_circuit/elite.json, control_circuit/infused_elite.json,
// processing/refined_obsidian/ingot/from_dust.json, teleportation_core.json, qio_*.json}; tags data/mekanism/tags/item/alloys/reinforced.json,
// data/c/tags/item/{circuits/advanced,circuits/ultimate,dusts/refined_obsidian,ingots/refined_obsidian,ender_pearls,glass_panes,ingots/lead}.json.
IDS.mek.eliteCircuit = 'mekanism:elite_control_circuit'
IDS.mek.eliteCircuitRecipes = ['mekanism:control_circuit/elite', 'mekanism:control_circuit/infused_elite']
IDS.mek.reinforcedAlloyTag = '#mekanism:alloys/reinforced'
IDS.mek.advancedCircuitTag = '#c:circuits/advanced'
IDS.mek.ultimateCircuitTag = '#c:circuits/ultimate'
IDS.mek.refinedObsidianDustTag = '#c:dusts/refined_obsidian'
IDS.mek.refinedObsidianIngot = 'mekanism:ingot_refined_obsidian'
IDS.mek.refinedObsidianIngotTag = '#c:ingots/refined_obsidian'
IDS.mek.refinedObsidianFromDustRecipe = 'mekanism:processing/refined_obsidian/ingot/from_dust'   // type mekanism:compressing
IDS.mek.teleportationCore = 'mekanism:teleportation_core'
IDS.mek.qioDashboard = 'mekanism:qio_dashboard'
IDS.mek.qioDriveArray = 'mekanism:qio_drive_array'       // recipe type mekanism:mek_data (t3 §4, D87)
IDS.mek.qioImporter = 'mekanism:qio_importer'
IDS.mek.qioExporter = 'mekanism:qio_exporter'
IDS.mek.personalStorageTag = '#mekanism:personal_storage'
IDS.mek.leadIngotTag = '#c:ingots/lead'
// t3 §5: ars_nouveau-1.21.1-5.13.1.jar data/ars_nouveau/recipe/ritual_brazier.json, data/c/tags/item/storage_blocks/source.json (via the recipe),
// data/ars_nouveau/tags/entity_type/drygmy_blacklist.json. t4 §3: recipe/planarium.json.
IDS.ars.ritualBrazier = 'ars_nouveau:ritual_brazier'
IDS.ars.arcanePedestal = 'ars_nouveau:arcane_pedestal'
IDS.ars.sourceBlockTag = '#c:storage_blocks/source'
IDS.ars.planarium = 'ars_nouveau:planarium'
IDS.ars.mobJar = 'ars_nouveau:mob_jar'
IDS.ars.stableWarpScroll = 'ars_nouveau:stable_warp_scroll'
IDS.ars.conjurationEssence = 'ars_nouveau:conjuration_essence'
IDS.ars.apparatusType = 'ars_nouveau:enchanting_apparatus'
IDS.ars.drygmyBlacklistTag = 'ars_nouveau:drygmy_blacklist'   // entity_type tag, not an item tag: not for check_tags
// t3 §6: irons_spellbooks-1.21.1-3.16.3.jar data/irons_spellbooks/recipe/lightning_upgrade_orb.json (8 lightning_rune round an upgrade_orb).
IDS.irons.lightningOrb = 'irons_spellbooks:lightning_upgrade_orb'
IDS.irons.lightningRune = 'irons_spellbooks:lightning_rune'
// t4 §2: industrialforegoing-1.21-3.6.39.jar data/industrialforegoing/recipe/dissolution_chamber/advanced_machine_frame.json.
IDS.ifg.advancedFrame = 'industrialforegoing:machine_frame_advanced'
IDS.ifg.advancedFrameTag = '#industrialforegoing:machine_frame/advanced'
IDS.ifg.pinkSlime = 'industrialforegoing:pink_slime'
IDS.ifg.diamondGearTag = '#c:gears/diamond'
IDS.ifg.stasisChamber = 'industrialforegoing:stasis_chamber'
// t4 §4–§6: cataclysm ender_guardian.json loot; deeperdarker dimension/otherside.json, loot_table/entities/{sludge,stalker}.json;
// the_bumblezone dimension/the_bumblezone.json, advancement/structures/enter_throne_pillar.json.
IDS.cataclysm.gauntletOfGuard = 'cataclysm:gauntlet_of_guard'
IDS.cataclysm.enderGuardian = 'cataclysm:ender_guardian'
IDS.dd = { resonarium: 'deeperdarker:resonarium', dimension: 'deeperdarker:otherside', sludge: 'deeperdarker:sludge', stalker: 'deeperdarker:stalker',
  soulCrystal: 'deeperdarker:soul_crystal', heartOfTheDeep: 'deeperdarker:heart_of_the_deep' }
IDS.bumblezone = { dimension: 'the_bumblezone:the_bumblezone', essence: 'the_bumblezone:essence_of_the_bees', beeQueen: 'the_bumblezone:bee_queen',
  thronePillarAdvancement: 'the_bumblezone:structures/enter_throne_pillar' }
IDS.vanilla.enderEye = 'minecraft:ender_eye'
IDS.vanilla.netherStarTag = '#c:nether_stars'
IDS.vanilla.redstoneBlockTag = '#c:storage_blocks/redstone'
IDS.vanilla.dragonBreath = 'minecraft:dragon_breath'
IDS.vanilla.enderPearlTag = '#c:ender_pearls'
IDS.vanilla.glassPaneTag = '#c:glass_panes'
IDS.vanilla.diamond = 'minecraft:diamond'
IDS.vanilla.stickyPiston = 'minecraft:sticky_piston'
IDS.vanilla.piston = 'minecraft:piston'
IDS.vanilla.theEnd = 'minecraft:the_end'
IDS.vanilla.enderDragon = 'minecraft:ender_dragon'
