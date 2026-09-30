"""The Other gate rules (v0.3 spec §4.2-4.4; D100, D101, D109), run in node against the real lib/ids.js.

kubejs/server_scripts/lib/other_gate.js is plain JavaScript with no KubeJS or Java calls, so node can run it. Each case
loads ids.js and other_gate.js into one vm context (the way KubeJS gives all server scripts one scope), calls one
OTHER_GATE function with stub callbacks, and returns the action plus how often each callback ran.

node runs V8, NOT the pack's Rhino (rhino-2101.2.7-build.85.jar under KubeJS 2101.7.2), so these tests pin the decisions,
not that Rhino accepts the file: the load proof is the boot (tools/server_boot.sh fails on any KubeJS ERROR line), and the
behaviour proof is the in-game probe (v0.3 plan Task 12, spec §12 probes 2 and 3). node must be on PATH: the `node` fixture
asserts it, so the 68 node tests run rather than skip.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SERVER_SCRIPTS = ROOT / "kubejs" / "server_scripts"
LIB = SERVER_SCRIPTS / "lib"
NODE = shutil.which("node")


@pytest.fixture(scope="module")
def node():
    assert NODE, ("node is not on PATH; the other-gate rules are JavaScript and these tests run them in node "
                  "(brew install node; v22.3.0 was used when this test was written)")
    return NODE


needs_node = pytest.mark.usefixtures("node")

HARNESS = r"""
const fs = require('fs'), vm = require('vm')
const ctx = vm.createContext({})
for (const f of process.argv.slice(1)) vm.runInContext(fs.readFileSync(f, 'utf8'), ctx, { filename: f })
const c = JSON.parse(fs.readFileSync(0, 'utf8'))
const calls = { team: 0, held: 0, exempt: 0 }
const answer = (name, value) => { calls[name]++; if (value === 'throw') throw new Error('boom in ' + name); return value }
const input = { dim: c.dim, hand: c.hand, dest: c.dest,
  team: () => answer('team', c.team), held: () => answer('held', c.held), exempt: () => answer('exempt', c.exempt) }
