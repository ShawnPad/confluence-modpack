// Spec §4.2 placement table, extended by the v0.3 spec §8 (docs/superpowers/specs/2026-09-25-v0.3-tiers-5-6-design.md).
// One row → configured_feature + placed_feature + add_features modifier (D14, D58). Optional row fields: `targets` (a row's own
// stone tags, D86), `discard` (discard_chance_on_air_exposure, default 0.0, D121). `biomes` is a biome id, a '#tag' or a list
// of biome ids; it goes into the modifier unchanged (see the modifier line below).
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
  // *_ore_replaceables tag (every installed jar checked, phase7-undergarden-worldgen-loot.md — "ug" below — §2), so this
  // row names the mod's own tags. The y −55..−16 band is dreadrock end to end: The_Undergarden-1.21.1-0.9.6.jar!data/
  // undergarden/worldgen/noise_settings/undergarden.json surface_rule entry [14] is a dimension-wide vertical_gradient
  // depthrock → dreadrock below y = 0 (measured 67,636 dreadrock / 0 shiverstone / 0 depthrock in 16 chunks,
  // research/phase7-v0.2-test-log.md §1). So allthemodium:vibranium_ore is the pack's one Vibranium block on every
  // target (D90); the depthrock and shiverstone targets are insurance if the band ever moves, and ATM's own two
  // Vibranium placements are disabled (ug §5). Band (D86): above the carver's lava floor at y ≤ −59 (ug §1), inside
  // froststeel's range (ug §6). size from the Twilight row; count 3, not 12, because Undergarden's carver leaves ~4× the
  // cave-floor area — count 12 measured 4.46 ore/chunk, count 3 averages 1.19 over five fresh 256-chunk squares, near
  // the Twilight row's 1.11 (D77). Runs logged in research/phase7-v0.2-test-log.md §1.
  { path: 'vibranium_undergarden', feature: 'confluence:vibranium_undergarden', biomes: IDS.undergarden.biomes,
    size: 4, count: 3, exposed: true, min: { absolute: -55 }, max: { absolute: -16 },
    targets: [
      { tag: IDS.undergarden.depthrockReplaceables, block: IDS.allthemodium.vibraniumOre },
      { tag: IDS.undergarden.shiverstoneReplaceables, block: IDS.allthemodium.vibraniumOre },
      { tag: IDS.undergarden.dreadrockReplaceables, block: IDS.allthemodium.vibraniumOre },
    ] },
  // ---- v0.3 rows (spec §8). OD = research/phase7-other-dimension.md, AA = research/phase7-tier6-adastra.md; jar paths below
  // are in .run/server/mods/. Probe runs: research/phase7-v0.3-test-log.md §1.
  // Unobtainium: The Other only (D5.2, D111), cave floors like the Allthemodium and Vibranium rows (D77). The Other's stone is
  // allthemodium:ancient_stone from y 8 up: allthemodium-3.0.1_mc_1.21.1.jar!data/allthemodium/worldgen/noise_settings/
  // the_other.json has default_block ancient_stone, and its surface_rule entry [1] is a dimension-wide vertical_gradient to
  // minecraft:deepslate, true at and below y 0, false at and above y 8 (OD §1). Ancient stone is in no *_ore_replaceables tag,
  // so the default stone/deepslate pair would hit only that deepslate band; the target is ATM's one-block tag
  // #allthemodium:ancient_stone (data/allthemodium/tags/block/ancient_stone.json; OD §2). ATM's own feature targets end_stone
  // (worldgen/configured_feature/unobtainium_ore.json) and stays off: kubejs/data/allthemodium/neoforge/biome_modifier/
  // allthemodium/unobtainium.json is {"type":"neoforge:none"}. Biomes: the seven in dimension/the_other.json's biome_source,
  // as a list (spec §8). '#allthemodium:other_biomes' (tags/worldgen/biome/other_biomes.json; tags.json count 7) also holds
  // these seven; the row lists them so it does not depend on ATM's tag contents (OD open question 3). Not
  // '#allthemodium:mining_features/other_features' (6 biomes, no basalt_deltas; tags.json count 6) and not
  // '#allthemodium:mining_features/mining_biomes' (adds allthemodium:mining; count 7). The Other's caves are plain
  // minecraft:air (aquifers_enabled false, default_fluid air; OD §1), which the floor scan's [air, cave_air] list accepts.
  // Band: uniform 8..128, the top of ATM's own placed_feature/unobtainium_ore.json. size 4 as the other floor rows; count
  // tuned by probe toward ~1.1 ore blocks per chunk (D111): count 16 averages 1.29 ore/chunk over three fresh 256-chunk
  // squares (research/phase7-v0.3-test-log.md §1).
  { path: 'unobtainium_other', feature: 'confluence:unobtainium_other', biomes: IDS.worldgen.otherBiomes,
    size: 4, count: 16, exposed: true, min: { absolute: 8 }, max: { absolute: 128 },
    targets: [{ tag: IDS.worldgen.ancientStone, block: IDS.allthemodium.unobtainiumOre }] },
  // Mercury and Glacio ores (kubejs/startup_scripts/items.js blocks; each drops its shard, M6.1). Ad Astra's planet stones are
  // in no vanilla *_ore_replaceables tag, so each row names Ad Astra's own tag: adastra-1.21.1-1.16.25-neoforge.jar!data/
  // ad_astra/tags/block/mercury_stone_replaceables.json = [ad_astra:mercury_stone] and glacio_stone_replaceables.json =
  // [ad_astra:glacio_stone, ad_astra:permafrost] (AA §4.3). Glacio turns to deepslate below y 8 (worldgen/noise_settings/
  // glacio.json vertical_gradient true at and below y 0, false at and above y 8; AA §4.2), so its row adds the vanilla
  // deepslate tag, Ad Astra's own glacio_* / glacio_deepslate_* split. Mercury has no deepslate layer. Biomes: each
  // dimension's whole biome_source (dimension/mercury.json: mercury_deltas; dimension/glacio.json: glacio_ice_peaks,
  // glacio_snowy_barrens; AA §4.1). discard 0.5 is Ad Astra's own planet-metal value: worldgen/configured_feature/
  // {moon_desh_ore,mars_ostrum_ore,venus_calorite_ore}.json all set "discard_chance_on_air_exposure": 0.5 (AA §4.4, D121).
  // Trapezoids with no floor scan. discard 0.5 drops each ore block that would touch air with chance 0.5 (server-1.21.1-
  // 20240808.144430-srg.jar OreFeature.canPlaceOre / shouldSkipAirCheck: nextFloat() >= chance skips the air check); vanilla
  // buried ore uses 1.0 (server-1.21.1-20240808.144430-extra.jar!data/minecraft/worldgen/configured_feature/
  // ore_diamond_buried.json; AA §4.3). Bands, size and count from spec §8.
  { path: 'mercury_ore', feature: 'confluence:mercury_ore', biomes: IDS.worldgen.mercuryBiomes,
    size: 3, count: 4, exposed: false, discard: 0.5, min: { absolute: -32 }, max: { absolute: 96 },
    targets: [{ tag: IDS.worldgen.mercuryStone, block: IDS.pack.mercuryOre }] },
  { path: 'glacio_ore', feature: 'confluence:glacio_ore', biomes: IDS.worldgen.glacioBiomes,
    size: 3, count: 4, exposed: false, discard: 0.5, min: { absolute: -48 }, max: { absolute: 64 },
    targets: [
      { tag: IDS.worldgen.glacioStone, block: IDS.pack.glacioOre },
      { tag: IDS.worldgen.deepslate, block: IDS.pack.glacioOre },
    ] },
]

