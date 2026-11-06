"""The Other gate wiring in events.js (v0.3 spec §4.2-4.4; D100, D101, D109, D110), run in node with recording stand-ins.

tools/tests/test_other_gate.py pins the decisions in lib/other_gate.js. These tests pin what events.js does with them,
which only events.js decides: the §4.2 unlock order (the flag and markDirty before one key is taken, from the hand the lib
chose), event.cancel() called outside the try (the stand-in throws, as KubeJS's cancel() throws EventExit), no error ever
leaving a native listener, the arrival move deferred until after the event with a still-there check, and the exact tp
command. Each case loads the real lib/ids.js, lib/other_gate.js and events.js into one vm context (KubeJS gives all
server scripts one scope), fires one captured listener, and returns every recorded call in order. The stand-ins model only
the members the section calls (its header comment cites each one), and each is as strict as the Java member it stands for:
getTeamForPlayer takes only the event's player (ftb-teams-neoforge-2101.1.11.jar TeamManager has no other overload), an
empty Optional's get() throws, getUuid() returns an object and PlayerList.getPlayer takes only that object, and the player
getPlayer returns is a distinct object with the same UUID (server-1.21.1-20240808.144430-srg.jar PlayerList.respawn builds a
new ServerPlayer), which alone moves when a tp works. Rhino itself is exercised by the boot and tools/gate_probe.sh.

The stand-ins also model the names KubeJS changes under Rhino, as measured on 2026-11-06 and read in
kubejs-neoforge-2101.7.2-build.377.jar (research/phase7-v0.3-probe-evidence/rhino-names.md). Entity.level() is @HideFromJS,
so `player.level` is KubeJS's bean, a Level object, and calling it is a TypeError. getUUID() and getStringUUID() are renamed
getUuid() and getStringUuid(), so the old names are undefined. Level.dimension() is renamed getDimensionKey(), so
`level.dimension` is KubeJS's bean, a ResourceLocation object, and calling it is a TypeError.

node runs V8, NOT the pack's Rhino (rhino-2101.2.7-build.85.jar under KubeJS 2101.7.2): a section that runs here can still
fail in KubeJS (tools/tests/test_rhino_hazards.py lints the one known case, a const directly inside a try). The load proof is
the boot (tools/server_boot.sh fails on any KubeJS ERROR line), and the behaviour proof is the in-game probe (v0.3 plan
Task 12, spec §12 probes 2 and 3). node must be on PATH: the `node` fixture asserts it, so these tests run rather than skip.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from kjs import scripts_root

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = scripts_root()   # pack/kubejs/server_scripts, or $CONFLUENCE_SCRIPTS_ROOT (the mutation corpus, test_pin_mutations.py)
NODE = shutil.which("node")


@pytest.fixture(scope="module")
def node():
    assert NODE, ("node is not on PATH; events.js is JavaScript and these tests run it in node "
                  "(brew install node; v22.3.0 was used when this test was written)")
    return NODE


pytestmark = pytest.mark.usefixtures("node")

HARNESS = r"""
const fs = require('fs'), vm = require('vm')
const c = JSON.parse(fs.readFileSync(0, 'utf8'))
c.team = c.team || {}
const log = []
const rec = s => { log.push(s) }
const boom = at => { if (c.throwAt === at) throw new Error('boom at ' + at) }
const EXIT = new Error('EventExit')
const key = id => ({ location: () => ({ toString: () => id }) })
const location = id => ({ toString: () => id })   // a ResourceLocation: String() gives "ns:path"
// A Level as Rhino shows it: `dimension` is a ResourceLocation bean, not a function (LevelMixin renames dimension()).
const levelAt = at => ({
  isClientSide: () => c.clientSide === true,
  dimension: location(at()),
  getDimension: () => { boom('dimension'); return location(at()) },
  getDimensionKey: () => { boom('dimension'); return key(at()) },
})
const team = {
  getExtraData: () => ({
    getBoolean: k => { rec('getBoolean ' + k); boom('getBoolean'); return c.team.unlocked === true },
    putBoolean: (k, v) => { rec('putBoolean ' + k + ' ' + v); boom('putBoolean') },
  }),
  markDirty: () => { rec('markDirty'); boom('markDirty') },
  getShortName: () => 'Team1',
}
// getTeamForPlayer(ServerPlayer) is FTB Teams' only overload (the UUID form is getTeamForPlayerID), so anything but the event's
// player is refused, as Rhino's method lookup would refuse it. An empty java.util.Optional's get() throws.
const api = {
  isManagerLoaded: () => { rec('isManagerLoaded'); boom('isManagerLoaded'); return c.team.manager !== false },
  getManager: () => ({ getTeamForPlayer: p => {
    rec('getTeamForPlayer')
    if (p !== player) throw new TypeError('getTeamForPlayer(ServerPlayer): not the event player')
    return { isPresent: () => c.team.found === true,
      get: () => { if (c.team.found !== true) throw new Error('java.util.NoSuchElementException: No value present'); return team } }
  } }),
}
const stack = (hand, id) => ({ getId: () => id, shrink: n => { rec('shrink ' + hand + ' ' + n); boom('shrink') } })
const UUID = { toString: () => 'uuid-1' }   // a java.util.UUID object, not a string
// Two player objects with the same UUID and the same starting dimension: `player` is the one the event carries, `online` the
// one PlayerList.getPlayer(UUID) returns. They are distinct, as after a respawn (PlayerList.respawn builds a new ServerPlayer),
// so only `online` moves (movedAway, a successful tp) and a read from the event's stale object shows.
const makePlayer = () => {
  const self = {
    at: c.dest,
    getMainHandItem: () => stack('MAIN_HAND', c.main || 'minecraft:air'),
    getOffhandItem: () => stack('OFF_HAND', c.off || 'minecraft:air'),
    isCreative: () => c.mode === 'creative',
    isSpectator: () => c.mode === 'spectator',
    displayClientMessage: (text, actionBar) => rec('say ' + text.literal + ' ' + actionBar),
    getScoreboardName: () => 'Alex',
    // EntityMixin: @RemapForJS("getUuid"), @RemapForJS("getStringUuid"). getUUID and getStringUUID are undefined under Rhino.
    getUuid: () => UUID,
    getStringUuid: () => 'uuid-1-str',
    getServer: () => server,
    // EntityMixin: level() is @HideFromJS, so `level` is the kjs$getLevel bean: an object, not a function.
    get level() { return levelAt(() => self.at) },
    getLevel: () => levelAt(() => self.at),
    isServerPlayer: () => c.serverPlayer !== false,
  }
  return self
}
const scheduled = []
const server = {
  scheduleInTicks: (n, fn) => { rec('schedule ' + n); boom('schedule'); scheduled.push(fn) },
  // PlayerList.getPlayer(UUID): a string or any other object is refused.
  getPlayerList: () => ({ getPlayer: u => {
    rec('getPlayer ' + u)
    if (u !== UUID) throw new TypeError('getPlayer(UUID): not the UUID object')
    return c.loggedOut ? null : online
  } }),
  overworld: () => ({ getSharedSpawnPos: () => ({ getX: () => 10, getY: () => 64, getZ: () => -5 }) }),
  // A tp that works moves the online player before the call returns; tpFails models one that did nothing (it is silent).
  runCommandSilent: cmd => {
    rec('command ' + cmd)
    boom('command')
    const m = /^execute in (\S+) run tp (\S+) /.exec(cmd)
    if (m && m[2] === online.getStringUuid() && !c.tpFails) online.at = m[1]
  },
}
const player = makePlayer()
const online = makePlayer()
const listeners = { pad: null, padId: null, native: {} }
const ctx = vm.createContext({
  console: { info: m => rec('info ' + m), warn: m => rec('warn ' + m), error: m => rec('error ' + m), log: m => rec('log ' + m) },
  Java: { loadClass: name => { rec('loadClass ' + name); return { name: name, api: () => api } } },
  Text: { literal: s => ({ literal: s }) },
  ServerEvents: new Proxy({}, { get: () => () => {} }),
  BlockEvents: { rightClicked: (id, fn) => { listeners.padId = id; listeners.pad = fn } },
  NativeEvents: { onEvent: (cls, fn) => { listeners.native[cls.name] = fn } },
})
for (const f of process.argv.slice(1)) vm.runInContext(fs.readFileSync(f, 'utf8'), ctx, { filename: f })
const out = { load: log.splice(0), padId: listeners.padId, native: Object.keys(listeners.native), log: log,
  cancelled: false, uncaught: null }