const gate = vm.runInContext('OTHER_GATE', ctx)
const out = c.fn.endsWith('Error') ? gate[c.fn](c.dest, new Error('outer boom')) : gate[c.fn](input)
process.stdout.write(JSON.stringify({ out: out, calls: calls }))
"""

# Ids the rules see as input. The first six equal IDS.vanilla.* / IDS.other.* (lib/ids.js, Task 2):
# allthemodium-3.0.1_mc_1.21.1.jar!data/allthemodium/dimension/{the_other,the_beyond,mining}.json. MOON is only an
# unrelated dimension for the untouched cases: adastra-1.21.1-1.16.25-neoforge.jar!data/ad_astra/dimension/moon.json
# (no IDS key; Task 2 lists ad_astra:moon among the ids used outside KubeJS code). KEY is IDS.pack.otherKey.
NETHER, END, OVERWORLD = "minecraft:the_nether", "minecraft:the_end", "minecraft:overworld"
OTHER, BEYOND, MINING, MOON = "allthemodium:the_other", "allthemodium:the_beyond", "allthemodium:mining", "ad_astra:moon"
KEY, AIR, DIRT = "kubejs:other_key", "minecraft:air", "minecraft:dirt"
UNLOCKED = {"found": True, "unlocked": True}
LOCKED = {"found": True, "unlocked": False}
NO_TEAM = {"found": False, "unlocked": False}
MSG_UNLOCKED = "The Other is open to your team. Sneak and right-click the pad with both hands empty to travel."
MSG_LOCKED = "Locked. Right-click this pad holding a Key to The Other."
MSG_BEYOND = "The Beyond is closed in Confluence."
MSG_TEAM = "Your team has not unlocked The Other."

PAD_UNTOUCHED = {"cancel": False, "unlock": False, "shrink": None, "message": None, "error": None}


def decide(fn, **case):
    case["fn"] = fn
    proc = subprocess.run(
        [NODE, "-e", HARNESS, str(LIB / "ids.js"), str(LIB / "other_gate.js")],
        input=json.dumps(case), capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def pad(dim, hand, team=LOCKED, main=AIR, off=AIR):
    return decide("pad", dim=dim, hand=hand, team=team, held={"main": main, "off": off})


# ---- §4.2 pad table -------------------------------------------------------------------------------------------------

@needs_node
@pytest.mark.parametrize("hand", ["MAIN_HAND", "OFF_HAND"])
def test_pad_nether_unlocked_team_is_untouched(hand):
    r = pad(NETHER, hand, team=UNLOCKED, main=KEY)
    assert r["out"] == PAD_UNTOUCHED
    assert r["calls"] == {"team": 1, "held": 0, "exempt": 0}


@needs_node
@pytest.mark.parametrize("main,off,shrink", [(KEY, AIR, "MAIN_HAND"), (AIR, KEY, "OFF_HAND"), (KEY, KEY, "MAIN_HAND"),
                                             (DIRT, KEY, "OFF_HAND")])
def test_pad_nether_locked_key_click_unlocks_and_takes_one_key(main, off, shrink):
    r = pad(NETHER, "MAIN_HAND", team=LOCKED, main=main, off=off)
    assert r["out"] == {"cancel": True, "unlock": True, "shrink": shrink, "message": MSG_UNLOCKED, "error": None}


@needs_node
@pytest.mark.parametrize("main,off", [(AIR, AIR), (DIRT, AIR), (AIR, DIRT)])
def test_pad_nether_locked_main_hand_without_key_is_refused(main, off):
    r = pad(NETHER, "MAIN_HAND", team=LOCKED, main=main, off=off)
    assert r["out"] == {"cancel": True, "unlock": False, "shrink": None, "message": MSG_LOCKED, "error": None}


@needs_node
@pytest.mark.parametrize("team", [LOCKED, NO_TEAM])
def test_pad_nether_locked_off_hand_event_cancels_silently(team):
    r = pad(NETHER, "OFF_HAND", team=team, off=KEY)
    assert r["out"] == {"cancel": True, "unlock": False, "shrink": None, "message": None, "error": None}
    assert r["calls"]["held"] == 0


@needs_node
@pytest.mark.parametrize("main,off", [(KEY, AIR), (AIR, KEY)])
def test_pad_no_team_keeps_the_key(main, off):
    r = pad(NETHER, "MAIN_HAND", team=NO_TEAM, main=main, off=off)
    assert r["out"] == {"cancel": True, "unlock": False, "shrink": None, "message": MSG_LOCKED, "error": None}


@needs_node
@pytest.mark.parametrize("hand,message", [("MAIN_HAND", MSG_BEYOND), ("OFF_HAND", None)])
def test_pad_end_always_cancels_without_a_team_lookup(hand, message):
    r = pad(END, hand, team=UNLOCKED, main=KEY)
    assert r["out"] == {"cancel": True, "unlock": False, "shrink": None, "message": message, "error": None}
    assert r["calls"] == {"team": 0, "held": 0, "exempt": 0}


@needs_node
@pytest.mark.parametrize("dim", [OVERWORLD, MINING, OTHER, BEYOND, MOON])
@pytest.mark.parametrize("hand", ["MAIN_HAND", "OFF_HAND"])
def test_pad_other_dimensions_are_untouched(dim, hand):
    r = pad(dim, hand, team=LOCKED, main=KEY)
    assert r["out"] == PAD_UNTOUCHED
    assert r["calls"] == {"team": 0, "held": 0, "exempt": 0}


@needs_node
@pytest.mark.parametrize("team,held", [("throw", {"main": KEY, "off": AIR}), (LOCKED, "throw")])
def test_pad_error_fails_closed_and_keeps_the_key(team, held):
    r = decide("pad", dim=NETHER, hand="MAIN_HAND", team=team, held=held)
    out = r["out"]
    assert (out["cancel"], out["unlock"], out["shrink"], out["message"]) == (True, False, None, None)
    assert "boom" in out["error"]


# ---- §4.3 travel check ----------------------------------------------------------------------------------------------

@needs_node
@pytest.mark.parametrize("team", [UNLOCKED, LOCKED, NO_TEAM])
def test_travel_beyond_is_closed_to_everyone_without_a_team_lookup(team):
    r = decide("travel", dest=BEYOND, exempt=False, team=team)
    assert r["out"] == {"cancel": True, "message": MSG_BEYOND, "error": None}
    assert r["calls"]["team"] == 0


@needs_node
@pytest.mark.parametrize("team,cancel,message", [(UNLOCKED, False, None), (LOCKED, True, MSG_TEAM), (NO_TEAM, True, MSG_TEAM)])
def test_travel_other_follows_the_team(team, cancel, message):
    r = decide("travel", dest=OTHER, exempt=False, team=team)
    assert r["out"] == {"cancel": cancel, "message": message, "error": None}
    assert r["calls"]["team"] == 1


@needs_node
@pytest.mark.parametrize("dest", [OTHER, BEYOND])
def test_travel_creative_and_spectator_are_exempt(dest):
    r = decide("travel", dest=dest, exempt=True, team=LOCKED)
    assert r["out"] == {"cancel": False, "message": None, "error": None}
    assert r["calls"]["team"] == 0


@needs_node
@pytest.mark.parametrize("dest", [NETHER, OVERWORLD, END, MINING, MOON])
def test_travel_other_destinations_are_untouched_and_read_nothing(dest):
    r = decide("travel", dest=dest, exempt=False, team=LOCKED)
    assert r["out"] == {"cancel": False, "message": None, "error": None}
    assert r["calls"] == {"team": 0, "held": 0, "exempt": 0}


@needs_node
@pytest.mark.parametrize("dest,exempt,team", [(OTHER, False, "throw"), (OTHER, "throw", UNLOCKED), (BEYOND, "throw", UNLOCKED)])
def test_travel_error_fails_closed_for_the_two_gated_dimensions(dest, exempt, team):
    out = decide("travel", dest=dest, exempt=exempt, team=team)["out"]
    assert out["cancel"] is True and out["message"] is None and "boom" in out["error"]


@needs_node
@pytest.mark.parametrize("dest,cancel", [(OTHER, True), (BEYOND, True), (NETHER, False), (MOON, False), (None, False)])
def test_travel_outer_error_cancels_only_the_gated_dimensions(dest, cancel):
    out = decide("travelError", dest=dest)["out"]
    assert out == {"cancel": cancel, "message": None, "error": "Error: outer boom"}


# ---- §4.4 arrival check ---------------------------------------------------------------------------------------------

@needs_node
@pytest.mark.parametrize("team", [UNLOCKED, LOCKED, NO_TEAM])
def test_arrival_beyond_always_sends_to_spawn(team):
    r = decide("arrival", dest=BEYOND, exempt=False, team=team)
    assert r["out"] == {"sendToSpawn": True, "message": MSG_BEYOND, "error": None}
    assert r["calls"]["team"] == 0


@needs_node
@pytest.mark.parametrize("team,send,message", [(UNLOCKED, False, None), (LOCKED, True, MSG_TEAM), (NO_TEAM, True, MSG_TEAM)])
def test_arrival_other_follows_the_team(team, send, message):
    r = decide("arrival", dest=OTHER, exempt=False, team=team)
    assert r["out"] == {"sendToSpawn": send, "message": message, "error": None}


@needs_node
@pytest.mark.parametrize("dest", [OTHER, BEYOND])
def test_arrival_creative_and_spectator_are_exempt(dest):
    r = decide("arrival", dest=dest, exempt=True, team=LOCKED)
    assert r["out"] == {"sendToSpawn": False, "message": None, "error": None}
    assert r["calls"]["team"] == 0


@needs_node
@pytest.mark.parametrize("dest", [NETHER, OVERWORLD, END, MINING, MOON])
def test_arrival_other_destinations_are_untouched_and_read_nothing(dest):
    r = decide("arrival", dest=dest, exempt=False, team=LOCKED)
    assert r["out"] == {"sendToSpawn": False, "message": None, "error": None}
    assert r["calls"] == {"team": 0, "held": 0, "exempt": 0}


@needs_node
@pytest.mark.parametrize("dest,exempt,team,message", [(OTHER, False, "throw", MSG_TEAM), (OTHER, "throw", UNLOCKED, MSG_TEAM),
                                                     (BEYOND, "throw", UNLOCKED, MSG_BEYOND)])
def test_arrival_error_treats_the_team_as_locked(dest, exempt, team, message):
    out = decide("arrival", dest=dest, exempt=exempt, team=team)["out"]
    assert out["sendToSpawn"] is True and out["message"] == message and "boom" in out["error"]


@needs_node
@pytest.mark.parametrize("dest,send,message", [(OTHER, True, MSG_TEAM), (BEYOND, True, MSG_BEYOND), (NETHER, False, None),
                                               (None, False, None)])
def test_arrival_outer_error_moves_only_from_the_gated_dimensions(dest, send, message):
    out = decide("arrivalError", dest=dest)["out"]
    assert out == {"sendToSpawn": send, "message": message, "error": "Error: outer boom"}


# ---- one shared scope -----------------------------------------------------------------------------------------------

TOP_LEVEL = re.compile(r"^(?:const|let|var|function)\s+([A-Za-z_$][\w$]*)", re.M)


def test_server_script_top_level_names_are_unique():
    """KubeJS 2101 runs every server script in one scope (HANDOFF §6): a top-level name may be declared only once."""
    seen = {}
    for path in sorted(SERVER_SCRIPTS.rglob("*.js")):
        for name in TOP_LEVEL.findall(path.read_text(encoding="utf-8")):
            seen.setdefault(name, []).append(str(path.relative_to(SERVER_SCRIPTS)))
    dupes = {name: files for name, files in seen.items() if len(files) > 1}
    assert dupes == {}
    assert seen["OTHER_GATE"] == ["lib/other_gate.js"]
