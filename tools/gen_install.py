"""Generate tools/install_mods.sh from design/modlist.md.

Host rule: a slug cell containing "CurseForge" is installed from CurseForge
(with --category mc-mods so modpacks with a similar slug are not matched),
everything else from Modrinth. Side comes from the Side column.
packwiz sets side automatically for Modrinth installs; for CurseForge
installs and to enforce the mod list's value, install_mods.sh rewrites
`side = "..."` in the .pw.toml afterwards (no CLI flag exists, see
research/phase6-tooling-worldgen-quests.md §1e).

Matching a slug to an installed mod: packwiz names the file after the
project slug (mods/<slug>.pw.toml) but the file text carries project/version
ids, not necessarily the slug. So a slug counts as installed when it equals a
.pw.toml file stem, or appears as a whole token (a maximal run of slug
characters) in a file's text, ignoring the human-readable `name = "..."`
line (so "Mekanism Generators" does not make "mekanism" look installed).
Never a loose substring: "mekanism" does not match "mekanism-generators".
"""
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Row:
    name: str
    slug: str
    host: str   # "modrinth" | "curseforge"
    side: str   # "both" | "client" | "server"


SLUG_RE = re.compile(r"`([a-z0-9._-]+)`")
TOKEN_RE = re.compile(r"[a-z0-9._-]+")
NAME_LINE_RE = re.compile(r"^\s*name\s*=")
META_EXT = ".pw.toml"


def parse_modlist(text: str) -> list[Row]:
    rows: list[Row] = []
    slug_col: int | None = None  # index of the "Slug" column in the current table
    for line in text.splitlines():
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("| Mod |") or line.startswith("| Library |"):
            # header row: remember which column is the slug column for the rows below
            slug_col = next((i for i, c in enumerate(cells) if c.lower().startswith("slug")), None)
            continue
        if len(cells) < 5:
            continue
        # find the slug cell: the table's Slug column if the header named one and it holds
        # a backticked slug, else the first cell containing a backticked slug. (A version
        # cell may contain a backticked fragment such as `-forge`; the header rule skips it.)
        if slug_col is not None and slug_col < len(cells) and SLUG_RE.search(cells[slug_col]):
            slug_idx = slug_col
        else:
            slug_idx = next((i for i, c in enumerate(cells) if SLUG_RE.search(c)), None)
        if slug_idx is None:
            continue
        slug_cell = cells[slug_idx]
        slug = SLUG_RE.search(slug_cell).group(1)
        host = "curseforge" if "curseforge" in slug_cell.lower() else "modrinth"
        side_cell = next((c for c in cells if c in ("both", "client", "server")), "both")
        rows.append(Row(name=cells[0], slug=slug, host=host, side=side_cell))
    return rows


def render_script(rows: list[Row]) -> str:
    out = ["#!/usr/bin/env bash", "set -euo pipefail", "cd \"$(dirname \"$0\")/..\"", ""]
    for r in rows:
        # a failed install is logged, not fatal, so one bad slug does not abort the rest.
        # CurseForge: pin the category to mc-mods (the path segment of every CurseForge URL in
        # research/phase4-compat-matrix-*.md); without it the slug lookup also matches modpacks
        # and, under -y, picked "Iron's Spells 'n Spellbooks +" (a modpack) for irons-spells-n-spellbooks.
        extra = " --category mc-mods" if r.host == "curseforge" else ""
        out.append(f'packwiz {r.host} install "{r.slug}" -y{extra} || echo "INSTALL FAILED: {r.slug} ({r.host})"')
    out.append("")
    out.append("# enforce sides from the mod list")
    out.append("# find_mod SLUG PATTERN: prints the .pw.toml for SLUG - exact file stem first, else a whole-token")
    out.append("# match in the file text ignoring the display-name line (never a substring: mekanism must not")
    out.append("# match mekanism-generators, and 'Mekanism Generators' must not count as mekanism)")
    out.append("find_mod() {")
    out.append(f'  if [ -f "mods/$1{META_EXT}" ]; then echo "mods/$1{META_EXT}"; return; fi')
    out.append(f'  for m in mods/*{META_EXT}; do')
    out.append('    if grep -v -E "^[[:space:]]*name[[:space:]]*=" "$m" 2>/dev/null | grep -q -i -E "(^|[^A-Za-z0-9._-])$2([^A-Za-z0-9._-]|$)"; then echo "$m"; return; fi')
    out.append("  done")
    out.append("  true")
    out.append("}")
    for r in rows:
        if r.side != "both":
            pattern = r.slug.replace(".", "\\.")
            out.append(
                f'f=$(find_mod "{r.slug}" "{pattern}"); '
                f'[ -n "$f" ] && (grep -q "^side" "$f" && sed -i "" "s/^side = .*/side = \\"{r.side}\\"/" "$f" '
                f'|| printf \'side = "{r.side}"\\n\' >> "$f") '
                f'|| echo "SIDE NOT SET: {r.slug} (no .pw.toml found)"'
            )
    out.append("packwiz refresh")
    return "\n".join(out) + "\n"


def _installed(mods_dir: Path) -> tuple[set[str], set[str]]:
    """Return (file stems, whole tokens in file text), both lower-cased."""
    stems: set[str] = set()
    tokens: set[str] = set()
    for p in mods_dir.glob(f"*{META_EXT}"):
        stems.add(p.name[: -len(META_EXT)].lower())
        for line in p.read_text().splitlines():
            if NAME_LINE_RE.match(line):
                continue  # display name, not an identifier
            tokens.update(TOKEN_RE.findall(line.lower()))
    return stems, tokens


def check(rows: list[Row], mods_dir: Path) -> int:
    stems, tokens = _installed(mods_dir)
    missing = [r.slug for r in rows if r.slug.lower() not in stems and r.slug.lower() not in tokens]
    text_only = [r.slug for r in rows if r.slug.lower() not in stems and r.slug.lower() in tokens]
    print(f"{len(rows)} rows, {len(missing)} missing")
    for m in missing:
        print("  missing:", m)
    for t in text_only:
        print(f"  matched by text token only (no mods/{t}{META_EXT}):", t)
    return 1 if missing else 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--check":
        rows = parse_modlist(Path(args[1]).read_text())
        sys.exit(check(rows, Path(__file__).resolve().parents[1] / "mods"))
    rows = parse_modlist(Path(args[0]).read_text())
    script = Path(__file__).resolve().parent / "install_mods.sh"
    script.write_text(render_script(rows))
    script.chmod(0o755)
    print(f"wrote {script} with {len(rows)} installs")
