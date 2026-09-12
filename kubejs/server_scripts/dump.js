// Writes every recipe id/type/output to kubejs/exported/recipes.json at each /reload (test harness).
ServerEvents.recipes(event => {
  const rows = []
  event.forEachRecipe({}, r => {
    let out = ''
    try { out = String(r.get('result') || r.get('output') || '') } catch (e) { out = '' }
    // r.type is a RecipeTypeFunction (a Rhino Scriptable), so r.type.id is undefined from JS; KubeRecipe.toString() is '<id>[<type>]'.
    const s = String(r)
    rows.push({ id: String(r.getOrCreateId()), type: s.slice(s.lastIndexOf('[') + 1, s.length - 1), output: out })
  })
  JsonIO.write('kubejs/exported/recipes.json', rows)
  console.log('confluence dump: ' + rows.length + ' recipes')
})
