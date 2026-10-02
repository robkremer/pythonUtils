'''
Draw the documentation's logo and favicon -- two meshing gears, in blue and
yellow, set on the diagonal (a nod to Python's logo, for a library of Python
utilities) -- as sphinx/source/images/pu-logo.png and pu-favicon.png.

Needs Pillow. Run from the project's top folder::

  python3 sphinx/makeLogo.py

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''
import math, os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
IMAGES = os.path.join(HERE, "source", "images")

BLUE = (55, 118, 171, 255)    # (Python's blue and yellow)
YELLOW = (255, 212, 59, 255)
OUTLINE = (34, 52, 80, 255)

def gear(d:ImageDraw.ImageDraw, cx:float, cy:float, outer:float, root:float, teeth:int, phase:float,
         fill, hole:float) -> None:
  '''
  Draw a gear: *teeth* trapezoidal teeth between radii *root* and *outer*,
  turned by *phase* (radians), with a hole of radius *hole* in the middle.
  '''
  pts = []
  step = 2 * math.pi / teeth
  for k in range(teeth):
    a = phase + k * step
    # a tooth: flank up, top, flank down, then the root between teeth
    for frac, r in ((0.00, root), (0.12, outer), (0.38, outer), (0.50, root)):
      pts.append((cx + r * math.cos(a + frac * step), cy + r * math.sin(a + frac * step)))
    for frac in (0.66, 0.83):
      pts.append((cx + root * math.cos(a + frac * step), cy + root * math.sin(a + frac * step)))
  d.polygon(pts, fill=fill, outline=OUTLINE, width=18)
  d.ellipse([cx - hole, cy - hole, cx + hole, cy + hole], fill=(0, 0, 0, 0), outline=OUTLINE, width=18)

def draw(size:int) -> Image.Image:
  S = 1024
  img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
  d = ImageDraw.Draw(img)
  teeth, outer, root = 12, 262, 216
  # (centres on the diagonal, close enough for the teeth to mesh)
  gap = outer + root + 4
  c1 = (512 - gap / (2 * math.sqrt(2)), 512 - gap / (2 * math.sqrt(2)))
  c2 = (512 + gap / (2 * math.sqrt(2)), 512 + gap / (2 * math.sqrt(2)))
  diag = math.pi / 4 # (the direction from gear 1 to gear 2)
  step = 2 * math.pi / teeth
  # gear 1: a tooth pointing at gear 2; gear 2: a gap facing gear 1
  gear(d, *c1, outer, root, teeth, diag - 0.25 * step, BLUE, 86)
  gear(d, *c2, outer, root, teeth, diag + math.pi - 0.75 * step, YELLOW, 86)
  return img.resize((size, size), Image.LANCZOS)

def main() -> None:
  os.makedirs(IMAGES, exist_ok=True)
  draw(160).save(os.path.join(IMAGES, "pu-logo.png"))
  draw(64).save(os.path.join(IMAGES, "pu-favicon.png"))
  print("wrote", os.path.join(IMAGES, "pu-logo.png"), "and pu-favicon.png")

if __name__ == "__main__":
  main()
