"""Gemini-backed dialogue helper used by the PokeLike demo game."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterable, List

import requests


# When the game is launched via ``python game/main.py`` the repository root is
# not automatically importable.  Inject it explicitly so ``config`` can be
# imported without requiring the package to be installed.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import gemini_config as CFG


class DialogueEngine:
    """Return flavour text locally or via the Gemini API."""

    def __init__(self, use_gemini: bool = False, model_name: str = "gemini-2.5-pro"):
        self.use_gemini = use_gemini
        self.model_name = model_name

    def npc_line(self, npc_prompt: str) -> str:
        npc_prompt = (npc_prompt or "Say hi.").strip()
        if not self.use_gemini:
            return self._local(npc_prompt)

        key = CFG.get_api_key()
        if not key:
            return "[Gemini] Missing API key. Put it in config/api_key.txt or set GOOGLE_API_KEY. " + self._local(npc_prompt)

        try:
            url = f"{CFG.MODEL_ENDPOINT}?key={key}"
            body = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": f"You are an NPC in a cozy top-down RPG. {npc_prompt}"
                            }
                        ]
                    }
                ]
            }
            response = requests.post(url, json=body, timeout=10)
            response.raise_for_status()
            data = response.json()
            text = self._extract_text(data.get("candidates", []))
            return text or self._local(npc_prompt)
        except Exception as exc:  # noqa: BLE001 - surface the failure to the player
            return f"[Gemini error: {exc}] " + self._local(npc_prompt)

    @staticmethod
    def _extract_text(candidates: Iterable[dict]) -> str:
        for candidate in candidates:
            parts: List[dict] = candidate.get("content", {}).get("parts", [])
            texts = [part.get("text", "").strip() for part in parts if part.get("text")]
            if texts:
                return " ".join(texts)
        return ""

    def _local(self, prompt: str) -> str:
        local_lines = [
            "If you get lost, follow the river.",
            "Press 'E' to talk and 'G' for clever mode.",
            "The shopkeeper loves blue berries.",
            "Treasure lies past the old bridge.",
        ]
        return local_lines[sum(ord(c) for c in prompt) % len(local_lines)]
