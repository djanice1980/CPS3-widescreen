/*
 * WIDE.C  Widescreen for JoJo's Bizarre Adventure: Heritage for the Future (CPS3, Darksoft bank 4)
 *
 * There is no source for this game; everything here is reached through addresses found in the program
 * (tools/build_jojoba.py lists them and builds the patch). In wide mode (screen mode 7, 496 pixels, the
 * 3rd Strike timing) the 384-pixel picture is shown in the middle of the wider screen:
 *
 *  - the text layer (the whole fight HUD, menus, messages): the game's text routines run from copies that
 *    write a RAM shadow of the tile map instead of text RAM (build_jojoba.py makes the copies and the
 *    dispatchers that pick them); once a frame, after the game's tasks have run, the visible rows are copied to
 *    text RAM 7 tiles (56 px) further right, and every tile 4:3 would not show (the text layer is a 512-pixel
 *    ring: sliding messages wait in its hidden part) is left blank, so nothing appears in the side margins;
 *  - sprites and background layers move together through the game's own global X offset (0205DDBE, the one
 *    its screen shake uses): +56 outside fights; in a fight the view follows the camera but stops at the
 *    stage edges, so the extra width shows real stage instead of whatever lies past the stage's end.
 *
 * Fights play exactly as in 4:3 (camera, limits and collisions are untouched); only what is drawn moves.
 * Wide mode is the SCREEN MODE item added to the service menu's game settings, read once at each boot.
 */

typedef signed char s8;
typedef unsigned char u8;
typedef short s16;
typedef unsigned short u16;
typedef long s32;
typedef unsigned long u32;

#include "game.h"  /* the game's addresses (G_*), written by tools/build_jojoba.py */

#pragma section WIDE

/*
 * The module's RAM: 0207C000-0207C01F, after the text shadow (02074000, 16 KB) and the 16 KB behind it that text
 * past the map's last row can reach. Neither game has a pointer into 02071510-0207EFFF (both programs scanned).
 * NOT 0207F000: the Darksoft versions of the games read their region byte from 0207F000 and their no-CD flag from
 * 0207F004 at boot (the Darksoft BIOS puts them there), so nothing of ours may be written near them.
 * Nothing is assumed about this RAM at power-on: wide mode is on only while WIDE_FLAG holds WIDE_MARK (the
 * dispatchers of tools/build_jojoba.py test the same value), and wide_boot_load sets everything else.
 */
#define WIDE_FLAG   (*(volatile u8*)0x0207C000)  /* WIDE_MARK: wide mode in effect (the SCREEN MODE setting at boot) */
#define WIDE_MARK   0x5A
#define WIDE_ON     (WIDE_FLAG == WIDE_MARK)
#define CAM_LIVE    (*(volatile u8*)0x0207C001)  /* frames the fight camera counts as running */
#define CAM_POS     (*(volatile u8*)0x0207C002)  /* next slot in CAM_HIST */
#define CAM_LAG     0                            /* camera frames between the camera and the picture */
#define SHIFT_NOW   (*(volatile s16*)0x0207C004) /* the world shift used this frame (for tests) */
#define TEXT_DIRTY  (*(volatile u8*)0x0207C008)  /* the shadow was drawn into (copy B's dispatchers set it too) */
#define CAM_HIST    ((volatile s16*)0x0207C010)  /* camera x, last 4 camera frames */

/* the game's */
#define CAMERA_X    (*(volatile s16*)G_CAMERA_X) /* camera x (16.16, integer part): left edge of the view */
#define STAGE_NO    (*(volatile u8*)G_STAGE_NO)
#define CAM_LIMITS  ((const s32*)G_CAM_LIMITS)    /* per stage: camera x min, max (16.16) */
#define SCROLL_OFS  (*(volatile s16*)G_SCROLL_OFS) /* global X offset for sprites and BG layers */
#define SCHED_PASS  (*(volatile s32*)G_SCHED_PASS) /* task scheduler: passes over the tasks this frame (0 = first) */

