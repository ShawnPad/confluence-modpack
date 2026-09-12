# Changelog

## 0.1.2
- Fix: Allthemodium never generated in the Twilight Forest (0 ore in 511 freshly generated chunks). The placement rule, copied from Allthemodium's own Deep Dark file, only starts in `minecraft:air` and aims at cave ceilings; the Twilight's caves are carver `cave_air`, and an ore vein sits at or below its origin, so the rule placed nothing. Veins now generate in the **floors** of Twilight caves below y 10, about one vein every 2-3 chunks (measured 1.1 ore per chunk over 256 chunks). Server-side: only chunks generated after the restart have ore, so explore Twilight caves nobody has visited yet. Quest text and PLAYTEST rows updated; the Mining Dimension never had Allthemodium in this pack (the 0.1.0 note below was wrong - it has uraninite only).
- Tooling: `tools/probe_worldgen.sh` boots the local server, generates a fresh block of chunks in one dimension and counts blocks in a y band.

## 0.1.1
- Fix: every client crashed at world join with `MixinPreProcessorException ... MixinRenderSectionManager from mod iris ... ClassNotFoundException: net.caffeinemc.mods.sodium.client.gui.SodiumGameOptions$PerformanceSettings`. Iris 1.8.12 was built for Sodium 0.6; the pack ships Sodium 0.8.13. Iris is now 1.8.14-beta.1, the build made for Sodium 0.8. Client-only change: relaunch the instance and packwiz swaps the jar; the server is unaffected.

## 0.1.0
- Tiers 0-2 of the progression tree: the Nether key (flint and steel needs osmium and a source gem), the Twilight key (the only Twilight portal activator), tier-2 rewrites for the Arcane Anvil, Tom's storage terminal and inventory connector, Powah's spirited crystal (uraninite), and Industrial Foregoing's simple machine frame and dissolution chamber.
- Allthemodium spawns only in the Twilight Forest and the Mining Dimension; uraninite only in the Mining Dimension; the Overworld, Nether, End and The Other placements are switched off.
- Bypass closures: laser-drilled ancient debris, Deeper and Darker gloomslate ores, the Twilight uncrafting table, fire-charge crafting, ruined-portal key loot; Allthemodium's 5x Mekanism chain needs Vibranium.
- Questbook: intro, Overworld, Nether, Twilight Forest, Aether, Cataclysm and Coin Shop chapters (45 quests) with coins on every quest and Common/Uncommon reward bags.
- Tooling: headless boot harness, recipe-gate, tag and quest checkers, chapter scaffolder, Prism instance generator.

## 0.0.0
- Skeleton: all mods, boots headless.
