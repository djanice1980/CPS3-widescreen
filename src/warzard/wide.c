/*
 * WIDE.C  Widescreen for Warzard (CPS3, Darksoft bank 1)
 *
 * There is no source for this game; everything here is reached through addresses found in the program
 * (tools/build_warzard.py lists them and builds the patch). In wide mode (screen mode 7, 496 pixels, the
 * 3rd Strike timing, which Warzard's window table already has) the 384-pixel picture is shown in the middle of the
 * wider screen:
 *
 *  - the text layer (the whole fight HUD, menus, messages): in wide mode the game's text code runs from a copy
 *    that draws into a RAM shadow of the tile map (tools/build_warzard.py makes the copies and the dispatchers
 *    that pick them); once a frame, in the vertical blank, the shadow goes to text RAM 7 tiles (56 px) further
 *    right, the margins filled with the tile the game cleared the row with. In 4:3 the game's own text code
 *    runs on the real text RAM and none of this does;
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
/* G_VARS + 8: the return address the memory check's print stubs keep (tools/build_warzard.py, PR_SAVE_OFFSET) */
#define TEXT_SEL    (*(volatile u32*)(G_VARS + 12)) /* which copy of the text code the dispatchers run: 0 = A,
                                                      the game's own on the real text RAM; 4 = B, into the
                                                      shadow (tools/build_warzard.py, TEXT_SEL_OFFSET) */

/* the game's */
#define LAYER0_X    (*(volatile s16*)G_LAYER0_X)   /* main layer x being published this frame (the camera) */
#define SCREEN_X    (*(volatile s16*)G_SCREEN_X)   /* global x offset, added to every layer and sprite scroll */
#define STAGE       (*(volatile u8*)G_STAGE)
#define CAM_LIMITS  ((const s16*)G_CAM_LIMITS)     /* per stage: camera x min, max */
#define STAGES      10

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
static void text_copy(void);
#define ORIG_CAMERA ((method)G_CAMERA)
#define ORIG_SCROLL ((method)G_SCROLL)
#define ORIG_SET_MODE ((method)G_SET_MODE)
#define ORIG_GSCROLL ((method)G_GSCROLL)

/* the fight camera's step (stages 0 to 7): run it, note that the camera is live */
s32 wide_camera(s32 a, s32 b, s32 c, s32 d) {
    s32 r = ORIG_CAMERA(a, b, c, d);
    CAM_LIVE = 4;
    return r;
}

/*
 * The fight scene's call that places the layers each frame. Stages 8 and 9 do not use the camera step above, so
 * without this their view was never held at the stage's ends: it stayed centered on the 384-pixel view and ran
 * 56 pixels past each end. Title, menus and the other scenes place their layers through other calls.
 */
#define ORIG_SET_LAYER ((method)G_SET_LAYER)
s32 wide_set_layer(s32 layer, s32 x, s32 y, s32 d) {
    if (layer == 0) {
        CAM_LIVE = 4;
    }
    return ORIG_SET_LAYER(layer, x, y, d);
}

/*
 * Stage 9 (the bonus stage with the statue) is the one stage whose camera never reaches the limits in the table:
 * with two fighters forced onto it in MAME it stopped at 224 and 530, where the table says 64 and 576. Its main
 * layer's artwork ends at x = 942, short of the 960 that the table's right limit stands for, and past that the
 * tile map wraps round to the stage's left end: at the camera's right stop the wide view showed a 27-pixel slice
 * of the left wall on the right edge of the screen. So the view stops where the artwork does.
 */
#define BONUS_STAGE     9
#define BONUS_VIEW_MAX  440     /* view's right edge at 936 */

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
    if (st == BONUS_STAGE && hi > BONUS_VIEW_MAX) {
        hi = BONUS_VIEW_MAX;
    }
    view = cam - HALF;
    if (hi >= lo) {
        if (view < lo) {
            view = lo;
        }
        if (view > hi) {
            view = hi;
        }
    }
    /* a scene can hold the camera outside its fight limits: the 384-pixel view stays on the screen whatever it does */
    view = cam - view;
    if (view < 0) {
        view = 0;
    }
    if (view > 2 * HALF) {
        view = 2 * HALF;
    }
    return view;
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

