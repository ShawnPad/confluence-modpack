# The pack's textures, one brief each

Generated from `art/briefs.json` by `tools/gen_preview.py`; edit the JSON, not this file. Rules in `art/STYLE.md`; how to hand work back in `art/CONTRIBUTING.md`. The images are the current PNGs at 8x, regenerated with `python3 tools/gen_textures.py --preview art/preview/x8`.

The pack ships tiers 0-2 today: the coin and the Twilight Key are in the game. Everything tagged (v0.2), (v0.3) or (v1.0) is designed but not built yet; the tag is the release it lands in. A "tier" is one rung of the pack's ladder of gated dimensions. The current PNGs are a baseline, not a constraint: redraw anything, keeping only the canvas rules (STYLE.md rules 1-3) and each family's shared silhouette (rule 6).

## One-offs

### Confluence Catalyst (`kubejs:confluence_catalyst`)

![confluence_catalyst at 8x](preview/x8/confluence_catalyst.png)

`kubejs/assets/kubejs/textures/item/confluence_catalyst.png` - item, family *single*.

**What it is:** The pack's final item, to be made at the Ars Nouveau Enchanting Apparatus; every mod's creative-tier item will be rewritten to consume one (v1.0).

**Where it is earned:** Planned recipe (v1.0): Etrium, the three Allthemodium alloys, a dragon egg, an Astral Focus, an AE2 wireless receiver and an AE2 crafting unit.

**What consumes it:** Every creative-tier recipe (v1.0).

**Drawing notes:** The signature texture and the pack's logo-in-waiting: three streams (ice = tech, purple = magic, green = exploration) meeting in an ember core. The only texture allowed four ramps. Spend your effort here first.

*Maintainer ref: tree node [X7.1].*

### Confluence Coin (`kubejs:coin`)

![coin at 8x](preview/x8/coin.png)

`kubejs/assets/kubejs/textures/item/coin.png` - item, family *single*.

**What it is:** The questbook currency, in the game today. Every quest pays a few; the Coin Shop chapter sells repeatable reward bags for them.

**Where it is earned:** Quest rewards, a few per quest; the reward bags can drop some too.

**What consumes it:** Coin Shop bag quests: 16 coins for a Common bag, 48 for an Uncommon bag. Rare bags arrive in v0.2, Epic and Legendary in v0.3.

**Drawing notes:** Stack of 64, so it must read at 16 px next to a number. One dark C in the centre; keep it plain. Also the Coin Shop chapter icon.

## Keys - the two dimension keys the pack adds (the other tiers reuse existing items); each is used up opening its dimension

### Twilight Key (`kubejs:twilight_key`)

![twilight_key at 8x](preview/x8/twilight_key.png)

`kubejs/assets/kubejs/textures/item/twilight_key.png` - item, family *keys*.

**What it is:** In the game today (tier 2). The only thing that opens a Twilight Forest portal in this pack; the diamond trigger is disabled. Thrown into the water pool like the vanilla diamond, one key per portal.

**Where it is earned:** Crafted from a netherite ingot, Aether zanite, a Mekanism advanced control circuit, an Ars Nouveau essence and a Cataclysm Monstrous Horn.

**What consumes it:** The portal pool (one per portal).

**Drawing notes:** Green ramp = Twilight Forest. The bow's ring and the two teeth are the silhouette the Other key must keep.

*Maintainer ref: tree node [D2.1].*

### Key to The Other (`kubejs:other_key`)

![other_key at 8x](preview/x8/other_key.png)

`kubejs/assets/kubejs/textures/item/other_key.png` - item, family *keys*.

**What it is:** Will be consumed at an Allthemodium Teleport Pad placed in the Nether to reach The Other, the tier-5 dimension (v0.3).

**Where it is earned:** Planned recipe (v0.3): a Vibranium ingot, a dragon egg, essence of the bees, an IF Advanced Machine Frame and an End Focus.

**What consumes it:** The Teleport Pad, once.

**Drawing notes:** Purple ramp = The Other. Same pixels as the Twilight key with the ramp swapped; change both keys together.

*Maintainer ref: tree node [D5.1].*

## Foci - Ars Nouveau Enchanting Apparatus products that gate the Other key and the catalyst

