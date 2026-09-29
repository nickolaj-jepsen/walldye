"""Verstappen's 2024 Suzuka pole lap as a telemetry plot of speed, throttle and brake over distance, the heavy stops picked out on a track map."""

import numpy as np
from numpy.typing import NDArray
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import gaussian_filter1d

from walldye import (
    ACCENT,
    ACCENT_7,
    ACCENT_HI,
    BG,
    BG_ALT,
    UI,
    UI_ALT,
    UI_HI,
    Canvas,
    P,
    Paint,
    Rect,
    design,
)
from walldye.geom import Affine, Polyline
from walldye.pixel import glyphs, text_width

# Verstappen's 1:28.197 from FastF1 (2024 Japan Q): distance rescaled to 0..LAP, sampled every 10 m from the S/F line.
SPEED_VER = """
281 283 285 287 289 290 290 291 293 295 296 297 298 299 299 300 302 303 305 305 306 307 308 309 310 310 311 311 312
313 314 314 315 315 315 316 316 317 318 318 318 319 319 319 319 320 320 321 321 321 321 322 322 322 322 322 322 323
323 323 324 324 323 323 321 320 318 316 314 312 305 297 287 276 263 249 235 223 211 203 195 190 183 177 172 173 175
177 179 182 190 198 201 207 212 216 220 224 227 231 234 237 240 240 244 248 250 251 252 253 253 254 254 255 255 255
256 258 251 244 240 234 231 230 229 229 229 232 234 236 239 241 239 236 233 231 229 225 224 225 225 226 227 229 232
236 238 238 236 223 214 209 201 197 194 191 190 194 198 200 202 203 205 207 214 218 223 226 229 231 232 233 234 236
238 239 241 242 242 244 246 247 248 249 250 252 253 255 257 259 260 261 263 264 265 267 268 270 271 272 273 274 275
276 277 278 279 280 281 282 282 283 284 285 285 286 286 287 288 289 290 290 290 291 291 290 285 281 276 271 269 267
268 268 269 267 254 237 219 203 189 168 153 146 142 140 144 148 157 167 177 183 191 197 202 208 213 219 222 226 229
233 237 240 242 244 247 251 253 255 257 260 262 263 263 264 264 265 266 259 252 238 219 202 184 157 139 121 103 90 79
74 80 88 97 106 119 135 146 160 171 176 182 189 196 202 207 214 220 222 226 230 235 236 238 241 245 247 248 249 252
255 258 259 259 260 262 264 267 269 271 273 274 276 277 278 279 280 281 282 283 284 285 286 287 287 288 289 289 290
290 290 290 290 291 291 292 293 293 292 292 293 293 294 294 294 294 294 295 295 296 295 293 292 287 278 269 264 257
249 244 238 235 233 232 233 235 234 228 218 211 205 200 192 184 178 174 171 169 172 178 184 189 196 201 206 211 214
218 223 226 230 234 238 242 246 249 251 253 255 257 259 261 263 265 266 268 270 271 273 274 276 276 277 278 279 280
281 282 283 284 285 285 286 287 288 288 289 289 290 290 290 291 292 292 293 293 293 293 293 295 295 295 295 296 296
297 297 298 298 298 299 299 299 300 300 301 301 301 302 302 302 303 303 303 303 304 304 303 303 303 304 304 304 303
302 301 301 300 300 300 299 299 298 298 297 297 297 297 297 297 297 297 297 297 297 297 298 298 298 298 298 298 299
299 299 299 300 296 285 273 259 244 214 172 153 136 125 106 97 91 92 101 105 101 101 105 117 126 137 150 155 167 178
184 190 197 202 208 213 217 219 224 229 232 235 238 241 244 246 248 250 254 258 262 264 266 268 269 271 273
"""
# Perez, 1:28.263 on the same axis: drawn as the ghost under Verstappen's trace.
SPEED_PER = """
280 282 284 285 286 287 289 291 292 293 293 294 296 297 299 301 302 302 302 304 305 306 307 308 309 309 310 311 312
312 313 314 314 315 315 316 316 316 316 317 318 318 318 318 319 319 320 320 320 320 320 321 321 321 321 321 321 321
322 322 323 323 322 321 320 319 318 316 314 312 308 303 297 283 266 254 244 231 216 207 200 194 189 182 178 176 174
175 180 185 190 195 200 206 210 213 217 222 226 230 234 236 240 243 246 247 248 251 253 254 255 255 256 256 255 255
256 255 249 243 240 236 231 227 225 225 226 228 230 233 236 239 240 239 238 234 230 226 220 220 220 220 223 224 225
229 232 232 231 226 219 214 209 204 199 195 190 187 190 194 196 199 206 209 213 216 219 224 229 231 233 235 236 237
236 237 239 239 241 242 244 244 246 248 250 252 254 255 256 257 259 260 261 263 266 267 268 270 271 272 273 274 275
277 277 278 279 280 281 281 282 283 284 284 285 286 287 287 288 289 290 291 291 291 292 292 289 284 278 274 271 270
270 270 270 270 266 255 239 212 183 170 158 147 143 139 138 144 150 155 166 179 188 194 199 204 210 215 220 223 226
231 235 239 242 244 247 250 253 254 256 258 260 262 263 263 264 265 266 266 250 233 212 194 166 144 131 115 99 88 81
75 81 88 97 107 127 139 150 163 174 181 187 192 199 206 212 217 220 225 230 234 237 240 242 243 246 248 250 253 255
257 258 261 262 263 264 266 268 269 270 272 274 276 277 278 280 282 283 284 285 286 287 287 288 289 289 290 290 290
290 290 290 291 291 292 292 293 293 293 293 294 294 294 295 295 295 295 295 296 296 297 297 298 293 287 279 271 262
254 248 243 241 240 241 240 235 228 220 213 207 202 196 192 188 182 177 174 172 176 181 186 192 198 204 209 212 215
216 222 229 232 237 240 243 246 250 253 254 256 259 262 263 264 266 268 270 271 272 274 276 277 278 279 279 280 281
282 283 284 285 286 287 287 288 289 289 290 290 291 292 292 292 293 293 293 294 294 295 296 296 297 298 299 299 299
299 299 299 300 301 301 301 302 302 302 302 303 304 304 304 304 304 304 305 305 305 305 305 305 305 305 305 305 304
304 303 303 302 301 301 300 299 299 299 298 298 298 298 298 298 298 299 299 299 299 298 298 299 299 300 300 300 299
299 299 299 299 291 274 251 227 202 176 160 139 121 108 95 89 87 97 103 100 100 104 114 126 137 152 163 172 179 187
193 199 204 210 215 220 224 228 230 232 236 239 243 245 248 250 253 256 257 258 262 264 266 269 271 272 274
"""
THROTTLE = """
100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100
100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100
100 100 100 100 100 100 100 100 100 100 98 87 39 0 0 0 0 0 0 0 0 0 0 0 3 21 43 50 66 78 87 89 95 100 100 100 100 100
100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 58 0 16 27 28 35 46 62 78 84 90 95 100
100 100 94 75 54 29 35 44 56 69 83 90 95 99 100 100 100 98 75 14 0 0 0 0 0 6 40 80 79 79 80 83 90 95 100 100 100 100
100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100
100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 64 2 0
2 26 51 78 100 100 100 94 59 32 9 0 0 0 0 0 2 11 36 63 71 89 100 100 100 100 100 100 100 100 100 100 100 100 100 100
100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 61 21 0 0 0 0 0 0 0 0 0 0 18 30 45 59 71 89 100 100
100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100
100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100
100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 81 40 0 0 0 5 16 27 51 71 82 89 96 34 0 0 0 0 0 0
0 6 20 39 68 82 87 91 94 99 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100
100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100
100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100
100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100
100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 86 50 12 0 0 0 0 0 0 0 0 0 16 40 35 4 2 41 59 62 86 93 99
100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100 100
100
"""
# The f1-circuits Suzuka outline in east/north meters, starting at the S/F line.
TRACK = """
176,-91 551,-531 578,-565 591,-584 596,-594 603,-613 605,-627 605,-635 598,-670 592,-691 585,-704 574,-716 565,-722
556,-726 546,-729 536,-730 516,-728 508,-726 492,-717 478,-703 460,-675 420,-609 402,-584 383,-566 363,-554 342,-546
304,-542 287,-538 268,-529 254,-518 243,-503 239,-494 221,-437 213,-418 207,-407 194,-392 180,-383 161,-375 141,-371
96,-367 80,-364 73,-362 56,-353 48,-347 33,-333 27,-325 17,-305 14,-296 13,-280 18,-261 43,-193 46,-175 46,-165
43,-155 34,-135 23,-121 8,-109 -29,-91 -68,-77 -97,-72 -116,-70 -143,-70 -163,-72 -172,-74 -195,-80 -218,-90 -233,-97
-254,-110 -270,-123 -294,-150 -338,-208 -368,-245 -378,-256 -391,-266 -398,-269 -418,-274 -470,-283 -502,-287
-520,-286 -531,-284 -541,-280 -549,-275 -555,-268 -560,-258 -566,-241 -571,-204 -605,-44 -613,7 -613,36 -608,58
-600,78 -584,115 -579,134 -579,144 -584,153 -591,159 -599,162 -607,160 -616,155 -623,148 -628,140 -657,88 -693,34
-705,19 -720,3 -741,-14 -767,-29 -795,-37 -838,-42 -879,-42 -904,-38 -936,-31 -961,-23 -1004,-7 -1026,3 -1042,12
-1068,29 -1084,43 -1112,72 -1132,102 -1146,129 -1182,212 -1202,248 -1214,263 -1219,268 -1231,275 -1248,281 -1258,283
-1278,283 -1310,279 -1327,274 -1344,265 -1352,259 -1358,252 -1363,243 -1367,234 -1370,214 -1367,195 -1364,185
-1353,165 -1343,152 -1322,132 -1280,99 -1230,65 -1179,33 -1118,1 -1054,-29 -1000,-50 -565,-197 -548,-202 -529,-205
-508,-203 -485,-197 -462,-188 -443,-179 -411,-161 -382,-142 -360,-125 -298,-67 -237,-5 -222,7 -203,18 -194,21 -185,22
-176,21 -167,17 -149,6 -141,4 -132,4 -122,6 -114,10 -92,29 -75,40 -64,44 -47,48 -26,48 8,43 39,33 64,20 90,1 109,-15
128,-36
"""
# FastF1 Brake is boolean: (on_m, off_m) runs of VER's lap on the same distance axis.
BRAKE = [
    (688, 818),
    (1467, 1521),
    (2250, 2283),
    (2353, 2435),
    (2805, 2895),
    (3735, 3809),
    (3875, 3939),
    (5303, 5386),
]
LAP = 5807  # meters
X0, X1 = 160, 1330  # chart columns
SPEED, THR, BRK = (250, 560), (600, 700), (730, 800)  # panel tops and bottoms
PANELS = (SPEED, THR, BRK)
VMAX_KPH = 350
SECTORS = (2170, 4678)  # timing lines from the lap's sector times 30.777 / 39.850 / 17.570
CURSOR = 4994  # 130R
MAJOR_DROP = 90  # km/h shed per stop to count as a heavy braking zone
MAP_BOX = Rect(1370, 308, 390, 195)
MAP_ROT = 49  # degrees, FastF1's rotation for Suzuka

