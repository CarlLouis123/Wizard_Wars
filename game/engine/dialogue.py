"""Gemini-backed dialogue helper used by the PokeLike demo game."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import sys
from threading import Lock
from pathlib import Path
from typing import Dict, Iterable, List

import requests
from requests import exceptions as req_exc


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
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="gemini")
        self._lock = Lock()
        self._cache: Dict[str, str] = {}
        self._futures: Dict[str, Future[str]] = {}

    def prewarm(self, prompts: Iterable[str]) -> None:
        """Kick off background Gemini requests for the provided prompts."""

        if not self.use_gemini:
            return

        for prompt in prompts:
            clean_prompt = (prompt or "Say hi.").strip()
            with self._lock:
                if clean_prompt in self._cache or clean_prompt in self._futures:
                    continue
                future = self._executor.submit(self._fetch_gemini, clean_prompt)
                self._futures[clean_prompt] = future
                future.add_done_callback(lambda fut, key=clean_prompt: self._store_future(key, fut))

    def npc_line(self, npc_prompt: str) -> str:
        npc_prompt = (npc_prompt or "Say hi.").strip()
        if not self.use_gemini:
            return self._local(npc_prompt)

        with self._lock:
            cached = self._cache.get(npc_prompt)
            future = self._futures.get(npc_prompt)

        if cached is not None:
            return cached

        if future is None:
            future = self._submit_prompt(npc_prompt)

        if future.done():
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001 - captured and logged in _fetch_gemini
                result = f"[Gemini error: {exc}] " + self._local(npc_prompt)
            with self._lock:
                self._cache[npc_prompt] = result
                self._futures.pop(npc_prompt, None)
            return result

        return "[Gemini channeling...] " + self._local(npc_prompt)

    def _submit_prompt(self, prompt: str) -> Future[str]:
        with self._lock:
            future = self._futures.get(prompt)
            if future is None:
                future = self._executor.submit(self._fetch_gemini, prompt)
                self._futures[prompt] = future
                future.add_done_callback(lambda fut, key=prompt: self._store_future(key, fut))
            return future

    def _store_future(self, prompt: str, future: Future[str]) -> None:
        try:
            result = future.result()
        except Exception:
            return
        with self._lock:
            self._cache[prompt] = result
            self._futures.pop(prompt, None)

    def _fetch_gemini(self, npc_prompt: str) -> str:
        key = CFG.get_api_key()
        if not key:
            CFG.log_error("Missing API key for Gemini request.")
            return "[Gemini] Missing API key. Put it in config/api_key.txt or set GOOGLE_API_KEY. " + self._local(npc_prompt)

        response = None
        try:
            url = f"{CFG.MODEL_ENDPOINT}?key={key}"
            body = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": (
                                    "You are an ancient archwizard speaking inside the minimalist "
                                    "dueling sanctum of WizardWars. Offer a brief, original piece "
                                    "of clever magical counsel in at most two sentences. Let your "
                                    "tone carry the wonder of epic fantasy sagas like the Wheel of "
                                    "Time, The Lord of the Rings, and Harry Potter without quoting "
                                    "or plagiarising them. "
                                    f"{npc_prompt}"
                                )
                            }
                        ]
                    }
                ]
            }
            response = requests.post(url, json=body, timeout=(5, 30))
            response.raise_for_status()
            data = response.json()
            text = self._extract_text(data.get("candidates", []))
            return text or self._local(npc_prompt)
        except req_exc.Timeout as exc:
            CFG.log_error(
                f"Gemini request failed: {exc} (timeout) | prompt={npc_prompt!r}"
            )
            return "[Gemini timeout] " + self._local(npc_prompt)
        except Exception as exc:  # noqa: BLE001 - surface the failure to the player
            extra = ""
            if response is not None:
                extra = f" | status={response.status_code} body={response.text[:500]!r}"
            CFG.log_error(
                f"Gemini request failed: {exc} | prompt={npc_prompt!r}{extra}"
            )
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
            "We duel with insight long before the first spark of mana.",
            "Even a whisper of focus can bend the weave of battle.",
            "A staff is only a reminder; the storm lives in your calm.",
            "When the moonlight pivots, step sideways through possibility.",
        ]
        return local_lines[sum(ord(c) for c in prompt) % len(local_lines)]
