/*
 * ============================================================================
 * tekken_mini.ino
 * Adafruit Metro RP2040 — Two-player arcade fighting game prototype
 * Display: ST7735R 1.8" TFT (128x160, rotated landscape → 160 wide x 128 tall)
 * ============================================================================
 *
 * WIRING QUICK-REFERENCE
 * -----------------------------------------------------------------------
 * TFT (ST7735R)   CS=8  DC=10  RST=not connected (tied to 3.3V)
 *                 MOSI / SCK = hardware SPI pins (bottom header)
 *
 * P1 Joystick     X=A0   Y=A1   SEL=2
 * P1 Buttons      Light=6   Heavy=7   Block=12
 *
 * P2 Joystick     X=A2   Y=A3   SEL=3
 * P2 Buttons      Light=13  Heavy=24  Block=25
 *
 * Shared LED      pin 4
 * Audio PWM       pin 5   ← NOTE: spec said pin 13, but 13 = P2 Light btn.
 *                           Connect PAM8302 IN+ to pin 5 instead.
 *                           Change PIN_AUDIO below if you rewire.
 *
 * -----------------------------------------------------------------------
 * LIBRARIES REQUIRED (install via Arduino Library Manager)
 *   Adafruit ST7735 and ST7789 Library
 *   Adafruit GFX Library
 * -----------------------------------------------------------------------
 *
 * HOW TO COMPILE
 *   Board: "Adafruit Metro RP2040"  (Boards Manager → Raspberry Pi RP2040 Boards)
 *   Flash size: any; CPU speed: 133 MHz (default is fine)
 *   Upload method: default
 * ============================================================================
 */

#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <SPI.h>

// ============================================================================
// HARDWARE PINS
// ============================================================================
#define TFT_CS    8
#define TFT_DC   10
#define TFT_RST  -1   // RST tied to 3.3V — pass -1 to skip software reset

#define P1_JOY_X    A0
#define P1_JOY_Y    A1
#define P1_JOY_SEL   2
#define P1_BTN_LIGHT 6
#define P1_BTN_HEAVY 7
#define P1_BTN_BLOCK 12

#define P2_JOY_X    A2
#define P2_JOY_Y    A3
#define P2_JOY_SEL   3
#define P2_BTN_LIGHT 13
#define P2_BTN_HEAVY 24
#define P2_BTN_BLOCK 25

#define PIN_LED    4
#define PIN_AUDIO  5   // ← moved from 13 to avoid conflict with P2_BTN_LIGHT

// ============================================================================
// SCREEN — ST7735R in landscape via setRotation(1): 160 wide × 128 tall
// ============================================================================
#define SCR_W  160
#define SCR_H  128

// ============================================================================
// GAMEPLAY CONSTANTS — Start here when tweaking feel
// ============================================================================

// --- Arena layout ------------------------------------------------------------
#define HUD_H         12    // top rows reserved for health bars
#define FLOOR_Y      106    // top edge of the floor surface (px from top)
#define FLOOR_THICK   22    // floor rectangle height

// --- Player body -------------------------------------------------------------
#define PLAYER_W      10
#define PLAYER_H      20
#define PLAYER_CROUCH_H 12  // height while crouching

// --- Movement (pixels/second as float) ---------------------------------------
#define MOVE_SPEED    65.0f
#define JUMP_VEL    -180.0f   // negative = upward; increase magnitude to jump higher
#define GRAVITY      450.0f   // downward accel; increase for snappier falls
#define KNOCKBACK_SPD 55.0f   // horizontal speed applied to defender on hit

// --- Light attack ------------------------------------------------------------
#define LIGHT_DMG          8   // damage dealt
#define LIGHT_RANGE       20   // hitbox reach (px) past player edge
#define LIGHT_CD_MS      400u  // cooldown after attacking (ms)
#define LIGHT_ACTIVE_MS  120u  // how long the hitbox is live (ms)

// --- Heavy attack ------------------------------------------------------------
#define HEAVY_DMG         22
#define HEAVY_RANGE       28
#define HEAVY_CD_MS     1050u
#define HEAVY_WINDUP_MS  160u  // delay before hitbox activates (ms)
#define HEAVY_ACTIVE_MS  200u

// --- Block -------------------------------------------------------------------
// Blocked damage = raw_damage × (BLOCK_DMG_NUM / BLOCK_DMG_DEN)
#define BLOCK_DMG_NUM   1
#define BLOCK_DMG_DEN   5   // → 20% of raw damage gets through

// --- Hitstop (brief physics freeze on hit) -----------------------------------
#define HITSTOP_LIGHT_MS  45u
#define HITSTOP_HEAVY_MS  75u

