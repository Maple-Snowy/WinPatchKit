"""Material 3 表面色精确计算（自包含移植，无第三方依赖）。

Flet 1.0.5 的 color_scheme_seed 由 Flutter 前端 ColorScheme.fromSeed 渲染，
Python 侧只透传 seed 字符串，无法直接拿到 surface 值。为了让 Win32 标题栏
与内容区 surface **逐值一致**（而非近似估算），这里把 Google 官方
material-color-utilities（Apache-2.0，material-foundation）的算法移植为纯 Python。

移植范围（仅 surface 所需链路，逐函数对齐官方 Dart 版）：
    ColorUtils   sRGB <-> XYZ / L* / Lab 转换
    MathUtils    标量与矩阵小工具
    ViewingConditions   CAM16 观察条件（sRGB 标准）
    Cam16        argb -> hue（正向）
    HctSolver    (hue, chroma, tone) -> argb（牛顿法 + 临界平面二分）

surface 公式（官方 SchemeTonalSpot + MaterialDynamicColors.surface）：
    neutralPalette = TonalPalette.of(seedHue, chroma=6.0)
    surface        = neutralPalette.get(isDark ? 6 : 98)
即 surface = HctSolver.solveToInt(seedHue, 6.0, 98 | 6)。
"""
from __future__ import annotations

import math

# ============================================================ MathUtils
def _signum(num):
    if num < 0:
        return -1
    if num == 0:
        return 0
    return 1


def _lerp(start, stop, amount):
    return (1.0 - amount) * start + amount * stop


def _clamp_int(minn, maxn, value):
    if value < minn:
        return minn
    if value > maxn:
        return maxn
    return value


def _sanitize_degrees(degrees):
    degrees = degrees % 360.0
    if degrees < 0:
        degrees += 360.0
    return degrees


def _matrix_multiply(row, matrix):
    a = row[0] * matrix[0][0] + row[1] * matrix[0][1] + row[2] * matrix[0][2]
    b = row[0] * matrix[1][0] + row[1] * matrix[1][1] + row[2] * matrix[1][2]
    c = row[0] * matrix[2][0] + row[1] * matrix[2][1] + row[2] * matrix[2][2]
    return [a, b, c]


def _dart_round(x):
    """Dart double.round 语义：就近取整，平局远离零（delinearized*255 恒正，等价 floor(x+0.5)）。"""
    return int(math.floor(x + 0.5)) if x >= 0 else int(math.ceil(x - 0.5))


# ============================================================ ColorUtils
_SRGB_TO_XYZ = [
    [0.41233895, 0.35762064, 0.18051042],
    [0.2126, 0.7152, 0.0722],
    [0.01932141, 0.11916382, 0.95034478],
]
_XYZ_TO_SRGB = [
    [3.2413774792388685, -1.5376652402851851, -0.49885366846268053],
    [-0.9691452513005321, 1.8758853451067872, 0.04156585616912061],
    [0.05562093689691305, -0.20395524564742123, 1.0571799111220335],
]
_WHITE_POINT_D65 = [95.047, 100.0, 108.883]


def _argb_from_rgb(r, g, b):
    return (255 << 24) | ((r & 255) << 16) | ((g & 255) << 8) | (b & 255)


def _red(a):
    return (a >> 16) & 255


def _green(a):
    return (a >> 8) & 255


def _blue(a):
    return a & 255


def _argb_from_linrgb(linrgb):
    return _argb_from_rgb(_delinearized(linrgb[0]), _delinearized(linrgb[1]),
                          _delinearized(linrgb[2]))


def _argb_from_xyz(x, y, z):
    m = _XYZ_TO_SRGB
    lr = m[0][0] * x + m[0][1] * y + m[0][2] * z
    lg = m[1][0] * x + m[1][1] * y + m[1][2] * z
    lb = m[2][0] * x + m[2][1] * y + m[2][2] * z
    return _argb_from_rgb(_delinearized(lr), _delinearized(lg), _delinearized(lb))


def _xyz_from_argb(a):
    r = _linearized(_red(a))
    g = _linearized(_green(a))
    b = _linearized(_blue(a))
    return _matrix_multiply([r, g, b], _SRGB_TO_XYZ)


