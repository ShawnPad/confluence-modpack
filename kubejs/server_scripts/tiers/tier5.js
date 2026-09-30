// Tier 5 — The Other (v0.3 spec, docs/superpowers/specs/2026-09-25-v0.3-tiers-5-6-design.md §5). Ids: lib/ids.js, v0.3 block.
// Report keys as in the spec: T5 = research/phase7-tier5-ids.md, AE2 = phase7-ae2-ids.md, OD = phase7-other-dimension.md,
// BA = phase7-tier5-6-bypass-audit.md. Each group of rows is its own recipes-event handler under a '// ----' heading; KubeJS
// runs every handler registered for the event, in script load order (EventHandlerContainer.add/handle, as dump.js cites). No
// top-level const or function in this file: all server scripts share one scope (HANDOFF §6). Later tasks count the handlers
// with grep -c '^ServerEvents\.recipes(', so each handler begins its line with that call and no other line may.

// ---- Mekanism: T5.1 ultimate control circuit, X5.3 Digital Miner.
ServerEvents.recipes(event => {
  // T5.1 (D104): both default producers go, by id. They are the only two recipes in the 118 jars that output the circuit
  // (Mekanism-1.21.1-10.7.19.85.jar!data/mekanism/recipe/control_circuit/ultimate.json, crafting ACA = 2 atomic alloy + 1 elite
  // circuit; control_circuit/infused_ultimate.json, Metallurgic Infuser, 240 mB refined obsidian + 1 elite circuit; T5 §1.1).
  // Ours: EAE/UTU/EAE = four elite circuits (each already costs an Allthemodium ingot, tier3.js T3.2), two atomic alloys, two
  // Unobtainium ingots and one Wilden Tribute (one per Wilden Chimera kill, T5 §5.1) -> four circuits.
  // Item.of(id, 4): kubejs-neoforge-2101.7.2-build.377.jar ItemWrapper.of(ItemStack, int) returns kjs$withCount(4), a copy with count 4.
  IDS.mek.ultimateCircuitRecipes.forEach(id => gate.remove(event, { id: id }))
  gate.shaped(event, 'confluence:tier5/ultimate_control_circuit', Item.of(IDS.mek.ultimateCircuit, 4), ['EAE', 'UTU', 'EAE'],
    { E: IDS.mek.eliteCircuitTag, A: IDS.mek.atomicAlloyTag, U: IDS.allthemodium.unobtainiumIngotTag, T: IDS.ars.wildenTribute })

  // X5.3 (D116): a pacing gate, not a bypass closure; the Miner already skips blocks with hardness below 0 (OD Q4, BA §3.1).
  // Default Mekanism-1.21.1-10.7.19.85.jar!data/mekanism/recipe/digital_miner.json (T5 §1.3): mekanism:mek_data, ACA/SRS/TXT,
  // every cell filled. Type, pattern and every other key kept; C, the basic circuit, becomes the ultimate circuit (which already
  // carries the Unobtainium). Removed by id; mek_data stays raw JSON (D87, as tier3.js's drive array).
  gate.remove(event, { id: IDS.mek.digitalMiner })
  gate.custom(event, 'confluence:tier5/digital_miner', {
    type: IDS.mek.mekDataType, category: 'misc',
    key: { A: { tag: tagId(IDS.mek.atomicAlloyTag) }, C: { tag: tagId(IDS.mek.ultimateCircuitTag) }, R: { item: IDS.mek.robit },
           S: { item: IDS.mek.logisticalSorter }, T: { item: IDS.mek.teleportationCore }, X: { item: IDS.mek.steelCasing } },
    pattern: ['ACA', 'SRS', 'TXT'],
    result: { count: 1, id: IDS.mek.digitalMiner },
  })
})