/*
 * Background layers that never scroll, per stage (bit n: layer n; layer 0 is the main one, the camera). Their x was
 * the same at both ends of every stage (MAME, both players walked to each end). Such a backdrop is drawn for the
 * 384-pixel view only: on stage 2 (the ice stage) the sky is one 512-pixel page shown from its column 64, so it has
 * 64 spare pixels a side. Slid by the world shift like the floor (0 at the left end of a stage, 112 at the right
 * end) it ran out of picture, a black block up to 48 pixels wide at the far edge of the screen. A backdrop that does
 * not move with the camera must not move with the world shift either: it gets the centered 56.
 */
static const u8 still_layers[STAGES] = {
    0x00, 0x00, 0x04, 0x00, 0x04, 0x06, 0x04, 0x04, 0x00, 0x04,
};
#define LAYER_X(n)  (*(volatile s16*)(G_LAYER0_X + 16 * (n)))  /* x the scroll writer is about to publish */

/* the vertical blank's layer scroll register writer: run it with the world shift in the global offset */
s32 wide_scroll(s32 a, s32 b, s32 c, s32 d) {
    s32 r;
    s16 s = 0;
    if (WIDE_ON) {
        s = world_shift();
        if (s != HALF && STAGE < STAGES) {
            /* the writer adds the global offset to every layer: take the difference out of the still ones. It
               latches each layer's next x over this one as it goes, so there is nothing to put back. */
            u8 still = still_layers[STAGE];
            if (still & 2) {
                LAYER_X(1) += s - HALF;
            }
            if (still & 4) {
                LAYER_X(2) += s - HALF;
            }
        }
    }
    SHIFT_NOW = s;
    SCREEN_X -= s;
    r = ORIG_SCROLL(a, b, c, d);
    SCREEN_X += s;
    if (WIDE_ON) {
        text_copy(); /* once a frame, in the vertical blank: what the frame's tasks drew goes on the screen */
    }
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
        volatile u32 *text = (volatile u32 *)TEXT_MAP;
        u32 *shadow = (u32 *)SHADOW;
        s32 row, k;
        if (on) {
            /* what is on the screen now was drawn straight into text RAM: it becomes the shadow's content */
            for (k = 0; k < MAP_ROWS * 64; k++) {
                shadow[k] = text[k];
            }
        } else {
            /* back to 4:3: the shadow's 48 columns where the game draws them, the rest the row's clear tile */
            for (row = 0; row < MAP_ROWS; row++) {
                u32 fill = shadow[FILL_COL];
                for (k = 0; k < VIS_COLS; k++) {
                    text[k] = shadow[k];
                }
                for (; k < 64; k++) {
                    text[k] = fill;
                }
                shadow += 64;
                text += 64;
            }
        }
        WIDE_ON = on;
        TEXT_SEL = on ? 4 : 0;
        if (CUR_MODE == 3 || CUR_MODE == 7) {
            wide_set_screen_mode(3, 0, 0, 0);
        }
    }
    return r;
}

/*
 * Wide mode only: the shadow to text RAM, both pages. Each row's first 48 tiles go 7 tiles right, the rest is the
 * row's clear tile (Warzard never scrolls the text layer sideways). In 4:3 there is no shadow: the dispatchers of
 * tools/build_warzard.py run the game's own text code on the real text RAM, and nothing here runs.
 */
static void text_copy(void) {
    const u32 *src = (const u32 *)SHADOW;
    volatile u32 *dst = (volatile u32 *)TEXT_MAP;
    s32 row, k;
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

/* after a print of the test menu memory check (tools/build_warzard.py, MEM_PRINTS): no vertical blank is
   served while a check runs with interrupts masked, so in wide mode each line is put on the screen as it is
   printed. In 4:3 the print went straight to text RAM. */
void wide_text_flush(void) {
    if (WIDE_ON) {
        text_copy();
    }
}