// --- Joystick dead-zone (raw ADC 0-1023; center ≈ 512) ----------------------
#define JOY_DEAD  110

// --- Round rules -------------------------------------------------------------
#define ROUNDS_TO_WIN       2
#define ROUND_END_DELAY_MS  2800u  // ms to display KO screen before next round
#define COUNTDOWN_STEP_MS    700u  // ms per countdown step (3, 2, 1, FIGHT)

// --- Visual feedback ---------------------------------------------------------
#define HIT_FLASH_MS  140u  // ms player flashes on damage

// --- Player starting positions (horizontal centers) --------------------------
#define P1_START_X  32
#define P2_START_X 118
#define START_Y     (FLOOR_Y - PLAYER_H)

// ============================================================================
// COLORS (RGB565)
// Use this site to pick: https://rgbcolorpicker.com/565
// ============================================================================
#define C_BLACK   0x0000
#define C_WHITE   0xFFFF
#define C_RED     0xF800
#define C_GREEN   0x07E0
#define C_BLUE    0x001F
#define C_YELLOW  0xFFE0
#define C_ORANGE  0xFD20
#define C_GRAY    0x8410
#define C_DKGRAY  0x2104  // near-black for backgrounds

#define C_BG      0x0861  // deep blue-black background
#define C_FLOOR   0x4228  // muted grey-green floor

#define C_P1      0x34DF  // blue fighter
#define C_P1_ATK  0x8EBF  // lighter blue when attacking
#define C_P2      0xF181  // red fighter
#define C_P2_ATK  0xFB8B  // lighter red when attacking

#define C_HP_BG   0x6000  // dark red behind health bar
#define C_HP_FG   0x0400  // dark green (overridden per-draw)
#define C_HP_OK   0x07C0  // bright green: health > 30%
#define C_HP_LOW  0xE800  // red: health ≤ 30%

// ============================================================================
// ENUMS
// ============================================================================
typedef enum {
    STATE_MENU = 0,
    STATE_COUNTDOWN,
    STATE_PLAYING,
    STATE_ROUND_END,
    STATE_GAME_OVER
} GameState;

typedef enum {
    ACT_IDLE = 0,
    ACT_WALKING,
    ACT_JUMPING,
    ACT_CROUCHING,
    ACT_LIGHT_ATK,
    ACT_HEAVY_ATK,
    ACT_BLOCKING,
    ACT_KO
} PlayerAction;

// ============================================================================
// DATA TYPES
// ============================================================================

// Axis-aligned rectangle (16-bit coordinates; saves RAM on tight boards)
typedef struct {
    int16_t x, y, w, h;
} Rect16;

// All state for one fighter
typedef struct {
    // --- Spatial ---
    float  x, y;           // top-left position (float for sub-pixel physics)
    float  vx, vy;
    bool   on_ground;
    bool   facing_right;

    // --- Health & score ---
    int    health;
    int    round_wins;
    bool   is_ko;

    // --- Action state ---
    PlayerAction action;

    // --- Attack timers (absolute millis() deadlines) ---
    // 0 means "ready"
    uint32_t light_cd_end;   // light attack cooldown expires
    uint32_t heavy_cd_end;   // heavy attack cooldown expires
    uint32_t attack_end;     // active hitbox window closes
    uint32_t windup_end;     // heavy windup finishes → hitbox opens
    bool     attack_active;  // hitbox is currently live
    bool     hit_registered; // prevents multi-hit in one swing
    uint8_t  current_atk;    // 0=none  1=light  2=heavy

    // --- Visual feedback ---
    uint32_t flash_end;      // hit-flash expires (0 = no flash)

    // --- Partial-redraw tracking ---
    // Stores the rect drawn last frame so we know what to erase
    int16_t  prev_x, prev_y, prev_w, prev_h;

    // --- Colors ---
    uint16_t color;          // idle body color
    uint16_t atk_color;      // body color while attacking
} Player;

// Snapshot of one player's input for one frame
// → Arduino port: replace read_input() with GPIO reads; struct stays the same
typedef struct {
    bool left, right, jump, crouch;
    bool light, heavy, block;
} InputState;

// ============================================================================
// GLOBALS
// ============================================================================
Adafruit_ST7735 tft = Adafruit_ST7735(TFT_CS, TFT_DC, TFT_RST);

Player    p1, p2;
GameState game_state = STATE_MENU;
int       round_num  = 1;

// --- Countdown ---
uint8_t  countdown_step = 0;   // 0="ROUND X", 1="3", 2="2", 3="1", 4="FIGHT!"
uint32_t countdown_next = 0;   // millis() for next step advance

