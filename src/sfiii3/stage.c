/*
 * stage.c  the savanna stage's backdrop in the wide screen mode
 *
 * bg_x_move_check places a background layer that follows the main one: its x is the main layer's distance from
 * the stage's middle times the layer's speed. The savanna stage (background 8) has a backdrop, layer 0, that
 * moves a sixteenth as fast as the floor and is one 512-pixel page wide (x 256 to 767). The 384-pixel view never
 * reaches its ends, but the 496-pixel view does at the left end of the stage: the backdrop's x goes down to 500,
 * the view's left edge to 252, and four columns with no artwork show as a black strip. A scroll limit cannot
 * hide that (the main layer would have to stop 64 pixels early), so here the backdrop itself stops at x = 504,
 * where its artwork begins at the view's left edge. It then stands still for the last 64 pixels of the main
 * layer's travel instead of moving another 4.
 *
 * This is the game's own routine with that one test added, and the test is false in the normal screen mode.
 */

#include "types.h"
#include "structs.h"
#include "work.h"
#include "cps3.h"

#pragma section WIDE

#define SAVANNA_BG      8
#define BACKDROP_MIN_X  504     /* 256 (the page's first column) + 248 (half the wide view) */

void wide_bg_x_move_check(void) {
    if (bg_w.chase_flag & 0xF) {
        bgw_ptr->old_pos_x = bgw_ptr->chase_xy[0].disp.pos;
    } else {
        bgw_ptr->old_pos_x = bgw_ptr->wxy[0].disp.pos;
    }
    if (bg_w.chase_flag & 0xF) {
        bgw_ptr->chase_xy[0].cal = bgw_ptr->speed_x * bg_w.bg2_sp_x2;
        bgw_ptr->chase_xy[0].disp.pos += bgw_ptr->pos_x_work;
        if (Game_setting.Screen_Mode && bg_w.bg_index == SAVANNA_BG && bgw_ptr == &bg_w.bgw[0]
            && bgw_ptr->chase_xy[0].disp.pos < BACKDROP_MIN_X) {
            bgw_ptr->chase_xy[0].disp.pos = BACKDROP_MIN_X;
            bgw_ptr->chase_xy[0].disp.low = 0;
        }
    } else {
        bgw_ptr->wxy[0].cal = bgw_ptr->xy[0].cal = bgw_ptr->speed_x * bg_w.bg2_sp_x2;
        bgw_ptr->xy[0].disp.pos += bgw_ptr->pos_x_work;
        if (Game_setting.Screen_Mode && bg_w.bg_index == SAVANNA_BG && bgw_ptr == &bg_w.bgw[0]
            && bgw_ptr->xy[0].disp.pos < BACKDROP_MIN_X) {
            bgw_ptr->xy[0].disp.pos = BACKDROP_MIN_X;
            bgw_ptr->xy[0].disp.low = 0;
            bgw_ptr->wxy[0].disp.low = 0;
        }
        bgw_ptr->wxy[0].disp.pos = bgw_ptr->xy[0].disp.pos;
    }
    if (!(bg_w.chase_flag & 0xF)) {
        bgw_ptr->chase_xy[0].disp.pos = bgw_ptr->wxy[0].disp.pos;
    }
}