// ---- Key, Supreme frame, alloys: D5.1 key (spec §4.1), T5.2 Supreme Machine Frame, M5.1 X5.1 X5.2 alloys; D105, D114, D115.
//
// Two of the five recipes are datapack JSON, not code (IF machine recipes are data, D31; the v0.2 T4.1 pattern):
//  - T5.2 kubejs/data/industrialforegoing/recipe/dissolution_chamber/supreme_machine_frame.json replaces IF's default at its
//    own id (industrialforegoing-1.21-3.6.39.jar!data/industrialforegoing/recipe/dissolution_chamber/supreme_machine_frame.json,
//    T5 §3.1): the two netherite ingots become two Unobtainium ingots, and the diamond gem, diamond gear and diamond gem become
//    a nitro crystal, an ultimate control circuit and an Unobtainium-Allthemodium alloy ingot. That is 8 items, the codec's
//    maximum (DissolutionChamberRecipe: `input` is Ingredient.CODEC.listOf(0, 8), T5 §3.2), hence one nitro, not two (D114).
//    The 135 mB of ether gas, the 300 ticks and IF's neoforge:item_exists condition stay.
//  - X5.2 kubejs/data/confluence/recipe/tier5/unobtainium_vibranium_alloy_ingot.json (id confluence:tier5/unobtainium_vibranium_alloy_ingot):
//    four industrialforegoing:pink_slime items, a Vibranium ingot, an Unobtainium ingot and a Piglich heart in the Dissolution
//    Chamber with 100 mB of allthemodium:soul_lava, 200 ticks. The chamber's input tank has no fluid validator (T5 §3.2-3.3).
// Both files are checked before any boot by tools/tests/test_if_dissolution_data.py; its docstring says what a boot can show.
//
// Numbers are D115's design values: ATM10's 1,000,000,000 FE, 10,000 source and 100 mB soul lava (AllTheMods/ATM-10
// kubejs/server_scripts/modpack/atm_alloys.js at dbfd9a2, quoted in T5 §4.5), with one Piglich heart per ingot where ATM10
// uses two (D105). allthemodium:piglich_heart drops exactly one per Piglich kill, with no Looting function
// (allthemodium-3.0.1_mc_1.21.1.jar!data/allthemodium/loot_table/entities/piglich.json, T5 §4.6), and the Piglich is the only
// source (D102). Heart budget: spec §5 with its §14 erratum. The trunk questline takes 10, because quest S5.2 asks for an ME
// controller (§9.1); the gating minimum is 9, because nothing consumes the controller (D117). The v1.0 catalyst adds 3.
// Soul lava (fluid allthemodium:soul_lava: allthemodium jar com/thevortex/allthemodium/registry/FluidRegistry ldc "soul_lava",
// lang fluid.allthemodium.soul_lava; T5 §4.4) is bucketable only from The Other's basalt-delta soul deltas and the Piglin
// Village `prisoners` piece; the `forge` and `mob_forge` templates hold falling flow, which gives no bucket. It does not
// spread into new sources (FluidSoulLava.canConvertToSource is false); the Productive Bees soul lava bee renews it once a
// player has one bucket (T5 §4.4).
//
// Nothing is removed. No loaded recipe makes the key or any alloy ingot except Allthemodium's 9-from-1 block recipes
// (allthemodium:*_alloy_ingot_from_block), which stay; the jar's tconstruct casting recipes drop at load because Tinkers is not
// installed (T5 §4.3; the 0.2.1 boot dump has no other maker). So every call below is add-only, and gate.custom is called
// WITHOUT its `output` argument: with one it would remove every recipe producing the alloy, the block recipe included.
ServerEvents.recipes(event => {
  // D5.1 Key to The Other (spec §4.1; pack spec §2.7 cost rule: keys cost one of each input). kubejs:other_key is a pack item
  // (startup_scripts/items.js) and no recipe makes it (0.2.1 boot dump), so this adds without removing.
  gate.shaped(event, 'confluence:tier5/other_key', IDS.pack.otherKey,
    [' E ', 'VFB', ' D '], { E: IDS.pack.endFocus, V: IDS.allthemodium.vibraniumIngotTag, F: IDS.ifg.advancedFrameTag,
      B: IDS.bumblezone.essence, D: IDS.vanilla.dragonEgg })

  // M5.1 Unobtainium-Allthemodium alloy ingot in the Ars Enchanting Apparatus: reagent an Unobtainium ingot; six pedestals, an
  // Allthemodium ingot, a Piglich heart and the four elemental essences; 10,000 source. The five codec fields plus `type`, as
  // tier4.js's Planarium, re-read from ars_nouveau-1.21.1-5.13.1.jar!com/hollingsworth/arsnouveau/common/crafting/recipes/
  // EnchantingApparatusRecipe$Serializer: reagent Ingredient.CODEC, result ItemStack.CODEC, pedestalItems
  // Ingredient.CODEC.listOf() (no cap in the codec; the Apparatus finds pedestals in a 7x7x7 cube, T5 §5.3), sourceCost
  // Codec.INT, keepNbtOfReagent Codec.BOOL.
  gate.custom(event, 'confluence:tier5/unobtainium_allthemodium_alloy_ingot', {
    type: IDS.ars.apparatusType, keepNbtOfReagent: false, sourceCost: 10000,
    reagent: { tag: tagId(IDS.allthemodium.unobtainiumIngotTag) },
    pedestalItems: [{ tag: tagId(IDS.allthemodium.ingot) }, { item: IDS.allthemodium.piglichHeart }]
      .concat(IDS.ars.essences.map(e => ({ item: e }))),
    result: { count: 1, id: IDS.allthemodium.unobAtmAlloy },
  })

  // X5.1 Vibranium-Allthemodium alloy ingot on the Energizing Orb: an Allthemodium ingot, a Vibranium ingot, a Piglich heart
  // and a Block of Nitro Crystal (4 of the orb's 6 input slots, T5 §2.1); 1,000,000,000 FE. Keys as tier3.js's nitro crystal.
  // Powah-6.2.10.jar!owmii/powah/block/energizing/EnergizingRecipe: `energy` is Codec.LONG into a `private final long energy`,
  // `ingredients` Ingredient.LIST_CODEC_NONEMPTY, `result` ItemStack.CODEC. 1e9 is below 2^31, so it takes the same path as the
  // 20,000,000 FE confluence:tier3/crystal_nitro; the boot dump's JSON shows the value.
  // One nitro rod (200,000 FE/t) fills it in 5,000 ticks plus a 20-tick warm-up, about 4 min 11 s; eight rods about 32 s (T5 §2.3).
  gate.custom(event, 'confluence:tier5/vibranium_allthemodium_alloy_ingot', {
    type: IDS.powah.energizingType, energy: 1000000000,
    ingredients: [
      { tag: tagId(IDS.allthemodium.ingot) }, { tag: tagId(IDS.allthemodium.vibraniumIngotTag) },
      { item: IDS.allthemodium.piglichHeart }, { item: IDS.powah.nitroBlock },
    ],
    result: { count: 1, id: IDS.allthemodium.vibAtmAlloy },
  })
})

