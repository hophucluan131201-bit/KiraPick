"""Ground truth for the owner's full shoot '20261025 - Aki/RAW' (439 NEF, 2026-10-25).

Main subject of each photo, grouped by look. Owner's statements (2026-10-27) are
marked 'owner'; the rest was labelled visually from the thumbnails by costume
continuity in capture order (may contain mistakes). Ranges are inclusive file
numbers; numbers that do not exist are ignored. Photos not listed are not scored
(crowds, unclear main subject, two equal people).
"""


def _r(a: int, b: int) -> list[int]:
    return list(range(a, b + 1))


LOOKS = {
    "A_photographer": [9645, 9646],
    "B_hanfu_sword": _r(9648, 9662),
    "C_peach": _r(9664, 9678),
    "D_blue_prince": _r(9679, 9681),
    "E_red_hair": _r(9682, 9689),
    "F_wings_lolita": _r(9690, 9702),
    "G_orange_lolita": _r(9703, 9705),
    "H_pink_mecha": _r(9706, 9721),
    "I_pink_cardigan": _r(9722, 9732),
    "J_guy_glasses": [9733],
    "K_doctor": _r(9739, 9752),
    "L_pink_white_dress": [9754, 9757],  # owner
    "M_bunny": _r(9760, 9762),  # owner ("9769 - 9762": the bunny photos are 9760-9762)
    "N_elysia": _r(9763, 9770),  # owner
    "O_silver_jacket": _r(9771, 9788),
    "P_white_seated": _r(9790, 9793),
    "Q_maid": _r(9795, 9812),
    "R_panda": _r(9814, 9820),
    "S_fox": _r(9821, 9828),
    "T_blonde_wings": _r(9830, 9845),
    "AJ_twotone_hair": _r(9846, 9850),
    "U_purple_pajama": [9856, 9857, 9858, 10],  # owner: 0010, 9857, 9858
    "V_blonde_fan": _r(9859, 9870),
    "W_white_royal": [9874, 9876] + _r(9877, 9883),  # owner: 9877-9879
    "X_lavender": _r(9885, 9906),  # owner: 9894-9904
    "Y_vr_man": [9907],
    "Z1_phone_man": [9911],
    "Z2_camera_man": [9912],
    "AK_black_shirt_man": [9914, 9915],
    "AL_cap_man": _r(9916, 9919),
    "AM_blonde_axe": _r(9920, 9925),
    "AN_suit_glasses": _r(9927, 9953),
    "AO_blue_flowers": [9954, 9955],
    "AP_snow_white_miku": _r(9957, 9976),
    "AQ_dark_knight": _r(9978, 9981),
    "AR_silver_princess": _r(9982, 9999),
    "G1_flower_hat": _r(2, 9),  # owner: 0002-0005
    "AA_green_glasses": _r(11, 48),
    "AB_blue_dragon": _r(50, 74),
    "AC_police": _r(76, 105),
    "AD_blue_dress": _r(107, 122),
    "AE_glasses_girl": [123],
    "AF_furina": _r(124, 156),
    "AG_dabi": _r(157, 169),
    "AH_purple_sleeve": _r(181, 189),  # owner: 0182-0189
    "AI_albedo": _r(190, 207),  # owner: 0190, 0191, 0192, 0207
}
