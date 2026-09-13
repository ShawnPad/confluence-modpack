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
  // addEntry takes the item id string (§M3); addToPool (lib/loot.js) logs and skips if that pool is gone in a future
  // TF version or a datapack, rather than quietly retargeting pool 0.
  // Weight 45: the pool's 13 entries total weight 575 (knightmetal and the four weapons 75 each, the eight books 25
  // each), so a bare addEntry (default weight 1) was 1 chest in 576 — issue #1 C10 saw none in 30 rolls. 45/620 is one
  // cache in 13.8, the "about 1 in 14" the plan and PLAYTEST promised. LootEntry.of(...).withWeight(int) is
  // lootjs-neoforge-1.21.1-3.7.0.jar!com/almostreliable/lootjs/core/entry/{LootEntry,SimpleLootEntry}.class (javap).
  addToPool(event, IDS.twilight.strongholdCache, 2, IDS.allthemodium.template, 45)

  // [D2.3] closure: Allthemodium's own template sources outside the tier dimensions (Ancient City suspicious clay →
  // `allthemodium:arch`, bastion suspicious soul sand → `allthemodium:arch2`; see IDS.allthemodium.strayTemplateTables
  // in lib/ids.js for the jar paths). Emptied, so the only loot source for the Allthemodium template is the Twilight
  // stronghold cache and for the Vibranium one the Undergarden catacombs pool below (D86); both have self-gated copy
  // recipes in the ATM jar, deliberately kept (D93) -- allthemodium-3.0.1_mc_1.21.1.jar!data/allthemodium/recipe/
  // smithing/{allthemodium,vibranium}_upgrade_smithing_template.json, each an existing template + 7 ingots + 1 stone
  // (netherite/deepslate, Allthemodium/ancient stone) for 2. The brushable blocks still generate; they yield nothing.
  IDS.allthemodium.strayTemplateTables.forEach(id => event.getLootTable(id).clear())

  // D3.3 (D86): the Vibranium template rides in Undergarden catacombs chests. undergarden:chests/catacombs has
  // three pools; pool index 2 is the valuable pool (minecraft:empty 8, forgotten_upgrade_smithing_template 3,
  // forgotten_nugget 1 = 12; The_Undergarden-1.21.1-0.9.6.jar!data/undergarden/loot_table/chests/catacombs.json,
  // phase7-undergarden-worldgen-loot.md §4). Weight 2 → 2/14, one chest in 7 (user choice, D86); the added weight
  // dilutes the pool's own entries — forgotten template 3/12 → 3/14, empty 8/12 → 8/14. Same addToPool guard as
  // the Twilight cache above.
  addToPool(event, IDS.undergarden.catacombsChest, 2, IDS.allthemodium.vibraniumTemplate, 2)
})
