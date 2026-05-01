from numpy import pi
# from gnuradio.filter import firdes
from enum import Enum

# 当前己方队伍选边
class CurrentSite(Enum):
    RED = 0
    BLUE = 1

SPS = 52.0
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

SENSITIVITY_SIG = 1.5756
SENSITIVITY_1 = 2.8323
SENSITIVITY_2 = 2.5809
SENSITIVITY_3 = 0.6646

BW_SIG = 540242
BW_1 = 940466
BW_2 = 860402
BW_3 = 250116

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

# TAPS_LPF_SIG_PRE = firdes.low_pass(1.0, samp_rate, DF_SIG + 10e3, 10e3)
# TAPS_LPF_SIG = firdes.low_pass(1.0, samp_rate, 20e3, 5e3)

# TAPS_LPF_1_PRE = firdes.low_pass(1.0, samp_rate, DF_1 + 10e3, 10e3)
# TAPS_LPF_1 = firdes.low_pass(1.0, samp_rate, 20e3, 5e3)

# TAPS_LPF_2_PRE = firdes.low_pass(1.0, samp_rate, DF_2 + 10e3, 10e3)
# TAPS_LPF_2 = firdes.low_pass(1.0, samp_rate, 20e3, 5e3)

# TAPS_LPF_3_PRE = firdes.low_pass(1.0, samp_rate, DF_3 + 10e3, 10e3)
# TAPS_LPF_3 = firdes.low_pass(1.0, samp_rate, 20e3, 5e3)

if __name__ == "__main__":
    print( DF_1 + 10e3)
    print( DF_2 + 10e3)
    print( DF_3 + 10e3)