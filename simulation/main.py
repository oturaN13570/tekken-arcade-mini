# =============================================================================
# main.py — Entry point. Game loop + state machine + hit detection.
#
# Run:
#   cd simulation
#   python main.py
#
# Game states
# -----------
#   MENU        Press Enter to begin.
#   COUNTDOWN   "Round X" → "3" → "2" → "1" → "FIGHT!"
#   PLAYING     Active combat.
#   ROUND_END   KO displayed for ROUND_END_DELAY seconds, then advance.
#   GAME_OVER   Match winner shown; Enter to restart, ESC to quit.
# =============================================================================

import pygame
import sys

from constants import *
from player import Player, Action
from input_handler import get_p1_actions, get_p2_actions
import renderer

# --- State labels (used as plain strings, easy to match in any language) ------
STATE_MENU       = "MENU"
STATE_COUNTDOWN  = "COUNTDOWN"
STATE_PLAYING    = "PLAYING"
STATE_ROUND_END  = "ROUND_END"
STATE_GAME_OVER  = "GAME_OVER"


# =============================================================================
# Countdown sequence manager
# =============================================================================

class CountdownManager:
    """
    Steps through: "ROUND X" → "3" → "2" → "1" → "FIGHT!"
    Check .done each frame; read .current_text for display.
    """

    # (label_template, display_seconds)
    STEPS = [
        ("{round}",  1.0),
        ("3",        0.75),
        ("2",        0.75),
        ("1",        0.75),
        ("FIGHT!",   0.55),
    ]

    def __init__(self, round_num):
        self.round_num    = round_num
        self.step         = 0
        self.timer        = self.STEPS[0][1]
        self.done         = False
        self.current_text = self._label(0)

    def update(self, dt):
        self.timer -= dt
        if self.timer <= 0:
            self.step += 1
            if self.step >= len(self.STEPS):
                self.done = True
            else:
                self.timer        = self.STEPS[self.step][1]
                self.current_text = self._label(self.step)

    def _label(self, step):
        text, _ = self.STEPS[step]
        return text.replace("{round}", f"ROUND  {self.round_num}")


# =============================================================================
# Hit detection (pure logic, no rendering)
# =============================================================================

def check_hit(attacker, defender):
    """
    Test whether attacker's hitbox overlaps defender this frame.
    Applies damage if so, deactivates the hitbox to prevent multi-hit.
    Returns True on a successful hit.
    """
    if not attacker.attack_active:
        return False

    if attacker.hit_registered:   # already landed this swing
        return False

    atk_rect = attacker.get_attack_hitbox()
    if atk_rect is None:
        return False

    if not atk_rect.colliderect(defender.get_rect()):
        return False

    # --- Resolve damage -------------------------------------------------------
    raw   = LIGHT_DAMAGE if attacker.current_attack == "light" else HEAVY_DAMAGE
    k_dir = 1 if attacker.facing_right else -1
    defender.take_damage(raw, k_dir)

    # Mark swing as landed so it won't register again this frame
    attacker.hit_registered = True

    return True


# =============================================================================
# Main game class
# =============================================================================

