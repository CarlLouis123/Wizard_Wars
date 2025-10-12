# ---- Display & timing ----
WINDOW_W = 960
WINDOW_H = 540
FPS = 60

# ---- World & tiles ----
TILE_SIZE = 32
WORLD_W = 96
WORLD_H = 96
SEED = 1337  # change for different procedural layouts

# ---- Player ----
# Player movement is defined in templates; this fallback keeps legacy behaviour consistent.
PLAYER_BASE_SPEED_TILES = 3.5

# ---- Gemini (dialogue) ----
USE_GEMINI = False       # Press G in-game to toggle ON/OFF
MODEL_NAME = "gemini-2.5-pro"  # not strictly used by the raw endpoint, but kept for clarity
