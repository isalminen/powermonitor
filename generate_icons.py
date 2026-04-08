#!/usr/bin/env python3
"""
generate_icons.py
Generates cartoonish Home Assistant integration icons for the Power Monitor.

Outputs:
  custom_components/powermonitor/brand/icon.png      256 x 256
  custom_components/powermonitor/brand/icon@2x.png   512 x 512
"""

import math
import os
from PIL import Image, ImageDraw, ImageFilter

OUT_DIR = os.path.join(os.path.dirname(__file__),
                       "custom_components", "powermonitor", "brand")
os.makedirs(OUT_DIR, exist_ok=True)

# ── colour palette ─────────────────────────────────────────────────────────────
BG_TOP      = (30,  40, 100)   # deep indigo (top of background gradient)
BG_BOT      = (20,  90, 200)   # electric blue (bottom)
METER_BODY  = (240, 245, 255)  # near-white card
METER_FACE  = (252, 254, 255)  # slightly brighter inner face
ARC_TRACK   = (200, 215, 230)  # gauge background arc
ARC_GREEN   = ( 56, 200, 120)  # low-power zone
ARC_YELLOW  = (255, 210,  40)  # mid-power zone
ARC_RED     = (255,  70,  60)  # high-power zone
NEEDLE_COL  = (220,  50,  50)  # dial needle
PIVOT_DARK  = ( 45,  55,  80)  # needle pivot (dark)
PIVOT_LIGHT = (230, 240, 255)  # needle pivot (bright dot)
BOLT_FILL   = (255, 220,  30)  # lightning bolt fill
BOLT_EDGE   = (230, 140,   0)  # lightning bolt outline / shadow
BLE_BLUE    = ( 80, 180, 255)  # BLE signal waves
DISP_BG     = ( 18,  28,  52)  # digital display background
DISP_SEG    = (  0, 230, 100)  # LED-green display segments
WHITE       = (255, 255, 255)
SHADOW      = (  0,   0,   0,  60)   # RGBA


# ── helpers ────────────────────────────────────────────────────────────────────

def rr(draw: ImageDraw.ImageDraw, xy, r, fill=None, outline=None, width=1):
    """Filled and/or outlined rounded rectangle."""
    x0, y0, x1, y1 = xy
    r = max(r, 1)
    if fill:
        draw.rectangle([x0 + r, y0, x1 - r, y1], fill=fill)
        draw.rectangle([x0, y0 + r, x1, y1 - r], fill=fill)
        for cx, cy in [(x0+r, y0+r), (x1-r, y0+r),
                       (x0+r, y1-r), (x1-r, y1-r)]:
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
    if outline:
        draw.rounded_rectangle([x0, y0, x1, y1], radius=r,
                               outline=outline, width=width)


def gradient_bg(size):
    """Vertical linear-gradient RGBA image."""
    img = Image.new("RGBA", (size, size))
    for y in range(size):
        t = y / (size - 1)
        r = int(BG_TOP[0] + t * (BG_BOT[0] - BG_TOP[0]))
        g = int(BG_TOP[1] + t * (BG_BOT[1] - BG_TOP[1]))
        b = int(BG_TOP[2] + t * (BG_BOT[2] - BG_TOP[2]))
        for x in range(size):
            img.putpixel((x, y), (r, g, b, 255))
    return img


def arc_thick(draw, cx, cy, radius, start_deg, end_deg, color, width, steps=400):
    """Smooth thick arc drawn as a series of line segments."""
    pts = []
    for i in range(steps + 1):
        t = i / steps
        angle = math.radians(start_deg + t * (end_deg - start_deg))
        pts.append((cx + radius * math.cos(angle),
                    cy + radius * math.sin(angle)))
    draw.line(pts, fill=color, width=width, joint="curve")