type F = NDArray[np.float64]


def floats(s: str) -> F:
    return np.array(s.split(), float)


def channel(s: str, sigma: float = 10) -> F:
    """10 m samples to a per-meter curve: pchip plus a light smooth so the 4 Hz steps vanish."""
    v = floats(s)
    x = np.arange(len(v) + 1) * 10.0
    f = PchipInterpolator(x, np.append(v, v[0]))
    return np.asarray(gaussian_filter1d(f(np.arange(LAP)), sigma, mode="wrap"), np.float64)


def brake_trace(kph: F) -> F:
    """Pressure 0..1 per meter: fast rise, peak by speed shed, bleeding off with speed into the apex."""
    b = np.zeros(LAP)
    for s0, s1 in BRAKE:
        m = np.arange(s0, s1)
        vin, vout = kph[s0], kph[s1]
        peak = np.clip(0.2 + (vin - vout) / 150, 0.2, 1)
        rise = np.minimum(1, (m - s0) / 10)
        fade = np.minimum(1, (s1 - m) / 14)
        b[m] = peak * rise * fade * (kph[m] / vin) ** 1.4
    return b


def stops(kph: F) -> list[tuple[int, int, bool]]:
    """Brake runs as (start, end, heavy); a re-application <150 m after a real stop (Spoon) joins it, a short tap (D1) never does."""
    merged: list[list[int]] = []
    for s0, s1 in BRAKE:
        if merged and s0 - merged[-1][1] < 150 and merged[-1][1] - merged[-1][0] > 40:
            merged[-1][1] = s1
        else:
            merged.append([s0, s1])
    out = []
    for s0, s1 in merged:
        drop = kph[max(0, s0 - 60) : s0 + 1].max() - kph[s0 : s1 + 40].min()
        out.append((s0, s1, bool(drop > MAJOR_DROP)))
    return out