// --- Round-end ---
uint32_t round_end_at = 0;     // millis() when to advance from ROUND_END
char     round_end_msg[20];    // "P1 WINS!" etc.

// --- Hitstop ---
uint32_t hitstop_end = 0;      // millis() when freeze ends

// --- LED ---
uint32_t led_off_at = 0;       // millis() when to turn LED off (0 = already off)

// --- Frame timing ---
uint32_t last_ms = 0;

// ============================================================================
// SOUND HELPERS
// tone() is available on RP2040 Arduino core; swap for buzzer/DAC as needed.
// Arduino → RP2040 PWM audio: connect PIN_AUDIO through PAM8302 amp
// ============================================================================
void play_tone(uint32_t freq, uint32_t dur_ms) {
    tone(PIN_AUDIO, freq, dur_ms);
}

void snd_light_hit()  { play_tone(880,  40); }
void snd_heavy_hit()  { play_tone(440,  85); }
void snd_block()      { play_tone(1400, 25); }
void snd_ko()         { play_tone(180, 550); }
void snd_fight()      { play_tone(660,  80); }
void snd_menu_beep()  { play_tone(880,  50); }

// ============================================================================
// LED HELPER
// ============================================================================
void led_flash(uint32_t dur_ms) {
    digitalWrite(PIN_LED, HIGH);
    led_off_at = millis() + dur_ms;
}

void led_tick() {
    if (led_off_at && millis() >= led_off_at) {
        digitalWrite(PIN_LED, LOW);
        led_off_at = 0;
    }
}

// ============================================================================
// INPUT READING
// Joystick: center ≈ 512, push left=low X, push right=high X,
//           push up=low Y, push down=high Y  (adjust if wired inverted)
// Buttons: INPUT_PULLUP → LOW when pressed
// ============================================================================
void read_input(InputState* inp,
                uint8_t jx_pin, uint8_t jy_pin,
                uint8_t btn_light, uint8_t btn_heavy, uint8_t btn_block) {
    int jx = analogRead(jx_pin);
    int jy = analogRead(jy_pin);

    inp->left   = (jx < 512 - JOY_DEAD);
    inp->right  = (jx > 512 + JOY_DEAD);
    inp->jump   = (jy < 512 - JOY_DEAD);   // push joystick up
    inp->crouch = (jy > 512 + JOY_DEAD);   // push joystick down

    inp->light  = (digitalRead(btn_light) == LOW);
    inp->heavy  = (digitalRead(btn_heavy) == LOW);
    inp->block  = (digitalRead(btn_block) == LOW);
}

// ============================================================================
// PLAYER INIT / RESET
// ============================================================================
void init_player(Player* p, float x, float y, bool facing_right,
                 uint16_t color, uint16_t atk_color) {
    p->x = x;  p->y = y;
    p->vx = 0; p->vy = 0;
    p->on_ground   = true;
    p->facing_right = facing_right;
    p->health      = 100;
    p->round_wins  = 0;
    p->is_ko       = false;
    p->action      = ACT_IDLE;
    p->light_cd_end  = 0;
    p->heavy_cd_end  = 0;
    p->attack_end    = 0;
    p->windup_end    = 0;
    p->attack_active = false;
    p->hit_registered = false;
    p->current_atk   = 0;
    p->flash_end     = 0;
    p->prev_x = -1;  p->prev_y = -1;  // signals "nothing drawn yet"
    p->prev_w = 0;   p->prev_h = 0;
    p->color     = color;
    p->atk_color = atk_color;
}

void reset_player_for_round(Player* p, float x, float y, bool facing_right) {
    p->x = x;  p->y = y;
    p->vx = 0; p->vy = 0;
    p->on_ground   = true;
    p->facing_right = facing_right;
    p->health      = 100;
    p->is_ko       = false;
    p->action      = ACT_IDLE;
    p->light_cd_end  = 0;
    p->heavy_cd_end  = 0;
    p->attack_end    = 0;
    p->windup_end    = 0;
    p->attack_active = false;
    p->hit_registered = false;
    p->current_atk   = 0;
    p->flash_end     = 0;
    p->prev_x = -1;  p->prev_y = -1;
    p->prev_w = 0;   p->prev_h = 0;
}

// ============================================================================
// RECTANGLE HELPERS
// ============================================================================

