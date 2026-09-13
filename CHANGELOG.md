# Changelog

## 0.2.0
- Tiers 3–4 are playable: Overworld → Nether → Twilight Forest → Undergarden → The End. New gates: Undergarden Catalyst (knightmetal + Allthemodium + IF Simple Machine Frame + Iron's Upgrade Orb), Powah nitro crystal (six inputs incl. spirited crystal, arcane essence, uraninite), Mekanism elite control circuit (+ Allthemodium ingot) and refined obsidian ingot (Combiner: dust + Allthemodium nugget), Ars Ritual Brazier (+ spirited crystal + second source gem block), Iron's Lightning Upgrade Orb (7 runes + orb + Allthemodium), QIO dashboard / drive array / importer / exporter (Vibranium), Eye of Ender (Vibranium + forgotten ingot + Resonarium + nitro + Ritual Brazier; the vanilla and Mystical Agriculture recipes are gone), IF Advanced Machine Frame (2 Vibranium + Lightning Upgrade Orb replace the netherite scrap and one gold), Ars Planarium (+ teleportation core + refined obsidian) and the pack's End Focus (Apparatus: Planarium + 4 essences + dragon's breath + Gauntlet of Guard + Ritual Brazier + source gem block).
- Worldgen: Vibranium ore now generates only in Undergarden cave floors between y −55 and −16 (about one per chunk, measured 1.2/chunk over five 256-chunk squares). **Undergarden chunks generated before 0.2.0 have no Vibranium.** The Vibranium upgrade smithing template rides in Undergarden catacombs chests at 2/14 (about one chest in seven; measured 45 in 300 rolls).
- Bypasses: the Vibranium 5× Mekanism chain (ore / raw / raw block → dirty slurry) is replaced by Combiner recipes that also consume an Unobtainium ingot, so ore quintupling waits for tier 5. Drygmies cannot farm the Forgotten Guardian, Sludges, Stalkers, the Ender Guardian, the Netherite Monstrosity, the Ender Dragon, the Wither, the Warden or the Bee Queen (`ars_nouveau:drygmy_blacklist`).
- Questbook: four new chapters (The Undergarden, The End, The Otherside, The Bumblezone; 11 chapters, 73 quests). Ore Quintupling now also waits on Vibranium. Coin Shop: Rare bag for 96 coins after the Undergarden Catalyst (netherite, diamonds, emeralds, steel, energized steel, ender pearls, blaze rods, coins), repeatable.
- Tooling: the chapter scaffolder renders `advancement:` tasks and refuses `repeat: true` on tasks that complete by themselves; `tools/check_tags.py` knows block and biome tags; loot injection goes through `addToPool`, which logs and skips instead of silently landing in the wrong pool.

## 0.1.4
- Textures: the pack's ten items and blocks (coin, both keys, both foci, the catalyst, both shards, both ores) get drawn starter textures in the bold-icon style (`art/STYLE.md`) instead of flat colour squares. Client-only; no server restart.
- Tooling: `art/` (palette, style sheet, briefs, contributor guide), `tools/check_textures.py` in the test loop, `tools/gen_textures.py` never overwrites an existing PNG.

## 0.1.3
- Fix: the questbook showed "Unnamed Group" / "Unnamed" for every group, chapter and quest, with no descriptions. The translations sat in `lang/en_us/{chapter,chapter_group}.snbt` + `lang/en_us/chapters/*.snbt`, the layout ATM10 uses - but ATM10 ships the FTB Quests Lang Splitter mod to merge those files, and FTB Quests itself reads only a flat `lang/en_us.snbt`. The pack now ships that one file (same keys, same text). Server-side and client-side; relaunch picks it up.
- Fix: the Allthemodium upgrade smithing template was in Twilight stronghold caches at weight 1 against a pool of weight 575 (1 chest in 576). It is now weight 45, about 1 cache in 14 (measured 17 in 300 rolls). And the template no longer appears where Allthemodium itself put it: Ancient City suspicious clay (`allthemodium:arch`) and, for the Vibranium template, bastion suspicious soul sand (`allthemodium:arch2`) now roll empty. Chests and suspicious blocks generated before this update keep their old contents.
- Quest text rewritten for players: no more tree ids or "Rewritten:"/"Audit:" prefixes; each description says what to do and what it leads to. Checkmark quests keep their 3 coins.
- Prism instance zip: the instance now asks for a 6 GB heap (`OverrideMemory`, `MaxMemAlloc=6144`). A single-player world on Prism's default 4 GB crashed with `java.lang.OutOfMemoryError: Java heap space`. Instances imported earlier: set 6144 MiB by hand once (PLAYTEST.md, Setup).
- Tooling: `tools/probe_loot.sh` rolls a loot table into a chest N times on the headless server and counts an item (the only check that sees what LootJS did to a table); `tools/scaffold_chapter.py --lang-only` rebuilds the lang file from `tools/chapters/*.yaml`; `check_quests.py` maps tree nodes to quests through their deterministic ids instead of a node-id line in the description.
- Verified, not changed: uraninite generates in the Mining Dimension at about 110 ore per chunk between y 65 and 250 (`tools/probe_worldgen.sh`, fresh 256-chunk block); a tester looked below y 0. PLAYTEST D1 now says where to look.

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
