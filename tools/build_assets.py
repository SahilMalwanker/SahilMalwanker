"""Generate the SVG artwork for the GitHub profile README (stdlib only).

    python3 tools/build_assets.py            # writes assets/*.svg
    python3 tools/build_assets.py --frames   # also writes banner frames for checking

banner.svg          animated pick-and-place cell (SMIL), self-contained dark card
banner-static.svg   same scene frozen mid-transfer (used for prefers-reduced-motion)
journey-*.svg       career trajectory through waypoints, light + dark
toolchain-*.svg     grouped tool chips, light + dark
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"

SANS = "'Inter','Segoe UI',-apple-system,BlinkMacSystemFont,'Helvetica Neue',Arial,sans-serif"
MONO = "'JetBrains Mono','SFMono-Regular',ui-monospace,Menlo,Consolas,'Liberation Mono',monospace"

# --------------------------------------------------------------------------------------
# Banner: a planar 3R arm moving boxes from an infeed to an outfeed conveyor
# --------------------------------------------------------------------------------------
W, H = 1000, 340
T = 8.0  # cycle length [s]
SX, SY = 905.0, 205.0  # shoulder position (SVG coordinates)
L1, L2, L3 = 125.0, 112.0, 50.0  # upper arm, forearm, wrist -> tool centre point
BELT_Y = 290.0  # belt surface
FLOOR_Y = 318.0
BOX_W, BOX_H = 34.0, 30.0
PICK_X, PLACE_X = 690.0, 805.0
EASE = (0.45, 0.0, 0.55, 1.0)


def ik(tcp_x: float, tcp_y: float, prefer: int) -> tuple[float, float, float]:
    """Joint angles [deg, maths convention] for a tool pointing straight down."""
    wx, wy = tcp_x - SX, SY - (tcp_y - L3)  # wrist relative to shoulder, y up
    c2 = (wx * wx + wy * wy - L1 * L1 - L2 * L2) / (2 * L1 * L2)
    q2 = prefer * math.acos(max(-1.0, min(1.0, c2)))
    q1 = math.atan2(wy, wx) - math.atan2(L2 * math.sin(q2), L1 + L2 * math.cos(q2))
    q1, q2 = math.degrees(q1), math.degrees(q2)
    return q1, q2, -90.0 - q1 - q2


def fk(q: tuple[float, float, float]) -> list[tuple[float, float]]:
    """Shoulder, elbow, wrist and TCP in SVG coordinates."""
    pts, x, y, a = [(SX, SY)], SX, SY, 0.0
    for qi, li in zip(q, (L1, L2, L3)):
        a += math.radians(qi)
        x, y = x + li * math.cos(a), y - li * math.sin(a)
        pts.append((x, y))
    return pts


GRASP_Y = BELT_Y - BOX_H / 2
POSES = {
    "home": ik(842, 172, +1),
    "above_a": ik(PICK_X, GRASP_Y - 62, +1),
    "at_a": ik(PICK_X, GRASP_Y, +1),
    "above_b": ik(PLACE_X, GRASP_Y - 70, +1),
    "at_b": ik(PLACE_X, GRASP_Y, +1),
}
# (time, pose, gripper opening 1 = open, state label)
KEYS = [
    (0.0, "home", 1, "MOVE_TO_PICK"),
    (1.5, "above_a", 1, "DESCEND"),
    (2.2, "at_a", 1, "GRASP"),
    (2.6, "at_a", 0, "LIFT"),
    (3.2, "above_a", 0, "TRANSFER"),
    (4.4, "above_b", 0, "DESCEND"),
    (5.0, "at_b", 0, "RELEASE"),
    (5.4, "at_b", 1, "RETREAT"),
    (5.9, "above_b", 1, "RETURN_HOME"),
    (7.2, "home", 1, "IDLE"),
    (8.0, "home", 1, "IDLE"),
]


def unwrap_keys() -> list[tuple[float, ...]]:
    out: list[tuple[float, ...]] = []
    for _, pose, _, _ in KEYS:
        q = list(POSES[pose])
        if out:
            for j in range(3):
                while q[j] - out[-1][j] > 180:
                    q[j] -= 360
                while q[j] - out[-1][j] < -180:
                    q[j] += 360
        out.append(tuple(q))
    return out


QK = unwrap_keys()


def ease(s: float) -> float:
    x1, y1, x2, y2 = EASE
    lo, hi = 0.0, 1.0
    for _ in range(40):
        u = (lo + hi) / 2
        x = 3 * (1 - u) ** 2 * u * x1 + 3 * (1 - u) * u * u * x2 + u**3
        lo, hi = (u, hi) if x < s else (lo, u)
    u = (lo + hi) / 2
    return 3 * (1 - u) ** 2 * u * y1 + 3 * (1 - u) * u * u * y2 + u**3


def interp(t: float, values: list) -> float | tuple:
    t %= T
    for i in range(len(KEYS) - 1):
        t0, t1 = KEYS[i][0], KEYS[i + 1][0]
        if t0 <= t <= t1:
            e = ease((t - t0) / (t1 - t0)) if t1 > t0 else 0.0
            a, b = values[i], values[i + 1]
            if isinstance(a, tuple):
                return tuple(x + (y - x) * e for x, y in zip(a, b))
            return a + (b - a) * e
    return values[-1]


def q_at(t: float) -> tuple[float, float, float]:
    return interp(t, QK)  # type: ignore[return-value]


def grip_at(t: float) -> float:
    return interp(t, [float(k[2]) for k in KEYS])  # type: ignore[return-value]


def wrap(q: tuple) -> tuple:
    return tuple((v + 180) % 360 - 180 for v in q)


def key_times() -> str:
    return ";".join(f"{k[0] / T:.4f}" for k in KEYS)


def splines() -> str:
    return ";".join(" ".join(str(v) for v in EASE) for _ in KEYS[:-1])


def smil_rotate(values: list[float]) -> str:
    vals = ";".join(f"{-v:.2f}" for v in values)  # SVG rotates clockwise
    return (f'<animateTransform attributeName="transform" type="rotate" values="{vals}" '
            f'keyTimes="{key_times()}" calcMode="spline" keySplines="{splines()}" '
            f'dur="{T}s" repeatCount="indefinite"/>')


def visible(start: float, end: float, attr: str = "opacity") -> str:
    """Discrete on/off window inside the cycle."""
    if start <= 0:
        vals, kt = "1;0", f"0;{end / T:.4f}"
    elif end >= T:
        vals, kt = "0;1", f"0;{start / T:.4f}"
    else:
        vals, kt = "0;1;0", f"0;{start / T:.4f};{end / T:.4f}"
    return (f'<animate attributeName="{attr}" values="{vals}" keyTimes="{kt}" '
            f'calcMode="discrete" dur="{T}s" repeatCount="indefinite"/>')


def state_windows() -> list[tuple[float, float, str]]:
    wins: list[tuple[float, float, str]] = []
    for i in range(len(KEYS) - 1):
        label = KEYS[i][3]
        if wins and wins[-1][2] == label:
            wins[-1] = (wins[-1][0], KEYS[i + 1][0], label)
        else:
            wins.append((KEYS[i][0], KEYS[i + 1][0], label))
    return wins


def box(x: float, y: float, extra: str = "") -> str:
    """Payload box with its centre at (x, y)."""
    return (f'<g transform="translate({x:.1f},{y:.1f})"{extra}>'
            f'<rect x="{-BOX_W/2}" y="{-BOX_H/2}" width="{BOX_W}" height="{BOX_H}" rx="3" fill="url(#crate)" stroke="#a86a00" stroke-width="1"/>'
            f'<path d="M{-BOX_W/2+5} {-BOX_H/2+9}H{BOX_W/2-5}" stroke="#a86a00" stroke-width="1.4" opacity=".7"/>'
            f'<rect x="-6" y="-2" width="12" height="9" rx="1.5" fill="#fff4dc" opacity=".85"/></g>')


def banner(t: float | None = None) -> str:
    """Animated banner, or a static frame at time t."""
    anim = t is None
    q = q_at(t) if not anim else QK[0]
    grip = grip_at(t) if not anim else 1.0

    def joint(i: int) -> str:
        return smil_rotate([k[i] for k in QK]) if anim else ""

    def rot(i: int) -> str:
        return "" if anim else f' transform="rotate({-q[i]:.2f})"'

    # fingers: half-gap from the tool axis (open 29, closed 20)
    gaps = [20 + 9 * k[2] for k in KEYS]
    if anim:
        fvals = ";".join(f"0,{-g:.1f}" for g in gaps)
        fvals2 = ";".join(f"0,{g:.1f}" for g in gaps)
        fing = lambda vals: (f'<animateTransform attributeName="transform" type="translate" values="{vals}" '
                             f'keyTimes="{key_times()}" calcMode="spline" keySplines="{splines()}" dur="{T}s" repeatCount="indefinite"/>')
        f1 = f'<g>{fing(fvals)}<rect x="30" y="-3" width="26" height="6" rx="2" fill="#2b3a50"/><rect x="50" y="-3" width="6" height="6" rx="1.5" fill="#ffb020"/></g>'
        f2 = f'<g>{fing(fvals2)}<rect x="30" y="-3" width="26" height="6" rx="2" fill="#2b3a50"/><rect x="50" y="-3" width="6" height="6" rx="1.5" fill="#ffb020"/></g>'
    else:
        g = 20 + 9 * grip
        f1 = f'<g transform="translate(0,{-g:.1f})"><rect x="30" y="-3" width="26" height="6" rx="2" fill="#2b3a50"/><rect x="50" y="-3" width="6" height="6" rx="1.5" fill="#ffb020"/></g>'
        f2 = f'<g transform="translate(0,{g:.1f})"><rect x="30" y="-3" width="26" height="6" rx="2" fill="#2b3a50"/><rect x="50" y="-3" width="6" height="6" rx="1.5" fill="#ffb020"/></g>'

    # box carried in the tool frame (tool axis = local +x, pointing down in the world)
    carry_on = 2.6 <= (t % T) < 5.4 if not anim else False
    carried = (f'<g transform="rotate(90 {L3} 0)">{box(L3, 0)}</g>')
    if anim:
        carried = f'<g opacity="0">{visible(2.6, 5.4)}{carried}</g>'
    elif not carry_on:
        carried = ""

    tool = (f'<g>'  # wrist flange, palm, fingers and the tool frame
            f'{carried}'
            f'<rect x="-6" y="-10" width="18" height="20" rx="4" fill="#1b2738" stroke="#2de2c0" stroke-width="1.2"/>'
            f'<rect x="12" y="-33" width="18" height="66" rx="4" fill="#d9e2ee"/>'
            f'<rect x="12" y="-33" width="5" height="66" rx="2" fill="#aebccd"/>'
            f'{f1}{f2}'
            f'<g stroke-width="2" stroke-linecap="round"><path d="M{L3} 0h18" stroke="#4aa3ff"/><path d="M{L3} 0v-18" stroke="#ff5c5c"/></g>'
            f'<circle cx="{L3}" cy="0" r="2.6" fill="#e8eef6"/>'
            f'</g>')

    hub = lambda r: (f'<circle r="{r}" fill="#162133" stroke="#2de2c0" stroke-width="2"/>'
                     f'<circle r="{r*0.38:.1f}" fill="#e8eef6"/>')
    link = lambda length, h: (f'<rect x="-10" y="{-h/2}" width="{length+20}" height="{h}" rx="{h/2}" fill="url(#steel)"/>'
                              f'<rect x="8" y="{-h/2+3}" width="{length-16}" height="3" rx="1.5" fill="#ffffff" opacity=".45"/>')

    arm = (f'<g transform="translate({SX},{SY})"><g{rot(0)}>{joint(0)}'
           f'{link(L1, 24)}'
           f'<g transform="translate({L1},0)"><g{rot(1)}>{joint(1)}'
           f'{link(L2, 19)}'
           f'<g transform="translate({L2},0)"><g{rot(2)}>{joint(2)}{tool}{hub(9)}</g></g>'
           f'{hub(12)}</g></g>'
           f'{hub(16)}</g></g>')

    # end-effector path over one cycle (dotted planned trajectory)
    pts = [fk(q_at(i * T / 240))[3] for i in range(241)]
    trace = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)

    # free boxes on the conveyors
    if anim:
        infeed = box(0, 0)
        infeed = (f'<g opacity="0">{visible(0, 2.6)}'
                  f'<g><animateTransform attributeName="transform" type="translate" '
                  f'values="572,{GRASP_Y};{PICK_X},{GRASP_Y};{PICK_X},{GRASP_Y}" keyTimes="0;{1.4/T:.4f};1" '
                  f'calcMode="spline" keySplines="0.3 0 0.4 1;0 0 1 1" dur="{T}s" repeatCount="indefinite"/>{infeed}</g></g>')
        outfeed = (f'<g opacity="0"><animate attributeName="opacity" values="0;0;1;1;0;0" '
                   f'keyTimes="0;{5.399/T:.4f};{5.4/T:.4f};{6.5/T:.4f};{7.4/T:.4f};1" dur="{T}s" repeatCount="indefinite"/>'
                   f'<g><animateTransform attributeName="transform" type="translate" '
                   f'values="{PLACE_X},{GRASP_Y};{PLACE_X},{GRASP_Y};{PLACE_X},{GRASP_Y+14}" keyTimes="0;{6.5/T:.4f};{7.4/T:.4f}" '
                   f'dur="{T}s" repeatCount="indefinite"/>{box(0, 0)}</g></g>')
        led = (f'<circle cx="727" cy="306" r="3.2" fill="#3a4a60">'
               f'<animate attributeName="fill" values="#3a4a60;#2de2c0;#3a4a60" keyTimes="0;{1.4/T:.4f};{2.6/T:.4f}" '
               f'calcMode="discrete" dur="{T}s" repeatCount="indefinite"/></circle>')
    else:
        tt = t % T
        infeed = box(PICK_X, GRASP_Y) if tt < 2.6 else ""
        outfeed = box(PLACE_X, GRASP_Y) if 5.4 <= tt < 6.8 else ""
        led = '<circle cx="727" cy="306" r="3.2" fill="#3a4a60"/>'

    belt_anim = ('<animate attributeName="stroke-dashoffset" values="0;-24" dur="0.9s" repeatCount="indefinite"/>'
                 if anim else "")

    def conveyor(x0: float, x1: float) -> str:
        return (f'<g><rect x="{x0}" y="{BELT_Y}" width="{x1-x0}" height="12" rx="6" fill="#18243a" stroke="#34465f"/>'
                f'<path d="M{x0+8} {BELT_Y+1}H{x1-8}" stroke="#4b6080" stroke-width="2" stroke-dasharray="6 6">{belt_anim}</path>'
                f'<circle cx="{x0+6}" cy="{BELT_Y+6}" r="4" fill="#2a3a52"/><circle cx="{x1-6}" cy="{BELT_Y+6}" r="4" fill="#2a3a52"/>'
                f'<rect x="{x0+14}" y="{BELT_Y+12}" width="5" height="{FLOOR_Y-BELT_Y-12}" fill="#1b2738"/>'
                f'<rect x="{x1-19}" y="{BELT_Y+12}" width="5" height="{FLOOR_Y-BELT_Y-12}" fill="#1b2738"/></g>')

    # HUD: state label and joint readout
    hud_x, hud_y = 560, 38
    if anim:
        states = "".join(f'<text x="{hud_x+150}" y="{hud_y}" opacity="0" fill="#ffb020">{visible(a, b)}{s}</text>'
                         for a, b, s in state_windows())
        readouts = []
        n = 32
        for i in range(n):
            qq = wrap(q_at(i * T / n))
            readouts.append(f'<text x="{hud_x}" y="{hud_y+22}" opacity="0">{visible(i*T/n, (i+1)*T/n)}'
                            f'q = [{qq[0]:+6.1f}°,{qq[1]:+6.1f}°,{qq[2]:+6.1f}°]</text>')
        readout = "".join(readouts)
        live = '<animate attributeName="opacity" values="1;.25;1" dur="1.6s" repeatCount="indefinite"/>'
        cursor = '<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;.5;.5;1" dur="1.1s" repeatCount="indefinite"/>'
    else:
        label = next(s for a, b, s in state_windows() if a <= t % T < b)
        states = f'<text x="{hud_x+150}" y="{hud_y}" fill="#ffb020">{label}</text>'
        qw = wrap(q)
        readout = f'<text x="{hud_x}" y="{hud_y+22}">q = [{qw[0]:+6.1f}°,{qw[1]:+6.1f}°,{qw[2]:+6.1f}°]</text>'
        live = cursor = ""

    chips, cx = [], 52.0
    for label, accent in (("HUMANOID ROBOTICS @ INFINEON", "#2de2c0"), ("EX-SIEMENS", "#9fb0c6"), ("EX-YASKAWA", "#9fb0c6")):
        w = len(label) * 7.9 + 24
        chips.append(f'<g transform="translate({cx:.1f},262)"><rect width="{w:.1f}" height="26" rx="13" fill="#111b2b" stroke="{accent}" stroke-opacity=".55"/>'
                     f'<text x="{w/2:.1f}" y="17.2" text-anchor="middle" fill="{accent}">{label}</text></g>')
        cx += w + 10

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
<title id="t">Sahil Malwanker — Robotics &amp; Automation Engineer</title>
<desc id="d">A three-joint robot arm picks boxes from an infeed conveyor and places them on an outfeed conveyor while a status readout shows its state and joint angles.</desc>
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0a0f1a"/><stop offset="1" stop-color="#0e1729"/></linearGradient>
<linearGradient id="steel" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#eef3f9"/><stop offset=".55" stop-color="#c4d0de"/><stop offset="1" stop-color="#8d9db2"/></linearGradient>
<linearGradient id="crate" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffc24d"/><stop offset="1" stop-color="#f09a00"/></linearGradient>
<radialGradient id="glow" cx="0.78" cy="0.55" r="0.5"><stop offset="0" stop-color="#2de2c0" stop-opacity=".10"/><stop offset="1" stop-color="#2de2c0" stop-opacity="0"/></radialGradient>
<pattern id="g1" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="#16233a" stroke-width="1"/></pattern>
<pattern id="g2" width="100" height="100" patternUnits="userSpaceOnUse"><path d="M100 0H0V100" fill="none" stroke="#1d2e4a" stroke-width="1"/></pattern>
<clipPath id="card"><rect width="{W}" height="{H}" rx="18"/></clipPath>
</defs>
<g clip-path="url(#card)">
<rect width="{W}" height="{H}" fill="url(#bg)"/>
<rect width="{W}" height="{H}" fill="url(#g1)"/><rect width="{W}" height="{H}" fill="url(#g2)"/>
<rect width="{W}" height="{H}" fill="url(#glow)"/>
<rect x="0" y="0" width="{W}" height="3" fill="#2de2c0" opacity=".8"/>

<g font-family="{MONO}" font-size="12.5" letter-spacing="2.4" fill="#2de2c0"><rect x="52" y="68" width="4" height="30" fill="#2de2c0"/>
<text x="66" y="80">ROBOTICS · DIGITAL TWINS</text><text x="66" y="97" fill="#9fb0c6">INDUSTRIAL AUTOMATION · INDUSTRIAL AI</text></g>
<text x="50" y="158" font-family="{SANS}" font-size="54" font-weight="700" fill="#e8eef6" letter-spacing="-0.5">Sahil Malwanker</text>
<text x="52" y="196" font-family="{SANS}" font-size="21" fill="#9fb0c6">Robotics &amp; Automation Engineer</text>
<text x="52" y="238" font-family="{MONO}" font-size="15" fill="#e8eef6"><tspan fill="#2de2c0">&gt; </tspan>simulate it. measure it. then move the robot.<tspan fill="#2de2c0">▍{cursor}</tspan></text>
<g font-family="{MONO}" font-size="11.5" letter-spacing="1">{"".join(chips)}</g>

<path d="M548 {FLOOR_Y}H1000" stroke="#22324a" stroke-width="1.5"/>
<path d="{trace}" fill="none" stroke="#2de2c0" stroke-opacity=".28" stroke-width="1.4" stroke-dasharray="2 5" stroke-linecap="round"/>
{conveyor(556, 735)}{conveyor(772, 838)}{led}
<g><path d="M{SX-34} {FLOOR_Y}L{SX-22} {SY+28}H{SX+22}L{SX+34} {FLOOR_Y}Z" fill="#162133" stroke="#2a3a52"/>
<rect x="{SX-46}" y="{FLOOR_Y-8}" width="92" height="8" rx="2" fill="#1d2b40"/>
<path d="M{SX-22} {SY+52}H{SX+22}" stroke="#2de2c0" stroke-opacity=".5" stroke-width="2"/></g>
<g stroke-width="2" stroke-linecap="round" transform="translate({SX+56},{FLOOR_Y-6})"><path d="M0 0h20" stroke="#ff5c5c"/><path d="M0 0v-20" stroke="#4aa3ff"/><circle r="2.4" fill="#e8eef6"/></g>
<text x="{SX}" y="{FLOOR_Y+15}" text-anchor="middle" font-family="{MONO}" font-size="10" fill="#6b7d96">base_link</text>
{infeed}{outfeed}
{arm}

<g font-family="{MONO}" font-size="12.5" fill="#9fb0c6">
<circle cx="{hud_x+4}" cy="{hud_y-4}" r="4" fill="#2de2c0">{live}</circle>
<text x="{hud_x+14}" y="{hud_y}" fill="#2de2c0">LIVE</text><text x="{hud_x+54}" y="{hud_y}">/cell/state</text>
{states}{readout}</g>
</g>
<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="18" fill="none" stroke="#22324a"/>
</svg>
'''


# --------------------------------------------------------------------------------------
# Light / dark themes for the transparent panels
# --------------------------------------------------------------------------------------
THEMES = {
    "dark": dict(text="#e6edf3", muted="#9198a1", faint="#3d444d", accent="#2de2c0", accent2="#ffb020",
                 chip="#151b23", chip_border="#30363d", node="#0d1117"),
    "light": dict(text="#1f2328", muted="#59636e", faint="#d1d9e0", accent="#0f8f7a", accent2="#b7700a",
                  chip="#f6f8fa", chip_border="#d1d9e0", node="#ffffff"),
}


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --------------------------------------------------------------------------------------
# Journey: career as a trajectory through waypoints
# --------------------------------------------------------------------------------------
WAYPOINTS = [
    # x, y, anchor, year, role, org, detail
    (60, 196, "start", "2016 – 2020", "B.E. Electrical & Electronics", "Goa College of Engineering", "electrical · electronics"),
    (240, 116, "middle", "2020 – 2023", "Application Development Engineer", "YASKAWA India · Bengaluru", "PLCs · motion control · cobots · 70+ projects"),
    (420, 196, "middle", "2024 – now", "M.Sc. EE & IT (Automation)", "Hochschule Darmstadt", "robotics · vision · control · IIoT"),
    (580, 116, "middle", "2025 – 2026", "Intern · Industrial Metaverse Lab", "Siemens AG · Munich", "LLM robot cell · digital twins"),
    (760, 196, "middle", "2026", "Working Student · Humanoid Robotics", "Infineon Technologies · Munich", "systems integration · benchmarking"),
    (940, 116, "end", "2026 – 2027", "Master's Thesis", "Infineon Technologies AG · Austria", "Virtualization in Humanoid Robotics"),
]


def catmull(points: list[tuple[float, float]]) -> list[tuple]:
    segs = []
    p = [points[0]] + points + [points[-1]]
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        segs.append((p1, c1, c2, p2))
    return segs


def bez_len(seg: tuple, n: int = 200) -> float:
    def at(u: float) -> tuple[float, float]:
        (x0, y0), (x1, y1), (x2, y2), (x3, y3) = seg
        a, b, c, d = (1 - u) ** 3, 3 * (1 - u) ** 2 * u, 3 * (1 - u) * u * u, u**3
        return a * x0 + b * x1 + c * x2 + d * x3, a * y0 + b * y1 + c * y2 + d * y3
    pts = [at(i / n) for i in range(n + 1)]
    return sum(math.dist(pts[i], pts[i + 1]) for i in range(n))


def journey(theme: str) -> str:
    c = THEMES[theme]
    pts = [(x, y) for x, y, *_ in WAYPOINTS]
    segs = catmull(pts)
    d = f"M{pts[0][0]} {pts[0][1]}" + "".join(
        f" C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]} {p2[1]}" for _, c1, c2, p2 in segs)
    lens = [bez_len(s) for s in segs]
    total = sum(lens)
    fr = [0.0]
    for ln in lens:
        fr.append(fr[-1] + ln / total)
    # travel 1.6 s per segment, dwell 0.9 s at each waypoint, rest at the end
    move, dwell = 1.6, 0.9
    times, keys, t = [0.0], [0.0], dwell
    times.append(t); keys.append(0.0)
    for i in range(1, len(fr)):
        t += move; times.append(t); keys.append(fr[i])
        t += dwell; times.append(t); keys.append(fr[i])
    t += 1.2; times.append(t); keys.append(1.0)
    dur = t
    kt = ";".join(f"{x / dur:.4f}" for x in times)
    kp = ";".join(f"{x:.4f}" for x in keys)

    labels = []
    for i, (x, y, anchor, year, role, org, detail) in enumerate(WAYPOINTS):
        up = y < 150
        y0 = 26 if up else 232
        now = "now" in year
        labels.append(
            f'<g text-anchor="{anchor}">'
            f'<text x="{x}" y="{y0}" font-family="{MONO}" font-size="12" letter-spacing="1.5" fill="{c["accent"]}">WP{i} · {esc(year)}</text>'
            f'<text x="{x}" y="{y0+23}" font-family="{SANS}" font-size="16" font-weight="700" fill="{c["text"]}">{esc(role)}</text>'
            f'<text x="{x}" y="{y0+43}" font-family="{SANS}" font-size="14" fill="{c["muted"]}">{esc(org)}</text>'
            f'<text x="{x}" y="{y0+62}" font-family="{MONO}" font-size="11.5" fill="{c["muted"]}" opacity=".85">{esc(detail)}</text>'
            f'</g>')
        stem_to = y - 12 if up else y + 12
        stem_from = y0 + 70 if up else y0 - 16
        labels.append(f'<path d="M{x} {stem_from}V{stem_to}" stroke="{c["faint"]}" stroke-dasharray="2 3"/>')
        ring = c["accent2"] if now or i == len(WAYPOINTS) - 1 else c["accent"]
        labels.append(f'<circle cx="{x}" cy="{y}" r="7" fill="{c["node"]}" stroke="{ring}" stroke-width="2.5"/>'
                      f'<circle cx="{x}" cy="{y}" r="2.6" fill="{ring}"/>')
    pulse = (f'<circle cx="{WAYPOINTS[-1][0]}" cy="{WAYPOINTS[-1][1]}" r="7" fill="none" stroke="{c["accent2"]}" stroke-width="2">'
             f'<animate attributeName="r" values="7;20" dur="1.8s" repeatCount="indefinite"/>'
             f'<animate attributeName="opacity" values=".9;0" dur="1.8s" repeatCount="indefinite"/></circle>')
    frame = (f'<g><animateMotion dur="{dur:.2f}s" repeatCount="indefinite" rotate="auto" keyPoints="{kp}" keyTimes="{kt}" calcMode="linear">'
             f'<mpath href="#traj"/></animateMotion>'
             f'<g stroke-width="2.4" stroke-linecap="round"><path d="M0 0h18" stroke="#ff5c5c"/><path d="M0 0v-18" stroke="#3ecf7a"/></g>'
             f'<circle r="4.5" fill="{c["accent"]}" stroke="{c["node"]}" stroke-width="1.5"/></g>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 310" width="1000" height="310" role="img" aria-labelledby="t">
<title id="t">Career trajectory: B.E. at Goa College of Engineering (2016–2020); Application Development Engineer at YASKAWA India (2020–2023); M.Sc. Automation at Hochschule Darmstadt (2024–now); Intern at the Siemens Industrial Metaverse Lab (2025–2026); Working Student in humanoid robotics at Infineon Technologies, Munich (2026); Master's thesis on virtualization in humanoid robotics at Infineon Technologies AG, Austria (2026–2027).</title>
<path id="traj" d="{d}" fill="none" stroke="{c["accent"]}" stroke-opacity=".55" stroke-width="2.2" stroke-dasharray="7 6" stroke-linecap="round"/>
{"".join(labels)}{pulse}{frame}
</svg>
'''


# --------------------------------------------------------------------------------------
# Toolchain: grouped chips
# --------------------------------------------------------------------------------------
TOOLS = [
    ("ROBOTICS & SIM", "#2de2c0", "#0f8f7a", ["ROS 2 Jazzy", "C++17", "NVIDIA Isaac Sim", "Omniverse · OpenUSD", "PhysX",
                                             "MuJoCo (WASM)", "Gazebo", "URDF · Xacro", "Process Simulate", "NX MCD", "Three.js"]),
    ("MOTION & CONTROL", "#4aa3ff", "#1f6fd1", ["FK · IK · Jacobians", "singularity analysis", "damped least squares",
                                               "state space · LQR", "system identification", "adaptive control (RLS)",
                                               "model-based control", "MATLAB · Simulink"]),
    ("INDUSTRIAL AUTOMATION", "#ffb020", "#b7700a", ["TIA Portal", "SIMATIC S7-1500", "IEC 61131-3 (LAD · FBD · ST)",
                                                    "WinCC HMI", "PLCSIM Advanced", "SIMIT", "Snap7 · TIA Openness",
                                                    "YASKAWA motion", "Industrial Edge"]),
    ("NETWORKS & IIOT", "#c084fc", "#8b3fd9", ["OPC UA", "PROFINET", "EtherNet/IP", "EtherCAT", "MECHATROLINK-III",
                                              "Modbus", "MQTT", "Node-RED", "OpenSearch"]),
    ("PERCEPTION & AI", "#ff7a90", "#c8324f", ["OpenCV", "stereo vision", "hand–eye calibration", "visual servoing",
                                              "policy learning (ES · ARS)", "scikit-learn", "LLM tool calling", "Azure OpenAI", "synthetic data"]),
    ("SOFTWARE", "#9fb0c6", "#59636e", ["Python", "C++", "TypeScript", "FastAPI", "React", "Docker", "Linux",
                                       "pytest · CI", "Git"]),
]


def toolchain(theme: str) -> str:
    c = THEMES[theme]
    left, right, cw, gap, rowh = 214, 990, 7.6, 8, 34
    out, y = [], 8
    for name, dark_acc, light_acc, items in TOOLS:
        acc = dark_acc if theme == "dark" else light_acc
        x, row_y, chips = left, y, []
        for item in items:
            w = len(item) * cw + 26
            if x + w > right:
                x, row_y = left, row_y + rowh
            chips.append(f'<g transform="translate({x:.1f},{row_y})"><rect width="{w:.1f}" height="26" rx="6" fill="{c["chip"]}" stroke="{c["chip_border"]}"/>'
                         f'<rect x="0" y="6" width="3" height="14" rx="1.5" fill="{acc}"/>'
                         f'<text x="{w/2+1.5:.1f}" y="17.5" text-anchor="middle">{esc(item)}</text></g>')
            x += w + gap
        out.append(f'<text x="0" y="{y+17.5}" font-family="{MONO}" font-size="12" letter-spacing="1.6" font-weight="700" fill="{acc}">{esc(name)}</text>')
        out.append(f'<g font-family="{MONO}" font-size="12.5" fill="{c["text"]}">{"".join(chips)}</g>')
        y = row_y + rowh + 14
    height = y - 6
    alt = "; ".join(f"{n.title()}: {', '.join(i)}" for n, _, _, i in TOOLS)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 {height}" width="1000" height="{height}" role="img" aria-labelledby="t">
<title id="t">Toolchain. {esc(alt)}</title>
{"".join(out)}
</svg>
'''


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    files = {
        "banner.svg": banner(),
        "banner-static.svg": banner(3.8),
        "journey-dark.svg": journey("dark"),
        "journey-light.svg": journey("light"),
        "toolchain-dark.svg": toolchain("dark"),
        "toolchain-light.svg": toolchain("light"),
    }
    if "--frames" in sys.argv:
        for t in (0.0, 1.5, 2.2, 3.2, 3.8, 4.4, 5.0, 5.9, 6.8):
            files[f"_frames/banner_t{t:.1f}.svg"] = banner(t)
    for name, text in files.items():
        path = ASSETS / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"  {name:28s} {len(text.encode()) / 1024:6.1f} KB")


if __name__ == "__main__":
    main()
