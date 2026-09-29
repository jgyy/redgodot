"""Procedural texture atlas for one character (numpy + Pillow).

Every material role of a character is a small cell in ONE atlas texture (=> one draw
surface per character).  Two kinds of cell:

  ramp   the vertex's U picks the baked ambient-occlusion value (0 = deep crease, 1 = open)
         and V picks the part's gradient parameter g (root->tip of hair, hem->collar of
         cloth, ...).  The painter shades a base colour along both axes, so AO, hair strand
         gradients, clothing stripes and hem trims live in the texture and the toon shader
         needs no vertex colours.
  detail explicit planar uv (eyes, blush + freckles, emblems ...) painted with Pillow at 4x
         supersampling.

Cell coordinates are Blender UV space (origin bottom-left); `render()` flips to image rows.
"""
import colorsys
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

PAD = 3
SS = 4          # supersampling for detail cells


def hex2rgb(h):
    h = (h or '#888888').lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)])


def rgb2hex(c):
    c = np.clip(np.asarray(c), 0, 1)
    return '#%02x%02x%02x' % tuple(int(round(v * 255)) for v in c)


def shade(c, amt):
    """gfx.js shade(): hue-shifted lighten / darken (matches toon.gdshader)."""
    r, g, b = c
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    hd = h * 360.0
    if amt < 0:
        dh = ((250 - hd + 540) % 360) - 180
        hd, s, l = hd + dh * min(1, -amt) * 0.35, min(1, s * (1 - amt * 0.15)), max(0, l + amt * 0.5)
    else:
        dh = ((55 - hd + 540) % 360) - 180
        hd, s, l = hd + dh * min(1, amt) * 0.3, max(0, s * (1 - amt * 0.1)), min(1, l + amt * 0.5)
    return np.array(colorsys.hls_to_rgb((hd % 360) / 360.0, l, s))


def mix(a, b, t):
    t = np.asarray(t)
    if t.ndim == 2:
        t = t[..., None]
    return a * (1 - t) + b * t


def _ao_shade(col, A, strength=0.78, dark=None):
    """col: (h,w,3) or (3,) base; A: (h,w) 0..1 ao.  Creases go cool + darker."""
    col = np.broadcast_to(col, A.shape + (3,)) if np.ndim(col) == 1 else col
    if dark is None:
        dark = col * np.array([0.60, 0.56, 0.80])
    k = ((1.0 - A) ** 1.1 * strength)[..., None]
    return col * (1 - k) + dark * k


# ----------------------------------------------------------------------------- ramp painters
def ramp_flat(base, top=1.04, bottom=0.94, ao=0.75):
    base = hex2rgb(base) if isinstance(base, str) else base

    def f(A, G):
        c = base[None, None, :] * (bottom + (top - bottom) * G)[..., None]
        return _ao_shade(np.clip(c, 0, 1), A, ao)
    return f


def ramp_skin(base, ao=0.7):
    base = hex2rgb(base)

    def f(A, G):
        warm = np.array([1.0, 0.94, 0.92])
        c = base[None, None, :] * (0.95 + 0.07 * G)[..., None]
        c = mix(c, c * warm, (1 - G) * 0.5)
        dark = np.clip(base * np.array([0.86, 0.68, 0.70]), 0, 1)   # creases go rosy
        return _ao_shade(np.clip(c, 0, 1), A, ao, dark=np.broadcast_to(dark, A.shape + (3,)))
    return f


def ramp_hair(base, gloss=0.16, ring=0.30, ao=0.62):
    base = hex2rgb(base)
    hi = shade(base, 0.32)
    root = shade(base, -0.18)

    def f(A, G):
        c = np.broadcast_to(base, A.shape + (3,)).copy()
        c = mix(c, root, np.clip(1 - G * 2.6, 0, 1) * 0.8)
        band = np.exp(-((G - ring) / 0.09) ** 2) * gloss / 0.16
        c = mix(c, hi, np.clip(band, 0, 1) * 0.75)
        tip = np.clip((G - 0.7) / 0.3, 0, 1)
        c = c * (1 - 0.06 * tip)[..., None]
        return _ao_shade(np.clip(c, 0, 1), A, ao)
    return f


