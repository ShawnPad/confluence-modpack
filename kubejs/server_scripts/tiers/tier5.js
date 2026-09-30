// Tier 5 — The Other (v0.3 spec, docs/superpowers/specs/2026-09-25-v0.3-tiers-5-6-design.md §5). Ids: lib/ids.js, v0.3 block.
// Report keys as in the spec: T5 = research/phase7-tier5-ids.md, AE2 = phase7-ae2-ids.md, OD = phase7-other-dimension.md,
// BA = phase7-tier5-6-bypass-audit.md. Each group of rows is its own recipes-event handler under a '// ----' heading; KubeJS
// runs every handler registered for the event, in script load order. No top-level const or function in this file: all server
// scripts share one scope (HANDOFF §6). This comment must not spell out the event call: later tasks count the handlers with grep.

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
