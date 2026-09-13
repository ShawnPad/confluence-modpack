// Spec §4.2 placement table. One row → configured_feature + placed_feature + add_features modifier (D14, D58).
const PLACEMENTS = [
  // Allthemodium: Twilight Forest, exposed in cave floors, vein 4, 6 attempts per chunk (see the exposed branch below)
  { path: 'allthemodium_twilight', feature: 'confluence:allthemodium_twilight', biomes: '#twilightforest:in_twilight_forest',
    size: 4, count: 12, exposed: true, min: { above_bottom: 0 }, max: { absolute: 10 },
    stone: 'allthemodium:allthemodium_ore', deepslate: 'allthemodium:allthemodium_slate_ore' },
  // uraninite ×3 tiers: Mining Dimension only, buried trapezoid 65–250 (ATM10 miningDim.js counts).
  // Bare biome id, not '#allthemodium:mining_features/mining_biomes': that tag also lists The Other's six biomes
  // (jar tags/worldgen/biome/mining_features/{mining_biomes,other_features}.json; phase6-tier0-2-ids-2.md §A4).
  { path: 'uraninite_mining', feature: 'confluence:uraninite_mining', biomes: 'allthemodium:mining',
    size: 8, count: 8, exposed: false, min: { absolute: 65 }, max: { absolute: 250 },
    stone: 'powah:uraninite_ore', deepslate: 'powah:deepslate_uraninite_ore' },
  { path: 'uraninite_poor_mining', feature: 'confluence:uraninite_poor_mining', biomes: 'allthemodium:mining',
    size: 8, count: 8, exposed: false, min: { absolute: 65 }, max: { absolute: 250 },
    stone: 'powah:uraninite_ore_poor', deepslate: 'powah:deepslate_uraninite_ore_poor' },
  { path: 'uraninite_dense_mining', feature: 'confluence:uraninite_dense_mining', biomes: 'allthemodium:mining',
    size: 8, count: 4, exposed: false, min: { absolute: 65 }, max: { absolute: 250 },
    stone: 'powah:uraninite_ore_dense', deepslate: 'powah:deepslate_uraninite_ore_dense' },
  // Vibranium: Undergarden only (D3.2), cave floors like the Allthemodium row (D77). Undergarden's stones are in no vanilla
  // *_ore_replaceables tag (every installed jar checked, phase7-undergarden-worldgen-loot.md §2), so this row names the
  // mod's own tags. Which stone actually fills the y −55..−16 band, read this session from
  // The_Undergarden-1.21.1-0.9.6.jar!data/undergarden/worldgen/noise_settings/undergarden.json surface_rule: the last
  // sequence entry [14] is a dimension-wide vertical_gradient (true_at_and_below {absolute: 0},
  // false_at_and_above {absolute: 5}) turning the default depthrock into dreadrock below y = 0 — vanilla's deepslate
  // mechanic, and not something §2 saw (it read dreadrock as depths-biome-only, from entry [8]).
  // Measured, not inferred (tools/probe_worldgen.sh, y −55..−16, 16 chunks at centre 102,32 — a column whose surface
  // biomes are undergarden:icy_sea / frosty_smogstem_forest per /locate biome): 67,636 dreadrock, 0 shiverstone,
  // 0 depthrock. The band is dreadrock end to end, so only the dreadrock target fires; depthrock (above y = 5) and
  // shiverstone (entry [13], frost biomes) are inert here and kept only as insurance if the band ever moves.
  // Consequence to know: other_vibranium_ore therefore does not generate — ATM's own two Vibranium placements are
  // disabled (§5) — so Vibranium is one block in this pack. Both blocks share one loot table (§5), so which one sits
  // on which tag is cosmetic; the split is left in place for the orchestrator to keep or collapse.
  // y −55..−16 (D86): below froststeel, above the carver's lava floor at y ≤ −59 (§1). size from the Twilight row;
  // count 3, not the Twilight's 12, because Undergarden's carver leaves ~4× the cave-floor area — count 12 measured
  // 4.46 ore/chunk, count 3 measures 1.22 / 1.27 / 1.39 / 0.54 across four fresh 256-chunk squares, averaging 1.11
  // ore/chunk: the Twilight row's own figure (D77). Runs logged in research/phase7-v0.2-test-log.md §1.
  { path: 'vibranium_undergarden', feature: 'confluence:vibranium_undergarden', biomes: IDS.undergarden.biomes,
    size: 4, count: 3, exposed: true, min: { absolute: -55 }, max: { absolute: -16 },
    targets: [
      { tag: IDS.undergarden.depthrockReplaceables, block: IDS.allthemodium.vibraniumOre },
      { tag: IDS.undergarden.shiverstoneReplaceables, block: IDS.allthemodium.otherVibraniumOre },
      { tag: IDS.undergarden.dreadrockReplaceables, block: IDS.allthemodium.vibraniumOre },
    ] },
]

ServerEvents.generateData('after_mods', pack => {
  PLACEMENTS.forEach(p => {
    const configured = JsonIO.toObject({
      type: 'minecraft:ore',
      config: {
        size: p.size, discard_chance_on_air_exposure: 0.0,
        // A row may name its own stone tags (Undergarden, D86); otherwise the vanilla stone/deepslate pair.
        targets: (p.targets || [
          { tag: '#minecraft:stone_ore_replaceables', block: p.stone },
          { tag: '#minecraft:deepslate_ore_replaceables', block: p.deepslate },
        ]).map(t => ({ target: { predicate_type: 'minecraft:tag_match', tag: t.tag.slice(1) }, state: { Name: t.block } })),
      },
    })
    const placement = [
      { type: 'minecraft:count', count: p.count },
      { type: 'minecraft:in_square' },
      { type: 'minecraft:height_range', height: { type: p.exposed ? 'minecraft:uniform' : 'minecraft:trapezoid', min_inclusive: p.min, max_inclusive: p.max } },
    ]
    if (p.exposed) {
      // Cave-floor scan, the shape of ATM's own unobtainium_ore.json (D77). Not its allthemodium_ore.json ceiling
      // scan: a vanilla ore blob is centred 0–2 blocks *below* its origin (OreFeature.place, origin.y + nextInt(3) - 2),
      // so an origin under a ceiling never reaches it, and the Twilight has no noise caves — its carver caves are
      // cave_air, which ATM's `matching_blocks: [air]` rejects (probe: 0 ore in 511 fresh chunks). No random_offset:
      // the origin is the floor block itself, so the vein sits in the floor with its top layer at the cave surface.
      placement.push({ type: 'minecraft:environment_scan', direction_of_search: 'down',
        target_condition: { type: 'minecraft:has_sturdy_face', direction: 'up' },
        allowed_search_condition: { type: 'minecraft:matching_blocks', blocks: ['minecraft:air', 'minecraft:cave_air'] }, max_steps: 12 })
    }
    placement.push({ type: 'minecraft:biome' })
    const placed = JsonIO.toObject({ feature: p.feature, placement: placement })
    const modifier = JsonIO.toObject({ type: 'neoforge:add_features', biomes: p.biomes, features: [p.feature], step: 'underground_ores' })
    pack.json(`confluence:worldgen/configured_feature/${p.path}.json`, configured)
    pack.json(`confluence:worldgen/placed_feature/${p.path}.json`, placed)
    pack.json(`confluence:neoforge/biome_modifier/${p.path}.json`, modifier)
  })
  console.log('confluence worldgen: ' + PLACEMENTS.length + ' placements')
})
