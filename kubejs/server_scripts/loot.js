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
  // Weight 45: the pool's 13 entries total weight 575 (knightmetal and the four weapons 75 each, the eight books 25
  // each), so a bare addEntry (default weight 1) was 1 chest in 576 — issue #1 C10 saw none in 30 rolls. 45/620 is one
  // cache in 13.8, the "about 1 in 14" the plan and PLAYTEST promised. LootEntry.of(...).withWeight(int) is
  // lootjs-neoforge-1.21.1-3.7.0.jar!com/almostreliable/lootjs/core/entry/{LootEntry,SimpleLootEntry}.class (javap).
  const cache = event.getLootTable('twilightforest:stronghold_cache')
  const pool = cache.getPool(2) || cache.firstPool()
  pool.addEntry(LootEntry.of(IDS.allthemodium.template).withWeight(45))

  // [D2.3] closure: Allthemodium's own template sources outside the tier dimensions (Ancient City suspicious clay →
  // `allthemodium:arch`, bastion suspicious soul sand → `allthemodium:arch2`; see IDS.allthemodium.strayTemplateTables
  // in lib/ids.js for the jar paths). Emptied, so the Allthemodium template exists only in Twilight stronghold caches and
  // the Vibranium one waits for its v0.2 Undergarden table. The brushable blocks still generate; they yield nothing.
  IDS.allthemodium.strayTemplateTables.forEach(id => event.getLootTable(id).clear())
})
