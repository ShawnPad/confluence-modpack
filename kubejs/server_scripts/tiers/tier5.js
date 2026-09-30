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

// ---- Key, Supreme frame, alloys: the Key to The Other [D5.1], the Supreme Machine Frame [T5.2] and the three
// Allthemodium alloys [M5.1, X5.1, X5.2]. Spec docs/superpowers/specs/2026-09-25-v0.3-tiers-5-6-design.md §4.1, §5; D105, D114, D115.
// Report keys as lib/ids.js's v0.3 block: T5 = research/phase7-tier5-ids.md.
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
// tools/tests/test_if_dissolution_data.py checks both files against the codec before any boot. After a boot, a file the codec
// rejects shows only in logs/latest.log ("Parsing error loading recipe <id>"; net.minecraft.world.item.crafting.RecipeManager.apply):
// KubeJS's "failed recipes" count covers script recipes only, and the recipe dump is taken before any codec runs.
//
// Numbers are D115's design values: ATM10's 1,000,000,000 FE, 10,000 source and 100 mB soul lava (AllTheMods/ATM-10
// kubejs/server_scripts/modpack/atm_alloys.js at dbfd9a2, quoted in T5 §4.5), with one Piglich heart per ingot where ATM10
// uses two (D105). allthemodium:piglich_heart drops exactly one per Piglich kill, with no Looting function
// (allthemodium-3.0.1_mc_1.21.1.jar!data/allthemodium/loot_table/entities/piglich.json, T5 §4.6), and the Piglich is the only
// source (D102). Hearts on the minimum path to the end of tier 6 (spec §5): Supreme frames for the inscriber, controller,
// terminal and one crafting unit 4, NASA Workbench 1, fuel refinery 1, four rockets 4 = 10; the v1.0 catalyst adds 3.
// Soul lava (fluid allthemodium:soul_lava: allthemodium jar com/thevortex/allthemodium/registry/FluidRegistry ldc "soul_lava",
// lang fluid.allthemodium.soul_lava; T5 §4.4) exists only in The Other, in the basalt-delta soul deltas and the Piglin
// Village `prisoners` piece. It does not spread into new sources (FluidSoulLava.canConvertToSource is false); the Productive
// Bees soul lava bee renews it once a player has one bucket (T5 §4.4).
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
  // Allthemodium ingot, a Piglich heart and the four elemental essences; 10,000 source. The same five keys as tier4.js's
  // Planarium, re-read from ars_nouveau-1.21.1-5.13.1.jar!com/hollingsworth/arsnouveau/common/crafting/recipes/
  // EnchantingApparatusRecipe$Serializer: reagent Ingredient, result ItemStack, pedestalItems Ingredient.listOf() (no cap in the
  // codec; the Apparatus finds pedestals in a 7x7x7 cube, T5 §5.3), sourceCost Codec.INT, keepNbtOfReagent Codec.BOOL.
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
