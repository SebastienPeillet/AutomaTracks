#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on Mon Apr 15 07:35:05 2019

@author: aandre
"""


NODATA_VALUE = -9999
MAX_VALUE = 9999


# Shifts to get every edges from each nodes. For now, based on 48 direction like:
#     |   |   |   | 43|   | 42|   |   |   |
#  ---|---|---|---|---|---|---|---|---|---|---
#     |   |   |   |   |   |   |   |   |   |
#  ---|---|---|---|---|---|---|---|---|---|---
#     |   |   | 30| 29|   | 28| 27|   |   |
#  ---|---|---|---|---|---|---|---|---|---|---
#     |   | 31| 14| 13| 12| 11| 10| 26|   |
#  ---|---|---|---|---|---|---|---|---|---|---
#   44|   | 32| 15| 3 | 2 | 1 | 9 | 25|   | 41
#  ---|---|---|---|---|---|---|---|---|---|---
#     |   |   | 16| 4 | 0 | 8 | 24|   |   |
#  ---|---|---|---|---|---|---|---|---|---|---
#   45|   | 33| 17| 5 | 6 | 7 | 23| 40|   | 48
#  ---|---|---|---|---|---|---|---|---|---|---
#     |   | 34| 18| 19| 20| 21| 22| 39|   |
#  ---|---|---|---|---|---|---|---|---|---|---
#     |   |   | 35| 36|   | 37| 38|   |   |
#  ---|---|---|---|---|---|---|---|---|---|---
#     |   |   |   |   |   |   |   |   |   |
#  ---|---|---|---|---|---|---|---|---|---|---
#     |   |   |   | 46|   | 47|   |   |   |
#          px  py
SHIFT = [(+0, +0),  # 0
         (-1, +1),  # 1
         (-1, +0),  # 2
         (-1, -1),  # 3
         (+0, -1),  # 4
         (+1, -1),  # 5
         (+1, +0),  # 6
         (+1, +1),  # 7
         (+0, +1),  # 8
         (-1, +2),  # 9
         (-2, +2),  # 10
         (-2, +1),  # 11
         (-2, +0),  # 12
         (-2, -1),  # 13
         (-2, -2),  # 14
         (-1, -2),  # 15
         (+0, -2),  # 16
         (+1, -2),  # 17
         (+2, -2),  # 18
         (+2, -1),  # 19
         (+2, +0),  # 20
         (+2, +1),  # 21
         (+2, +2),  # 22
         (+1, +2),  # 23
         (+0, +2),  # 24
         (-1, +3),  # 25
         (-2, +3),  # 26
         (-3, +2),  # 27
         (-3, +1),  # 28
         (-3, -1),  # 29
         (-3, -2),  # 30
         (-2, -3),  # 31
         (-1, -3),  # 32
         (+1, -3),  # 33
         (+2, -3),  # 34
         (+3, -2),  # 35
         (+3, -1),  # 36
         (+3, +1),  # 37
         (+3, +2),  # 38
         (+2, +3),  # 39
         (+1, +3),  # 40
         (-1, +5),  # 41
         (-5, +1),  # 42
         (-5, -1),  # 43
         (-1, -5),  # 44
         (+1, -5),  # 45
         (+5, -1),  # 46
         (+5, +1),  # 47
         (+1, +5)   # 48
        ]
# List for the slope calc
SLOPE_CALC_COORD = [(0, 0),                                                                                           # 0
                    ([[SHIFT[2], SHIFT[8]]]),                                                                         # 1
                    ([[SHIFT[4], SHIFT[8]], [SHIFT[3], SHIFT[1]]]),                                                   # 2
                    ([[SHIFT[4], SHIFT[2]]]),                                                                         # 3
                    ([[SHIFT[6], SHIFT[2]], [SHIFT[5], SHIFT[3]]]),                                                   # 4
                    ([[SHIFT[4], SHIFT[6]]]),                                                                         # 5
                    ([[SHIFT[8], SHIFT[4]], [SHIFT[7], SHIFT[5]]]),                                                   # 6
                    ([[SHIFT[8], SHIFT[6]]]),                                                                         # 7
                    ([[SHIFT[2], SHIFT[6]], [SHIFT[1], SHIFT[7]]]),                                                   # 8
                    ([[SHIFT[2], SHIFT[7]], [SHIFT[11], SHIFT[24]], [SHIFT[12], SHIFT[8]], [SHIFT[1], SHIFT[23]]]),   # 9
                    ([[SHIFT[11], SHIFT[9]], [SHIFT[2], SHIFT[8]]]),                                                  # 10
                    ([[SHIFT[3], SHIFT[8]], [SHIFT[2], SHIFT[24]], [SHIFT[12], SHIFT[9]], [SHIFT[13], SHIFT[1]]]),    # 11
                    ([[SHIFT[13], SHIFT[11]], [SHIFT[3], SHIFT[1]], [SHIFT[4], SHIFT[8]]]),                           # 12
                    ([[SHIFT[4], SHIFT[1]], [SHIFT[3], SHIFT[11]], [SHIFT[16], SHIFT[2]], [SHIFT[15], SHIFT[12]]]),   # 13
                    ([[SHIFT[4], SHIFT[2]], [SHIFT[15], SHIFT[13]]]),                                                 # 14
                    ([[SHIFT[5], SHIFT[2]], [SHIFT[4], SHIFT[12]], [SHIFT[16], SHIFT[13]], [SHIFT[17], SHIFT[3]]]),   # 15
                    ([[SHIFT[17], SHIFT[15]], [SHIFT[5], SHIFT[3]], [SHIFT[6], SHIFT[2]]]),                           # 16
                    ([[SHIFT[6], SHIFT[3]], [SHIFT[20], SHIFT[4]], [SHIFT[5], SHIFT[15]], [SHIFT[19], SHIFT[16]]]),   # 17
                    ([[SHIFT[6], SHIFT[4]], [SHIFT[19], SHIFT[17]]]),                                                 # 18
                    ([[SHIFT[7], SHIFT[4]], [SHIFT[6], SHIFT[16]], [SHIFT[21], SHIFT[5]], [SHIFT[20], SHIFT[17]]]),   # 19
                    ([[SHIFT[8], SHIFT[4]], [SHIFT[5], SHIFT[7]], [SHIFT[21], SHIFT[19]]]),                           # 20
                    ([[SHIFT[8], SHIFT[5]], [SHIFT[24], SHIFT[6]], [SHIFT[7], SHIFT[19]], [SHIFT[23], SHIFT[20]]]),   # 21
                    ([[SHIFT[8], SHIFT[6]], [SHIFT[23], SHIFT[21]]]),                                                 # 22
                    ([[SHIFT[1], SHIFT[6]], [SHIFT[8], SHIFT[20]], [SHIFT[24], SHIFT[21]], [SHIFT[9], SHIFT[7]]]),    # 23
                    ([[SHIFT[2], SHIFT[6]], [SHIFT[7], SHIFT[1]], [SHIFT[9], SHIFT[23]]]),                            # 24
                    ([[SHIFT[2], SHIFT[21]], [SHIFT[12], SHIFT[7]], [SHIFT[1], SHIFT[22]], [SHIFT[11], SHIFT[23]]]),  # 25
                    ([[SHIFT[2], SHIFT[22]], [SHIFT[12], SHIFT[23]], [SHIFT[1], SHIFT[39]], [SHIFT[13], SHIFT[7]]]),  # 26
                    ([[SHIFT[3], SHIFT[23]], [SHIFT[2], SHIFT[40]], [SHIFT[13], SHIFT[24]], [SHIFT[14], SHIFT[8]]]),  # 27
                    ([[SHIFT[3], SHIFT[24]], [SHIFT[15], SHIFT[8]], [SHIFT[13], SHIFT[9]], [SHIFT[14], SHIFT[1]]]),   # 28
                    ([[SHIFT[4], SHIFT[9]], [SHIFT[16], SHIFT[1]], [SHIFT[3], SHIFT[10]], [SHIFT[15], SHIFT[11]]]),   # 29
                    ([[SHIFT[4], SHIFT[10]], [SHIFT[16], SHIFT[11]], [SHIFT[3], SHIFT[27]], [SHIFT[17], SHIFT[1]]]),  # 30
                    ([[SHIFT[5], SHIFT[11]], [SHIFT[4], SHIFT[28]], [SHIFT[17], SHIFT[12]], [SHIFT[18], SHIFT[2]]]),  # 31
                    ([[SHIFT[5], SHIFT[12]], [SHIFT[19], SHIFT[2]], [SHIFT[17], SHIFT[13]], [SHIFT[18], SHIFT[3]]]),  # 32
                    ([[SHIFT[6], SHIFT[13]], [SHIFT[20], SHIFT[3]], [SHIFT[5], SHIFT[14]], [SHIFT[19], SHIFT[15]]]),  # 33
                    ([[SHIFT[6], SHIFT[14]], [SHIFT[20], SHIFT[15]], [SHIFT[5], SHIFT[31]], [SHIFT[21], SHIFT[3]]]),  # 34
                    ([[SHIFT[6], SHIFT[32]], [SHIFT[7], SHIFT[15]], [SHIFT[21], SHIFT[16]], [SHIFT[22], SHIFT[4]]]),  # 35
                    ([[SHIFT[7], SHIFT[16]], [SHIFT[23], SHIFT[4]], [SHIFT[21], SHIFT[17]], [SHIFT[22], SHIFT[5]]]),  # 36
                    ([[SHIFT[8], SHIFT[17]], [SHIFT[24], SHIFT[5]], [SHIFT[7], SHIFT[18]], [SHIFT[23], SHIFT[19]]]),  # 37
                    ([[SHIFT[8], SHIFT[18]], [SHIFT[24], SHIFT[19]], [SHIFT[7], SHIFT[35]], [SHIFT[23], SHIFT[36]]]), # 38
                    ([[SHIFT[1], SHIFT[19]], [SHIFT[9], SHIFT[20]], [SHIFT[8], SHIFT[36]], [SHIFT[10], SHIFT[6]]]),   # 39
                    ([[SHIFT[1], SHIFT[20]], [SHIFT[9], SHIFT[21]], [SHIFT[24], SHIFT[37]], [SHIFT[11], SHIFT[6]]]),  # 40
                    ([[SHIFT[12], SHIFT[37]], [SHIFT[28], SHIFT[22]], [SHIFT[27], SHIFT[39]]]),                       # 41
                    ([[SHIFT[14], SHIFT[25]], [SHIFT[32], SHIFT[24]], [SHIFT[30], SHIFT[26]]]),                       # 42
                    ([[SHIFT[16], SHIFT[25]], [SHIFT[32], SHIFT[10]], [SHIFT[30], SHIFT[26]]]),                       # 43
                    ([[SHIFT[18], SHIFT[29]], [SHIFT[36], SHIFT[12]], [SHIFT[34], SHIFT[30]]]),                       # 44
                    ([[SHIFT[20], SHIFT[29]], [SHIFT[36], SHIFT[14]], [SHIFT[35], SHIFT[31]]]),                       # 45
                    ([[SHIFT[22], SHIFT[33]], [SHIFT[40], SHIFT[16]], [SHIFT[38], SHIFT[34]]]),                       # 46
                    ([[SHIFT[24], SHIFT[33]], [SHIFT[40], SHIFT[18]], [SHIFT[39], SHIFT[35]]]),                       # 47
                    ([[SHIFT[10], SHIFT[37]], [SHIFT[28], SHIFT[20]], [SHIFT[26], SHIFT[38]]])                        # 48
                   ]