def xpos(m: float) -> float:
    return X0 + m / LAP * (X1 - X0)


def trace(vals: F, lo: float, hi: float, y0: float, y1: float) -> F:
    """A per-meter channel decimated to ~1 px columns, as (N, 2) panel points."""
    idx = np.linspace(0, LAP - 1, X1 - X0 + 1).astype(int)
    xs = X0 + idx / (LAP - 1) * (X1 - X0)
    ys = y1 - (vals[idx] - lo) / (hi - lo) * (y1 - y0)
    return np.column_stack([xs, ys])


def track_line() -> Polyline:
    """The circuit fitted into MAP_BOX in FastF1's broadcast orientation (main straight on top, T1 right)."""
    pts = np.array([p.split(",") for p in TRACK.split()], float)
    r = (Affine.scale(1, -1) @ Affine.rotate(deg=MAP_ROT)).apply(pts)  # north is up on screen
    lo, hi = r.min(0), r.max(0)
    k = min(MAP_BOX.w / (hi[0] - lo[0]), MAP_BOX.h / (hi[1] - lo[1]))
    return Polyline((r - (lo + hi) / 2) * k + MAP_BOX.center, closed=True)


def label(s: Canvas, txt: str, paint: Paint, x: float, y: float, anchor: str = "start") -> None:
    """5x8 text placed like glyphs' anchor, its origin rounded to whole pixels."""
    shift = {"start": 0.0, "middle": 0.5, "end": 1.0}[anchor]
    x -= shift * text_width(txt, font="5x8", px=1)
    glyphs(s, txt, paint, at=(round(x), round(y)), font="5x8", px=1)


