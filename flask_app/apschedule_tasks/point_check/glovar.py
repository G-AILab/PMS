import numpy as np
import threading


dict_sub_SYS, dict_LARGE_SYS, dict_KIND_SYS, dict_function_flag, His_DATA, dict_MODOUT, HisPREDATA, dict_normalized, dict_neu, \
    dict_normalized1, dict_neu1, dict_normalizedSVR, dict_neuSVR, dict_runtime, dict_run_stoptime, XTScore =[dict() for _ in range(16)]

time_numb, Pmakeupin, Pmakeupout, PmakeupoutUP, PAin, PAout, PBin, PBout, PMin, PMout, PABCOUT, P_FW014OUT, PACWOUT, PBCWOUT, PABCWOUT, \
    PLIN, PLM, PLOUT, PRIN, PRM, PROUT, PACWin, PBCWin, PCWOUT, PTV, PGV = [0 for _ in range(26)]

makeuptank, DEAtank = [np.zeros(2) for _ in range(2)]

VHP8, VHP7, VHP6 = [np.zeros(3) for _ in range(3)]

BPAmakeup, BPBmakeup, BPAF, BPA, BPBF, BPB, BPMF, BPM, BPACW, BPBCW = [np.zeros(5) for _ in range(10)]

VmakeupIN, VmakeupACLC, VmakeupBCLC, VmakeupCTR, VmakeupGUP, V_SOOTBLOWERSTEAM, VCV8404, VBPAOUT, VBPAh, VBPBOUT, VBPBh, VBPMOUT, \
    VBPMh, V_FW014, V_FA, V_FB, V_SA, V_SB, VBPAclc, VBPBclc, VBPMclc, VACWOUT, VBCWOUT, VALIN, VLDOWN, VLUP, VALREF, VALOUT, VABLR, \
        VBRIN, VRDOWN, VRUP, VBRREF, VBROUT, VCWOUT, VTV1, VTV2, VGV1, VGV2, VGV3, VGV4, VTUBIN = [np.zeros(8) for _ in range(42)]

ASECTE, BSECTE, CSECTE, DSECTE = [list() for _ in range(4)]

STEAMEXT8_FLOW, STEAMEXT7_FLOW, STEAMEXT6_FLOW = 0, 0, 0
HHEATERFD_zhixindu, numboilsso = 0, 0
VREHEATSPRAYVALVE = 0
HZCWIN = 0
tub_zt = -1
B_modle = np.zeros(10000)
numbmill = 0
Dhistime = 1  # redis中的实时数据是每秒记录的

CDATA = dict()
MID = dict()

cached_warnings = list() # 供 apr 使用

# tlocal = threading.local()
# tlocal.latest = '-1'  # str, 最新时间戳
latest_ts = -1

import logging
from logging.handlers import TimedRotatingFileHandler
from flask_app import _get_config
import sys


# logger = logging.getLogger('point_check')
# logger.setLevel(logging.DEBUG if _get_config.DEBUG else logging.INFO)
# # logger.setLevel(logging.INFO)
# file_handler = TimedRotatingFileHandler('logs/point_check.log', when='M', backupCount=5, encoding='utf-8')
# # file_handler = logging.StreamHandler(sys.stdout)
# # file_handler = logging.FileHandler('logs/point_check.log', mode='w')
# file_handler.setFormatter(logging.Formatter("%(asctime)s - %(filename)s[line:%(lineno)d] - %(levelname)s: %(message)s"))
# logger.addHandler(file_handler)
