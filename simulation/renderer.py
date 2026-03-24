# =============================================================================
# renderer.py — All drawing code. No game logic lives here.
#
# Arduino mapping:
#   These functions become TFT drawing calls (tft.fillRect, tft.drawString,
#   tft.drawLine, etc.). The same separation of logic vs. rendering applies.
# =============================================================================

import pygame
from constants import *
from player import Action

# Module-level font cache; populated by init_fonts()
_fonts: dict = {}


def init_fonts():
    """Call once after pygame.init() to populate the font cache."""
    _fonts["large"]  = pygame.font.Font(None, FONT_LARGE)
    _fonts["medium"] = pygame.font.Font(None, FONT_MEDIUM)
    _fonts["small"]  = pygame.font.Font(None, FONT_SMALL)


# =============================================================================
# Primitive helpers
# =============================================================================

def draw_text(surface, text, size, color, x, y, center=True):
    """Render a text string. size is 'large' | 'medium' | 'small'."""
    font = _fonts.get(size, _fonts["medium"])
    surf = font.render(str(text), True, color)
    rect = surf.get_rect(center=(x, y)) if center else surf.get_rect(topleft=(x, y))
    surface.blit(surf, rect)


# =============================================================================
# Scene elements
# =============================================================================

def draw_background(surface):
    """Solid background + floor platform."""
    surface.fill(BG_COLOR)
    # Floor fill
    pygame.draw.rect(surface, FLOOR_COLOR,
                     pygame.Rect(0, FLOOR_Y, SCREEN_WIDTH, SCREEN_HEIGHT - FLOOR_Y))
    # Floor edge line
    pygame.draw.line(surface, FLOOR_LINE_COLOR, (0, FLOOR_Y), (SCREEN_WIDTH, FLOOR_Y), 3)

    # Subtle background grid lines for depth
    for gx in range(0, SCREEN_WIDTH, 96):
        pygame.draw.line(surface, (20, 20, 34), (gx, 0), (gx, FLOOR_Y), 1)


def draw_player(surface, player):
    """Draw the fighter rectangle with visual state feedback."""
    rect = player.get_rect()

    # --- Choose fill color based on state ------------------------------------
    if player.is_flashing() and int(player.hit_flash_timer * 22) % 2 == 0:
        # Alternating white flash when hit
        fill_color = WHITE
    elif player.action in (Action.LIGHT_ATTACK, Action.HEAVY_ATTACK):
        fill_color = player.attack_color
    elif player.action == Action.BLOCKING:
        fill_color = GRAY
    elif player.action == Action.KO:
        fill_color = DARK_GRAY
    else:
        fill_color = player.color

    pygame.draw.rect(surface, fill_color, rect)
    pygame.draw.rect(surface, WHITE, rect, 2)  # outline

    # --- Face indicator (eye dot) --------------------------------------------
    # Shows which direction the player is facing
    eye_offset = rect.width - 10 if player.facing_right else 10
    eye_x = rect.left + eye_offset
    eye_y = rect.top + 16
    pygame.draw.circle(surface, WHITE, (eye_x, eye_y), 6)
    pupil_offset = 2 if player.facing_right else -2
    pygame.draw.circle(surface, BLACK, (eye_x + pupil_offset, eye_y), 3)

    # --- Blocking shield indicator -------------------------------------------
    if player.action == Action.BLOCKING:
        shield_x = rect.right if player.facing_right else rect.left - 8
        pygame.draw.rect(surface, CYAN, pygame.Rect(shield_x, rect.top + 10, 8, rect.height - 20))

    # --- Active attack hitbox (debug outline) --------------------------------
    atk_rect = player.get_attack_hitbox()
    if atk_rect:
        pygame.draw.rect(surface, YELLOW, atk_rect, 2)

    # --- Heavy attack windup indicator (pulsing bar above player) -----------
    if player.action == Action.HEAVY_ATTACK and player.attack_windup > 0:
        ratio = player.attack_windup / HEAVY_WINDUP
        bar_w = int(player.width * ratio)
        pygame.draw.rect(surface, ORANGE,
                         pygame.Rect(int(player.x), int(player.y) - 12, bar_w, 6))


def draw_cooldown_bars(surface, p1, p2):
    """Small bars above each player showing cooldown remaining. Blue=light, orange=heavy."""
    for player in (p1, p2):
        base_y = int(player.y) - 10

        if player.light_cooldown > 0:
            ready_ratio = 1.0 - (player.light_cooldown / LIGHT_COOLDOWN)
            bar_w = int(player.width * ready_ratio)
            # Background (empty)
            pygame.draw.rect(surface, DARK_GRAY,
                             pygame.Rect(int(player.x), base_y - 14, player.width, 5))
            # Fill (progress toward ready)
            pygame.draw.rect(surface, CYAN,
                             pygame.Rect(int(player.x), base_y - 14, bar_w, 5))

        if player.heavy_cooldown > 0:
            ready_ratio = 1.0 - (player.heavy_cooldown / HEAVY_COOLDOWN)
            bar_w = int(player.width * ready_ratio)
            pygame.draw.rect(surface, DARK_GRAY,
                             pygame.Rect(int(player.x), base_y - 22, player.width, 5))
            pygame.draw.rect(surface, ORANGE,
                             pygame.Rect(int(player.x), base_y - 22, bar_w, 5))


