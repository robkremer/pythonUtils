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
*util.choiceDialog.askChoice()*: a button for each choice, the first the
right-most; Return makes the default choice, Escape (or closing the window)
the cancel one.

Created on Oct 24, 2026

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''
import unittest
import tkinter as tk
from util.choiceDialog import ChoiceDialog
from util.utils import frameOffset

CHOICES = ["Update", "Replace", "Cancel"]

class TestChoiceDialog(unittest.TestCase):

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

  def ask(self, act, **kwargs) -> str|None:
    'Show the dialog, and do *act* to it once it\'s up: what\'s chosen.'
    d = ChoiceDialog(self.root, "Title", "Which?", CHOICES, **kwargs)
    d.after(50, lambda: act(d))
    return d.show()

  def test_buttons(self):
    'A button for each choice, the first the right-most; its default shown as such.'
    d = ChoiceDialog(self.root, "Title", "Which?", CHOICES, default="Update", cancel="Cancel", icon="warning")
    d.update()
    self.assertEqual(list(d.buttons), CHOICES)
    xs = [d.buttons[c].winfo_x() for c in CHOICES]
    self.assertEqual(xs, sorted(xs, reverse=True))
    self.assertEqual(str(d.buttons["Update"].cget("default")), "active")
    d.destroy()

  def test_choose(self):
    self.assertEqual(self.ask(lambda d: d.buttons["Replace"].invoke(), default="Update", cancel="Cancel"), "Replace")

  def test_keys(self):
    'Return: the default; Escape or closing the window: the cancel choice (None, if there isn\'t one).'
    self.assertEqual(self.ask(lambda d: d.event_generate("<Return>"), default="Update", cancel="Cancel"), "Update")
    self.assertEqual(self.ask(lambda d: d.event_generate("<Escape>"), default="Update", cancel="Cancel"), "Cancel")
    self.assertEqual(self.ask(lambda d: d.tk.call(d.protocol("WM_DELETE_WINDOW")), cancel="Cancel"), "Cancel")
    self.assertIsNone(self.ask(lambda d: d.event_generate("<Escape>")))

  def test_onScreen(self):
    'With no window on screen (only the hidden root): in the middle of the screen, wholly on it.'
    d = ChoiceDialog(self.root, "Title", "Which? " * 40, CHOICES, icon="warning")
    d.update()
    x, y, w, h = d.winfo_x(), d.winfo_y(), d.winfo_width(), d.winfo_height()
    sw, sh = d.winfo_screenwidth(), d.winfo_screenheight()
    self.assertTrue(0 <= x and x + w <= sw and 0 <= y and y + h <= sh, (x, y, w, h, sw, sh))
    self.assertLessEqual(abs(x + w / 2 - sw / 2), 2, (x, y, w, h, sw, sh)) # (centred across)
    d.destroy()

  def test_overParent(self):
    'Over a window on screen: centred across it.'
    top = tk.Toplevel(self.root)
    top.geometry("600x400+100+100")
    top.update()
    d = ChoiceDialog(top, "Title", "Which?", CHOICES)
    d.update()
    self.assertLessEqual(abs((d.winfo_rootx() + d.winfo_width() / 2) - (top.winfo_rootx() + top.winfo_width() / 2)), 2)
    d.destroy()
    top.destroy()

  def test_frameOffset(self):
    'Where a window\'s inside is in its frame: none for a window that isn\'t shown.'
    self.assertEqual(frameOffset(self.root), (0, 0))
    top = tk.Toplevel(self.root)
    top.geometry("300x200+120+140")
    top.update()
    dx, dy = frameOffset(top)
    self.assertTrue(0 <= dx <= 100 and 0 <= dy <= 200, (dx, dy))
    self.assertEqual((top.winfo_rootx() - dx, top.winfo_rooty() - dy), (120, 140)) # (the frame's where it was put)
    top.destroy()

  def test_badIcon(self):
    with self.assertRaises(ValueError):
      ChoiceDialog(self.root, "Title", "Which?", CHOICES, icon="smiley")

if __name__ == "__main__":
  unittest.main()
