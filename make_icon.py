"""Build-time: draw the GRWRP icon (reticle with a civilian shirt) -> icon.ico + icon.png."""
import sys, os
from PIL import Image, ImageDraw

BG, ACC, FG = '#1B1F24', '#D4A24C', '#E8EAEC'
SHIRT = [(96, 104), (114, 94), (142, 94), (160, 104), (172, 124), (156, 132), (150, 122),
         (150, 164), (106, 164), (106, 122), (100, 132), (84, 124)]

def draw(ticks=True, ring=14, ss=4):
    S = 256 * ss; k = ss
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((8 * k, 8 * k, 248 * k, 248 * k), radius=48 * k, fill=BG)
    d.ellipse((48 * k, 48 * k, 208 * k, 208 * k), outline=ACC, width=ring * k)
    if ticks:
        for x0, y0, x1, y1 in ((121, 28, 135, 64), (121, 192, 135, 228), (28, 121, 64, 135), (192, 121, 228, 135)):
            d.rectangle((x0 * k, y0 * k, x1 * k, y1 * k), fill=ACC)
    d.polygon([(x * k, y * k) for x, y in SHIRT], fill=FG)
    d.ellipse((118 * k, 88 * k, 138 * k, 104 * k), fill=BG)
    return im.resize((256, 256), Image.LANCZOS)

def main(out_dir):
    big, small = draw(), draw(ticks=False, ring=20)
    frames = [(small if s <= 24 else big).resize((s, s), Image.LANCZOS) for s in (16, 24, 32, 48, 64, 128, 256)]
    frames[-1].save(os.path.join(out_dir, 'icon.ico'), sizes=[(f.width, f.height) for f in frames],
                    append_images=frames[:-1])
    big.save(os.path.join(out_dir, 'icon.png'))

if __name__ == '__main__':
    main(sys.argv[1])