// Body hurtbox (crouching = shorter rect anchored to floor)
Rect16 player_rect(const Player* p) {
    Rect16 r;
    int h      = (p->action == ACT_CROUCHING) ? PLAYER_CROUCH_H : PLAYER_H;
    int offset = PLAYER_H - h;   // shift down so feet stay on floor
    r.x = (int16_t)p->x;
    r.y = (int16_t)(p->y + offset);
    r.w = PLAYER_W;
    r.h = (int16_t)h;
    return r;
}

// Active attack hitbox (w=0 when inactive — check w>0 before using)
Rect16 attack_rect(const Player* p) {
    Rect16 r; r.x=0; r.y=0; r.w=0; r.h=0;
    if (!p->attack_active) return r;
    int reach = (p->current_atk == 1) ? LIGHT_RANGE : HEAVY_RANGE;
    r.x  = p->facing_right ? (int16_t)(p->x + PLAYER_W) : (int16_t)(p->x - reach);
    r.y  = (int16_t)(p->y + 4);
    r.w  = (int16_t)reach;
    r.h  = (int16_t)(PLAYER_H - 8);
    return r;
}

bool rects_overlap(Rect16 a, Rect16 b) {
    return (a.x < b.x + b.w) && (a.x + a.w > b.x)
        && (a.y < b.y + b.h) && (a.y + a.h > b.y);
}

// ============================================================================
// PHYSICS UPDATE
// ============================================================================
void update_physics(Player* p, float dt) {
    if (!p->on_ground)
        p->vy += GRAVITY * dt;

    p->x += p->vx * dt;
    p->y += p->vy * dt;

    // Floor collision
    const float floor_top = (float)(FLOOR_Y - PLAYER_H);
    if (p->y >= floor_top) {
        p->y = floor_top;
        p->vy = 0;
        if (!p->on_ground) {
            p->on_ground = true;
            if (p->action == ACT_JUMPING)
                p->action = ACT_IDLE;
        }
    }

    // Screen edge clamp
    if (p->x < 0) p->x = 0;
    if (p->x > SCR_W - PLAYER_W) p->x = (float)(SCR_W - PLAYER_W);
}

// ============================================================================
// ATTACK WINDOW UPDATE (millis-based timers → no dt required)
// ============================================================================
void update_attack_window(Player* p) {
    if (p->action != ACT_LIGHT_ATK && p->action != ACT_HEAVY_ATK) return;

    uint32_t now = millis();

    // Heavy: windup done → activate hitbox
    if (p->windup_end && now >= p->windup_end) {
        p->windup_end    = 0;
        p->attack_active = true;
        p->hit_registered = false;
    }

    // Active window expired → return to idle
    if (p->attack_end && now >= p->attack_end) {
        p->attack_end    = 0;
        p->attack_active = false;
        p->current_atk   = 0;
        p->action        = ACT_IDLE;
    }
}

// ============================================================================
// START AN ATTACK
// ============================================================================
void start_attack(Player* p, uint8_t atk_type) {
    uint32_t now = millis();
    p->vx = 0;
    p->current_atk    = atk_type;
    p->hit_registered = false;

    if (atk_type == 1) {  // light: instant hitbox
        p->action        = ACT_LIGHT_ATK;
        p->attack_active = true;
        p->windup_end    = 0;
        p->attack_end    = now + LIGHT_ACTIVE_MS;
        p->light_cd_end  = now + LIGHT_CD_MS;
    } else {              // heavy: windup → hitbox
        p->action        = ACT_HEAVY_ATK;
        p->attack_active = false;
        p->windup_end    = now + HEAVY_WINDUP_MS;
        p->attack_end    = now + HEAVY_WINDUP_MS + HEAVY_ACTIVE_MS;
        p->heavy_cd_end  = now + HEAVY_CD_MS;
    }
}

