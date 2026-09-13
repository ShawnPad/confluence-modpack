// priority: 1
// Loot helpers. The priority header loads this before every other server script, exactly as lib/ids.js does.

// Adds one weighted entry to an existing pool of a loot table, or logs loudly and skips. A silent fallback to pool 0 was the
// failure mode behind issue #1 C10 (loot.js comment): the entry lands in an always-rolling junk pool at a fraction of the rate.
function addToPool(event, tableId, index, itemId, weight) {
  const table = event.getLootTable(tableId)
  const pool = table.getPool(index)
  if (!pool) { console.error('confluence loot: ' + tableId + ' has no pool ' + index + '; ' + itemId + ' NOT added'); return false }
  pool.addEntry(LootEntry.of(itemId).withWeight(weight))
  return true
}
