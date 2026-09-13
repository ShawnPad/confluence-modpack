// Tier 3 — The Undergarden (spec §3, D83, D84, D87). Ids: lib/ids.js (phase7-tier3-ids.md).
ServerEvents.recipes(event => {
  // D3.1 Undergarden catalyst: default CSC/SES/CSC (copper, stones, ender pearl) replaced by knightmetal + Allthemodium ingot +
  // IF Simple Machine Frame + Iron's Upgrade Orb (a plain crafting item, D83). The crumbling catalyst stays (D47).
  gate.replaceShaped(event, 'confluence:tier3/undergarden_catalyst', IDS.undergarden.catalyst,
    [' K ', 'AFO'], { K: IDS.twilight.knightmetal, A: IDS.allthemodium.ingot, F: IDS.ifg.simpleFrameTag, O: IDS.irons.upgradeOrb })

  // T3.1 Nitro crystal: six inputs — the Energizing Orb has six input slots (D87), so ours drops one of the default's two redstone blocks. Removed by recipe id so the 9↔1 block
  // recipes survive (D69 lesson). Powah's default: nether star + 2 redstone blocks + blazing crystal block, 20,000,000 FE, 16 out.
  gate.remove(event, { id: IDS.powah.nitroRecipe })
  gate.custom(event, 'confluence:tier3/crystal_nitro', {
    type: 'powah:energizing', energy: 20000000,
    ingredients: [
      { tag: tagId(IDS.vanilla.netherStarTag) }, { tag: tagId(IDS.vanilla.redstoneBlockTag) }, { item: IDS.powah.blazingCrystalBlock },
      { item: IDS.powah.spirited }, { item: IDS.irons.arcaneEssence }, { item: IDS.powah.uraninite },
    ],
    result: { count: 16, id: IDS.powah.nitro },
  })

  // T3.2 Elite control circuit: both defaults go (crafting ACA and the infuser alternate), ours adds an Allthemodium ingot.
  // Removed by id, not output: gates.yaml asserts both default ids individually (D87).
  IDS.mek.eliteCircuitRecipes.forEach(id => gate.remove(event, { id: id }))
  gate.shaped(event, 'confluence:tier3/elite_control_circuit', IDS.mek.eliteCircuit, [' M ', 'ACA'],
    { M: IDS.allthemodium.ingot, A: IDS.mek.reinforcedAlloyTag, C: IDS.mek.advancedCircuitTag })

  // T3.2 Refined obsidian: dust → ingot leaves the Osmium Compressor (mekanism:compressing, one item input) for the Combiner with
  // an Allthemodium nugget (D87). JSON shape as bypass.js (Mekanism combining/obsidian.json).
  gate.remove(event, { id: IDS.mek.refinedObsidianFromDustRecipe })
  gate.custom(event, 'confluence:tier3/refined_obsidian_ingot', {
    type: 'mekanism:combining',
    main_input: { count: 1, tag: tagId(IDS.mek.refinedObsidianDustTag) },
    extra_input: { count: 1, tag: tagId(IDS.allthemodium.nugget) },
    output: { count: 1, id: IDS.mek.refinedObsidianIngot },
  })

  // M3.1 Ritual Brazier (D84): Ars' shapeless (pedestal + source gem block + 3 gold) plus a Powah spirited crystal and a second source gem block (2 total).
  gate.replaceShapeless(event, 'confluence:tier3/ritual_brazier', IDS.ars.ritualBrazier,
    [IDS.ars.arcanePedestal, IDS.ars.sourceBlockTag, IDS.vanilla.goldIngotTag, IDS.vanilla.goldIngotTag, IDS.vanilla.goldIngotTag, IDS.powah.spirited, IDS.ars.sourceBlockTag])

  // M3.2 Lightning Upgrade Orb: 7 runes + orb + Allthemodium ingot (D83, user choice).
  gate.replaceShaped(event, 'confluence:tier3/lightning_upgrade_orb', IDS.irons.lightningOrb,
    ['RRR', 'ROR', 'RMR'], { R: IDS.irons.lightningRune, O: IDS.irons.upgradeOrb, M: IDS.allthemodium.ingot })

  // S3.1 QIO. Dashboard: Tom's crafting terminal + teleportation core + 3 refined obsidian + Vibranium (spec §3 S3.1).
  gate.replaceShaped(event, 'confluence:tier3/qio_dashboard', IDS.mek.qioDashboard,
    ['I I', 'VTC', ' I '], { I: IDS.mek.refinedObsidianIngotTag, V: IDS.allthemodium.vibraniumIngotTag, T: IDS.mek.teleportationCore, C: IDS.toms.craftingTerminal })
  // Drive array keeps Mekanism's own recipe type mekanism:mek_data (a shaped variant that initialises the block's data, D87);
  // default TGT/C#C/TIT with the bottom ender pearl replaced by Vibranium.
  gate.remove(event, { id: IDS.mek.qioDriveArrayRecipe })
  gate.custom(event, 'confluence:tier3/qio_drive_array', {
    type: 'mekanism:mek_data', category: 'misc',
    key: { '#': { tag: tagId(IDS.mek.personalStorageTag) }, C: { tag: tagId(IDS.mek.ultimateCircuitTag) }, G: { tag: tagId(IDS.vanilla.glassPaneTag) },
           T: { item: IDS.mek.teleportationCore }, V: { tag: tagId(IDS.allthemodium.vibraniumIngotTag) } },
    pattern: ['TGT', 'C#C', 'TVT'],
    result: { count: 1, id: IDS.mek.qioDriveArray },
  })
  // Importer / exporter: default ITI/ACA/ # with one lead ingot replaced by Vibranium. Keys built per call (Rhino: no object spread).
  const qio = (name, output, piston) => gate.replaceShaped(event, 'confluence:tier3/qio_' + name, output,
    ['VTI', 'ACA', ' # '], { V: IDS.allthemodium.vibraniumIngotTag, T: IDS.mek.teleportationCore, I: IDS.mek.leadIngotTag,
      A: IDS.vanilla.enderPearlTag, C: IDS.mek.ultimateCircuitTag, '#': piston })
  qio('importer', IDS.mek.qioImporter, IDS.vanilla.stickyPiston)
  qio('exporter', IDS.mek.qioExporter, IDS.vanilla.piston)
})
