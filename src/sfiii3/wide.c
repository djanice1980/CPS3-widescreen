/*
 * WIDE.C  Widescreen option for Street Fighter III 3rd Strike (CPS3, sfiii3nr1)
 *
 * The game still has the board's 496-pixel wide mode (set_screen_mode(7), display_mode_setup and the HUD's
 * wide positions, all keyed on Game_setting.Screen_Mode) and an English SCREEN MODE item for its configuration
 * page (game_config_screen_item_en), but the page's item table no longer lists it. This module is the English
 * GAME CONFIGURATION page again with that item restored as item 8, EXIT moving to 9:
 *
 *   1. GAME DIFFICULTY ... 7. BONUS GAME   (the game's own items, unchanged)
 *   8. SCREEN MODE        NORMAL / WIDE    (game_config_screen_item_en, the game's own routine)
 *   9. EXIT
 *
 * It lives in its own section (PWIDE / CWIDE at a free address), so every routine of the game stays where it
 * was. The game reaches it through a jump written over the start of game_config_menu_en (tools/hooks).
 * No RAM of its own: it uses the configuration page's own work variables.
 */

#include "types.h"
#include "structs.h"
#include "work.h"
#include "romdata.h"
#include "cps3.h"

#pragma section WIDE

#define ITEM_SCREEN 7
#define ITEM_EXIT   8
#define ITEM_LAST   8

/* the configuration page's own work (game_config_en.c) */
extern s8 Config_Item_en;
extern s8 Config_Exit_en;
extern s8 Config_New_en;
extern s16 Config_Attr_en;

/* the game's own routines (game_config_en.c, textsound.c) */
void game_config_init_en(void);
void game_config_level_item_en(void);
void game_config_damage_item_en(void);
void game_config_timer_item_en(void);
void game_config_1p_round_item_en(void);
void game_config_2p_round_item_en(void);
void game_config_event_item_en(void);
void game_config_bonus_item_en(void);
void game_config_screen_item_en(void);
void game_config_exit_item_en(void);
s8 game_config_lever_repeat_en(u16 sw, s16 ix);
void game_config_draw_cursor_en(s16 code);
void game_config_print_value_en(s16 attr, const TM_STRING* str);
void tilemap_print_string(u16 x, u16 y, u16 attr, const TM_STRING* sc);

static const s8 wide_line_screen_en[] = "8. SCREEN MODE       NORMAL  \n";
static const s8 wide_line_exit_en[] = "9. EXIT                     ";

/* rows 18 and 20: SCREEN MODE where EXIT was, EXIT a row lower */
static const TM_STRING wide_lines_en[2] = {
    { 5, 18, 2, wide_line_screen_en },
    { 5, 20, 2, wide_line_exit_en },
};

static void wide_config_init_en(void) {
    game_config_init_en(); /* the page as the game draws it, cursor on item 1 */
    tilemap_print_string(0, 0, 0xFFFF, wide_lines_en);
    Config_Item_en = ITEM_SCREEN;
    game_config_work.Screen_Mode &= 1;
    Config_New_en = game_config_work.Screen_Mode;
    Config_Attr_en = (Config_New_en != Game_setting.Screen_Mode) ? 8 : 2;
    game_config_print_value_en(Config_Attr_en, &gcfg_screen_str_en[Config_New_en]);
    Config_Item_en = 0;
}

static void wide_config_cursor_move_en(void) {
    game_config_draw_cursor_en(32);
    if (game_config_lever_repeat_en(1, 0)) {
        Config_Item_en--;
        if (Config_Item_en < 0) {
            Config_Item_en = ITEM_LAST;
        }
    } else if (game_config_lever_repeat_en(2, 1)) {
        Config_Item_en++;
        if (Config_Item_en > ITEM_LAST) {
            Config_Item_en = 0;
        }
    }
}

static void wide_config_move_en(void) {
    static void (* const page_tbl[ITEM_LAST + 1])(void) = {
        game_config_level_item_en, game_config_damage_item_en, game_config_timer_item_en,
        game_config_1p_round_item_en, game_config_2p_round_item_en, game_config_event_item_en,
        game_config_bonus_item_en, game_config_screen_item_en, game_config_exit_item_en,
    };
    wide_config_cursor_move_en();
    page_tbl[Config_Item_en]();
    game_config_draw_cursor_en(62);
    if (Config_Item_en == ITEM_EXIT) {
        tilemap_print_string(0, 0, 0xFFFF, config_help_return_str_tbl);
    } else {
        tilemap_print_string(0, 0, 0xFFFF, config_help_modify_str_tbl);
    }
}

