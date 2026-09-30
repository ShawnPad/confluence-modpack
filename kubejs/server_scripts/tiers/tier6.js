// Tier 6 — Space (v0.3 spec, docs/superpowers/specs/2026-09-25-v0.3-tiers-5-6-design.md §6; D107, D117–D120, D123). Ids:
// lib/ids.js, v0.3 block. Report keys as in the spec: AA = research/phase7-tier6-adastra.md, AE2 = phase7-ae2-ids.md,
// SS = phase7-soulshard-essence.md, GAP = phase7-v0.3-gaps.md. Each group of rows is its own recipes-event handler under a
// '// ----' heading: Space (plan Task 6) first, then AE2 S6.1–S6.2 (Task 7). KubeJS runs every handler registered for the
// event, in script load order (EventHandlerContainer.add/handle, as dump.js cites); the two handlers touch disjoint ids, so
// neither depends on order. No top-level const or function in this file: all server scripts share one scope (HANDOFF §6).
// Keep each handler's call at column 0 and no other line may begin with it, so an anchored grep -c '^ServerEvents\.recipes('
// counts the handlers (the tier5.js convention).

// ---- Space: D6.1, D6.3, T6.1, T6.2, D6.9, M6.1 (plan Task 6)
ServerEvents.recipes(event => {
  // The five Ad Astra machines below each have exactly one recipe (minecraft:crafting_shaped, recipe id = item id), and no
  // other data/*/recipe/** file in any of the 118 jars has one of these items as its result (v0.3 plan Task 6 Fact 2). So
  // replaceShaped (remove by output) removes only Ad Astra's own recipe. Each pattern is the default
  // (adastra-1.21.1-1.16.25-neoforge.jar!data/ad_astra/recipe/<item>.json, quoted in AA §1.1–1.4) with only the spec's slot
  // changes. All five fill the 3x3 grid, so the load-time trim of empty edge rows and columns changes nothing: kubejs:shaped
  // decodes through vanilla's ShapedRecipePattern.MAP_CODEC (ShapedKubeJSRecipe$SerializerKJS,
  // kubejs-neoforge-2101.7.2-build.377.jar), whose unpack calls shrink (net.minecraft.world.item.crafting.ShapedRecipePattern,
  // server-1.21.1-20240808.144430-srg.jar).
  // The kubejs:shaped serializer and the category these recipes omit: see the note in tiers/tier3.js's v0.3 D113 block.

  // D6.1 NASA Workbench. Default |#| / TCT / #B# (| = #ad_astra:iron_rods, T = minecraft:redstone_torch). The four gate
  // items take the two iron-rod and two torch slots (AA §1.8, option a): X ultimate circuit, Y Unobtainium-Allthemodium alloy
  // ingot, Z Unobtainium block, W Unrealium ingot (Eternal Starlight, D123). The steel plates, table and steel block stay.
  gate.replaceShaped(event, 'confluence:tier6/nasa_workbench', IDS.adastra.nasaWorkbench,
    ['X#Y', 'ZCW', '#B#'], { X: IDS.mek.ultimateCircuit, Y: IDS.allthemodium.unobAtmAlloy, Z: IDS.allthemodium.unobtainiumBlockTag,
      W: IDS.starlight.unrealiumIngotTag, '#': IDS.adastra.steelPlateTag, C: IDS.vanilla.craftingTable, B: IDS.adastra.steelBlockTag })

  // D6.3 Space suit (the chest piece). Default '# #' / TOT / #W#: the elytra fills the empty top-middle (D107, empty-slot rule).
  gate.replaceShaped(event, 'confluence:tier6/space_suit', IDS.adastra.spaceSuit,
    ['#E#', 'TOT', '#W#'], { '#': IDS.adastra.steelPlateTag, E: IDS.vanilla.elytra, T: IDS.adastra.gasTank, O: IDS.adastra.oxygenGear,
      W: IDS.vanilla.woolTag })
  // D6.3 Oxygen loader. Default #F# / G|G / #R# has no empty slot: Mekanism's electric pump replaces the redstone block R.
  gate.replaceShaped(event, 'confluence:tier6/oxygen_loader', IDS.adastra.oxygenLoader,
    ['#F#', 'G|G', '#P#'], { '#': IDS.adastra.steelPlateTag, F: IDS.adastra.fan, G: IDS.adastra.gasTank, '|': IDS.vanilla.lightningRod,
      P: IDS.mek.electricPump })

  // T6.1 Fuel refinery. Default ### / BFB / ### has no empty slot: the six steel plates are the replaced fillers. The four Ars
  // essences are four item slots (a air, e earth, w water, f fire), because one #confluence:ars_essences slot would accept any
  // single essence (AA §1.8); plus C ultimate circuit and V Vibranium-Allthemodium alloy ingot. Buckets and furnace stay.
  gate.replaceShaped(event, 'confluence:tier6/fuel_refinery', IDS.adastra.fuelRefinery,
    ['aCe', 'BFB', 'wVf'], { a: IDS.ars.airEssence, e: IDS.ars.earthEssence, w: IDS.ars.waterEssence, f: IDS.ars.fireEssence,
      C: IDS.mek.ultimateCircuit, V: IDS.allthemodium.vibAtmAlloy, B: IDS.vanilla.bucket, F: IDS.vanilla.furnace })

  // T6.2 Steel engine, the only engine that carries tier-6 gate items (D118). Default ### / #E# / ' F ': the nitro crystal N
  // replaces the top-middle plate, and the ultimate circuit C and Unobtainium-Vibranium alloy ingot A fill the two empty bottom
  // corners (D107). The desh, ostrum and calorite engines stay default: each takes the previous engine as its E key (AA §1.4),
  // so all three inherit this gate by nesting.
  gate.replaceShaped(event, 'confluence:tier6/steel_engine', IDS.adastra.steelEngine,
    ['#N#', '#E#', 'CFA'], { '#': IDS.adastra.steelPlateTag, N: IDS.powah.nitro, E: IDS.adastra.engineFrame, F: IDS.adastra.fan,
      C: IDS.mek.ultimateCircuit, A: IDS.allthemodium.unobVibAlloy })

  // D6.2 unchanged (D118): the four rockets (ad_astra:nasa_workbench/tier_{1,2,3,4}_rocket_from_nasa_workbench) and the launch
  // pad (ad_astra:launch_pad) keep their default recipes. A rocket recipe uses all 14 positional inputs, so it has no spare
  // slot (AA §1.5). Ad Astra's atmosphereLeave config stays at its default 600 (GAP §1); the pack ships no Ad Astra config.

  // D6.9 Etrium (D119). No recipe in any jar makes Etrium and no Etrium tag exists (AA §2.3), so both recipes name the item.
  // ad_astra:alloying runs only in the Etrionic Blast Furnace, and every ingredient consumes exactly one item; matches() checks
  // at most four ingredients (AA §2.1), so this recipe has four. Field names: the jar's only alloying recipe
  // (recipe/alloying/steel_ingot_from_alloying_iron_ingot_and_barrier.json) and AlloyingRecipe's codec (cookingtime, energy,
  // ingredients, result; earth/terrarium/adastra/common/recipes/machines/AlloyingRecipe.class). Numbers (cookingtime 200,
  // energy 40): spec §6 D6.9, not the jar recipe's (100, 20).
  gate.custom(event, 'confluence:tier6/etrium_ingot', {
    type: IDS.adastra.alloyingType, cookingtime: 200, energy: 40,
    ingredients: [{ tag: tagId(IDS.adastra.deshIngotTag) }, { tag: tagId(IDS.adastra.ostrumIngotTag) },
                  { tag: tagId(IDS.adastra.caloriteIngotTag) }, { item: IDS.adastra.iceShard }],
    result: { count: 1, id: IDS.adastra.etriumIngot },
  })
  // Etrium plate. ad_astra:compressing takes one `ingredient` (singular; CompressingRecipe's codec). The numbers are the
  // desh plate's (recipe/compressing/desh_plate_from_compressing_desh_ingots.json: cookingtime 100, energy 20, count 1).
  gate.custom(event, 'confluence:tier6/etrium_plate', {
    type: IDS.adastra.compressingType, cookingtime: 100, energy: 20,
    ingredient: { item: IDS.adastra.etriumIngot },
    result: { count: 1, id: IDS.adastra.etriumPlate },
  })

  // M6.1 Astral Focus (D120): reagent an Etrium ingot; pedestals one divine soulshard (one per Echo of Tyros kill, SS §1.2) and
  // the two planet shards (kubejs/startup_scripts/items.js; the drops of kubejs:mercury_ore and kubejs:glacio_ore). sourceCost 0:
  // the gate is the ingredients. The same six keys as tier4.js's End Focus
  // (ars_nouveau-1.21.1-5.13.1.jar!data/ars_nouveau/recipe/planarium.json).
  gate.custom(event, 'confluence:tier6/astral_focus', {
    type: IDS.ars.apparatusType, keepNbtOfReagent: false, sourceCost: 0,
    reagent: { item: IDS.adastra.etriumIngot },
    pedestalItems: [{ item: IDS.irons.divineSoulshard }, { item: IDS.pack.mercuryShard }, { item: IDS.pack.glacioShard }],
    result: { count: 1, id: IDS.pack.astralFocus },
  })
})

