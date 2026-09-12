// Spec §4.2 placement table. One row → configured_feature + placed_feature + add_features modifier (D14, D58).
const PLACEMENTS = [
  // Allthemodium: Twilight Forest, cave-exposed, vein 4, 6 per chunk (ATM10's environment_scan rule)
  { path: 'allthemodium_twilight', feature: 'confluence:allthemodium_twilight', biomes: '#twilightforest:in_twilight_forest',
    size: 4, count: 6, exposed: true, min: { above_bottom: 0 }, max: { absolute: 10 },
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
]

ServerEvents.generateData('after_mods', pack => {
  PLACEMENTS.forEach(p => {
    const configured = JsonIO.toObject({
      type: 'minecraft:ore',
      config: {
        size: p.size, discard_chance_on_air_exposure: 0.0,
        targets: [
          { target: { predicate_type: 'minecraft:tag_match', tag: 'minecraft:stone_ore_replaceables' }, state: { Name: p.stone } },
          { target: { predicate_type: 'minecraft:tag_match', tag: 'minecraft:deepslate_ore_replaceables' }, state: { Name: p.deepslate } },
        ],
      },
    })
    const placement = [
      { type: 'minecraft:count', count: p.count },
      { type: 'minecraft:in_square' },
      { type: 'minecraft:height_range', height: { type: p.exposed ? 'minecraft:uniform' : 'minecraft:trapezoid', min_inclusive: p.min, max_inclusive: p.max } },
    ]
    if (p.exposed) {
      placement.push({ type: 'minecraft:environment_scan', direction_of_search: 'up',
        target_condition: { type: 'minecraft:has_sturdy_face', direction: 'down' },
        allowed_search_condition: { type: 'minecraft:matching_blocks', blocks: ['minecraft:air'] }, max_steps: 12 })
      placement.push({ type: 'minecraft:random_offset', xz_spread: 0, y_spread: -1 })
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
