// Script gates (spec §2.3). Only the Twilight tag swap ships in v0.1; the Other pad handler is tier 5.
ServerEvents.tags('item', event => {
  event.get(IDS.twilight.activatorTag).remove('#c:gems/diamond').add(IDS.pack.twilightKey)
})
