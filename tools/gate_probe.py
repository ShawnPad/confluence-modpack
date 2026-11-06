#!/usr/bin/env python3
"""One command for the Rhino-side gate check (v0.3, D138): node cannot see Rhino, so this runs the real events.js on a server.

    python3 tools/gate_probe.py [--events FILE] [--rows FILE]

It starts tools/server_session.sh on a throwaway world, installs tools/gate_probe/standin.js in the run folder only, drives rows
P2.1-P2.12, P3.1 and P3.4 (the Other gate) and P6.0-P6.5 (the Piglich), prints one row per check in the test log's format, then
removes the stand-in and the world and stops. Exit 0 only if every row passes, no unnamed ERROR line was logged during the rows and
the stop worked. It refuses to run beside another session: that session's world and server are left alone. If the stop fails, the
stand-in still goes and --events is still put back, the exit is non-zero, and a world a server may still have open stays on disk.
--events FILE  load this file as the run folder's events.js for the session (to prove the check fails on old code; it is put back).
--rows FILE    also append the rows to FILE.

What it does not prove (research/phase7-v0.3-probe-evidence/README.md): the stand-in has no client, so no action-bar text, no chat
click, no client hand sequencing, no packet reach check, no quest screen, no landing x, z after a change of dimension and no real
rejoin (P3.4 posts the login event for a stand-in already in The Other). Pack
rows P3.2, P4.x and P5.x are not driven here. Measured damage is for server.properties' difficulty only.
P6.2 and P6.3 depend on the route: they fired with P1 brought in by the pad (the full run) and stayed quiet with P1 brought in by a
cross-level tp (--piglich-only, and --events old code, where the pad cannot unlock), cause [UNVERIFIED]. So under those two modes their
FAIL is not a finding about the Piglich.
"""
import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = Path(os.environ.get("CONFLUENCE_RUN", ROOT / ".run" / "server"))
SESSION = ROOT / "tools" / "server_session.sh"
STANDIN = ROOT / "tools" / "gate_probe" / "standin.js"
INSTALLED = RUN / "kubejs" / "server_scripts" / "zz_gate_probe_standin.js"
EVENTS = ROOT / "kubejs" / "server_scripts" / "events.js"
RUN_EVENTS = RUN / "kubejs" / "server_scripts" / "events.js"
KJ_LOG = RUN / "logs" / "kubejs" / "server.log"
LATEST = RUN / "logs" / "latest.log"
WORLD = "gate_probe_throwaway"
DIMS = ["minecraft:overworld", "minecraft:the_nether", "minecraft:the_end", "allthemodium:the_other", "allthemodium:the_beyond"]
OTHER, BEYOND, NETHER, END, OVER, MINING = ("allthemodium:the_other", "allthemodium:the_beyond", "minecraft:the_nether",
                                            "minecraft:the_end", "minecraft:overworld", "allthemodium:mining")
P1, P2, P3 = "ProbeP1", "ProbeP2", "ProbeP3"
KEY = "kubejs:other_key"
NETHER_PAD, END_PAD, OVER_PAD = (102, 101, 102), (2, 71, 602), (8, 201, 0)
# ERROR lines the stand-in itself causes, named one by one; anything else logged during the rows fails the run.
# The borrowed memory channel (H.conn): a server packet to a connection with no client encoder.
TOLERATED = [re.compile(r"\[Netty Local Client IO #\d+/ERROR\] \[net\.minecraft\.network\.PacketEncoder/\]: .*custom_payload"),
             # Old empty slots in mod structures (D141), as in tools/boot_allowlist.txt. This wording only.
             re.compile(r"\[[^/]+/ERROR\] \[net\.minecraft\.world\.item\.ItemStack/\]: Tried to load invalid item: 'Item must not be minecraft:air'")]


def session(*args, timeout=200):
    r = subprocess.run([str(SESSION), *args], capture_output=True, text=True, timeout=timeout, cwd=ROOT)
    return r.stdout + r.stderr


def con(command, secs=15):
    return session("cmd", command, str(secs), timeout=secs + 60).strip()


