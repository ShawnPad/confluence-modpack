// Script gates and tag edits: the v0.1 Twilight activator tag swap, the v0.3 removes of allthemodium's unregistered tag
// entries (D132), the v0.3 tier-ore block tags (v0.3 spec §7, D112) and, at the end of this file, The Other's pad, travel
// and arrival checks (v0.3 spec §4.2-4.5).
ServerEvents.tags('item', event => {
  event.get(IDS.twilight.activatorTag).remove('#c:gems/diamond').add(IDS.pack.twilightKey)

  // v0.3 Task 8c (D132): allthemodium-3.0.1_mc_1.21.1.jar!data/minecraft/tags/item/enchantable/{bow,crossbow,equippable}.json
  // and data/c/tags/item/tools/{bow,crossbow,shield}.json name allthemodium:allthemodium_bow, unobtainium_crossbow and
  // vibranium_shield, which com/thevortex/allthemodium/registry/ModRegistry never registers (lib/ids.js has the evidence).
  // Each is a required entry, so vanilla's TagLoader.build drops all six tags, and with them every tag that requires one
  // (c:tools, c:enchantables, functionalstorage:armory_cabinet_insertable, twilightforest:lower_on_drying_rack): 20
  // "Couldn't load tag" ERRORs at boot, the three enchantable tags bound empty, and no bow or crossbow taking power, punch,
  // flame, infinity, multishot, piercing or quick_charge (supported_items in server-1.21.1-20240808.144430-extra.jar!data/
  // minecraft/enchantment/*.json). Removing just those entries lets the six tags load with everything else in them.
  // Why this lands in time (kubejs-neoforge-2101.7.2-build.377.jar, javap): TagLoaderMixin injects at the RETURN of
  // TagLoader.load, and TagLoaderKJS.kjs$customTags wraps the loaded EntryWithSource lists, posts ServerEvents.tags and puts
  // them back, so this edit is in the lists before TagLoader.build and KubeJS's own CachedTagLookup build read them. A
  // removal matches by id only: TagEventFilter$ID.testElementId is ResourceLocation.equals, with no registry lookup (only its
  // add checks the registry), so it removes an id no registry holds. Not a datapack tag file instead: NeoForge's tag `remove`
  // list is appended to the same entry list as optional removals, and build still fails on ATM's required entry; and
  // `replace: true` would also drop every other mod's entries in these tags (5 to 7 other jars write each of the six).
  // AllTheMods 10 ships the same six removes (AllTheMods/ATM-10, kubejs/server_scripts/Tweaks/tags.js).
  // An allthemodium version bump must re-check the three ids (lib/ids.js): if a later jar registers one, this silently
  // strips a real item from these tags. Deliberately unguarded (no Item.exists check, D132): that re-check is the safeguard.
  // tools/tests/test_item_tags.py pins the six (tag, id) pairs.
  IDS.allthemodium.unregisteredTagEntries.forEach(e => event.remove(tagId(e.tag), e.id))
})

