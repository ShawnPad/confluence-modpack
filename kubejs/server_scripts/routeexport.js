// Dev-only route export (v1.0 spec §6.1 "sources: (generated)", §10 item 12; v1.0 plan Task 13). Writes
// kubejs/exported/ma_crops.json, {crops: [{id, enabled, seeds, essence, crux, material, biomes}]}: every Mystical Agriculture
// crop the registry holds (Agradditions registers into the same registry), for tools/route_generated.py. Runs only with
// -Dconfluence.dev=true (lib/dev.js), like dump.js and tagcheck.js; production logs the skip line instead.
// API (MysticalAgriculture-1.21.1-8.0.28.jar, javap): com.blakebr0.mysticalagriculture.api.MysticalAgricultureAPI
//   .getCropRegistry() -> ICropRegistry; .getCrops() -> List<Crop>; Crop.getId() ResourceLocation, isEnabled(),
//   getSeedsItem(), getEssenceItem(), getCruxBlock() (Block, null when the crop has none), getLazyIngredient() ->
//   LazyIngredient.getId() String (null for EMPTY), isTag(); getRequiredBiomes() -> Set<ResourceLocation>.
// Ids: net.minecraft.core.registries.BuiltInRegistries.ITEM.getKey(item). KubeJS's class filter allows both packages
// (ClassFilter.isAllowed0 allows any class no deny rule names; v1.0 plan Task 13).
// JsonIO.write(Path, JsonElement) (kubejs-neoforge-2101.7.2-build.377.jar, javap): the JS object reaches it through
// JsonUtils.objectOf, which calls JsonUtils.of on every map value, so nested objects and arrays are written as such.
if (!CONFLUENCE_DEV) console.log('confluence routeexport: skipped (confluence.dev unset)')
else ServerEvents.loaded(event => {
  const api = Java.loadClass('com.blakebr0.mysticalagriculture.api.MysticalAgricultureAPI')
  const registries = Java.loadClass('net.minecraft.core.registries.BuiltInRegistries')
  const out = []
  api.getCropRegistry().getCrops().forEach(crop => {
    const crux = crop.getCruxBlock()
    // A crux block with no item form maps to minecraft:air through asItem(); the route tools want null for "no crux item".
    const cruxItem = crux ? String(registries.ITEM.getKey(crux.asItem())) : null
    const lazy = crop.getLazyIngredient()
    const lazyId = lazy ? lazy.getId() : null
    const biomes = []
    crop.getRequiredBiomes().forEach(b => { biomes.push(String(b)) })
    biomes.sort()
    out.push({
      id: String(crop.getId()),
      enabled: crop.isEnabled() == true,
      seeds: String(registries.ITEM.getKey(crop.getSeedsItem())),
      essence: String(registries.ITEM.getKey(crop.getEssenceItem())),
      crux: cruxItem === 'minecraft:air' ? null : cruxItem,
      material: lazyId ? { id: String(lazyId), tag: lazy.isTag() == true } : null,
      biomes: biomes,
    })
  })
  JsonIO.write('kubejs/exported/ma_crops.json', { crops: out })
  console.log('confluence routeexport: ' + out.length + ' Mystical Agriculture crops')
})
