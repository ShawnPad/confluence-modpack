// Loot edits (spec §4.3 and tree closures). LootJS 3.7.
LootJS.lootTables(event => {
  // D1.1 closure: ruined portals no longer hand out the Nether key's vanilla forms.
  event.getLootTable('minecraft:chests/ruined_portal').removeItem('minecraft:flint_and_steel')
  event.getLootTable('minecraft:chests/ruined_portal').removeItem('minecraft:fire_charge')
})
