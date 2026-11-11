"""Deploy helper for the release task (v0.3 plan Task 13; promoted to tools/ by v1.0 plan Tasks 1-2). Never shipped:
.packwizignore lists tools/.

    <pterodactyl venv>/bin/python tools/ptero_wait.py servers
    <pterodactyl venv>/bin/python tools/ptero_wait.py wait <state> <seconds> [ident]
    <pterodactyl venv>/bin/python tools/ptero_wait.py waitlog <seconds> [since epoch]
    <pterodactyl venv>/bin/python tools/ptero_wait.py evidence <pack dir> <out.json> <since epoch>

API calls copied from ~/Documents/Projects/2-Homelab/pterodactyl: ptero.py Ptero.client() (client API, JSON), cmd_read()
(GET /api/client/servers/<id>/files/contents?file=...), the files/list call in _flatten_if_nested(), and update_tmod.py
wait_state() (GET /servers/<id>/resources -> attributes.current_state). The pterodactyl venv has `requests`. Both imports are
lazy (_api), so `import ptero_wait` works without them (tools/tests/test_ptero_wait.py).

`evidence` compares production with the local boot in <pack dir>/.run/server (v1.0 spec §4.2, §7.2, §9):
  - production's FTB Quests "Loaded ..." line and "confluence worldgen:" line must equal the local boot's, read from
    .run/server/logs/latest.log and .run/server/logs/kubejs/server.log (local_expectations), never hard-coded;
  - production's logs/kubejs/server.log must hold every SKIP_LINES line: start.sh never sets -Dconfluence.dev, so dump.js,
    tagcheck.js and routeexport.js must not run there (lib/dev.js);
  - production's kubejs/exported/ must be absent, or hold no file modified after <since epoch>, the restart time.
The rules are pure (problems, exported_problem), so a test can feed them made-up evidence.
"""
import gzip
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

SERVER = "93ec4619"
PTERO_DIR = os.path.expanduser("~/Documents/Projects/2-Homelab/pterodactyl")
FTBQ = "[FTB Quests/]: Loaded"
WORLDGEN = "confluence worldgen:"
# lib/dev.js's callers log these when -Dconfluence.dev is unset (kubejs/server_scripts/dump.js, tagcheck.js, routeexport.js).
SKIP_LINES = ("confluence dump: skipped (confluence.dev unset)", "confluence tagcheck: skipped (confluence.dev unset)",
              "confluence routeexport: skipped (confluence.dev unset)")   # routeexport.js: v1.0 plan Task 13
_PT = []


def _api():
    """(requests, the Ptero instance), imported and built on first use."""
    if PTERO_DIR not in sys.path:
        sys.path.insert(0, PTERO_DIR)
    import requests
    from ptero import Ptero
    if not _PT:
        _PT.append(Ptero())
    return requests, _PT[0]


def state(ident=SERVER):
    return _api()[1].client("GET", f"/servers/{ident}/resources")["attributes"]["current_state"]


def read(path):
    requests, pt = _api()
    r = requests.get(f"{pt.base}/api/client/servers/{SERVER}/files/contents",
                     headers=pt._headers(pt.cfg["PTERO_CLIENT_KEY"]), params={"file": path}, timeout=60)
    r.raise_for_status()
    return r.content


def listing(directory):
    """[{name, modified_at, ...}] for one server directory (the files/list call)."""
    return [f["attributes"] for f in _api()[1].client("GET", f"/servers/{SERVER}/files/list",
                                                      params={"directory": directory})["data"]]


def last(text, needle):
    hits = [line.strip() for line in text.splitlines() if needle in line]
    return hits[-1] if hits else ""


def after(line, needle):
    """The text after `needle` in `line`, stripped; '' when it is not there."""
    return line.split(needle, 1)[1].strip() if needle in line else ""