// ---- v0.3 tier-ore breakers (spec §7 D112 (a) and (b)). Block-tag edits, so they live here with the other tag edits.
// KubeJS 2101 API (kubejs-neoforge-2101.7.2-build.377.jar, javap): ServerEvents.tags takes a registry target; the string
// 'block' becomes ResourceKey.createRegistryKey(ResourceLocation.parse('block')) = minecraft:block (EventTargetType
// .toRegistryKey). TagKubeEvent.add(ResourceLocation, Object...) -> TagWrapper.add(Object...) -> TagEventFilter.unwrap: Rhino
// converts a JS array passed as the last argument to the Object... varargs array itself (rhino-2101.2.7-build.85.jar
// NativeJavaMethod.call: a NativeArray last argument goes through Context.jsToJava to the varargs type), and unwrap wraps an
// array whose length is not 1 in Arrays.asList, which TagEventFilter.of walks as a Collection, one filter per element. A
// '#ns:path' string adds TagEntry.tag(ns:path), a tag reference resolved when tags bind; a plain id adds TagEntry.element(id) only when
// that block is registered (otherwise it is skipped with at most a warning, hence the tags.json counts in the verify step).
// TagKubeEvent.get creates a tag that has no file (computeIfAbsent), which the two Cataclysm deny tags need. The first
// argument is a ResourceLocation, so a tag held with its leading '#' goes through tagId().
ServerEvents.tags('block', event => {
  // (a) Nine tool tiers ship an EMPTY deny tag (boot tags.json: 0 blocks each; GAP §2.4), so they mine every tier ore:
  // Cataclysm's Tooltier (L_Ender's Cataclysm 1.21.1-3.33.jar com/github/L_Ender/cataclysm/items/Tooltier: SimpleTier with
  // BlockTags.create(cataclysm:needs_monstrosity_tool / needs_black_steel_tool) as the incorrect-for tag), the Forgotten tools,
  // the Resonarium and Warden tools, the Atomic Disassembler and Meka-Tool, and the two Supremium paxel tiers. Each gets
  // exactly what ATM adds to vanilla's netherite deny tag (allthemodium-3.0.1_mc_1.21.1.jar!data/minecraft/tags/block/
  // incorrect_for_netherite_tool.json = [#c:needs_allthemodium_tool, #c:needs_vibranium_tool, #c:needs_unobtainium_tool,
  // #c:needs_allthemodiumalloy_tool]). Vibranium ore is in the first (4 blocks), Unobtainium ore in the second (3), the third
  // holds ancient-stone decoratives and the alloy blocks (20); Allthemodium ore is only in #neoforge:needs_netherite_tool.
  // So these tools then mine Allthemodium ore and nothing above it, like netherite; each tag ends at 27 blocks.
  // Not nested: minecraft:incorrect_for_netherite_tool itself, because The_Undergarden-1.21.1-0.9.6.jar!data/minecraft/
  // tags/block/incorrect_for_netherite_tool.json adds #undergarden:needs_forgotten_tool to it, and nesting it would stop the
  // Forgotten pickaxe mining its own tier.
  // The fourth tag is bound but empty (ATM ships {"values": []}); it is nested for parity with ATM's list, and built from
  // the bare IDS string so tools/check_tags.py (which fails on a '#' literal that names an empty tag) does not look it up.
  const deny = IDS.tierOres.needsToolTags.concat(['#' + IDS.tierOres.alloyToolTagEmpty])
  IDS.tierOres.incorrectForTags.forEach(tag => event.add(tag, deny))

  // (b) The five tier-ore blocks join the Wither's immune tag (its body-break, blue skulls and a jarred Wither all check
  // minecraft:wither_immune and drop the raw item with no tool; GAP §2.3c) and the four Cataclysm boss immune tags
  // (L_Ender's Cataclysm 1.21.1-3.33.jar!data/cataclysm/tags/block/{ignis,maledictus,scylla,netherite_monstrosity}_immune.json).
  // No jar lists an ATM block in any of the five today (every wither_immune.json and the four Cataclysm files were read).
  // Benign spillover: two tags nest #minecraft:wither_immune, so they gain the five ores too (tags.json 142 -> 147, 265 -> 270).
  // twilightforest-1.21.1-4.8.3345-universal.jar!data/twilightforest/tags/block/block_and_chain_never_breaks.json (ChainBlock
  // .canBreakBlockAt refuses its blocks; GAP §2.3) and the_bumblezone-7.15.3+1.21.1-neoforge.jar!data/the_bumblezone/tags/
  // block/sentry_watcher/forced_never_destroy.json (SentryWatcherEntity stops at its blocks): both only protect a block.
  IDS.tierOres.immuneTags.forEach(tag => event.add(tagId(tag), IDS.tierOres.blocks))
})