#define TEXT_MAP    0x25040000                   /* text RAM tile map: 64 rows of 64 tiles, 4 bytes each */
#define ROWSCROLL   ((volatile u16*)0x25044000)  /* per line: 2 halfwords, the scroll is the first's low byte */
#define SHADOW      0x02074000                   /* RAM copy of the tile map the game draws into in wide mode */
#define ROWS        28                           /* rows on screen (224 lines; vertical scroll is fixed) */
#define BLANK       0x00200000                   /* the tile the game clears the map with */
#define SHIFT_TILES 7
#define HALF        56                           /* (496 - 384) / 2 */

typedef s32 (*method)(s32, s32, s32, s32);
#define ORIG_CAMERA         ((method)G_CAMERA)
#define ORIG_SCROLL_PUBLISH ((method)G_SCROLL_PUBLISH)
#define ORIG_SCROLL_RESET   ((method)G_SCROLL_RESET)
#define ORIG_SET_MODE       ((method)G_SET_MODE)

/* camera task method: run it, then keep its x */
s32 wide_camera(s32 a, s32 b, s32 c, s32 d) {
    s32 r = ORIG_CAMERA(a, b, c, d);
    CAM_HIST[CAM_POS & 3] = CAMERA_X;
    CAM_POS++;
    CAM_LIVE = 4;
    return r;
}