def boot_log(since=0.0):
    """latest.log, or the newest rotated log that holds the boot (latest.log rotates at midnight, HANDOFF §5 item 0).

    Rotated logs are read newest first by the listing's modified_at, not by name: the midnight rollover writes
    YYYY-MM-DD-1.log.gz, which is newer than that day's startup rollovers -2, -3, ... (files/list /logs, 2026-09-25).
    Files modified before `since` (epoch seconds) are skipped.
    """
    log = read("logs/latest.log").decode("utf-8", "replace")
    if FTBQ in log:
        return log, "logs/latest.log"
    rotated = [(datetime.fromisoformat(a["modified_at"]).timestamp(), a["name"]) for a in listing("/logs")
               if re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d+\.log\.gz", a["name"])]
    for mtime, name in sorted(rotated, reverse=True):
        if mtime < since:
            break
        text = gzip.decompress(read(f"logs/{name}")).decode("utf-8", "replace")
        if FTBQ in text:
            return text, f"logs/{name}"
    return log, "logs/latest.log"


def local_expectations(run: Path) -> dict:
    """What production must print, read from the local boot in `run` (<pack>/.run/server): the text after FTBQ in
    logs/latest.log and after WORLDGEN in logs/kubejs/server.log, '' for a line or file that is not there."""
    def text(rel):
        p = run / rel
        return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""
    return {"ftbq": after(last(text("logs/latest.log"), FTBQ), FTBQ),
            "worldgen": after(last(text("logs/kubejs/server.log"), WORLDGEN), WORLDGEN)}


def exported_problem(entries, since):
    """None when kubejs/exported/ is absent (`entries` None) or no file in it was modified after `since` (epoch seconds);
    otherwise a message naming the newest such file."""
    if entries is None:
        return None
    newer = sorted((a["modified_at"], a["name"]) for a in entries
                   if datetime.fromisoformat(a["modified_at"]).timestamp() > since)
    if not newer:
        return None
    stamp, name = newer[-1]
    return f"kubejs/exported/{name} modified {stamp}, after the restart"


def problems(ev, expect):
    """One message per failed rule; [] when production matches the local boot and spec §7.2."""
    bad = []
    if ev["packFileHash"] != ev["pack_sha256"]:
        bad.append("packwiz.json packFileHash is not the sha256 of pack.toml")
    if not ev["done_line"]:
        bad.append("no 'Done (' line in the boot log")
    for key, line_key, needle, what in (("ftbq", "ftbq_line", FTBQ, "FTB Quests"), ("worldgen", "worldgen_line", WORLDGEN,
                                                                                         "worldgen")):
        if not expect[key]:
            bad.append(f"no {what} line in the local boot to compare with (boot locally first)")
        elif after(ev[line_key], needle) != expect[key]:
            bad.append(f"{what} line differs from the local boot's: server {after(ev[line_key], needle)!r}, "
                       f"local {expect[key]!r}")
    if ev["kubejs_errors"] != 0:
        bad.append(f"{ev['kubejs_errors']} KubeJS ERROR lines on the server")
    if not ev["tombstone_line"].endswith("lost_tablet_search_outside_world = false"):
        bad.append("Tombstone key is not false")
    if not ev["lang_same_as_pack"]:
        bad.append("the server's lang file differs from the pack's")
    for line in SKIP_LINES:
        if line not in ev["skip_lines"]:
            bad.append(f"skip line missing from logs/kubejs/server.log: '{line}'")
    if ev["exported"] is not None:
        bad.append(ev["exported"])
    return bad


def evidence(pack, out, since):
    ev = {}
    ev["packFileHash"] = json.loads(read("packwiz.json"))["packFileHash"]["value"]
    ev["pack_sha256"] = hashlib.sha256((pack / "pack.toml").read_bytes()).hexdigest()
    log, ev["log_file"] = boot_log()
    ev["done_line"] = last(log, "Done (")
    ev["ftbq_line"] = last(log, FTBQ)
    kjs = read("logs/kubejs/server.log").decode("utf-8", "replace")
    ev["worldgen_line"] = last(kjs, WORLDGEN)
    ev["skip_lines"] = [s for s in SKIP_LINES if s in kjs]
    ev["kubejs_errors"] = sum(1 for f in ("logs/kubejs/startup.log", "logs/kubejs/server.log")
                              for line in read(f).decode("utf-8", "replace").splitlines()
                              if re.match(r"^\[.*ERROR", line))
    tomb = read("config/tombstone-common.toml")
    ev["tombstone_line"] = next((f"{i}: {line.strip()}" for i, line in enumerate(tomb.decode().splitlines(), 1)
                                 if "lost_tablet_search_outside_world" in line), "")
    ev["tombstone_same_as_pack"] = tomb == (pack / "config" / "tombstone-common.toml").read_bytes()
    ev["lang_same_as_pack"] = (read("config/ftbquests/quests/lang/en_us.snbt")
                               == (pack / "config" / "ftbquests" / "quests" / "lang" / "en_us.snbt").read_bytes())
    names = {a["name"] for a in listing("/kubejs")}
    ev["exported"] = exported_problem(listing("/kubejs/exported") if "exported" in names else None, since)
    expect = local_expectations(pack / ".run" / "server")
    ev["local_ftbq"], ev["local_worldgen"], ev["since"] = expect["ftbq"], expect["worldgen"], since
    bad = problems(ev, expect)
    out.write_text(json.dumps(ev, indent=1) + "\n")
    for key, val in ev.items():
        print(f"{key}: {val}")
    print("SERVER OK" if not bad else "SERVER FAIL: " + "; ".join(bad))
    return 1 if bad else 0


def main(argv):
    if argv[:1] == ["servers"]:
        for s in _api()[1].client("GET", "")["data"]:
            a = s["attributes"]
            print("\t".join([a["identifier"], a["name"], str(a["limits"]["memory"]), state(a["identifier"])]))
        return 0
    if argv[:1] == ["wait"]:
        want, timeout = argv[1], int(argv[2])
        ident = argv[3] if len(argv) > 3 else SERVER
        t0, s, seen = time.time(), None, set()
        while time.time() - t0 < timeout:
            s = state(ident)
            seen.add(s)
            if s == want:
                print(f"{ident}: {s} after {int(time.time() - t0)}s")
                return 0
            if want == "running" and s == "offline" and "starting" in seen:
                # start.sh runs under set -e: a failed packwiz sync exits before NeoForge starts
                print(f"{ident}: went back to offline after {int(time.time() - t0)}s; start.sh stopped, read the panel console")
                return 1
            time.sleep(5)
        print(f"{ident}: still {s} after {timeout}s, wanted {want}")
        return 1
    if argv[:1] == ["waitlog"]:
        # Run only after `wait running`: by then log4j has rotated the previous boot out of latest.log.
        timeout, t0 = int(argv[1]), time.time()
        since = float(argv[2]) if len(argv) > 2 else t0
        while time.time() - t0 < timeout:
            text, name = boot_log(since)
            if FTBQ in text:
                print(f"FTB Quests loaded after {int(time.time() - t0)}s ({name})")
                return 0
            time.sleep(5)
        print(f"no FTB Quests load line in logs/latest.log or a log rotated since {int(since)} after {timeout}s")
        return 1
    if argv[:1] == ["evidence"] and len(argv) == 4:
        return evidence(Path(argv[1]), Path(argv[2]), float(argv[3]))
    print("usage: ptero_wait.py servers | wait <state> <seconds> [ident] | waitlog <seconds> [since epoch] | "
          "evidence <pack dir> <out.json> <since epoch>")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