// ---- The Other gate (v0.3 spec §4.2-4.4; D100, D101, D109, D110). lib/other_gate.js decides (node-tested by
// tools/tests/test_other_gate.py); this section reads the game state and carries out the actions it returns (node-tested
// with recording stand-ins by tools/tests/test_other_gate_events.py, which pins every call below in order).
// Every member below was read with javap in the v0.3 plan session. Jars: KJS = mods/kubejs-neoforge-2101.7.2-build.377.jar,
// RH = mods/rhino-2101.2.7-build.85.jar, FTBT = mods/ftb-teams-neoforge-2101.1.11.jar, NF = libraries/.../neoforge-21.1.250-
// {server,universal}.jar, MC = libraries/.../server-1.21.1-20240808.144430-srg.jar (all under .run/server/).
//   Script bindings Java, Text, NativeEvents: KJS BuiltinKubeJSPlugin.registerBindings. Java.loadClass(String) goes through
//     KubeJSContext.loadJavaClass (class filter; KJS kubejs.classfilter.txt allows net.neoforged, FTBT's allows
//     dev.ftb.mods.ftbteams) and returns a NativeJavaClass; NativeEvents.onEvent(Class, Consumer<Event>) accepts it because
//     KubeJSContext.classOf unwraps a NativeJavaClass with getClassObject() (RH Context.jsToJava -> classOf for a Class).
//   Names under Rhino are KubeJS's, not Minecraft's. KJS core/mixin/EntityMixin marks Entity.level() @HideFromJS and renames
//     getUUID() and getStringUUID() to getUuid() and getStringUuid(); KJS core/mixin/LevelMixin renames Level.dimension() to
//     getDimensionKey(). Measured under Rhino on 2026-11-06 on a live ServerPlayer and ServerLevel: player.level() and
//     level.dimension() throw "Cannot call property ... It is not a function, it is "object"", because those names are
//     KubeJS's beans (KJS EntityKJS.kjs$getLevel, LevelKJS.kjs$getDimension), and typeof player.getUUID and
//     player.getStringUUID are "undefined". So every read below calls entity.getLevel() and
//     String(level.getDimension()) (kjs$getDimension -> ResourceLocation, whose toString() is "ns:path"). A ResourceKey
//     from a NeoForge event still goes through dimId. Node cannot see any of this: tools/gate_probe.sh runs these paths
//     under Rhino (research/phase7-v0.3-probe-evidence/rhino-names.md).
//   BlockRightClickedKubeEvent (KJS): getPlayer() and getLevel() from KubeEntityEvent (getLevel = getEntity().level()),
//     getHand() -> InteractionHand (MC enum MAIN_HAND / OFF_HAND). Rhino wraps the enum as a NativeJavaObject (RH
//     Context.wrapAsJavaObject) and exposes the inherited Enum.name() (RH CachedClassInfo.getAccessibleMethods walks the
//     superclasses; the class filter is checked only on InteractionHand itself, in the JavaMembers constructor).
//   cancel(): the script call is KJS KubeEvent.cancel(Context), which delegates to cancel(Context, Object); that builds
//     EventResult$Type.INTERRUPT_FALSE.exit(...) and throws the EventExit (athrow, offset 15). EventHandler.postInternal
//     catches EventExit (exception table 91-287 -> 290) before Throwable (-> 302: logged, result ERROR), and
//     EventResult.applyCancel cancels the click only for INTERRUPT_FALSE. So cancel() is called only outside the try, and
//     the handler catches its own errors and cancels itself, because an uncaught error would let the click through
//     (spec §4.2, PAD §2.3).
//   Player (MC): getMainHandItem(), getOffhandItem(), isCreative(), isSpectator(), displayClientMessage(Component, true) =
//     the action bar (KJS PlayerKJS.kjs$setStatusMessage does the same call), getScoreboardName(), getUuid(),
//     getStringUuid(), getServer(), getLevel(); Level.isClientSide(). ItemStack.shrink(int) (MC); ItemStack getId() is
//     KJS ItemStackKJS.kjs$getId() = the item's registry id (RemapPrefixForJS "kjs$"). Text.literal(String) (KJS TextWrapper).
//   Entity.isServerPlayer() is KJS EntityKJS.kjs$isServerPlayer() (false), overridden true by ServerPlayerKJS.
//   FTB Teams (FTBT, PAD §3a): FTBTeamsAPI.api() -> API; isManagerLoaded(); getManager() -> TeamManager;
//     getTeamForPlayer(ServerPlayer) -> java.util.Optional<Team>. Rhino wraps the Optional as a plain NativeJavaObject
//     (RH Context.javaToJS/wrap/wrapAsJavaObject have no Optional case; KJS KubeJSContext converts Optional only JS -> Java),
//     so the code calls isPresent()/get(). Team.getExtraData() -> CompoundTag, which reaches JS as a NativeJavaMap over its
//     NBT keys (KJS CompoundTagMixin.convertJavaToJs); NativeJavaMap.get falls back to the CompoundTag's own methods for a
//     name that is not a key, so getBoolean(String) / putBoolean(String, boolean) (MC) are method calls. Never read the flag
//     as a property (tag[flag]): that gives a Tag object, not a boolean. Team.markDirty(); getShortName().
//   NeoForge events (NF universal): EntityTravelToDimensionEvent getDimension() -> ResourceKey, getEntity(),
//     setCanceled(boolean) from ICancellableEvent; PlayerEvent$PlayerChangedDimensionEvent getTo() -> ResourceKey,
//     getEntity() -> Player.
//   Server (KJS MinecraftServerKJS / MinecraftEnvironmentKJS, RemapPrefixForJS "kjs$"): scheduleInTicks(TickDuration,
//     Callback). A number becomes TickDuration.of(long) (the TickDuration type wrapper registered in
//     BuiltinKubeJSPlugin.registerTypeWrappers, and TickDuration.wrap), and an arrow function becomes the Callback
//     (RH Context.jsToJava -> createInterfaceAdapter).
//     ScheduledEvents sets endTime = currentTick + 1, and currentTick moves only in tickAll, which
//     MinecraftServerMixin.kjs$postTickServer calls at the RETURN of MinecraftServer.tickServer. So the callback runs at the
//     next end of a server tick (this tick's, or the next one's if the event fired between ticks): never inside the event,
//     so after Tombstone's own Helper.teleport has returned. runCommandSilent(String) = performPrefixedCommand as the server
//     source (permission 4, output suppressed). MC MinecraftServer.overworld(), getPlayerList().getPlayer(UUID);
//     Level.getSharedSpawnPos() -> BlockPos (getX/getY/getZ).
//   Command (MC): ExecuteCommand literal "in" + dimension, TeleportCommand "tp" targets location; a UUID target is parsed
//     by EntitySelectorParser.parseNameOrUUID and found across getAllLevels() by EntitySelector.
// Nothing here logs at load time, so a "confluence other-gate" line in kubejs/server.log always means a gate acted: a boot
// with no player online has none (v0.3 plan Task 9 Step 7 greps for it), and test_other_gate_events.py's
// test_section_registers_its_listeners_and_logs_nothing_while_loading pins that loading records only the three loadClass
// calls. (tools/tests/run_server_scripts.js sends script console output to stderr, so its JSON stdout does not need this.)
// The boot proof is KubeJS's own "Loaded Java class '...'" line for each of the three Java.loadClass calls below.
// Rhino note. Under Rhino 2101.2.7 a `const` declared directly in a `try` block throws "redeclaration of var" when the block
// runs (a runtime error: rhino-2101.2.7-build.85.jar Interpreter.doSetConstVar / ScriptableObject.putConstImpl), while V8,
// and so node, accepts it (v0.3 plan Task 2 Step 4, "Correction (execution, session 13)"; tools/tests/test_rhino_hazards.py
// lints that case). The standalone Rhino harness in that step showed `let` inside a `try` works but tried no other form, so
// every name a try, catch or finally body assigns is declared with `let` before the `try`, with its starting value (`null`,
// or `false` for the pad's `cancel`). Nested functions declare their own names.
const OTHER_GATE_MC = {
  teamsApi: Java.loadClass('dev.ftb.mods.ftbteams.api.FTBTeamsAPI'),
  travelEvent: Java.loadClass('net.neoforged.neoforge.event.entity.EntityTravelToDimensionEvent'),
  changedEvent: Java.loadClass('net.neoforged.neoforge.event.entity.player.PlayerEvent$PlayerChangedDimensionEvent'),

  dimId: function (key) {
    return String(key.location().toString())
  },

  // { found, unlocked, team }: found is false when FTB Teams has no manager or the player has no team (spec §4.2).
  lookup: function (player) {
    const api = OTHER_GATE_MC.teamsApi.api()
    if (!api.isManagerLoaded()) return { found: false, unlocked: false, team: null }
    const opt = api.getManager().getTeamForPlayer(player)
    if (!opt.isPresent()) return { found: false, unlocked: false, team: null }
    const team = opt.get()
    return { found: true, unlocked: team.getExtraData().getBoolean(IDS.other.unlockFlag) === true, team: team }
  },

  say: function (player, text) {
    player.displayClientMessage(Text.literal(text), true)
  },

  exempt: function (player) {
    return player.isCreative() || player.isSpectator()
  },

  // §4.4: at the next end of a server tick (so after Tombstone's own teleport has returned), if the player is still online
  // and still in dest, move them to the Overworld world spawn and show the message. If the tp left them in dest, log an
  // error instead of the message.
  toSpawn: function (player, dest, message) {
    const server = player.getServer()
    const uuid = player.getUuid()
    server.scheduleInTicks(1, scheduled => {
      // Declared before the try (Rhino note above).
      let p = null
      let spawn = null
      try {
        p = server.getPlayerList().getPlayer(uuid)
        if (p === null || String(p.getLevel().getDimension()) !== dest) return
        spawn = server.overworld().getSharedSpawnPos()
        server.runCommandSilent('execute in ' + IDS.vanilla.overworld + ' run tp ' + p.getStringUuid() + ' ' +
          (spawn.getX() + 0.5) + ' ' + spawn.getY() + ' ' + (spawn.getZ() + 0.5))
        // runCommandSilent returns void (KJS MinecraftServerKJS.kjs$runCommandSilent) and a failed tp is silent (MC
        // Commands.performCommand catches Exception, exception table 37-55 -> 70, and the source's output is suppressed). The
        // tp runs before the call returns (MC Commands.executeCommandInContext runs the command queue at once when no context
        // is open, offsets 15-94; ServerPlayer.teleportTo -> changeDimension, offset 67), so where p is now tells.
        if (String(p.getLevel().getDimension()) === dest) {
          console.error('confluence other-gate: arrival move did not leave ' + dest + ' for ' + p.getScoreboardName())
          return
        }
        OTHER_GATE_MC.say(p, message)
        console.info('confluence other-gate: arrival check sent ' + p.getScoreboardName() + ' from ' + dest + ' to the Overworld spawn')
      } catch (e) {
        console.error('confluence other-gate: arrival move failed for ' + dest + ': ' + e)
      }
    })
  },
}