/* how far right sprites and background are drawn */
static s16 world_shift(void) {
    s32 cam, lo, hi, view;
    if (CAM_LIVE == 0) {
        return HALF;
    }
    CAM_LIVE--;
    cam = CAM_HIST[(u8)(CAM_POS - 1 - CAM_LAG) & 3];
    lo = CAM_LIMITS[STAGE_NO * 2] >> 16;
    hi = (CAM_LIMITS[STAGE_NO * 2 + 1] >> 16) - 2 * HALF;
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

static void shift_world(void) {
    s16 s = 0;
    if (WIDE_ON) {
        s = world_shift();
        SCROLL_OFS -= s;
    }
    SHIFT_NOW = s;
}

/* the screen control task's per-frame step (sets the global offset from the shake offset) */
s32 wide_scroll_publish(s32 a, s32 b, s32 c, s32 d) {
    s32 r = ORIG_SCROLL_PUBLISH(a, b, c, d);
    shift_world();
    return r;
}

/* ... and its reset */
s32 wide_scroll_reset(s32 a, s32 b, s32 c, s32 d) {
    s32 r = ORIG_SCROLL_RESET(a, b, c, d);
    shift_world();
    return r;
}

/* (no apostrophes in this block: SHC 5.0 lexes skipped #if blocks and an odd quote breaks the file) */
#if G_HAS_MENU
/*
 * The SCREEN MODE item of the service menu game settings (build_jojoba.py adds it to the menu tables as item id
 * 7, before EXIT). The setting is byte 0x15 of the game settings block, which the game saves to EEPROM, loads,
 * snapshots and resets to its defaults (0) with the rest of the block but never uses itself. The game plays from
 * its EEPROM image (0205C05C: system, game settings, signature, then a second copy); the service menu edits a
 * working copy (0205C02C) and writes it back with "save".
 */
#define REGION      (*(volatile s32*)G_REGION)   /* 0, 1: Japanese menus */
#define CFG_WIDE    (*(volatile u8*)G_CFG_WIDE)  /* game settings + 0x15: the working copy of the menu */
#define CFG_SNAP    (*(volatile u8*)G_CFG_SNAP)  /* ... as it was when the menu opened (changed values show red) */
#define EE_WIDE     (*(volatile u8*)G_EE_WIDE)   /* ... in the EEPROM image the game runs from (0205C05C + 0x16) */
#define RED         4
#define OWN_COLOR   0xFFFF                       /* use the colour of the record */

/* English text record: position, colour, string (a newline at its end: the next record follows) */
struct en_rec {
    u16 x, y, attr, pad;
    const char *s;
};
typedef void (*print_fn)(s32 x, s32 y, s32 color, const void *rec);
#define PRINT_EN    ((print_fn)G_PRINT_EN)       /* records, offset by x, y */
#define PRINT_JP    ((print_fn)G_PRINT_JP)       /* halfword streams: x, y, colour, glyphs, 0 */
#define EN_ROW      0x13

const struct en_rec wide_en_labels[2] = {
    {3, EN_ROW, 1, 0, "8. SCREEN MODE\n"},
    {3, EN_ROW + 2, 1, 0, "9. EXIT"},
};
static const struct en_rec en_values[2] = {
    {0, 0, 1, 0, "NORMAL"},
    {0, 0, 1, 0, "WIDE  "},
};
/* the Japanese menu font: katakana codes (no kanji beyond those of each screen), 0001 is a blank */
static const u16 jp_normal[] = {0x16, 0x0A, 1, 0xA5, 0x29, 0xB5, 0xBF, 0};   /* NORMAL (as for EVENT) */
static const u16 jp_wide[] = {0x16, 0x0A, 1, 0xC2, 0x7F, 0xA0, 0x01, 0};     /* WIDE */

void wide_cfg_draw(void) {
    s32 v = CFG_WIDE & 1;
    s32 color = CFG_WIDE == CFG_SNAP ? OWN_COLOR : RED;
    if (REGION == 0 || REGION == 1) {
        PRINT_JP(0, 0, color, v ? jp_wide : jp_normal);
    } else {
        PRINT_EN(0x19, EN_ROW, color, &en_values[v]);
    }
}

/* left, right, shot 1 or shot 2 on the item */
void wide_cfg_change(s32 dir) {
    CFG_WIDE = (CFG_WIDE + 1) & 1;
    wide_cfg_draw();
}

/* boot (also after the service menu): the game reads EEPROM, then the screen mode is fixed until the next boot */
s32 wide_boot_load(s32 a, s32 b, s32 c, s32 d) {
    s32 r = ((method)G_EE_LOAD)(a, b, c, d);
    CAM_LIVE = 0;
    CAM_POS = 0;
    TEXT_DIRTY = 1;
    WIDE_FLAG = (EE_WIDE & 1) ? WIDE_MARK : 0;
    return r;
}

#endif

/* screen mode: 3 (normal) becomes 7 (wide) */
s32 wide_set_screen_mode(s32 mode, s32 b, s32 c, s32 d) {
    if (WIDE_ON && mode == 3) {
        mode = 7;
    }
    return ORIG_SET_MODE(mode, b, c, d);
}

/* text RAM plane base (the method at 061BE760): plane 0 is the tile map */
s32 wide_ss_base(s32 task, s32 plane) {
    if (plane == 1) {
        return 0x25044000;
    }
    if (plane == 2) {
        return 0x25048000;
    }
    if (WIDE_ON) {
        TEXT_DIRTY = 1;
        return SHADOW;
    }
    return TEXT_MAP;
}

/*
 * At the end of the task scheduler's first pass in a frame (all tasks have run), and after any later pass that drew
 * text (some screens' tasks draw late in the frame): the shadow to text RAM.
 * A line drawn with row scroll r shows tile column c at x = 8c - r (mod 512); in 4:3 the columns from r/8 to
 * (r+383)/8 are (at least partly) on screen. Those go 7 columns right; the rest are blanked. A row takes the
 * columns any of its 8 lines shows.
 */
void wide_text_frame(void) {
    const u32 *src;
    volatile u32 *dst;
    volatile u16 *rs;
    s32 row, i, r, rmin, rmax, c, n, k;
    if (!WIDE_ON || (SCHED_PASS != 0 && !TEXT_DIRTY)) {
        return;
    }
    TEXT_DIRTY = 0;
    src = (const u32 *)SHADOW;
    dst = (volatile u32 *)TEXT_MAP;
    for (row = 0; row < ROWS; row++) {
        rmin = 255;
        rmax = 0;
        for (i = 0; i < 8; i++) {
            /* line 8*row+i uses the scroll entry of the line before */
            rs = ROWSCROLL + (((row * 8 + i - 1) & 0x1FF) << 1);
            r = *rs & 0xFF;
            if (r < rmin) {
                rmin = r;
            }
            if (r > rmax) {
                rmax = r;
            }
        }
        c = rmin >> 3;
        n = ((rmax + 383) >> 3) - c + 1;
        if (n > 64) {
            n = 64;
        }
        for (k = 0; k < n; k++) {
            dst[(c + SHIFT_TILES) & 63] = src[c];
            c = (c + 1) & 63;
        }
        for (; k < 64; k++) {
            dst[(c + SHIFT_TILES) & 63] = BLANK;
            c = (c + 1) & 63;
        }
        src += 64;
        dst += 64;
    }
}
