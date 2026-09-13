// Bypass closures for tiers 0–2 (spec §2.4). Ids in research/phase6-tier0-2-ids.md §A/§B and
// research/phase6-tier0-2-ids-2.md §A3/§M7; regex removal confirmed on 2101, syntax report §2.2.
ServerEvents.recipes(event => {
  gate.remove(event, { id: 'industrialforegoing:laser_drill_ore/ancient_debris' })   // X2.5
  gate.remove(event, { id: IDS.twilight.uncraftingTable })                          // X2.6
  gate.remove(event, { id: /^deeperdarker:.*gloomslate_.*_ore$/ })                    // [X2.2] note: no gloomslate smelting shortcut

  // [X2.2] (D62): the Allthemodium 5x chain's three entry recipes (type mekanism:dissolution, ore/raw ore/raw block ->
  // dirty slurry) are removed and re-expressed as mekanism:combining recipes whose extra input is one vibranium ingot,
  // so the 5x route cannot run before Vibranium [D3.2]. Yields are the 5x chain's, expressed as crystals.
  // Recipe ids and their c: input tags read from the installed jar:
  //   allthemodium-3.0.1_mc_1.21.1.jar!data/allthemodium/recipe/processing/allthemodium/slurry/dirty/{from_ore,
  //   from_raw_ore,from_raw_block}.json  ->  item_input tags c:ores/allthemodium (1), c:raw_materials/allthemodium (3),
  //   c:storage_blocks/raw_allthemodium (1).
  // JSON shape copied from Mekanism-1.21.1-10.7.19.85.jar!data/mekanism/recipe/combining/obsidian.json:
  //   {"type":"mekanism:combining","extra_input":{"count":1,"tag":"c:cobblestones/deepslate"},
  //    "main_input":{"count":4,"tag":"c:dusts/obsidian"},"output":{"count":1,"id":"minecraft:obsidian"}}
  // (same three keys as the KubeJS Mekanism combining schema, syntax report §5). Raw JSON tags carry no leading '#'.
  const vibranium = { count: 1, tag: tagId(IDS.allthemodium.vibraniumIngotTag) }
  gate.remove(event, { id: IDS.mek.allthemodiumChain.slurryDirtyFromOre })
  gate.remove(event, { id: IDS.mek.allthemodiumChain.slurryDirtyFromRawOre })
  gate.remove(event, { id: IDS.mek.allthemodiumChain.slurryDirtyFromRawBlock })
  gate.custom(event, 'confluence:bypass/allthemodium_crystal_from_ore', {
    type: 'mekanism:combining',
    main_input: { count: 1, tag: 'c:ores/allthemodium' },
    extra_input: vibranium,
    output: { count: 5, id: IDS.allthemodium.crystal },
  })
  gate.custom(event, 'confluence:bypass/allthemodium_crystal_from_raw_ore', {
    type: 'mekanism:combining',
    main_input: { count: 3, tag: 'c:raw_materials/allthemodium' },
    extra_input: vibranium,
    output: { count: 10, id: IDS.allthemodium.crystal },
  })
  gate.custom(event, 'confluence:bypass/allthemodium_crystal_from_raw_block', {
    type: 'mekanism:combining',
    main_input: { count: 1, tag: 'c:storage_blocks/raw_allthemodium' },
    extra_input: vibranium,
    output: { count: 30, id: IDS.allthemodium.crystal },
  })

  // [X2.2] (D62 pattern, v0.2): the Vibranium 5x chain's three entry recipes (allthemodium:processing/vibranium/slurry/dirty/
  // {from_ore,from_raw_ore,from_raw_block}, type mekanism:dissolution; inputs c:ores/vibranium (1), c:raw_materials/vibranium (3),
  // c:storage_blocks/raw_vibranium (1); phase7-tier3-ids.md §2) become mekanism:combining recipes whose extra input is one
  // Unobtainium ingot, so the 5x route waits for [D5.2]. Same 5/10/30 crystal yields as the Allthemodium chain.
  const unobtainium = { count: 1, tag: tagId(IDS.allthemodium.unobtainiumIngotTag) }
  gate.remove(event, { id: IDS.mek.vibraniumChain.slurryDirtyFromOre })
  gate.remove(event, { id: IDS.mek.vibraniumChain.slurryDirtyFromRawOre })
  gate.remove(event, { id: IDS.mek.vibraniumChain.slurryDirtyFromRawBlock })
  gate.custom(event, 'confluence:bypass/vibranium_crystal_from_ore', {
    type: 'mekanism:combining',
    main_input: { count: 1, tag: 'c:ores/vibranium' },
    extra_input: unobtainium,
    output: { count: 5, id: IDS.allthemodium.vibraniumCrystal },
  })
  gate.custom(event, 'confluence:bypass/vibranium_crystal_from_raw_ore', {
    type: 'mekanism:combining',
    main_input: { count: 3, tag: 'c:raw_materials/vibranium' },
    extra_input: unobtainium,
    output: { count: 10, id: IDS.allthemodium.vibraniumCrystal },
  })
  gate.custom(event, 'confluence:bypass/vibranium_crystal_from_raw_block', {
    type: 'mekanism:combining',
    main_input: { count: 1, tag: 'c:storage_blocks/raw_vibranium' },
    extra_input: unobtainium,
    output: { count: 30, id: IDS.allthemodium.vibraniumCrystal },
  })
})