def cp(code, secs=20):
    """Run JS in the stand-in. The console reply is one 'cprobe> ...' line; a stand-in error raises, so the row fails."""
    out = con("cprobe " + code, secs)
    m = re.search(r"cprobe> (.*)", out)
    if not m or m.group(1).startswith("ERR "):
        raise RuntimeError(f"cprobe {code[:60]}: {out[:300]}")
    return m.group(1)


def fill(command):
    """`fill` can answer 'That position is not loaded' right after a forceload (plan Task 12 Step 9)."""
    for _ in range(6):
        out = con(command, 120)
        if "Successfully filled" in out or "No blocks were filled" in out:
            return
        time.sleep(2)
    raise RuntimeError(f"{command}: {out[:200]}")


def build_sites():
    for c in ("gamerule keepInventory true", "gamerule spawnRadius 0", "gamerule doMobSpawning false", "gamerule doDaylightCycle false",
              "time set day"):
        con(c)
    def ei(dim):
        return f"execute in {dim} run "
    con(ei(OVER) + "forceload add -6 -6 14 14")
    fill(ei(OVER) + "fill -6 199 -6 14 208 14 minecraft:glass hollow")
    fill(ei(OVER) + "fill -5 200 -5 13 200 13 minecraft:smooth_stone")
    con(ei(OVER) + f"setblock {OVER_PAD[0]} {OVER_PAD[1]} {OVER_PAD[2]} allthemodium:teleport_pad")
    con("setworldspawn 0 201 0")
    con(ei(OVER) + "forceload add 494 494 506 506")
    fill(ei(OVER) + "fill 494 199 494 506 206 506 minecraft:glass hollow")
    fill(ei(OVER) + "fill 495 200 495 505 200 505 minecraft:smooth_stone")
    con(ei(NETHER) + "forceload add 94 94 110 110")
    fill(ei(NETHER) + "fill 94 99 94 110 106 110 minecraft:glass hollow")
    fill(ei(NETHER) + "fill 95 100 95 109 100 109 minecraft:obsidian")
    con(ei(NETHER) + f"setblock {NETHER_PAD[0]} {NETHER_PAD[1]} {NETHER_PAD[2]} allthemodium:teleport_pad")
    con(ei(END) + "forceload add -6 594 10 610")
    fill(ei(END) + "fill -6 69 594 10 76 610 minecraft:glass hollow")
    fill(ei(END) + "fill -5 70 595 9 70 609 minecraft:obsidian")
    con(ei(END) + f"setblock {END_PAD[0]} {END_PAD[1]} {END_PAD[2]} allthemodium:teleport_pad")
    con(ei(OTHER) + "forceload add 196 196 204 204")
    fill(ei(OTHER) + "fill 196 199 196 204 199 204 minecraft:glass")
    con(ei(BEYOND) + "forceload add 0 0")
    fill(ei(BEYOND) + "fill -2 149 -2 2 149 2 minecraft:glass")
    con(ei(OTHER) + "forceload add 300 300 340 340")
    fill(ei(OTHER) + "fill 300 150 300 340 160 340 minecraft:stone hollow")


def status():
    try:
        return session("status", timeout=30)
    except (subprocess.TimeoutExpired, OSError) as e:
        return f"status failed: {e}"


def own_session(reply, proc):
    """`wait` answers for whatever session is up, so only this reply from a start process still running makes it ours."""
    return f"session: up (world {WORLD})" in reply and proc.poll() is None


def melee_seen(out):
    """P6.3: a `mob` damage source or 7.0 damage on the stand-in. Other damage in the window can be its fireballs and the fire."""
    return bool(re.search(r"playerSources=\[(?:[^\]]* )?mobx\d", out) or re.search(r"playerDamage=\[(?:[^\]]* )?7\.0x\d", out))


def lines(path):
    return path.read_text(encoding="utf-8", errors="replace").splitlines() if path.exists() else []


