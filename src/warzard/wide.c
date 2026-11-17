/*
 * WIDE.C  Widescreen for Warzard (CPS3, Darksoft bank 1)
 *
 * There is no source for this game; everything here is reached through addresses found in the program
 * (tools/build_warzard.py lists them and builds the patch). In wide mode (screen mode 7, 496 pixels, the
 * 3rd Strike timing, which Warzard's window table already has) the 384-pixel picture is shown in the middle of the
 * wider screen:
 *
 *  - the text layer (the whole fight HUD, menus, messages): every code literal that addresses the text tile map
 *    (25040000-25043FFF) points at a RAM shadow instead, in both modes; at the end of the task scheduler's first
 *    two passes in a frame (all text is drawn by then) the shadow is copied to text RAM: as it is in 4:3, 7 tiles
 *    (56 px) further right in wide mode, the margins filled with the tile the game cleared the row with;
 *  - sprites and background layers move together through the game's own global X offset (02051BC0, added to
 *    every layer's scroll and sprite scroll), changed only while the vertical blank routines write the scroll
 *    registers, so the game never sees it: +56 outside fights; in a fight the view follows the camera but stops
 *    at the stage's camera limits, so the extra width shows only stage the game shows in 4:3; screen-fixed sprite
 *    groups always +56.
 *
 * Fights play exactly as in 4:3 (camera, limits and collisions are untouched); only what is drawn moves.
 *
 * Wide mode is the SCREEN MODE item added to the service menu game settings (both its pages: English and
 * Japanese), in effect from the next boot (the game applies its EEPROM image at boot and after a save).
 */

typedef signed char s8;
typedef unsigned char u8;
typedef short s16;
typedef unsigned short u16;
typedef long s32;
typedef unsigned long u32;

#include "game.h"  /* the game's addresses (G_*), written by tools/build_warzard.py */

#pragma section WIDE

/* the module's RAM (G_VARS, in a RAM range the game never uses) */
#define WIDE_ON     (*(volatile u8*)(G_VARS + 0))   /* wide mode in effect */
#define CAM_LIVE    (*(volatile u8*)(G_VARS + 1))   /* vertical blanks the fight camera counts as running */
#define SHIFT_NOW   (*(volatile s16*)(G_VARS + 4))  /* the world shift used this frame (for tests) */

/* the game's */
#define LAYER0_X    (*(volatile s16*)G_LAYER0_X)   /* main layer x being published this frame (the camera) */
#define SCREEN_X    (*(volatile s16*)G_SCREEN_X)   /* global x offset, added to every layer and sprite scroll */
#define STAGE       (*(volatile u8*)G_STAGE)
#define CAM_LIMITS  ((const s16*)G_CAM_LIMITS)     /* per stage: camera x min, max */
#define STAGES      10
#define SCHED_PASS  (*(volatile s32*)G_SCHED_PASS) /* task scheduler: passes over the tasks this frame (0 = first) */

#define TEXT_MAP    0x25040000                     /* text RAM tile map: 64 rows of 64 tiles, 4 bytes each */
#define SHADOW      G_SHADOW                       /* its RAM shadow, which the game draws into */
#define MAP_ROWS    64                             /* two 32-row pages (the game flips between them) */
#define FILL_COL    56                             /* a column 4:3 never shows: holds the tile the row was
                                                      cleared with (0x00200012 in the game, 0x12000000 in the
                                                      service menu, whose font differs) */
#define SHIFT_TILES 7
#define VIS_COLS    48                             /* 384 / 8 */
#define HALF        56                             /* (496 - 384) / 2 */

typedef s32 (*method)(s32, s32, s32, s32);
#define ORIG_CAMERA ((method)G_CAMERA)
#define ORIG_SCROLL ((method)G_SCROLL)
#define ORIG_SET_MODE ((method)G_SET_MODE)
#define ORIG_GSCROLL ((method)G_GSCROLL)

/* the fight camera's step (all stages): run it, note that the camera is live */
s32 wide_camera(s32 a, s32 b, s32 c, s32 d) {
    s32 r = ORIG_CAMERA(a, b, c, d);
    CAM_LIVE = 4;
    return r;
}

/* how far right sprites and background are drawn */
static s16 world_shift(void) {
    s32 cam, lo, hi, view, st;
    if (CAM_LIVE == 0) {
        return HALF;
    }
    CAM_LIVE--;
    st = STAGE;
    if (st >= STAGES) {
        return HALF;
    }
    cam = LAYER0_X;
    lo = CAM_LIMITS[st * 2];
    hi = CAM_LIMITS[st * 2 + 1] - 2 * HALF;
    view = cam - HALF;
    if (hi >= lo) {
        if (view < lo) {
            view = lo;
        }
        if (view > hi) {
            view = hi;
        }
    }
    return cam - view;
}

