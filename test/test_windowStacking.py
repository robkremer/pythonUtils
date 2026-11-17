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
*util.windowStacking*: the order windows are stacked in on the screen, and
stacking them in an order again -- windows just made too, before they're on
the screen; those hidden aren't shown, and come first.

Created on Nov 17, 2026

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''
import time
import unittest
from unittest import mock
import tkinter as tk
from util.windowStacking import stackingOrder, restack

class TestWindowStacking(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    try:
      cls.root = tk.Tk()
    except tk.TclError as ex:
      raise unittest.SkipTest(f"no display: {ex}")
    cls.root.withdraw()

  @classmethod
  def tearDownClass(cls):
    cls.root.destroy()

  def setUp(self):
    self.windows:list[tk.Toplevel] = []

  def tearDown(self):
    for w in self.windows:
      w.destroy()
    self.root.update()

  def make(self, count:int) -> list[tk.Toplevel]:
    'Make *count* windows, overlapping one another (not yet on the screen).'
    made = []
    for i in range(count):
      w = tk.Toplevel(self.root)
      w.title(f"window {i}")
      w.geometry(f"240x160+{60 + 30*i}+{80 + 30*i}")
      made.append(w)
    self.windows += made
    return made

  def settle(self, windows:list[tk.Toplevel], expected:list[tk.Toplevel], seconds:float=3) -> list[tk.Toplevel]:
    'Let the window manager catch up (eg: on Linux, it stacks them when it gets to it): *windows* in their stacking order, once it\'s *expected* (or the time\'s up).'
    end = time.monotonic() + seconds
    while True:
      self.root.update()
      order = stackingOrder(windows)
      if order == expected or time.monotonic() > end:
        return order
      time.sleep(0.02)

  def test_stackingOrder(self):
    'The windows from the one at the back to the one in front, however they were made; hidden ones first, as given.'
    a, b, c, d = self.make(4)
    self.settle([a, b, c, d], [a, b, c, d], seconds=0.5) # (on the screen, in whatever order)
    for w in (c, a, d, b):
      w.lift()
    self.assertEqual(self.settle([a, b, c, d], [c, a, d, b]), [c, a, d, b])
    self.assertEqual(stackingOrder([d, b]), [d, b]) # (just those asked about)
    self.assertEqual(stackingOrder([]), [])
    d.withdraw()
    self.assertEqual(self.settle([a, b, c, d], [d, c, a, b]), [d, c, a, b])
    self.assertEqual(stackingOrder([self.root, b, a]), [self.root, a, b]) # (the hidden main window first)

  def test_restack(self):
    'Windows just made, stacked as asked -- the one in front given the focus; a hidden one stays hidden.'
    a, b, c, d = self.make(4)
    d.withdraw()
    with mock.patch.object(a, "focus_force") as focus:
      restack([c, b, d, a])
    focus.assert_called_once_with()
    self.assertEqual(self.settle([a, b, c, d], [d, c, b, a]), [d, c, b, a])
    self.assertEqual(d.state(), "withdrawn")
    restack([a, c, b], focus=False) # (again, the other way)
    self.assertEqual(self.settle([a, b, c], [a, c, b]), [a, c, b])
    restack([]) # (nothing to do)
    b.destroy()
    restack([b, a]) # (a window destroyed meanwhile: just left out)
    self.assertEqual(self.settle([a, c], [c, a]), [c, a])


if __name__ == "__main__":
  unittest.main()