def draw_action_label(surface, p1, p2):
    """Tiny state label beneath each fighter — helpful during development."""
    for player in (p1, p2):
        rect = player.get_rect()
        draw_text(surface, player.action.upper(), "small", LIGHT_GRAY,
                  rect.centerx, rect.bottom + 14)


# =============================================================================
# HUD
# =============================================================================

def draw_hud(surface, p1, p2, round_num, p1_wins, p2_wins):
    """Health bars, win pips, and round number."""
    bar_w   = 310
    bar_h   = 26
    bar_y   = 12
    padding = 18

    # --- P1 health bar (left) ------------------------------------------------
    _draw_health_bar(surface,
                     x=padding, y=bar_y, w=bar_w, h=bar_h,
                     health=p1.health, max_health=MAX_HEALTH,
                     label="P1", flip=False)

    # --- P2 health bar (right, fill from right edge) -------------------------
    _draw_health_bar(surface,
                     x=SCREEN_WIDTH - padding - bar_w, y=bar_y, w=bar_w, h=bar_h,
                     health=p2.health, max_health=MAX_HEALTH,
                     label="P2", flip=True)

    # --- Round label (centre) ------------------------------------------------
    draw_text(surface, f"ROUND {round_num}", "small", WHITE,
              SCREEN_WIDTH // 2, bar_y + bar_h // 2)

    # --- Win pips (small circles beneath bars) --------------------------------
    pip_y   = bar_y + bar_h + 10
    pip_r   = 7
    pip_gap = 20

    for i in range(ROUNDS_TO_WIN):
        # P1 pips grow rightward from left edge
        cx = padding + pip_r + i * pip_gap
        color = YELLOW if i < p1_wins else DARK_GRAY
        pygame.draw.circle(surface, color, (cx, pip_y), pip_r)
        pygame.draw.circle(surface, WHITE,  (cx, pip_y), pip_r, 1)

        # P2 pips grow leftward from right edge
        cx = SCREEN_WIDTH - padding - pip_r - i * pip_gap
        color = YELLOW if i < p2_wins else DARK_GRAY
        pygame.draw.circle(surface, color, (cx, pip_y), pip_r)
        pygame.draw.circle(surface, WHITE,  (cx, pip_y), pip_r, 1)


def _draw_health_bar(surface, x, y, w, h, health, max_health, label, flip):
    ratio   = health / max_health
    fill_w  = max(0, int(w * ratio))
    bar_color = HP_BAR_LOW if ratio < 0.30 else HP_BAR_FG

    # Background
    pygame.draw.rect(surface, HP_BAR_BG, (x, y, w, h))

    # Health fill — P2 bar fills from the right
    if fill_w > 0:
        fill_x = x + (w - fill_w) if flip else x
        pygame.draw.rect(surface, bar_color, (fill_x, y, fill_w, h))

    # Border
    pygame.draw.rect(surface, HP_BORDER, (x, y, w, h), 2)

    # Label
    draw_text(surface, f"{label}  {health}", "small", WHITE, x + w // 2, y + h // 2)


# =============================================================================
# Game state screens
# =============================================================================

def draw_menu(surface):
    surface.fill(BG_COLOR)

    draw_text(surface, "TEKKEN  MINI", "large",  YELLOW,
              SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3 - 10)
    draw_text(surface, "2-PLAYER ARCADE FIGHTER", "medium", LIGHT_GRAY,
              SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3 + 52)

    draw_text(surface, "Press  ENTER  to  Start", "medium", WHITE,
              SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 30)

    # Controls cheat-sheet
    ctrl_y = SCREEN_HEIGHT * 3 // 4
    draw_text(surface,
              "P1:  A/D  Move    W  Jump    S  Crouch    J  Light    K  Heavy    L  Block",
              "small", P1_COLOR, SCREEN_WIDTH // 2, ctrl_y)
    draw_text(surface,
              "P2:  ←/→  Move    ↑  Jump    ↓  Crouch    ,  Light    .  Heavy    /  Block",
              "small", P2_COLOR, SCREEN_WIDTH // 2, ctrl_y + 28)
    draw_text(surface, "ESC  Pause / Quit", "small", GRAY,
              SCREEN_WIDTH // 2, ctrl_y + 60)


def draw_countdown(surface, text):
    """Overlay large countdown text on top of the playing field."""
    # Semi-transparent black backdrop
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 110))
    surface.blit(overlay, (0, 0))
    draw_text(surface, text, "large", WHITE, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)


def draw_round_end(surface, round_win_text):
    """KO / round result overlay."""
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 150))
    surface.blit(overlay, (0, 0))

    draw_text(surface, "K . O .", "large", RED,
              SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 40)
    draw_text(surface, round_win_text, "medium", YELLOW,
              SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 30)


def draw_paused(surface):
    overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    surface.blit(overlay, (0, 0))
    draw_text(surface, "PAUSED", "large", WHITE, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
    draw_text(surface, "ESC to resume", "small", LIGHT_GRAY,
              SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 55)


def draw_game_over(surface, winner_text):
    surface.fill(BG_COLOR)
    draw_text(surface, "GAME  OVER", "large",  RED,
              SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3)
    draw_text(surface, winner_text, "medium", YELLOW,
              SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
    draw_text(surface, "ENTER — Play Again     ESC — Quit", "small", LIGHT_GRAY,
              SCREEN_WIDTH // 2, SCREEN_HEIGHT * 2 // 3 + 10)
