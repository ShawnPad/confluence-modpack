// Pack items (spec §2.5) and the two feature ore blocks (spec §4.2, D56).
StartupEvents.registry('item', event => {
  event.create('twilight_key').displayName('Twilight Key').maxStackSize(16)
  event.create('other_key').displayName('Key to The Other').maxStackSize(16)
  event.create('end_focus').displayName('End Focus').maxStackSize(16)
  event.create('astral_focus').displayName('Astral Focus').maxStackSize(16)
  event.create('confluence_catalyst').displayName('Confluence Catalyst').maxStackSize(16)
  event.create('coin').displayName('Confluence Coin').maxStackSize(64)
  event.create('mercury_shard').displayName('Mercury Shard').maxStackSize(64)
  event.create('glacio_shard').displayName('Glacio Shard').maxStackSize(64)
})

StartupEvents.registry('block', event => {
  event.create('mercury_ore').displayName('Mercury Ore')
    .hardness(3).resistance(3).requiresTool()
    .tagBlock('minecraft:mineable/pickaxe', 'minecraft:needs_diamond_tool')
    .drops(() => BlockDrops.createDefault(Item.of('kubejs:mercury_shard', 1)))
  event.create('glacio_ore').displayName('Glacio Ore')
    .hardness(3).resistance(3).requiresTool()
    .tagBlock('minecraft:mineable/pickaxe', 'minecraft:needs_diamond_tool')
    .drops(() => BlockDrops.createDefault(Item.of('kubejs:glacio_shard', 1)))
})