def ramp_cloth(base, stripes=None, top=1.06, bottom=0.92, hem=None, hem_w=0.08, ao=0.8, check=None):
    """stripes: list of (g0, g1, hex); hem: hex colour trim at g<hem_w (bottom edge)."""
    base = hex2rgb(base)
    st = [(a, b, hex2rgb(c)) for a, b, c in (stripes or [])]
    hemc = hex2rgb(hem) if hem else None

    def f(A, G):
        c = base[None, None, :] * (bottom + (top - bottom) * G)[..., None]
        c = np.broadcast_to(c, A.shape + (3,)).copy()
        for a, b, col in st:
            m = ((G >= a) & (G <= b))[..., None]
            c = np.where(m, col[None, None, :] * (bottom + (top - bottom) * G)[..., None], c)
        if hemc is not None:
            m = (G < hem_w)[..., None]
            c = np.where(m, hemc[None, None, :], c)
        return _ao_shade(np.clip(c, 0, 1), A, ao)
    return f


def ramp_metal(base, ao=0.7):
    base = hex2rgb(base)

    def f(A, G):
        band = 0.86 + 0.28 * (0.5 + 0.5 * np.sin(G * 9.0))
        c = base[None, None, :] * band[..., None]
        return _ao_shade(np.clip(c, 0, 1), A, ao)
    return f


def ramp_fur(base, ao=0.8):
    return ramp_flat(base, 1.08, 0.9, ao)


def ramp_ball(base='#e04040', ao=0.8):
    red = hex2rgb(base)

    def f(A, G):
        c = np.where((G > 0.56)[..., None], red[None, None, :], np.array([0.96, 0.96, 0.98])[None, None, :])
        c = np.where((np.abs(G - 0.5) <= 0.06)[..., None], np.array([0.12, 0.12, 0.16])[None, None, :], c)
        return _ao_shade(np.clip(c, 0, 1), A, ao)
    return f


RAMPS = {'ball': ramp_ball, 'flat': ramp_flat, 'skin': ramp_skin, 'hair': ramp_hair, 'cloth': ramp_cloth, 'metal': ramp_metal}


# ----------------------------------------------------------------------------- detail painters (PIL)
def _canvas(w, h, bg):
    return Image.new('RGBA', (w * SS, h * SS), tuple(int(v * 255) for v in bg) + (255,))


def _finish_detail(img, w, h):
    img = img.resize((w, h), Image.LANCZOS)
    return np.asarray(img.convert('RGB'), dtype=float) / 255.0


def _rgb255(c):
    return tuple(int(round(v * 255)) for v in np.clip(c, 0, 1))