ServerEvents.generateData('after_mods', pack => {
  PLACEMENTS.forEach(p => {
    const configured = JsonIO.toObject({
      type: 'minecraft:ore',
      config: {
        // discard: OreConfiguration's codec takes a float in [0, 1] (server-1.21.1-20240808.144430-srg.jar
        // net/minecraft/world/level/levelgen/feature/configurations/OreConfiguration, Codec.floatRange(0, 1) on
        // "discard_chance_on_air_exposure"). A row without `discard` keeps the 0.0 every v0.1/v0.2 row shipped with.
        size: p.size, discard_chance_on_air_exposure: p.discard === undefined ? 0.0 : p.discard,
        // A row may name its own stone tags (Undergarden, D86); otherwise the vanilla stone/deepslate pair. Tags keep the
        // leading '#' (lib/ids.js convention) so tools/check_tags.py sees them; tagId() strips it for the raw JSON.
        targets: (p.targets || [
          { tag: '#minecraft:stone_ore_replaceables', block: p.stone },
          { tag: '#minecraft:deepslate_ore_replaceables', block: p.deepslate },
        ]).map(t => ({ target: { predicate_type: 'minecraft:tag_match', tag: tagId(t.tag) }, state: { Name: t.block } })),
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
    // `biomes` passes through as the row gives it: a '#tag', one biome id or a list of ids. neoforge:add_features reads it with
    // Biome.LIST_CODEC (neoforge-21.1.250-universal.jar NeoForgeMod.lambda$static$7, fields biomes / features / step), which is
    // RegistryCodecs.homogeneousList(BIOME, DIRECT_CODEC) (server-1.21.1-20240808.144430-srg.jar Biome.<clinit> offsets 34–43).
    // That passes onlyLists = false to HolderSetCodec.create, whose homogenousList takes a list or a single element
    // (neoforge-21.1.250-server.jar net/minecraft/resources/HolderSetCodec). A shipped list: Oh-The-Biomes-Weve-Gone-NeoForge-
    // 2.6.0.jar!data/biomeswevegone/neoforge/biome_modifier/vanilla/flower_plains.json ("biomes": ["minecraft:plains", …]).
    const modifier = JsonIO.toObject({ type: 'neoforge:add_features', biomes: p.biomes, features: [p.feature], step: 'underground_ores' })
    pack.json(`confluence:worldgen/configured_feature/${p.path}.json`, configured)
    pack.json(`confluence:worldgen/placed_feature/${p.path}.json`, placed)
    pack.json(`confluence:neoforge/biome_modifier/${p.path}.json`, modifier)
  })
  console.log('confluence worldgen: ' + PLACEMENTS.length + ' placements')
})