// ============================================================================
// HANDLE INPUT → PLAYER ACTION STATE
// This function is the main porting target: replace InputState reads with GPIO.
// ============================================================================
void handle_input(Player* p, const InputState* inp) {
    if (p->is_ko) return;

    uint32_t now       = millis();
    bool     in_attack = (p->action == ACT_LIGHT_ATK || p->action == ACT_HEAVY_ATK);

    if (!in_attack) {
        // Horizontal movement
        if      (inp->left)  p->vx = -MOVE_SPEED;
        else if (inp->right) p->vx =  MOVE_SPEED;
        else                 p->vx =  0;

        // Jump (only from ground)
        if (inp->jump && p->on_ground) {
            p->vy        = JUMP_VEL;
            p->on_ground = false;
            p->action    = ACT_JUMPING;
        }

        // Crouch (only on ground)
        if (inp->crouch && p->on_ground) {
            p->vx     = 0;
            p->action = ACT_CROUCHING;
        } else if (!inp->crouch && p->action == ACT_CROUCHING) {
            p->action = ACT_IDLE;
        }

        // Block (only on ground — held button)
        if (inp->block && p->on_ground) {
            p->vx     = 0;
            p->action = ACT_BLOCKING;
        } else if (!inp->block && p->action == ACT_BLOCKING) {
            p->action = ACT_IDLE;
        }

        // Attacks — cooldown prevents spam; holding button is fine
        if (inp->light && now >= p->light_cd_end) {
            start_attack(p, 1);
        } else if (inp->heavy && now >= p->heavy_cd_end) {
            start_attack(p, 2);
        }
    }

    // Correct idle / walking / jumping label based on physics state
    if (p->on_ground &&
        p->action != ACT_CROUCHING  && p->action != ACT_BLOCKING  &&
        p->action != ACT_LIGHT_ATK  && p->action != ACT_HEAVY_ATK &&
        p->action != ACT_KO) {
        p->action = (p->vx != 0) ? ACT_WALKING : ACT_IDLE;
    }
    if (!p->on_ground &&
        p->action != ACT_LIGHT_ATK && p->action != ACT_HEAVY_ATK &&
        p->action != ACT_KO) {
        p->action = ACT_JUMPING;
    }
}

// ============================================================================
// AUTO-FACE OPPONENT
// ============================================================================
void auto_face(Player* p, const Player* opp) {
    float my_cx  = p->x   + PLAYER_W * 0.5f;
    float opp_cx = opp->x + PLAYER_W * 0.5f;
    p->facing_right = (opp_cx > my_cx);
}

// ============================================================================
// TAKE DAMAGE (blocking reduces damage and knockback)
// ============================================================================
void take_damage(Player* defender, int damage, int kb_dir) {
    if (defender->action == ACT_BLOCKING) {
        damage = (damage * BLOCK_DMG_NUM) / BLOCK_DMG_DEN;
        // Reduced knockback when blocking
        defender->vx = kb_dir * KNOCKBACK_SPD * 0.35f;
    } else {
        defender->vx = (float)(kb_dir * KNOCKBACK_SPD);
    }

    defender->health -= damage;
    if (defender->health < 0) defender->health = 0;
    defender->flash_end = millis() + HIT_FLASH_MS;

    if (defender->health == 0) {
        defender->is_ko  = true;
        defender->action = ACT_KO;
        defender->vy     = -80.0f;  // small upward pop on KO
        defender->vx     = 0;
    }
}

// ============================================================================
// HIT DETECTION AND RESOLUTION
// Returns: 0 = miss,  1 = hit landed,  2 = blocked
// ============================================================================
uint8_t check_and_resolve_hit(Player* attacker, Player* defender) {
    if (!attacker->attack_active)   return 0;
    if (attacker->hit_registered)   return 0;

    Rect16 atk = attack_rect(attacker);
    if (atk.w == 0) return 0;

    Rect16 def = player_rect(defender);
    if (!rects_overlap(atk, def)) return 0;

    bool is_heavy      = (attacker->current_atk == 2);
    bool was_blocking  = (defender->action == ACT_BLOCKING);
    int  damage        = is_heavy ? HEAVY_DMG : LIGHT_DMG;
    int  kb_dir        = attacker->facing_right ? 1 : -1;

    take_damage(defender, damage, kb_dir);
    attacker->hit_registered = true;

    return was_blocking ? 2 : 1;
}

// ============================================================================
// RENDERING HELPERS
// ============================================================================

// Erase a rect back to background, then repaint the floor strip if needed.
void erase_rect(int16_t x, int16_t y, int16_t w, int16_t h) {
    if (w <= 0 || h <= 0) return;
    tft.fillRect(x, y, w, h, C_BG);
    // Repaint floor strip if this rect overlaps it
    int16_t fy = max(y, (int16_t)FLOOR_Y);
    int16_t fb = min((int16_t)(y + h), (int16_t)(FLOOR_Y + FLOOR_THICK));
    if (fb > fy)
        tft.fillRect(x, fy, w, fb - fy, C_FLOOR);
}

