#!/usr/bin/env python3
"""Tiny parser tests for suggest-prompts (no Ollama required)."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "suggest-prompts.py"


def load_mod():
    spec = importlib.util.spec_from_file_location("suggest_prompts", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class ParseMoveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_mod()

    def test_arrow_right(self):
        got = self.mod.parse_move_reply("MOVE: ArrowRight | dodge the pan")
        self.assertEqual(got["input"], "ArrowRight")
        self.assertIn("pan", got["reason"])

    def test_none(self):
        self.assertIsNone(self.mod.parse_move_reply("MOVE: NONE | calm beat"))

    def test_alias_down(self):
        got = self.mod.parse_move_reply("MOVE: down | duck")
        self.assertEqual(got["input"], "ArrowDown")

    def test_coalesce_gap(self):
        hits = [
            {"atMs": 1000, "input": "ArrowRight", "reason": "a"},
            {"atMs": 1200, "input": "ArrowLeft", "reason": "b"},
            {"atMs": 3000, "input": "ArrowDown", "reason": "c"},
        ]
        kept = self.mod.coalesce_suggestions(hits, window_ms=1200, min_gap_ms=1500)
        self.assertEqual([k["prompt"]["input"] for k in kept], ["ArrowRight", "ArrowDown"])
        self.assertEqual(kept[0]["prompt"]["atMs"], 1000)
        self.assertEqual(kept[0]["prompt"]["label"], "→")


if __name__ == "__main__":
    unittest.main()