def _y_from_lstar(lstar):
    return 100.0 * _lab_invf((lstar + 16.0) / 116.0)


def _lstar_from_y(y):
    return _lab_f(y / 100.0) * 116.0 - 16.0


def _argb_from_lstar(lstar):
    y = _y_from_lstar(lstar)
    comp = _delinearized(y)
    return _argb_from_rgb(comp, comp, comp)


def _linearized(rgb):
    normalized = rgb / 255.0
    if normalized <= 0.040449936:
        return normalized / 12.92 * 100.0
    return ((normalized + 0.055) / 1.055) ** 2.4 * 100.0


def _delinearized(rgb_component):
    normalized = rgb_component / 100.0
    if normalized <= 0.0031308:
        d = normalized * 12.92
    else:
        d = 1.055 * (normalized ** (1.0 / 2.4)) - 0.055
    return _clamp_int(0, 255, _dart_round(d * 255.0))


def _lab_f(t):
    e = 216.0 / 24389.0
    k = 24389.0 / 27.0
    return t ** (1.0 / 3.0) if t > e else (k * t + 16.0) / 116.0


def _lab_invf(ft):
    e = 216.0 / 24389.0
    k = 24389.0 / 27.0
    ft3 = ft * ft * ft
    return ft3 if ft3 > e else (116.0 * ft - 16.0) / k


# ============================================================ ViewingConditions（sRGB 标准）
def _viewing_conditions():
    wp = _WHITE_POINT_D65
    adapting_luminance = (200.0 / math.pi * _y_from_lstar(50.0) / 100.0)
    surround = 2.0
    x, y, z = wp
    rW = x * 0.401288 + y * 0.650173 + z * -0.051461
    gW = x * -0.250268 + y * 1.204414 + z * 0.045854
    bW = x * -0.002079 + y * 0.048952 + z * 0.953127
    f = 0.8 + (surround / 10.0)
    c = (_lerp(0.59, 0.69, (f - 0.9) * 10.0) if f >= 0.9
         else _lerp(0.525, 0.59, (f - 0.8) * 10.0))
    d = f * (1.0 - ((1.0 / 3.6) * math.exp((-adapting_luminance - 42.0) / 92.0)))
    d = 1.0 if d > 1.0 else (0.0 if d < 0.0 else d)
    nc = f
    rgbD = [
        d * (100.0 / rW) + 1.0 - d,
        d * (100.0 / gW) + 1.0 - d,
        d * (100.0 / bW) + 1.0 - d,
    ]
    k = 1.0 / (5.0 * adapting_luminance + 1.0)
    k4 = k ** 4
    k4f = 1.0 - k4
    fl = k4 * adapting_luminance + 0.1 * k4f * k4f * (5.0 * adapting_luminance) ** (1.0 / 3.0)
    n = _y_from_lstar(50.0) / wp[1]
    zc = 1.48 + math.sqrt(n)
    nbb = 0.725 / (n ** 0.2)
    ncb = nbb
    rAf = (fl * rgbD[0] * rW / 100.0) ** 0.42
    gAf = (fl * rgbD[1] * gW / 100.0) ** 0.42
    bAf = (fl * rgbD[2] * bW / 100.0) ** 0.42
    rgbA = [
        (400.0 * rAf) / (rAf + 27.13),
        (400.0 * gAf) / (gAf + 27.13),
        (400.0 * bAf) / (bAf + 27.13),
    ]
    aw = (40.0 * rgbA[0] + 20.0 * rgbA[1] + rgbA[2]) / 20.0 * nbb
    return {
        "backgroundYTowhitePointY": n,
        "aw": aw, "nbb": nbb, "ncb": ncb, "c": c, "nC": nc,
        "rgbD": rgbD, "fl": fl, "fLRoot": fl ** 0.25, "z": zc,
    }


_VC = _viewing_conditions()


