// Exports every bound tag (id -> element count) for every registry to kubejs/exported/tags.json, so
// tools/check_tags.py can prove that no recipe/script in the pack points at an empty tag. An empty-tag
// ingredient loads with zero KubeJS errors and is uncraftable in game (D69, the `#c:gems/zanite` defect).
//
// Event: ServerEvents.loaded. Jar evidence (kubejs-neoforge-2101.7.2-build.377.jar, `javap -p`):
//   dev/latvian/mods/kubejs/plugin/builtin/event/ServerEvents  -> `EventHandler LOADED`, bound to the JS name
//     "loaded" (the constant-pool string at the GROUP.add call for LOADED), event object ServerKubeEvent.
//   dev/latvian/mods/kubejs/server/KubeJSServerEventHandler.serverStarting(ServerStartingEvent) -> the only
//     poster of ServerEvents.LOADED. ServerStartingEvent fires after MinecraftServer.loadLevel(), i.e. after the
//     first datapack reload has run TagManager and bound tags -- unlike ServerEvents.tags (the tag-*modification*
//     event) and unlike ServerEvents.recipes, whose ordering against tag binding is not guaranteed.
//   dev/latvian/mods/kubejs/server/ServerKubeEvent -> `public final MinecraftServer server`.
// Registry/tag API from server-1.21.1-20240808.144430-srg.jar (`javap`):
//   net/minecraft/server/MinecraftServer.registryAccess() -> RegistryAccess$Frozen
//   net/minecraft/core/RegistryAccess.registries() -> Stream<RegistryAccess$RegistryEntry<?>>
//   net/minecraft/core/RegistryAccess$RegistryEntry -> record key():ResourceKey, value():Registry
//   net/minecraft/core/Registry.getTags() -> Stream<com.mojang.datafixers.util.Pair<TagKey<T>, HolderSet$Named<T>>>
//   net/minecraft/core/HolderSet.size() -> int
// `.forEach(jsLambda)` over a Java Stream/List is the same coercion dump.js already relies on.
//
// ServerEvents.loaded does NOT re-fire on /reload, so the export is a fresh-boot artifact -- which is exactly how
// tools/server_boot.sh runs the pack.

// Rhino exposes a Java record component as a zero-arg method here, but KubeJS' type wrappers expose some as plain
// properties; accept either shape rather than betting on one.
const TAGCHECK_component = (obj, name) => {
  const v = obj[name]
  return typeof v === 'function' ? obj[name]() : v
}

ServerEvents.loaded(event => {
  const out = {}
  let registries = 0
  let tags = 0
  let empty = 0
  event.server.registryAccess().registries().forEach(entry => {
    const registryId = String(TAGCHECK_component(TAGCHECK_component(entry, 'key'), 'location'))
    const counts = {}
    TAGCHECK_component(entry, 'value').getTags().forEach(pair => {
      const tagKey = typeof pair.getFirst === 'function' ? pair.getFirst() : pair.first
      const holders = typeof pair.getSecond === 'function' ? pair.getSecond() : pair.second
      const id = String(TAGCHECK_component(tagKey, 'location'))
      const size = holders.size()
      counts[id] = size
      tags++
      if (size === 0) empty++
    })
    out[registryId] = counts
    registries++
  })
  JsonIO.write('kubejs/exported/tags.json', out)
  console.log('confluence tagcheck: ' + tags + ' tags in ' + registries + ' registries (' + empty + ' bound-but-empty)')
})