### End Focus (`kubejs:end_focus`)

![end_focus at 8x](preview/x8/end_focus.png)

`kubejs/assets/kubejs/textures/item/end_focus.png` - item, family *foci*.

**What it is:** The tier-4 magic composite: an Enchanting Apparatus product that will be an input of the Other key (v0.2).

**Where it is earned:** Planned Enchanting Apparatus recipe (v0.2): four Ars essences, dragon's breath, a Gauntlet of Guard, a Ritual of Binding charm, a source gem block, a Planarium.

**What consumes it:** The Other key recipe (v0.3).

**Drawing notes:** Dark purple gem (purple base / dark / deep) in a neutral frame. The frame is shared with the Astral Focus.

*Maintainer ref: tree node [M4.2].*

### Astral Focus (`kubejs:astral_focus`)

![astral_focus at 8x](preview/x8/astral_focus.png)

`kubejs/assets/kubejs/textures/item/astral_focus.png` - item, family *foci*.

**What it is:** The last focus: the magic-side input of the Confluence Catalyst, and the reason the two planet ores exist (v0.3).

**Where it is earned:** Planned Enchanting Apparatus recipe (v0.3): Etrium, a divine soulshard, a Mercury shard and a Glacio shard.

**What consumes it:** The Confluence Catalyst recipe (v1.0).

**Drawing notes:** Pale gold gem in the same frame as the End Focus. Should look like the end focus's bright sibling.

*Maintainer ref: tree node [M6.1].*

## Shards - drops of the two planet ores, the Astral Focus inputs

### Mercury Shard (`kubejs:mercury_shard`)

![mercury_shard at 8x](preview/x8/mercury_shard.png)

`kubejs/assets/kubejs/textures/item/mercury_shard.png` - item, family *shards*.

**What it is:** Dropped by Mercury Ore (the block already drops it); one of the two Astral Focus inputs, and nothing else will make it.

**Where it is earned:** Mining Mercury Ore on Mercury (Ad Astra) once the ore is placed there (v0.3).

**What consumes it:** The Astral Focus recipe (v0.3).

**Drawing notes:** Ember ramp. Same crystal as the Glacio shard; change both together.

*Maintainer ref: tree node [D6.7].*

### Glacio Shard (`kubejs:glacio_shard`)

![glacio_shard at 8x](preview/x8/glacio_shard.png)

`kubejs/assets/kubejs/textures/item/glacio_shard.png` - item, family *shards*.

**What it is:** Dropped by Glacio Ore (the block already drops it); the other Astral Focus input, and nothing else will make it.

**Where it is earned:** Mining Glacio Ore on Glacio (Ad Astra) once the ore is placed there (v0.3).

**What consumes it:** The Astral Focus recipe (v0.3).

**Drawing notes:** Ice ramp. Same crystal as the Mercury shard; change both together.

*Maintainer ref: tree node [D6.8].*

## Ores - the two pack blocks, one on Mercury and one on Glacio

### Mercury Ore (`kubejs:mercury_ore`)

![mercury_ore at 8x](preview/x8/mercury_ore.png)

`kubejs/assets/kubejs/textures/block/mercury_ore.png` - block, family *ores*.

**What it is:** Pack block that will generate only in Mercury's one biome, buried in small veins (v0.3; not placed yet). Drops Mercury Shards.

**Where it is earned:** Worldgen on Mercury (v0.3).

**What consumes it:** Mined for shards.

**Drawing notes:** Fully opaque, tiles on all four edges (check the corners against each other). Neutral stone base, ember flecks each with their own outline. Same base as Glacio Ore.

*Maintainer ref: tree node [D6.7].*

### Glacio Ore (`kubejs:glacio_ore`)

![glacio_ore at 8x](preview/x8/glacio_ore.png)

`kubejs/assets/kubejs/textures/block/glacio_ore.png` - block, family *ores*.

**What it is:** Pack block that will generate only in Glacio's two biomes, buried in small veins (v0.3; not placed yet). Drops Glacio Shards.

**Where it is earned:** Worldgen on Glacio (v0.3).

**What consumes it:** Mined for shards.

**Drawing notes:** Fully opaque, tiles. Same base as Mercury Ore, ice flecks.

*Maintainer ref: tree node [D6.8].*
