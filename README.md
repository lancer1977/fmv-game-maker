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
python3 -m http.server 8765
```

Open [http://localhost:8765/player/?adventure=../examples/placeholder/adventure.json](http://localhost:8765/player/?adventure=../examples/placeholder/adventure.json)

Serve from the repo root so the player can fetch `examples/` and clips.

Regenerate placeholder clips (optional):

```bash
./scripts/gen-placeholder-clips.sh
```

Suggest draft prompts from a clip (Ollama vision model; AGH-style frame→VLM):

```bash
./scripts/suggest-prompts.py examples/placeholder/clips/hallway.mp4 --mock -o /tmp/hallway-draft.json
# real VLM (needs e.g. `ollama pull qwen2.5vl:7b`):
./scripts/suggest-prompts.py examples/placeholder/clips/hallway.mp4 -o /tmp/hallway-draft.json
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
| `scripts/` | Clip generation + `suggest-prompts.py` (VLM draft prompts) |

## Content policy

Adventures reference local media you supply. Do not commit copyrighted
episode rips. Keep personal packs outside the repo (or gitignored).

## Status

V1: playable graph + overlay prompts + placeholder demo. Offline
`suggest-prompts.py` spike can draft MOVE prompts from sampled frames.
Authoring UI / timeline editor not started yet.
