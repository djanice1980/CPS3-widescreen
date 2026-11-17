/*
 * mode.c  display_mode_setup for the widescreen patch
 *
 * The game's own routine, but with full vitality kept at 160 in the wide screen mode too. 3rd Strike's
 * unfinished wide mode sets Max_vitality to 192, while the vitality bars (VITAL.C) are still drawn for 160:
 * vital_control does nothing while vital_new is over 160, so a fighter's bar would not move until a sixth of
 * the life was gone. Damage is scaled by Max_vitality, so 160 also keeps the fights exactly as in 4:3.
 */

#include "types.h"
#include "structs.h"
#include "work.h"
#include "cps3.h"
#include "Com_Pl.h"

extern s16 DE_X[19];
extern s16 Max_vitality;

#pragma section WIDE

void wide_display_mode_setup(void) {
    if (Game_setting.Screen_Mode) {
        set_screen_mode(7);
        screen_flip_offsets_set();
        DE_X[0] = 8;
        DE_X[1] = 16;
        DE_X[2] = 6;
        DE_X[3] = 7;
        DE_X[4] = 9;
        DE_X[5] = 112;
        DE_X[6] = 4;
        DE_X[7] = 11;
        DE_X[8] = 2;
        DE_X[9] = 12;
        DE_X[10] = 56;
        DE_X[11] = 0x100;
        DE_X[12] = 13;
        DE_X[13] = 1;
        DE_X[14] = 32;
        DE_X[15] = 16;
        DE_X[16] = 5;
        DE_X[17] = 3;
        DE_X[18] = 14;
    } else {
        set_screen_mode(3);
        screen_flip_offsets_set();
        DE_X[0] = 0;
        DE_X[1] = 0;
        DE_X[2] = 0;
        DE_X[3] = 0;
        DE_X[4] = 0;
        DE_X[5] = 0;
        DE_X[6] = 0;
        DE_X[7] = 0;
        DE_X[8] = 0;
        DE_X[9] = 0;
        DE_X[10] = 0;
        DE_X[11] = 0xC0;
        DE_X[12] = 0;
        DE_X[13] = 0;
        DE_X[14] = 0;
        DE_X[15] = 0;
        DE_X[16] = 0;
        DE_X[17] = 0;
        DE_X[18] = 0;
    }
    Max_vitality = 0xA0;
}
