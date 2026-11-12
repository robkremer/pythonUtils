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
*util.reportWindow.ReportWindow*: a report that can be copied but not
changed, replaced by *show()*; the maker's controls above it; Copy, Close and
Escape.

Created on Nov 12, 2026

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''
import unittest
import tkinter as tk
from tkinter import ttk
from util.reportWindow import ReportWindow

class TestReportWindow(unittest.TestCase):

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

  def test_report(self):
    'Its title and text; the text read only; show() replaces it; Copy puts it all on the clipboard.'
    w = ReportWindow(self.root, "Report: net", "line 1\nline 2")
    w.top.update()
    self.assertEqual(w.top.title(), "Report: net")
    self.assertEqual(w.report(), "line 1\nline 2")
    self.assertEqual(str(w.text.cget("state")), "disabled")
    w.show("other")
    self.assertEqual(w.report(), "other")
    w.copy()
    self.assertEqual(w.top.clipboard_get(), "other")
    with w.busy():
      self.assertEqual(str(w.top.cget("cursor")), "watch")
    self.assertEqual(str(w.top.cget("cursor")), "")
    w.close()
    self.assertFalse(w.top.winfo_exists())

  def test_controls(self):
    'What its maker puts in its controls goes above the text.'
    w = ReportWindow(self.root, "Report", "text")
    b = ttk.Button(w.controls, text="Again", command=lambda: w.show("again"))
    b.pack(side=tk.LEFT)
    w.top.update()
    self.assertLess(b.winfo_rooty(), w.text.winfo_rooty())
    b.invoke()
    self.assertEqual(w.report(), "again")
    w.close()

  def test_escape(self):
    'Escape closes it.'
    w = ReportWindow(self.root, "Report", "text")
    w.top.update()
    w.top.event_generate("<Escape>")
    w.top.update()
    self.assertFalse(w.top.winfo_exists())

if __name__ == "__main__":
  unittest.main()
