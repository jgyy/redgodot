"""Painted realistic eyes.

The eye patch is an almond lifted onto the eyeball dome.  (t, y) are the shared almond coordinates: t 0..1 runs across
the opening in +X order, y in [EYE_YLO, EYE_YHI] is height (0 = the lid line at rest).  char_face builds the mesh from
the same curves, so the painted outline and the geometry always agree.
"""
import numpy as np
from PIL import Image

from char_paint import hex2rgb, SS

EYE_YLO, EYE_YHI = -0.62, 1.0

EYE_STYLES = {
    'round':      dict(top=0.92, bot=0.70, tilt=0.00, iris=0.235, droop=0.16, lash=2.6),
    'big':        dict(top=1.00, bot=0.78, tilt=0.00, iris=0.27, droop=0.10, lash=2.8),
    'oval':       dict(top=0.84, bot=0.66, tilt=0.05, iris=0.22, droop=0.20, lash=2.4),
    'tall':       dict(top=0.98, bot=0.74, tilt=0.00, iris=0.22, droop=0.12, lash=2.5),
    'narrow':     dict(top=0.62, bot=0.50, tilt=0.03, iris=0.20, droop=0.30, lash=2.4),
    'sharp':      dict(top=0.70, bot=0.52, tilt=0.20, iris=0.215, droop=0.28, lash=3.0),
    'sleepy':     dict(top=0.68, bot=0.62, tilt=-0.06, iris=0.22, droop=0.42, lash=2.6),
    'dot':        dict(top=0.60, bot=0.50, tilt=0.00, iris=0.19, droop=0.22, lash=2.2),
    'lash':       dict(top=0.96, bot=0.72, tilt=0.14, iris=0.245, droop=0.14, lash=3.6, flick=True),
    'lash_white': dict(top=0.92, bot=0.70, tilt=0.14, iris=0.235, droop=0.16, lash=3.8, flick=True),
}


def eye_curves(style, n=40):
    """Upper / lower almond boundary as (t, y) arrays for a style."""
    s = EYE_STYLES.get(style, EYE_STYLES['round'])
    t = np.linspace(0, 1, n)
    top = s['top'] * np.sin(np.pi * t) ** 0.85 + s['tilt'] * (t - 0.5) * 1.6 * np.sin(np.pi * t) ** 0.5
    bot = -s['bot'] * 0.62 * np.sin(np.pi * t) ** 1.15 + s['tilt'] * (t - 0.5) * 0.6 * np.sin(np.pi * t)
    return t, np.clip(top, 0, EYE_YHI), np.clip(bot, EYE_YLO, 0)


def detail_eye_real(style='round', side=1, iris='#4a3a2a', skin='#f0b88a', lash=False, dark='#181420', w=72, h=44,
                    sclera='#ece9e4'):
    st = EYE_STYLES.get(style, EYE_STYLES['round'])
    iris_c, dark_c, skin_c, scl = hex2rgb(iris), hex2rgb(dark), hex2rgb(skin), hex2rgb(sclera)
    lash_w = st['lash'] * (1.25 if lash else 1.0)

    def paint():
        W, H = w * SS, h * SS
        t, top, bot = eye_curves(style, 60)

        def Y(yy):
            return (EYE_YHI - yy) / (EYE_YHI - EYE_YLO) * (H - 1)
        yy, xx = np.mgrid[0:H, 0:W]
        tt = xx / (W - 1.0)
        yv = EYE_YHI - yy / (H - 1.0) * (EYE_YHI - EYE_YLO)
        tu = np.interp(tt, t, top)
        tb = np.interp(tt, t, bot)
        inside = (yv <= tu) & (yv >= tb)
        img = np.broadcast_to(skin_c, (H, W, 3)).copy()
        # sclera with lid shadow and pink corners
        edge_top = np.clip((tu - yv) / 0.45, 0, 1)
        shade = 0.72 + 0.28 * edge_top ** 0.6
        inner = 0.0 if side > 0 else 1.0
        corner = np.exp(-((tt - inner) / 0.16) ** 2) * 0.5 + np.exp(-((tt - (1.0 - inner)) / 0.12) ** 2) * 0.22
        sc = scl[None, None, :] * shade[..., None]
        sc = sc * (1 - corner[..., None]) + np.array([0.86, 0.5, 0.48])[None, None, :] * corner[..., None]
        img = np.where(inside[..., None], sc, img)
        # iris
        icx = 0.5 + (0.03 if side > 0 else -0.03)
        icy = st['top'] * 0.5 - 0.03
        R = st['iris'] * W
        dx, dy = xx - icx * (W - 1), yy - Y(icy)
        rr = np.sqrt(dx * dx + dy * dy) / R
        ang = np.arctan2(dy, dx)
        streak = 0.5 + 0.5 * np.sin(ang * 23 + np.sin(ang * 7) * 2)
        body = iris_c[None, None, :] * (0.78 + 0.5 * (1 - np.clip(rr, 0, 1)) ** 1.5)[..., None]
        body = body * (0.92 + 0.16 * streak)[..., None]
        ring = np.clip((rr - 0.78) / 0.22, 0, 1)
        body = body * (1 - 0.62 * ring[..., None]) + dark_c[None, None, :] * 0.35 * ring[..., None]
        pupil = np.clip(1 - (rr - 0.38) / 0.05, 0, 1)
        body = body * (1 - pupil[..., None]) + dark_c[None, None, :] * pupil[..., None]
        is_iris = (rr <= 1.0) & inside
        img = np.where(is_iris[..., None], body, img)
        # highlights
        hx, hy = -0.34 * R, -0.38 * R
        h1 = np.clip(1 - np.sqrt(((dx - hx) / (0.30 * R)) ** 2 + ((dy - hy) / (0.27 * R)) ** 2), 0, 1)
        h2 = np.clip(1 - np.sqrt(((dx + 0.42 * R) / (0.13 * R)) ** 2 + ((dy - 0.46 * R) / (0.11 * R)) ** 2), 0, 1) * 0.55
        hl = np.clip(np.maximum(h1 * 3, h2 * 2), 0, 1) * inside
        img = img * (1 - hl[..., None]) + np.ones(3)[None, None, :] * hl[..., None]
        # upper lid shadow over the iris
        lidshade = np.clip(1 - (tu - yv) / (0.10 + st['droop'] * 0.5), 0, 1) ** 1.6 * 0.5
        img = np.where(inside[..., None], img * (1 - lidshade[..., None]), img)
        # lash line (thicker toward the outer corner) and the faint lower lid
        outer = 1.0 if side > 0 else 0.0
        k = np.abs(tt - outer)
        lw = (lash_w * SS / (H - 1.0)) * (EYE_YHI - EYE_YLO) * (0.55 + 0.9 * (1 - k))
        if st.get('flick'):
            lw = lw * (1 + 0.8 * np.exp(-(k / 0.18) ** 2))
        line = np.clip(1 - np.clip(tu - yv, 0, None) / np.maximum(lw, 1e-3), 0, 1) * inside
        line = np.clip(line * 1.6, 0, 1)
        img = img * (1 - line[..., None]) + dark_c[None, None, :] * 0.9 * line[..., None]
        lowl = np.clip(1 - np.clip(yv - tb, 0, None) / 0.07, 0, 1) * inside * 0.35
        img = img * (1 - lowl[..., None]) + dark_c[None, None, :] * lowl[..., None]
        out = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS)
        return np.asarray(out, dtype=float) / 255.0
    return paint