/*
 * the vertical blank's sprite scroll register writer (all 8 groups: x = group x - global offset + 02051BC4): run it
 * with the screen centered (+56) in the global offset. Groups 0 and 4-7 keep that: screen-fixed sprites (group 7:
 * continue screen, menus); the scroll register writer below, which the vertical blank runs next, rewrites groups 1-3
 * (world sprites, layers) with the world shift.
 */
s32 wide_gscroll(s32 a, s32 b, s32 c, s32 d) {
    s32 r;
    s16 s = WIDE_ON ? HALF : 0;
    SCREEN_X -= s;
    r = ORIG_GSCROLL(a, b, c, d);
    SCREEN_X += s;
    return r;
}

/* the vertical blank's layer scroll register writer: run it with the world shift in the global offset */
s32 wide_scroll(s32 a, s32 b, s32 c, s32 d) {
    s32 r;
    s16 s = 0;
    if (WIDE_ON) {
        s = world_shift();
    }
    SHIFT_NOW = s;
    SCREEN_X -= s;
    r = ORIG_SCROLL(a, b, c, d);
    SCREEN_X += s;
    return r;
}

/* screen mode: 3 (normal) becomes 7 (wide) */
s32 wide_set_screen_mode(s32 mode, s32 b, s32 c, s32 d) {
    if (WIDE_ON && mode == 3) {
        mode = 7;
    }
    return ORIG_SET_MODE(mode, b, c, d);
}

/*
 * The SCREEN MODE item. The setting is byte 7 of the game settings (02059E1E: 7 settings and a spare byte), which
 * the game loads from its EEPROM image, copies into the menu working copy (02017A04), saves and resets with the
 * rest of the block, but never uses itself. Each language has its own hard-coded game settings page (a draw
 * routine, a step routine and a handler per item); the module replaces both routines (in the page tables), runs
 * the original draw (its label list: the module copy with the new item, from tools/build_warzard.py) and handlers,
 * and handles the new item itself, before EXIT (English) or return (Japanese). The cursor wraps one item later
 * (patched in the cursor movers).
 */
#define CFG_WIDE    (*(volatile u8*)G_CFG_WIDE)    /* the setting: menu working copy */
#define LIVE_WIDE   (*(volatile u8*)G_LIVE_WIDE)   /* ... in the settings in effect */
#define CUR_MODE    (*(volatile s32*)G_CUR_MODE)   /* the screen mode last set */
#define PAD_NOW     (*(volatile u16*)G_PAD_NOW)    /* player 1 inputs */
#define PAD_PREV    (*(volatile u16*)G_PAD_PREV)   /* ... the frame before */
#define SHOT1       0x10
#define SHOT2       0x20
#define UNCHANGED   2                              /* value colours: as in effect, changed */
#define CHANGED     8

typedef void (*void_fn)(void);
typedef s32 (*input_fn)(s32 mask, s32 slot);       /* a direction pressed (with repeat) */
typedef void (*print_fn)(s32 x, s32 y, s32 attr, u32 rec);
typedef void (*value_fn)(s32 color, u32 rec);      /* at the cursor item row */
typedef void (*arg_fn)(u32 arg);
typedef void (*copy_fn)(u32 dst, u32 src, s32 tiles);

static s32 wide_item_input(input_fn in) {
    u16 pressed;
    if (in(4, 2)) {
        return -1;
    }
    if (in(8, 3)) {
        return 1;
    }
    pressed = (u16)(~PAD_PREV & PAD_NOW);
    if (pressed & SHOT2) {
        return 1;
    }
    if (pressed & SHOT1) {
        return -1;
    }
    return 0;
}

static s32 wide_item_color(void) {
    return CFG_WIDE == LIVE_WIDE ? UNCHANGED : CHANGED;
}

/* English page: SCREEN MODE is item 7, EXIT item 8 */
#define EN_CURSOR   (*(volatile u8*)G_EN_CURSOR)
#define EN_HANDLERS ((const void_fn *)G_EN_HANDLERS)
#define EN_ITEM     7

static void wide_en_value(void) {
    ((value_fn)G_EN_VALUE)(wide_item_color(), G_EN_VALUES + 12 * (CFG_WIDE & 1));
}