/* replaces game_config_menu_en (hooked at its entry) */
s32 wide_game_config_menu_en(void) {
    if (Config_No_2 == 0) {
        wide_config_init_en(); /* game_config_init_en steps Config_No_2 */
    } else {
        wide_config_move_en();
    }
    if (Config_Exit_en) {
        return 1;
    }
    return 0;
}


/*
 * The Japanese page (Country 1). Its rows are 2-glyph-high script lines (tilemap_print_script_seq, kind 1):
 * { glyph count, x, y, attr, glyph codes..., } ending with a 0 count. A glyph code 0x1200 + 4n is glyph n of
 * jp_menu_font_cg, 2 x 2 tiles. 3rd Strike's font has no "wa" any more (its slot became "na", so the game's own
 * gcfg_screen_scr_jp_1 now reads "naido"): wide_config_init_jp makes one in glyph slot 120, past the end of the
 * font (jp_menu_font_cg is 118 glyphs), from the font's "u" without its top stroke.
 *
 *   8. "sukuriin" (screen)   "nomaru" (normal) / "waido" (wide)
 *   9. "settei menyu ni modoru" (back to settings)
 */
extern s8 Config_Item_jp;
extern s8 Config_Exit_jp;
extern s8 Config_Move_jp;
extern s8 Config_New_jp;
extern s16 Config_Attr_jp;
extern u8 Country;
extern const u8 jp_menu_font_cg[];

void game_config_init_jp(void);
void game_config_level_item_jp(void);
void game_config_damage_item_jp(void);
void game_config_timer_item_jp(void);
void game_config_1p_round_item_jp(void);
void game_config_2p_round_item_jp(void);
void game_config_event_item_jp(void);
void game_config_bonus_item_jp(void);
void game_config_exit_item_jp(void);
s8 game_config_lever_repeat_jp(u16 sw, s16 ix);
void game_config_print_value_jp(s16 attr, const TMSCRIPT* script);
void game_config_print_cursor_jp(const TMSCRIPT* script);
void tilemap_print_script_seq(u16 pos_x, u16 y, u16 pal, const TMSCRIPT* scr);
void set_screen_mode(s32 mode);
void screen_flip_offsets_set(void);
extern TMSCRIPT gcfg_cursor_scr_jp[1];
extern TMSCRIPT gcfg_cursor_clr_scr_jp[1];
extern TMSCRIPT gcfg_guide_scr_jp[1];
extern TMSCRIPT gcfg_exit_guide_scr_jp[1];
extern const u16 gcfg_screen_scr_jp_0[]; /* "nomaru" (normal) */

#define JP_GLYPH(n)     (0x1200 + 4 * (n))
#define JP_BLANK        JP_GLYPH(0)
#define JP_U            36          /* "u" */
#define JP_WA           120         /* our "wa" */
#define SS_FONT         (SS_RAM + 0x8000)
#define TILE_BYTES      32

/* row 16: "sukuriin" (screen) over the old return line; row 18: the return line, a row lower */
static const u16 wide_lines_jp[] = {
    9, 4, 16, 2, 0x12B0, 0x1298, 0x1310, 0x13C8, 0x131C, JP_BLANK, JP_BLANK, JP_BLANK, JP_BLANK,
    9, 4, 18, 2, 0x133C, 0x1340, 0x1300, 0x12D4, 0x1308, 0x13C8, 0x125C, 0x1344, 0x1264,
    0, 0,
};
static const TMSCRIPT wide_lines_scr_jp[1] = { { 1, 0, wide_lines_jp } };

/* "waido" (wide), padded to "nomaru" (normal)'s four glyphs */
static const u16 wide_wide_jp[] = {
    4, 0, 0, 2, JP_GLYPH(JP_WA), 0x1288, 0x12D0, JP_BLANK,
    0,
};
static const TMSCRIPT wide_screen_scr_jp[2] = {
    { 1, 0, gcfg_screen_scr_jp_0 },
    { 1, 0, wide_wide_jp },
};

