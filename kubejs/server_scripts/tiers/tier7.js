// Tier 7 — the catalyst (v1.0 spec, docs/superpowers/specs/2026-11-11-v1.0-catalyst-tier-design.md §3; D143, D144, A1–A10).
// Ids: lib/ids.js, v1.0 block (IDS.top) and the older blocks. CT = research/phase7-v1.0-catalyst-tier.md. Each group of rows is
// its own recipes-event handler under a '// ----' heading: X7.1 (plan Task 4), X7.2–X7.7 (Task 5), the X7.8 grid rows (Task 6).
// The Infinity Drill is a datapack override, not a script (Task 7). KubeJS runs every handler registered for the event, in script
// load order; the handlers touch disjoint ids, so none depends on order. No top-level const or function in this file: all server
// scripts share one scope (HANDOFF §6). Each handler's call starts at column 0 and no other line starts with it, so
// grep -c '^ServerEvents\.recipes(' counts the handlers (the tier5.js convention). tools/tests/test_tier7.py pins every row.

// ---- X7.1 Confluence Catalyst (plan Task 4)
ServerEvents.recipes(event => {
  // Reagent the Astral Focus; seven pedestals; source 0, as tier6.js's Astral Focus: the gate is the ingredients (A2; CT §1.1–1.4;
  // D84, D120). Seven stays inside the eight pedestals the pack already ships (CT §1.4). Add-only: no `output` argument, so
  // gate.custom removes nothing (the catalyst has no recipe, CT §1.2).
  gate.custom(event, 'confluence:tier7/confluence_catalyst', {
    type: IDS.ars.apparatusType, keepNbtOfReagent: false, sourceCost: 0,
    reagent: { item: IDS.pack.astralFocus },
    pedestalItems: [{ item: IDS.adastra.etriumIngot }, { item: IDS.allthemodium.vibAtmAlloy }, { item: IDS.allthemodium.unobAtmAlloy },
      { item: IDS.allthemodium.unobVibAlloy }, { item: IDS.vanilla.dragonEgg }, { item: IDS.ae2.wirelessReceiver },
      { item: IDS.ae2.craftingUnit }],
    result: { count: 1, id: IDS.pack.catalyst },
  })
})

// ---- X7.2–X7.7 creative items (plan Task 5)
// Spec §3.2: shapeless, the family's top non-creative item + one catalyst, add-only (CT §4: no creative item has a survival route,
// so nothing is removed; tools/gates.yaml sole_producers pins each to this one recipe). A3: event.shapeless drops the Mekanism
// cube's and tank's mekanism:mek_data, so stored energy or chemical is not carried over. A4: only the tree's two Mekanism items.
ServerEvents.recipes(event => {
  gate.shapeless(event, 'confluence:tier7/creative_energy_cube', IDS.top.creativeEnergyCube, [IDS.top.ultimateEnergyCube, IDS.pack.catalyst])
  gate.shapeless(event, 'confluence:tier7/creative_chemical_tank', IDS.top.creativeChemicalTank, [IDS.top.ultimateChemicalTank, IDS.pack.catalyst])
  gate.shapeless(event, 'confluence:tier7/creative_energy_cell', IDS.top.creativeEnergyCell, [IDS.top.denseEnergyCell, IDS.pack.catalyst])
  gate.shapeless(event, 'confluence:tier7/energy_cell_creative', IDS.top.creativeCell, [IDS.top.nitroCell, IDS.pack.catalyst])
  gate.shapeless(event, 'confluence:tier7/creative_source_jar', IDS.top.creativeSourceJar, [IDS.top.sourceJar, IDS.pack.catalyst])
  gate.shapeless(event, 'confluence:tier7/creative_essence', IDS.top.creativeEssence, [IDS.top.awakenedSupremiumEssence, IDS.pack.catalyst])
  gate.shapeless(event, 'confluence:tier7/creative_vending_upgrade', IDS.top.creativeVendingUpgrade, [IDS.fs.netheriteUpgrade, IDS.pack.catalyst])
})