// §4.2 pad. Decide inside the try, cancel outside it: cancel() throws, and a try around it would swallow the cancel.
// KubeJS never posts this event while the clicking hand's item is on cooldown (KJS KubeJSBlockEventHandler.rightClick offsets
// 47-71; PAD §1.6): the pad itself may then act, and the travel check below still refuses the trip (PAD §1.5, §4.3).
BlockEvents.rightClicked(IDS.allthemodium.teleportPad, event => {
  // Declared before the try (Rhino note above).
  let cancel = false
  let player = null
  let found = null
  let act = null
  let stack = null
  try {
    player = event.getPlayer()
    act = OTHER_GATE.pad({
      dim: String(event.getLevel().getDimension()),
      hand: String(event.getHand().name()),
      team: () => {
        found = OTHER_GATE_MC.lookup(player)
        return found
      },
      held: () => {
        return { main: String(player.getMainHandItem().getId()), off: String(player.getOffhandItem().getId()) }
      },
    })
    if (act.error !== null) console.error('confluence other-gate: pad check failed, click cancelled: ' + act.error)
    cancel = act.cancel
    if (act.unlock) {
      // §4.2 unlock order: the flag first, then one key, so an error before the shrink never eats a key.
      found.team.getExtraData().putBoolean(IDS.other.unlockFlag, true)
      found.team.markDirty()
      stack = act.shrink === 'MAIN_HAND' ? player.getMainHandItem() : player.getOffhandItem()
      stack.shrink(1)
      console.info('confluence other-gate: ' + player.getScoreboardName() + ' unlocked The Other for team ' + found.team.getShortName())
    }
    if (act.message !== null) OTHER_GATE_MC.say(player, act.message)
  } catch (e) {
    // §4.2: on any error, log and cancel (fail closed). Outside the Nether nothing above can throw except the dimension and
    // hand reads, so a pad elsewhere is cancelled only if those fail.
    console.error('confluence other-gate: pad handler error, click cancelled: ' + e)
    cancel = true
  }
  if (cancel) event.cancel()
})

