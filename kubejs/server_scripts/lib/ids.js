// priority: 1
// Verified registry ids and tags (research/phase6-tier0-2-ids.md §A). Keep alphabetical by mod. The priority header makes
// this file load before every other server script (ScriptFile.compareTo: priority descending, then path), so top-level
// IDS uses such as worldgen.js PLACEMENTS do not depend on file-name order.
const IDS = {
  // zanite: the only zanite gem tag in any installed jar is aether-1.21.1-1.5.10-neoforge.jar!data/aether/tags/
  // item/gems/zanite.json ({"values":["aether:zanite_gemstone"]}) = tag id aether:gems/zanite. No jar ships
  // data/c/tags/item/gems/zanite.json, so the c: form phase6-tier0-2-ids.md line 77 lists is an empty tag.
  aether: { zanite: '#aether:gems/zanite' },
  allthemodium: { ingot: '#c:ingots/allthemodium', nugget: '#c:nuggets/allthemodium', ore: 'allthemodium:allthemodium_ore', slateOre: 'allthemodium:allthemodium_slate_ore', teleportPad: 'allthemodium:teleport_pad' },
  ars: { sourceGem: 'ars_nouveau:source_gem', apparatus: 'ars_nouveau:enchanting_apparatus', sourcestone: 'ars_nouveau:sourcestone',
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
// The Twilight stronghold cache, the loot table loot.js adds the Allthemodium template to (D2.3):
// twilightforest-1.21.1-4.8.3345-universal.jar!data/twilightforest/loot_table/stronghold_cache.json -- this version has
// no `structures/` path segment, so the id is the bare twilightforest:stronghold_cache.
IDS.twilight.strongholdCache = 'twilightforest:stronghold_cache'
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
// The 5x chain's three item_input tags, all in allthemodium-3.0.1_mc_1.21.1.jar!data/c/tags/item/:
// ores/allthemodium.json, raw_materials/allthemodium.json, storage_blocks/raw_allthemodium.json.
IDS.allthemodium.oreTag = '#c:ores/allthemodium'
IDS.allthemodium.rawTag = '#c:raw_materials/allthemodium'
IDS.allthemodium.rawBlockTag = '#c:storage_blocks/raw_allthemodium'
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
// phase7-undergarden-worldgen-loot.md ("ug"). Tags keep the leading '#'; raw-JSON call sites wrap it in tagId().
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
IDS.allthemodium.unobtainiumIngotTag = '#c:ingots/unobtainium'   // allthemodium-3.0.1_mc_1.21.1.jar!data/c/tags/item/ingots/unobtainium.json
// The Vibranium chain's three item_input tags, all in allthemodium-3.0.1_mc_1.21.1.jar!data/c/tags/item/:
// ores/vibranium.json, raw_materials/vibranium.json, storage_blocks/raw_vibranium.json.
IDS.allthemodium.vibraniumOreTag = '#c:ores/vibranium'
IDS.allthemodium.vibraniumRawTag = '#c:raw_materials/vibranium'
IDS.allthemodium.vibraniumRawBlockTag = '#c:storage_blocks/raw_vibranium'
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
// data/c/tags/item/{circuits/advanced,circuits/ultimate,dusts/refined_obsidian,ingots/refined_obsidian,ingots/lead}.json. (c:ender_pearls and
// c:glass_panes are only referenced by Mekanism's recipes, not defined in its jar; tools/check_tags.py proves both bound and
// non-empty against the boot-time tag export every run — see IDS.vanilla below.)
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
IDS.mek.qioDriveArrayRecipe = 'mekanism:qio_drive_array'   // Mekanism-1.21.1-10.7.19.85.jar!data/mekanism/recipe/qio_drive_array.json
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
IDS.ars.planariumRecipe = 'ars_nouveau:planarium'   // ars_nouveau-1.21.1-5.13.1.jar!data/ars_nouveau/recipe/planarium.json
IDS.ars.mobJar = 'ars_nouveau:mob_jar'
IDS.ars.stableWarpScroll = 'ars_nouveau:stable_warp_scroll'
IDS.ars.conjurationEssence = 'ars_nouveau:conjuration_essence'
IDS.ars.apparatusType = 'ars_nouveau:enchanting_apparatus'
// t3 §6: irons_spellbooks-1.21.1-3.16.3.jar data/irons_spellbooks/recipe/lightning_upgrade_orb.json (8 lightning_rune round an upgrade_orb).
IDS.irons.lightningOrb = 'irons_spellbooks:lightning_upgrade_orb'
IDS.irons.lightningRune = 'irons_spellbooks:lightning_rune'
// t4 §2: industrialforegoing-1.21-3.6.39.jar data/industrialforegoing/recipe/dissolution_chamber/advanced_machine_frame.json.
// Only the two tags: the recipe itself is an in-place datapack override (kubejs/data/industrialforegoing/recipe/
// dissolution_chamber/advanced_machine_frame.json), which cannot read IDS, so these exist to put both tags under
// tools/check_tags.py's boot-time coverage.
IDS.ifg.advancedFrameTag = '#industrialforegoing:machine_frame/advanced'
IDS.ifg.diamondGearTag = '#c:gears/diamond'
// t4 §4–§6: L_Ender's Cataclysm 1.21.1-3.33.jar!data/cataclysm/loot_table/entities/ender_guardian.json;
// deeperdarker-neoforge-1.21.1-1.4.1.jar!data/deeperdarker/{dimension/otherside.json, loot_table/entities/{sludge,stalker}.json};
// the_bumblezone-7.15.3+1.21.1-neoforge.jar!data/the_bumblezone/{dimension/the_bumblezone.json, advancement/structures/enter_throne_pillar.json}.
IDS.cataclysm.gauntletOfGuard = 'cataclysm:gauntlet_of_guard'
IDS.cataclysm.enderGuardian = 'cataclysm:ender_guardian'
IDS.dd = { resonarium: 'deeperdarker:resonarium', dimension: 'deeperdarker:otherside', sludge: 'deeperdarker:sludge', stalker: 'deeperdarker:stalker',
  soulCrystal: 'deeperdarker:soul_crystal', heartOfTheDeep: 'deeperdarker:heart_of_the_deep' }
// beeQueen is the entity id: the_bumblezone-7.15.3+1.21.1-neoforge.jar!data/the_bumblezone/loot_table/entities/bee_queen.json
// and assets/the_bumblezone/lang/en_us.json key `entity.the_bumblezone.bee_queen` ("Bee Queen").
IDS.bumblezone = { dimension: 'the_bumblezone:the_bumblezone', essence: 'the_bumblezone:essence_of_the_bees', beeQueen: 'the_bumblezone:bee_queen',
  thronePillarAdvancement: 'the_bumblezone:structures/enter_throne_pillar' }
IDS.vanilla.enderEye = 'minecraft:ender_eye'
IDS.vanilla.netherStarTag = '#c:nether_stars'
IDS.vanilla.redstoneBlockTag = '#c:storage_blocks/redstone'
IDS.vanilla.dragonBreath = 'minecraft:dragon_breath'
IDS.vanilla.enderPearlTag = '#c:ender_pearls'
IDS.vanilla.glassPaneTag = '#c:glass_panes'
IDS.vanilla.goldIngotTag = '#c:ingots/gold'   // c: convention tag, bound by NeoForge; tools/check_tags.py verifies it non-empty each boot
IDS.vanilla.diamond = 'minecraft:diamond'
IDS.vanilla.stickyPiston = 'minecraft:sticky_piston'
IDS.vanilla.piston = 'minecraft:piston'
IDS.vanilla.theEnd = 'minecraft:the_end'
IDS.vanilla.enderDragon = 'minecraft:ender_dragon'

// ---- v0.3 (tiers 5–6). Report keys are the v0.3 spec's (docs/superpowers/specs/2026-09-25-v0.3-tiers-5-6-design.md):
// T5 = research/phase7-tier5-ids.md, AE2 = phase7-ae2-ids.md, AA = phase7-tier6-adastra.md, OD = phase7-other-dimension.md,
// ES = phase7-eternal-starlight.md, SS = phase7-soulshard-essence.md, BA = phase7-tier5-6-bypass-audit.md,
// PAD = phase7-other-pad-script.md, GAP = phase7-v0.3-gaps.md. Every id was re-read from the jar or the boot exports
// (.run/server/kubejs/exported/{tags,recipes}.json) when this block was written. Tags keep the leading '#', except the
// bound-but-empty ones, which stay bare so tools/check_tags.py (which fails on an empty '#' literal) does not see them.

// Dimensions. Vanilla: server-1.21.1-20240808.144430-srg.jar net/minecraft/world/level/Level.<clinit> string constants
// "overworld" / "the_nether" (OVERWORLD / NETHER). ATM: allthemodium-3.0.1_mc_1.21.1.jar!data/allthemodium/dimension/
// {the_other,the_beyond,mining}.json (OD §1, PAD §1.4). unlockFlag is the pack's own FTB Teams extraData key (D109;
// storage per PAD §3(a)), not a mod id.
IDS.vanilla.overworld = 'minecraft:overworld'
IDS.vanilla.theNether = 'minecraft:the_nether'
IDS.other = { dimension: 'allthemodium:the_other', beyond: 'allthemodium:the_beyond', mining: 'allthemodium:mining',
  unlockFlag: 'confluence_other_unlocked' }

// Vanilla items the v0.3 recipes name (spec §4.1, §5, §6): lang block.minecraft.{dragon_egg,redstone_torch,crafting_table,
// lightning_rod,furnace} and item.minecraft.{bucket,elytra} in server-1.21.1-20240808.144430-extra.jar. The two c: tags are
// NeoForge's: neoforge-21.1.250-universal.jar!data/c/tags/item/ingots/{copper,iron}.json. #minecraft:wool is the space suit's
// W (AA §1.2); 337 items in tags.json.
IDS.vanilla.dragonEgg = 'minecraft:dragon_egg'
IDS.vanilla.redstoneTorch = 'minecraft:redstone_torch'
IDS.vanilla.craftingTable = 'minecraft:crafting_table'
IDS.vanilla.lightningRod = 'minecraft:lightning_rod'
IDS.vanilla.bucket = 'minecraft:bucket'
IDS.vanilla.furnace = 'minecraft:furnace'
IDS.vanilla.elytra = 'minecraft:elytra'
IDS.vanilla.copperIngotTag = '#c:ingots/copper'
IDS.vanilla.ironIngotTag = '#c:ingots/iron'
IDS.vanilla.woolTag = '#minecraft:wool'

// T5 §1.1–1.5: Mekanism-1.21.1-10.7.19.85.jar!data/mekanism/recipe/{control_circuit/ultimate,control_circuit/infused_ultimate,
// digital_miner,qio_drive_base,qio_redstone_adapter,quantum_entangloporter,chemical_dissolution_chamber,chemical_washer,
// chemical_crystallizer}.json; tags data/c/tags/item/circuits/elite.json, data/mekanism/tags/item/alloys/atomic.json,
// data/c/tags/item/gems/fluorite.json (1 entry each in tags.json). Items: lang item.mekanism.* / block.mekanism.*.
IDS.mek.ultimateCircuit = 'mekanism:ultimate_control_circuit'
IDS.mek.ultimateCircuitRecipes = ['mekanism:control_circuit/ultimate', 'mekanism:control_circuit/infused_ultimate']
IDS.mek.eliteCircuitTag = '#c:circuits/elite'
IDS.mek.atomicAlloyTag = '#mekanism:alloys/atomic'
IDS.mek.fluoriteGemTag = '#c:gems/fluorite'
IDS.mek.steelCasing = 'mekanism:steel_casing'
IDS.mek.basicChemicalTank = 'mekanism:basic_chemical_tank'
IDS.mek.basicFluidTank = 'mekanism:basic_fluid_tank'
IDS.mek.robit = 'mekanism:robit'
IDS.mek.logisticalSorter = 'mekanism:logistical_sorter'
IDS.mek.digitalMiner = 'mekanism:digital_miner'           // item and default recipe id (dump type mekanism:mek_data)
IDS.mek.hdpeSheet = 'mekanism:hdpe_sheet'                 // T5 §1.4, AE2 §5: no c: tag holds it
IDS.mek.electricPump = 'mekanism:electric_pump'           // spec §6 D6.3 oxygen-loader swap
// The six tier-3 defaults D113 re-keys to elite circuits (spec §5 "T5.1 side"). Each id is both the item and its default
// recipe (dump: qio_drive_base, qio_redstone_adapter, quantum_entangloporter, chemical_crystallizer are
// minecraft:crafting_shaped; chemical_dissolution_chamber, chemical_washer are mekanism:mek_data). Spec §5 says "eight" but
// lists these six. D113 names nine items; the other three (QIO drive array, importer, exporter) are already the pack's own
// recipes in tiers/tier3.js (confluence:tier3/qio_{drive_array,importer,exporter}).
IDS.mek.qioDriveBase = 'mekanism:qio_drive_base'
IDS.mek.qioRedstoneAdapter = 'mekanism:qio_redstone_adapter'
IDS.mek.quantumEntangloporter = 'mekanism:quantum_entangloporter'
IDS.mek.chemicalDissolutionChamber = 'mekanism:chemical_dissolution_chamber'
IDS.mek.chemicalWasher = 'mekanism:chemical_washer'
IDS.mek.chemicalCrystallizer = 'mekanism:chemical_crystallizer'
IDS.mek.eliteSwapRecipes = ['mekanism:qio_drive_base', 'mekanism:qio_redstone_adapter', 'mekanism:quantum_entangloporter',
  'mekanism:chemical_dissolution_chamber', 'mekanism:chemical_washer', 'mekanism:chemical_crystallizer']
// Raw-JSON recipe types (serializer ids as the dump's `type` column prints them: 89 mekanism:combining, 86 mekanism:mek_data rows).
IDS.mek.combiningType = 'mekanism:combining'
IDS.mek.mekDataType = 'mekanism:mek_data'
// BA §1.1, §1.3: the Unobtainium 5x chain's three entry recipes (type mekanism:dissolution; allthemodium-3.0.1_mc_1.21.1.jar!
// data/allthemodium/recipe/processing/unobtainium/slurry/dirty/*.json). Removed and replaced by mekanism:combining (spec §7 X2.2).
IDS.mek.unobtainiumChain = {
  slurryDirtyFromOre: 'allthemodium:processing/unobtainium/slurry/dirty/from_ore',
  slurryDirtyFromRawOre: 'allthemodium:processing/unobtainium/slurry/dirty/from_raw_ore',
  slurryDirtyFromRawBlock: 'allthemodium:processing/unobtainium/slurry/dirty/from_raw_block',
}

// T5 §3.1: industrialforegoing-1.21-3.6.39.jar!data/industrialforegoing/recipe/dissolution_chamber/supreme_machine_frame.json
// (the id the T5.2 datapack override replaces; dump type industrialforegoing:dissolution_chamber) and
// data/industrialforegoing/tags/item/machine_frame/supreme.json (1 entry). Item: lang block.industrialforegoing.machine_frame_supreme.
IDS.ifg.supremeFrame = 'industrialforegoing:machine_frame_supreme'
IDS.ifg.supremeFrameTag = '#industrialforegoing:machine_frame/supreme'
IDS.ifg.supremeFrameRecipe = 'industrialforegoing:dissolution_chamber/supreme_machine_frame'

// T5 §2.1–2.2: Powah-6.2.10.jar (lang block.powah.nitro_crystal_block); energizing is the dump type of 19 rows.
IDS.powah.nitroBlock = 'powah:nitro_crystal_block'
IDS.powah.energizingType = 'powah:energizing'

// T5 §4.1–4.2, §4.6, OD §2: allthemodium-3.0.1_mc_1.21.1.jar lang item.allthemodium.* / block.allthemodium.unobtainium_ore;
// tags data/c/tags/item/{storage_blocks/unobtainium,ores/unobtainium,raw_materials/unobtainium,storage_blocks/raw_unobtainium}.json.
IDS.allthemodium.unobtainiumOre = 'allthemodium:unobtainium_ore'
IDS.allthemodium.unobtainiumCrystal = 'allthemodium:unobtainium_crystal'
IDS.allthemodium.unobtainiumBlockTag = '#c:storage_blocks/unobtainium'
IDS.allthemodium.unobtainiumOreTag = '#c:ores/unobtainium'
IDS.allthemodium.unobtainiumRawTag = '#c:raw_materials/unobtainium'
IDS.allthemodium.unobtainiumRawBlockTag = '#c:storage_blocks/raw_unobtainium'
IDS.allthemodium.unobAtmAlloy = 'allthemodium:unobtainium_allthemodium_alloy_ingot'   // M5.1 result
IDS.allthemodium.vibAtmAlloy = 'allthemodium:vibranium_allthemodium_alloy_ingot'      // X5.1 result
IDS.allthemodium.unobVibAlloy = 'allthemodium:unobtainium_vibranium_alloy_ingot'     // X5.2 result
IDS.allthemodium.piglichHeart = 'allthemodium:piglich_heart'

// Tier-ore closures (spec §7 D112; GAP §2.2 tags the ores are in, §2.4 the nine empty incorrect_for tags). Block-tag
// counts are the boot's tags.json, registry minecraft:block.
IDS.tierOres = {
  // D112b: the five ore blocks (lang block.allthemodium.* and assets/allthemodium/blockstates/*.json).
  blocks: [IDS.allthemodium.ore, IDS.allthemodium.slateOre, IDS.allthemodium.vibraniumOre, IDS.allthemodium.otherVibraniumOre,
    IDS.allthemodium.unobtainiumOre],
  // D112a: ATM's three non-empty tool-tier tags (allthemodium jar data/c/tags/block/needs_{allthemodium,vibranium,unobtainium}_tool.json;
  // 4, 3 and 20 blocks).
  needsToolTags: ['#c:needs_allthemodium_tool', '#c:needs_vibranium_tool', '#c:needs_unobtainium_tool'],
  // The spec's fourth tag is bound but EMPTY: allthemodium jar data/c/tags/block/needs_allthemodiumalloy_tool.json is
  // {"values": []} and tags.json counts 0. Bare on purpose, because check_tags fails on an empty '#' literal. D112a still
  // nests all four: Task 8 writes '#' + IDS.tierOres.alloyToolTagEmpty, which check_tags does not see, by design.
  alloyToolTagEmpty: 'c:needs_allthemodiumalloy_tool',
  // The nine tags D112a fills. Each is bare because it is bound but empty until then (0 blocks in tags.json; GAP §2.4), so
  // a '#' literal would fail check_tags. Bare is also the form event.add(tag, ...) takes as its first argument.
  incorrectForTags: ['cataclysm:needs_monstrosity_tool', 'cataclysm:needs_black_steel_tool', 'undergarden:incorrect_for_forgotten_tool',
    'deeperdarker:incorrect_for_resonarium_tool', 'deeperdarker:incorrect_for_warden_tool', 'mekanism:incorrect_for_disassembler',
    'mekanism:incorrect_for_meka_tool', 'mysticalagriculture:incorrect_for_supremium_tool',
    'mysticalagriculture:incorrect_for_awakened_supremium_tool'],
  // D112b: block tags the five ores join. All bound and non-empty (wither_immune 102; ignis, maledictus, scylla 26 each;
  // netherite_monstrosity 39): server-1.21.1-20240808.144430-extra.jar!data/minecraft/tags/block/wither_immune.json and
  // L_Ender's Cataclysm 1.21.1-3.33.jar!data/cataclysm/tags/block/{ignis,maledictus,scylla,netherite_monstrosity}_immune.json.
  // Non-empty, so kept with '#' for check_tags. Task 8 passes tagId(t) as the first argument of event.add:
  // kubejs-neoforge-2101.7.2-build.377.jar TagKubeEvent.add(ResourceLocation, Object...) converts a JS string with
  // ID.mc -> ID.of(o, false) -> ResourceLocation.parse, which does not strip a '#', so a '#' id there throws at load.
  immuneTags: ['#minecraft:wither_immune', '#cataclysm:ignis_immune', '#cataclysm:maledictus_immune', '#cataclysm:scylla_immune',
    '#cataclysm:netherite_monstrosity_immune'],
  // D112c: the six plain-furnace recipes removed (dump type minecraft:smelting). The *_from_raw_blasting rows stay.
  smeltingRecipes: ['allthemodium:allthemodium_ingot_from_ore_smelting', 'allthemodium:vibranium_ingot_from_ore_smelting',
    'allthemodium:unobtainium_ingot_from_ore_smelting', 'allthemodium:allthemodium_ingot_from_raw_smelting',
    'allthemodium:vibranium_ingot_from_raw_smelting', 'allthemodium:unobtainium_ingot_from_raw_smelting'],
}

// Spec §8 worldgen. OD §1: The Other's biome_source lists exactly these seven biomes (allthemodium jar
// data/allthemodium/dimension/the_other.json; each at data/allthemodium/worldgen/biome/<name>.json) and its stone is
// allthemodium:ancient_stone (tag data/allthemodium/tags/block/ancient_stone.json, 1 block). AA §4.1–4.4:
// adastra-1.21.1-1.16.25-neoforge.jar data/ad_astra/worldgen/biome/{mercury_deltas,glacio_ice_peaks,glacio_snowy_barrens}.json
// and data/ad_astra/tags/block/{mercury,glacio}_stone_replaceables.json (1 and 2 blocks). Biome lists are plain ids.
IDS.worldgen = {
  otherBiomes: ['allthemodium:soul_sand_valley', 'allthemodium:the_other', 'allthemodium:desert', 'allthemodium:basalt_deltas',
    'allthemodium:warped_forest', 'allthemodium:desert_hills', 'allthemodium:crimson_forest'],
  ancientStone: '#allthemodium:ancient_stone',
  mercuryBiomes: ['ad_astra:mercury_deltas'],
  mercuryStone: '#ad_astra:mercury_stone_replaceables',
  glacioBiomes: ['ad_astra:glacio_ice_peaks', 'ad_astra:glacio_snowy_barrens'],
  glacioStone: '#ad_astra:glacio_stone_replaceables',
  deepslate: '#minecraft:deepslate_ore_replaceables',
}

// Pack items from kubejs/startup_scripts/items.js (event.create): the two planet shards (M6.1) and their ore blocks (§8).
IDS.pack.mercuryShard = 'kubejs:mercury_shard'
IDS.pack.glacioShard = 'kubejs:glacio_shard'
IDS.pack.mercuryOre = 'kubejs:mercury_ore'
IDS.pack.glacioOre = 'kubejs:glacio_ore'

// T5 §5.1 (Wilden Tribute); the four essences by name for T6.1's four item slots (same ids as IDS.ars.essences; lang
// item.ars_nouveau.{air,earth,water,fire}_essence in ars_nouveau-1.21.1-5.13.1.jar).
IDS.ars.wildenTribute = 'ars_nouveau:wilden_tribute'
IDS.ars.airEssence = 'ars_nouveau:air_essence'
IDS.ars.earthEssence = 'ars_nouveau:earth_essence'
IDS.ars.waterEssence = 'ars_nouveau:water_essence'
IDS.ars.fireEssence = 'ars_nouveau:fire_essence'
// SS §1.1: irons_spellbooks-1.21.1-3.16.3.jar lang item.irons_spellbooks.divine_soulshard (M6.1 pedestal).
IDS.irons.divineSoulshard = 'irons_spellbooks:divine_soulshard'
// ES §3.7: eternalstarlight-0.9.0+1.21.1+neoforge.jar!data/c/tags/item/ingots/unrealium.json (1 entry; D6.1's W).
IDS.starlight = { unrealiumIngotTag: '#c:ingots/unrealium' }

// AE2 §1.1–1.2, §3, §5: appliedenergistics2-19.2.17.jar lang block.ae2.* / item.ae2.*. The default recipes are removed BY ID:
// removing by output also kills ae2:network/blocks/pattern_providers_interface_alt (AE2 §4.5), and part/material outputs
// dump as 'PartItem[...]' / 'MaterialItem[...]', not as item ids. Recipe ids are dump rows.
IDS.ae2 = {
  inscriber: 'ae2:inscriber', charger: 'ae2:charger', controller: 'ae2:controller', drive: 'ae2:drive',
  importBus: 'ae2:import_bus', exportBus: 'ae2:export_bus', terminal: 'ae2:terminal',
  fluixCrystal: 'ae2:fluix_crystal', fluixPearl: 'ae2:fluix_pearl', quartzFiber: 'ae2:quartz_fiber',
  engineeringProcessor: 'ae2:engineering_processor', logicProcessor: 'ae2:logic_processor', calculationProcessor: 'ae2:calculation_processor',
  skyStoneBlock: 'ae2:smooth_sky_stone_block', fluixGlassCable: 'ae2:fluix_glass_cable',
  annihilationCore: 'ae2:annihilation_core', formationCore: 'ae2:formation_core',
  illuminatedPanel: 'ae2:semi_dark_monitor',   // lang item.ae2.semi_dark_monitor = "Illuminated Panel"
  wirelessReceiver: 'ae2:wireless_receiver', craftingUnit: 'ae2:crafting_unit', patternProvider: 'ae2:pattern_provider',
  recipes: {
    inscriber: 'ae2:network/blocks/inscribers', charger: 'ae2:network/blocks/crystal_processing_charger',
    controller: 'ae2:network/blocks/controller', drive: 'ae2:network/blocks/storage_drive',
    importBus: 'ae2:network/parts/import_bus', exportBus: 'ae2:network/parts/export_bus',
    terminal: 'ae2:network/parts/terminals',                          // minecraft:crafting_shapeless
    wirelessReceiver: 'ae2:network/wireless_part', craftingUnit: 'ae2:network/crafting/cpu_crafting_unit',
    patternProvider: 'ae2:network/blocks/pattern_providers_interface',   // only this one (spec §6 S6.2)
  },
}

// AA §1.1–1.4, §2, §3.2: adastra-1.21.1-1.16.25-neoforge.jar lang item.ad_astra.* / block.ad_astra.*; tags
// data/ad_astra/tags/item/{steel_plates,steel_blocks}.json (1 and 2 entries) and data/c/tags/item/ingots/{desh,ostrum,calorite}.json
// (1 each); recipe types from ModRecipeTypes (AA §2; dump types ad_astra:alloying 1 row, ad_astra:compressing 10). No Etrium
// tag exists (AA §2.3), so Etrium is named by item. Each machine's item id is also its default recipe id (dump rows, all
// minecraft:crafting_shaped).
IDS.adastra = {
  nasaWorkbench: 'ad_astra:nasa_workbench', spaceSuit: 'ad_astra:space_suit', oxygenLoader: 'ad_astra:oxygen_loader',
  fuelRefinery: 'ad_astra:fuel_refinery', steelEngine: 'ad_astra:steel_engine',
  engineFrame: 'ad_astra:engine_frame', fan: 'ad_astra:fan', oxygenGear: 'ad_astra:oxygen_gear', gasTank: 'ad_astra:gas_tank',
  etriumIngot: 'ad_astra:etrium_ingot', etriumPlate: 'ad_astra:etrium_plate', iceShard: 'ad_astra:ice_shard',
  steelPlateTag: '#ad_astra:steel_plates', steelBlockTag: '#ad_astra:steel_blocks',
  deshIngotTag: '#c:ingots/desh', ostrumIngotTag: '#c:ingots/ostrum', caloriteIngotTag: '#c:ingots/calorite',
  alloyingType: 'ad_astra:alloying', compressingType: 'ad_astra:compressing',
  recipes: { nasaWorkbench: 'ad_astra:nasa_workbench', spaceSuit: 'ad_astra:space_suit', oxygenLoader: 'ad_astra:oxygen_loader',
    fuelRefinery: 'ad_astra:fuel_refinery', steelEngine: 'ad_astra:steel_engine' },
}

// Raw recipe/worldgen JSON wants a tag id without the leading '#'. Fails loudly instead of silently mangling a plain id.
function tagId(tag) {
  if (typeof tag !== 'string' || tag[0] !== '#') throw new Error('tagId: expected a #tag, got ' + tag)
  return tag.slice(1)
}
