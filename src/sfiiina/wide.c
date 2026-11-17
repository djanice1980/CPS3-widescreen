/*
 * WIDE.C  Widescreen option for Street Fighter III New Generation (CPS3, sfiiina / Darksoft bank 0)
 *
 * New Generation keeps its whole wide mode (set_screen_mode(7) and every Game_setting.Screen_Mode test in
 * the fight, the HUD and the effects), the SCREEN MODE item routines (game_config_screen_item_en/_jp) and
 * the strings for them, but its GAME CONFIGURATION page no longer lists the item. This module is that page
 * again with the item restored as item 6, EXIT moving to 7:
 *
 *   1. GAME DIFFICULTY ... 5. EVENT   (the game's own items, unchanged)
 *   6. SCREEN MODE   NORMAL / WIDE    (game_config_screen_item_en, the game's own routine)
 *   7. EXIT
 *
 * It lives in its own sections (PWIDE / CWIDE at a free address), so every routine of the game stays where it
 * was; the game reaches it through a jump written over the start of game_config_main. No RAM of its own.
 */

#include "structs.h"
#include "work.h"
#include "romdata.h"
#include "extern.h"
#include "cps3.h"

#pragma section WIDE

#define ITEM_SCREEN 5
#define ITEM_EXIT   6
#define ITEM_LAST   6

/* the configuration pages' own work (game_config_en.c, game_config_jp.c) */
extern s8 Config_Item_en;
extern s8 Config_Exit_en;
extern s8 Config_New_en;
extern s16 Config_Attr_en;
extern s8 Config_Item_jp;
extern s8 Config_Exit_jp;
extern s8 Config_Move_jp;
extern s8 Config_New_jp;
extern s16 Config_Attr_jp;

/* the game's own routines and tables */
void game_config_init_en(void);
void game_config_level_item_en(void);
void game_config_damage_item_en(void);
void game_config_timer_item_en(void);
void game_config_1p_round_item_en(void);
void game_config_event_item_en(void);
void game_config_screen_item_en(void);
void game_config_exit_item_en(void);
s8 game_config_lever_repeat_en(u16 sw, s16 ix);
void game_config_draw_cursor_en(s16 code);
void game_config_print_value_en(s16 attr, const TM_STRING* str);
extern TM_STRING gcfg_screen_str_en[2];
extern const TM_STRING config_help_modify_str_tbl[];
extern const TM_STRING config_help_return_str_tbl[];
void tilemap_print_string();

void game_config_init_jp(void);
void game_config_level_item_jp(void);
void game_config_damage_item_jp(void);
void game_config_timer_item_jp(void);
void game_config_1p_round_item_jp(void);
void game_config_event_item_jp(void);
void game_config_exit_item_jp(void);
s8 game_config_lever_repeat_jp(u16 sw, s16 ix);
void game_config_print_value_jp(s16 attr, const TMSCRIPT* script);
void game_config_print_cursor_jp(const TMSCRIPT* script);
void tilemap_print_script_seq();
void set_screen_mode(s32 mode);
void screen_flip_offsets_set(void);
extern TMSCRIPT gcfg_screen_scr_jp[2];
extern TMSCRIPT gcfg_cursor_scr_jp[1];
extern TMSCRIPT gcfg_cursor_clr_scr_jp[1];
extern TMSCRIPT gcfg_guide_scr_jp[1];
extern TMSCRIPT gcfg_exit_guide_scr_jp[1];


/* English page: rows 14 and 16, SCREEN MODE where EXIT was, EXIT a row lower */
static const s8 wide_line_screen_en[] = "6. SCREEN MODE        \n";
/* the last line has no newline: tilemap_print_string takes one as "go on with the next TM_STRING" */
static const s8 wide_line_exit_en[] = "7. EXIT";
static const TM_STRING wide_lines_en[2] = {
    { 3, 14, 2, wide_line_screen_en },
    { 3, 16, 2, wide_line_exit_en },
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
        game_config_1p_round_item_en, game_config_event_item_en, game_config_screen_item_en,
        game_config_exit_item_en,
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


/*
 * Japanese page (Country 1). Rows are 2-glyph-high script lines (tilemap_print_script_seq, kind 1):
 * { glyph count, x, y, attr, glyph codes..., } ending with a 0 count; 0x1200 + 4n is glyph n of the menu font.
 * The game's own value scripts (gcfg_screen_scr_jp: "nomaru" / "waido") are used as they are.
 *
 *   6. "sukuriin" (screen)            row 12, over the old return line
 *   7. "settei menyu ni modoru"       row 14
 */
#define JP_BLANK 0x1200
static const u16 wide_lines_jp[] = {
    9, 4, 12, 2, 0x12B0, 0x1298, 0x1310, 0x13C8, 0x131C, JP_BLANK, JP_BLANK, JP_BLANK, JP_BLANK,
    9, 4, 14, 2, 0x133C, 0x1340, 0x1300, 0x12D4, 0x1308, 0x13C8, 0x125C, 0x1344, 0x1264,
    0, 0,
};
static const TMSCRIPT wide_lines_scr_jp[1] = { { 1, 0, wide_lines_jp } };

static void wide_print_screen_value_jp(void) {
    Config_Item_jp = ITEM_SCREEN;
    Config_New_jp = game_config_work.Screen_Mode & 1;
    Config_Attr_jp = (Config_New_jp != Game_setting.Screen_Mode) ? 8 : 2;
    game_config_print_value_jp(Config_Attr_jp, &gcfg_screen_scr_jp[Config_New_jp]);
}

static void wide_config_init_jp(void) {
    game_config_init_jp(); /* the page as the game draws it, cursor on item 1 */
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

/* as game_config_screen_item_jp, which prints on row 2 (the item's old place): this prints on the item's row */
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
        wide_print_screen_value_jp();
    }
}

static void wide_config_move_jp(void) {
    static void (* const page_tbl[ITEM_LAST + 1])(void) = {
        game_config_level_item_jp, game_config_damage_item_jp, game_config_timer_item_jp,
        game_config_1p_round_item_jp, game_config_event_item_jp, wide_config_screen_item_jp,
        game_config_exit_item_jp,
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
        return Config_Exit_jp ? 1 : 0;
    }
    if (Config_No_2 == 0) {
        wide_config_init_en(); /* game_config_init_en steps Config_No_2 */
    } else {
        wide_config_move_en();
    }
    return Config_Exit_en ? 1 : 0;
}
