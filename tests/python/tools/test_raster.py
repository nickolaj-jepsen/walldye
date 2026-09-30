from PIL import Image

from walldye.tools import raster

NORD = {"bg": "#2E3440", "fg": "#ECEFF4", "accent": "#88C0D0"}
FIREPROOF_SEEDS = {"bg": "#1C1B1A", "fg": "#DAD8CE", "accent": "#CF6A4C"}

# --- rasterizing -------------------------------------------------------------------


def test_rasterize_ink_and_focus():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100" width="200" height="100">'
        '<rect x="0" y="0" width="200" height="100" fill="#000000"/>'
        '<rect x="150" y="0" width="50" height="50" fill="#FFFFFF"/></svg>'
    )
    img = raster.rasterize(svg, 100)
    assert img.mode == "RGB" and img.size == (100, 50)
    assert raster.focus(img, "#000000") == (0.875, 0.25)
    assert raster.focus(Image.new("RGB", (10, 10)), "#000000") == (0.5, 0.5)
    assert raster.rasterize(svg, 40, crop=(100, 0, 100, 100)).size == (40, 40)
    m = raster.ink_map(img, "#000000")
    assert m.shape == (64 * 36,) and abs((m @ m) - 1) < 1e-9
    assert raster.viewbox(svg) == "0 0 200 100" and raster.viewbox("<svg/>") is None
    assert raster.crop_svg(svg, (10, 20, 30, 40)).startswith(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="10 20 30 40" width="30" height="40">'
    )


def test_background_is_the_rect_after_the_defs():
    head = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 9" width="16" height="9">\n'
    rect = '<rect x="0" y="0" width="16" height="9" fill="#100F0F"/>\n'
    mask = '<defs><mask id="m1"><rect x="0" y="0" width="16" height="9" fill="#FFFFFF"/>'
    assert raster.background(head + rect + "</svg>\n") == "#100F0F"
    assert raster.background(head + mask + "</mask></defs>\n" + rect + "</svg>\n") == "#100F0F"
    assert raster.background(head + '<path d="M0 0H9"/>\n' + rect) == raster.FIREPROOF_BG
