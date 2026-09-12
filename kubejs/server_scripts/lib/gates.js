// Remove-and-re-add helpers (spec §2.1). Every id is confluence:<tier>/<name>.
const gate = {
  // Replace a crafting-grid recipe: remove every recipe producing `output`, add ours.
  replaceShaped(event, id, output, pattern, keys) {
    event.remove({ output: output })
    event.shaped(Item.of(output), pattern, keys).id(id)
  },
  replaceShapeless(event, id, output, inputs) {
    event.remove({ output: output })
    event.shapeless(Item.of(output), inputs).id(id)
  },
  // Remove by id (string or regex) without adding anything (bypass closures).
  remove(event, filter) { event.remove(filter) },
  // Any mod recipe type by JSON; removes recipes producing `output` first when given.
  custom(event, id, json, output) {
    if (output) event.remove({ output: output })
    event.custom(json).id(id)
  },
}