def detail_eye(style='round', side=1, iris='#3a2a2a', skin='#f0b88a', lash=False, w=48, h=48,
               dark='#181420', glint='#ffffff', lid=None, pupil=True):
    """One eye texture.  The disc mesh maps u to the head's azimuth (u grows toward the
    character's LEFT/+X for side=+1 ... mirrored for side=-1), v = elevation."""
    skin_c, dark_c, iris_c = hex2rgb(skin), hex2rgb(dark), hex2rgb(iris)

    def paint():
        S = w * SS
        img = _canvas(w, h, skin_c)
        d = ImageDraw.Draw(img)
        cx, cy = S * 0.5, h * SS * 0.5
        rx, ry = S * 0.46, h * SS * 0.46
        if style == 'dot':
            rx, ry = S * 0.28, h * SS * 0.28
        elif style == 'narrow':
            ry = h * SS * 0.28
        elif style == 'sharp':
            ry = h * SS * 0.32
        elif style == 'tall':
            rx = S * 0.36
        elif style == 'sleepy':
            ry = h * SS * 0.40
        # sclera (some styles) + dark eye body
        white = style in ('white', 'sharp', 'lash')
        if white:
            d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(250, 248, 250))
            irx, iry = rx * 0.66, ry * 0.9
            if style == 'sharp':
                irx, iry = rx * 0.56, ry * 0.95
            d.ellipse([cx - irx, cy - iry, cx + irx, cy + iry], fill=_rgb255(iris_c * 0.85))
            d.ellipse([cx - irx * 0.72, cy - iry * 0.72, cx + irx * 0.72, cy + iry * 0.72], fill=_rgb255(iris_c))
            pr = irx * 0.42
            d.ellipse([cx - pr, cy - pr * 1.25, cx + pr, cy + pr * 1.25], fill=_rgb255(dark_c))
            d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=_rgb255(dark_c), width=int(SS * 1.6))
            d.ellipse([cx - irx * 0.55, cy - iry * 0.75, cx - irx * 0.05, cy - iry * 0.25], fill=(255, 255, 255))
        else:
            d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=_rgb255(dark_c))
            if style in ('round', 'oval', 'tall', 'sleepy') and iris != dark:
                # coloured iris ring low in the eye, dark pupil above it
                ir = ry * 0.86
                d.ellipse([cx - rx * 0.78, cy - ry * 0.05, cx + rx * 0.78, cy + ry * 0.92], fill=_rgb255(iris_c * 0.7))
                d.ellipse([cx - rx * 0.62, cy + ry * 0.12, cx + rx * 0.62, cy + ry * 0.86], fill=_rgb255(iris_c))
                d.ellipse([cx - rx * 0.28, cy - ry * 0.35, cx + rx * 0.28, cy + ry * 0.35], fill=_rgb255(dark_c))
            gx = cx - rx * 0.32 * side * 0
            d.ellipse([cx - rx * 0.62, cy - ry * 0.72, cx - rx * 0.06, cy - ry * 0.16], fill=(255, 255, 255))
            d.ellipse([cx + rx * 0.16, cy + ry * 0.25, cx + rx * 0.48, cy + ry * 0.55], fill=(235, 240, 255))
        if style == 'sleepy' or lid:
            # heavy upper lid painted in skin colour
            k = 0.30 if lid is None else lid
            d.rectangle([0, 0, S, cy - ry + 2 * ry * k], fill=_rgb255(skin_c * 0.97))
            d.line([(cx - rx, cy - ry + 2 * ry * k), (cx + rx, cy - ry + 2 * ry * k)], fill=_rgb255(dark_c), width=int(SS * 1.7))
        if lash:
            # upper lash line + outer flick
            d.arc([cx - rx * 1.05, cy - ry * 1.05, cx + rx * 1.05, cy + ry * 1.05], 200, 340, fill=_rgb255(dark_c), width=int(SS * 3))
            ox = cx + side * rx * 0.98
            d.line([(ox, cy - ry * 0.55), (ox + side * rx * 0.38, cy - ry * 0.95)], fill=_rgb255(dark_c), width=int(SS * 2.4))
        return _finish_detail(img, w, h)
    return paint


def detail_cheek(skin='#f0b88a', blush='#f08a80', freckles=False, w=24, h=24, strength=0.55):
    skin_c, bl = hex2rgb(skin), hex2rgb(blush)

    def paint():
        S = w * SS
        img = _canvas(w, h, skin_c)
        arr = np.asarray(img.convert('RGB'), dtype=float) / 255.0
        yy, xx = np.mgrid[0:h * SS, 0:S]
        r = np.sqrt(((xx - S / 2) / (S * 0.5)) ** 2 + ((yy - h * SS / 2) / (h * SS * 0.5)) ** 2)
        a = np.clip(1 - r, 0, 1) ** 1.2 * strength
        arr = arr * (1 - a[..., None]) + bl[None, None, :] * a[..., None]
        img = Image.fromarray((arr * 255).astype(np.uint8))
        if freckles:
            d = ImageDraw.Draw(img)
            rng = np.random.default_rng(11)
            for _ in range(7):
                px, py = rng.uniform(0.28, 0.72) * S, rng.uniform(0.3, 0.7) * h * SS
                rr = SS * rng.uniform(0.7, 1.1)
                d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=_rgb255(shade(skin_c, -0.30) * np.array([1.0, 0.8, 0.7])))
        return _finish_detail(img, w, h)
    return paint


