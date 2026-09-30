// priority: -1
// Writes every recipe's id/type/output and its full JSON to kubejs/exported/recipes.json at each /reload (test harness).
// The header above makes this file load last (ScriptFile.compareTo: priority descending, then path), and ServerEvents.recipes
// handlers run in load order (EventHandlerContainer.add/handle), so this runs after tiers/*.js and the dump is the post-gate set.
// forEachRecipe walks originalRecipes only and skips r.removed (RecipesKubeEvent.recipeStream); the recipes the tier scripts add
// live in the public field event.addedRecipes, so both are dumped. Sources: research/phase6-recipe-dump-and-fire-charge.md §1.
// `json` (v0.3): kubejs-neoforge-2101.7.2-build.377.jar dev/latvian/mods/kubejs/recipe/KubeRecipe has the public field
// `JsonObject json` and `KubeRecipe serializeChanges()`, which for a new or changed recipe writes its values into `json`
// (serialize(), plus type and _kubejs_changed_marker) and for an untouched original leaves the datapack file's JSON; either way
// it returns the recipe. RecipesKubeEvent.applyChanges calls serializeChanges() on every kept recipe after this handler and then
// reads `json`, and a second call rewrites the same values, so calling it here changes nothing that loads. String(JsonObject) is
// gson's compact toString(). `json` is '' only when serialize() throws (it throws KubeRuntimeException for a null value it must
// write) or this script errors; such rows are counted and the log line names the first error. A component that fails to encode
// is logged at ERROR by KubeJS itself (RecipeComponent.writeToJson -> ConsoleJS.SERVER.error), which fails tools/server_boot.sh,
// and its key is left out of an otherwise partial `json`.
// Compare recipe types by the `type` column, not json.type: at 0.2.1, 469 bodies (Mystical Agriculture 387, MA Agradditions 49,
// Tombstone 29, Explorer's and Nature's Compass 2 each) carry an un-namespaced type such as "crafting_shaped", and bodies may
// carry neoforge:conditions (2553 at 0.2.1).
ServerEvents.recipes(event => {
  const rows = []
  let noJson = 0
  let firstErr = ''
  const row = r => {
    let out = ''
    try { out = String(r.get('result') || r.get('output') || '') } catch (e) { out = '' }
    let json = ''
    // rhino 2101.2.7: a const declared directly inside try throws "redeclaration of var" at runtime (the catch hid it); declare outside
    let j = null
    try { j = r.serializeChanges().json; json = j == null ? '' : String(j) } catch (e) { json = ''; if (!firstErr) firstErr = String(e) }
    if (json === '') noJson++
    // r.type is a RecipeTypeFunction (a Rhino Scriptable), so r.type.id is undefined from JS; KubeRecipe.toString() is '<id>[<type>]'.
    const s = String(r)
    return { id: String(r.getOrCreateId()), type: s.slice(s.lastIndexOf('[') + 1, s.length - 1), output: out, json: json }
  }
  event.forEachRecipe({}, r => rows.push(row(r)))
  event.addedRecipes.forEach(r => rows.push(row(r)))
  JsonIO.write('kubejs/exported/recipes.json', rows)
  console.log('confluence dump: ' + rows.length + ' recipes, ' + noJson + ' without json' +
    (noJson > 0 ? ' (first error: ' + (firstErr || 'none thrown; json was null') + ')' : ''))
})