// Draw one player with partial-erase optimization.
// Only repaints pixels that actually changed (position or color flash).
void draw_player(Player* p) {
    uint32_t now = millis();
    Rect16   r   = player_rect(p);

    // Erase old position if it moved or size changed
    if (p->prev_x >= 0) {
        bool moved = (r.x != p->prev_x || r.y != p->prev_y ||
                      r.w != p->prev_w || r.h != p->prev_h);
        if (moved)
            erase_rect(p->prev_x, p->prev_y, p->prev_w, p->prev_h);
    }

    // Pick body color
    uint16_t col;
    if (p->is_ko) {
        col = C_GRAY;
    } else if (p->flash_end && now < p->flash_end) {
        // Alternate white and body color at ~10 Hz for hit flash
        col = ((now / 50) % 2 == 0) ? C_WHITE : p->color;
    } else if (p->action == ACT_LIGHT_ATK || p->action == ACT_HEAVY_ATK) {
        col = p->atk_color;
    } else if (p->action == ACT_BLOCKING) {
        col = C_GRAY;
    } else {
        col = p->color;
    }

    // Body rectangle + white outline
    tft.fillRect(r.x, r.y, r.w, r.h, col);
    tft.drawRect(r.x, r.y, r.w, r.h, C_WHITE);

    // Facing dot (1-pixel eye on the side facing the opponent)
    int16_t eye_x = p->facing_right ? r.x + r.w - 2 : r.x + 1;
    int16_t eye_y = r.y + 3;
    tft.drawPixel(eye_x, eye_y, C_BLACK);

    // Save rect for next frame erase
    p->prev_x = r.x;  p->prev_y = r.y;
    p->prev_w = r.w;  p->prev_h = r.h;
}

// Health bar.  flip=true → bar drains left (used for P2 mirrored layout).
void draw_health_bar(int16_t x, int16_t y, int16_t w, int16_t h,
                     int health, bool flip) {
    int fill = (w * health) / 100;
    if (fill < 0) fill = 0;
    uint16_t fg = (health <= 30) ? C_HP_LOW : C_HP_OK;

    tft.fillRect(x, y, w, h, C_HP_BG);
    if (fill > 0) {
        int16_t fx = flip ? x + (w - fill) : x;
        tft.fillRect(fx, y, fill, h, fg);
    }
    tft.drawRect(x, y, w, h, C_WHITE);
}

// Full HUD: both health bars + round win pips.
void draw_hud() {
    // P1 bar (left, drains right)
    draw_health_bar(2, 2, 64, 8, p1.health, false);
    // P2 bar (right, drains left — mirrored feel)
    draw_health_bar(94, 2, 64, 8, p2.health, true);

    // Round win pips in the center gap (pips are 3px circles)
    tft.fillRect(68, 2, 24, 8, C_BG);   // clear center
    for (int i = 0; i < ROUNDS_TO_WIN; i++) {
        uint16_t cp1 = (i < p1.round_wins) ? C_YELLOW : C_DKGRAY;
        uint16_t cp2 = (i < p2.round_wins) ? C_YELLOW : C_DKGRAY;
        tft.fillCircle(72 + i * 7, 6, 2, cp1);
        tft.fillCircle(88 - i * 7, 6, 2, cp2);
    }
}

// Draw the static arena floor line.
void draw_floor() {
    tft.fillRect(0, FLOOR_Y, SCR_W, FLOOR_THICK, C_FLOOR);
    tft.drawLine(0, FLOOR_Y, SCR_W, FLOOR_Y, C_GRAY);
}

// Clear only the playfield (between HUD and floor), then redraw floor.
void clear_arena() {
    tft.fillRect(0, HUD_H + 1, SCR_W, FLOOR_Y - HUD_H - 1, C_BG);
    draw_floor();
    // Reset prev rects so players redraw from scratch next frame
    p1.prev_x = -1;
    p2.prev_x = -1;
}

// Draw text centered at (cx, y).  Adafruit GFX characters are 6*size wide.
void draw_centered(const char* txt, int16_t y, uint16_t color, uint8_t size) {
    tft.setTextSize(size);
    tft.setTextColor(color, C_BG);   // second arg = background → erases behind text
    int16_t text_w = (int16_t)(strlen(txt) * 6 * size);
    int16_t x      = (SCR_W - text_w) / 2;
    if (x < 0) x = 0;
    tft.setCursor(x, y);
    tft.print(txt);
}

// Erase a horizontal text band (used to clear countdown digits).
void clear_text_band(int16_t y, int16_t h) {
    tft.fillRect(0, y, SCR_W, h, C_BG);
}

// ============================================================================
// STATE: MENU
// ============================================================================
void enter_menu() {
    game_state = STATE_MENU;
    tft.fillScreen(C_BG);
    tft.setTextWrap(false);
    draw_centered("TEKKEN MINI", 18, C_YELLOW, 2);
    draw_centered("2-PLAYER FIGHTER",  44, C_WHITE, 1);
    draw_centered("P1: JOY + B1/B2/B3", 60, C_P1, 1);
    draw_centered("P2: JOY + B1/B2/B3", 72, C_P2, 1);
    draw_centered("B1 = Light  B2 = Heavy", 84, C_WHITE, 1);
    draw_centered("B3 = Block",           96, C_WHITE, 1);
    draw_centered("Press P1-B1 to Start", 112, C_YELLOW, 1);
}