void wide_en_draw(void) {
    ((void_fn)G_EN_DRAW)();
    EN_CURSOR = EN_ITEM;
    wide_en_value();
    EN_CURSOR = 0;
}

void wide_en_step(void) {
    s32 c;
    ((void_fn)G_EN_CURSOR_MOVE)();
    c = EN_CURSOR;
    if (c < EN_ITEM) {
        EN_HANDLERS[c]();
    } else if (c == EN_ITEM) {
        if (wide_item_input((input_fn)G_EN_INPUT)) {
            CFG_WIDE = (CFG_WIDE + 1) & 1;
            wide_en_value();
        }
    } else {
        EN_HANDLERS[EN_ITEM]();
    }
    ((arg_fn)G_EN_DRAW_CURSOR)(0x3E);
    ((print_fn)G_PRINT8)(0, 0, 0xFFFF, EN_CURSOR == EN_ITEM + 1 ? G_EN_HELP_EXIT : G_EN_HELP_CHANGE);
}

/* Japanese page: SCREEN MODE is item 6, return item 7 */
#define JP_CURSOR   (*(volatile u8*)G_JP_CURSOR)
#define JP_HANDLERS ((const void_fn *)G_JP_HANDLERS)
#define JP_ITEM     6

static void wide_jp_value(void) {
    ((value_fn)G_JP_VALUE)(wide_item_color(), G_JP_VALUES + 8 * (CFG_WIDE & 1));
}

void wide_jp_draw(void) {
    ((void_fn)G_JP_DRAW)();
    ((copy_fn)G_FONT_COPY)(G_WA_DST, G_WA_GLYPH, 4);   /* the font has no WA: the module adds it */
    JP_CURSOR = JP_ITEM;
    wide_jp_value();
    JP_CURSOR = 0;
}

void wide_jp_step(void) {
    s32 c;
    ((void_fn)G_JP_CURSOR_MOVE)();
    c = JP_CURSOR;
    if (c < JP_ITEM) {
        JP_HANDLERS[c]();
    } else if (c == JP_ITEM) {
        if (wide_item_input((input_fn)G_JP_INPUT)) {
            CFG_WIDE = (CFG_WIDE + 1) & 1;
            wide_jp_value();
        }
    } else {
        JP_HANDLERS[JP_ITEM]();
    }
    ((arg_fn)G_JP_DRAW_CURSOR)(G_JP_CURSOR_REC);
    ((print_fn)G_PRINT16)(0, 0, 0xFFFF, JP_CURSOR == JP_ITEM + 1 ? G_JP_HELP_EXIT : G_JP_HELP_CHANGE);
}

/*
 * The game applies its EEPROM image (at boot: after the screen mode is set; after a save): then the setting is
 * latched, and the screen mode set again when it changed.
 */
s32 wide_ee_apply(s32 img, s32 b, s32 c, s32 d) {
    s32 r = ((method)G_APPLY_BODY)(img, b, c, d);
    s32 on = LIVE_WIDE & 1;
    if (on != WIDE_ON) {
        WIDE_ON = on;
        if (CUR_MODE == 3 || CUR_MODE == 7) {
            wide_set_screen_mode(3, 0, 0, 0);
        }
    }
    return r;
}

/*
 * At the end of the task scheduler's first and second pass in a frame: the shadow to text RAM, both pages.
 * 4:3: as it is. Wide: each row's first 48 tiles 7 tiles right, the rest the row's clear tile (Warzard never
 * scrolls the text layer sideways).
 */
void wide_text_frame(void) {
    const u32 *src;
    volatile u32 *dst;
    s32 row, k;
    if (SCHED_PASS > 1) {
        return;
    }
    src = (const u32 *)SHADOW;
    dst = (volatile u32 *)TEXT_MAP;
    if (!WIDE_ON) {
        for (k = 0; k < MAP_ROWS * 64; k += 4) {
            dst[k] = src[k];
            dst[k + 1] = src[k + 1];
            dst[k + 2] = src[k + 2];
            dst[k + 3] = src[k + 3];
        }
        return;
    }
    for (row = 0; row < MAP_ROWS; row++) {
        u32 fill = src[FILL_COL];
        for (k = 0; k < SHIFT_TILES; k++) {
            dst[k] = fill;
        }
        for (k = 0; k < VIS_COLS; k++) {
            dst[k + SHIFT_TILES] = src[k];
        }
        for (k = VIS_COLS + SHIFT_TILES; k < 64; k++) {
            dst[k] = fill;
        }
        src += 64;
        dst += 64;
    }
}