// ---- AE2, tier 6 (v0.3 Task 7; spec §6 S6.1–S6.2, D107, D117). Shapes: research/phase7-ae2-ids.md §3 (OSR2 1.7.1) and §1.2
// (appliedenergistics2-19.2.17.jar defaults). Removed BY ID (IDS.ae2.recipes), as in tier5.js.
ServerEvents.recipes(event => {
  // S6.1 Wireless Receiver (OSR2 crafting.js lines 5635–5649): desh ×3 where the default has iron. The access point and both
  // wireless terminals consume the receiver (AE2 §4.1), so they wait for Moon desh.
  gate.remove(event, { id: IDS.ae2.recipes.wirelessReceiver })
  gate.shaped(event, 'confluence:tier6/wireless_receiver', IDS.ae2.wirelessReceiver, [' A ', 'BCB', ' B '],
    { A: IDS.ae2.fluixPearl, B: IDS.adastra.deshIngotTag, C: IDS.ae2.quartzFiber })

  // S6.2 Crafting Unit (OSR2 expert_crafting.js lines 1636–1652) with one ostrum ingot in place of one of its two fluix glass
  // cables (D117; pack spec §2.7, one gate item per replaced filler). Every crafting CPU consumes a unit (research/
  // phase7-v0.3-gaps.md §3.2), so ostrum gates network autocrafting. The mirror image also crafts: vanilla ShapedRecipePattern.matches
  // tries the mirrored grid, then the plain one (server-1.21.1-20240808.144430-srg.jar).
  gate.remove(event, { id: IDS.ae2.recipes.craftingUnit })
  gate.shaped(event, 'confluence:tier6/crafting_unit', IDS.ae2.craftingUnit, ['ABA', 'CDF', 'AEA'],
    { A: IDS.ae2.fluixCrystal, B: IDS.ae2.calculationProcessor, C: IDS.adastra.ostrumIngotTag, D: IDS.ifg.supremeFrameTag,
      E: IDS.ae2.logicProcessor, F: IDS.ae2.fluixGlassCable })

  // S6.2 Pattern Provider: AE2's default aba / c d / aba with an ostrum ingot in the empty centre (D107). Only
  // ae2:network/blocks/pattern_providers_interface is removed, so the part <-> block conversions ..._interface_alt and
  // ..._interface_part survive (AE2 §4.5; removing by output would take _alt with it).
  gate.remove(event, { id: IDS.ae2.recipes.patternProvider })
  gate.shaped(event, 'confluence:tier6/pattern_provider', IDS.ae2.patternProvider, ['ABA', 'COD', 'ABA'],
    { A: IDS.vanilla.ironIngotTag, B: IDS.vanilla.craftingTable, C: IDS.ae2.annihilationCore, D: IDS.ae2.formationCore,
      O: IDS.adastra.ostrumIngotTag })

  // S6.2 Molecular Assembler and Pattern Encoding Terminal: unchanged (D117; OSR2 leaves both alone, AE2 §3). A lone assembler with
  // a hand-placed pattern automates one recipe from tier 5 (research/phase7-v0.3-gaps.md §3.1).
})
