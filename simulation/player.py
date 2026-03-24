# =============================================================================
# player.py — Player class: physics, state, attacks, health.
#
# Arduino mapping:
#   - This class becomes a C struct + set of update functions.
#   - Floats become int16_t (fixed-point or scaled pixel coords).
#   - Timers become uint32_t counters using millis() deltas.
# =============================================================================

import pygame
from constants import *


# --- Action states ------------------------------------------------------------
# Use string constants so debug labels are human-readable.
# On Arduino these become an enum or #define integers.
class Action:
    IDLE         = "idle"
    WALKING      = "walking"
    JUMPING      = "jumping"
    CROUCHING    = "crouching"
    LIGHT_ATTACK = "light_attack"
    HEAVY_ATTACK = "heavy_attack"
    BLOCKING     = "blocking"
    KO           = "ko"


# =============================================================================
class Player:
    """
    Represents one fighter. Owns physics, health, cooldowns, and state.
    Input is passed in as an 'actions' dict (see input_handler.py), so
    the class itself has no knowledge of which keys are pressed.
    """

    def __init__(self, x, y, color, attack_color, facing_right=True):
        # ── Spatial state ──────────────────────────────────────────────────
        self.x = float(x)
        self.y = float(y)
        self.width  = PLAYER_WIDTH
        self.height = PLAYER_HEIGHT

        self.vel_x     = 0.0
        self.vel_y     = 0.0
        self.on_ground = True
        self.facing_right = facing_right

        # ── Visual / identity ──────────────────────────────────────────────
        self.color        = color
        self.attack_color = attack_color

        # ── Health & score ─────────────────────────────────────────────────
        self.health      = MAX_HEALTH
        self.round_wins  = 0
        self.is_ko       = False

        # ── Action / animation state ───────────────────────────────────────
        self.action = Action.IDLE

        # ── Attack timers ──────────────────────────────────────────────────
        self.light_cooldown  = 0.0   # seconds until light attack is available
        self.heavy_cooldown  = 0.0   # seconds until heavy attack is available

        self.attack_timer    = 0.0   # counts down active + windup window
        self.attack_windup   = 0.0   # windup remaining before hitbox goes live
        self.attack_active   = False # True when hitbox should deal damage
        self.current_attack  = None  # "light" or "heavy"
        self.hit_registered  = False # True once this attack swing already landed

        # ── Visual feedback ────────────────────────────────────────────────
        self.hit_flash_timer = 0.0   # counts down; player flashes white while > 0

    # =========================================================================
    # Public API
    # =========================================================================

    def update(self, dt, actions, opponent):
        """
        Main update. Call once per frame.
        dt      — delta time in seconds
        actions — dict of action_name -> bool (from input_handler)
        opponent — the other Player instance (for facing direction)
        """
        if self.is_ko:
            # Still apply gravity/physics so the KO body falls naturally
            self._apply_physics(dt)
            return

        self._update_cooldowns(dt)
        self._update_attack_window(dt)
        self._update_hit_flash(dt)
        self._handle_input(actions, dt)
        self._apply_physics(dt)
        self._clamp_to_screen()
        self._auto_face(opponent)

    def take_damage(self, raw_damage, knockback_dir):
        """
        Apply damage to this player.
        raw_damage   — damage before block reduction
        knockback_dir — +1 (rightward) or -1 (leftward)
        """
        damage = int(raw_damage * BLOCK_DAMAGE_MULT) if self.action == Action.BLOCKING else raw_damage

        self.health = max(0, self.health - damage)
        self.hit_flash_timer = HIT_FLASH_DURATION

        # Small knockback impulse
        self.vel_x = knockback_dir * KNOCKBACK_SPEED

        if self.health <= 0:
            self.is_ko    = True
            self.action   = Action.KO
            self.vel_x    = 0
            self.vel_y    = -200   # small hop on KO for feel

        return damage  # return actual damage dealt (useful for UI/sound hooks)

    def get_attack_hitbox(self):
        """
        Returns a pygame.Rect representing the active attack hitbox,
        or None if no hitbox is active right now.
        """
        if not self.attack_active:
            return None

        reach = LIGHT_RANGE if self.current_attack == "light" else HEAVY_RANGE
        rect_y = int(self.y + 10)
        rect_h = self.height - 20

        if self.facing_right:
            hx = int(self.x + self.width)
        else:
            hx = int(self.x - reach)

        return pygame.Rect(hx, rect_y, reach, rect_h)

    def get_rect(self):
        """Collision/render rect. Shrinks vertically when crouching."""
        if self.action == Action.CROUCHING:
            offset = self.height - PLAYER_CROUCH_HEIGHT
            return pygame.Rect(int(self.x), int(self.y) + offset,
                               self.width, PLAYER_CROUCH_HEIGHT)
        return pygame.Rect(int(self.x), int(self.y), self.width, self.height)

    def get_center_x(self):
        return self.x + self.width / 2

    def is_flashing(self):
        return self.hit_flash_timer > 0

    def reset_for_round(self):
        """Called between rounds to restore health and clear state."""
        self.health          = MAX_HEALTH
        self.is_ko           = False
        self.vel_x           = 0.0
        self.vel_y           = 0.0
        self.on_ground       = True
        self.action          = Action.IDLE
        self.light_cooldown  = 0.0
        self.heavy_cooldown  = 0.0
        self.attack_timer    = 0.0
        self.attack_windup   = 0.0
        self.attack_active   = False
        self.current_attack  = None
        self.hit_registered  = False
        self.hit_flash_timer = 0.0

    # =========================================================================
    # Private helpers
    # =========================================================================

    def _update_cooldowns(self, dt):
        if self.light_cooldown > 0:
            self.light_cooldown = max(0.0, self.light_cooldown - dt)
        if self.heavy_cooldown > 0:
            self.heavy_cooldown = max(0.0, self.heavy_cooldown - dt)

    def _update_attack_window(self, dt):
        """Advance the attack timing window (windup → active → finished)."""
        if self.action not in (Action.LIGHT_ATTACK, Action.HEAVY_ATTACK):
            return

        self.attack_timer -= dt

        # Tick down windup phase; activate hitbox once windup expires
        if self.attack_windup > 0:
            self.attack_windup -= dt
            if self.attack_windup <= 0:
                self.attack_windup   = 0.0
                self.attack_active   = True
                self.hit_registered  = False

        # Attack window expired → return to idle
        if self.attack_timer <= 0:
            self.attack_timer   = 0.0
            self.attack_active  = False
            self.current_attack = None
            self.action         = Action.IDLE

    def _update_hit_flash(self, dt):
        if self.hit_flash_timer > 0:
            self.hit_flash_timer = max(0.0, self.hit_flash_timer - dt)

    def _handle_input(self, actions, dt):
        """
        Map action booleans to state changes.
        This function is the only place that reads player input.
        To port to Arduino: swap 'actions' dict with GPIO reads.
        """
        in_attack = self.action in (Action.LIGHT_ATTACK, Action.HEAVY_ATTACK)

        # --- Movement and actions (locked out during attacks) ----------------
        if not in_attack:

            # Horizontal movement
            if actions.get("left"):
                self.vel_x = -MOVE_SPEED
            elif actions.get("right"):
                self.vel_x = MOVE_SPEED
            else:
                self.vel_x = 0

            # Jump (only from ground)
            if actions.get("jump") and self.on_ground:
                self.vel_y    = JUMP_VELOCITY
                self.on_ground = False
                self.action   = Action.JUMPING

            # Crouch (ground only; cancels on release)
            if actions.get("crouch") and self.on_ground:
                self.vel_x  = 0
                self.action = Action.CROUCHING
            elif not actions.get("crouch") and self.action == Action.CROUCHING:
                self.action = Action.IDLE

            # Block (ground only; cancels on release)
            if actions.get("block") and self.on_ground:
                self.vel_x  = 0
                self.action = Action.BLOCKING
            elif not actions.get("block") and self.action == Action.BLOCKING:
                self.action = Action.IDLE

            # Light attack
            if actions.get("light") and self.light_cooldown <= 0:
                self._start_attack("light")

            # Heavy attack
            elif actions.get("heavy") and self.heavy_cooldown <= 0:
                self._start_attack("heavy")

        # --- Derive idle / walking state automatically -----------------------
        if self.on_ground and self.action not in (
            Action.CROUCHING, Action.BLOCKING,
            Action.LIGHT_ATTACK, Action.HEAVY_ATTACK, Action.KO
        ):
            self.action = Action.WALKING if self.vel_x != 0 else Action.IDLE

        if not self.on_ground and self.action not in (
            Action.LIGHT_ATTACK, Action.HEAVY_ATTACK, Action.KO
        ):
            self.action = Action.JUMPING

    def _start_attack(self, attack_type):
        """Initiate an attack and set all relevant timers."""
        self.vel_x = 0  # stop moving when attacking

        if attack_type == "light":
            self.action         = Action.LIGHT_ATTACK
            self.attack_timer   = LIGHT_ACTIVE_FRAMES
            self.attack_windup  = 0.0              # immediate activation
            self.attack_active  = True
            self.light_cooldown = LIGHT_COOLDOWN
            self.current_attack = "light"
        else:  # heavy
            self.action         = Action.HEAVY_ATTACK
            self.attack_timer   = HEAVY_WINDUP + HEAVY_ACTIVE_FRAMES
            self.attack_windup  = HEAVY_WINDUP     # hitbox delayed
            self.attack_active  = False
            self.heavy_cooldown = HEAVY_COOLDOWN
            self.current_attack = "heavy"

        self.hit_registered = False

    def _apply_physics(self, dt):
        # Gravity
        if not self.on_ground:
            self.vel_y += GRAVITY * dt

        self.x += self.vel_x * dt
        self.y += self.vel_y * dt

        # Floor collision
        floor_surface = float(FLOOR_Y - self.height)
        if self.y >= floor_surface:
            self.y     = floor_surface
            self.vel_y = 0.0
            if not self.on_ground:
                self.on_ground = True
                if self.action == Action.JUMPING:
                    self.action = Action.IDLE

    def _clamp_to_screen(self):
        self.x = max(0.0, min(self.x, float(SCREEN_WIDTH - self.width)))

    def _auto_face(self, opponent):
        """Turn to always face the opponent."""
        self.facing_right = opponent.get_center_x() > self.get_center_x()