void update_menu(const InputState* i1) {
    if (i1->light) {
        snd_menu_beep();
        delay(80);  // debounce
        init_player(&p1, P1_START_X - PLAYER_W/2, START_Y, true,  C_P1, C_P1_ATK);
        init_player(&p2, P2_START_X - PLAYER_W/2, START_Y, false, C_P2, C_P2_ATK);
        round_num = 1;
        enter_countdown();
    }
}

// ============================================================================
// STATE: COUNTDOWN  ("ROUND X" → "3" → "2" → "1" → "FIGHT!")
// ============================================================================
void enter_countdown() {
    game_state      = STATE_COUNTDOWN;
    countdown_step  = 0;
    countdown_next  = millis() + COUNTDOWN_STEP_MS + 300;  // first step a bit longer

    clear_arena();
    draw_hud();
    draw_player(&p1);
    draw_player(&p2);

    // Show "ROUND X"
    char buf[14];
    snprintf(buf, sizeof(buf), "ROUND %d", round_num);
    draw_centered(buf, 50, C_YELLOW, 2);
}

void update_countdown() {
    if (millis() < countdown_next) return;

    countdown_step++;
    clear_text_band(42, 40);   // erase countdown area

    if (countdown_step <= 3) {
        // "3", "2", "1"
        char buf[4];
        snprintf(buf, sizeof(buf), "%d", 4 - countdown_step);
        draw_centered(buf, 48, C_WHITE, 3);
        countdown_next = millis() + COUNTDOWN_STEP_MS;
    } else if (countdown_step == 4) {
        draw_centered("FIGHT!", 50, C_GREEN, 2);
        countdown_next = millis() + 500;
    } else {
        // Clear the FIGHT! text and start playing
        clear_text_band(42, 40);
        game_state = STATE_PLAYING;
        last_ms    = millis();
        snd_fight();
    }
}

// ============================================================================
// STATE: PLAYING
// ============================================================================
void update_playing(const InputState* i1, const InputState* i2) {
    uint32_t now = millis();

    // Hitstop: freeze everything briefly on impact
    if (now < hitstop_end) {
        led_tick();
        return;
    }

    // Delta time (capped to prevent spiral-of-death after lag spikes)
    float dt = (now - last_ms) / 1000.0f;
    last_ms  = now;
    if (dt > 0.05f) dt = 0.05f;

    // Advance attack windows (millis-based — dt independent)
    update_attack_window(&p1);
    update_attack_window(&p2);

    // Input → state
    handle_input(&p1, i1);
    handle_input(&p2, i2);

    // Auto-face
    auto_face(&p1, &p2);
    auto_face(&p2, &p1);

    // Physics
    update_physics(&p1, dt);
    update_physics(&p2, dt);

    // Hit detection (P1 hits P2, then P2 hits P1)
    uint8_t h1 = check_and_resolve_hit(&p1, &p2);
    uint8_t h2 = check_and_resolve_hit(&p2, &p1);

    // Hit feedback
    if (h1 > 0) {
        bool heavy = (p1.current_atk == 2);
        if (h1 == 2)     snd_block();
        else if (heavy)  snd_heavy_hit();
        else             snd_light_hit();
        led_flash(80);
        hitstop_end = now + (heavy ? HITSTOP_HEAVY_MS : HITSTOP_LIGHT_MS);
    }
    if (h2 > 0) {
        bool heavy = (p2.current_atk == 2);
        if (h2 == 2)     snd_block();
        else if (heavy)  snd_heavy_hit();
        else             snd_light_hit();
        led_flash(80);
        hitstop_end = now + (heavy ? HITSTOP_HEAVY_MS : HITSTOP_LIGHT_MS);
    }

    led_tick();

    // Render both fighters and HUD
    draw_player(&p1);
    draw_player(&p2);
    draw_hud();

    // Check for KO
    if (p1.is_ko || p2.is_ko)
        enter_round_end();
}