class Game:

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        renderer.init_fonts()

        # Sound hooks — replace None with pygame.mixer.Sound("file.wav")
        # Arduino equivalent: call tone() / a buzzer helper at the same spots.
        self._init_sounds()

        self.paused = False
        self.state  = STATE_MENU

        # These are set in _full_reset / _reset_round
        self.p1            = None
        self.p2            = None
        self.round_num     = 1
        self.countdown     = None
        self.round_end_timer = 0.0
        self.round_end_text  = ""

        self._create_players()

    # =========================================================================
    # Sound stubs
    # =========================================================================

    def _init_sounds(self):
        """
        Populate with real pygame.mixer.Sound objects to add audio.
        Keeping them None means everything still works silently.
        """
        self.snd_light_hit = None   # short punch/hit
        self.snd_heavy_hit = None   # heavier impact
        self.snd_block     = None   # clank/guard sound
        self.snd_ko        = None   # crowd reaction / bell
        self.snd_fight     = None   # announcer "FIGHT!"

    def _play(self, snd):
        if snd:
            snd.play()

    # =========================================================================
    # Player / round management
    # =========================================================================

    def _create_players(self):
        self.p1 = Player(
            x=P1_START_X - PLAYER_WIDTH // 2,
            y=START_Y,
            color=P1_COLOR,
            attack_color=P1_ATTACK_COLOR,
            facing_right=True,
        )
        self.p2 = Player(
            x=P2_START_X - PLAYER_WIDTH // 2,
            y=START_Y,
            color=P2_COLOR,
            attack_color=P2_ATTACK_COLOR,
            facing_right=False,
        )

    def _reset_round(self):
        """Restore player positions and health without touching round wins."""
        self.p1.x = float(P1_START_X - PLAYER_WIDTH // 2)
        self.p1.y = float(START_Y)
        self.p2.x = float(P2_START_X - PLAYER_WIDTH // 2)
        self.p2.y = float(START_Y)
        self.p1.reset_for_round()
        self.p2.reset_for_round()

    def _full_reset(self):
        """Reset everything for a brand-new match."""
        self._create_players()
        self.round_num = 1
        self._reset_round()
        self._enter_countdown()

    def _enter_countdown(self):
        self.state     = STATE_COUNTDOWN
        self.countdown = CountdownManager(self.round_num)

    # =========================================================================
    # Main loop
    # =========================================================================

    def run(self):
        while True:
            # Delta time in seconds; capped to avoid physics spiral on lag spikes
            dt = min(self.clock.tick(FPS) / 1000.0, 0.05)

            self._handle_events()
            self._update(dt)
            self._render()

    # =========================================================================
    # Event handling
    # =========================================================================

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._quit()

            if event.type == pygame.KEYDOWN:
                self._on_keydown(event.key)

    def _on_keydown(self, key):
        if key == pygame.K_ESCAPE:
            if self.state == STATE_PLAYING:
                self.paused = not self.paused
            else:
                self._quit()

        if key == pygame.K_RETURN:
            if self.state == STATE_MENU:
                self._reset_round()
                self._enter_countdown()
            elif self.state == STATE_GAME_OVER:
                self._full_reset()

    def _quit(self):
        pygame.quit()
        sys.exit()

    # =========================================================================
    # Update
    # =========================================================================

    def _update(self, dt):
        if self.paused:
            return

        if self.state == STATE_MENU:
            pass  # waiting for ENTER

        elif self.state == STATE_COUNTDOWN:
            self._update_countdown(dt)

        elif self.state == STATE_PLAYING:
            self._update_playing(dt)

        elif self.state == STATE_ROUND_END:
            self._update_round_end(dt)

        elif self.state == STATE_GAME_OVER:
            pass  # waiting for ENTER

    # --- Per-state update helpers --------------------------------------------

    def _update_countdown(self, dt):
        self.countdown.update(dt)
        if self.countdown.done:
            self.state = STATE_PLAYING
            self._play(self.snd_fight)

    def _update_playing(self, dt):
        keys = pygame.key.get_pressed()

        # Update both fighters
        self.p1.update(dt, get_p1_actions(keys), self.p2)
        self.p2.update(dt, get_p2_actions(keys), self.p1)

        # Hit detection — check both attack directions each frame
        self._resolve_hit(self.p1, self.p2)
        self._resolve_hit(self.p2, self.p1)

        # Check for KO
        if self.p1.is_ko or self.p2.is_ko:
            self._handle_ko()

    def _update_round_end(self, dt):
        self.round_end_timer -= dt
        if self.round_end_timer <= 0:
            self._advance_round()

    # =========================================================================
    # Combat helpers
    # =========================================================================

    def _resolve_hit(self, attacker, defender):
        """Run hit detection and trigger sound on successful hit."""
        hit = check_hit(attacker, defender)
        if not hit:
            return

        if defender.action == Action.BLOCKING:
            self._play(self.snd_block)
        else:
            snd = self.snd_heavy_hit if attacker.current_attack == "heavy" else self.snd_light_hit
            self._play(snd)

    def _handle_ko(self):
        """Award a round win and transition to ROUND_END."""
        both_ko = self.p1.is_ko and self.p2.is_ko

        if both_ko:
            self.round_end_text = "DRAW"
        elif self.p2.is_ko:
            self.p1.round_wins += 1
            self.round_end_text = "PLAYER 1 WINS!"
        else:
            self.p2.round_wins += 1
            self.round_end_text = "PLAYER 2 WINS!"

        self._play(self.snd_ko)
        self.state           = STATE_ROUND_END
        self.round_end_timer = ROUND_END_DELAY

    def _advance_round(self):
        """After the round-end pause, either start next round or end the match."""
        if (self.p1.round_wins >= ROUNDS_TO_WIN
                or self.p2.round_wins >= ROUNDS_TO_WIN):
            self.state = STATE_GAME_OVER
        else:
            self.round_num += 1
            self._reset_round()
            self._enter_countdown()

    # =========================================================================
    # Render
    # =========================================================================

    def _render(self):
        if self.state == STATE_MENU:
            renderer.draw_menu(self.screen)

        elif self.state == STATE_COUNTDOWN:
            renderer.draw_background(self.screen)
            renderer.draw_player(self.screen, self.p1)
            renderer.draw_player(self.screen, self.p2)
            renderer.draw_hud(self.screen, self.p1, self.p2,
                               self.round_num, self.p1.round_wins, self.p2.round_wins)
            renderer.draw_countdown(self.screen, self.countdown.current_text)

        elif self.state == STATE_PLAYING:
            renderer.draw_background(self.screen)
            renderer.draw_player(self.screen, self.p1)
            renderer.draw_player(self.screen, self.p2)
            renderer.draw_hud(self.screen, self.p1, self.p2,
                               self.round_num, self.p1.round_wins, self.p2.round_wins)
            renderer.draw_cooldown_bars(self.screen, self.p1, self.p2)
            renderer.draw_action_label(self.screen, self.p1, self.p2)

            if self.paused:
                renderer.draw_paused(self.screen)

        elif self.state == STATE_ROUND_END:
            renderer.draw_background(self.screen)
            renderer.draw_player(self.screen, self.p1)
            renderer.draw_player(self.screen, self.p2)
            renderer.draw_hud(self.screen, self.p1, self.p2,
                               self.round_num, self.p1.round_wins, self.p2.round_wins)
            renderer.draw_round_end(self.screen, self.round_end_text)

        elif self.state == STATE_GAME_OVER:
            if self.p1.round_wins >= ROUNDS_TO_WIN:
                winner = "PLAYER 1  WINS THE MATCH!"
            elif self.p2.round_wins >= ROUNDS_TO_WIN:
                winner = "PLAYER 2  WINS THE MATCH!"
            else:
                winner = "IT'S A DRAW!"
            renderer.draw_game_over(self.screen, winner)

        pygame.display.flip()


# =============================================================================
# Entry point
# =============================================================================

if __name__ == "__main__":
    game = Game()
    game.run()
