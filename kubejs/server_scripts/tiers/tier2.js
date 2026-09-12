// Tier 2 — Twilight Forest and Mining Dimension (spec §3).
ServerEvents.recipes(event => {
  // D2.1 Twilight key. The portal tag swap is in events.js.
  gate.replaceShaped(event, 'confluence:tier2/twilight_key', IDS.pack.twilightKey,
    [' Z ', 'NCH', ' E '], { Z: IDS.aether.zanite, N: IDS.vanilla.netherite, C: IDS.mek.advancedCircuit, H: IDS.cataclysm.monstrousHorn, E: IDS.ars.essenceTag })

  // D2.5 Teleport Pad: Allthemodium's default already is 4 nuggets + ender pearl (ids report §B). No script.

  // M2.1 Arcane Anvil: Iron's default with one polished deepslate replaced by a Simple Machine Frame.
  gate.replaceShaped(event, 'confluence:tier2/arcane_anvil', IDS.irons.arcaneAnvil,
    ['AAA', ' D ', 'FVS'], { A: 'minecraft:amethyst_block', D: '#c:gems/diamond', V: 'minecraft:anvil', S: 'minecraft:polished_deepslate', F: IDS.ifg.simpleFrameTag })

  // S2.1 Tom's Storage Terminal: default PCP/cGg/PCP with the corners replaced by Simple frame, essence,
  // netherite storage upgrade + drawer controller (the "netherite-upgraded controller" as two items), Sophisticated chest.
  gate.replaceShaped(event, 'confluence:tier2/storage_terminal', IDS.toms.storageTerminal,
    ['FCE', 'UGK', 'PSP'], { F: IDS.ifg.simpleFrameTag, C: 'minecraft:comparator', E: IDS.ars.essenceTag, U: IDS.fs.netheriteUpgrade, G: '#c:dusts/glowstone', K: IDS.fs.controller, P: '#minecraft:planks', S: IDS.soph.chest })
  // S2.1 Inventory Connector: default PCP/cDc/PEP with the diamond replaced by a Simple frame.
  gate.replaceShaped(event, 'confluence:tier2/inventory_connector', IDS.toms.inventoryConnector,
    ['PCP', 'cFc', 'PEP'], { P: '#minecraft:planks', C: 'minecraft:comparator', c: '#c:chests', F: IDS.ifg.simpleFrameTag, E: '#c:ender_pearls' })

  // X2.1 Powah spirited crystal: uraninite replaces the emerald (energy unchanged, 1,000,000 FE).
  // Removed by RECIPE id, not by { output: IDS.powah.spirited }: Powah-6.2.10.jar also ships
  // data/powah/recipe/crafting/spirited_crystal.json (shapeless powah:spirited_crystal_block -> 9x
  // powah:crystal_spirited), and an output-wide removal takes that unpack recipe with it, making the
  // 9-crystal block (data/powah/recipe/crafting/spirited_crystal_block.json) a one-way trap.
  gate.remove(event, { id: IDS.powah.spiritedRecipe })
  gate.custom(event, 'confluence:tier2/crystal_spirited', {
    type: 'powah:energizing', energy: 1000000,
    ingredients: [{ item: IDS.powah.uraninite }],
    result: { count: 1, id: IDS.powah.spirited },
  })
})
