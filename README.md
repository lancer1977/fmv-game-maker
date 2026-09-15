# FMV Game Maker

Author and play **Dragon's Lair–style** full-motion video adventures: timed
directional prompts over video clips, with success/fail edges and death
restart nodes.

Bring your own footage. This repo ships the **scene-graph format**, a
browser **player**, and a **placeholder demo** with synthetic clips (no
third-party IP).

## Quick start

```bash
cd ~/code/fmv-game-maker
python3 -m http.server 8765 --directory player
```

Open [http://localhost:8765/?adventure=../examples/placeholder/adventure.json](http://localhost:8765/?adventure=../examples/placeholder/adventure.json)

Or open `player/index.html` via any static file server that can also serve
`examples/` (the player fetches the adventure JSON + clips relative to the
page).

Regenerate placeholder clips (optional):

```bash
./scripts/gen-placeholder-clips.sh
```

Controls: **↑ ↓ ← →** (or **W A S D**). Press the shown direction inside the
prompt window. Wrong key or timeout → death node → checkpoint restart.

## Layout

| Path | Role |
|------|------|
| `docs/scene-graph.md` | V1 scene-graph contract |
| `schema/adventure.schema.json` | JSON Schema for adventures |
| `player/` | Browser runtime (HTML/CSS/JS) |
| `examples/placeholder/` | Demo adventure + synthetic MP4s |
| `scripts/` | Clip generation helpers |

## Content policy

Adventures reference local media you supply. Do not commit copyrighted
episode rips. Keep personal packs outside the repo (or gitignored).

## Status

V1: playable graph + overlay prompts + placeholder demo. Authoring UI and
timeline editor are not started yet.
