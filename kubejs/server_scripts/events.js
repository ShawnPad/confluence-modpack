// Script gates (spec §2.3). Only the Twilight tag swap ships in v0.1; the Other pad handler is tier 5.
ServerEvents.tags('item', event => {
  event.get(IDS.twilight.activatorTag).remove('#c:gems/diamond').add(IDS.pack.twilightKey)
})

// ---- v0.3 tier-ore breakers (spec §7 D112 (a) and (b)). Block-tag edits, so they live here with the other tag edit.
// KubeJS 2101 API (kubejs-neoforge-2101.7.2-build.377.jar, javap): ServerEvents.tags takes a registry target; the string
// 'block' becomes ResourceKey.createRegistryKey(ResourceLocation.parse('block')) = minecraft:block (EventTargetType
// .toRegistryKey). TagKubeEvent.add(ResourceLocation, Object...) -> TagWrapper.add(Object...) -> TagEventFilter.unwrap: Rhino
// converts a JS array passed as the last argument to the Object... varargs array itself (rhino-2101.2.7-build.85.jar
// NativeJavaMethod.call: a NativeArray last argument goes through Context.jsToJava to the varargs type), and unwrap wraps an
// array whose length is not 1 in Arrays.asList, which TagEventFilter.of walks as a Collection, one filter per element. A
// '#ns:path' string adds TagEntry.tag(ns:path), a tag reference resolved when tags bind; a plain id adds TagEntry.element(id) only when
// that block is registered (otherwise it is skipped with at most a warning, hence the tags.json counts in the verify step).
// TagKubeEvent.get creates a tag that has no file (computeIfAbsent), which the two Cataclysm deny tags need. The first
// argument is a ResourceLocation, so a tag held with its leading '#' goes through tagId().
ServerEvents.tags('block', event => {
  // (a) Nine tool tiers ship an EMPTY deny tag (boot tags.json: 0 blocks each; GAP §2.4), so they mine every tier ore:
  // Cataclysm's Tooltier (L_Ender's Cataclysm 1.21.1-3.33.jar com/github/L_Ender/cataclysm/items/Tooltier: SimpleTier with
  // BlockTags.create(cataclysm:needs_monstrosity_tool / needs_black_steel_tool) as the incorrect-for tag), the Forgotten tools,
  // the Resonarium and Warden tools, the Atomic Disassembler and Meka-Tool, and the two Supremium paxel tiers. Each gets
  // exactly what ATM adds to vanilla's netherite deny tag (allthemodium-3.0.1_mc_1.21.1.jar!data/minecraft/tags/block/
  // incorrect_for_netherite_tool.json = [#c:needs_allthemodium_tool, #c:needs_vibranium_tool, #c:needs_unobtainium_tool,
  // #c:needs_allthemodiumalloy_tool]). Vibranium ore is in the first (4 blocks), Unobtainium ore in the second (3), the third
  // holds ancient-stone decoratives and the alloy blocks (20); Allthemodium ore is only in #neoforge:needs_netherite_tool.
  // So these tools then mine Allthemodium ore and nothing above it, like netherite; each tag ends at 27 blocks.
  // Not nested: minecraft:incorrect_for_netherite_tool itself, because The_Undergarden-1.21.1-0.9.6.jar!data/minecraft/
  // tags/block/incorrect_for_netherite_tool.json adds #undergarden:needs_forgotten_tool to it, and nesting it would stop the
  // Forgotten pickaxe mining its own tier.
  // The fourth tag is bound but empty (ATM ships {"values": []}); it is nested for parity with ATM's list, and built from
  // the bare IDS string so tools/check_tags.py (which fails on a '#' literal that names an empty tag) does not look it up.
  const deny = IDS.tierOres.needsToolTags.concat(['#' + IDS.tierOres.alloyToolTagEmpty])
  IDS.tierOres.incorrectForTags.forEach(tag => event.add(tag, deny))

  // (b) The five tier-ore blocks join the Wither's immune tag (its body-break, blue skulls and a jarred Wither all check
  // minecraft:wither_immune and drop the raw item with no tool; GAP §2.3c) and the four Cataclysm boss immune tags
  // (L_Ender's Cataclysm 1.21.1-3.33.jar!data/cataclysm/tags/block/{ignis,maledictus,scylla,netherite_monstrosity}_immune.json).
  // No jar lists an ATM block in any of the five today (every wither_immune.json and the four Cataclysm files were read).
  // Benign spillover: two tags nest #minecraft:wither_immune, so they gain the five ores too (tags.json 142 -> 147, 265 -> 270).
  // twilightforest-1.21.1-4.8.3345-universal.jar!data/twilightforest/tags/block/block_and_chain_never_breaks.json (ChainBlock
  // .canBreakBlockAt refuses its blocks; GAP §2.3) and the_bumblezone-7.15.3+1.21.1-neoforge.jar!data/the_bumblezone/tags/
  // block/sentry_watcher/forced_never_destroy.json (SentryWatcherEntity stops at its blocks): both only protect a block.
  IDS.tierOres.immuneTags.forEach(tag => event.add(tagId(tag), IDS.tierOres.blocks))
})
