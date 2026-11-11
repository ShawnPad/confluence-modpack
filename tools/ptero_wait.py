"""0.3.0 deploy helper for plan Task 13. Lives in pack/.run/ (gitignored); never shipped.

API calls copied from ~/Documents/Projects/2-Homelab/pterodactyl: ptero.py Ptero.client() (client API, JSON),
cmd_read() (GET /api/client/servers/<id>/files/contents?file=...), the files/list call in _flatten_if_nested(),
and update_tmod.py wait_state() (GET /servers/<id>/resources -> attributes.current_state).
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

sys.path.insert(0, os.path.expanduser("~/Documents/Projects/2-Homelab/pterodactyl"))
import requests  # noqa: E402  (installed in the pterodactyl venv)
from ptero import Ptero  # noqa: E402

SERVER = "93ec4619"
pt = Ptero()


def state(ident=SERVER):
    return pt.client("GET", f"/servers/{ident}/resources")["attributes"]["current_state"]


def read(path):
    r = requests.get(f"{pt.base}/api/client/servers/{SERVER}/files/contents",
                     headers=pt._headers(pt.cfg["PTERO_CLIENT_KEY"]), params={"file": path}, timeout=60)
    r.raise_for_status()
    return r.content


def last(text, needle):
    hits = [line.strip() for line in text.splitlines() if needle in line]
    return hits[-1] if hits else ""


def boot_log(since=0.0):
    """latest.log, or the newest rotated log that holds the boot (latest.log rotates at midnight, HANDOFF §5 item 0).

    Rotated logs are read newest first by the listing's modified_at, not by name: the midnight rollover writes
    YYYY-MM-DD-1.log.gz, which is newer than that day's startup rollovers -2, -3, ... (files/list /logs, 2026-09-25).
    Files modified before `since` (epoch seconds) are skipped.
    """
    log = read("logs/latest.log").decode("utf-8", "replace")
    if "[FTB Quests/]: Loaded" in log:
        return log, "logs/latest.log"
    files = [f["attributes"] for f in
             pt.client("GET", f"/servers/{SERVER}/files/list", params={"directory": "/logs"})["data"]]
    rotated = [(datetime.fromisoformat(a["modified_at"]).timestamp(), a["name"]) for a in files
               if re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d+\.log\.gz", a["name"])]
    for mtime, name in sorted(rotated, reverse=True):
        if mtime < since:
            break
        text = gzip.decompress(read(f"logs/{name}")).decode("utf-8", "replace")
        if "[FTB Quests/]: Loaded" in text:
            return text, f"logs/{name}"
    return log, "logs/latest.log"


def evidence(pack, out):
    rel = pack / ".run" / "release-0.3.0"
    ev, bad = {}, []
    ev["packFileHash"] = json.loads(read("packwiz.json"))["packFileHash"]["value"]
    ev["pack_sha256"] = hashlib.sha256((pack / "pack.toml").read_bytes()).hexdigest()
    log, ev["log_file"] = boot_log()
    ev["done_line"] = last(log, "Done (")
    ev["ftbq_line"] = last(log, "[FTB Quests/]: Loaded")
    ev["worldgen_line"] = last(read("logs/kubejs/server.log").decode("utf-8", "replace"), "confluence worldgen:")
    ev["kubejs_errors"] = sum(1 for f in ("logs/kubejs/startup.log", "logs/kubejs/server.log")
                              for line in read(f).decode("utf-8", "replace").splitlines()
                              if re.match(r"^\[.*ERROR", line))
    tomb = read("config/tombstone-common.toml")
    ev["tombstone_line"] = next((f"{i}: {line.strip()}" for i, line in enumerate(tomb.decode().splitlines(), 1)
                                 if "lost_tablet_search_outside_world" in line), "")
    ev["tombstone_same_as_pack"] = tomb == (pack / "config" / "tombstone-common.toml").read_bytes()
    ev["lang_same_as_pack"] = (read("config/ftbquests/quests/lang/en_us.snbt")
                               == (pack / "config" / "ftbquests" / "quests" / "lang" / "en_us.snbt").read_bytes())
    local = last((rel / "boot.txt").read_text(), "[FTB Quests/]: Loaded")
    ev["ftbq_matches_local"] = bool(local) and ev["ftbq_line"].split("Loaded", 1)[-1] == local.split("Loaded", 1)[-1]
    checks = [
        (ev["packFileHash"] == ev["pack_sha256"], "packwiz.json packFileHash is not the sha256 of pack.toml"),
        (ev["done_line"] != "", "no 'Done (' line in " + ev["log_file"]),
        ("14 chapters" in ev["ftbq_line"] and ev["ftbq_matches_local"], "FTB Quests line differs from the local boot's"),
        (ev["worldgen_line"].endswith("confluence worldgen: 8 placements"), "worldgen line is not '8 placements'"),
        (ev["kubejs_errors"] == 0, "KubeJS ERROR lines on the server"),
        (ev["tombstone_line"].endswith("lost_tablet_search_outside_world = false"), "Tombstone key is not false"),
        (ev["lang_same_as_pack"], "the server's lang file differs from the pack's"),
    ]
    bad += [msg for ok, msg in checks if not ok]
    out.write_text(json.dumps(ev, indent=1) + "\n")
    for key, val in ev.items():
        print(f"{key}: {val}")
    print("SERVER OK" if not bad else "SERVER FAIL: " + "; ".join(bad))
    return 1 if bad else 0


def main(argv):
    if argv[:1] == ["servers"]:
        for s in pt.client("GET", "")["data"]:
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
            if "[FTB Quests/]: Loaded" in text:
                print(f"FTB Quests loaded after {int(time.time() - t0)}s ({name})")
                return 0
            time.sleep(5)
        print(f"no FTB Quests load line in logs/latest.log or a log rotated since {int(since)} after {timeout}s")
        return 1
    if argv[:1] == ["evidence"]:
        return evidence(Path(argv[1]), Path(argv[2]))
    print("usage: ptero_wait.py servers | wait <state> <seconds> [ident] | waitlog <seconds> [since epoch] | evidence <pack dir> <out.json>")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