class Rows:
    def __init__(self, label, rows_file):
        self.label, self.rows_file, self.failed, self.count = label, rows_file, 0, 0

    def row(self, rid, players, did, expected, run):
        """`run` returns (ok, observed); a raised error is a FAIL with its text. Gate ERROR lines fail any row."""
        mark = len(lines(KJ_LOG))
        try:
            ok, observed = run()
        except Exception as e:   # a row's failure must not stop the others or the teardown
            ok, observed = False, f"stand-in error: {e}"
        gate = [ln for ln in lines(KJ_LOG)[mark:] if "confluence other-gate" in ln]
        errors = [ln for ln in gate if "ERROR" in ln]
        if errors:
            ok = False
        text = observed + ("" if not gate else " | gate log: " + " ; ".join(ln.split("other-gate: ", 1)[-1][:150] for ln in gate))
        verdict = "PASS" if ok else "FAIL"
        self.count += 1
        self.failed += 0 if ok else 1
        line = (f"| {datetime.date.today().isoformat()} | {rid} | {players} | stand-in | {did} | {expected} | "
                f"{self.label}: {text.replace('|', '/')} | {verdict} |")
        print(line, flush=True)
        if self.rows_file:
            with open(self.rows_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")


def gate_since(mark):
    return [ln for ln in lines(KJ_LOG)[mark:] if "confluence other-gate" in ln]


def click(n, pad, hand="main", sneak=True):
    return cp(f"H.click('{n}',{pad[0]},{pad[1]},{pad[2]},'{hand}',{'true' if sneak else 'false'},'up')")


def dim(n):
    return cp(f"H.dim('{n}')")


def key_count(n):
    return int(float(cp(f"H.count('{n}','{KEY}')")))


def pad_stays(n, pad, want):
    """Sneak-click and read the dimension. A `travel check stopped` line fails it: the pad is meant to refuse before any travel,
    so without this a pad that stopped refusing would be masked by the travel check behind it."""
    mark = len(lines(KJ_LOG))
    click(n, pad)
    got = dim(n)
    time.sleep(1)
    stopped = [ln for ln in gate_since(mark) if "travel check stopped" in ln]
    return got == want and not stopped, f"{n} in {got}; travel check lines {len(stopped)}"


def gate_rows(r):
    def to_nether(n):
        cp(f"H.tp('{n}','{NETHER}',98.5,101,98.5)")

    def p27():
        con(f"gamemode creative {P2}", 5)
        cp(f"H.tp('{P2}','{OTHER}',102.5,150,102.5)")
        a = dim(P2)
        cp(f"H.tp('{P2}','{BEYOND}',0.5,150,0.5)")
        b = dim(P2)
        to_nether(P2)
        click(P2, NETHER_PAD)
        c = dim(P2)
        cp(f"H.tp('{P2}','{END}',-1.5,71,598.5)")
        click(P2, END_PAD)
        d = dim(P2)
        con(f"gamemode survival {P2}", 5)
        return (a, b, c, d) == (OTHER, BEYOND, NETHER, END), f"landed {a}, {b}; after pads {c}, {d}"
    r.row("P2.7", "L", "tp into the_other and the_beyond as creative; sneak-click Nether and End pads",
          "both tps arrive; pads stop them; no gate error", p27)

    def p21():
        to_nether(P2)
        return pad_stays(P2, NETHER_PAD, NETHER)
    r.row("P2.1", "L", "sneak-click Nether pad, hands empty, no key used yet", "stays in the Nether, refused by the pad; no gate error", p21)

    def p28():
        cp(f"H.tp('{P2}','{END}',-1.5,71,598.5)")
        return pad_stays(P2, END_PAD, END)
    r.row("P2.8", "L", "sneak-click End pad, hands empty", "stays in the End, refused by the pad; no gate error", p28)

    def p29():
        cp(f"H.tp('{P2}','{OVER}',6.5,201,0.5)")
        out = pad_stays(P2, OVER_PAD, MINING)
        cp(f"H.tp('{P2}','{OVER}',0.5,201,0.5)")
        return out
    r.row("P2.9", "L", "sneak-click Overworld pad, hands empty", "arrives in allthemodium:mining; no gate error", p29)

    def p22():
        to_nether(P1)
        con(f"clear {P1}", 5)
        con(f"give {P1} {KEY} 2")
        cp(f"H.select('{P1}',0)")
        mark = len(lines(KJ_LOG))
        click(P1, NETHER_PAD, sneak=False)
        n, d = key_count(P1), dim(P1)
        unlocked = [ln for ln in gate_since(mark) if "unlocked The Other" in ln]
        return (n, d, len(unlocked)) == (1, NETHER, 1), f"keys left {n}; in {d}; unlock lines {len(unlocked)}"
    r.row("P2.2", "P1", "right-click Nether pad holding 2 keys (main hand)", "one key used; one unlock line; stays in the Nether", p22)

    def p23():
        con(f"clear {P1} {KEY}", 5)
        to_nether(P1)
        click(P1, NETHER_PAD)
        time.sleep(1)
        got = dim(P1)
        return got == OTHER, f"{P1} in {got}"
    r.row("P2.3", "P1", "sneak-click Nether pad, hands empty, after unlock", "arrives in the_other", p23)
    con(f"execute in {OTHER} run forceload add 100 100")
    fill(f"execute in {OTHER} run fill 98 149 98 102 149 102 minecraft:glass")
    cp(f"H.tp('{P1}','{OTHER}',100.5,150,100.5)")

    def p24():
        to_nether(P2)
        return pad_stays(P2, NETHER_PAD, NETHER)
    r.row("P2.4", "P2", "P2 (own team) sneak-clicks Nether pad after P1 unlocked", "stays in the Nether, refused by the pad; no gate error", p24)

    def p25():
        mark = len(lines(KJ_LOG))
        cp(f"H.raw('tpa {P1}','{P2}')")
        cp(f"H.tpaAccept('{P1}')")
        time.sleep(2)
        got = dim(P2)
        stopped = [ln for ln in gate_since(mark) if f"travel check stopped {P2} going to {OTHER}" in ln]
        return got == NETHER and bool(stopped), f"{P2} in {got}; travel check lines {len(stopped)}"
    r.row("P2.5", "P1, P2", "P2 ran /tpa ProbeP1; P1 accepted", "P2 stays in the Nether; travel check line", p25)

    def p26():
        con(f"gamemode creative {P2}", 5)
        cp(f"H.tp('{P2}','{OTHER}',200.5,200,200.5)")
        cp(f"H.hold('{P2}','waystones:waystone',1)")
        cp(f"H.click('{P2}',202,199,202,'main',false,'up')")
        time.sleep(1)
        cp(f"H.wsFind('{P2}',202,200,202)")
        cp(f"H.click('{P2}',202,200,202,'main',false,'north')")
        time.sleep(1)
        active = cp(f"H.wsFind('{P2}',202,200,202)")
        cp(f"H.close('{P2}')")
        con(f"gamemode survival {P2}", 5)
        cp(f"H.tp('{P2}','{OVER}',500.5,201,500.5)")
        con(f"clear {P2}", 5)
        con(f"xp add {P2} 30 levels")
        con(f"give {P2} waystones:warp_stone 1")
        cp(f"H.select('{P2}',0)")
        mark = len(lines(KJ_LOG))
        cp(f"H.useitem('{P2}')")
        time.sleep(5)
        cp(f"H.wsSelect('{P2}')")
        time.sleep(2)
        got = dim(P2)
        stopped = [ln for ln in gate_since(mark) if f"travel check stopped {P2} going to {OTHER}" in ln]
        return got == OVER and bool(stopped), f"{active}; {P2} in {got}; travel check lines {len(stopped)}"
    r.row("P2.6", "L", "warp stone from the Overworld to a waystone in The Other, by the packet handler", "warp stopped; travel check line", p26)

    def p31():
        cp(f"H.tp('{P3}','{OVER}',3.5,201,3.5)")
        con(f"clear {P3}", 5)
        con(f'give {P3} tombstone:tablet_of_assistance[tombstone:tb_enchanted=true,tombstone:tb_engraved_name="{P1}"]')
        cp(f"H.select('{P3}',0)")
        mark = len(lines(KJ_LOG))
        cp(f"H.useitem('{P3}')")
        time.sleep(6)
        u = cp(f"H.uuid('{P3}')")
        cp(f"H.raw('tbacceptteleport {u}','{P1}')")
        time.sleep(3)
        got = dim(P3)
        sent = [ln for ln in gate_since(mark) if f"arrival check sent {P3} from {OTHER} to the Overworld spawn" in ln]
        return got == OVER and bool(sent), f"{P3} in {got}; arrival check lines {len(sent)}"
    r.row("P3.1", "P1, P3", "locked P3 held a Tablet of Assistance engraved with P1 (80 ticks); P1 ran /tbacceptteleport <uuid>",
          "back in the Overworld one tick after arriving; arrival check line", p31)

    def p34():
        con(f"gamemode creative {P3}", 5)
        cp(f"H.tp('{P3}','{OTHER}',200.5,200,200.5)")
        there = dim(P3)
        con(f"gamemode survival {P3}", 5)
        mark = len(lines(KJ_LOG))
        cp(f"H.login('{P3}')")
        time.sleep(2)
        got = dim(P3)
        sent = [ln for ln in gate_since(mark) if f"arrival check sent {P3} from {OTHER} to the Overworld spawn" in ln]
        return there == OTHER and got == OVER and bool(sent), f"before the login {there}; after it {got}; arrival check lines {len(sent)}"
    r.row("P3.4", "P3", "locked P3 in The Other (tp as creative, then survival); login event posted", "back in the Overworld; arrival check line", p34)

    def p210():
        cp(f"H.alive('{P1}')")
        said = [cp(f"H.raw('ftbteams party create probe_party','{P1}')")]
        time.sleep(1)
        said.append(cp(f"H.raw('ftbteams party invite {P2}','{P1}')"))
        team = cp(f"H.team('{P1}')")
        said.append(cp(f"H.raw('ftbteams party join {team}','{P2}')"))
        same = cp(f"H.team('{P2}')") == team
        click(P2, NETHER_PAD)
        time.sleep(1)
        got = dim(P2)
        return same and got == OTHER, f"same team {same}; {P2} in {got}" + ("" if same else "; " + " ; ".join(said))
    def p210_setup():
        con(f"clear {P2}", 5)   # P2.6 left a warp stone in the main hand, and the pad wants empty hands
        to_nether(P2)
        return p210()
    r.row("P2.10", "P1, P2", "P2 joins P1's party, then sneak-clicks Nether pad with no key", "P2 arrives in the_other", p210_setup)

    def p211():
        pad = cp(f"H.findBlock('{P2}','allthemodium:teleport_pad',12,60,250)")
        back = "no arrival pad within 12 blocks"
        returned = None
        if pad != "none" and dim(P2) == OTHER:
            x, y, z = (int(v) for v in pad.split(","))
            click(P2, (x, y, z))
            time.sleep(1)
            returned = dim(P2)
            back = f"pad {pad} returned to {returned}"
        cp(f"H.raw('ftbteams party leave','{P2}')")
        to_nether(P2)
        click(P2, NETHER_PAD)
        got = dim(P2)
        return returned == NETHER and got == NETHER, f"{back}; left the party, team {cp(f'H.team({chr(39)}{P2}{chr(39)})')}; {P2} in {got}"
    r.row("P2.11", "P2", "P2 sneak-clicks the arrival pad in The Other, leaves the party, sneak-clicks Nether pad",
          "the arrival pad returns to the Nether; then stays in the Nether (the unlock stays with the party)", p211)

    def p212():
        con(f"clear {P2}", 5)
        con(f"item replace entity {P2} weapon.offhand with {KEY} 2")
        mark = len(lines(KJ_LOG))
        click(P2, NETHER_PAD, "main", False)
        after_main = key_count(P2)
        click(P2, NETHER_PAD, "off", False)
        after_off, got = key_count(P2), dim(P2)
        unlocked = [ln for ln in gate_since(mark) if "unlocked The Other" in ln]
        ok = (after_off, got, len(unlocked)) == (1, NETHER, 1)
        return ok, f"keys after main event {after_main}, after off-hand event {after_off}; in {got}; unlock lines {len(unlocked)}"
    r.row("P2.12", "P2", "2 keys in the off hand, main hand empty: useItemOn main hand, then off hand", "one key used; one unlock line; stays in the Nether", p212)


def piglich_rows(r):
    ot = f"execute in {OTHER} run "
    pg = "@e[type=allthemodium:piglich,x=320,y=151,z=320,distance=..80,limit=1]"
    cp(f"H.alive('{P1}')")
    cp(f"H.tp('{P1}','{OTHER}',305.5,151,320.5)")
    con(f"clear {P1}", 5)
    con(f"gamemode survival {P1}", 5)
    con(f"{ot}kill @e[type=!minecraft:player,x=300,y=150,z=300,dx=40,dy=10,dz=40]")
    con(f"{ot}summon allthemodium:piglich 330 151 320")

    def num(out):
        m = re.search(r"(-?\d+(?:\.\d+)?)[a-z]?\s*$", out)
        return float(m.group(1)) if m else None

    def p61():
        got = {"health": num(con(f"{ot}data get entity {pg} Health")),
               **{k: num(con(f"{ot}attribute {pg} minecraft:generic.{a} get"))
                  for k, a in (("armor", "armor"), ("toughness", "armor_toughness"), ("attack", "attack_damage"))}}
        return got == {"health": 1024.0, "armor": 24.0, "toughness": 20.0, "attack": 12.0}, str(got)
    r.row("P6.1", "-", "summoned Piglich: Health and attributes", "health 1024, armor 24, toughness 20, attack 12", p61)

    def hold_at(dist, secs):
        """Keep the stand-in `dist` from the Piglich for the whole monitor window, however long each console round takes."""
        cp(f"H.near('{P1}',{dist})")
        cp(f"H.monStart('{P1}',{secs})")
        end = time.time() + secs + 1
        while time.time() < end:
            time.sleep(1)
            cp(f"H.near('{P1}',{dist})")
        return cp("H.monRead()")

    def provoked(out, fired, dist, secs):
        """The rows ask whether the attack fires. Unprovoked targeting differed between runs of this harness (cause [UNVERIFIED]),
        so a quiet first window gets one hit and a second window, and the row says which window fired."""
        if fired(out):
            return True, "unprovoked: " + out
        cp(f"H.near('{P1}',1.5)")
        cp(f"H.hit('{P1}')")
        second = hold_at(dist, secs)
        return fired(second), f"unprovoked window quiet; after one hit: {second}"

    def p62():
        con(f"effect clear {P1}")   # the attack rows measure damage
        out = con(f"attribute {P1} minecraft:generic.max_health base set 400")
        if "400" not in out:
            raise RuntimeError(f"max_health: {out[:200]}")
        cp(f"H.heal('{P1}',400)")
        fired = lambda o: int(re.search(r"fireballs=(\d+)", o).group(1)) > 0
        return provoked(hold_at(12, 20), fired, 12, 20)
    r.row("P6.2", "P1", "stand-in held 12 blocks from the Piglich, no hits, per-tick monitor", "small fireballs fire", p62)

    def p63():
        cp(f"H.alive('{P1}')")
        cp(f"H.heal('{P1}',400)")
        return provoked(hold_at(1.5, 10), melee_seen, 1.5, 10)
    r.row("P6.3", "P1", "stand-in held within 2 blocks, no hits, per-tick monitor", "melee lands (figure recorded)", p63)

    def p64():
        cp(f"H.alive('{P1}')")
        cp(f"H.heal('{P1}',400)")
        con(f"effect give {P1} minecraft:resistance 600 4 true")
        cp("H.killWitches()")
        cp(f"H.near('{P1}',1.5)")
        cp(f"H.monStart('{P1}',40)")
        con(f"give {P1} minecraft:netherite_sword 1")
        cp(f"H.select('{P1}',0)")
        for _ in range(10):
            time.sleep(1.5)
            cp(f"H.near('{P1}',1.5)")
            cp(f"H.hit('{P1}')")
        time.sleep(12)
        out = cp("H.monRead()")
        # No witches> 0 here: spawnSupport makes 5 random placement tries at a distance, so 6 damage events can place none
        # (witches=0 on 2026-11-06 at 1ff3efb; 1 to 3 in four other runs). D5.3 says "up to one", and the count stays in the row.
        two = int(re.search(r"twoInOneTick=(\d+)", out).group(1))
        nodrop = int(re.search(r"witchNoDrop=(\d+)", out).group(1))
        return two == 0 and nodrop == 0, out
    r.row("P6.4", "P1", "10 Player.attack sword hits, then 12 s; per-tick monitor of Piglich health and new Witches",
          "Never two Witches in a tick, never one in a tick without damage to the Piglich (D5.3's clause); the count varies", p64)

    def p65():
        cp("H.killWitches()")
        con(f"{ot}data merge entity {pg} {{Health:1.0f}}")
        heart = "allthemodium:piglich_heart"
        before = int(float(cp(f"H.count('{P1}','{heart}')")))
        hits, alive = 0, 1
        while alive and hits < 5:   # a hit inside the Piglich's damage cooldown does nothing
            cp(f"H.near('{P1}',1.5)")
            cp(f"H.hit('{P1}')")
            hits += 1
            time.sleep(1)
            alive = int(float(cp("H.piglichs()")))
        ground = int(float(cp("H.hearts()")))
        picked = int(float(cp(f"H.count('{P1}','{heart}')"))) - before   # the stand-in stands close enough to pick the drop up
        n = ground + picked
        return (not alive) and n == 1, f"{n} Piglich Heart item(s) dropped ({ground} on the ground, {picked} picked up) after {hits} hit(s); Piglichs alive {alive}"
    r.row("P6.5", "P1", "set Piglich health to 1, kill it with Player.attack", "exactly one Piglich Heart", p65)

    def p60():
        out = con(f"{ot}locate structure allthemodium:ancient_pyramid", 120)
        return "ancient_pyramid" in out and "nearest" in out, out[-160:]
    r.row("P6.0", "-", "console: locate structure allthemodium:ancient_pyramid in The Other", "a pyramid exists in this new world", p60)


def stop_session(proc):
    """True only if the stop says it worked and the start process has ended."""
    try:
        r = subprocess.run([str(SESSION), "stop"], capture_output=True, text=True, timeout=240, cwd=ROOT)
    except (subprocess.TimeoutExpired, OSError) as e:
        print(f"teardown: the stop did not finish: {e}")
        return False
    print((r.stdout + r.stderr).strip()[-400:])
    ok = r.returncode == 0
    if not ok:
        print(f"teardown: the stop exited {r.returncode}")
    try:
        proc.wait(timeout=120)
    except subprocess.TimeoutExpired:
        print("teardown: the session process did not end")
        ok = False
    return ok


def teardown(proc, run_events_was_replaced, mine):
    """Returns True if the session this run started is gone. The stand-in and --events are put right whichever way that went."""
    clean = True
    try:
        if not mine:
            # Refused or still booting. A boot of ours gets stopped (status said down before the start); anything else is not ours.
            st = status()
            mine = proc.poll() is None and (f"world {WORLD}" in st or "session: starting" in st)
        if mine:
            try:
                cp("H.despawnAll()")
            except Exception as e:
                print(f"teardown: {e}")
            for d in DIMS:
                try:
                    con(f"execute in {d} run forceload remove all", 5)
                except Exception as e:
                    print(f"teardown: {e}")
            clean = stop_session(proc)
        else:
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                print("teardown: the refused start process did not end")
                clean = False
    finally:
        INSTALLED.unlink(missing_ok=True)
        if run_events_was_replaced:
            shutil.copyfile(EVENTS, RUN_EVENTS)
    st = status()
    if "session: down" in st:
        shutil.rmtree(RUN / WORLD, ignore_errors=True)
    else:
        print(f"teardown: {RUN / WORLD} kept, because the session is not down: {st.strip()[-200:]}")
    return clean


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run the Other-gate and Piglich rows on a throwaway world, under Rhino.")
    ap.add_argument("--events", type=Path, help="load this events.js in the run folder for this session only")
    ap.add_argument("--rows", type=Path, help="also append the rows to this file")
    ap.add_argument("--piglich-only", action="store_true", help="skip the gate rows (P1 is then placed in The Other by tp, untested)")
    args = ap.parse_args(argv)
    if not (RUN / "run.sh").exists():
        print(f"no server in {RUN}: run tools/server_boot.sh once first")
        return 2
    if WORLD != "gate_probe_throwaway" or (RUN / WORLD).resolve().parent != RUN.resolve():
        raise AssertionError("refusing a world outside the run folder")
    # Before anything is touched: `start` would refuse too, but only after this run had put a stand-in beside a live server.
    st = status()
    if "session: down" not in st:
        print(f"refusing: another session is up or starting, and this run would alter its world: {st.strip()[-200:]}")
        return 2
    shutil.rmtree(RUN / WORLD, ignore_errors=True)
    shutil.copyfile(STANDIN, INSTALLED)
    os.environ["PATH"] = f"{Path.home()}/go/bin:" + os.environ["PATH"]
    log = open(ROOT / ".run" / "gate-probe-session.log", "w")
    proc = subprocess.Popen([str(SESSION), "start", "--world", WORLD], stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
    state = {"mine": False, "replaced": False}
    rows = Rows("old events.js" if args.events else "working-tree events.js", args.rows)
    code, clean = None, False
    try:
        code = drive(args, proc, rows, state)
    finally:
        clean = teardown(proc, state["replaced"], state["mine"])
        log.close()
    if code is not None:
        return code
    last = f"gate_probe: {rows.count} rows, {rows.failed} failed ({rows.label})"
    if args.piglich_only:
        last += "; GATE ROWS DID NOT RUN (--piglich-only)"
    if not clean:
        last += "; THE STOP FAILED (see above)"
    print(last)
    return 1 if rows.failed or not clean else 0


def drive(args, proc, rows, state):
    """Everything between start and teardown. None when the rows ran, or the exit code when they could not."""
    for _ in range(60):   # `wait` says "not running" until the start process has written its pid file
        if (RUN / "session.pids").exists():
            break
        time.sleep(1)
    out = session("wait", timeout=700)
    state["mine"] = own_session(out, proc)
    if not state["mine"]:
        print(f"the session is not this run's (expected world {WORLD} and a live start process; "
              "a failed start is a finding, D134; do not retry it away):", out[-300:])
        print((ROOT / ".run" / "gate-probe-session.log").read_text(errors="replace")[-800:])
        return 2
    same = EVENTS.read_bytes() == RUN_EVENTS.read_bytes()
    if args.events:
        shutil.copyfile(args.events, RUN_EVENTS)
        state["replaced"] = True
        print(con("reload", 180)[-200:])
    elif not same:
        print("the run folder's events.js differs from the working tree's: the sync did not take")
        return 2
    latest_mark = len(lines(LATEST))
    build_sites()
    for n in (P1, P2, P3):
        cp(f"H.spawn('{n}')")
        con(f"clear {n}", 5)
        # As plan Task 12 Step 9: they wait for minutes in The Other, where nothing else protects them.
        con(f"effect give {n} minecraft:resistance 3600 4 true")
        con(f"effect give {n} minecraft:fire_resistance 3600 0 true")
    if not args.piglich_only:
        gate_rows(rows)
    piglich_rows(rows)
    new_errors = [ln for ln in lines(LATEST)[latest_mark:] if "/ERROR]" in ln and not any(t.search(ln) for t in TOLERATED)]
    rows.row("LOG", "-", "ERROR lines in latest.log during the rows, except the named stand-in ones", "none",
             lambda: (not new_errors, f"{len(new_errors)} line(s): " + " ; ".join(ln[:220] for ln in new_errors[:6])))
    return None


if __name__ == "__main__":
    sys.exit(main())