@design()
def draw(s: Canvas) -> None:
    kph, ref = channel(SPEED_VER), channel(SPEED_PER)
    steps = np.interp(np.arange(LAP), np.arange(0, LAP, 10), floats(THROTTLE))
    thr = gaussian_filter1d(steps, 3, mode="wrap") / 100
    brk = brake_trace(kph)
    zones = stops(kph)

    def vy(kmh: float) -> float:
        return SPEED[1] - kmh / VMAX_KPH * (SPEED[1] - SPEED[0])

    grid = P()
    for g in range(50, VMAX_KPH, 50):
        grid.M(X0, vy(g)).H(X1)
    s.stroke(grid, BG_ALT, 1)
    sec = P()
    for m in SECTORS:
        for y0, y1 in PANELS:
            sec.M(round(xpos(m)) + 0.5, y0).V(y1)
    s.stroke(sec, UI, 1, dash=(4, 6))

    s.stroke(P().poly(trace(thr, 0, 1, THR[0] + 4, THR[1])), UI_ALT, 1, join="round")
    s.stroke(P().poly(trace(ref, 0, VMAX_KPH, *SPEED)), UI_ALT, 1)
    s.stroke(P().poly(trace(kph, 0, VMAX_KPH, *SPEED)), UI_HI, 1.5, join="round")

    # brake: light taps in UI_HI, the heavy stops filled and traced in the accent
    s.stroke(P().M(X0, BRK[1] - 0.5).H(X1), UI_ALT, 1)
    bp = trace(brk, 0, 1, BRK[0] + 4, BRK[1])
    taps, hard, wells = P(), P(), P()
    for s0, s1, heavy in zones:
        seg = bp[(bp[:, 0] >= xpos(s0 - 4)) & (bp[:, 0] <= xpos(s1 + 4))]
        if heavy:
            foot = [(seg[-1, 0], BRK[1]), (seg[0, 0], BRK[1])]
            wells.poly(np.vstack([seg, foot]), closed=True)
            hard.poly(seg)
        else:
            taps.poly(seg)
    s.fill(wells, ACCENT_7)
    s.stroke(taps, UI_HI, 1, join="round")
    s.stroke(hard, ACCENT, 1.5, join="round")

    frames = P()
    for y0, y1 in PANELS:
        frames.rect(X0, y0, X1 - X0, y1 - y0)
    s.stroke(frames, UI, 1)

    for name, (top, _) in zip(("KM/H", "THR", "BRK"), PANELS):
        label(s, name, UI_HI, X0 + 8, top + 7)
    label(s, "0", UI_HI, X0, BRK[1] + 8)
    label(s, str(LAP), UI_HI, X1, BRK[1] + 8, "end")
    for g in range(100, VMAX_KPH, 100):
        label(s, str(g), UI, X0 - 7, round(vy(g)) - 4, "end")
    edges = (0, *SECTORS, LAP)
    for i in range(3):
        label(s, f"S{i + 1}", UI_HI, xpos((edges[i] + edges[i + 1]) / 2), BRK[1] + 8, "middle")

    # cursor at 130R with a speed / throttle / brake readout above the panels
    cx = round(xpos(CURSOR)) + 0.5
    tag_y, cw = SPEED[0] - 30, 30
    s.stroke(P().M(cx, tag_y + 18).V(BRK[1]), UI_HI, 1)
    cells = (f"{kph[CURSOR]:.0f}", f"{thr[CURSOR] * 100:.0f}", f"{brk[CURSOR] * 100:.0f}")
    bx = cx - cw * len(cells) / 2
    s.path(P().rect(bx, tag_y, cw * len(cells), 18), fill=BG, stroke=UI_HI, stroke_width=1)
    s.stroke(P().M(bx + cw, tag_y).V(tag_y + 18).M(bx + 2 * cw, tag_y).V(tag_y + 18), UI, 1)
    for i, txt in enumerate(cells):
        label(s, txt, ACCENT if i == 2 else UI_HI, bx + (i + 0.5) * cw, tag_y + 5, "middle")

    # inset map: S/F tick, the heavy stops and the cursor
    track = track_line()
    k = track.length / LAP
    s.stroke(P().poly(track.pts, closed=True), UI_ALT, 1.25, join="round")
    sf, n = track.at(0), track.tangent(0).perp() * 6
    s.stroke(P().M(sf - n).L(sf + n), UI_HI, 1.5)
    zp = P()
    for s0, s1, heavy in zones:
        if heavy:
            zp.poly(track.at(np.arange(s0, s1 + 1, 3) * k))
    s.stroke(zp, ACCENT, 2, cap="round", join="round")
    s.fill(P().circle(track.at(CURSOR * k), 3.5), ACCENT_HI)