// ---- X7.8 crafting-grid rows (plan Task 6)
// Spec §3.3–3.5, 3.7, 3.8 (D144). Each replaced default is removed BY ID, then ours is added (tier6.js's AE2 block). A shaped
// default that fills the grid gives one filler slot to the catalyst (A5, A9; pack spec §2.7, D107); a default with an empty slot
// gets the catalyst there (A7). Defaults read at plan time (v1.0 plan Task 4 table). The jet suit's helmet, pants and boots keep
// their defaults (D144). The Infinity Drill is the datapack override of plan Task 7.
ServerEvents.recipes(event => {
  // Ancient Codex. Default TNT / BRB / TLT (irons_spellbooks-1.21.1-3.16.3.jar!data/irons_spellbooks/recipe/
  // netherite_spell_book.json): the catalyst K replaces the top-left magic cloth (A5).
  gate.remove(event, { id: IDS.top.codexRecipe })
  gate.shaped(event, 'confluence:tier7/netherite_spell_book', IDS.top.codex, ['KNT', 'BRB', 'TLT'], { K: IDS.pack.catalyst,
    N: IDS.vanilla.netheriteIngotTag, T: IDS.top.magicCloth, B: IDS.top.bloodVial, R: IDS.top.ruinedBook, L: IDS.top.lightningBottle })

  // Advanced Wireless Terminal. Default minecraft:smithing_transform (one addition slot): replaced by a shapeless craft of the
  // smithing inputs plus the catalyst (A6). A shapeless craft does not copy the base's components; the base is a fresh tier-0
  // item (spec §10 item 3, P7.10 reads the crafted item).
  gate.remove(event, { id: IDS.top.advWirelessTerminalRecipe })
  gate.shapeless(event, 'confluence:tier7/adv_wireless_terminal', IDS.top.advWirelessTerminal,
    [IDS.top.wirelessTerminal, IDS.vanilla.netheriteIngotTag, IDS.top.netheriteTemplate, IDS.pack.catalyst])

  // Jet Suit (chest piece). Default '# #' / TNT / CEC (adastra-1.21.1-1.16.25-neoforge.jar!data/ad_astra/recipe/jet_suit.json):
  // the catalyst fills the empty top-middle (A7). N is the Netherite Space Suit, which takes an elytra after plan Task 8.
  gate.remove(event, { id: IDS.top.jetSuitRecipe })
  gate.shaped(event, 'confluence:tier7/jet_suit', IDS.top.jetSuit, ['#K#', 'TNT', 'CEC'], { '#': IDS.top.caloritePlateTag,
    K: IDS.pack.catalyst, T: IDS.top.caloriteTank, N: IDS.adastra.netheriteSpaceSuit, C: IDS.top.etrionicCapacitor,
    E: IDS.top.caloriteEngine })

  // Upgrade: Productivity Omega. Default CEC / EBE / CEC (productivelib-1.21.1-0.2.0.jar, jar-in-jar in productivebees): the
  // catalyst replaces the bottom-middle heart of the sea; the four Gamma upgrades and the upgrade block stay (A9).
  gate.remove(event, { id: IDS.top.productivity4Recipe })
  gate.shaped(event, 'confluence:tier7/upgrade_productivity_4', IDS.top.productivity4, ['CEC', 'EBE', 'CKC'],
    { C: IDS.top.productivity3, E: IDS.top.heartOfTheSea, B: IDS.top.upgradeBlock, K: IDS.pack.catalyst })

  // Tri-Bow. No default recipe; the Snow Queen's snow_queen_bows pool stays a second source (D144). Ice Bow and Aurora Block come
  // from her structure (A10).
  gate.shapeless(event, 'confluence:tier7/triple_bow', IDS.top.triBow,
    [IDS.top.iceBow, IDS.top.bow, IDS.top.bow, IDS.top.auroraBlock, IDS.pack.catalyst])
})
