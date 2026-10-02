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
//
// v0.3 Task 8c: it also writes kubejs/exported/tag_members.json, {"minecraft:block": {tag: [block id, ...]}}, the members of the
// D112 block tags, so tools/check_tags.py can check them by name (spec §7 D112; counts alone cannot tell the wrong 27 blocks
// from the right ones). The tags are lib/ids.js's IDS.tierOres lists, the ones check_tags.py reads: incorrectForTags (the nine
// deny tags), needsToolTags and alloyToolTagEmpty (ATM's four needs tags) and immuneTags (wither_immune and the four Cataclysm
// immune tags). Same walk as the counts; member API from server-1.21.1-20240808.144430-srg.jar (`javap`):
//   net/minecraft/core/HolderSet.stream() -> Stream<Holder<T>> (HolderSet$Named extends HolderSet$ListBacked, which has it)
//   net/minecraft/core/Holder.getRegisteredName() -> String: unwrapKey().map(k -> k.location().toString())
//     .orElse("[unregistered]") (`javap -c`, offsets 1-16), so each member is written as its registry id.
//
// v0.3 Task 8c round 2 (R3): it also writes kubejs/exported/item_tag_members.json, {"minecraft:item": {tag: [item id, ...]}},
// the members of every bound item tag, empty ones included, from the same walk. tools/check_recipes.py reads it to expand a
// tag product (a recipe whose result is '#c:...' or {tag}) into the items it can give, and tools/check_tags.py checks that
// each list is as long as tags.json's count and that every bound item tag is there, so the file is this boot's.

// Rhino exposes a Java record component as a zero-arg method here, but KubeJS' type wrappers expose some as plain
// properties; accept either shape rather than betting on one.
const TAGCHECK_component = (obj, name) => {
  const v = obj[name]
  return typeof v === 'function' ? obj[name]() : v
}

// The registry and tags whose members are written (see the header). A tag id without its leading '#'.
const TAGCHECK_MEMBER_REGISTRY = 'minecraft:block'
// Every tag of this registry has its members written, to its own file (see the header).
const TAGCHECK_ITEM_REGISTRY = 'minecraft:item'
const TAGCHECK_bare = t => (String(t).charAt(0) === '#' ? String(t).substring(1) : String(t))
// The sorted registry ids of a tag's members (HolderSet.stream, Holder.getRegisteredName: see the header).
const TAGCHECK_members = holders => {
  const ids = []
  holders.stream().forEach(h => { ids.push(String(h.getRegisteredName())) })
  ids.sort()
  return ids
}
const TAGCHECK_memberTags = () => {
  const wanted = {}
  IDS.tierOres.incorrectForTags.concat(IDS.tierOres.needsToolTags, [IDS.tierOres.alloyToolTagEmpty], IDS.tierOres.immuneTags)
    .forEach(t => { wanted[TAGCHECK_bare(t)] = true })
  return wanted
}

ServerEvents.loaded(event => {
  const out = {}
  const wanted = TAGCHECK_memberTags()
  const members = {}
  const itemMembers = {}
  let memberTags = 0
  let itemTags = 0
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
      if (registryId === TAGCHECK_MEMBER_REGISTRY && wanted[id] === true) {
        members[id] = TAGCHECK_members(holders)
        memberTags++
      }
      if (registryId === TAGCHECK_ITEM_REGISTRY) {
        itemMembers[id] = TAGCHECK_members(holders)
        itemTags++
      }
    })
    out[registryId] = counts
    registries++
  })
  JsonIO.write('kubejs/exported/tags.json', out)
  const memberOut = {}
  memberOut[TAGCHECK_MEMBER_REGISTRY] = members
  JsonIO.write('kubejs/exported/tag_members.json', memberOut)
  const itemOut = {}
  itemOut[TAGCHECK_ITEM_REGISTRY] = itemMembers
  JsonIO.write('kubejs/exported/item_tag_members.json', itemOut)
  console.log('confluence tagcheck: ' + tags + ' tags in ' + registries + ' registries (' + empty + ' bound-but-empty); members of ' +
    memberTags + ' ' + TAGCHECK_MEMBER_REGISTRY + ' tags and all ' + itemTags + ' ' + TAGCHECK_ITEM_REGISTRY + ' tags')
})
