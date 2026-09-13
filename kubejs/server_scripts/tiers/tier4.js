// Tier 4 — The End (spec §3, D84, D87, D88). Ids: lib/ids.js (phase7-tier4-ids.md).
ServerEvents.recipes(event => {
  // D4.1 Eye of Ender: Vibranium ingot + forgotten ingot + Resonarium + nitro crystal + a Ritual Brazier (D84: the brazier block
  // itself, since Ars charms are wild-mob Apparatus products the brazier does not gate). replaceShaped removes every recipe
  // that outputs an eye, vanilla's included.
  gate.replaceShaped(event, 'confluence:tier4/ender_eye', IDS.vanilla.enderEye,
    [' V ', 'RBN', ' F '], { V: IDS.allthemodium.vibraniumIngotTag, R: IDS.dd.resonarium, B: IDS.ars.ritualBrazier, N: IDS.powah.nitro, F: IDS.undergarden.forgottenIngot })

  // M4.1 Planarium: Ars' Apparatus recipe (reagent mob jar; pedestals stable warp scroll, conjuration essence, diamond) plus a
  // Mekanism teleportation core and a refined obsidian ingot on the pedestals. Removed by id, re-added as raw JSON — the same
  // six keys (type, keepNbtOfReagent, pedestalItems, reagent, result, sourceCost) as ars_nouveau-1.21.1-5.13.1.jar!data/ars_nouveau/recipe/planarium.json (phase7-tier4-ids.md §3).
  gate.remove(event, { id: IDS.ars.planarium })
  gate.custom(event, 'confluence:tier4/planarium', {
    type: IDS.ars.apparatusType, keepNbtOfReagent: false, sourceCost: 0,
    reagent: { item: IDS.ars.mobJar },
    pedestalItems: [{ item: IDS.ars.stableWarpScroll }, { item: IDS.ars.conjurationEssence }, { item: IDS.vanilla.diamond },
                    { item: IDS.mek.teleportationCore }, { tag: tagId(IDS.mek.refinedObsidianIngotTag) }],
    result: { count: 1, id: IDS.ars.planarium },
  })

  // M4.2 End Focus: reagent Planarium; eight pedestals — the four essences, dragon's breath, Gauntlet of Guard, a Ritual Brazier
  // (D84) and a source gem block. The Apparatus has eight pedestals (the drygmy_charm recipe lists eight, phase7-tier3-ids §5).
  gate.custom(event, 'confluence:tier4/end_focus', {
    type: IDS.ars.apparatusType, keepNbtOfReagent: false, sourceCost: 0,
    reagent: { item: IDS.ars.planarium },
    pedestalItems: IDS.ars.essences.map(e => ({ item: e })).concat([
      { item: IDS.vanilla.dragonBreath }, { item: IDS.cataclysm.gauntletOfGuard }, { item: IDS.ars.ritualBrazier }, { item: IDS.ars.sourceGemBlock }]),
    result: { count: 1, id: IDS.pack.endFocus },
  })
})
