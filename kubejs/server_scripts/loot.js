// Loot edits (spec §4.3 and tree closures). LootJS 3.7.
LootJS.lootTables(event => {
  // D1.1 closure: ruined portals no longer hand out the Nether key's vanilla forms.
  event.getLootTable('minecraft:chests/ruined_portal').removeItem('minecraft:flint_and_steel')
  event.getLootTable('minecraft:chests/ruined_portal').removeItem('minecraft:fire_charge')

  // D2.3: the Allthemodium smithing template rides with the ore (spec §4.3). Pool 3 — the valuable pool holding the
  // knightmetal ingot — is index 2: MutableLootTable.getPool(int) is 0-based (`if (index < 0 || index >= pools.size())
  // return null; return new MutableLootPool(pools.get(index))`,
  // https://raw.githubusercontent.com/AlmostReliable/lootjs/1.21.1/src/main/java/com/almostreliable/lootjs/loot/table/MutableLootTable.java),
  // and twilightforest-1.21.1-4.8.3345-universal.jar!data/twilightforest/loot_table/stronghold_cache.json has exactly
  // three pools with knightmetal in the third (research/phase6-tier0-2-ids-2.md §T1).
  // addEntry takes the item id string (§M3).
  // getPool returns null when the table has fewer pools than expected (a future TF version or datapack); fall back to
  // the first pool rather than throw inside the LootJS callback.
  const cache = event.getLootTable('twilightforest:stronghold_cache')
  const pool = cache.getPool(2) || cache.firstPool()
  pool.addEntry(IDS.allthemodium.template)
})
