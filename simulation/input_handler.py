# =============================================================================
# input_handler.py — Keyboard-to-action mapping.
#
# Returns an 'actions' dict: { "left": bool, "right": bool, ... }
# The Player class only sees this dict, never raw key codes.
#
# Arduino port: replace get_p1_actions / get_p2_actions with functions
# that read digitalRead() on GPIO pins wired to joystick switches/buttons.
# The actions dict structure stays identical.
#
# Controls
# --------
# Player 1:  A / D      move     W    jump    S    crouch
#            J          light    K    heavy   L    block
#
# Player 2:  ← / →      move     ↑    jump    ↓    crouch
#            ,           light    .    heavy   /    block
# =============================================================================

import pygame

# --- Key maps (change these to remap controls) --------------------------------

P1_KEY_MAP = {
    "left":   pygame.K_a,
    "right":  pygame.K_d,
    "jump":   pygame.K_w,
    "crouch": pygame.K_s,
    "light":  pygame.K_j,
    "heavy":  pygame.K_k,
    "block":  pygame.K_l,
}

P2_KEY_MAP = {
    "left":   pygame.K_LEFT,
    "right":  pygame.K_RIGHT,
    "jump":   pygame.K_UP,
    "crouch": pygame.K_DOWN,
    "light":  pygame.K_COMMA,    # ,
    "heavy":  pygame.K_PERIOD,   # .
    "block":  pygame.K_SLASH,    # /
}

# --- Public helpers -----------------------------------------------------------

def get_p1_actions(keys):
    """Return P1 actions from a pygame.key.get_pressed() snapshot."""
    return _build_actions(keys, P1_KEY_MAP)


def get_p2_actions(keys):
    """Return P2 actions from a pygame.key.get_pressed() snapshot."""
    return _build_actions(keys, P2_KEY_MAP)


def _build_actions(keys, key_map):
    """Generic helper: map a key_map to bool values from the pressed-keys array."""
    return {action: bool(keys[key]) for action, key in key_map.items()}
