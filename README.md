# Wizard Wars – Template Driven Dueling Sandbox

Wizard Wars is a procedural, top-down wizard dueling experiment. Every tile, 
character, line of dialogue, and spell is rendered from JSON/YAML templates, 
making the world endlessly remixable. The default content matches the "Wizard 
Wars V2" design document: five expanding biomes culminating in the Astral 
Citadel, spell-focused player progression, and Gemini-assisted dialogue.

## Features

- **Biome-driven overworld** – Arcane Plains, Molten Dunes, Frostlands, Verdant
  Marsh, and the Astral Citadel are authored in `content/templates/world`.
  Terrain tiles, decorative props, spawn radii, music cues, and ambient filters
  all come from data files.
- **Template-defined characters** – The player is described by
  `player_wizard.json`, while NPC archetypes, spawn rings, and fallback dialogue
  live in `npc_wizard.yaml`.
- **Spellbook as data** – Spells such as `spark`, `blink`, `barrier`, and
  `fireball` are loaded from YAML. The player UI surfaces health, mana, and the
  configured spell list directly from those definitions.
- **Gemini-ready conversations** – Toggle the Gemini dialogue channel with `G`.
  Without an API key the game falls back to deterministic template lines for
  each archetype.

## Prerequisites

- [Python 3.10+](https://www.python.org/downloads/)
- Optional but recommended: a virtual environment

Install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Running the game

```bash
python game/main.py
```

Controls:

- **WASD** / **Arrow keys** – Move
- **E** – Commune with the closest wizard
- **G** – Toggle Gemini dialogue on/off
- **Esc** – Quit the session

To validate the sources without launching the window (useful for CI), run:

```bash
python -m compileall game
```

## Gemini configuration

Set the `GOOGLE_API_KEY` environment variable or store the key in
`config/api_key.txt`. The key is read at runtime whenever Gemini dialogue is
requested, so you can add or rotate credentials without restarting the game.
