#!/usr/bin/env python3
"""Suggest timed FMV directional prompts from a video clip via a local VLM.

Borrows the Ollama+image call style from agentic-game-harness
``perception/scene_control_api.py``, but runs offline against a file
(ffmpeg frame samples → draft prompt JSON). No AGH dependency.

Example:

  ./scripts/suggest-prompts.py examples/placeholder/clips/hallway.mp4

  ./scripts/suggest-prompts.py clip.mp4 --fps 1 --window-ms 1200 -o draft.json

Requires a vision-capable Ollama model (default ``qwen2.5vl:7b``). Set
``FMV_SUGGEST_MODEL`` or ``--model`` to override. Use ``--dry-run`` to only
extract frames, or ``--mock`` to emit a fixture suggestion without Ollama.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_MODEL = os.environ.get("FMV_SUGGEST_MODEL", "qwen2.5vl:7b")
DEFAULT_OLLAMA = os.environ.get("FMV_SUGGEST_OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
DEFAULT_FPS = 1.0
DEFAULT_WINDOW_MS = 1200
INPUTS = ("ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight")
LABELS = {
    "ArrowUp": "↑",
    "ArrowDown": "↓",
    "ArrowLeft": "←",
    "ArrowRight": "→",
}

PROMPT_TEMPLATE = """You are helping author a Dragon's Lair-style FMV game beat.
This is one frame from a video clip at about {t_ms} ms.

Decide whether the player must press a direction RIGHT NOW to survive or
progress. If nothing urgent is happening, say NONE.

Reply with exactly one of these lines (no other commentary):
MOVE: ArrowUp | short reason
MOVE: ArrowDown | short reason
MOVE: ArrowLeft | short reason
MOVE: ArrowRight | short reason
MOVE: NONE | short reason
"""


def build_prompt(t_ms: int) -> str:
    return PROMPT_TEMPLATE.format(t_ms=t_ms)


def parse_move_reply(reply: str) -> dict | None:
    """Parse a single MOVE line into {input, reason} or None for NONE/invalid."""
    for raw in (reply or "").splitlines():
        line = raw.strip()
        if not line.upper().startswith("MOVE:"):
            continue
        body = line[5:].strip()
        parts = [p.strip() for p in body.split("|", 1)]
        token = parts[0]
        reason = parts[1] if len(parts) > 1 else ""
        if token.upper() == "NONE":
            return None
        # Accept bare words too: up/down/left/right
        aliases = {
            "UP": "ArrowUp",
            "DOWN": "ArrowDown",
            "LEFT": "ArrowLeft",
            "RIGHT": "ArrowRight",
            "ARROWUP": "ArrowUp",
            "ARROWDOWN": "ArrowDown",
            "ARROWLEFT": "ArrowLeft",
            "ARROWRIGHT": "ArrowRight",
        }
        key = aliases.get(token.replace(" ", "").upper(), token)
        if key not in INPUTS:
            continue
        return {"input": key, "reason": reason}
    return None


def probe_duration_ms(video: Path) -> int | None:
    try:
        out = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.strip()
        return int(float(out) * 1000)
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        return None


def extract_frames(video: Path, out_dir: Path, fps: float) -> list[tuple[int, Path]]:
    """Return [(t_ms, path), ...] using ffmpeg fps filter + filename index."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "frame_%04d.png"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video),
            "-vf",
            f"fps={fps}",
            str(pattern),
        ],
        check=True,
        timeout=120,
    )
    frames = sorted(out_dir.glob("frame_*.png"))
    result: list[tuple[int, Path]] = []
    for i, path in enumerate(frames):
        t_ms = int(round((i / fps) * 1000))
        result.append((t_ms, path))
    return result


def ask_vlm(prompt: str, frame_path: Path, *, model: str, ollama_url: str, timeout: float) -> str:
    encoded = base64.b64encode(frame_path.read_bytes()).decode("ascii")
    payload = {
        "model": model,
        "prompt": prompt,
        "images": [encoded],
        "stream": False,
    }
    request = urllib.request.Request(
        ollama_url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read()).get("response", "").strip()
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")[:2000]
        raise RuntimeError(f"Ollama HTTP {error.code}: {body}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Cannot reach Ollama at {ollama_url}: {error}. Is `ollama serve` running?"
        ) from error


def coalesce_suggestions(
    hits: list[dict],
    *,
    window_ms: int,
    min_gap_ms: int,
) -> list[dict]:
    """Keep first hit in each cluster; skip repeats closer than min_gap_ms."""
    hits = sorted(hits, key=lambda h: h["atMs"])
    kept: list[dict] = []
    for hit in hits:
        if kept and hit["atMs"] - kept[-1]["atMs"] < min_gap_ms:
            continue
        prompt = {
            "atMs": hit["atMs"],
            "windowMs": window_ms,
            "input": hit["input"],
            "label": LABELS[hit["input"]],
        }
        kept.append(
            {
                "atMs": hit["atMs"],
                "prompt": prompt,
                "reason": hit.get("reason", ""),
                "frame": hit.get("frame"),
            }
        )
    return kept


def mock_hits(frames: list[tuple[int, Path]]) -> list[dict]:
    """Deterministic fixture when --mock is set (no Ollama)."""
    if not frames:
        return []
    picks = [
        {
            "atMs": frames[0][0],
            "input": "ArrowRight",
            "reason": "mock early dodge",
            "frame": str(frames[0][1]),
        }
    ]
    if len(frames) >= 2:
        later = frames[-1]
        picks.append(
            {
                "atMs": later[0],
                "input": "ArrowDown",
                "reason": "mock late duck",
                "frame": str(later[1]),
            }
        )
    return picks


