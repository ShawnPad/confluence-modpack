# Confluence v0.3 playtest

Tiers 0–6 are playable: Overworld → Nether → Twilight Forest → Undergarden → The End → The Other → Space, plus the Eternal Starlight spur. **0.3.0 changes worldgen:** Unobtainium ore in The Other and Mercury and Glacio ore on those planets appear only in chunks generated on 0.3.0 or later; explore fresh chunks. New in 0.3: sections **I** (tier 5, The Other) and **J** (tier 6, Space and Eternal Starlight). This page is the checklist; **report in [issue #1](https://github.com/ShawnPad/confluence-modpack/issues/1)** (one comment per session: probe id, PASS or FAIL, what you did, what happened, screenshots). Anything not listed here that feels wrong is worth reporting too.

## Setup

1. Install [Prism Launcher](https://prismlauncher.org/) and a Java 21 runtime (Prism → Settings → Java can download one).
2. Prism → **Add Instance → Import** → paste `https://github.com/ShawnPad/confluence-modpack/releases/latest/download/confluence-prism.zip` → launch. The first launch downloads about 130 mods; every later launch checks for updates by itself, so never re-import.
3. **Memory.** The zip from 0.1.3 on asks Prism for a 6 GB heap. If you imported before 0.1.3, set it once by hand: instance → Edit → Settings → Java → tick Memory → Maximum **6144** MiB. Prism's default 4 GB ran out of heap in a single-player world (`java.lang.OutOfMemoryError: Java heap space`).
4. Multiplayer → Add Server → `136.60.16.74:25584`.
5. If a launch fails with an install error: close Prism, delete `<instance>/.minecraft/packwiz.json`, launch again. Logs live in `<instance>/.minecraft/logs/latest.log`, crashes in `crash-reports/`. This update replaces `config/fml.toml` once by itself, so do not restore an old copy. If the game opens on a KubeJS error list at startup, or `logs/kubejs/startup.log` has a line starting `confluence tf-gamerules guard FAILED`, the pack stopped a Twilight Forest load-order fault on purpose: press **Quit**, do not play on, and post that line and `latest.log` in the issue linked at the top of this page.

Two kinds of probe. **Server** = play normally on the server. **Creative** = make a single-player creative world with cheats on (same instance) and use the commands given; you cannot run those on the server unless you are an op. In JEI, hover an item and press **R** for its recipe, **U** for its uses.

**Fixed, so report it if you see it:** up to 0.2.1 the log showed about twenty "Couldn't load tag … missing following references" errors at world load. They were not harmless: Allthemodium lists a bow, a crossbow and a shield in item tags but never adds them, so the game dropped those tags, and bows and crossbows could not take their enchantments (Power, Punch, Flame, Infinity, Multishot, Piercing, Quick Charge). The pack now takes those three names out of the tags. If any "Couldn't load tag" line still shows up in `latest.log`, paste it into the issue linked at the top of this page.

**Known, not a bug to report:** the pack ships Iris 1.8.14-beta.1 (the only Iris that works with Sodium 0.8). With a shader pack enabled, block entities such as chests can be missing from shadows and FPS may drop in busy areas; that is upstream Iris. Shaders off = unaffected. If the game crashes, attach the newest file from the instance's `.minecraft/crash-reports/` to the issue linked at the top of this page.

## A. Getting in

| # | Kind | Do | Expected |
|---|---|---|---|
| A1 | Server | Launch, join the server. Search JEI for "Twilight Key" and "Coin". | You are in; both items exist. |
| A2 | Server | Open the questbook (the FTB Quests book button in your inventory, or its keybind under Controls). | Fourteen chapters in three groups (listed in H6), every one titled. Each quest has a description that says what to do and what it leads to. (0.1.2 and earlier showed "Unnamed" everywhere: the translation file was in a layout FTB Quests does not read. Fixed in 0.1.3.) |
| A3 | Creative | In a creative world, take an anvil, a bow, and an Enchanted Book of Power from the creative menu (or `/give @s minecraft:enchanted_book[minecraft:stored_enchantments={levels:{"minecraft:power":1}}]`). Put the bow in the anvil's left slot and the book in the middle slot. | The anvil offers a bow with Power. Before 0.3 it offered nothing. |

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
| C10 | Creative | `/loot give @s loot twilightforest:stronghold_cache`, thirty times. | The Allthemodium upgrade smithing template shows up at least once (about 1 in 14 caches; 0.1.2 had it at 1 in 576 by mistake, fixed in 0.1.3). Brushing suspicious clay in an Overworld Ancient City never gives it any more; the template exists only in Knight Stronghold chests (the goblin ruin under the Dark Forest, not the Minotaur Labyrinth). |
| C11 | Server | Look up the Twilight Uncrafting Table. | No recipe, and it never appears in Twilight loot. |
| C12 | Creative | Mekanism Combiner with Allthemodium ore + a vibranium ingot; 3 raw Allthemodium + ingot; a raw block + ingot. Then look up Allthemodium ore's uses. | 5, 10 and 30 Allthemodium crystals. The ore → dirty slurry Dissolution Chamber route is gone from JEI. (Vibranium is a later tier, so this one is creative only.) |
| C13 | Server | Read the "Allthemodium Ore" quest. Put Raw Allthemodium Ore in a furnace, then in a blast furnace. If you have an Enrichment Chamber, grind 3 raw ore and cook the dust in a furnace. | The quest says all this. The furnace does not cook the raw ore; the blast furnace makes an Allthemodium ingot. 3 raw ore make 4 dust, and the dust cooks into ingots in a furnace. |

## D. Worldgen (Creative)

| # | Do | Expected |
|---|---|---|
| D1 | `/execute in allthemodium:mining run tp @s 0 120 0`, then spectate or dig **between y 65 and y 250** (the ore is buried in stone; nothing is placed below y 65, so the bottom layers are the wrong place to look). | Uraninite ore (poor / normal / dense) is common, dozens per chunk. No Allthemodium anywhere in this dimension: in this pack it spawns only in the Twilight Forest. |
| D2 | `/execute in allthemodium:the_other run tp @s 0 64 0`, look around underground. | No uraninite. |
| D3 | Twilight Forest caves, floors, y ≤ 10, freshly generated chunks. | Allthemodium ore present. |
| D4 | Overworld deep dark, the Nether, the End. | No Allthemodium, Vibranium, Unobtainium or uraninite anywhere. |
| D5 | `/give @s kubejs:mercury_ore` and `/give @s kubejs:glacio_ore`; place and break with a diamond-tier pickaxe. | Each drops its shard. |
| D6 | `/execute in undergarden:undergarden run tp @s 0 -30 0`, dig around between y −55 and −16 in fresh chunks. | Vibranium ore in cave floors, about one per chunk; none above y −16 and none in any other dimension (Nether, The Other, End all clear). |
| D7 | `/execute in allthemodium:the_other run tp @s 0 100 0`, then spectate or dig through the ancient stone between y 8 and y 128 in fresh chunks. | Unobtainium ore on cave floors, about one per chunk. None in the Overworld, the Nether or the End. |
| D8 | `/execute in ad_astra:mercury run tp @s 0 100 0`, dig between y −32 and 96; then `/execute in ad_astra:glacio run tp @s 0 100 0`, dig between y −48 and 64 (deepslate at the bottom, glacio stone above). | Mercury ore on Mercury, Glacio ore on Glacio in both stones. Each drops its shard. |

## E. Questbook and rewards (Creative)

| # | Do | Expected |
|---|---|---|
| E1 | `/give @s ftbquests:lootcrate[ftbquests:loot_crate="common_bag"]`, then use it. | A crate that rolls three items. |
| E2 | `/ftbquests reload` | No errors in chat or the log; the fourteen chapters are still there. |
| E3 | `/give @s ftbquests:lootcrate[ftbquests:loot_crate="epic_bag"]` and `/give @s ftbquests:lootcrate[ftbquests:loot_crate="legendary_bag"]`, then use each. | Each rolls three items. None is a key, a tier ore or ingot, a planet metal, a Piglich Heart or a boss drop. |

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
| H6 | Creative | `/ftbquests reload` | No errors; fourteen chapters (Trunk: Start Here, Overworld, Nether, Twilight Forest, The Undergarden, The End, The Other, Space; Spurs: The Aether, Cataclysm, The Otherside, The Bumblezone, Eternal Starlight; Shop). |

## I. Tier 5: The Other

Teams: `/ftbteams party create <name>`, then `/ftbteams party invite <player>`; the invited player runs `/ftbteams party join <inviter's name>`. A party created by a player who already unlocked The Other starts unlocked. Everyone in the party shares one unlock.

| # | Kind | Do | Expected |
|---|---|---|---|
| I1 | Server | Look up the Key to The Other in JEI; hover it. | End Focus, Vibranium ingot, Advanced Machine Frame, Essence of the Bees, Dragon Egg, one of each. The tooltip explains the two clicks. |
| I2 | Server | Place a Teleport Pad in the Nether. Before anyone on your team has used a key, sneak and right-click it with both hands empty. | You stay in the Nether. The action bar says "Locked. Right-click this pad holding a Key to The Other." |
| I3 | Creative | Right-click the Nether pad (no sneaking) holding two Keys to The Other (on the server this costs two full keys). If a second team can try it: key in the off hand, main hand empty. | One key is used up and the other stays. The action bar says "The Other is open to your team. Sneak and right-click the pad with both hands empty to travel." You stay in the Nether. |
| I4 | Server | Sneak and right-click the pad with both hands empty. Then a teammate in the same party does the same without a key. | Both of you arrive in The Other; "Into The Other" completes in the questbook. |
| I5 | Server | A player on a team that has not used a key: sneak-click the Nether pad, then `/tpa` to someone standing in The Other and have them accept. | The pad gives the Locked message. The `/tpa` gives "Your team has not unlocked The Other." and you stay where you were. |
| I6 | Server | Sneak-click a Teleport Pad placed in the End, then one placed in the Overworld. | End: "The Beyond is closed in Confluence." and you stay in the End. Overworld: you go to the Mining Dimension as before. |
| I7 | Server | In The Other, look for Unobtainium ore in the ancient stone between y 8 and y 128, in chunks nobody visited before 0.3.0. Mine it with a Vibranium pickaxe, then try a Resonarium or Forgotten pickaxe on it and on Vibranium ore. | About one ore per chunk; the Vibranium pickaxe gets Raw Unobtainium Ore. The Resonarium and Forgotten pickaxes break both ores slowly and drop nothing. |
| I8 | Server | Find an ancient pyramid in The Other Soul Sand Valley and fight Piglichs there, wearing no gold. | Report how often they spawn, which attacks they use (melee, fireball volleys), whether Witches show up when you hit one, and how long a kill takes. Each Piglich drops exactly one Piglich Heart. |
| I9 | Server | Fill a bucket with soul lava in The Other (the "Soul Lava" quest says where). | A Soul Lava Bucket; the quest completes. |
| I10 | Server | At a Ritual Brazier, run Summon Wilden augmented with a Wilden Spike, a Wilden Horn and a Wilden Wing; kill the Wilden Chimera. | One Wilden Tribute drops. Report how hard the fight was (one Tribute makes four Ultimate Control Circuits). |
| I11 | Server | JEI: Ultimate Control Circuit. Then craft it. | Crafting only: 4 Elite Control Circuits, 2 atomic alloy, 2 Unobtainium ingots and a Wilden Tribute make 4 circuits. No other recipe makes it. |
| I12 | Server | JEI: QIO Drive Array, QIO Importer, QIO Exporter, QIO Drive, QIO Redstone Adapter, Quantum Entangloporter, Chemical Dissolution Chamber, Chemical Washer, Chemical Crystallizer. | Each takes Elite Control Circuits where it used to take ultimate ones. |
| I13 | Server | JEI: Digital Miner. | Its circuit is an Ultimate Control Circuit (it used to take a basic one). |
| I14 | Server | JEI: Supreme Machine Frame. | Dissolution Chamber, 135 mB ether gas, 300 ticks: an Advanced Machine Frame, 2 plastic, a nitro crystal, an Ultimate Control Circuit, 2 Unobtainium ingots and an Unobtainium - Allthemodium Alloy Ingot. |
| I15 | Server | JEI: the three alloy ingots. | Unobtainium - Allthemodium: Enchanting Apparatus, Unobtainium ingot in the middle; Allthemodium ingot, Piglich Heart and the four elemental essences on the pedestals; 10,000 Source. Vibranium - Allthemodium: Energizing Orb; Allthemodium ingot, Vibranium ingot, Piglich Heart, Block Of Nitro Crystal; 1,000,000,000 FE. Unobtainium - Vibranium: Dissolution Chamber, 100 mB soul lava, 200 ticks; 4 pink slime, Vibranium ingot, Unobtainium ingot, Piglich Heart. |
| I16 | Server | JEI: Inscriber, Charger, ME Controller, ME Drive, ME Import Bus, ME Export Bus, ME Terminal. | Inscriber: 4 HDPE sheets, 2 pistons, 2 copper, a Supreme Machine Frame. Charger: 5 knightmetal, 2 copper. Controller: 2 fluix crystals, a forgotten ingot, 2 engineering processors, a Supreme frame, 2 Sky Stone Blocks, an Inventory Connector. Drive: 4 iron, 2 engineering processors, 2 Fluix ME Glass Cables, a QIO Drive Array. Import / Export Bus: QIO Importer / Exporter, Annihilation / Formation Core, 2 iron, a piston. Terminal: Illuminated Panel, Formation Core, Supreme frame, Annihilation Core, 2 logic processors, QIO Dashboard. |
| I17 | Creative | Mekanism Combiner: Unobtainium Ore (1), Raw Unobtainium Ore (3) and a Block of Raw Unobtainium (1), each with one Etrium Ingot. Then look up Unobtainium Ore's uses. | 5, 10 and 30 Unobtainium Crystals. The ore → dirty slurry route is gone from JEI. |
| I18 | Creative | `/summon minecraft:wither` next to Vibranium ore and Unobtainium ore, and hit it. | The Wither breaks the blocks around it but leaves both ores. |
| I19 | Creative | A furnace and a blast furnace, each with Raw Unobtainium Ore and fuel. Then a filled Flamethrower (creative inventory) in Heat mode on Allthemodium ore and on iron ore. | The furnace does not cook it; the blast furnace makes an Unobtainium ingot. The Flamethrower leaves the Allthemodium ore alone and still cooks the iron ore. |
| I20 | Creative | An Energized Smelter powered by a Creative Energy Cube: Raw Vibranium Ore, then Vibranium Dust. | The raw ore does not cook (the smelter may refuse it outright); the dust cooks into a Vibranium Ingot. Raw tier metal still becomes ingots in a blast furnace or by Mekanism ore processing. |
| I21 | Server | Coin Shop after the key quest. | An Epic bag for 192 coins, repeatable; three items per bag. |
| I22 | Server | Waystone into The Other from a locked team. While in a party that has unlocked The Other, place a Waystone in The Other and activate it. Leave the party (`/ftbteams party leave`; a party owner can leave only as its last member), with a personal team that never used a key. Go back to the Nether by the pad, then to the Overworld, and warp to that waystone with a Warp Stone (hold right-click; a warp between dimensions costs 27 levels). | You do not stay in The Other: either the warp does not happen, or you land at the Overworld spawn. The action bar says "Your team has not unlocked The Other." If Waystones refuses first ("You do not have enough experience to teleport." or "You cannot warp between these worlds."), the gate was never reached: report which. |
| I23 | Server | Tablet of Assistance into The Other (two players on different teams). A player whose team has not unlocked The Other gets a Tablet of Assistance ready: JEI has its recipe, and its tooltip says to enchant it on a Grave Soul and engrave a player's name. The name is that of a player standing in The Other. Hold right-click with it. The player in The Other clicks Here in the chat request within two minutes. | The tablet user sees `Waiting for <name> to accept`, and the other player `Click Here to allow <name> to teleport to you`. After the click, the tablet user arrives in The Other and is moved to the Overworld spawn at once. The action bar says "Your team has not unlocked The Other." |
| I24 | Creative | Before using any key: `/execute in allthemodium:the_other run tp @s 0 150 0`, then `/execute in allthemodium:the_beyond run tp @s 0 150 0`. Start flying as soon as you arrive, because The Beyond may have no ground there. Then sneak and right-click, hands empty, a Teleport Pad placed in the Nether and one placed in the End. | Both teleports work and you stay: creative and spectator players are exempt from the travel and arrival checks. The pads still refuse. The Nether pad says "Locked. Right-click this pad holding a Key to The Other." The End pad says "The Beyond is closed in Confluence." |

## J. Tier 6: Space and Eternal Starlight

| # | Kind | Do | Expected |
|---|---|---|---|
| J1 | Server | JEI: Nasa Workbench. | An Ultimate Control Circuit, an Unobtainium - Allthemodium Alloy Ingot, a block of Unobtainium and an Unrealium Ingot where the torches and rods were, with the usual steel plates, crafting table and steel block. |
| J2 | Server | JEI: Space Suit, Oxygen Loader, Fuel Refinery, Steel Engine. | Space Suit: an elytra in the top middle. Oxygen Loader: an Electric Pump instead of the redstone block. Fuel Refinery: the four elemental essences, an Ultimate Control Circuit, a Vibranium - Allthemodium Alloy Ingot, 2 buckets and a furnace. Steel Engine: a nitro crystal, an Ultimate Control Circuit and an Unobtainium - Vibranium Alloy Ingot with the steel plates, engine frame and fan. The desh, ostrum and calorite engines are unchanged. |
| J3 | Server | Build a Tier 1 Rocket and a Launch Pad, fuel it and fly to the Moon. Then climb the ladder: Mars (tier 2), Venus and Mercury (tier 3), Glacio (tier 4). | Every rocket is Ad Astra's own recipe, and each tier reaches only its planets. Report anything that blocks the ladder and roughly how long each step took. |
| J4 | Server | Moon and Mars in a space suit with oxygen. Venus and Mercury in a space suit with oxygen plus Fire Resistance (or a netherite or jet suit). Glacio with no suit. | You survive each one. A plain space suit without Fire Resistance burns on Venus and Mercury. Glacio needs nothing. |
| J5 | Server | On Venus, stand under the open sky while it rains in the Overworld; then under a roof. | Acid rain hurts under the open sky whatever you wear. A roof, a rocket or a lander stops it. |
| J6 | Server | On Mars, build a Cryo Freezer, freeze ice, packed ice or blue ice into cryo fuel, and launch with it. | Cryo fuel needs no oil and no refinery. A launch takes 1000 mB of it instead of 3000 mB of fuel. |
| J7 | Server | JEI: Etrium Ingot and Etrium Plate; then make an ingot. | Ingot: Etrionic Blast Furnace, a desh, an ostrum and a calorite ingot and an Ice Shard. Plate: the Compressor. |
| J8 | Server | Mine Mercury ore on Mercury and Glacio ore on Glacio with a diamond pickaxe. | Each drops its shard. Report how easy they were to find. |
| J9 | Server | Summon the Echo of Tyros with a Cinderous Soulcaller at a Cinderous Soul Rune and kill it. | One Divine Soulshard per kill; the Soulcaller is used up. |
| J10 | Server | JEI: Astral Focus. | Enchanting Apparatus: Etrium Ingot in the middle; Divine Soulshard, Mercury Shard and Glacio Shard on the pedestals; no Source. |
| J11 | Server | JEI: Wireless Receiver, Crafting Unit, ME Pattern Provider, Molecular Assembler, ME Pattern Encoding Terminal. | Receiver: a fluix pearl, 3 desh, a quartz fiber. Crafting Unit: 4 fluix crystals, a calculation processor, an ostrum ingot, a Supreme Machine Frame, a Fluix ME Glass Cable, a logic processor. Pattern Provider: an ostrum ingot in the centre. Assembler and Encoding Terminal: Applied Energistics' own. |
| J12 | Server | Eternal Starlight: at a Portal Ruins structure in the Overworld (Common, Forest, Desert, Jungle or Cold Portal Ruins), beat The Gatekeeper. Clear the five centre cells of the Chiseled Voidstone frame and light it with the Orb of Prophecy. | "The Gatekeeper" quest completes when you win (advancement "Duke it out!"). The Orb stays in your hand and you arrive in Starlight. Report how hard the Gatekeeper was. |
| J13 | Server | In Starlight, kill the Starlight Golem (Golem Forge) and the Lunar Monstrosity (Cursed Garden); make an Unrealium Ingot. | The Starlight Golem quest completes on the kill ("Ancient Wisdom"). The Lunar Monstrosity drops 3–4 Soul Dew. Unrealium takes deepsilver, golem steel, malarite and Soul Dew. |
| J14 | Server | Coin Shop after Mercury. | A Legendary bag for 384 coins, repeatable; three items per bag. |

## F. Opinions we want

| # | Question |
|---|---|
| F1 | Fire charges cannot be crafted at all in v0.1. Fine, or should there be a Nether-only recipe? |
| F2 | The Common bag can give osmium ingots and source gems, the two inputs of the Nether key. Too generous? |
| F3 | The server runs on Easy right now. What difficulty do you want? |
| F4 | Anything too grindy, too cheap, or confusing in the quest text. |