// §4.3 travel check. A NativeEvents listener has no KubeJS guard (an uncaught error reaches changeDimension), so the whole
// body is in the try; the destination is read first and nothing else runs for any other dimension.
NativeEvents.onEvent(OTHER_GATE_MC.travelEvent, event => {
  // Declared before the try (Rhino note above).
  let dest = null
  let entity = null
  let act = null
  try {
    dest = OTHER_GATE_MC.dimId(event.getDimension())
    if (!OTHER_GATE.gated(dest)) return
    entity = event.getEntity()
    if (entity.getLevel().isClientSide() || !entity.isServerPlayer()) return
    act = OTHER_GATE.travel({
      dest: dest,
      exempt: () => OTHER_GATE_MC.exempt(entity),
      team: () => OTHER_GATE_MC.lookup(entity),
    })
    if (act.error !== null) console.error('confluence other-gate: travel check failed, trip to ' + dest + ' cancelled: ' + act.error)
    if (act.cancel) {
      event.setCanceled(true)
      console.info('confluence other-gate: travel check stopped ' + entity.getScoreboardName() + ' going to ' + dest)
      if (act.message !== null) OTHER_GATE_MC.say(entity, act.message)
    }
  } catch (e) {
    act = OTHER_GATE.travelError(dest, e)
    console.error('confluence other-gate: travel check error (destination ' + dest + ', cancelled: ' + act.cancel + '): ' + e)
    if (act.cancel) event.setCanceled(true)
  }
})

