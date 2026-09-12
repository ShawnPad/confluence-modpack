from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gen_install import parse_modlist, render_script

SAMPLE = """
| Mod | Tree nodes | 1.21.1 NeoForge version (date) | Slug (host) | Required libraries | Side | Notes |
|---|---|---|---|---|---|---|
| Mekanism | [T0.2] | 10.7.19.85 (2026-04-10) | `mekanism` | none | both | core |
| Twilight Forest | [D2.1] | 4.8.3345 | `the-twilight-forest` (CurseForge only) | none | both | tier 2 |
| Sodium | perf | 0.6 | `sodium` | none | client | client only |
| Library | Version (date) | Slug | Used by | Side |
|---|---|---|---|---|
| Rhino | 2101.2.7 | `rhino` | KubeJS | both |
| playerAnimator | 2.0.4+1.21.1-forge (2025-12-28; neoforge-tagged file, `-forge` is a naming artifact), beta only | `playeranimator` | Iron's Spells | both |
"""

def test_parse_rows():
    rows = parse_modlist(SAMPLE)
    assert [r.slug for r in rows] == ["mekanism", "the-twilight-forest", "sodium", "rhino", "playeranimator"]
    assert rows[1].host == "curseforge"
    assert rows[0].host == "modrinth"
    assert rows[2].side == "client"

def test_render_script():
    rows = parse_modlist(SAMPLE)
    script = render_script(rows)
    assert 'packwiz modrinth install "mekanism" -y' in script
    assert 'packwiz curseforge install "the-twilight-forest" -y' in script
    assert "sodium" in script and "client" in script

def test_slug_comes_from_slug_column_not_first_backtick():
    # Regression: the playerAnimator row has `-forge` backticked inside its version cell.
    # The slug must come from the table's Slug column, never from the first backticked cell.
    rows = parse_modlist(SAMPLE)
    by_name = {r.name: r for r in rows}
    assert by_name["playerAnimator"].slug == "playeranimator"
    assert by_name["playerAnimator"].host == "modrinth"
    script = render_script(rows)
    assert 'packwiz modrinth install "playeranimator" -y' in script
    assert 'install "-forge"' not in script
