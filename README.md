# Astroids

A simple Python take on Asteroids built with `pygame`.

This version uses generated retro sound effects and particle bursts, so there are no external asset files to manage.

## Plan

1. Build a single-window arcade loop with smooth keyboard controls.
2. Add ship thrust, rotation, screen wrapping, bullets, and asteroid splitting.
3. Layer in score, lives, level progression, and restart handling.
4. Keep the code small enough to be a good base for later polish.

## Controls

- `Enter`: start from the title screen or restart after game over
- `Left` / `Right`: rotate
- `Up`: thrust
- `Space`: fire
- `R`: restart after game over
- `Esc`: quit

## Run

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```
