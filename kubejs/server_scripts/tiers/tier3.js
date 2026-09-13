// Tier 3 — The Undergarden (spec §3, D83–D87). Ids: lib/ids.js (phase7-tier3-ids.md).
ServerEvents.recipes(event => {
  // D3.1 Undergarden catalyst: default CSC/SES/CSC (copper, stones, ender pearl) replaced by knightmetal + Allthemodium ingot +
  // IF Simple Machine Frame + Iron's Upgrade Orb (a plain crafting item, D83). The crumbling catalyst stays (D47).
  gate.replaceShaped(event, 'confluence:tier3/undergarden_catalyst', IDS.undergarden.catalyst,
    [' K ', 'AFO'], { K: IDS.twilight.knightmetal, A: IDS.allthemodium.ingot, F: IDS.ifg.simpleFrameTag, O: IDS.irons.upgradeOrb })

  // T3.1 Nitro crystal: six inputs — the Energizing Orb has six input slots (D87). Removed by recipe id so the 9↔1 block
  // recipes survive (D69 lesson). Powah's default: nether star + 2 redstone blocks + blazing crystal block, 20,000,000 FE, 16 out.
  gate.remove(event, { id: IDS.powah.nitroRecipe })
  gate.custom(event, 'confluence:tier3/crystal_nitro', {
    type: 'powah:energizing', energy: 20000000,
    ingredients: [
      { tag: IDS.vanilla.netherStarTag.slice(1) }, { tag: IDS.vanilla.redstoneBlockTag.slice(1) }, { item: IDS.powah.blazingCrystalBlock },
      { item: IDS.powah.spirited }, { item: IDS.irons.arcaneEssence }, { item: IDS.powah.uraninite },
    ],
    result: { count: 16, id: IDS.powah.nitro },
  })

  // T3.2 Elite control circuit: both defaults go (crafting ACA and the infuser alternate), ours adds an Allthemodium ingot.
  IDS.mek.eliteCircuitRecipes.forEach(id => gate.remove(event, { id: id }))
  event.shaped(Item.of(IDS.mek.eliteCircuit), [' M ', 'ACA'],
    { M: IDS.allthemodium.ingot, A: IDS.mek.reinforcedAlloyTag, C: IDS.mek.advancedCircuitTag }).id('confluence:tier3/elite_control_circuit')
  // T3.2 Refined obsidian: dust → ingot leaves the Osmium Compressor (mekanism:compressing, one item input) for the Combiner with
  // an Allthemodium nugget (D87). JSON shape as bypass.js (Mekanism combining/obsidian.json).
  gate.remove(event, { id: IDS.mek.refinedObsidianFromDustRecipe })
  gate.custom(event, 'confluence:tier3/refined_obsidian_ingot', {
    type: 'mekanism:combining',
    main_input: { count: 1, tag: IDS.mek.refinedObsidianDustTag.slice(1) },
    extra_input: { count: 1, tag: IDS.allthemodium.nugget.slice(1) },
    output: { count: 1, id: IDS.mek.refinedObsidianIngot },
  })

  // M3.1 Ritual Brazier: Ars' shapeless (pedestal + source block + 3 gold) plus a Powah spirited crystal and a source gem block.
  gate.replaceShapeless(event, 'confluence:tier3/ritual_brazier', IDS.ars.ritualBrazier,
    [IDS.ars.arcanePedestal, IDS.ars.sourceBlockTag, '#c:ingots/gold', '#c:ingots/gold', '#c:ingots/gold', IDS.powah.spirited, IDS.ars.sourceGemBlock])

  // M3.2 Lightning Upgrade Orb: 7 runes + orb + Allthemodium ingot (D83, user choice).
  gate.replaceShaped(event, 'confluence:tier3/lightning_upgrade_orb', IDS.irons.lightningOrb,
    ['RRR', 'ROR', 'RMR'], { R: IDS.irons.lightningRune, O: IDS.irons.upgradeOrb, M: IDS.allthemodium.ingot })

  // S3.1 QIO. Dashboard: Tom's crafting terminal + teleportation core + 3 refined obsidian + Vibranium (spec, ozone pattern).
  gate.replaceShaped(event, 'confluence:tier3/qio_dashboard', IDS.mek.qioDashboard,
    ['I I', 'VTC', ' I '], { I: IDS.mek.refinedObsidianIngotTag, V: IDS.allthemodium.vibraniumIngotTag, T: IDS.mek.teleportationCore, C: IDS.toms.craftingTerminal })
  // Drive array keeps Mekanism's own recipe type mekanism:mek_data (a shaped variant that initialises the block's data, D87);
  // default TGT/C#C/TIT with the bottom ender pearl replaced by Vibranium.
  gate.remove(event, { id: IDS.mek.qioDriveArray })
  gate.custom(event, 'confluence:tier3/qio_drive_array', {
    type: 'mekanism:mek_data', category: 'misc',
    key: { '#': { tag: IDS.mek.personalStorageTag.slice(1) }, C: { tag: IDS.mek.ultimateCircuitTag.slice(1) }, G: { tag: IDS.vanilla.glassPaneTag.slice(1) },
           T: { item: IDS.mek.teleportationCore }, V: { tag: IDS.allthemodium.vibraniumIngotTag.slice(1) } },
    pattern: ['TGT', 'C#C', 'TVT'],
    result: { count: 1, id: IDS.mek.qioDriveArray },
  })
  // Importer / exporter: default ITI/ACA/ # with one lead ingot replaced by Vibranium.
  gate.replaceShaped(event, 'confluence:tier3/qio_importer', IDS.mek.qioImporter,
    ['VTI', 'ACA', ' # '], { V: IDS.allthemodium.vibraniumIngotTag, T: IDS.mek.teleportationCore, I: IDS.mek.leadIngotTag, A: IDS.vanilla.enderPearlTag, C: IDS.mek.ultimateCircuitTag, '#': IDS.vanilla.stickyPiston })
  gate.replaceShaped(event, 'confluence:tier3/qio_exporter', IDS.mek.qioExporter,
    ['VTI', 'ACA', ' # '], { V: IDS.allthemodium.vibraniumIngotTag, T: IDS.mek.teleportationCore, I: IDS.mek.leadIngotTag, A: IDS.vanilla.enderPearlTag, C: IDS.mek.ultimateCircuitTag, '#': IDS.vanilla.piston })
})
