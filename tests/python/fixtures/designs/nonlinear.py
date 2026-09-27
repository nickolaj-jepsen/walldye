"""A ground set to the per-channel maximum of two tokens: no linear mix, so no slot formula fits."""

from walldye import ACCENT, BG, H, W, hex_to_rgb, rgb_to_hex


def draw(s):
    s.rect(0, 0, W, H, fill=rgb_to_hex(*(max(a, b) for a, b in zip(hex_to_rgb(BG), hex_to_rgb(ACCENT)))))
