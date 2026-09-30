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
// gson's compact toString(). A recipe whose JSON cannot be produced gets json '' and is counted in the log line.
ServerEvents.recipes(event => {
  const rows = []
  let noJson = 0
  const row = r => {
    let out = ''
    try { out = String(r.get('result') || r.get('output') || '') } catch (e) { out = '' }
    let json = ''
    // rhino 2101.2.7: a const declared directly inside try throws "redeclaration of var" at runtime (the catch hid it); declare outside
    let j = null
    try { j = r.serializeChanges().json; json = j == null ? '' : String(j) } catch (e) { json = '' }
    if (json === '') noJson++
    // r.type is a RecipeTypeFunction (a Rhino Scriptable), so r.type.id is undefined from JS; KubeRecipe.toString() is '<id>[<type>]'.
    const s = String(r)
    return { id: String(r.getOrCreateId()), type: s.slice(s.lastIndexOf('[') + 1, s.length - 1), output: out, json: json }
  }
  event.forEachRecipe({}, r => rows.push(row(r)))
  event.addedRecipes.forEach(r => rows.push(row(r)))
  JsonIO.write('kubejs/exported/recipes.json', rows)
  console.log('confluence dump: ' + rows.length + ' recipes, ' + noJson + ' without json')
})
