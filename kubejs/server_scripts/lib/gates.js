// Remove-and-re-add helpers (spec §2.1). Every id is confluence:<tier>/<name>.
const gate = {
  // Add a crafting-grid recipe with an explicit id, no removal.
  shaped(event, id, output, pattern, keys) { event.shaped(Item.of(output), pattern, keys).id(id) },
  shapeless(event, id, output, inputs) { event.shapeless(Item.of(output), inputs).id(id) },
  // Replace a crafting-grid recipe: remove every recipe producing `output`, add ours.
  replaceShaped(event, id, output, pattern, keys) {
    event.remove({ output: output })
    gate.shaped(event, id, output, pattern, keys)
  },
  replaceShapeless(event, id, output, inputs) {
    event.remove({ output: output })
    gate.shapeless(event, id, output, inputs)
  },
  // Remove by id (string or regex) without adding anything (bypass closures).
  remove(event, filter) { event.remove(filter) },
  // Any mod recipe type by JSON; removes recipes producing `output` first when given.
  custom(event, id, json, output) {
    if (output) event.remove({ output: output })
    event.custom(json).id(id)
  },
}