// §4.4 arrival check: Tombstone's Helper.teleport skips the travel event but fires this one after the move (PAD §4.3, GAP §5).
NativeEvents.onEvent(OTHER_GATE_MC.changedEvent, event => {
  // Declared before the try (Rhino note above).
  let dest = null
  let player = null
  let act = null
  let move = null
  try {
    dest = OTHER_GATE_MC.dimId(event.getTo())
    if (!OTHER_GATE.gated(dest)) return
    player = event.getEntity()
    if (player.getLevel().isClientSide()) return
    act = OTHER_GATE.arrival({
      dest: dest,
      exempt: () => OTHER_GATE_MC.exempt(player),
      team: () => OTHER_GATE_MC.lookup(player),
    })
    if (act.error !== null) console.error('confluence other-gate: arrival check failed, treating the team as locked: ' + act.error)
    if (act.sendToSpawn) OTHER_GATE_MC.toSpawn(player, dest, act.message)
  } catch (e) {
    act = OTHER_GATE.arrivalError(dest, e)
    // Without the player (getEntity itself failed) there is nobody to move, and the log says so.
    move = act.sendToSpawn && player !== null
    console.error('confluence other-gate: arrival check error (destination ' + dest + ', moving: ' + move + '): ' + e)
    if (move) {
      try {
        OTHER_GATE_MC.toSpawn(player, dest, act.message)
      } catch (e2) {
        console.error('confluence other-gate: arrival move could not be scheduled: ' + e2)
      }
    }
  }
})