// ---- AE2, tier 5 (v0.3 Task 7; spec §5 S5.1–S5.3, D107, D117). Shapes: OSR2 1.7.1 crafting.js as quoted in
// research/phase7-ae2-ids.md §3; AE2 defaults: appliedenergistics2-19.2.17.jar!data/ae2/recipe/network/** (AE2 §1.2).
// Every default is removed BY ID (IDS.ae2.recipes). A scan of every jar's data/*/recipe/** and the boot dump found exactly one
// recipe outputting each of these seven items, and the id is what tools/gates.yaml asserts; the buses and the terminal are
// cable parts, which the dump prints as 'PartItem[...]', not as item ids (AE2 §4.5).
ServerEvents.recipes(event => {
  // S5.1 Inscriber (OSR2 crafting.js lines 4130–4145): AE2's default aba / c a / aba has iron ×5, piston ×2 and copper ×1.
  // OSR2 turns the four corner irons into HDPE sheets and the middle-right iron into a second copper, and puts the Supreme
  // frame in the default's empty centre (D107); the two pistons stay. HDPE is named by item: no tag holds it (AE2 §5).
  gate.remove(event, { id: IDS.ae2.recipes.inscriber })
  gate.shaped(event, 'confluence:tier5/inscriber', IDS.ae2.inscriber, ['ABA', 'CDC', 'ABA'],
    { A: IDS.mek.hdpeSheet, B: IDS.vanilla.piston, C: IDS.vanilla.copperIngotTag, D: IDS.ifg.supremeFrameTag })

  // S5.1 Charger (OSR2 lines 3141–3154): knightmetal ×5 where the default has iron. OSR2's Ender IO copper alloy is not in the
  // pack, so the default's copper ×2 stays. The two empty cells are the default's own: vanilla's ShapedRecipePattern codec
  // (which kubejs:shaped uses) takes rows of equal width with spaces, as it does for AE2's own 'a  ' row.
  gate.remove(event, { id: IDS.ae2.recipes.charger })
  gate.shaped(event, 'confluence:tier5/charger', IDS.ae2.charger, ['ABA', 'A  ', 'ABA'],
    { A: IDS.twilight.knightmetal, B: IDS.vanilla.copperIngotTag })

  // S5.2 ME Controller (OSR2 lines 4147–4164): one forgotten ingot (B occurs once), the Supreme frame in the centre, Tom's
  // inventory connector bottom centre. A scale gate, not an entry gate: networks of up to 8 channels run without it (D117, AE2 §4.4).
  gate.remove(event, { id: IDS.ae2.recipes.controller })
  gate.shaped(event, 'confluence:tier5/controller', IDS.ae2.controller, ['ABA', 'CDC', 'EFE'],
    { A: IDS.ae2.fluixCrystal, B: IDS.undergarden.forgottenIngot, C: IDS.ae2.engineeringProcessor, D: IDS.ifg.supremeFrameTag,
      E: IDS.ae2.skyStoneBlock, F: IDS.toms.inventoryConnector })

  // S5.3 ME Drive (OSR2 lines 3242–3257): the QIO drive array fills the default's empty centre (D107). OSR2's aluminium is not in
  // the pack, so the default's iron ×4 stays.
  gate.remove(event, { id: IDS.ae2.recipes.drive })
  gate.shaped(event, 'confluence:tier5/drive', IDS.ae2.drive, ['ABA', 'CDC', 'ABA'],
    { A: IDS.vanilla.ironIngotTag, B: IDS.ae2.engineeringProcessor, C: IDS.ae2.fluixGlassCable, D: IDS.mek.qioDriveArray })

  // S5.3 Import / export bus (OSR2 lines 3208–3240): the QIO importer / exporter over the annihilation / formation core, a piston
  // between two metals. OSR2's zinc is not in the pack, so the default's iron ×2 stays.
  gate.remove(event, { id: IDS.ae2.recipes.importBus })
  gate.shaped(event, 'confluence:tier5/import_bus', IDS.ae2.importBus, [' A ', ' B ', 'CDC'],
    { A: IDS.mek.qioImporter, B: IDS.ae2.annihilationCore, C: IDS.vanilla.ironIngotTag, D: IDS.vanilla.piston })
  gate.remove(event, { id: IDS.ae2.recipes.exportBus })
  gate.shaped(event, 'confluence:tier5/export_bus', IDS.ae2.exportBus, [' A ', ' B ', 'CDC'],
    { A: IDS.mek.qioExporter, B: IDS.ae2.formationCore, C: IDS.vanilla.ironIngotTag, D: IDS.vanilla.piston })

  // S5.3 ME Terminal (OSR2 lines 4166–4183): AE2's shapeless default (formation core, any #ae2:illuminated_panel, logic processor,
  // annihilation core) becomes OSR2's shaped recipe: the Illuminated Panel item ae2:semi_dark_monitor, the Supreme frame, a second
  // logic processor and the QIO dashboard, which already contains Tom's crafting terminal (tier3.js). The crafting terminal, the
  // wireless terminal and the ME chest consume the terminal; the pattern encoding terminal and the wireless crafting terminal
  // consume the crafting terminal (AE2 §4.1). So all of them wait for it.
  gate.remove(event, { id: IDS.ae2.recipes.terminal })
  gate.shaped(event, 'confluence:tier5/terminal', IDS.ae2.terminal, [' A ', 'BCD', 'EFE'],
    { A: IDS.ae2.illuminatedPanel, B: IDS.ae2.formationCore, C: IDS.ifg.supremeFrameTag, D: IDS.ae2.annihilationCore,
      E: IDS.ae2.logicProcessor, F: IDS.mek.qioDashboard })
})