# ============================================================ Cam16（正向 argb -> hue）
def _cam16_hue_from_argb(argb):
    x, y, z = _xyz_from_argb(argb)
    vc = _VC
    rC = 0.401288 * x + 0.650173 * y - 0.051461 * z
    gC = -0.250268 * x + 1.204414 * y + 0.045854 * z
    bC = -0.002079 * x + 0.048952 * y + 0.953127 * z
    rD = vc["rgbD"][0] * rC
    gD = vc["rgbD"][1] * gC
    bD = vc["rgbD"][2] * bC
    rAF = (vc["fl"] * abs(rD) / 100.0) ** 0.42
    gAF = (vc["fl"] * abs(gD) / 100.0) ** 0.42
    bAF = (vc["fl"] * abs(bD) / 100.0) ** 0.42
    rA = _signum(rD) * 400.0 * rAF / (rAF + 27.13)
    gA = _signum(gD) * 400.0 * gAF / (gAF + 27.13)
    bA = _signum(bD) * 400.0 * bAF / (bAF + 27.13)
    a = (11.0 * rA + -12.0 * gA + bA) / 11.0
    b = (rA + gA - 2.0 * bA) / 9.0
    return _sanitize_degrees(math.atan2(b, a) * 180.0 / math.pi)


# ============================================================ HctSolver
_SCALED_DISCOUNT_FROM_LINRGB = [
    [0.001200833568784504, 0.002389694492170889, 0.0002795742885861124],
    [0.0005891086651375999, 0.0029785502573438758, 0.0003270666104008398],
    [0.00010146692491640572, 0.0005364214359186694, 0.0032979401770712076],
]
_LINRGB_FROM_SCALED_DISCOUNT = [
    [1373.2198709594231, -1100.4251190754821, -7.278681089101213],
    [-271.815969077903, 559.6580465940733, -32.46047482791194],
    [1.9622899599665666, -57.173814538844006, 308.7233197812385],
]
_Y_FROM_LINRGB = [0.2126, 0.7152, 0.0722]

