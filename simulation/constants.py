# =============================================================================
# constants.py — All tunable gameplay values live here.
# Tweak these freely without touching game logic.
# On Arduino: these become #define or const int values at the top of your sketch.
# =============================================================================

# --- Screen -------------------------------------------------------------------
SCREEN_WIDTH  = 960
SCREEN_HEIGHT = 540
FPS           = 60
TITLE         = "TEKKEN MINI"

# --- Floor --------------------------------------------------------------------
FLOOR_Y = 430           # Y coordinate of the floor surface (pixels from top)

# --- Player dimensions --------------------------------------------------------
PLAYER_WIDTH         = 50
PLAYER_HEIGHT        = 80
PLAYER_CROUCH_HEIGHT = 48   # height when crouching

# --- Movement -----------------------------------------------------------------
MOVE_SPEED        = 230     # horizontal speed (pixels/second)
JUMP_VELOCITY     = -620    # initial upward velocity on jump (negative = up)
GRAVITY           = 1500    # downward acceleration (pixels/second²)
KNOCKBACK_SPEED   = 190     # horizontal speed applied to defender on hit

# --- Health -------------------------------------------------------------------
MAX_HEALTH = 100

# --- Light attack -------------------------------------------------------------
LIGHT_DAMAGE          = 8     # damage dealt
LIGHT_RANGE           = 75    # hitbox horizontal reach (pixels beyond player edge)
LIGHT_COOLDOWN        = 0.40  # seconds before can attack again
LIGHT_ACTIVE_FRAMES   = 0.12  # seconds the hitbox is active

# --- Heavy attack -------------------------------------------------------------
HEAVY_DAMAGE          = 22    # damage dealt
HEAVY_RANGE           = 95    # hitbox horizontal reach
HEAVY_COOLDOWN        = 1.05  # seconds before can attack again
HEAVY_WINDUP          = 0.16  # seconds of windup before hitbox activates
HEAVY_ACTIVE_FRAMES   = 0.20  # seconds the hitbox is active

# --- Block --------------------------------------------------------------------
BLOCK_DAMAGE_MULT = 0.20    # multiplier applied to incoming damage while blocking
                             # 0.20 = 80% reduction

# --- Round rules --------------------------------------------------------------
ROUNDS_TO_WIN      = 2      # round wins needed to win the match
COUNTDOWN_DURATION = 1.0    # seconds per countdown step
ROUND_END_DELAY    = 2.8    # seconds to show KO screen before advancing

# --- Visual feedback ----------------------------------------------------------
HIT_FLASH_DURATION = 0.14   # seconds player flashes white after taking damage

# --- Player start positions ---------------------------------------------------
P1_START_X = SCREEN_WIDTH  // 4        # horizontal centre for P1
P2_START_X = (SCREEN_WIDTH * 3) // 4  # horizontal centre for P2
START_Y    = FLOOR_Y - PLAYER_HEIGHT   # vertical start (standing on floor)

# =============================================================================
# Colors
# =============================================================================
BLACK       = (  0,   0,   0)
WHITE       = (255, 255, 255)
DARK_GRAY   = ( 30,  30,  30)
GRAY        = ( 80,  80,  80)
LIGHT_GRAY  = (170, 170, 170)

RED         = (220,  50,  50)
DARK_RED    = (100,  15,  15)
GREEN       = ( 50, 195,  75)
BLUE        = ( 50, 110, 220)
DARK_BLUE   = ( 15,  35, 110)
YELLOW      = (255, 215,   0)
ORANGE      = (255, 145,   0)
CYAN        = (  0, 200, 215)

# Player colors
P1_COLOR        = ( 65, 130, 220)   # blue fighter
P1_ATTACK_COLOR = (140, 195, 255)   # lighter blue during attack
P2_COLOR        = (215,  65,  65)   # red fighter
P2_ATTACK_COLOR = (255, 155, 140)   # lighter red during attack

# Environment
BG_COLOR         = ( 12,  12,  22)
FLOOR_COLOR      = ( 50,  50,  68)
FLOOR_LINE_COLOR = ( 95,  95, 118)

# HUD
HP_BAR_BG   = ( 55,  18,  18)
HP_BAR_FG   = ( 55, 185,  75)   # healthy
HP_BAR_LOW  = (215,  55,  55)   # below 30%
HP_BORDER   = (200, 200, 200)

# Fonts (passed as strings to renderer)
FONT_LARGE  = 68
FONT_MEDIUM = 38
FONT_SMALL  = 24