def analyze_frames(
    frames: list[tuple[int, Path]],
    *,
    model: str,
    ollama_url: str,
    timeout: float,
    mock: bool,
) -> list[dict]:
    if mock:
        return mock_hits(frames)

    hits: list[dict] = []
    for t_ms, path in frames:
        reply = ask_vlm(build_prompt(t_ms), path, model=model, ollama_url=ollama_url, timeout=timeout)
        parsed = parse_move_reply(reply)
        print(f"  t={t_ms:>5}ms  {path.name}: {reply.splitlines()[0] if reply else '(empty)'}", file=sys.stderr)
        if not parsed:
            continue
        hits.append(
            {
                "atMs": t_ms,
                "input": parsed["input"],
                "reason": parsed["reason"],
                "frame": str(path),
                "raw": reply,
            }
        )
    return hits


def build_draft(
    video: Path,
    suggestions: list[dict],
    *,
    duration_ms: int | None,
    fps: float,
    model: str,
) -> dict:
    node_id = re.sub(r"[^a-z0-9]+", "-", video.stem.lower()).strip("-") or "clip"
    # V1 scene graph allows one prompt per node — emit the strongest/earliest
    # as `prompt`, and keep the full list under `suggestedPrompts` for editing.
    primary = suggestions[0]["prompt"] if suggestions else None
    node: dict = {
        "kind": "scene",
        "clip": video.name,
        "durationMs": duration_ms or 3000,
        "checkpoint": True,
        "onFail": "death_todo",
        "onTimeout": "death_todo",
    }
    if primary:
        node["prompt"] = primary
        node["onSuccess"] = f"{node_id}_next"
    if len(suggestions) > 1:
        node["suggestedPrompts"] = [s["prompt"] for s in suggestions]
        node["_notes"] = [
            f"{s['atMs']}ms {s['prompt']['input']}: {s.get('reason', '')}".strip()
            for s in suggestions
        ]

    return {
        "source": {
            "video": str(video.resolve()),
            "fps": fps,
            "model": model,
            "durationMs": duration_ms,
        },
        "suggestions": suggestions,
        "draftNode": {node_id: node},
        "hint": "Copy draftNode into an adventure.json nodes map; split multi-prompt clips into sequential nodes by hand for V1.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("video", type=Path, help="Path to an MP4 (or other ffmpeg-readable) clip")
    parser.add_argument("--fps", type=float, default=DEFAULT_FPS, help="Frame sample rate (default 1)")
    parser.add_argument("--window-ms", type=int, default=DEFAULT_WINDOW_MS, help="Prompt windowMs for drafts")
    parser.add_argument("--min-gap-ms", type=int, default=1500, help="Min spacing between kept suggestions")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama VL model (default {DEFAULT_MODEL})")
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA, help="Ollama /api/generate URL")
    parser.add_argument("--timeout", type=float, default=60.0, help="Per-frame VLM timeout seconds")
    parser.add_argument("-o", "--output", type=Path, help="Write draft JSON here (default stdout)")
    parser.add_argument("--keep-frames", type=Path, help="Directory to keep extracted PNGs")
    parser.add_argument("--dry-run", action="store_true", help="Extract frames only; print frame list JSON")
    parser.add_argument("--mock", action="store_true", help="Skip Ollama; emit fixture suggestions")
    args = parser.parse_args(argv)

    if not args.video.is_file():
        print(f"error: video not found: {args.video}", file=sys.stderr)
        return 1
    if shutil.which("ffmpeg") is None:
        print("error: ffmpeg not found on PATH", file=sys.stderr)
        return 1

    duration_ms = probe_duration_ms(args.video)
    tmp_ctx = None
    if args.keep_frames:
        frame_dir = args.keep_frames
        frame_dir.mkdir(parents=True, exist_ok=True)
    else:
        tmp_ctx = tempfile.TemporaryDirectory(prefix="fmv-suggest-")
        frame_dir = Path(tmp_ctx.name)

    try:
        print(f"Sampling {args.video} at {args.fps} fps…", file=sys.stderr)
        frames = extract_frames(args.video, frame_dir, args.fps)
        print(f"Got {len(frames)} frame(s); duration≈{duration_ms}ms", file=sys.stderr)

        if args.dry_run:
            payload = {
                "video": str(args.video.resolve()),
                "durationMs": duration_ms,
                "frames": [{"atMs": t, "path": str(p)} for t, p in frames],
            }
            text = json.dumps(payload, indent=2)
            if args.output:
                args.output.write_text(text + "\n")
            else:
                print(text)
            return 0

        print(
            f"Analyzing with {'mock' if args.mock else args.model}…",
            file=sys.stderr,
        )
        hits = analyze_frames(
            frames,
            model=args.model,
            ollama_url=args.ollama_url,
            timeout=args.timeout,
            mock=args.mock,
        )
        suggestions = coalesce_suggestions(hits, window_ms=args.window_ms, min_gap_ms=args.min_gap_ms)
        draft = build_draft(
            args.video,
            suggestions,
            duration_ms=duration_ms,
            fps=args.fps,
            model="mock" if args.mock else args.model,
        )
        text = json.dumps(draft, indent=2)
        if args.output:
            args.output.write_text(text + "\n")
            print(f"Wrote {args.output}", file=sys.stderr)
        else:
            print(text)
        return 0
    except subprocess.CalledProcessError as error:
        print(f"error: ffmpeg failed: {error}", file=sys.stderr)
        return 1
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        print(
            "hint: install a vision model, e.g. `ollama pull qwen2.5vl:7b`, or pass --mock / --dry-run",
            file=sys.stderr,
        )
        return 1
    finally:
        if tmp_ctx is not None:
            tmp_ctx.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