_CRITICAL_PLANES = [
    0.015176349177441876, 0.045529047532325624, 0.07588174588720938,
    0.10623444424209313, 0.13658714259697685, 0.16693984095186062,
    0.19729253930674434, 0.2276452376616281, 0.2579979360165119,
    0.28835063437139563, 0.3188300904430532, 0.350925934958123,
    0.3848314933096426, 0.42057480301049466, 0.458183274052838,
    0.4976837250274023, 0.5391024159806381, 0.5824650784040898,
    0.6277969426914107, 0.6751227633498623, 0.7244668422128921,
    0.775853049866786, 0.829304845476233, 0.8848452951698498,
    0.942497089126609, 1.0022825574869039, 1.0642236851973577,
    1.1283421258858297, 1.1946592148522128, 1.2631959812511864,
    1.3339731595349034, 1.407011200216447, 1.4823302800086415,
    1.5599503113873272, 1.6398909516233677, 1.7221716113234105,
    1.8068114625156377, 1.8938294463134073, 1.9832442801866852,
    2.075074464868551, 2.1693382909216234, 2.2660538449872063,
    2.36523901573795, 2.4669114995532007, 2.5710888059345764,
    2.6777882626779785, 2.7870270208169257, 2.898822059350997,
    3.0131901897720907, 3.1301480604002863, 3.2497121605402226,
    3.3718988244681087, 3.4967242352587946, 3.624204428461639,
    3.754355295633311, 3.887192587735158, 4.022731918402185,
    4.160988767090289, 4.301978482107941, 4.445716283538092,
    4.592217266055746, 4.741496401646282, 4.893568542229298,
    5.048448422192488, 5.20615066083972, 5.3666897647573375,
    5.5300801301023865, 5.696336044816294, 5.865471690767354,
    6.037501145825082, 6.212438385869475, 6.390297286737924,
    6.571091626112461, 6.7548350853498045, 6.941541251256611,
    7.131223617812143, 7.323895587840543, 7.5195704746346665,
    7.7182615035334345, 7.919981813454504, 8.124744458384042,
    8.332562408825165, 8.543448553206703, 8.757415699253682,
    8.974476575321063, 9.194643831691977, 9.417930041841839,
    9.644347703669503, 9.873909240696694, 10.106627003236781,
    10.342513269534024, 10.58158024687427, 10.8238400726681,
    11.069304815507364, 11.317986476196008, 11.569896988756009,
    11.825048221409341, 12.083451977536606, 12.345119996613247,
    12.610063955123938, 12.878295467455942, 13.149826086772048,
    13.42466730586372, 13.702830557985108, 13.984327217668513,
    14.269168601521828, 14.55736596900856, 14.848930523210871,
    15.143873411576273, 15.44220572664832, 15.743938506781891,
    16.04908273684337, 16.35764934889634, 16.66964922287304,
    16.985093187232053, 17.30399201960269, 17.62635644741625,
    17.95219714852476, 18.281524751807332, 18.614349837764564,
    18.95068293910138, 19.290534541298456, 19.633915083172692,
    19.98083495742689, 20.331304511189067, 20.685334046541502,
    21.042933821039977, 21.404114048223256, 21.76888489811322,
    22.137256497705877, 22.50923893145328, 22.884842241736916,
    23.264076429332462, 23.6469514538663, 24.033477234264016,
    24.42366364919083, 24.817520537484558, 25.21505769858089,
    25.61628489293138, 26.021211842414342, 26.429848230738664,
    26.842203703840827, 27.258287870275353, 27.678110301598522,
    28.10168053274597, 28.529008062403893, 28.96010235337422,
    29.39497283293396, 29.83362889318845, 30.276079891419332,
    30.722335150426627, 31.172403958865512, 31.62629557157785,
    32.08401920991837, 32.54558406207592, 33.010999283389665,
    33.4802739966603, 33.953417292456834, 34.430438229418264,
    34.911345834551085, 35.39614910352207, 35.88485700094671,
    36.37747846067349, 36.87402238606382, 37.37449765026789,
    37.87891309649659, 38.38727753828926, 38.89959975977785,
    39.41588851594697, 39.93615253289054, 40.460400508064545,
    40.98864111053629, 41.520882981230194, 42.05713473317016,
    42.597404951718396, 43.141702194811224, 43.6900349931913,
    44.24241185063697, 44.798841244188324, 45.35933162437017,
    45.92389141541209, 46.49252901546552, 47.065252796817916,
    47.64207110610409, 48.22299226451468, 48.808024568002054,
    49.3971762874833, 49.9904556690408, 50.587870934119984,
    51.189430279724725, 51.79514187861014, 52.40501387947288,
    53.0190544071392, 53.637271562750364, 54.259673423945976,
    54.88626804504493, 55.517063457223934, 56.15206766869424,
    56.79128866487574, 57.43473440856916, 58.08241284012621,
    58.734331877617365, 59.39049941699807, 60.05092333227251,
    60.715611475655585, 61.38457167773311, 62.057811747619894,
    62.7353394731159, 63.417162620860914, 64.10328893648692,
    64.79372614476921, 65.48848194977529, 66.18756403501224,
    66.89098006357258, 67.59873767827808, 68.31084450182222,
    69.02730813691093, 69.74813616640164, 70.47333615344107,
    71.20291564160104, 71.93688215501312, 72.67524319850172,
    73.41800625771542, 74.16517879925733, 74.9167682708136,
    75.67278210128072, 76.43322770089146, 77.1981124613393,
    77.96744375590167, 78.74122893956174, 79.51947534912904,
    80.30219030335869, 81.08938110306934, 81.88105503125999,
    82.67721935322541, 83.4778813166706, 84.28304815182372,
    85.09272707154808, 85.90692527145302, 86.72564993000343,
    87.54890820862819, 88.3767072518277, 89.2090541872801,
    90.04595612594655, 90.88742016217518, 91.73345337380438,
    92.58406282226491, 93.43925555268066, 94.29903859396902,
    95.16341895893969, 96.03240364439274, 96.9059996312159,
    97.78421388448044, 98.6670533535366, 99.55452497210776,
]


def _sanitize_radians(angle):
    return (angle + math.pi * 8) % (math.pi * 2)


def _true_delinearized(rgb_component):
    normalized = rgb_component / 100.0
    if normalized <= 0.0031308:
        d = normalized * 12.92
    else:
        d = 1.055 * (normalized ** (1.0 / 2.4)) - 0.055
    return d * 255.0


def _chromatic_adaptation(component):
    af = abs(component) ** 0.42
    return _signum(component) * 400.0 * af / (af + 27.13)


