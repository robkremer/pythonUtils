'''
Marks along a line on a Tk canvas -- arrowheads, circles, dots and bars --
written as a short text (a *mark spec*), laid out along the line, and drawn
turned to follow it.

A mark spec is a sequence of marks, written in order from the line's start
toward its end (so, with the line running left to right, as it looks):

==================  ========================================================
``>``, ``<``        an arrowhead pointing toward the line's end, or its start
``arrow``           an arrowhead pointing outward: off whichever end of the
                    line it's at (toward the end, in the middle of a line)
``o``, ``circle``   a circle, filled with the fill colour
``*``, ``dot``      a solid circle, in the line's colour
``@``, ``ring``     a hollow circle: outlined in the line's colour, filled
                    with the canvas's background (see *HOLLOW*)
``|``, ``bar``      a bar across the line (the line runs through it)
``diamond``         a hollow diamond, its tip on the line's end (UML's
                    aggregation); ``fdiamond``, a filled one (composition)
``{``, ``}``        a crow's foot, its toes spread toward the line's end,
``crow``            or its start (ER's "many"), the brace opening toward
                    them as in text ER notations (``|{`` at the end: one
                    or many); ``crow``: toward the end it's at, like
                    ``arrow``
==================  ========================================================

Any mark may be followed by its sizes in parentheses: ``arrow(8,10,3)`` (as
Tk's "arrowshape": tip to neck, tip to trailing points, and how far the
trailing points stand out from the line's edge), ``circle(6)``, ``dot(6)`` and
``ring(6)`` (the diameter), ``bar(12)`` (its length across the line),
``diamond(12,7)`` (along the line, and across it), ``crow(10,10)`` (likewise);
``>(8,10,3)`` too.
Marks may be separated by spaces or commas, or run together: ``o>``, ``>>``,
``|||``, ``<|>``, ``@{`` (ER's "zero or many"), ``circle(6) arrow(8,10,3)``.

A sequence goes at a line's start (*START*: ``<o`` gives ``<o----``), at its end
(*END*: ``o>`` gives ``----o>``), or in its middle (*MIDDLE*: ``|||`` gives
``--|||--``). The line stops at the marks it can't pass through (arrowheads and
circles), and runs through bars: *layoutMarks()* says where everything goes,
*drawMarks()* draws the marks (and the bits of line between them), and
*drawMarkedPath()* draws a whole line -- straight, or a smooth 3-point curve --
with marks at either end. New kinds of mark are added with *registerMarkKind()*.

Created on Nov 2, 2026

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''
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
from __future__ import annotations
import math
from ast import literal_eval
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Optional, Sequence

Point = tuple[float, float]

FORWARD = 1
"A mark's direction: it points toward the line's end (``>``)."
BACKWARD = -1
"A mark's direction: it points toward the line's start (``<``)."
OUTWARD = 0
"A mark's direction: off whichever end it's at (toward the end, in the middle) -- eg ``arrow``."

START = "start"
"Where a sequence of marks goes (see *layoutMarks()*): at the line's start."
END = "end"
"Where a sequence of marks goes: at the line's end."
MIDDLE = "middle"
"Where a sequence of marks goes: centred on a point in the middle of the line."

STROKE = "lm:stroke"
"A drawn item's role (one of its canvas tags -- see *recolorMarks()*): a line, in the line colour."
SOLID = "lm:solid"
"A drawn item's role: filled with the line colour, with no outline (an arrowhead)."
DOT = "lm:dot"
"A drawn item's role: filled and outlined with the line colour."
OPEN = "lm:open"
"A drawn item's role: outlined with the line colour, filled with the fill colour."
HOLLOW = "lm:hollow"
"""A drawn item's role: outlined with the line colour, filled with the background colour (the canvas's,
unless *drawMarks()* is told another) -- so it looks empty, and hides the line under it."""
ROLES = (STROKE, SOLID, DOT, OPEN, HOLLOW)


class MarkSpecError(ValueError):
  'A mark spec that can\'t be read.'


@dataclass(frozen=True)
class Mark:
  '''
  One mark: its kind's name (see *KINDS*), its sizes (complete: see
  *MarkKind.normalize()*), and its direction (*FORWARD*, *BACKWARD* or
  *OUTWARD*; only arrowheads have one that matters).
  '''
  kind: str
  sizes: tuple[float, ...] = ()
  direction: int = OUTWARD


def arrowHead(tip:Point, toward:Point, width:float, shape:Sequence[float]) -> tuple[list[Point], Point]:
  '''
  An arrowhead as Tk draws one on a line, at *tip*, the line coming from *toward*.

  :param width: The line's width.
  :param shape: Its "arrowshape": (d1, d2, d3) -- as far along the line from
    the tip to the neck, and to the trailing points, and how far the trailing
    points are out from the line's edge.
  :returns: The head's polygon, and where the line is to end (under the head).
  '''
  d1, d2, d3 = shape
  dx, dy = tip[0] - toward[0], tip[1] - toward[1]
  n = math.hypot(dx, dy) or 1.0
  ux, uy = dx / n, dy / n
  px, py = -uy, ux
  out = width / 2 + d3
  neck = (tip[0] - ux * d1, tip[1] - uy * d1)
  a = (tip[0] - ux * d2 + px * out, tip[1] - uy * d2 + py * out)
  b = (tip[0] - ux * d2 - px * out, tip[1] - uy * d2 - py * out)
  frac = (width / 2) / out if out else 0
  back = frac * d2 + d1 * (1 - frac) / 2
  return [tip, a, neck, b], (tip[0] - ux * back, tip[1] - uy * back)


# =============================================================================
# Kinds of mark
# =============================================================================

class MarkKind:
  '''
  A kind of mark: how it's written, how much of the line it takes up, and how
  it's drawn. Positions along the line are *x* (increasing toward the line's
  end); across it, *y*.
  '''
  name:str = ""
  "Its name in a mark spec (eg: \"arrow\")."
  shorthands:dict[str, int] = {}
  "Its one-character names, each with the direction it gives (eg: {\">\": FORWARD, \"<\": BACKWARD})."
  defaultSizes:tuple[float, ...] = ()
  "Its sizes when none are given."
  solid:bool = True
  "Whether the line stops at it (else it runs through it, as through a bar)."
  spacing:float = 0.0
  "The gap it wants between it and its neighbours."

  def normalize(self, sizes:tuple[float, ...]) -> tuple[float, ...]:
    '''
    :param sizes: The sizes written in the spec (perhaps none).
    :returns: Its complete sizes.
    '''
    return tuple(sizes[:len(self.defaultSizes)]) + self.defaultSizes[len(sizes):]

  def length(self, sizes:tuple[float, ...], width:float) -> float:
    '''
    :param width: The line's width.
    :returns: How much of the line it takes up (along it).
    '''
    return 0.0

  def breadth(self, sizes:tuple[float, ...], width:float) -> float:
    '''
    :returns: How wide it is (across the line).
    '''
    return width

  def endOffset(self, sizes:tuple[float, ...]) -> float:
    '''
    :returns: How far in from the line's end (or start) it sits when it's the
      outermost of a sequence there -- negative if it overhangs the end (a
      circle is centred on it).
    '''
    return 0.0

  def joins(self, sizes:tuple[float, ...], width:float, forward:bool) -> tuple[float, float]:
    '''
    For a solid mark: (how far into it, from its start side, a line coming
    from that side reaches; the same from its end side) -- eg: a line runs on
    under an arrowhead's trailing points, to its neck.
    '''
    return (0.0, 0.0)

  def draw(self, pen:"_Pen", x0:float, x1:float, sizes:tuple[float, ...], width:float, forward:bool) -> None:
    '''
    Draw it with *pen*, between *x0* and *x1* along the line (*forward*: it points toward the line's end).
    '''
    raise NotImplementedError(f'{type(self).__name__}.draw()')


class ArrowKind(MarkKind):
  '''
  An arrowhead (``arrow``, ``>``, ``<``): sizes as Tk's "arrowshape" -- (tip to
  neck, tip to trailing points, how far the trailing points stand out from the
  line's edge). One size *a* is (a, 1.25a, 0.375a); two, *a*, *b*, are (a, b, 0.375a).
  '''
  name = "arrow"
  shorthands = {">": FORWARD, "<": BACKWARD}
  defaultSizes = (8.0, 10.0, 3.0)

  def normalize(self, sizes):
    if len(sizes) == 0:
      return self.defaultSizes
    if len(sizes) == 1:
      return (sizes[0], sizes[0] * 1.25, sizes[0] * 0.375)
    if len(sizes) == 2:
      return (sizes[0], sizes[1], sizes[0] * 0.375)
    return tuple(sizes[:3])

  def length(self, sizes, width):
    return max(sizes[0], sizes[1])

  def breadth(self, sizes, width):
    return width + 2 * sizes[2]

  def joins(self, sizes, width, forward):
    L = self.length(sizes, width)
    _, end = arrowHead((L, 0.0), (0.0, 0.0), width, sizes) # (its base edge at 0, its tip at L)
    under = end[0] # (from its base edge to where the line ends, under it)
    return (under, 0.0) if forward else (0.0, under)

  def draw(self, pen, x0, x1, sizes, width, forward):
    tip, toward = (x1, x0) if forward else (x0, x1)
    head, _ = arrowHead(pen.pt(tip), pen.pt(toward), width, sizes)
    pen.polygon(head, SOLID)


class CircleKind(MarkKind):
  '''
  A circle (``circle``, ``o``), filled with the fill colour: its size is its diameter.
  '''
  name = "circle"
  shorthands = {"o": OUTWARD}
  defaultSizes = (5.0,)
  role = OPEN

  def length(self, sizes, width):
    return sizes[0]

  def breadth(self, sizes, width):
    return sizes[0]

  def endOffset(self, sizes):
    return -sizes[0] / 2 # (at a line's end, it's centred on it)

  def draw(self, pen, x0, x1, sizes, width, forward):
    pen.oval(pen.pt((x0 + x1) / 2), sizes[0] / 2, self.role)


class DotKind(CircleKind):
  '''
  A solid circle (``dot``, ``*``), in the line's colour: its size is its diameter.
  '''
  name = "dot"
  shorthands = {"*": OUTWARD}
  role = DOT


class RingKind(CircleKind):
  '''
  A hollow circle (``ring``, ``@``): outlined in the line's colour, filled with the
  background colour (see *HOLLOW*), so it reads as empty whatever the fill colour
  is. Its size is its diameter.
  '''
  name = "ring"
  shorthands = {"@": OUTWARD}
  role = HOLLOW


class DiamondKind(MarkKind):
  '''
  A hollow diamond (``diamond``) -- UML's aggregation -- its tip on the end of
  the line it's at: sizes (along the line, across it); one size *a* is (a, 0.6a).
  '''
  name = "diamond"
  defaultSizes = (12.0, 7.0)
  role = HOLLOW

  def normalize(self, sizes):
    if len(sizes) == 1:
      return (sizes[0], sizes[0] * 0.6)
    return super().normalize(sizes)

  def length(self, sizes, width):
    return sizes[0]

  def breadth(self, sizes, width):
    return sizes[1]

  def draw(self, pen, x0, x1, sizes, width, forward):
    xm, h = (x0 + x1) / 2, sizes[1] / 2
    pen.polygon([pen.pt(x0), pen.pt(xm, -h), pen.pt(x1), pen.pt(xm, h)], self.role)


class FilledDiamondKind(DiamondKind):
  '''
  A filled diamond (``fdiamond``), in the line's colour -- UML's composition.
  '''
  name = "fdiamond"
  role = DOT


class CrowFootKind(MarkKind):
  '''
  A crow's foot (``crow``, ``{``, ``}``) -- ER's "many": three toes fanning
  out from a point on the line to the end it's at (``{``: toward the line's
  end; ``}``: toward its start -- the brace opens toward the toes, as text ER
  notations write it: ``|{`` at a line's end, ``}|`` at its start; ``crow``:
  outward, like ``arrow``). Sizes:
  (along the line, across it at the toes). The line runs through it (it is
  the middle toe).
  '''
  name = "crow"
  shorthands = {"{": FORWARD, "}": BACKWARD}
  defaultSizes = (10.0, 10.0)
  solid = False

  def length(self, sizes, width):
    return sizes[0]

  def breadth(self, sizes, width):
    return sizes[1]

  def draw(self, pen, x0, x1, sizes, width, forward):
    heel, toes = (x0, x1) if forward else (x1, x0)
    h = sizes[1] / 2
    pen.line([pen.pt(toes, -h), pen.pt(heel), pen.pt(toes, h)], STROKE, dash="")


class BarKind(MarkKind):
  '''
  A bar across the line (``bar``, ``|``): its size is its length. The line runs through it.
  '''
  name = "bar"
  shorthands = {"|": OUTWARD}
  defaultSizes = (10.0,)
  solid = False
  spacing = 4.0

  def breadth(self, sizes, width):
    return sizes[0]

  def endOffset(self, sizes):
    return self.spacing # (not on the end: it would be lost in the edge of what the line meets)

  def draw(self, pen, x0, x1, sizes, width, forward):
    x = (x0 + x1) / 2
    pen.line([pen.pt(x, -sizes[0] / 2), pen.pt(x, sizes[0] / 2)], STROKE, dash="")


KINDS:dict[str, MarkKind] = {}
"The known kinds of mark, by name (see *registerMarkKind()*)."
SHORTHANDS:dict[str, tuple[str, int]] = {}
"The one-character marks: each to (its kind's name, its direction)."

def registerMarkKind(kind:MarkKind) -> MarkKind:
  '''
  Make *kind* known: it can then be written in mark specs, by its name and its
  shorthands (each replacing any it had before).

  :returns: *kind*.
  '''
  if not kind.name.isalpha():
    raise ValueError(f'registerMarkKind(): a mark kind\'s name must be letters only: "{kind.name}".')
  for ch in kind.shorthands:
    if len(ch) != 1 or ch.isspace() or ch in "(),":
      raise ValueError(f'registerMarkKind(): bad shorthand "{ch}" for "{kind.name}".')
  KINDS[kind.name.lower()] = kind
  for ch, direction in kind.shorthands.items():
    SHORTHANDS[ch] = (kind.name.lower(), direction)
  if "parseMarks" in globals(): # (what it read before may read differently now)
    parseMarks.cache_clear()
  return kind

for _k in (ArrowKind(), CircleKind(), DotKind(), RingKind(), DiamondKind(), FilledDiamondKind(), CrowFootKind(), BarKind()):
  registerMarkKind(_k)


# =============================================================================
# Reading mark specs
# =============================================================================

def _sizes(text:str, spec:str) -> tuple[float, ...]:
  '''
  The sizes in a mark's "(...)": positive numbers, separated by commas.
  '''
  if not text.strip():
    return ()
  try:
    vals = literal_eval("(" + text + ",)")
  except Exception:
    raise MarkSpecError(f'bad sizes "({text})" in mark spec "{spec}"') from None
  if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 for v in vals):
    raise MarkSpecError(f'sizes must be positive numbers: "({text})" in mark spec "{spec}"')
  return tuple(float(v) for v in vals)

@lru_cache(maxsize=1024)
def parseMarks(spec:Optional[str]) -> tuple[Mark, ...]:
  '''
  :param spec: A mark spec (see the module doc), eg: ``o>``, ``circle(6) arrow``; None or "" for none.
  :returns: Its marks, in order from the line's start toward its end.
  :raises MarkSpecError: If *spec* can't be read.
  '''
  if not spec:
    return ()
  out:list[Mark] = []
  s, i = str(spec), 0
  while i < len(s):
    c = s[i]
    if c.isspace() or c == ",":
      i += 1
      continue
    if c.isalpha():
      j = i
      while j < len(s) and s[j].isalpha():
        j += 1
      word = s[i:j]
      if word.lower() in KINDS:
        tokens = [(word.lower(), OUTWARD)]
      elif all(ch in SHORTHANDS for ch in word): # (eg: "oo")
        tokens = [SHORTHANDS[ch] for ch in word]
      else:
        raise MarkSpecError(f'unknown mark "{word}" in mark spec "{spec}" (known: {", ".join(sorted(KINDS))})')
      i = j
    elif c in SHORTHANDS:
      tokens = [SHORTHANDS[c]]
      i += 1
    else:
      raise MarkSpecError(f'unexpected "{c}" in mark spec "{spec}"')
    sizes:tuple[float, ...] = ()
    if i < len(s) and s[i] == "(": # (the sizes of the last of the tokens)
      j = s.find(")", i)
      if j < 0:
        raise MarkSpecError(f'unclosed "(" in mark spec "{spec}"')
      sizes = _sizes(s[i+1:j], spec)
      i = j + 1
    for k, (name, direction) in enumerate(tokens):
      out.append(Mark(name, KINDS[name].normalize(sizes if k == len(tokens) - 1 else ()), direction))
  return tuple(out)

def checkMarks(spec:Optional[str]) -> Optional[str]:
  '''
  :returns: Why *spec* can't be read, or None if it can.
  '''
  try:
    parseMarks(spec)
    return None
  except MarkSpecError as ex:
    return str(ex)


# =============================================================================
# Laying marks out along a line
# =============================================================================

@dataclass
class PlacedMark:
  '''
  A mark, laid out: from *x0* to *x1* along the line, pointing toward its end (*forward*) or not.
  '''
  mark:Mark
  kind:MarkKind
  x0:float
  x1:float
  forward:bool


@dataclass
class MarkLayout:
  '''
  Where a sequence of marks goes along a line (see *layoutMarks()*), in
  distances along it from the point it's laid out at (positive toward the
  line's end).
  '''
  marks:list[PlacedMark] = field(default_factory=list)
  lowStop:Optional[float] = None
  "Where the line coming from the start side stops (None: it isn't stopped -- there are no solid marks)."
  highStop:Optional[float] = None
  "Where the line coming from the end side stops (likewise)."
  joiners:list[tuple[float, float]] = field(default_factory=list)
  "The bits of line among the marks: between solid ones, and on to the line's end (or start) past the last."
  low:float = 0.0
  "Its extent: from *low* ..."
  high:float = 0.0
  "... to *high*."
  breadth:float = 0.0
  "How wide it is, across the line."

  def length(self) -> float:
    '''
    :returns: How much of the line it spans.
    '''
    return self.high - self.low

def layoutMarks(marks:Sequence[Mark]|str|None, at:str, width:float=1.0) -> MarkLayout:
  '''
  Lay out a sequence of marks along a line.

  :param marks: The marks, or a mark spec (see *parseMarks()*).
  :param at: *START* (they begin at x = 0, the line's start, and go toward its
    end), *END* (they end at x = 0, the line's end) or *MIDDLE* (centred on x = 0).
  :param width: The line's width.
  :returns: Where they go, where the line stops for them, and the bits of line among them.
  '''
  if marks is None or isinstance(marks, str):
    marks = parseMarks(marks)
  ret = MarkLayout()
  if not marks:
    return ret
  kinds = [KINDS[m.kind] for m in marks]
  lengths = [k.length(m.sizes, width) for k, m in zip(kinds, marks)]
  gaps = [max(kinds[i].spacing, kinds[i+1].spacing) for i in range(len(marks) - 1)]
  total = sum(lengths) + sum(gaps)
  if at == END:
    x = -kinds[-1].endOffset(marks[-1].sizes) - total
  elif at == START:
    x = kinds[0].endOffset(marks[0].sizes)
  elif at == MIDDLE:
    x = -total / 2
  else:
    raise ValueError(f'layoutMarks(): "at" must be START, END or MIDDLE, not {at!r}.')
  for k, (m, kind, length) in enumerate(zip(marks, kinds, lengths)):
    forward = m.direction == FORWARD or (m.direction == OUTWARD and at != START)
    ret.marks.append(PlacedMark(m, kind, x, x + length, forward))
    x += length + (gaps[k] if k < len(gaps) else 0.0)
  ret.low, ret.high = ret.marks[0].x0, ret.marks[-1].x1
  ret.breadth = max(k.breadth(m.sizes, width) for k, m in zip(kinds, marks))
  solids = []
  for p in ret.marks:
    if p.kind.solid:
      lo, hi = p.kind.joins(p.mark.sizes, width, p.forward)
      solids.append((p.x0 + lo, p.x1 - hi))
  if solids:
    ret.lowStop, ret.highStop = solids[0][0], solids[-1][1]
    for (_, a), (b, _) in zip(solids, solids[1:]):
      if b > a:
        ret.joiners.append((a, b))
    if at == END and solids[-1][1] < 0:
      ret.joiners.append((solids[-1][1], 0.0))
    if at == START and solids[0][0] > 0:
      ret.joiners.insert(0, (0.0, solids[0][0]))
  return ret


# =============================================================================
# Drawing
# =============================================================================

class _Pen:
  '''
  Draws marks on *canvas* in a frame along a line: *x* along it (from
  *origin*, toward the line's end, as *direction* points), *y* across it --
  reusing the canvas items in *existing*, in order, where they're of the right
  type (see *finish()*).
  '''
  def __init__(self, canvas, origin:Point, direction:Point, existing:Sequence[int], tags:Sequence[str],
               toWindow:Callable[[list[float]], list[float]], lineColor:str, fillColor:str, strokeWidth:float,
               backColor:Optional[str]=None):
    n = math.hypot(direction[0], direction[1]) or 1.0
    self.ux, self.uy = direction[0] / n, direction[1] / n
    self.ox, self.oy = origin
    self.canvas = canvas
    self.existing = list(existing)
    self.tags = list(tags)
    self.toWindow = toWindow
    self.lineColor, self.fillColor = lineColor, fillColor
    self._backColor = backColor
    self.strokeWidth = strokeWidth
    self.ids:list[int] = []

  @property
  def backColor(self) -> str:
    '''
    What *HOLLOW* items are filled with: the canvas's background, unless told
    another -- asked for only when one is drawn (a round-trip to Tk).
    '''
    if self._backColor is None:
      self._backColor = backgroundColor(self.canvas)
    return self._backColor

  def pt(self, x:float, y:float=0.0) -> Point:
    '''
    :returns: The point *x* along the line, *y* across it.
    '''
    return (self.ox + self.ux * x - self.uy * y, self.oy + self.uy * x + self.ux * y)

  def _item(self, typ:str, points:Sequence[Point], role:str, opts:dict[str, Any]) -> int:
    coords = self.toWindow([c for p in points for c in p])
    tags = self.tags + [role]
    canvas = self.canvas
    while self.existing:
      i = self.existing.pop(0)
      if itemType(canvas, i) == typ:
        try:
          canvas.coords(i, coords)
          configureItem(canvas, i, tags, opts)
          self.ids.append(i)
          return i
        except Exception: # (gone)
          forgetItem(canvas, i)
          continue
      deleteItem(canvas, i)
    i = getattr(canvas, "create_" + typ)(coords, tags=tags, **opts)
    _rememberedTypes(canvas)[i] = typ
    _rememberedOptions(canvas)[i] = _optionsKey(tags, opts)
    self.ids.append(i)
    return i

  def polygon(self, points:Sequence[Point], role:str=SOLID) -> int:
    '''
    A polygon through *points* (view coordinates), coloured as *role* says.
    '''
    return self._item("polygon", points, role, self._colors(role, "polygon"))

  def _colors(self, role:str, typ:str) -> dict[str, Any]:
    return _roleOptions(role, self.lineColor, self.fillColor, typ, self.backColor if role == HOLLOW else "")

  def oval(self, centre:Point, r:float, role:str=OPEN) -> int:
    '''
    A circle at *centre*, of radius *r*, coloured as *role* says.
    '''
    return self._item("oval", [(centre[0] - r, centre[1] - r), (centre[0] + r, centre[1] + r)], role,
                      self._colors(role, "oval"))

  def line(self, points:Sequence[Point], role:str=STROKE, **opts) -> int:
    '''
    A line through *points*, in the line colour and width (and *opts*: eg: dash).
    '''
    o = dict(fill=self.lineColor, width=self.strokeWidth)
    o.update(opts)
    return self._item("line", points, role, o)

  def finish(self) -> list[int]:
    '''
    Delete the existing items it didn't reuse.

    :returns: The items it drew, in order.
    '''
    for i in self.existing:
      deleteItem(self.canvas, i)
    self.existing = []
    return self.ids


# Canvas items' types, remembered: a redraw in place reuses an item only if it's
# of the right type, and asking the canvas (canvas.type()) is a round-trip to
# Tk for every mark, every frame. Tk never reuses an item's id, so a remembered
# type is right for as long as the item exists; one that's gone is forgotten
# when that's found out (see _Pen._item()), or when it's deleted here.

_TYPES_ATTR = "_lineMarksItemTypes"

def _rememberedTypes(canvas) -> dict[int, str]:
  '''
  :returns: The types of *canvas*'s items made (or asked about) here, by id.
  '''
  types = canvas.__dict__.get(_TYPES_ATTR)
  if types is None:
    types = {}
    setattr(canvas, _TYPES_ATTR, types)
  elif len(types) > 200_000: # (items deleted behind our back aren't forgotten: start over, rather than grow for ever)
    types.clear()
  return types

def itemType(canvas, i:int) -> Optional[str]:
  '''
  :returns: Canvas item *i*'s type (eg: "line"), as remembered, or as the
    canvas says if it isn't; None if there's no such item.
  '''
  types = _rememberedTypes(canvas)
  typ = types.get(i)
  if typ is None:
    try:
      typ = canvas.type(i) or None
    except Exception:
      typ = None
    if typ is not None:
      types[i] = typ
  return typ

def forgetItem(canvas, i:int) -> None:
  '''
  Forget item *i*'s type and options (it's gone).
  '''
  _rememberedTypes(canvas).pop(i, None)
  _rememberedOptions(canvas).pop(i, None)

# Likewise the options an item was last configured with here: a redraw in place
# sets every item's colours, width and tags again, every frame, though they
# seldom change -- a round-trip to Tk each. An item configured with the same
# options as last time is left alone. Anything that configures an item behind
# this module's back (eg: recolorMarks(), here) forgets its options, so the next
# draw sets them again.

_OPTIONS_ATTR = "_lineMarksItemOptions"

def _rememberedOptions(canvas) -> dict[int, tuple]:
  '''
  :returns: The options (see _optionsKey()) *canvas*'s items were last configured with here, by id.
  '''
  options = canvas.__dict__.get(_OPTIONS_ATTR)
  if options is None:
    options = {}
    setattr(canvas, _OPTIONS_ATTR, options)
  elif len(options) > 200_000: # (as _rememberedTypes())
    options.clear()
  return options

def _optionsKey(tags:Sequence[str], opts:dict[str, Any]) -> tuple:
  '''
  :returns: *tags* and *opts*, as something to compare with next time's.
  '''
  return (tuple(tags), tuple(sorted((k, repr(v)) for k, v in opts.items())))

def configureItem(canvas, i:int, tags:Sequence[str], opts:dict[str, Any]) -> None:
  '''
  Configure canvas item *i* with *tags* and *opts* -- unless it was last
  configured with the same, here (see *forgetItem()*).

  :raises Exception: As the canvas does, if there's no such item.
  '''
  key = _optionsKey(tags, opts)
  remembered = _rememberedOptions(canvas)
  if remembered.get(i) == key:
    return
  canvas.itemconfigure(i, tags=list(tags), **opts)
  remembered[i] = key

def deleteItem(canvas, i:int) -> None:
  '''
  Delete canvas item *i* (if it's still there), and forget it.
  '''
  forgetItem(canvas, i)
  try:
    canvas.delete(i)
  except Exception:
    pass

def backgroundColor(canvas) -> str:
  '''
  :returns: *canvas*'s background colour (what a *HOLLOW* mark is filled with) -- "" if it can't say.
  '''
  try:
    return str(canvas.cget("background") or "")
  except Exception:
    return ""

def _roleOptions(role:str, lineColor:str, fillColor:str, typ:str, backColor:str="") -> dict[str, Any]:
  '''
  The colour options of a polygon or oval of *role*.
  '''
  if role == SOLID:
    return dict(fill=lineColor, outline="")
  if role == DOT:
    return dict(fill=lineColor, outline=lineColor)
  if role == OPEN:
    return dict(fill=fillColor, outline=lineColor)
  if role == HOLLOW:
    return dict(fill=backColor, outline=lineColor)
  return dict(fill=lineColor)

def recolorMarks(canvas, ids:Sequence[int], lineColor:str, fillColor:str, backColor:Optional[str]=None) -> None:
  '''
  Colour items *drawMarks()* drew (or any line items) afresh, each as its role says (see *ROLES*).

  :param backColor: What *HOLLOW* items are filled with (default: the canvas's background).
  '''
  for i in ids:
    try:
      tags = canvas.gettags(i)
      typ = canvas.type(i)
    except Exception:
      continue
    role = next((t for t in tags if t in ROLES), STROKE if typ == "line" else OPEN)
    if typ == "line":
      canvas.itemconfigure(i, fill=lineColor)
    else:
      if role == HOLLOW and backColor is None:
        backColor = backgroundColor(canvas) # (once, when it's needed)
      canvas.itemconfigure(i, **_roleOptions(role, lineColor, fillColor, typ, backColor or ""))
    _rememberedOptions(canvas).pop(i, None) # (not as drawn: the next draw sets its options again)

def _identity(coords:list[float]) -> list[float]:
  return coords

def drawMarks(canvas, layout:MarkLayout, origin:Point, direction:Point, *,
              width:float=1.0, strokeWidth:Optional[float]=None,
              lineColor:str="black", fillColor:str="", backColor:Optional[str]=None, tags:Sequence[str]=(),
              existing:Sequence[int]=(), toWindow:Optional[Callable[[list[float]], list[float]]]=None,
              lineOptions:Optional[dict[str, Any]]=None) -> list[int]:
  '''
  Draw laid-out marks (see *layoutMarks()*) and the bits of line among them.

  :param canvas: The Tk canvas.
  :param layout: Where they go: distances from *origin*.
  :param origin: The point they were laid out at (eg: the line's end).
  :param direction: Which way the line runs there (toward its end): any length.
  :param width: The line's width, in the units of *origin* (for the marks' sizes: eg: an arrowhead's).
  :param strokeWidth: The width of the lines drawn (bars, and the bits of line), as the canvas takes it
    (default: *width*).
  :param lineColor: The line's colour.
  :param fillColor: Circles' fill colour.
  :param backColor: What hollow marks (rings) are filled with: the canvas's background, by default.
  :param tags: Canvas tags for every item (and each gets its role too: see *ROLES*).
  :param existing: The items an earlier call drew for these marks: reused, so a redraw doesn't make new ones.
  :param toWindow: Converts a flat list of coordinates to the canvas's (default: as they are).
  :param lineOptions: Options for the bits of line (eg: dash), as for the line itself.
  :returns: The items drawn (pass them back as *existing* next time).
  '''
  pen = _Pen(canvas, origin, direction, existing, tags, toWindow or _identity, lineColor, fillColor,
             width if strokeWidth is None else strokeWidth, backColor)
  opts = dict(lineOptions or {})
  for a, b in layout.joiners: # (first: under the marks)
    pen.line([pen.pt(a), pen.pt(b)], STROKE, **opts)
  for p in layout.marks:
    p.kind.draw(pen, p.x0, p.x1, p.mark.sizes, width, p.forward)
  return pen.finish()


# =============================================================================
# Paths: a straight segment [p0, p1], or a quadratic Bezier [p0, control, p1]
# (as Tk draws a 3-point line with smooth=True)
# =============================================================================

def pathPoint(path:Sequence[Point], t:float) -> Point:
  '''
  :returns: The point at parameter *t* (0..1) along *path*.
  '''
  if len(path) == 2:
    (x0, y0), (x1, y1) = path
    return (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t)
  p0, p1, p2 = path
  mt = 1 - t
  return (mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0],
          mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1])

def subPath(path:Sequence[Point], t0:float, t1:float) -> list[Point]:
  '''
  :returns: The part of *path* from parameter *t0* to *t1*, exactly (a quadratic's own control point too).
  '''
  if len(path) == 2:
    return [pathPoint(path, t0), pathPoint(path, t1)]
  p0, p1, p2 = path
  w0, w1, w2 = (1 - t0) * (1 - t1), t0 * (1 - t1) + t1 * (1 - t0), t0 * t1
  c = (w0 * p0[0] + w1 * p1[0] + w2 * p2[0], w0 * p0[1] + w1 * p1[1] + w2 * p2[1])
  return [pathPoint(path, t0), c, pathPoint(path, t1)]

def paramAtDistance(path:Sequence[Point], d:float, fromEnd:bool=False) -> Optional[float]:
  '''
  :returns: The parameter of the point on *path* *d* away (in a straight line)
    from its start (or end) -- the nearest such -- or None if all of it is closer.
  '''
  if d <= 0:
    return 1.0 if fromEnd else 0.0
  ref = path[-1] if fromEnd else path[0]
  far = 0.0 if fromEnd else 1.0
  dist = lambda t: math.hypot(pathPoint(path, t)[0] - ref[0], pathPoint(path, t)[1] - ref[1])
  if len(path) == 2:
    total = dist(far)
    if total < d:
      return None
    return 1.0 - d / total if fromEnd else d / total
  # A quadratic. The distances asked for are small next to the path (a few
  # marks' worth), where dist() grows with t and is nearly linear: guess from
  # the speed at the near end, then correct by secant steps -- a handful of
  # evaluations, not the 60-odd a scan-and-bisect takes.
  near = 1.0 - far
  speed = 2 * math.hypot(path[1][0] - ref[0], path[1][1] - ref[1]) # (|B'| at the near end)
  if speed > 0:
    a, fa = near, -d
    b = near + (far - near) * min(1.0, d / speed)
    fb = dist(b) - d
    for _ in range(12):
      if abs(fb) <= 1e-4:
        return b
      if fb == fa:
        break
      c = b - fb * (b - a) / (fb - fa)
      if not (min(near, far) <= c <= max(near, far)) or c == b:
        break
      a, fa, b, fb = b, fb, c, dist(c) - d
  # (not found that way -- eg: the curve bends back toward the end, or all of
  # it is closer than d: the first point that far out, by stepping, then bisecting)
  steps = 32
  prev = near
  for k in range(1, steps + 1):
    t = near + (far - near) * k / steps
    if dist(t) >= d:
      lo, hi = prev, t
      for _ in range(30):
        mid = (lo + hi) / 2
        if dist(mid) < d:
          lo = mid
        else:
          hi = mid
      return hi
    prev = t
  return None

def pathDirection(path:Sequence[Point], atEnd:bool, over:float=0.0) -> Point:
  '''
  :returns: Which way *path* runs (toward its end) at its start (or end):
    the direction of the chord over its first (or last) *over* units -- or
    its tangent there, if *over* is 0 (or more than the path's length).
  '''
  t = paramAtDistance(path, over, fromEnd=atEnd) if over > 0 else None
  if t is not None:
    a, b = (pathPoint(path, t), path[-1]) if atEnd else (path[0], pathPoint(path, t))
  else:
    a, b = (path[-2], path[-1]) if atEnd else (path[0], path[1])
  dx, dy = b[0] - a[0], b[1] - a[1]
  if dx == 0 and dy == 0:
    dx, dy = path[-1][0] - path[0][0], path[-1][1] - path[0][1]
  n = math.hypot(dx, dy) or 1.0
  return (dx / n, dy / n)


@dataclass
class MarkedPathIDs:
  '''
  The canvas items *drawMarkedPath()* drew: pass it back in to have them redrawn in place.
  '''
  line:Optional[int] = None
  start:list[int] = field(default_factory=list)
  end:list[int] = field(default_factory=list)

  def all(self) -> list[int]:
    '''
    :returns: All its items.
    '''
    return ([self.line] if self.line is not None else []) + self.start + self.end

  def deleteAll(self, canvas) -> None:
    '''
    Delete all its items.
    '''
    for i in self.all():
      deleteItem(canvas, i)
    self.line, self.start, self.end = None, [], []

def drawMarkedPath(canvas, path:Sequence[Point], startMarks:Sequence[Mark]|str|None=None,
                   endMarks:Sequence[Mark]|str|None=None, ids:Optional[MarkedPathIDs]=None, *,
                   width:float=1.0, strokeWidth:Optional[float]=None,
                   lineColor:str="black", fillColor:str="", backColor:Optional[str]=None, tags:Sequence[str]=(),
                   toWindow:Optional[Callable[[list[float]], list[float]]]=None,
                   lineOptions:Optional[dict[str, Any]]=None) -> MarkedPathIDs:
  '''
  Draw *path* -- a straight line [p0, p1], or a smooth one [p0, control, p1]
  -- with marks at its start and end: the line is cut back where they stop it.

  :param ids: The items an earlier call drew: redrawn in place (None: new ones).
  :param lineOptions: More options for the line (eg: dash): it's drawn with
    *lineColor*, *strokeWidth*, no arrowheads (they're marks), and smooth if it has 3 points.
  :returns: The items drawn. (No line if the marks leave none of it.)

  The other parameters are as *drawMarks()*'s.
  '''
  ids = ids if ids is not None else MarkedPathIDs()
  toWindow = toWindow or _identity
  sw = width if strokeWidth is None else strokeWidth
  startLayout = layoutMarks(startMarks, START, width)
  endLayout = layoutMarks(endMarks, END, width)
  t0 = paramAtDistance(path, startLayout.highStop or 0.0)
  t1 = paramAtDistance(path, -(endLayout.lowStop or 0.0), fromEnd=True)
  ret = MarkedPathIDs()
  if t0 is not None and t1 is not None and t0 < t1:
    pts = subPath(path, t0, t1) if (t0, t1) != (0.0, 1.0) else list(path)
    coords = toWindow([c for p in pts for c in p])
    opts:dict[str, Any] = dict(fill=lineColor, width=sw, arrow="none", smooth=len(pts) == 3)
    opts.update(lineOptions or {})
    ret.line = None
    if ids.line is not None and itemType(canvas, ids.line) == "line":
      try:
        canvas.coords(ids.line, coords)
        configureItem(canvas, ids.line, tags, opts)
        ret.line = ids.line
      except Exception: # (gone)
        forgetItem(canvas, ids.line)
    if ret.line is None:
      if ids.line is not None:
        deleteItem(canvas, ids.line)
      ret.line = canvas.create_line(coords, tags=list(tags), **opts)
      _rememberedTypes(canvas)[ret.line] = "line"
      _rememberedOptions(canvas)[ret.line] = _optionsKey(tags, opts)
  elif ids.line is not None:
    deleteItem(canvas, ids.line)
  common:dict[str, Any] = dict(width=width, strokeWidth=sw, lineColor=lineColor, fillColor=fillColor,
                               backColor=backColor, tags=tags, toWindow=toWindow, lineOptions=lineOptions)
  ret.start = drawMarks(canvas, startLayout, path[0], pathDirection(path, False, startLayout.high),
                        existing=ids.start, **common)
  ret.end = drawMarks(canvas, endLayout, path[-1], pathDirection(path, True, -endLayout.low),
                      existing=ids.end, **common)
  return ret

