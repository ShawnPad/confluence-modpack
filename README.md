# Confluence

A NeoForge 1.21.1 progression modpack: tech and magic in one tree, expert recipes, space as a late gate, ore tiers in gated dimensions. Distributed with packwiz, so every client and the server update themselves from this repository.

## Play (friends): install once, updates are automatic

1. Install [Prism Launcher](https://prismlauncher.org/) and a Java 21 runtime (Prism can download one under Settings → Java).
2. In Prism: **Add Instance → Import → paste this URL** (or download the file and pick it):

   `https://github.com/ShawnPad/confluence-modpack/releases/latest/download/confluence-prism.zip`

3. Launch the instance. The first launch downloads all mods (a few minutes); every later launch checks this repository and pulls whatever changed, so you never re-import.
4. Multiplayer → Add Server → `136.60.16.74:25584`.

**Help test:** the v0.1 checklist is in [PLAYTEST.md](PLAYTEST.md); report in [issue #1](https://github.com/ShawnPad/confluence-modpack/issues/1).

If a launch fails with an "error while installing" message, close Prism, delete the instance's `.minecraft/packwiz.json`, and launch again.

## Server (Pterodactyl)

Startup is `sh start.sh`, which runs the packwiz installer server-side before NeoForge:

```
java -jar packwiz-installer-bootstrap.jar -g -s server https://raw.githubusercontent.com/ShawnPad/confluence-modpack/main/pack.toml
```

so a server restart is all it takes to pick up a pushed change. Pin: NeoForge 21.1.250, Java 21, 10 GB heap.

## Repository layout

`pack.toml` / `index.toml` (packwiz manifest), `mods/*.pw.toml`, `kubejs/` (recipes, gates, worldgen, tag checks), `config/ftbquests/` (questbook), `config/*.toml`, `tools/` (headless test harness and checkers; not shipped to clients), `art/` (palette, style sheet, texture briefs and the maintainer's drafting grids; not shipped; see `art/CONTRIBUTING.md`).
