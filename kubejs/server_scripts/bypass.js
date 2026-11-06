// Bypass closures (pack spec §2.4; the v0.3 rows at the end follow the v0.3 spec §7). Ids in research/phase6-tier0-2-ids.md §A/§B and
// research/phase6-tier0-2-ids-2.md §A3/§M7; regex removal confirmed on 2101, syntax report §2.2.
ServerEvents.recipes(event => {
  gate.remove(event, { id: 'industrialforegoing:laser_drill_ore/ancient_debris' })   // X2.5
  gate.remove(event, { id: IDS.twilight.uncraftingTable })                          // X2.6
  gate.remove(event, { id: /^deeperdarker:.*gloomslate_.*_ore$/ })                    // [X2.2] note: no gloomslate smelting shortcut

  // [X2.2] (D62): the Allthemodium 5x chain's three entry recipes (type mekanism:dissolution, ore/raw ore/raw block ->
  // dirty slurry) are removed and re-expressed as mekanism:combining recipes whose extra input is one vibranium ingot,
  // so the 5x route cannot run before Vibranium [D3.2]. Yields are the 5x chain's, expressed as crystals.
  // Recipe ids read from allthemodium-3.0.1_mc_1.21.1.jar!data/allthemodium/recipe/processing/allthemodium/slurry/
  // dirty/{from_ore,from_raw_ore,from_raw_block}.json; their item_input tags and counts (1 ore / 3 raw / 1 raw block)
  // are IDS.allthemodium.{oreTag,rawTag,rawBlockTag} in lib/ids.js.
  // JSON shape copied from Mekanism-1.21.1-10.7.19.85.jar!data/mekanism/recipe/combining/obsidian.json:
  //   {"type":"mekanism:combining","extra_input":{"count":1,"tag":"c:cobblestones/deepslate"},
  //    "main_input":{"count":4,"tag":"c:dusts/obsidian"},"output":{"count":1,"id":"minecraft:obsidian"}}
  // (same three keys as the KubeJS Mekanism combining schema, syntax report §5). Raw JSON tags carry no leading '#'.
  const vibraniumIngot = { count: 1, tag: tagId(IDS.allthemodium.vibraniumIngotTag) }
  gate.remove(event, { id: IDS.mek.allthemodiumChain.slurryDirtyFromOre })
  gate.remove(event, { id: IDS.mek.allthemodiumChain.slurryDirtyFromRawOre })
  gate.remove(event, { id: IDS.mek.allthemodiumChain.slurryDirtyFromRawBlock })
  gate.custom(event, 'confluence:bypass/allthemodium_crystal_from_ore', {
    type: 'mekanism:combining',
    main_input: { count: 1, tag: tagId(IDS.allthemodium.oreTag) },
    extra_input: vibraniumIngot,
    output: { count: 5, id: IDS.allthemodium.crystal },
  })
  gate.custom(event, 'confluence:bypass/allthemodium_crystal_from_raw_ore', {
    type: 'mekanism:combining',
    main_input: { count: 3, tag: tagId(IDS.allthemodium.rawTag) },
    extra_input: vibraniumIngot,
    output: { count: 10, id: IDS.allthemodium.crystal },
  })
  gate.custom(event, 'confluence:bypass/allthemodium_crystal_from_raw_block', {
    type: 'mekanism:combining',
    main_input: { count: 1, tag: tagId(IDS.allthemodium.rawBlockTag) },
    extra_input: vibraniumIngot,
    output: { count: 30, id: IDS.allthemodium.crystal },
  })

  // [X2.2] (D62 pattern, v0.2): the Vibranium 5x chain's three entry recipes (allthemodium:processing/vibranium/slurry/dirty/
  // {from_ore,from_raw_ore,from_raw_block}, type mekanism:dissolution; inputs c:ores/vibranium (1), c:raw_materials/vibranium (3),
  // c:storage_blocks/raw_vibranium (1); phase7-tier3-ids.md §2) become mekanism:combining recipes whose extra input is one
  // Unobtainium ingot, so the 5x route waits for [D5.2]. Same 5/10/30 crystal yields as the Allthemodium chain.
  const unobtainiumIngot = { count: 1, tag: tagId(IDS.allthemodium.unobtainiumIngotTag) }
  gate.remove(event, { id: IDS.mek.vibraniumChain.slurryDirtyFromOre })
  gate.remove(event, { id: IDS.mek.vibraniumChain.slurryDirtyFromRawOre })
  gate.remove(event, { id: IDS.mek.vibraniumChain.slurryDirtyFromRawBlock })
  gate.custom(event, 'confluence:bypass/vibranium_crystal_from_ore', {
    type: 'mekanism:combining',
    main_input: { count: 1, tag: tagId(IDS.allthemodium.vibraniumOreTag) },
    extra_input: unobtainiumIngot,
    output: { count: 5, id: IDS.allthemodium.vibraniumCrystal },
  })
  gate.custom(event, 'confluence:bypass/vibranium_crystal_from_raw_ore', {
    type: 'mekanism:combining',
    main_input: { count: 3, tag: tagId(IDS.allthemodium.vibraniumRawTag) },
    extra_input: unobtainiumIngot,
    output: { count: 10, id: IDS.allthemodium.vibraniumCrystal },
  })
  gate.custom(event, 'confluence:bypass/vibranium_crystal_from_raw_block', {
    type: 'mekanism:combining',
    main_input: { count: 1, tag: tagId(IDS.allthemodium.vibraniumRawBlockTag) },
    extra_input: unobtainiumIngot,
    output: { count: 30, id: IDS.allthemodium.vibraniumCrystal },
  })

  // [X2.2] (D125, v0.3 spec §7): the Unobtainium 5x chain's three entry recipes (type mekanism:dissolution) become
  // mekanism:combining recipes whose extra input is one Etrium ingot, so the 5x route waits for [D6.9]. Ids and item_input
  // tags/counts read from allthemodium-3.0.1_mc_1.21.1.jar!data/allthemodium/recipe/processing/unobtainium/slurry/dirty/
  // {from_ore,from_raw_ore,from_raw_block}.json: c:ores/unobtainium x1 -> 1000 mB, c:raw_materials/unobtainium x3 -> 2000 mB,
  // c:storage_blocks/raw_unobtainium x1 -> 6000 mB dirty slurry; processing/unobtainium/crystal/from_slurry.json takes 200 mB
  // per allthemodium:unobtainium_crystal, hence 5 / 10 / 30 crystals, as in the two chains above (BA §1.3).
  // No Etrium tag exists (no jar ships one; the boot's tags.json has none; BA §1.3, AA §2.3), so the extra input names the
  // item (adastra-1.21.1-1.16.25-neoforge.jar lang item.ad_astra.etrium_ingot). Item form of a combining input, from
  // Mekanism-1.21.1-10.7.19.85.jar!data/mekanism/recipe/combining/muddy_mangrove_roots.json: "extra_input":{"count":1,
  // "item":"minecraft:mud"}; kubejs-mekanism-neoforge-2101.1.7-build.18.jar!data/mekanism/kubejs/recipe_schema/combining.json
  // types extra_input as flat_sized_ingredient (NeoForge SizedIngredient.FLAT_CODEC), which reads that form.
  // Orphaned on purpose, as in the two chains above: ATM's processing/unobtainium/slurry/clean and crystal/from_slurry stay
  // registered, but no recipe makes allthemodium:dirty_unobtainium any more (boot dump), so nothing can feed them.
  const etriumIngot = { count: 1, item: IDS.adastra.etriumIngot }
  gate.remove(event, { id: IDS.mek.unobtainiumChain.slurryDirtyFromOre })
  gate.remove(event, { id: IDS.mek.unobtainiumChain.slurryDirtyFromRawOre })
  gate.remove(event, { id: IDS.mek.unobtainiumChain.slurryDirtyFromRawBlock })
  gate.custom(event, 'confluence:bypass/unobtainium_crystal_from_ore', {
    type: 'mekanism:combining',
    main_input: { count: 1, tag: tagId(IDS.allthemodium.unobtainiumOreTag) },
    extra_input: etriumIngot,
    output: { count: 5, id: IDS.allthemodium.unobtainiumCrystal },
  })
  gate.custom(event, 'confluence:bypass/unobtainium_crystal_from_raw_ore', {
    type: 'mekanism:combining',
    main_input: { count: 3, tag: tagId(IDS.allthemodium.unobtainiumRawTag) },
    extra_input: etriumIngot,
    output: { count: 10, id: IDS.allthemodium.unobtainiumCrystal },
  })
  gate.custom(event, 'confluence:bypass/unobtainium_crystal_from_raw_block', {
    type: 'mekanism:combining',
    main_input: { count: 1, tag: tagId(IDS.allthemodium.unobtainiumRawBlockTag) },
    extra_input: etriumIngot,
    output: { count: 30, id: IDS.allthemodium.unobtainiumCrystal },
  })

  // [D112c] (v0.3 spec §7 "tier ores: smelting"): the six plain-furnace recipes that turn a tier ore, or its raw drop, into an
  // ingot. The Mekanism Flamethrower in heat mode smelts the ore block where it stands, and the AE2 Entropy Manipulator smelts
  // the raw item the block drops; both look up only minecraft:smelting and check neither hardness nor tool (GAP §2.3c, §2.3d).
  // Ids and type ("type":"minecraft:smelting") from allthemodium-3.0.1_mc_1.21.1.jar!data/allthemodium/recipe/
  // {allthemodium,vibranium,unobtainium}_ingot_from_{ore,raw}_smelting.json; no other jar has a smelting recipe for these
  // ores or raw items. Kept on purpose: *_ingot_from_{ore,raw}_blasting (a blast furnace still works) and
  // *_ingot_from_dust_{smelting,blasting} (dust comes from Mekanism processing of a mined ore, never from a breaker).
  // Side effect, a change to 0.2 play that spec §7 does not list (D130): Mekanism's Energized Smelter and smelting
  // factories read the same minecraft:smelting list
  // (Mekanism-1.21.1-10.7.19.85.jar MekanismRecipeType.getRecipesUncached: RecipeManager.getAllRecipesFor(RecipeType.SMELTING);
  // TileEntityEnergizedSmelter and TileEntityItemStackToItemStackFactory use MekanismRecipeType.SMELTING), so they stop
  // cooking tier ore and raw metal too. Tier dusts still cook there through the kept *_ingot_from_dust_smelting.
  IDS.tierOres.smeltingRecipes.forEach(id => gate.remove(event, { id: id }))
})