try {
  if (c.fn === 'pad') {
    // Both forms of the hand and dimension reads are modelled, so the task's in-game fallbacks (String(event.getHand())
    // through Enum.toString(), and event.getBlock().getDimensionKey()) pass or fail these tests the same way.
    // BlockRightClickedKubeEvent.getLevel() is a method on the event itself, and returns a Level as Rhino shows it.
    listeners.pad({
      getPlayer: () => { boom('getPlayer'); return player },
      getLevel: () => levelAt(() => c.dim),
      getBlock: () => ({ getDimensionKey: () => { boom('dimension'); return key(c.dim) } }),
      getHand: () => ({ name: () => c.hand, toString: () => c.hand }),
      cancel: () => { rec('cancel'); throw EXIT },
    })
  } else if (c.fn === 'travel') {
    listeners.native['net.neoforged.neoforge.event.entity.EntityTravelToDimensionEvent']({
      getDimension: () => { boom('getDimension'); return key(c.dest) },
      getEntity: () => { rec('getEntity'); boom('getEntity'); return player },
      setCanceled: b => rec('setCanceled ' + b),
    })
  } else if (c.fn === 'arrival') {
    listeners.native['net.neoforged.neoforge.event.entity.player.PlayerEvent$PlayerChangedDimensionEvent']({
      getTo: () => { boom('getTo'); return key(c.dest) },
      getEntity: () => { rec('getEntity'); boom('getEntity'); return player },
    })
    rec('tick end')
    if (c.movedAway) online.at = 'minecraft:the_nether'
    scheduled.forEach(fn => fn({}))
  }
} catch (e) {
  if (e === EXIT) out.cancelled = true
  else out.uncaught = String(e)
}
process.stdout.write(JSON.stringify(out))
"""

# Ids: the dimensions, the key and the flag equal IDS.vanilla.*, IDS.other.* and IDS.pack.otherKey (lib/ids.js, where the
# jar paths are cited; allthemodium-3.0.1_mc_1.21.1.jar!data/allthemodium/dimension/{the_other,the_beyond}.json). The two
# event class names are the ones the events.js section loads (neoforge-21.1.250-universal.jar, cited in its header).
NETHER, END, OVERWORLD = "minecraft:the_nether", "minecraft:the_end", "minecraft:overworld"
OTHER, BEYOND = "allthemodium:the_other", "allthemodium:the_beyond"
KEY, DIRT = "kubejs:other_key", "minecraft:dirt"
FLAG = "confluence_other_unlocked"
TRAVEL_EVENT = "net.neoforged.neoforge.event.entity.EntityTravelToDimensionEvent"
CHANGED_EVENT = "net.neoforged.neoforge.event.entity.player.PlayerEvent$PlayerChangedDimensionEvent"
UNLOCKED = {"found": True, "unlocked": True}
LOCKED = {"found": True, "unlocked": False}
NO_TEAM = {"found": False}
NO_MANAGER = {"manager": False}

LOOKUP = ["isManagerLoaded", "getTeamForPlayer", "getBoolean " + FLAG]
UNLOCK = ["putBoolean " + FLAG + " true", "markDirty"]
SAY_UNLOCKED = "say The Other is open to your team. Sneak and right-click the pad with both hands empty to travel. true"
SAY_LOCKED = "say Locked. Right-click this pad holding a Key to The Other. true"
SAY_BEYOND = "say The Beyond is closed in Confluence. true"
SAY_TEAM = "say Your team has not unlocked The Other. true"
TP = "command execute in minecraft:overworld run tp uuid-1-str 10.5 64 -4.5"


def pad_error(at):
    return "error confluence other-gate: pad handler error, click cancelled: Error: boom at " + at


def stopped(dest):
    return "info confluence other-gate: travel check stopped Alex going to " + dest


def moved(dest, say):
    return ["schedule 1", "tick end", "getPlayer uuid-1", TP, say,
            "info confluence other-gate: arrival check sent Alex from " + dest + " to the Overworld spawn"]


def fire(fn, **case):
    case["fn"] = fn
    proc = subprocess.run(
        [NODE, "-e", HARNESS, str(SCRIPTS / "lib" / "ids.js"), str(SCRIPTS / "lib" / "other_gate.js"),
         str(SCRIPTS / "events.js")],
        input=json.dumps(case), capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["uncaught"] is None, out
    return out


def test_section_registers_its_listeners_and_logs_nothing_while_loading():
    out = fire("load")
    assert out["load"] == ["loadClass dev.ftb.mods.ftbteams.api.FTBTeamsAPI", "loadClass " + TRAVEL_EVENT,
                           "loadClass " + CHANGED_EVENT]
    assert out["padId"] == "allthemodium:teleport_pad"
    assert out["native"] == [TRAVEL_EVENT, CHANGED_EVENT]
    assert out["log"] == [] and out["cancelled"] is False


# ---- §4.2 pad -------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("main,off,hand", [(KEY, None, "MAIN_HAND"), (None, KEY, "OFF_HAND"), (KEY, KEY, "MAIN_HAND")])
def test_pad_unlock_sets_the_flag_before_taking_one_key(main, off, hand):
    out = fire("pad", dim=NETHER, hand="MAIN_HAND", team=LOCKED, main=main, off=off)
    assert out["log"] == LOOKUP + UNLOCK + ["shrink " + hand + " 1",
                                            "info confluence other-gate: Alex unlocked The Other for team Team1",
                                            SAY_UNLOCKED, "cancel"]
    assert out["cancelled"] is True


@pytest.mark.parametrize("at,done", [("putBoolean", UNLOCK[:1]), ("markDirty", UNLOCK),
                                     ("shrink", UNLOCK + ["shrink MAIN_HAND 1"])])
def test_pad_error_during_the_unlock_takes_no_key_before_the_flag_and_still_cancels(at, done):
    out = fire("pad", dim=NETHER, hand="MAIN_HAND", team=LOCKED, main=KEY, throwAt=at)
    assert out["log"] == LOOKUP + done + [pad_error(at), "cancel"]
    assert out["cancelled"] is True


@pytest.mark.parametrize("case,log,cancelled", [
    pytest.param(dict(dim=NETHER, hand="MAIN_HAND", team=UNLOCKED, main=KEY), LOOKUP, False, id="unlocked-team-untouched"),
    pytest.param(dict(dim=NETHER, hand="MAIN_HAND", team=LOCKED, main=DIRT), LOOKUP + [SAY_LOCKED, "cancel"], True,
                 id="locked-without-key"),
    pytest.param(dict(dim=NETHER, hand="OFF_HAND", team=LOCKED, off=KEY), LOOKUP + ["cancel"], True,
                 id="locked-off-hand-event-silent"),
    pytest.param(dict(dim=NETHER, hand="MAIN_HAND", team=NO_TEAM, main=KEY),
                 ["isManagerLoaded", "getTeamForPlayer", SAY_LOCKED, "cancel"], True, id="no-team-keeps-key"),
    pytest.param(dict(dim=NETHER, hand="MAIN_HAND", team=NO_MANAGER, main=KEY), ["isManagerLoaded", SAY_LOCKED, "cancel"],
                 True, id="no-manager-keeps-key"),
    pytest.param(dict(dim=END, hand="MAIN_HAND", team=UNLOCKED, main=KEY), [SAY_BEYOND, "cancel"], True, id="end-main-hand"),
    pytest.param(dict(dim=END, hand="OFF_HAND", team=UNLOCKED), ["cancel"], True, id="end-off-hand"),
    pytest.param(dict(dim=OVERWORLD, hand="MAIN_HAND", team=LOCKED, main=KEY), [], False, id="overworld-untouched"),
    # Spec §4.2: the pad rules hold "in every game mode (no creative exemption at the pad)" (D109).
    pytest.param(dict(dim=NETHER, hand="MAIN_HAND", team=LOCKED, main=DIRT, mode="creative"), LOOKUP + [SAY_LOCKED, "cancel"],
                 True, id="creative-gets-no-pad-exemption"),
    pytest.param(dict(dim=END, hand="MAIN_HAND", team=UNLOCKED, mode="spectator"), [SAY_BEYOND, "cancel"], True,
                 id="spectator-gets-no-pad-exemption"),
    pytest.param(dict(dim=NETHER, hand="MAIN_HAND", team=LOCKED, main=KEY, throwAt="isManagerLoaded"),
                 ["isManagerLoaded",
                  "error confluence other-gate: pad check failed, click cancelled: Error: boom at isManagerLoaded", "cancel"],
                 True, id="lookup-error-cancels"),
    pytest.param(dict(dim=NETHER, hand="MAIN_HAND", team=LOCKED, main=KEY, throwAt="getPlayer"),
                 [pad_error("getPlayer"), "cancel"], True, id="player-read-error-cancels"),
    pytest.param(dict(dim=OVERWORLD, hand="MAIN_HAND", team=LOCKED, main=KEY, throwAt="dimension"),
                 [pad_error("dimension"), "cancel"], True, id="dimension-read-error-cancels"),
])
def test_pad_cancels_once_after_its_own_code(case, log, cancelled):
    out = fire("pad", **case)
    assert out["log"] == log
    assert out["cancelled"] is cancelled


# ---- §4.3 travel check ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("case,log", [
    pytest.param(dict(dest=OTHER, team=LOCKED), ["getEntity"] + LOOKUP + ["setCanceled true", stopped(OTHER), SAY_TEAM],
                 id="other-locked-team"),
    pytest.param(dict(dest=OTHER, team=NO_TEAM),
                 ["getEntity", "isManagerLoaded", "getTeamForPlayer", "setCanceled true", stopped(OTHER), SAY_TEAM],
                 id="other-no-team"),
    pytest.param(dict(dest=OTHER, team=UNLOCKED), ["getEntity"] + LOOKUP, id="other-unlocked-team"),
    pytest.param(dict(dest=BEYOND, team=UNLOCKED), ["getEntity", "setCanceled true", stopped(BEYOND), SAY_BEYOND],
                 id="beyond-closed-no-lookup"),
    pytest.param(dict(dest=OTHER, team=LOCKED, mode="creative"), ["getEntity"], id="creative-exempt"),
    pytest.param(dict(dest=BEYOND, mode="spectator"), ["getEntity"], id="spectator-exempt"),
    pytest.param(dict(dest=OTHER, team=LOCKED, clientSide=True), ["getEntity"], id="client-side-ignored"),
    pytest.param(dict(dest=OTHER, team=LOCKED, serverPlayer=False), ["getEntity"], id="non-player-ignored"),
    pytest.param(dict(dest=NETHER, team=LOCKED), [], id="nether-reads-nothing"),
    pytest.param(dict(dest=OTHER, throwAt="getDimension"),
                 ["error confluence other-gate: travel check error (destination null, cancelled: false): "
                  "Error: boom at getDimension"], id="destination-read-error-not-cancelled"),
    pytest.param(dict(dest=OTHER, throwAt="getEntity"),
                 ["getEntity", "error confluence other-gate: travel check error (destination allthemodium:the_other, "
                  "cancelled: true): Error: boom at getEntity", "setCanceled true"], id="entity-read-error-cancelled"),
    pytest.param(dict(dest=OTHER, team=LOCKED, throwAt="isManagerLoaded"),
                 ["getEntity", "isManagerLoaded", "error confluence other-gate: travel check failed, trip to "
                  "allthemodium:the_other cancelled: Error: boom at isManagerLoaded", "setCanceled true", stopped(OTHER)],
                 id="lookup-error-cancelled"),
])
def test_travel_listener(case, log):
    out = fire("travel", **case)
    assert out["log"] == log


# ---- §4.4 arrival check ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("case,log", [
    pytest.param(dict(dest=OTHER, team=LOCKED), ["getEntity"] + LOOKUP + moved(OTHER, SAY_TEAM), id="other-locked-team"),
    pytest.param(dict(dest=OTHER, team=NO_MANAGER), ["getEntity", "isManagerLoaded"] + moved(OTHER, SAY_TEAM),
                 id="other-no-manager"),
    pytest.param(dict(dest=BEYOND, team=UNLOCKED), ["getEntity"] + moved(BEYOND, SAY_BEYOND), id="beyond-no-lookup"),
    pytest.param(dict(dest=OTHER, team=UNLOCKED), ["getEntity"] + LOOKUP + ["tick end"], id="other-unlocked-team"),
    pytest.param(dict(dest=BEYOND, mode="creative"), ["getEntity", "tick end"], id="creative-exempt"),
    pytest.param(dict(dest=OTHER, team=LOCKED, mode="spectator"), ["getEntity", "tick end"], id="spectator-exempt"),
    pytest.param(dict(dest=OTHER, team=LOCKED, clientSide=True), ["getEntity", "tick end"], id="client-side-ignored"),
    pytest.param(dict(dest=NETHER, team=LOCKED), ["tick end"], id="nether-reads-nothing"),
    pytest.param(dict(dest=OTHER, team=LOCKED, movedAway=True),
                 ["getEntity"] + LOOKUP + ["schedule 1", "tick end", "getPlayer uuid-1"], id="already-left-not-moved"),
    pytest.param(dict(dest=BEYOND, loggedOut=True), ["getEntity", "schedule 1", "tick end", "getPlayer uuid-1"],
                 id="logged-out-not-moved"),
    pytest.param(dict(dest=OTHER, team=LOCKED, tpFails=True),
                 ["getEntity"] + LOOKUP + ["schedule 1", "tick end", "getPlayer uuid-1", TP,
                                           "error confluence other-gate: arrival move did not leave allthemodium:the_other for Alex"],
                 id="tp-did-nothing-logged-no-message"),
    pytest.param(dict(dest=OTHER, throwAt="getTo"),
                 ["error confluence other-gate: arrival check error (destination null, moving: false): Error: boom at getTo",
                  "tick end"], id="destination-read-error-not-moved"),
    pytest.param(dict(dest=OTHER, team=UNLOCKED, throwAt="isManagerLoaded"),
                 ["getEntity", "isManagerLoaded", "error confluence other-gate: arrival check failed, treating the team as "
                  "locked: Error: boom at isManagerLoaded"] + moved(OTHER, SAY_TEAM), id="lookup-error-treated-as-locked"),
    pytest.param(dict(dest=OTHER, throwAt="getEntity"),
                 ["getEntity", "error confluence other-gate: arrival check error (destination allthemodium:the_other, "
                  "moving: false): Error: boom at getEntity", "tick end"], id="entity-read-error-nobody-to-move"),
    pytest.param(dict(dest=BEYOND, throwAt="schedule"),
                 ["getEntity", "schedule 1", "error confluence other-gate: arrival check error (destination "
                  "allthemodium:the_beyond, moving: true): Error: boom at schedule", "schedule 1",
                  "error confluence other-gate: arrival move could not be scheduled: Error: boom at schedule", "tick end"],
                 id="schedule-error-contained"),
    pytest.param(dict(dest=BEYOND, throwAt="command"),
                 ["getEntity", "schedule 1", "tick end", "getPlayer uuid-1", TP,
                  "error confluence other-gate: arrival move failed for allthemodium:the_beyond: Error: boom at command"],
                 id="command-error-contained"),
])
def test_arrival_listener(case, log):
    out = fire("arrival", **case)
    assert out["log"] == log
