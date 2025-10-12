# PokeLike - Template Driven (Gemini-ready)

Everything in this small top-down demo is drawn from templates (JSON/YAML).
Dialogue can optionally be routed through Google Gemini, but the game runs
perfectly offline with built-in responses.

## Prerequisites

- [Python 3.10+](https://www.python.org/downloads/) with the `py` launcher
  installed (this is the default when installing Python on Windows).
- [PowerShell](https://learn.microsoft.com/powershell/) – the instructions
  below assume you open a PowerShell window directly inside the repository
  folder (e.g. `Shift` + right-click → **Open PowerShell window here**).

## First-time setup on Windows

```powershell
# 1. Create and activate a virtual environment (recommended)
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Upgrade pip and install the requirements
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# 3. Optional: sanity check the sources compile
python -m compileall game
```

If you plan to use Gemini-powered dialogue, either set the `GOOGLE_API_KEY`
environment variable or place the API key in `config\api_key.txt` (create the
file if it does not already exist). The key is read each time you talk to an
NPC, so you can edit the file while the game is running.

## Running the game

```powershell
python game\main.py
```

Controls:

- **WASD** or **Arrow keys** – Move
- **E** – Talk to the nearest NPC (within range)
- **G** – Toggle Gemini dialogue on/off
- **Esc** – Quit

If you want to verify that everything is working without launching the window
(for example on a CI machine), you can run `python -m compileall game` to catch
syntax errors.