def detail_mouth_open(dark='#5a1c28', tongue='#e0708a', w=24, h=24):
    dk, tg = hex2rgb(dark), hex2rgb(tongue)

    def paint():
        S = w * SS
        img = _canvas(w, h, dk)
        d = ImageDraw.Draw(img)
        d.ellipse([S * 0.2, h * SS * 0.5, S * 0.8, h * SS * 1.25], fill=_rgb255(tg))
        d.rectangle([S * 0.12, 0, S * 0.88, h * SS * 0.16], fill=(250, 248, 246))
        return _finish_detail(img, w, h)
    return paint


def _poke_ball(d, cx, cy, r, top='#e04040', S=1):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(250, 250, 252))
    d.pieslice([cx - r, cy - r, cx + r, cy + r], 180, 360, fill=tuple(int(v * 255) for v in hex2rgb(top)))
    d.rectangle([cx - r, cy - r * 0.11, cx + r, cy + r * 0.11], fill=(30, 30, 40))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(30, 30, 40), width=max(1, int(r * 0.11)))
    d.ellipse([cx - r * 0.3, cy - r * 0.3, cx + r * 0.3, cy + r * 0.3], fill=(250, 250, 252), outline=(30, 30, 40), width=max(1, int(r * 0.1)))


def detail_pokeball(bg='#d8383a', top='#e04040', w=32, h=32, ring=False):
    bgc = hex2rgb(bg)

    def paint():
        S = w * SS
        img = _canvas(w, h, bgc)
        d = ImageDraw.Draw(img)
        _poke_ball(d, S / 2, h * SS / 2, S * 0.36, top)
        return _finish_detail(img, w, h)
    return paint


def detail_letter_R(bg='#2a2a34', fg='#e04040', w=32, h=32):
    bgc, fgc = hex2rgb(bg), hex2rgb(fg)

    def paint():
        S = w * SS
        img = _canvas(w, h, bgc)
        d = ImageDraw.Draw(img)
        f = _rgb255(fgc)
        lw = S * 0.13
        x0, x1 = S * 0.28, S * 0.70
        y0, y1 = h * SS * 0.20, h * SS * 0.82
        ym = h * SS * 0.50
        d.rectangle([x0, y0, x0 + lw, y1], fill=f)
        d.rectangle([x0, y0, x1 - lw * 0.5, y0 + lw], fill=f)
        d.rectangle([x0, ym - lw * 0.5, x1 - lw * 0.5, ym + lw * 0.5], fill=f)
        d.arc([x1 - (ym - y0) - lw * 0.6, y0, x1 + lw * 0.5, ym + lw * 0.5], 270, 90, fill=f, width=int(lw * 1.05))
        d.polygon([(x0 + lw * 1.2, ym), (x0 + lw * 2.4, ym), (x1 + lw * 0.5, y1), (x1 - lw * 0.7, y1)], fill=f)
        return _finish_detail(img, w, h)
    return paint


def detail_cross(bg='#f4f4f8', fg='#e03848', w=32, h=32, round_=False):
    bgc, fgc = hex2rgb(bg), hex2rgb(fg)

    def paint():
        S = w * SS
        img = _canvas(w, h, bgc)
        d = ImageDraw.Draw(img)
        f = _rgb255(fgc)
        d.rectangle([S * 0.40, h * SS * 0.18, S * 0.60, h * SS * 0.82], fill=f)
        d.rectangle([S * 0.18, h * SS * 0.40, S * 0.82, h * SS * 0.60], fill=f)
        return _finish_detail(img, w, h)
    return paint


def detail_badge(bg='#e8c84a', fg='#b89020', w=32, h=32, star=True):
    bgc, fgc = hex2rgb(bg), hex2rgb(fg)

    def paint():
        S = w * SS
        img = _canvas(w, h, bgc)
        d = ImageDraw.Draw(img)
        cx, cy = S / 2, h * SS / 2
        if star:
            pts = []
            for i in range(10):
                r = S * (0.4 if i % 2 == 0 else 0.17)
                a = -math.pi / 2 + i * math.pi / 5
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
            d.polygon(pts, fill=_rgb255(fgc))
        else:
            d.ellipse([S * 0.2, S * 0.2, S * 0.8, S * 0.8], outline=_rgb255(fgc), width=int(SS * 2))
        return _finish_detail(img, w, h)
    return paint


