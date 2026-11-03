#################################################################################
# (c) Copyright 2026, Rob Kremer, MIT open source license.                      #
#                                                                               #
# Permission is hereby granted, free of charge, to any person obtaining a copy  #
# of this software and associated documentation files (the "Software"), to deal #
# in the Software without restriction, including without limitation the rights  #
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell     #
# copies of the Software, and to permit persons to whom the Software is         #
# furnished to do so, subject to the following conditions:                      #
#                                                                               #
# The above copyright notice and this permission notice shall be included in all#
# copies or substantial portions of the Software.                               #
#                                                                               #
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR    #
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,      #
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE   #
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER        #
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, #
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE #
# SOFTWARE.                                                                     #
#################################################################################
'''
*util.lineMarks*: reading mark specs, laying marks out along a line, and
drawing them (on a hidden canvas).

Created on Nov 2, 2026

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''
import math
import unittest
import tkinter as tk
from util import lineMarks as lm
from util.lineMarks import Mark, parseMarks, layoutMarks, MarkSpecError, START, END, MIDDLE, FORWARD, BACKWARD, OUTWARD

class TestParse(unittest.TestCase):

  def test_empty(self):
    self.assertEqual(parseMarks(None), ())
    self.assertEqual(parseMarks(""), ())
    self.assertEqual(parseMarks("  "), ())

  def test_oldTerminatorSpecs(self):
    'What vis/terminator<n> held before marks: one mark, as it was.'
    self.assertEqual(parseMarks("arrow"), (Mark("arrow", (8.0, 10.0, 3.0), OUTWARD),))
    self.assertEqual(parseMarks("arrow(8,8,5)"), (Mark("arrow", (8.0, 8.0, 5.0), OUTWARD),))
    self.assertEqual(parseMarks("arrow(8)"), (Mark("arrow", (8.0, 10.0, 3.0), OUTWARD),))
    self.assertEqual(parseMarks("arrow(8, 12)"), (Mark("arrow", (8.0, 12.0, 3.0), OUTWARD),))
    self.assertEqual(parseMarks("circle(5)"), (Mark("circle", (5.0,), OUTWARD),))
    self.assertEqual(parseMarks("Circle"), (Mark("circle", (5.0,), OUTWARD),))

  def test_shorthands(self):
    self.assertEqual([(m.kind, m.direction) for m in parseMarks("o>")], [("circle", OUTWARD), ("arrow", FORWARD)])
    self.assertEqual([(m.kind, m.direction) for m in parseMarks(">>")], [("arrow", FORWARD)] * 2)
    self.assertEqual([m.kind for m in parseMarks("|||")], ["bar"] * 3)
    self.assertEqual([(m.kind, m.direction) for m in parseMarks("<|>")],
                     [("arrow", BACKWARD), ("bar", OUTWARD), ("arrow", FORWARD)])
    self.assertEqual([m.kind for m in parseMarks("*o")], ["dot", "circle"])
    self.assertEqual([m.kind for m in parseMarks("oo")], ["circle", "circle"])
    self.assertEqual([(m.kind, m.direction) for m in parseMarks("@>")], [("ring", OUTWARD), ("arrow", FORWARD)])

  def test_ring(self):
    'A hollow circle: "ring", "@"; sized as a circle is.'
    self.assertEqual(parseMarks("ring"), (Mark("ring", (5.0,), OUTWARD),))
    self.assertEqual(parseMarks("ring(6)"), (Mark("ring", (6.0,), OUTWARD),))
    self.assertEqual(parseMarks("@(6)"), (Mark("ring", (6.0,), OUTWARD),))
    self.assertEqual(parseMarks("Ring"), parseMarks("@"))
    self.assertNotEqual(parseMarks("@"), parseMarks("o"))

  def test_mixedAndSizes(self):
    marks = parseMarks("circle(6) arrow(8,10,3)")
    self.assertEqual(marks, (Mark("circle", (6.0,)), Mark("arrow", (8.0, 10.0, 3.0))))
    self.assertEqual(parseMarks("o(7),>"), (Mark("circle", (7.0,)), Mark("arrow", (8.0, 10.0, 3.0), FORWARD)))
    self.assertEqual(parseMarks("bar(12)"), (Mark("bar", (12.0,)),))
    self.assertEqual(parseMarks("|(12)|"), (Mark("bar", (12.0,)), Mark("bar", (10.0,))))

  def test_errors(self):
    for bad in ("arow", "o>x", "circle(", "circle(-1)", "circle(a)", "arrow(1,True)", "#"):
      with self.subTest(bad=bad):
        with self.assertRaises(MarkSpecError):
          parseMarks(bad)
        self.assertIsNotNone(lm.checkMarks(bad))
    self.assertIsNone(lm.checkMarks("o>"))

  def test_diamondsAndCrowsFeet(self):
    'Diamonds (hollow and filled) and crows\' feet: by name, and the feet by "}" / "{".'
    self.assertEqual(parseMarks("diamond"), (Mark("diamond", (12.0, 7.0), OUTWARD),))
    self.assertEqual(parseMarks("diamond(10)"), (Mark("diamond", (10.0, 6.0), OUTWARD),))
    self.assertEqual(parseMarks("fdiamond(12,8)"), (Mark("fdiamond", (12.0, 8.0), OUTWARD),))
    self.assertEqual([(m.kind, m.direction) for m in parseMarks("}")], [("crow", FORWARD)])
    self.assertEqual([(m.kind, m.direction) for m in parseMarks("{")], [("crow", BACKWARD)])
    self.assertEqual(parseMarks("crow"), (Mark("crow", (10.0, 10.0), OUTWARD),))
    self.assertEqual([m.kind for m in parseMarks("@}")], ["ring", "crow"])             # (ER: zero or many)
    self.assertEqual([m.kind for m in parseMarks("|}")], ["bar", "crow"])              # (one or many)
    self.assertEqual([(m.kind, m.direction) for m in parseMarks("diamond>")], [("diamond", OUTWARD), ("arrow", FORWARD)])

  def test_register(self):
    'A new kind of mark: written by its name and its shorthand.'
    class Square(lm.CircleKind):
      name = "square"
      shorthands = {"#": OUTWARD}
    try:
      lm.registerMarkKind(Square())
      self.assertEqual([m.kind for m in parseMarks("#square")], ["square", "square"])
    finally:
      del lm.KINDS["square"], lm.SHORTHANDS["#"]
      parseMarks.cache_clear()


class TestLayout(unittest.TestCase):

  def test_arrowAtEnd(self):
    'One arrowhead at the end: tip on the end, the line stopping under it (as Tk draws).'
    lay = layoutMarks("arrow", END)
    p, = lay.marks
    self.assertTrue(p.forward)
    self.assertEqual((p.x0, p.x1), (-10.0, 0.0))
    _, end = lm.arrowHead((0, 0), (-10, 0), 1.0, (8, 10, 3))
    self.assertAlmostEqual(lay.lowStop, end[0])
    self.assertEqual(lay.joiners, [])

  def test_arrowAtStartPointsOut(self):
    p, = layoutMarks("arrow", START).marks
    self.assertFalse(p.forward)                                    # (toward the start: off the line)
    self.assertEqual((p.x0, p.x1), (0.0, 10.0))

  def test_circleCentredOnEnd(self):
    'A lone circle at the end is centred on it (as circle terminators were); the line stops at its edge.'
    lay = layoutMarks("o", END)
    p, = lay.marks
    self.assertEqual((p.x0, p.x1), (-2.5, 2.5))
    self.assertEqual(lay.lowStop, -2.5)

  def test_ringLikeCircle(self):
    'A ring is laid out as a circle is: centred on the end, and the line stops at its edge.'
    for spec in ("@", "ring"):
      with self.subTest(spec=spec):
        lay = layoutMarks(spec, END)
        p, = lay.marks
        self.assertEqual((p.x0, p.x1), (-2.5, 2.5))
        self.assertEqual(lay.lowStop, -2.5)
        self.assertEqual(lay.breadth, 5.0)
    lay = layoutMarks("@>", END)
    r, a = lay.marks
    self.assertEqual((r.x0, r.x1), (-15.0, -10.0))
    self.assertEqual(lay.lowStop, -15.0)

  def test_diamondAtEnd(self):
    'A diamond at the end: its tip on the end, the line stopping at its other tip.'
    for spec in ("diamond", "fdiamond"):
      with self.subTest(spec=spec):
        lay = layoutMarks(spec, END)
        p, = lay.marks
        self.assertEqual((p.x0, p.x1), (-12.0, 0.0))
        self.assertEqual(lay.lowStop, -12.0)
        self.assertEqual(lay.breadth, 7.0)
        self.assertEqual(lay.joiners, [])
    p, = layoutMarks("diamond", START).marks
    self.assertEqual((p.x0, p.x1), (0.0, 12.0))

  def test_crowsFoot(self):
    'A crow\'s foot is on the end, the line running through it (it is the middle toe); behind a ring, the line runs on from the ring to the end.'
    lay = layoutMarks("}", END)
    p, = lay.marks
    self.assertEqual((p.x0, p.x1, p.forward), (-10.0, 0.0, True))
    self.assertIsNone(lay.lowStop)
    self.assertEqual(lay.joiners, [])
    p, = layoutMarks("crow", START).marks
    self.assertEqual((p.x0, p.x1, p.forward), (0.0, 10.0, False))          # (toes toward the start)
    lay = layoutMarks("@}", END)
    ring, foot = lay.marks
    self.assertEqual((ring.x0, ring.x1, foot.x0, foot.x1), (-15.0, -10.0, -10.0, 0.0))
    self.assertEqual(lay.lowStop, -15.0)
    self.assertEqual(lay.joiners, [(-10.0, 0.0)])

  def test_circleThenArrow(self):
    '"o>" at the end: ----o> -- the circle behind the arrowhead, touching it.'
    lay = layoutMarks("o>", END)
    c, a = lay.marks
    self.assertEqual((a.x0, a.x1), (-10.0, 0.0))
    self.assertEqual((c.x0, c.x1), (-15.0, -10.0))
    self.assertEqual(lay.lowStop, -15.0)
    _, under = lm.arrowHead((0, 0), (-10, 0), 1.0, (8, 10, 3))
    self.assertEqual(lay.joiners, [(-10.0, under[0])])             # (they touch; the line runs on under the arrowhead, as Tk draws one)

  def test_doubleArrow(self):
    lay = layoutMarks(">>", END)
    a1, a2 = lay.marks
    self.assertEqual((a1.x0, a1.x1, a2.x0, a2.x1), (-20.0, -10.0, -10.0, 0.0))
    self.assertTrue(-20.0 < lay.lowStop < -10.0)                    # (under the inner arrowhead)

  def test_barsRunThrough(self):
    'Bars: spaced, kept off the end, and the line runs through them.'
    lay = layoutMarks("|||", END)
    self.assertEqual([p.x0 for p in lay.marks], [-12.0, -8.0, -4.0])
    self.assertIsNone(lay.lowStop)
    self.assertEqual(lay.joiners, [])

  def test_lineOnToEnd(self):
    '">|" at the end: the line stops for the arrowhead, then runs on from its tip, through the bar, to the end.'
    lay = layoutMarks(">|", END)
    a, b = lay.marks
    self.assertEqual((b.x0, b.x1), (-4.0, -4.0))
    self.assertEqual(a.x1, -8.0)
    self.assertEqual(lay.joiners, [(-8.0, 0.0)])

  def test_middle(self):
    '"<|>" in the middle: centred; the line from either side meets an arrowhead\'s tip, and runs on under both heads, through the bar.'
    lay = layoutMarks("<|>", MIDDLE)
    l, b, r = lay.marks
    self.assertEqual((l.x0, l.x1, b.x0, r.x0, r.x1), (-14.0, -4.0, 0.0, 4.0, 14.0))
    self.assertFalse(l.forward)
    self.assertTrue(r.forward)
    self.assertEqual((lay.lowStop, lay.highStop), (-14.0, 14.0))
    (a, z), = lay.joiners
    self.assertTrue(-14.0 < a < -4.0 and 4.0 < z < 14.0)
    self.assertAlmostEqual(a, -z)

  def test_middleBarsOnly(self):
    lay = layoutMarks("|||", MIDDLE)
    self.assertEqual([p.x0 for p in lay.marks], [-4.0, 0.0, 4.0])
    self.assertIsNone(lay.lowStop)
    self.assertIsNone(lay.highStop)
    self.assertEqual(lay.breadth, 10.0)


class TestPaths(unittest.TestCase):

  def test_straight(self):
    path = [(0.0, 0.0), (100.0, 0.0)]
    self.assertEqual(lm.paramAtDistance(path, 10), 0.1)
    self.assertEqual(lm.paramAtDistance(path, 10, fromEnd=True), 0.9)
    self.assertIsNone(lm.paramAtDistance(path, 200))
    self.assertEqual(lm.subPath(path, 0.1, 0.9), [(10.0, 0.0), (90.0, 0.0)])

  def test_quadratic(self):
    path = [(0.0, 0.0), (50.0, 50.0), (100.0, 0.0)]
    t = lm.paramAtDistance(path, 10, fromEnd=True)
    x, y = lm.pathPoint(path, t)
    self.assertAlmostEqual(math.hypot(100 - x, y), 10.0, places=4)
    sub = lm.subPath(path, 0.25, 0.75)                             # (exactly that part of the curve)
    for s in (0.0, 0.3, 1.0):
      self.assertAlmostEqual(lm.pathPoint(sub, s)[0], lm.pathPoint(path, 0.25 + 0.5 * s)[0])
      self.assertAlmostEqual(lm.pathPoint(sub, s)[1], lm.pathPoint(path, 0.25 + 0.5 * s)[1])
    dx, dy = lm.pathDirection(path, atEnd=True)
    self.assertAlmostEqual(dx, math.sqrt(0.5))
    self.assertAlmostEqual(dy, -math.sqrt(0.5))


class TestDraw(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    try:
      cls.root = tk.Tk()
    except tk.TclError as ex:
      raise unittest.SkipTest(f"no display: {ex}")
    cls.root.withdraw()
    cls.canvas = tk.Canvas(cls.root, width=300, height=200)

  @classmethod
  def tearDownClass(cls):
    cls.root.destroy()

  def tearDown(self):
    self.canvas.delete("all")

  def test_markedPath(self):
    'A line with "o>" at its end: cut back to the circle; the marks in their roles.'
    c = self.canvas
    ids = lm.drawMarkedPath(c, [(0.0, 50.0), (100.0, 50.0)], None, "o>", lineColor="red", fillColor="white", tags=["t"])
    self.assertEqual(c.coords(ids.line), [0.0, 50.0, 85.0, 50.0])
    self.assertEqual(c.itemcget(ids.line, "arrow"), "none")
    joiner, circle, arrow = ids.end                                # (the bit of line under the arrowhead first: under the marks)
    self.assertEqual((c.type(joiner), c.type(circle), c.type(arrow)), ("line", "oval", "polygon"))
    self.assertEqual(c.itemcget(joiner, "fill"), "red")
    self.assertEqual(c.coords(circle), [85.0, 47.5, 90.0, 52.5])
    self.assertEqual(c.itemcget(circle, "fill"), "white")
    self.assertEqual(c.itemcget(arrow, "fill"), "red")
    self.assertIn("t", c.gettags(arrow))
    self.assertIn(lm.SOLID, c.gettags(arrow))

  def test_redrawInPlace(self):
    'A redraw reuses the items; a changed spec reuses what it can and deletes the rest.'
    c = self.canvas
    ids = lm.drawMarkedPath(c, [(0.0, 50.0), (100.0, 50.0)], None, ">>")
    again = lm.drawMarkedPath(c, [(0.0, 60.0), (120.0, 60.0)], None, ">>", ids)
    self.assertEqual(again.all(), ids.all())
    self.assertEqual([c.type(i) for i in again.end], ["line", "polygon", "polygon"]) # (a bit of line under the inner arrowhead)
    fewer = lm.drawMarkedPath(c, [(0.0, 60.0), (120.0, 60.0)], None, ">", again)
    self.assertEqual(fewer.end, [again.end[1]])
    self.assertEqual([c.type(again.end[0]), c.type(again.end[2])], [None, None]) # (deleted)

  def test_smoothPath(self):
    c = self.canvas
    ids = lm.drawMarkedPath(c, [(0.0, 100.0), (100.0, 0.0), (200.0, 100.0)], "<", ">")
    self.assertEqual(len(c.coords(ids.line)), 6)
    self.assertEqual(c.itemcget(ids.line, "smooth"), "true")

  def test_middleAndRecolor(self):
    c = self.canvas
    lay = layoutMarks("*o|", MIDDLE)
    items = lm.drawMarks(c, lay, (100.0, 100.0), (0.0, 1.0), lineColor="blue", fillColor="yellow")
    dot, circle, bar = items
    self.assertEqual((c.itemcget(dot, "fill"), c.itemcget(dot, "outline")), ("blue", "blue"))
    self.assertEqual(c.itemcget(circle, "fill"), "yellow")
    x0, y0, x1, y1 = c.coords(bar)                                 # (across the line: it runs down)
    self.assertEqual((y0, y1), (y0, y0))
    self.assertEqual(abs(x1 - x0), 10.0)
    lm.recolorMarks(c, items, "grey", "")
    self.assertEqual((c.itemcget(dot, "fill"), c.itemcget(circle, "fill"), c.itemcget(circle, "outline"),
                      c.itemcget(bar, "fill")), ("grey", "", "grey", "grey"))

  def test_hollow(self):
    'A ring is filled with the canvas\'s background, outlined in the line colour -- whatever the fill colour is.'
    c = self.canvas
    c.configure(background="#123456")
    lay = layoutMarks("@o*", MIDDLE)
    ring, circle, dot = lm.drawMarks(c, lay, (100.0, 100.0), (1.0, 0.0), lineColor="blue", fillColor="blue")
    self.assertEqual((c.itemcget(ring, "fill"), c.itemcget(ring, "outline")), ("#123456", "blue"))
    self.assertEqual((c.itemcget(circle, "fill"), c.itemcget(dot, "fill")), ("blue", "blue"))
    self.assertIn(lm.HOLLOW, c.gettags(ring))
    self.assertEqual(lm.backgroundColor(c), "#123456")
    lm.recolorMarks(c, [ring, circle, dot], "grey", "white")           # (faded: the ring stays hollow)
    self.assertEqual((c.itemcget(ring, "fill"), c.itemcget(ring, "outline")), ("#123456", "grey"))
    self.assertEqual(c.itemcget(circle, "fill"), "white")
    lm.recolorMarks(c, [ring], "grey", "white", backColor="yellow")   # (or told what it's over)
    self.assertEqual(c.itemcget(ring, "fill"), "yellow")
    ids = lm.drawMarkedPath(c, [(0.0, 50.0), (100.0, 50.0)], "@", "@>", backColor="pink", lineColor="red")
    self.assertEqual(c.coords(ids.line), [2.5, 50.0, 85.0, 50.0])     # (cut back to both rings)
    for i in ids.start + ids.end:
      if c.type(i) == "oval":
        self.assertEqual((c.itemcget(i, "fill"), c.itemcget(i, "outline")), ("pink", "red"))
    c.configure(background="white")

  def test_diamondsAndCrowsFeetDrawn(self):
    'A hollow diamond is filled with the background, a filled one with the line colour; a crow\'s foot is one 3-point line, toes at the end.'
    c = self.canvas
    c.configure(background="#eeeeee")
    ids = lm.drawMarkedPath(c, [(0.0, 50.0), (100.0, 50.0)], "diamond", "fdiamond", lineColor="red")
    self.assertEqual(c.coords(ids.line), [12.0, 50.0, 88.0, 50.0])
    hollow, = ids.start
    filled, = ids.end
    self.assertEqual((c.type(hollow), c.itemcget(hollow, "fill"), c.itemcget(hollow, "outline")), ("polygon", "#eeeeee", "red"))
    self.assertEqual((c.type(filled), c.itemcget(filled, "fill"), c.itemcget(filled, "outline")), ("polygon", "red", "red"))
    self.assertEqual(c.coords(hollow), [0.0, 50.0, 6.0, 46.5, 12.0, 50.0, 6.0, 53.5])   # (tip on the start)
    self.assertEqual(c.coords(filled)[4:6], [100.0, 50.0])                               # (tip on the end)
    ids = lm.drawMarkedPath(c, [(0.0, 50.0), (100.0, 50.0)], None, "@}", lineColor="blue")
    joiner, ring, foot = ids.end
    self.assertEqual((c.type(joiner), c.type(ring), c.type(foot)), ("line", "oval", "line"))
    self.assertEqual(c.coords(joiner), [90.0, 50.0, 100.0, 50.0])                        # (from the ring to the end, under the foot)
    self.assertEqual(c.coords(foot), [100.0, 45.0, 90.0, 50.0, 100.0, 55.0])             # (toes at the end, heel 10 back)
    self.assertEqual(c.itemcget(foot, "fill"), "blue")
    c.configure(background="white")

  def test_nothingLeft(self):
    'Marks longer than the line: no line, just the marks.'
    ids = lm.drawMarkedPath(self.canvas, [(0.0, 0.0), (5.0, 0.0)], None, ">>")
    self.assertIsNone(ids.line)
    self.assertEqual([self.canvas.type(i) for i in ids.end], ["line", "polygon", "polygon"])

if __name__ == "__main__":
  unittest.main()
