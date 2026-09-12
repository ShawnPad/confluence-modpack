// priority: -1
// Writes every recipe id/type/output to kubejs/exported/recipes.json at each /reload (test harness).
// The header above makes this file load last (ScriptFile.compareTo: priority descending, then path), and ServerEvents.recipes
// handlers run in load order (EventHandlerContainer.add/handle), so this runs after tiers/*.js and the dump is the post-gate set.
// forEachRecipe walks originalRecipes only and skips r.removed (RecipesKubeEvent.recipeStream); the recipes the tier scripts add
// live in the public field event.addedRecipes, so both are dumped. Sources: research/phase6-recipe-dump-and-fire-charge.md §1.
ServerEvents.recipes(event => {
  const rows = []
  const row = r => {
    let out = ''
    try { out = String(r.get('result') || r.get('output') || '') } catch (e) { out = '' }
    // r.type is a RecipeTypeFunction (a Rhino Scriptable), so r.type.id is undefined from JS; KubeRecipe.toString() is '<id>[<type>]'.
    const s = String(r)
    return { id: String(r.getOrCreateId()), type: s.slice(s.lastIndexOf('[') + 1, s.length - 1), output: out }
  }
  event.forEachRecipe({}, r => rows.push(row(r)))
  event.addedRecipes.forEach(r => rows.push(row(r)))
  JsonIO.write('kubejs/exported/recipes.json', rows)
  console.log('confluence dump: ' + rows.length + ' recipes')
})
