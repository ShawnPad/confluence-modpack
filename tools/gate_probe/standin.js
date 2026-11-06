// TEMPORARY probe stand-in (D138). tools/gate_probe.py copies this into .run/server/kubejs/server_scripts/ for one session and
// removes it. It must never ship: tools/ is in .packwizignore, and tools/tests/test_gate_probe.py fails if it appears in kubejs/.
//
// A stand-in: FakePlayerFactory.get, then PlayerList.respawn, gives a plain ServerPlayer in the PlayerList and the level, whose
// connection is FakePlayer's no-op handler. The login event is posted by hand so FTB Teams sees it. research/phase7-v0.3-probe-
// evidence/README.md has what this does not prove. Limits worked around here:
// - outbound packets are dropped, so a same-level tp loses its position (H.tp sets it as handleMovePlayer would);
// - no client ack, so isChangingDimension stays true (invulnerable, frozen portal cooldown): H.move calls hasChangedDimension;
// - online-mode profile lookups fail for an offline UUID, so H.spawn adds the profile to the cache (ftbteams needs it);
// - Rhino reflecting on a menu object logs RuntimeDistCleaner's RecipeBookCategories ERROR, so no helper reads containerMenu.
const CP = {
  FPF: Java.loadClass('net.neoforged.neoforge.common.util.FakePlayerFactory'),
  GameProfile: Java.loadClass('com.mojang.authlib.GameProfile'),
  UUIDUtil: Java.loadClass('net.minecraft.core.UUIDUtil'),
  NeoForge: Java.loadClass('net.neoforged.neoforge.common.NeoForge'),
  LoggedIn: Java.loadClass('net.neoforged.neoforge.event.entity.player.PlayerEvent$PlayerLoggedInEvent'),
  Removal: Java.loadClass('net.minecraft.world.entity.Entity$RemovalReason'),
  Hand: Java.loadClass('net.minecraft.world.InteractionHand'),
  BHR: Java.loadClass('net.minecraft.world.phys.BlockHitResult'),
  Vec3: Java.loadClass('net.minecraft.world.phys.Vec3'),
  AABB: Java.loadClass('net.minecraft.world.phys.AABB'),
  BlockPos: Java.loadClass('net.minecraft.core.BlockPos'),
  Direction: Java.loadClass('net.minecraft.core.Direction'),
  RL: Java.loadClass('net.minecraft.resources.ResourceLocation'),
  StringArg: Java.loadClass('com.mojang.brigadier.arguments.StringArgumentType'),
  server: null, list: {}, ctx0: null, conn0: null, ws: null, mon: null,
}
const OTHER = 'allthemodium:the_other'
const H = {}
H.p = function (n) { var x = CP.server.getPlayerList().getPlayerByName(n); if (x === null) throw 'no player ' + n; return x }
H.dim = function (n) { return String(H.p(n).getLevel().getDimension()) }
H.levelOf = function (dim) { return CP.server.getLevel(CP.RL.parse(dim)) }
H.conn = function () {
  if (CP.ctx0) return
  var CONN = Java.loadClass('net.minecraft.network.Connection')
  CP.conn0 = CONN.connectToLocalServer(CP.server.getConnection().startMemoryChannel())
  CP.ctx0 = CP.conn0.channel().pipeline().firstContext()
}
H.spawn = function (n) {
  var s = CP.server
  H.conn()
  var profile = new CP.GameProfile(CP.UUIDUtil.createOfflinePlayerUUID(n), n)
  var fake = CP.FPF.get(s.overworld(), profile)
  fake.connection.getConnection().channelActive(CP.ctx0)
  var p = s.getPlayerList().respawn(fake, true, CP.Removal.CHANGED_DIMENSION)
  p.connection.player = p
  s.getProfileCache().add(profile)
  CP.NeoForge.EVENT_BUS.post(new CP.LoggedIn(p))
  CP.list[n] = true
  return n + ' dim=' + H.dim(n) + ' mode=' + p.gameMode.getGameModeForPlayer()
}
// The same post again, for a stand-in already in a dimension: row P3.4's rejoin. No real client rejoin happens.
H.login = function (n) { CP.NeoForge.EVENT_BUS.post(new CP.LoggedIn(H.p(n))); return n + ' login posted in ' + H.dim(n) }
// A dead stand-in stays in the PlayerList but leaves the level: nothing targets it and it stops ticking, so its rows would read as
// a Piglich that does not attack. The first run lost P1 this way, so the rows check first.
H.alive = function (n) { var p = H.p(n); if (p.isRemoved() || p.isDeadOrDying()) throw n + ' is dead: removed=' + p.getRemovalReason() + ' health=' + p.getHealth() + ' ' + H.lastDeath; return n + ' alive, health ' + p.getHealth() }
H.despawn = function (n) { var p = H.p(n); delete CP.list[n]; CP.server.getPlayerList().remove(p); return 'removed ' + n }
H.despawnAll = function () { var n, o = 0; for (n in CP.list) { H.despawn(n); o++ } return 'removed ' + o }
H.move = function (n, x, y, z) {
  var p = H.p(n)
  p.hasChangedDimension()
  p.setPortalCooldown(0)
  p.absMoveTo(x, y, z)
  p.serverLevel().getChunkSource().move(p)
  return n + ' at ' + p.getX() + ',' + p.getY() + ',' + p.getZ() + ' in ' + H.dim(n)
}
H.tp = function (n, dim, x, y, z) {
  CP.server.runCommandSilent('execute in ' + dim + ' run tp ' + n + ' ' + x + ' ' + y + ' ' + z)
  return H.move(n, x, y, z)
}
H.sneak = function (n, on) { var p = H.p(n); p.setShiftKeyDown(!!on); p.doTick(); return n + ' crouching=' + p.isCrouching() }
// ServerGamePacketListenerImpl.handleUseItemOn's call, minus the packet decode and the reach check.
H.click = function (n, x, y, z, hand, sneak, face) {
  var p = H.p(n)
  if (sneak !== undefined) H.sneak(n, sneak)
  var h = hand === 'off' ? CP.Hand.OFF_HAND : CP.Hand.MAIN_HAND
  var hit = new CP.BHR(new CP.Vec3(x + 0.5, y + 1.0, z + 0.5), CP.Direction.byName(face || 'up'), new CP.BlockPos(x, y, z), false)
  var before = H.dim(n)
  var r = p.gameMode.useItemOn(p, p.getLevel(), p.getItemInHand(h), h, hit)
  return n + ' click ' + x + ',' + y + ',' + z + ' ' + hand + ' result=' + r + ' dim ' + before + ' -> ' + H.dim(n)
}
H.useitem = function (n) {
  var p = H.p(n)
  var r = p.gameMode.useItem(p, p.getLevel(), p.getMainHandItem(), CP.Hand.MAIN_HAND)
  return n + ' useItem result=' + r + ' using=' + p.isUsingItem()
}
H.select = function (n, i) { H.p(n).getInventory().selected = i; return 'selected ' + i }
H.hold = function (n, item, count) { var p = H.p(n); p.setItemInHand(CP.Hand.MAIN_HAND, Item.of(item, count || 1)); return n + ' main=' + p.getMainHandItem() }
H.count = function (n, id) {
  var inv = H.p(n).getInventory(), i, c = 0, st
  for (i = 0; i < inv.getContainerSize(); i++) { st = inv.getItem(i); if (String(st.getId()) === id) c += st.getCount() }
  return c
}
H.close = function (n) { H.p(n).closeMenu(); return 'closed' }
H.raw = function (cmd, n) {
  var src = n ? H.p(n).createCommandSourceStack() : CP.server.createCommandSourceStack()
  try { return cmd + ' -> ' + CP.server.getCommands().getDispatcher().execute(cmd, src) } catch (e) { return cmd + ' THREW ' + (e.javaException || e) }
}
H.uuid = function (n) { return String(H.p(n).getGameProfile().getId()) }
H.team = function (n) { return String(Java.loadClass('dev.ftb.mods.ftbteams.api.FTBTeamsAPI').api().getManager().getTeamForPlayer(H.p(n)).get().getShortName()) }
H.tpaAccept = function (acceptor) {
  var ids = []
  Java.loadClass('dev.ftb.mods.ftbessentials.commands.impl.teleporting.TPACommand').requests().forEach(function (k, v) { ids.push(String(k)) })
  return ids.length === 0 ? 'no tpa request' : H.raw('tpaccept ' + ids[0], acceptor)
}
H.findBlock = function (n, id, r, ylo, yhi) {
  var p = H.p(n), lv = p.getLevel(), x, y, z, cx = Math.floor(p.getX()), cz = Math.floor(p.getZ())
  for (x = cx - r; x <= cx + r; x++) for (z = cz - r; z <= cz + r; z++) for (y = ylo; y <= yhi; y++) {
    if (String(lv.getBlockState(new CP.BlockPos(x, y, z)).getBlock().getId()) === id) return x + ',' + y + ',' + z
  }
  return 'none'
}
H.wsFind = function (n, x, y, z) {
  var API = Java.loadClass('net.blay09.mods.waystones.api.WaystonesAPI')
  var w = API.getWaystoneAt(H.p(n).getLevel(), new CP.BlockPos(x, y, z))
  if (!w.isPresent()) return 'no waystone'
  CP.ws = w.get()
  return 'activated=' + API.isWaystoneActivated(H.p(n), CP.ws)
}
H.wsSelect = function (n) {
  var M = Java.loadClass('net.blay09.mods.waystones.network.message.SelectWaystoneMessage')
  M.handle(H.p(n), new M(CP.ws.getWaystoneUid()))
  return 'select sent; dim=' + H.dim(n)
}
// ---- Piglich rows: the arena is 300..340, 150..160, 300..340 in The Other (tools/gate_probe.py); the wider box counts Witches.
H.around = function () { return H.levelOf(OTHER).getEntities(null, new CP.AABB(250, 100, 250, 390, 215, 390)) }
H.piglich = function () {
  var es = H.around(), i, t = null
  for (i = 0; i < es.size(); i++) { if (String(es.get(i).getType()) === 'allthemodium:piglich') t = es.get(i) }
  return t
}
H.near = function (n, dist) {
  var t = H.piglich()
  return H.move(n, Math.min(Math.max(t.getX() - dist, 302), 338), 151, t.getZ())
}
H.hit = function (n) {
  var t = H.piglich(), p = H.p(n), h0 = t.getHealth()
  p.attack(t)
  p.resetAttackStrengthTicker()
  return 'piglich ' + h0 + '->' + t.getHealth()
}
H.heal = function (n, hp) {
  var p = H.p(n)
  p.setHealth(hp)
  if (p.getHealth() < hp) throw n + ' health ' + p.getHealth() + ' after setHealth ' + hp + ': raise max_health first'
  return n + ' health=' + p.getHealth()
}
H.killWitches = function () { var es = H.around(), i, c = 0; for (i = 0; i < es.size(); i++) { if (String(es.get(i).getType()) === 'minecraft:witch') { es.get(i).discard(); c++ } } return c }
H.piglichs = function () { var es = H.around(), i, c = 0; for (i = 0; i < es.size(); i++) { if (String(es.get(i).getType()) === 'allthemodium:piglich' && es.get(i).isAlive()) { c++ } } return c }
H.hearts = function () {
  var es = H.around(), i, c = 0
  for (i = 0; i < es.size(); i++) { if (String(es.get(i).getType()) === 'minecraft:item' && String(es.get(i).getItem().getId()) === 'allthemodium:piglich_heart') c += es.get(i).getItem().getCount() }
  return c
}
// Per-tick monitor. Player: damage taken and new small fireballs. Piglich: each health drop, its source, and each new Witch. A Witch
// that appears in a tick with no health drop, or two in one tick, contradicts "up to one Witch each time it takes damage".
H.monStart = function (n, secs) {
  var t = H.piglich()
  CP.mon = { n: n, left: secs * 20, fb: {}, fbn: 0, dmg: {}, last: H.p(n).getHealth(), pl: t === null ? 0 : t.getHealth(), witch: {}, wn: 0, drops: 0, src: {}, psrc: {}, twoInOneTick: 0, withoutDrop: 0 }
  var es = H.around(), i
  for (i = 0; i < es.size(); i++) { if (String(es.get(i).getType()) === 'minecraft:witch') CP.mon.witch[es.get(i).getId()] = true }
  return 'monitor ' + secs + ' s'
}
H.monTick = function () {
  var m = CP.mon; if (!m || m.left <= 0) return
  m.left--
  var p = H.p(m.n), h = p.getHealth(), k
  m.minHealth = Math.min(m.minHealth === undefined ? h : m.minHealth, h)
  if (h < m.last - 0.001) {
    k = (m.last - h).toFixed(1); m.dmg[k] = (m.dmg[k] || 0) + 1
    try { k = String(p.getLastDamageSource().type().msgId()) } catch (x2) { k = 'unknown' }
    m.psrc[k] = (m.psrc[k] || 0) + 1
  }
  m.last = h
  var es = H.around(), i, e, id, t = null, fresh = 0
  for (i = 0; i < es.size(); i++) {
    e = es.get(i); id = String(e.getType())
    if (id === 'minecraft:small_fireball' && !m.fb[e.getId()]) { m.fb[e.getId()] = true; m.fbn++ }
    if (id === 'minecraft:witch' && !m.witch[e.getId()]) { m.witch[e.getId()] = true; m.wn++; fresh++ }
    if (id === 'allthemodium:piglich') t = e
  }
  var drop = false
  if (t !== null) {
    if (t.getHealth() < m.pl - 0.001) {
      drop = true; m.drops++
      try { k = String(t.getLastDamageSource().type().msgId()) } catch (x) { k = 'unknown' }
      m.src[k] = (m.src[k] || 0) + 1
    }
    m.pl = t.getHealth()
  }
  if (fresh > 1) m.twoInOneTick++
  if (fresh > 0 && !drop) m.withoutDrop++
}
H.monRead = function () {
  var m = CP.mon, k, d = '', s = '', ps = ''
  for (k in m.dmg) d += k + 'x' + m.dmg[k] + ' '
  for (k in m.psrc) ps += k + 'x' + m.psrc[k] + ' '
  for (k in m.src) s += k + 'x' + m.src[k] + ' '
  return 'left=' + m.left + ' fireballs=' + m.fbn + ' playerDamage=[' + d.trim() + '] playerSources=[' + ps.trim() + '] witches=' + m.wn + ' piglichDrops=' + m.drops + ' sources=[' + s.trim() + '] twoInOneTick=' + m.twoInOneTick + ' witchNoDrop=' + m.withoutDrop + ' piglichHealth=' + m.pl + ' playerHealth=' + m.last + ' min=' + m.minHealth
}
H.lastDeath = ''
EntityEvents.death(event => {
  if (event.entity.isPlayer()) H.lastDeath = 'died: ' + event.entity.getScoreboardName() + ' at ' + event.entity.getX() + ',' + event.entity.getY() + ',' + event.entity.getZ() + ' by ' + event.getSource().type().msgId() + ' from ' + event.getSource().getEntity()
})
ServerEvents.loaded(event => { CP.server = event.server })
ServerEvents.tick(event => {
  var n, q
  CP.server = event.server
  for (n in CP.list) {
    try { q = event.server.getPlayerList().getPlayerByName(n); if (q !== null && !q.isRemoved()) q.doTick() } catch (e) { console.error('gate-probe tick ' + n + ': ' + e) }
  }
  try { H.monTick() } catch (e2) { console.error('gate-probe monitor: ' + e2) }
})
ServerEvents.commandRegistry(event => {
  const C = event.commands
  event.register(C.literal('cprobe').requires(s => s.hasPermission(2))
    .then(C.argument('code', CP.StringArg.greedyString()).executes(ctx => {
      const code = String(CP.StringArg.getString(ctx, 'code'))
      let out = null
      CP.server = ctx.source.getServer()
      try { out = String(eval(code)) } catch (e) { out = 'ERR ' + e }
      ctx.source.sendSystemMessage(Text.literal('cprobe> ' + out))
      return 1
    })))
})
console.info('gate-probe stand-in loaded')