/* "wa": the font's "u" (glyph 36) into glyph slot 120, its top rows 1-3 (the short stroke) left blank */
static void wide_make_wa_glyph(void) {
    /* as tilemap_chunk_copy_16b loads the font: each byte of a tile into a halfword of SS RAM */
    const s8* src = (const s8*)(jp_menu_font_cg + JP_U * 4 * TILE_BYTES);
    volatile s16* dst = (volatile s16*)(SS_FONT + JP_WA * 4 * TILE_BYTES * 2);
    s32 i;
    for (i = 0; i < 4 * TILE_BYTES; i++) {
        s32 tile = i / TILE_BYTES;
        s32 row = (i % TILE_BYTES) / 4; /* 8 pixels of 4 bits: 4 bytes a row */
        dst[i] = (tile < 2 && row >= 1 && row <= 3) ? 0 : src[i];
    }
}

static void wide_print_screen_value_jp(void) {
    Config_Item_jp = ITEM_SCREEN;
    Config_New_jp = game_config_work.Screen_Mode & 1;
    Config_Attr_jp = (Config_New_jp != Game_setting.Screen_Mode) ? 8 : 2;
    game_config_print_value_jp(Config_Attr_jp, &wide_screen_scr_jp[Config_New_jp]);
}

static void wide_config_init_jp(void) {
    game_config_init_jp(); /* the page as the game draws it, cursor on item 1 */
    wide_make_wa_glyph();
    tilemap_print_script_seq(0, 0, 0xFFFF, wide_lines_scr_jp);
    game_config_work.Screen_Mode &= 1;
    wide_print_screen_value_jp();
    Config_Item_jp = 0;
    game_config_print_cursor_jp(gcfg_cursor_scr_jp);
}

static void wide_config_cursor_move_jp(void) {
    game_config_print_cursor_jp(gcfg_cursor_clr_scr_jp);
    if (game_config_lever_repeat_jp(1, 0)) {
        Config_Item_jp--;
        if (Config_Item_jp < 0) {
            Config_Item_jp = ITEM_LAST;
        }
    }
    if (game_config_lever_repeat_jp(2, 1)) {
        Config_Item_jp++;
        if (Config_Item_jp > ITEM_LAST) {
            Config_Item_jp = 0;
        }
    }
}

/* as game_config_screen_item_jp, which prints on the first row: this prints on its own */
static void wide_config_screen_item_jp(void) {
    Config_Move_jp = 0;
    if (game_config_lever_repeat_jp(4, 2)) {
        Config_Move_jp = -1;
    } else if (game_config_lever_repeat_jp(8, 3)) {
        Config_Move_jp = 1;
    } else {
        if ((p1sw_0 & ~p1sw_1) & BUTTON_LP) {
            Config_Move_jp = -1;
        }
        if ((p1sw_0 & ~p1sw_1) & BUTTON_MP) {
            Config_Move_jp = 1;
        }
    }
    if (Config_Move_jp) {
        game_config_work.Screen_Mode += Config_Move_jp;
        game_config_work.Screen_Mode &= 1;
        set_screen_mode(game_config_work.Screen_Mode ? 7 : 3);
        screen_flip_offsets_set();
        wide_print_screen_value_jp();
    }
}

static void wide_config_move_jp(void) {
    static void (* const page_tbl[ITEM_LAST + 1])(void) = {
        game_config_level_item_jp, game_config_damage_item_jp, game_config_timer_item_jp,
        game_config_1p_round_item_jp, game_config_2p_round_item_jp, game_config_event_item_jp,
        game_config_bonus_item_jp, wide_config_screen_item_jp, game_config_exit_item_jp,
    };
    wide_config_cursor_move_jp();
    page_tbl[Config_Item_jp]();
    game_config_print_cursor_jp(gcfg_cursor_scr_jp);
    if (Config_Item_jp == ITEM_EXIT) {
        tilemap_print_script_seq(0, 0, 0xFFFF, gcfg_exit_guide_scr_jp);
    } else {
        tilemap_print_script_seq(0, 0, 0xFFFF, gcfg_guide_scr_jp);
    }
}

/* replaces game_config_main (hooked at its entry): the configuration page of the test menu */
s8 wide_game_config_main(void) {
    if (Country == 1) {
        if (Config_No_2 == 0) {
            wide_config_init_jp(); /* game_config_init_jp steps Config_No_2 */
        } else {
            wide_config_move_jp();
        }
        if (Config_Exit_jp) {
            return 1;
        }
        return 0;
    }
    if (wide_game_config_menu_en()) {
        return 1;
    }
    return 0;
}