def _hue_of(linrgb):
    sd = _matrix_multiply(linrgb, _SCALED_DISCOUNT_FROM_LINRGB)
    rA = _chromatic_adaptation(sd[0])
    gA = _chromatic_adaptation(sd[1])
    bA = _chromatic_adaptation(sd[2])
    a = (11.0 * rA + -12.0 * gA + bA) / 11.0
    b = (rA + gA - 2.0 * bA) / 9.0
    return math.atan2(b, a)


def _are_in_cyclic_order(a, b, c):
    dAB = _sanitize_radians(b - a)
    dAC = _sanitize_radians(c - a)
    return dAB < dAC


def _intercept(source, mid, target):
    return (mid - source) / (target - source)


def _lerp_point(source, t, target):
    return [
        source[0] + (target[0] - source[0]) * t,
        source[1] + (target[1] - source[1]) * t,
        source[2] + (target[2] - source[2]) * t,
    ]


def _set_coordinate(source, coordinate, target, axis):
    t = _intercept(source[axis], coordinate, target[axis])
    return _lerp_point(source, t, target)


def _is_bounded(x):
    return 0.0 <= x <= 100.0


def _nth_vertex(y, n):
    kR, kG, kB = _Y_FROM_LINRGB
    coord_a = 0.0 if (n % 4) <= 1 else 100.0
    coord_b = 0.0 if (n % 2) == 0 else 100.0
    if n < 4:
        g, b = coord_a, coord_b
        r = (y - g * kG - b * kB) / kR
        return [r, g, b] if _is_bounded(r) else [-1.0, -1.0, -1.0]
    elif n < 8:
        b, r = coord_a, coord_b
        g = (y - r * kR - b * kB) / kG
        return [r, g, b] if _is_bounded(g) else [-1.0, -1.0, -1.0]
    else:
        r, g = coord_a, coord_b
        b = (y - r * kR - g * kG) / kB
        return [r, g, b] if _is_bounded(b) else [-1.0, -1.0, -1.0]


def _bisect_to_segment(y, target_hue):
    left = [-1.0, -1.0, -1.0]
    right = left
    left_hue = 0.0
    right_hue = 0.0
    initialized = False
    uncut = True
    for n in range(12):
        mid = _nth_vertex(y, n)
        if mid[0] < 0:
            continue
        mid_hue = _hue_of(mid)
        if not initialized:
            left = mid
            right = mid
            left_hue = mid_hue
            right_hue = mid_hue
            initialized = True
            continue
        if uncut or _are_in_cyclic_order(left_hue, mid_hue, right_hue):
            uncut = False
            if _are_in_cyclic_order(left_hue, target_hue, mid_hue):
                right = mid
                right_hue = mid_hue
            else:
                left = mid
                left_hue = mid_hue
    return [left, right]


def _midpoint(a, b):
    return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2]


def _critical_plane_below(x):
    return math.floor(x - 0.5)


def _critical_plane_above(x):
    return math.ceil(x - 0.5)


def _bisect_to_limit(y, target_hue):
    segment = _bisect_to_segment(y, target_hue)
    left = segment[0]
    left_hue = _hue_of(left)
    right = segment[1]
    for axis in range(3):
        if left[axis] != right[axis]:
            if left[axis] < right[axis]:
                l_plane = _critical_plane_below(_true_delinearized(left[axis]))
                r_plane = _critical_plane_above(_true_delinearized(right[axis]))
            else:
                l_plane = _critical_plane_above(_true_delinearized(left[axis]))
                r_plane = _critical_plane_below(_true_delinearized(right[axis]))
            for _ in range(8):
                if abs(r_plane - l_plane) <= 1:
                    break
                m_plane = math.floor((l_plane + r_plane) / 2.0)
                mid_coord = _CRITICAL_PLANES[m_plane]
                mid = _set_coordinate(left, mid_coord, right, axis)
                mid_hue = _hue_of(mid)
                if _are_in_cyclic_order(left_hue, target_hue, mid_hue):
                    right = mid
                    r_plane = m_plane
                else:
                    left = mid
                    left_hue = mid_hue
                    l_plane = m_plane
    return _midpoint(left, right)


