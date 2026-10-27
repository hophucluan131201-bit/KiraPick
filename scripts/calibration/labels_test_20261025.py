"""Ground truth for the owner's 'Test' shoot (109 NEF, 2026-10-25), main subject of each photo.

Sources: owner's labels (G1-G6, given in chat 2026-10-27) + visual labelling of the thumbnails
by costume continuity (marked 'visual'). Keys are look ids; LOOK_TO_PERSON merges looks the owner
said are the same person. Photos not listed have no clear main subject.
"""

LOOKS = {
    "A_photographer": [9646, 9647],  # visual, uncertain (same navy jacket)
    "B_hanfu_sword": [9648, 9652, 9653, 9662],
    "C_peach": [9664, 9665, 9675],
    "D_blue_prince": [9680, 9681],
    "E_red_hair": [9683, 9689],
    "F_wings_lolita": [9690, 9701],
    "G_orange_lolita": [9703],
    "H_pink_mecha": [9706, 9707, 9716, 9718],
    "I_pink_cardigan": [9723, 9726, 9731, 9732],
    "J_guy_glasses": [9733],
    "K_doctor": [9739, 9745, 9749, 9750],
    "L_pink_white_dress": [9754, 9757],
    "M_bunny": [9761, 9762],
    "N_elysia": [9764],
    "O_silver_jacket": [9774, 9781, 9788],
    "P_white_seated": [9790, 9791],
    "Q_maid": [9810, 9811, 9812],
    "R_panda": [9814, 9815, 9820],
    "S_fox": [9824, 9825],
    "T_blonde_wings": [9834, 9835],
    "U_purple_pajama": [9857, 9858, 10],  # owner G2
    "V_blonde_fan": [9859, 9860, 9861, 9862, 9868, 9869, 9870],
    "W_white_royal": [9877, 9878, 9879],  # owner G3
    "X_lavender": [9894, 9895, 9896, 9902, 9904],  # owner G4
    "Y_vr_man": [9907, 9910],
    "Z1_phone_man": [9911],
    "Z2_camera_man": [9912],
    "G1_flower_hat": [2, 3, 4, 5],  # owner G1
    "AA_green_glasses": [15, 16, 28, 40, 48],
    "AB_blue_dragon": [50, 59, 62, 74],
    "AC_police": [88, 93, 101, 103],
    "AD_blue_dress": [109, 114, 119],
    "AE_glasses_girl": [123],
    "AF_furina": [125, 126, 135, 143, 151, 155],
    "AG_dabi": [162, 163, 164, 169],
    "AH_purple_sleeve": [182, 188, 189],  # owner G5 (0182-0189)
    "AI_albedo": [190, 191, 192, 207],  # owner G6
}