def detail_lens(tint='#c8d8f0', w=24, h=24, dark=False):
    t = hex2rgb(tint)

    def paint():
        S = w * SS
        img = _canvas(w, h, t)
        d = ImageDraw.Draw(img)
        d.polygon([(S * 0.15, h * SS * 0.85), (S * 0.45, h * SS * 0.15), (S * 0.6, h * SS * 0.15), (S * 0.3, h * SS * 0.85)],
                  fill=_rgb255(np.clip(t * 1.25 + 0.15, 0, 1)))
        return _finish_detail(img, w, h)
    return paint


def detail_flat(color, w=8, h=8):
    c = hex2rgb(color)

    def paint():
        return np.broadcast_to(c, (h, w, 3)).copy()
    return paint


# ----------------------------------------------------------------------------- atlas
class Cell:
    def __init__(self, name, kind, w, h, fn):
        self.name, self.kind, self.w, self.h, self.fn = name, kind, w, h, fn
        self.x = self.y = 0


class Atlas:
    def __init__(self, size=256):
        self.size = size
        self.cells = {}
        self.order = []

    def ramp(self, name, style='flat', color='#888888', w=20, h=20, **kw):
        if name in self.cells:
            return self.cells[name]
        fn = RAMPS[style](color, **kw)
        c = Cell(name, 'ramp', w, h, fn)
        self.cells[name] = c
        self.order.append(name)
        return c

    def detail(self, name, painter, w, h):
        if name in self.cells:
            return self.cells[name]
        c = Cell(name, 'detail', w, h, painter)
        self.cells[name] = c
        self.order.append(name)
        return c

    def _pack(self):
        # shelf packing, tallest first
        cs = sorted(self.cells.values(), key=lambda c: (-c.h, -c.w))
        x = y = shelf = 0
        for c in cs:
            if x + c.w > self.size:
                x, y, shelf = 0, y + shelf, 0
            c.x, c.y = x, y
            x += c.w
            shelf = max(shelf, c.h)
        if y + shelf > self.size:
            raise ValueError('atlas overflow (%d rows)' % (y + shelf))

    def uv(self, name, ao=None, g=None, uv=None):
        """Per-vertex uv for a cell (Blender uv space)."""
        c = self.cells[name]
        S = float(self.size)
        iw, ih = c.w - 2 * PAD, c.h - 2 * PAD
        if c.kind == 'detail':
            u = np.clip(uv[:, 0], 0, 1)
            v = np.clip(uv[:, 1], 0, 1)
        else:
            u = np.clip(ao, 0, 1)
            v = np.clip(g, 0, 1)
        return np.stack([(c.x + PAD + 0.5 + u * (iw - 1)) / S, (c.y + PAD + 0.5 + v * (ih - 1)) / S], 1)

    def render(self):
        self._pack()
        S = self.size
        img = np.full((S, S, 3), 0.5)
        for c in self.cells.values():
            iw, ih = c.w - 2 * PAD, c.h - 2 * PAD
            if c.kind == 'ramp':
                xs = np.clip((np.arange(c.w) - PAD + 0.5) / iw, 0, 1)
                ys = np.clip((np.arange(c.h) - PAD + 0.5) / ih, 0, 1)
                A, G = np.meshgrid(xs, ys)
                arr = c.fn(A, G)
            else:
                arr = c.fn()
                if arr.shape[0] != c.h or arr.shape[1] != c.w:
                    arr = np.asarray(Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)).resize((c.w, c.h), Image.LANCZOS),
                                     dtype=float) / 255.0
                arr = np.flipud(arr)
                # replicate border into the padding
                inner = arr
                arr = np.pad(inner[PAD:c.h - PAD, PAD:c.w - PAD], ((PAD, PAD), (PAD, PAD), (0, 0)), mode='edge')
            img[c.y:c.y + c.h, c.x:c.x + c.w] = arr
        out = (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
        return np.flipud(out)      # row 0 of the PNG = top = uv v=1

    def save(self, path):
        Image.fromarray(self.render(), 'RGB').save(path, optimize=True)
