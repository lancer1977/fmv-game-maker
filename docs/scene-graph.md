# Scene graph V1

An **adventure** is a directed graph of **nodes**. Each node plays a clip
(or a visual fallback), optionally shows a timed input prompt, then follows
an edge based on success, failure, timeout, or natural completion.

## Adventure document

```json
{
  "id": "placeholder-demo",
  "title": "Escape the Kitchen",
  "version": 1,
  "start": "intro",
  "assetsBase": "./clips",
  "nodes": { }
}
```

| Field | Required | Meaning |
|-------|----------|---------|
| `id` | yes | Stable adventure id |
| `title` | yes | Display title |
| `version` | yes | Format version; V1 players require `1` |
| `start` | yes | Node id to begin (and default checkpoint) |
| `assetsBase` | no | Base path for relative `clip` paths |
| `nodes` | yes | Map of node id → node |

## Node

Every node:

| Field | Required | Meaning |
|-------|----------|---------|
| `kind` | no | `"scene"` (default) or `"death"` |
| `clip` | no | Video path relative to `assetsBase` or absolute URL |
| `fallback` | no | Shown when clip missing: `{ "bg", "title", "subtitle" }` |
| `durationMs` | yes* | Playback length used for timing when no video metadata; *required if no clip |
| `checkpoint` | no | If true, surviving here updates the restart point |
| `prompt` | no | Timed input window (scene nodes) |
| `onSuccess` | no | Next node when prompt answered correctly |
| `onFail` | no | Next node on wrong input |
| `onTimeout` | no | Next node when window expires unanswered (defaults to `onFail`) |
| `onComplete` | no | Next node when clip ends with no prompt, or after a death beat |

### Prompt

```json
{
  "atMs": 2500,
  "windowMs": 1200,
  "input": "ArrowRight",
  "label": "→"
}
```

| Field | Meaning |
|-------|---------|
| `atMs` | Prompt appears this many ms after node start |
| `windowMs` | How long the player has to press the correct input |
| `input` | `ArrowUp` / `ArrowDown` / `ArrowLeft` / `ArrowRight` (WASD aliases accepted by the player) |
| `label` | Overlay glyph (usually an arrow) |

Inputs before `atMs` are ignored. After a correct press, the player may
cut early to `onSuccess` or finish the remaining clip first — V1 **cuts
immediately** on success/fail for snappy feel.

### Death nodes

`kind: "death"` plays a fail beat, then follows `onComplete` (usually back
to the last checkpoint or `start`). Death nodes do not take prompts.

## Edges (mental model)

```
scene --prompt ok--> next scene
scene --wrong/timeout--> death --> checkpoint/start
scene --no prompt, clip ends--> onComplete
```

## Authoring tips

1. Mark safe landings with `"checkpoint": true`.
2. Keep prompt windows ~0.8–1.5s; shorter feels unfair, longer feels slack.
3. Put `atMs` slightly before the on-screen “decision” in the footage.
4. One prompt per node in V1 (multi-prompt scenes come later as sequences).
