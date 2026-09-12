# Confluence v0.1 playtest

Tiers 0–2 are playable: Overworld → Nether → Twilight Forest. This page is the checklist; **report in [issue #1](https://github.com/ShawnPad/confluence-modpack/issues/1)** (one comment per session: probe id, PASS or FAIL, what you did, what happened, screenshots). Anything not listed here that feels wrong is worth reporting too.

## Setup

1. Install [Prism Launcher](https://prismlauncher.org/) and a Java 21 runtime (Prism → Settings → Java can download one).
2. Prism → **Add Instance → Import** → paste `https://github.com/ShawnPad/confluence-modpack/releases/latest/download/confluence-prism.zip` → launch. The first launch downloads about 130 mods; every later launch checks for updates by itself, so never re-import.
3. Multiplayer → Add Server → `136.60.16.74:25584`.
4. If a launch fails with an install error: close Prism, delete `<instance>/.minecraft/packwiz.json`, launch again. Logs live in `<instance>/.minecraft/logs/latest.log`, crashes in `crash-reports/`.

Two kinds of probe. **Server** = play normally on the server. **Creative** = make a single-player creative world with cheats on (same instance) and use the commands given; you cannot run those on the server unless you are an op. In JEI, hover an item and press **R** for its recipe, **U** for its uses.

Harmless and known: the log shows a couple of dozen "Couldn't load tag … missing following references" errors at world load. They come from mods referencing items that are not in this pack; no need to report them.

## A. Getting in

| # | Kind | Do | Expected |
|---|---|---|---|
| A1 | Server | Launch, join the server. Search JEI for "Twilight Key" and "Coin". | You are in; both items exist. |
| A2 | Server | Open the questbook (the FTB Quests book button in your inventory, or its keybind under Controls). | Seven chapters in three groups: Intro, Overworld, Nether, Twilight Forest; Aether, Cataclysm; Coin Shop. Descriptions are readable and make sense. |

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
| C9 | Server | Mine in Twilight Forest caves with a netherite pickaxe. | Allthemodium ore exists there and drops raw Allthemodium. |
| C10 | Creative | `/loot give @s loot twilightforest:stronghold_cache`, twenty times. | The Allthemodium upgrade smithing template shows up at least once (roughly 1 in 14 rolls). |
| C11 | Server | Look up the Twilight Uncrafting Table. | No recipe, and it never appears in Twilight loot. |
| C12 | Creative | Mekanism Combiner with Allthemodium ore + a vibranium ingot; 3 raw Allthemodium + ingot; a raw block + ingot. Then look up Allthemodium ore's uses. | 5, 10 and 30 Allthemodium crystals. The ore → dirty slurry Dissolution Chamber route is gone from JEI. (Vibranium is a later tier, so this one is creative only.) |

## D. Worldgen (Creative)

| # | Do | Expected |
|---|---|---|
| D1 | `/execute in allthemodium:mining run tp @s 0 40 0`, then dig or spectate down to y −60 … −20. | Allthemodium ore and uraninite ore are present. |
| D2 | `/execute in allthemodium:the_other run tp @s 0 64 0`, look around underground. | No uraninite. |
| D3 | Twilight Forest caves. | Allthemodium ore present. |
| D4 | Overworld deep dark, the Nether, the End. | No Allthemodium, Vibranium, Unobtainium or uraninite anywhere. |
| D5 | `/give @s kubejs:mercury_ore` and `/give @s kubejs:glacio_ore`; place and break with a diamond-tier pickaxe. | Each drops its shard. |

## E. Questbook and rewards (Creative)

| # | Do | Expected |
|---|---|---|
| E1 | `/give @s ftbquests:lootcrate[ftbquests:loot_crate="common_bag"]`, then use it. | A crate that rolls three items. |
| E2 | `/ftbquests reload` | No errors in chat or the log; the seven chapters are still there. |

## F. Opinions we want

| # | Question |
|---|---|
| F1 | Fire charges cannot be crafted at all in v0.1. Fine, or should there be a Nether-only recipe? |
| F2 | The Common bag can give osmium ingots and source gems, the two inputs of the Nether key. Too generous? |
| F3 | The server runs on Easy right now. What difficulty do you want? |
| F4 | Anything too grindy, too cheap, or confusing in the quest text. |
