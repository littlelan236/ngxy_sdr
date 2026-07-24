# 信号参数设置

from numpy import pi
from enum import Enum

class CurrentSite(Enum):
    RED = 0
    BLUE = 1

SPS = 47.0
SAMP_RATE = 1e6
BT = 0.35

FC_RED = 433.2e6
FC_BLUE = 433.92e6
FC_RED_1 = 432.2e6
FC_RED_2 = 432.5e6
FC_RED_3 = 432.8e6
FC_BLUE_1 = 434.92e6
FC_BLUE_2 = 434.62e6
FC_BLUE_3 = 434.32e6

SENSITIVITY_SIG = 1.5628
SENSITIVITY_1 = 2.8194
SENSITIVITY_2 = 2.5681
SENSITIVITY_3 = 0.6517

DF_SIG = SENSITIVITY_SIG * SAMP_RATE / (2 * pi)
DF_1 = SENSITIVITY_1 * SAMP_RATE / (2 * pi)
DF_2 = SENSITIVITY_2 * SAMP_RATE / (2 * pi)
DF_3 = SENSITIVITY_3 * SAMP_RATE / (2 * pi)

BW_SIG = 2 * (DF_SIG + SAMP_RATE / SPS)
BW_1 = 2 * (DF_1 + SAMP_RATE / SPS)
BW_2 = 2 * (DF_2 + SAMP_RATE / SPS)
BW_3 = 2 * (DF_3 + SAMP_RATE / SPS)

GAIN_SIG = 1 / SENSITIVITY_SIG
GAIN_1 = 1 / SENSITIVITY_1
GAIN_2 = 1 / SENSITIVITY_2
GAIN_3 = 1 / SENSITIVITY_3

if __name__ == "__main__":
    print(BW_SIG / 2)
    print(BW_1 / 2)
    print(BW_2 / 2)
    print(BW_3 / 2)