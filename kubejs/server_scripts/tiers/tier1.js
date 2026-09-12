// Tier 1 — Nether (spec §3). Every gate is a rewritten recipe; quests only mirror them (D18).
ServerEvents.recipes(event => {
  // D1.1 flint and steel: flint + osmium ingot + Ars source gem. Removes the vanilla recipe.
  gate.replaceShaped(event, 'confluence:tier1/flint_and_steel', IDS.vanilla.flintAndSteel,
    ['O ', ' F', 'G '], { O: IDS.mek.osmiumIngot, F: 'minecraft:flint', G: IDS.ars.sourceGem })

  // T1.1 Metallurgic Infuser: Mekanism default with one iron replaced by a source gem.
  gate.replaceShaped(event, 'confluence:tier1/metallurgic_infuser', IDS.mek.infuser,
    ['I#G', 'ROR', 'I#I'], { '#': 'minecraft:furnace', I: '#c:ingots/iron', O: IDS.mek.osmiumIngot, R: IDS.mek.redstoneDust, G: IDS.ars.sourceGem })

  // M1.1 Enchanting Apparatus: Ars default with one gold nugget replaced by an osmium ingot.
  gate.replaceShaped(event, 'confluence:tier1/enchanting_apparatus', IDS.ars.apparatus,
    ['nsO', 'gdg', 'nsn'], { n: '#c:nuggets/gold', s: IDS.ars.sourcestone, g: '#c:ingots/gold', d: '#c:gems/diamond', O: IDS.mek.osmiumIngot })

  // D1.1 closure (tree note): no fire charges before the Nether.
  gate.remove(event, { id: IDS.vanilla.fireCharge })
  // D1.1 closure, second fire-charge recipe (D64): Ars Nouveau's fire essence + gunpowder + coal -> 3 fire charges
  // (ars_nouveau-1.21.1-5.13.1.jar, data/ars_nouveau/recipe/fire_essence_to_charge.json). Fire essence has a Productive Bees
  // route that never touches the key, so this recipe goes too; research/phase6-recipe-dump-and-fire-charge.md §3.
  gate.remove(event, { id: 'ars_nouveau:fire_essence_to_charge' })
})
