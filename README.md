# tekken-arcade-mini

A two-player arcade fighting game — built first as a Python/Pygame desktop prototype, then ported to Arduino hardware with a TFT screen, joysticks, buttons, LEDs, and optional audio.

---

## Project structure

```
tekken-arcade-mini/
├── simulation/          # Python/Pygame desktop prototype
│   ├── main.py          # Game loop, state machine, hit detection
│   ├── player.py        # Player class: physics, attacks, health
│   ├── constants.py     # All tunable gameplay values
│   ├── input_handler.py # Keyboard → actions mapping
│   ├── renderer.py      # All drawing/UI code
│   └── requirements.txt
├── arduino/             # Arduino firmware (future)
├── assets/              # Sprites, sounds, fonts (future)
└── docs/                # Design notes and wiring diagrams (future)
```

---

## Simulation (Python/Pygame)

### Requirements

- Python 3.9+
- pygame 2.1+

```bash
cd simulation
pip install -r requirements.txt
python3 main.py
```

### Controls

| Action | Player 1 | Player 2 |
|---|---|---|
| Move | `A` / `D` | `←` / `→` |
| Jump | `W` | `↑` |
| Crouch | `S` | `↓` |
| Light attack | `J` | `,` |
| Heavy attack | `K` | `.` |
| Block | `L` | `/` |
| Pause / Quit | `ESC` | `ESC` |
| Start / Restart | `Enter` | |

### Game states

`MENU` → `COUNTDOWN` → `PLAYING` → `ROUND_END` → `GAME_OVER`

First player to win **2 rounds** wins the match.

### Gameplay defaults

| Parameter | Value |
|---|---|
| Max health | 100 |
| Move speed | 230 px/s |
| Jump velocity | −620 px/s |
| Gravity | 1500 px/s² |
| Light attack damage / cooldown | 8 / 0.40 s |
| Heavy attack damage / cooldown | 22 / 1.05 s |
| Block damage reduction | 80% |
| Knockback speed | 190 px/s |

All values live in `simulation/constants.py` and are easy to tweak.

### Architecture

The code is intentionally separated so the core logic can be ported to Arduino:

| File | Responsibility |
|---|---|
| `constants.py` | Tunable numbers and colors only — maps to `#define` / `const` on Arduino |
| `player.py` | Fighter state machine and physics — maps to a C `struct` + update functions |
| `input_handler.py` | Keyboard → action dict — maps to `digitalRead()` GPIO reads |
| `renderer.py` | All drawing — maps to TFT library calls (`fillRect`, `drawString`, etc.) |
| `main.py` | Game loop and state machine — maps to Arduino `loop()` |

---

## Arduino port (planned)

Target hardware:

- Arduino Mega or ESP32
- ILI9341 or ST7735 TFT display
- 2× analog joystick modules
- Push buttons for attacks and block
- Optional: piezo buzzer or DFPlayer Mini for audio
- Optional: RGB LEDs for hit feedback

Porting path:

1. Replace `input_handler.py` with `digitalRead()` / `analogRead()` calls
2. Replace `renderer.py` with TFT library draw calls at the same resolution
3. Convert `Player` class to a C struct with equivalent update functions
4. Replace float timers with `millis()` delta counters
5. Replace `pygame.Rect.colliderect` with a manual AABB check

---

## What to build next

1. **Sound** — drop `.wav` files into `assets/sounds/` and fill in the `snd_*` hooks in `main.py`
2. **Animations** — the `Action` state machine already drives when each frame plays; swap rectangles for sprite sheets
3. **Special moves** — add input buffering to `input_handler.py` (e.g. down → forward + attack)
4. **CPU opponent** — replace one player's input call with a simple behavior tree
5. **Arduino port** — stub out Pygame in the Python code to validate logic headlessly before flashing