// ============================================================================
// STATE: ROUND_END
// ============================================================================
void enter_round_end() {
    game_state = STATE_ROUND_END;

    if (p1.is_ko && p2.is_ko) {
        snprintf(round_end_msg, sizeof(round_end_msg), "DRAW!");
    } else if (p2.is_ko) {
        p1.round_wins++;
        snprintf(round_end_msg, sizeof(round_end_msg), "P1 WINS!");
    } else {
        p2.round_wins++;
        snprintf(round_end_msg, sizeof(round_end_msg), "P2 WINS!");
    }

    snd_ko();
    led_flash(700);

    // Draw KO overlay box
    draw_hud();  // update win pip immediately
    tft.fillRect(18, 44, SCR_W - 36, 40, C_BG);
    tft.drawRect(18, 44, SCR_W - 36, 40, C_WHITE);
    draw_centered("K  O  !", 48, C_RED, 2);
    draw_centered(round_end_msg, 70, C_YELLOW, 1);

    round_end_at = millis() + ROUND_END_DELAY_MS;
}

void update_round_end() {
    led_tick();
    if (millis() < round_end_at) return;

    // Advance to next round or game over
    if (p1.round_wins >= ROUNDS_TO_WIN || p2.round_wins >= ROUNDS_TO_WIN) {
        enter_game_over();
    } else {
        round_num++;
        reset_player_for_round(&p1, P1_START_X - PLAYER_W/2, START_Y, true);
        reset_player_for_round(&p2, P2_START_X - PLAYER_W/2, START_Y, false);
        enter_countdown();
    }
}

// ============================================================================
// STATE: GAME_OVER
// ============================================================================
void enter_game_over() {
    game_state = STATE_GAME_OVER;
    tft.fillScreen(C_BG);
    tft.setTextWrap(false);

    const char* winner_line;
    if (p1.round_wins >= ROUNDS_TO_WIN)
        winner_line = "P1 WINS MATCH!";
    else if (p2.round_wins >= ROUNDS_TO_WIN)
        winner_line = "P2 WINS MATCH!";
    else
        winner_line = "IT'S A DRAW!";

    draw_centered("GAME OVER",   28, C_RED,    2);
    draw_centered(winner_line,   58, C_YELLOW, 1);
    draw_centered("Press P1-B1", 90, C_WHITE,  1);
    draw_centered("to play again",102, C_WHITE, 1);
}

void update_game_over(const InputState* i1) {
    if (i1->light) {
        snd_menu_beep();
        delay(120);  // debounce
        init_player(&p1, P1_START_X - PLAYER_W/2, START_Y, true,  C_P1, C_P1_ATK);
        init_player(&p2, P2_START_X - PLAYER_W/2, START_Y, false, C_P2, C_P2_ATK);
        round_num = 1;
        enter_countdown();
    }
}

// ============================================================================
// SETUP
// ============================================================================
void setup() {
    Serial.begin(115200);

    // --- Input pin modes ---
    pinMode(P1_JOY_SEL,  INPUT_PULLUP);
    pinMode(P1_BTN_LIGHT, INPUT_PULLUP);
    pinMode(P1_BTN_HEAVY, INPUT_PULLUP);
    pinMode(P1_BTN_BLOCK, INPUT_PULLUP);

    pinMode(P2_JOY_SEL,  INPUT_PULLUP);
    pinMode(P2_BTN_LIGHT, INPUT_PULLUP);
    pinMode(P2_BTN_HEAVY, INPUT_PULLUP);
    pinMode(P2_BTN_BLOCK, INPUT_PULLUP);

    // --- LED ---
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, LOW);

    // --- TFT ---
    // INITR_BLACKTAB matches most 1.8" ST7735R modules with black border.
    // If colors look wrong, try INITR_GREENTAB or INITR_144GREENTAB.
    tft.initR(INITR_BLACKTAB);
    tft.setRotation(1);       // landscape: 160 wide × 128 tall
    tft.fillScreen(C_BG);
    tft.setTextWrap(false);

    enter_menu();
}

// ============================================================================
// LOOP
// ============================================================================
void loop() {
    // --- Read both players' inputs ---
    InputState i1, i2;
    read_input(&i1, P1_JOY_X, P1_JOY_Y, P1_BTN_LIGHT, P1_BTN_HEAVY, P1_BTN_BLOCK);
    read_input(&i2, P2_JOY_X, P2_JOY_Y, P2_BTN_LIGHT, P2_BTN_HEAVY, P2_BTN_BLOCK);

    // --- State machine ---
    switch (game_state) {
        case STATE_MENU:       update_menu(&i1);         break;
        case STATE_COUNTDOWN:  update_countdown();        break;
        case STATE_PLAYING:    update_playing(&i1, &i2); break;
        case STATE_ROUND_END:  update_round_end();        break;
        case STATE_GAME_OVER:  update_game_over(&i1);    break;
    }

    // Small yield — RP2040 core 0 yields to core 1 / USB stack
    delay(1);
}
