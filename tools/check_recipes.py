"""Assert the gate manifest (tools/gates.yaml) against the KubeJS recipe dump."""
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DUMP = ROOT / ".run" / "server" / "kubejs" / "exported" / "recipes.json"
MANIFEST = ROOT / "tools" / "gates.yaml"


@dataclass
class Result:
    missing: list = field(default_factory=list)
    still_present: list = field(default_factory=list)
    duplicates: list = field(default_factory=list)


def load_manifest(path: Path) -> tuple[list[str], list[str]]:
    gates, removed, section = [], [], None
    for line in path.read_text().splitlines():
        s = line.strip()
        if s.startswith("#") or not s:
            continue
        if s.startswith("gates:"):
            section = gates
            continue
        if s.startswith("removed:"):
            section = removed
            continue
        if s.startswith("- ") and section is not None:
            section.append(s[2:].strip().strip('"'))
    return gates, removed


def run_checks(dump: list[dict], gates: list[str], removed: list[str]) -> Result:
    ids = {r["id"] for r in dump}
    res = Result()
    res.missing = [g for g in gates if g not in ids]
    res.still_present = [r for r in removed if r in ids]
    counts = Counter((r["type"], r["output"]) for r in dump if r["output"] and not r["type"].startswith("minecraft:crafting"))
    res.duplicates = sorted(k for k, n in counts.items() if n > 1)
    return res


if __name__ == "__main__":
    dump = json.loads(DUMP.read_text())
    gates, removed = load_manifest(MANIFEST)
    r = run_checks(dump, gates, removed)
    print(f"gates: {len(gates)} expected, {len(r.missing)} missing, {len(r.still_present)} removed-still-present")
    for m in r.missing:
        print("  MISSING", m)
    for p in r.still_present:
        print("  STILL PRESENT", p)
    print(f"non-crafting duplicate outputs: {len(r.duplicates)} (informational; crafting-grid conflicts are Polymorph's job)")
    for d in r.duplicates[:50]:
        print("  dup", d)
    sys.exit(1 if (r.missing or r.still_present) else 0)
