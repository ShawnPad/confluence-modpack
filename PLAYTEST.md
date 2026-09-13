# Confluence v0.2 playtest

Tiers 0–4 are playable: Overworld → Nether → Twilight Forest → Undergarden → The End. **0.2.0 changes worldgen:** Undergarden chunks generated before 0.2.0 have no Vibranium; explore fresh chunks. This page is the checklist; **report in [issue #1](https://github.com/ShawnPad/confluence-modpack/issues/1)** (one comment per session: probe id, PASS or FAIL, what you did, what happened, screenshots). Anything not listed here that feels wrong is worth reporting too.

## Setup

1. Install [Prism Launcher](https://prismlauncher.org/) and a Java 21 runtime (Prism → Settings → Java can download one).
2. Prism → **Add Instance → Import** → paste `https://github.com/ShawnPad/confluence-modpack/releases/latest/download/confluence-prism.zip` → launch. The first launch downloads about 130 mods; every later launch checks for updates by itself, so never re-import.
3. **Memory.** The zip from 0.1.3 on asks Prism for a 6 GB heap. If you imported before 0.1.3, set it once by hand: instance → Edit → Settings → Java → tick Memory → Maximum **6144** MiB. Prism's default 4 GB ran out of heap in a single-player world (`java.lang.OutOfMemoryError: Java heap space`).
4. Multiplayer → Add Server → `136.60.16.74:25584`.
5. If a launch fails with an install error: close Prism, delete `<instance>/.minecraft/packwiz.json`, launch again. Logs live in `<instance>/.minecraft/logs/latest.log`, crashes in `crash-reports/`.

Two kinds of probe. **Server** = play normally on the server. **Creative** = make a single-player creative world with cheats on (same instance) and use the commands given; you cannot run those on the server unless you are an op. In JEI, hover an item and press **R** for its recipe, **U** for its uses.

Harmless and known: the log shows a couple of dozen "Couldn't load tag … missing following references" errors at world load. They come from mods referencing items that are not in this pack; no need to report them.

**Known, not a bug to report:** the pack ships Iris 1.8.14-beta.1 (the only Iris that works with Sodium 0.8). With a shader pack enabled, block entities such as chests can be missing from shadows and FPS may drop in busy areas; that is upstream Iris. Shaders off = unaffected. If the game crashes, attach the newest file from the instance's `.minecraft/crash-reports/` to issue #1.

## A. Getting in

| # | Kind | Do | Expected |
|---|---|---|---|
| A1 | Server | Launch, join the server. Search JEI for "Twilight Key" and "Coin". | You are in; both items exist. |
| A2 | Server | Open the questbook (the FTB Quests book button in your inventory, or its keybind under Controls). | Seven chapters in three groups (Trunk: Start Here, Overworld, Nether, Twilight Forest; Spurs: The Aether, Cataclysm; Shop: Coin Shop), every one titled. Each quest has a description that says what to do and what it leads to. (0.1.2 and earlier showed "Unnamed" everywhere: the translation file was in a layout FTB Quests does not read. Fixed in 0.1.3.) |

## B. Tier 1: the Nether key

| # | Kind | Do | Expected |
|---|---|---|---|
| B1 | Server | Look up flint and steel in JEI, then craft it. | The vanilla recipe is gone. The new one needs an osmium ingot (Mekanism), a source gem (Ars Nouveau) and flint. |
| B2 | Server | Look up fire charge in JEI. | No crafting recipe at all (vanilla and Ars Nouveau's are both removed). Tell us if that feels wrong, see F1. |
| B3 | Server | Complete the Nether key quest and claim it. | 10 coins and a Common bag. Right-click the bag: three items. |
| B4 | Server | In the Coin Shop chapter, hand in 16 coins, then 48. | 16 → a Common bag, 48 → an Uncommon bag. Both quests can be repeated. |

## C. Tier 2: the Twilight Forest

| # | Kind | Do | Expected |
|---|---|---|---|
| C1 | Server | Build the 2×2 Twilight portal pool. Throw in a diamond, then a Twilight Key. | The diamond does nothing. The key opens the portal. |
| C2 | Server | Look up the Twilight Key in JEI. | Netherite ingot, zanite gemstone (the Aether), Mekanism advanced control circuit, an Ars Nouveau essence, Cataclysm's Monstrous Horn. |
| C3 | Server | Complete and claim the Twilight key quest. | 15 coins and an Uncommon bag. |
| C4 | Server | Look up the Arcane Anvil (Iron's Spells 'n Spellbooks). | An Industrial Foregoing Simple Machine Frame sits where one polished deepslate used to be. Uncraftable without the frame. |
| C5 | Server | Look up Tom's Storage Terminal and Inventory Connector. | New recipes: they use a Sophisticated Storage chest and a netherite-upgraded Functional Storage drawer. |
| C6 | Server | Powah Energizing Orb: try an emerald, then uraninite. | The emerald no longer makes a spirited crystal. Uraninite does, at 1,000,000 FE. |
| C7 | Server | Craft 9 spirited crystals into a block, then the block back. | Both directions work (9 ↔ 1). |
| C8 | Server | Look up Industrial Foregoing's Simple Machine Frame and Dissolution Chamber. | Frame (Dissolution Chamber recipe): one nether brick replaced by an Ars Nouveau essence (air, earth, fire or water). Chamber (crafting): one gold replaced by a basic control circuit. |
| C9 | Server | Walk Twilight Forest caves below y 10 (in chunks nobody visited before 0.1.2) and look at the **floors**; mine with a netherite pickaxe. | Allthemodium ore shows in cave floors, roughly a vein every 2–3 chunks, and drops raw Allthemodium. |
| C10 | Creative | `/loot give @s loot twilightforest:stronghold_cache`, thirty times. | The Allthemodium upgrade smithing template shows up at least once (about 1 in 14 caches; 0.1.2 had it at 1 in 576 by mistake, fixed in 0.1.3). Brushing suspicious clay in an Overworld Ancient City never gives it any more; the template exists only in Twilight strongholds. |
| C11 | Server | Look up the Twilight Uncrafting Table. | No recipe, and it never appears in Twilight loot. |
| C12 | Creative | Mekanism Combiner with Allthemodium ore + a vibranium ingot; 3 raw Allthemodium + ingot; a raw block + ingot. Then look up Allthemodium ore's uses. | 5, 10 and 30 Allthemodium crystals. The ore → dirty slurry Dissolution Chamber route is gone from JEI. (Vibranium is a later tier, so this one is creative only.) |

## D. Worldgen (Creative)

| # | Do | Expected |
|---|---|---|
| D1 | `/execute in allthemodium:mining run tp @s 0 120 0`, then spectate or dig **between y 65 and y 250** (the ore is buried in stone; nothing is placed below y 65, so the bottom layers are the wrong place to look). | Uraninite ore (poor / normal / dense) is common, dozens per chunk. No Allthemodium anywhere in this dimension: in this pack it spawns only in the Twilight Forest. |
| D2 | `/execute in allthemodium:the_other run tp @s 0 64 0`, look around underground. | No uraninite. |
| D3 | Twilight Forest caves, floors, y ≤ 10, freshly generated chunks. | Allthemodium ore present. |
| D4 | Overworld deep dark, the Nether, the End. | No Allthemodium, Vibranium, Unobtainium or uraninite anywhere. |
| D5 | `/give @s kubejs:mercury_ore` and `/give @s kubejs:glacio_ore`; place and break with a diamond-tier pickaxe. | Each drops its shard. |
| D6 | `/execute in undergarden:undergarden run tp @s 0 -30 0`, dig around between y −55 and −16 in fresh chunks. | Vibranium ore in cave floors, about one per chunk; none above y −16 and none in any other dimension (Nether, The Other, End all clear). |

## E. Questbook and rewards (Creative)

| # | Do | Expected |
|---|---|---|
| E1 | `/give @s ftbquests:lootcrate[ftbquests:loot_crate="common_bag"]`, then use it. | A crate that rolls three items. |
| E2 | `/ftbquests reload` | No errors in chat or the log; the eleven chapters are still there. |

## G. Tier 3: the Undergarden

| # | Kind | Do | Expected |
|---|---|---|---|
| G1 | Server | Look up the Undergarden Catalyst in JEI. | Knightmetal ingot, Allthemodium ingot, IF Simple Machine Frame, Iron's Upgrade Orb. Copper/stone/pearl recipe gone; the Crumbling Catalyst recipe still exists. |
| G2 | Server | Light an Undergarden portal (stone-brick frame, catalyst on the bottom inner block) and go through. | You arrive; the questbook's "Into the Undergarden" completes by itself within a few seconds. |
| G3 | Server | Undergarden caves below y −16, fresh chunks: look at floors with an Allthemodium pickaxe. | Vibranium ore in cave floors (about one per chunk); drops raw Vibranium. None above y −16, none in any other dimension. |
| G4 | Server | Open catacombs chests. | The Vibranium upgrade template shows up about one chest in seven; the Forgotten template about one in five. |
| G5 | Server | Powah Energizing Orb: nether star, redstone block, blazing crystal block, spirited crystal, arcane essence, uraninite. | 16 nitro crystals at 20,000,000 FE. The old four-item recipe does nothing. |
| G6 | Server | JEI: elite control circuit, refined obsidian ingot. | Circuit needs an Allthemodium ingot; the infuser route is gone. Refined obsidian ingot is a Combiner recipe (dust + Allthemodium nugget); the Osmium Compressor route is gone. |
| G7 | Server | JEI: Ritual Brazier, Lightning Upgrade Orb. | Brazier adds a spirited crystal and a second source gem block. Orb: 7 lightning runes + upgrade orb + Allthemodium ingot. |
| G8 | Server | JEI: QIO Dashboard, Drive Array, Importer, Exporter. | Dashboard: Tom's crafting terminal + teleportation core + 3 refined obsidian + Vibranium. The other three each contain a Vibranium ingot; the Drive Array still crafts and places normally. |
| G9 | Creative | Mekanism Combiner: Vibranium ore + Unobtainium ingot. Then look up Vibranium ore's uses. | 5 Vibranium crystals; the ore → dirty slurry route is gone. (Unobtainium is tier 5, so creative only.) |
| G10 | Creative | Bind a Drygmy near a Forgotten Guardian, a Sludge, the Ender Guardian, a Wither, a Warden, the Bee Queen. | The Drygmy produces nothing from them (Ars' blacklist). Iron golems too, as in vanilla Ars. Other mobs work. |
| G11 | Server | Coin Shop after the catalyst quest. | A Rare bag for 96 coins, repeatable; three items per bag. |

## H. Tier 4: the End

| # | Kind | Do | Expected |
|---|---|---|---|
| H1 | Server | Look up the Eye of Ender. | Vibranium ingot, forgotten ingot, Resonarium, nitro crystal, Ritual Brazier. No other eye recipe. |
| H2 | Server | Otherside: find an Ancient City, check the centre frame's inside is air (dig out anything left), stand inside holding one Heart of the Deep and right-click a frame face; then kill the smallest Sludges in the Blooming Caverns. | Portal lights (the frame cannot be mined, so this is the only way in); a return portal is generated on the other side; small Sludges drop Resonarium (0–1 each). |
| H3 | Server | JEI: IF Advanced Machine Frame. | Dissolution Chamber, 500 mB pink slime: plastic ×2, Simple frame, Vibranium ×2, Lightning Upgrade Orb, diamond gear, gold ingot. |
| H4 | Server | JEI: Planarium, End Focus. | Planarium adds a teleportation core + refined obsidian on the pedestals. End Focus: Planarium reagent; essences ×4, dragon's breath, Gauntlet of Guard, Ritual Brazier, source gem block. |
| H5 | Server | Kill the dragon; enter the Bumblezone via a piston on a beehive; find the Throne Pillar. | "The Dragon" quest completes on the kill; "The Bumblezone" on arrival; "Throne Pillar" when the advancement fires. |
| H6 | Creative | `/ftbquests reload` | No errors; eleven chapters (Trunk: Start Here, Overworld, Nether, Twilight Forest, The Undergarden, The End; Spurs: The Aether, Cataclysm, The Otherside, The Bumblezone; Shop). |

## F. Opinions we want

| # | Question |
|---|---|
| F1 | Fire charges cannot be crafted at all in v0.1. Fine, or should there be a Nether-only recipe? |
| F2 | The Common bag can give osmium ingots and source gems, the two inputs of the Nether key. Too generous? |
| F3 | The server runs on Easy right now. What difficulty do you want? |
| F4 | Anything too grindy, too cheap, or confusing in the quest text. |