def _inverse_chromatic_adaptation(adapted):
    a = abs(adapted)
    base = max(0, 27.13 * a / (400.0 - a))
    return _signum(adapted) * (base ** (1.0 / 0.42))


def _find_result_by_j(hue_radians, chroma, y):
    j = math.sqrt(y) * 11.0
    vc = _VC
    t_inner_coeff = 1.0 / ((1.64 - (0.29 ** vc["backgroundYTowhitePointY"])) ** 0.73)
    e_hue = 0.25 * (math.cos(hue_radians + 2.0) + 3.8)
    p1 = e_hue * (50000.0 / 13.0) * vc["nC"] * vc["ncb"]
    h_sin = math.sin(hue_radians)
    h_cos = math.cos(hue_radians)
    for iteration in range(5):
        j_normalized = j / 100.0
        alpha = 0.0 if (chroma == 0.0 or j == 0.0) else chroma / math.sqrt(j_normalized)
        t = (alpha * t_inner_coeff) ** (1.0 / 0.9)
        ac = vc["aw"] * (j_normalized ** (1.0 / vc["c"] / vc["z"]))
        p2 = ac / vc["nbb"]
        gamma = 23.0 * (p2 + 0.305) * t / (23.0 * p1 + 11 * t * h_cos + 108.0 * t * h_sin)
        a = gamma * h_cos
        b = gamma * h_sin
        rA = (460.0 * p2 + 451.0 * a + 288.0 * b) / 1403.0
        gA = (460.0 * p2 - 891.0 * a - 261.0 * b) / 1403.0
        bA = (460.0 * p2 - 220.0 * a - 6300.0 * b) / 1403.0
        linrgb = _matrix_multiply(
            [_inverse_chromatic_adaptation(rA), _inverse_chromatic_adaptation(gA),
             _inverse_chromatic_adaptation(bA)],
            _LINRGB_FROM_SCALED_DISCOUNT)
        if linrgb[0] < 0 or linrgb[1] < 0 or linrgb[2] < 0:
            return 0
        kR, kG, kB = _Y_FROM_LINRGB
        fnj = kR * linrgb[0] + kG * linrgb[1] + kB * linrgb[2]
        if fnj <= 0:
            return 0
        if iteration == 4 or abs(fnj - y) < 0.002:
            if linrgb[0] > 100.01 or linrgb[1] > 100.01 or linrgb[2] > 100.01:
                return 0
            return _argb_from_linrgb(linrgb)
        j = j - (fnj - y) * j / (2 * fnj)
    return 0


def _solve_to_int(hue_degrees, chroma, lstar):
    if chroma < 0.0001 or lstar < 0.0001 or lstar > 99.9999:
        return _argb_from_lstar(lstar)
    hue_degrees = _sanitize_degrees(hue_degrees)
    hue_radians = hue_degrees / 180.0 * math.pi
    y = _y_from_lstar(lstar)
    exact = _find_result_by_j(hue_radians, chroma, y)
    if exact != 0:
        return exact
    return _argb_from_linrgb(_bisect_to_limit(y, hue_radians))


# ============================================================ 对外 API
def _lstar_from_argb(argb):
    return _lstar_from_y(_xyz_from_argb(argb)[1])


def _argb_from_hct(hue, chroma, tone):
    return _solve_to_int(hue, chroma, tone)


def _hex_to_rgb(rgb_hex):
    h = (rgb_hex or "").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return None
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return None


def surface_color(seed: str, dark: bool) -> str:
    """返回与 Flet 内容区一致的 Material 3 surface 色（'#RRGGBB'）。

    等价于 SchemeTonalSpot 的 surface：neutralPalette(chroma=6).get(tone)。
    seed 非法时回退海绿 #2E8B57。
    """
    rgb = _hex_to_rgb(seed) or (46, 139, 87)
    seed_argb = _argb_from_rgb(rgb[0], rgb[1], rgb[2])
    hue = _cam16_hue_from_argb(seed_argb)
    tone = 6.0 if dark else 98.0
    argb = _solve_to_int(hue, 6.0, tone)
    return "#%02X%02X%02X" % (_red(argb), _green(argb), _blue(argb))