def bolt_polygon(cx, cy, w, h):
    """Six-point lightning-bolt polygon centred roughly at (cx, cy)."""
    return [
        (cx + w * 0.22,  cy - h * 0.50),   # top-right
        (cx - w * 0.20,  cy - h * 0.02),   # mid-left
        (cx + w * 0.10,  cy - h * 0.02),   # mid-right notch
        (cx - w * 0.22,  cy + h * 0.50),   # bottom-left
        (cx + w * 0.20,  cy + h * 0.02),   # mid-right
        (cx - w * 0.10,  cy + h * 0.02),   # mid-left notch
    ]


# ── main drawing function ──────────────────────────────────────────────────────

def draw_icon(size: int) -> Image.Image:
    s = size
    sc = s / 512          # scale factor relative to 512-px master
    half = s // 2

    # ── 1. Rounded-square background ─────────────────────────────────────────
    base = gradient_bg(s)
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, s - 1, s - 1], radius=int(90 * sc), fill=255)
    base.putalpha(mask)

    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    img.paste(base, mask=base)
    draw = ImageDraw.Draw(img, "RGBA")

    # Subtle white inner-glow ring
    draw.rounded_rectangle(
        [int(6*sc), int(6*sc), s - int(6*sc), s - int(6*sc)],
        radius=int(85 * sc),
        outline=(255, 255, 255, 35),
        width=max(1, int(3 * sc)))

    # ── 2. Meter body card ────────────────────────────────────────────────────
    pad = int(52 * sc)
    card = (pad, pad, s - pad, s - pad)
    card_r = int(36 * sc)

    # drop shadow
    shadow_img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_img, "RGBA")
    so = int(7 * sc)
    rr(sd, (card[0]+so, card[1]+so, card[2]+so, card[3]+so),
       card_r, fill=(0, 0, 0, 70))
    shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(int(8 * sc)))
    img = Image.alpha_composite(img, shadow_img)
    draw = ImageDraw.Draw(img, "RGBA")

    # card body
    rr(draw, card, card_r, fill=METER_BODY)
    inner_pad = int(14 * sc)
    rr(draw, (card[0]+inner_pad, card[1]+inner_pad,
              card[2]-inner_pad, card[3]-inner_pad),
       max(card_r - 8, 4), fill=METER_FACE)

    # thin top accent stripe
    stripe_h = int(22 * sc)
    stripe_img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    si = ImageDraw.Draw(stripe_img, "RGBA")
    rr(si, card, card_r, fill=(*BG_BOT, 220))
    si.rectangle([card[0], card[1]+stripe_h, card[2], card[3]], fill=(0,0,0,0))
    img = Image.alpha_composite(img, stripe_img)
    draw = ImageDraw.Draw(img, "RGBA")

    # ── 3. Gauge arcs ─────────────────────────────────────────────────────────
    cx   = half
    cy   = int(305 * sc)
    gr   = int(135 * sc)        # gauge radius
    aw   = max(int(22 * sc), 4) # arc stroke width

    # background track
    arc_thick(draw, cx, cy, gr, 205, 335, ARC_TRACK, aw)

    # coloured zones
    arc_thick(draw, cx, cy, gr, 205, 254, ARC_GREEN,  aw)
    arc_thick(draw, cx, cy, gr, 256, 288, ARC_YELLOW, aw)
    arc_thick(draw, cx, cy, gr, 290, 335, ARC_RED,    aw)

    # tick marks (minor)
    for angle_deg in range(205, 336, 13):
        angle = math.radians(angle_deg)
        r_inner = gr - aw // 2 - int(6 * sc)
        r_outer = gr - aw // 2 - int(18 * sc)
        draw.line(
            [(cx + r_inner * math.cos(angle), cy + r_inner * math.sin(angle)),
             (cx + r_outer * math.cos(angle), cy + r_outer * math.sin(angle))],
            fill=(130, 145, 165), width=max(1, int(2 * sc)))

    # ── 4. Needle (pointing to yellow zone, ~265°) ────────────────────────────
    needle_angle = math.radians(262)
    needle_len   = int(108 * sc)
    nx = cx + needle_len * math.cos(needle_angle)
    ny = cy + needle_len * math.sin(needle_angle)

    # shadow
    draw.line([(cx+int(2*sc), cy+int(2*sc)),
               (nx+int(2*sc), ny+int(2*sc))],
              fill=(0, 0, 0, 80), width=max(int(6*sc), 3))
    # needle
    draw.line([(cx, cy), (nx, ny)],
              fill=NEEDLE_COL, width=max(int(5*sc), 2))

    # pivot circles
    pr = int(11 * sc)
    draw.ellipse([cx-pr, cy-pr, cx+pr, cy+pr], fill=PIVOT_DARK)
    pr2 = int(5 * sc)
    draw.ellipse([cx-pr2, cy-pr2, cx+pr2, cy+pr2], fill=PIVOT_LIGHT)

    # ── 5. Lightning bolt ─────────────────────────────────────────────────────
    bx, by = half, int(185 * sc)
    bw, bh = int(78 * sc), int(110 * sc)

    # outer glow (soft, yellow-orange)
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(glow, "RGBA")
    for g_expand in range(int(14*sc), 0, -1):
        alpha = int(18 - g_expand * 18 // int(14*sc))
        pts_g = bolt_polygon(bx, by, bw + g_expand*2, bh + g_expand*2)
        gd.polygon(pts_g, fill=(255, 200, 0, alpha))
    glow = glow.filter(ImageFilter.GaussianBlur(int(6 * sc)))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img, "RGBA")

    # shadow
    shadow_pts = [(x + int(3*sc), y + int(3*sc))
                  for x, y in bolt_polygon(bx, by, bw, bh)]
    draw.polygon(shadow_pts, fill=(180, 100, 0, 100))

    # bolt fill
    pts = bolt_polygon(bx, by, bw, bh)
    draw.polygon(pts, fill=BOLT_FILL)
    draw.polygon(pts, outline=BOLT_EDGE, width=max(int(2*sc), 1))

    # ── 6. Digital display bar ────────────────────────────────────────────────
    disp_w = int(200 * sc)
    disp_h = int(40 * sc)
    dx0 = cx - disp_w // 2
    dy0 = int(368 * sc)
    disp_r = int(8 * sc)
    rr(draw, (dx0, dy0, dx0+disp_w, dy0+disp_h), disp_r, fill=DISP_BG)

    # LED segment bars  (stylised "1.2 kW")
    seg_defs = [
        (30,  10, 0.55),   # "1"
        (42,   4, 0.35),   # "."
        (56,  10, 0.55),   # "2"
        (72,   5, 0.30),   # gap
        (82,   9, 0.50),   # "k"
        (96,   9, 0.50),   # "W"
    ]
    for rel_x, seg_w, seg_h_ratio in seg_defs:
        sx  = dx0 + int(rel_x * sc)
        sw  = max(int(seg_w * sc), 2)
        sh  = max(int(disp_h * seg_h_ratio), 2)
        sy0 = dy0 + (disp_h - sh) // 2
        draw.rounded_rectangle(
            [sx, sy0, sx + sw, sy0 + sh],
            radius=max(int(2*sc), 1), fill=DISP_SEG)

    # ── 7. BLE signal arcs (top-right corner of card) ─────────────────────────
    ble_cx = int(400 * sc)
    ble_cy = int(126 * sc)

    for i, wave_r in enumerate([int(11*sc), int(20*sc), int(30*sc)]):
        alpha = 220 - i * 55
        col   = (*BLE_BLUE, alpha)
        arc_thick(draw, ble_cx, ble_cy, wave_r, 250, 340,
                  col, max(int(3*sc), 1), steps=60)

    dot_r = max(int(4 * sc), 2)
    draw.ellipse([ble_cx-dot_r, ble_cy-dot_r, ble_cx+dot_r, ble_cy+dot_r],
                 fill=(*BLE_BLUE, 255))

    return img


# ── entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    for filename, size in [("icon.png", 256), ("icon@2x.png", 512)]:
        icon = draw_icon(size)
        path = os.path.join(OUT_DIR, filename)
        icon.save(path, "PNG", optimize=True)
        print(f"Saved  {path}  ({size}×{size})")
