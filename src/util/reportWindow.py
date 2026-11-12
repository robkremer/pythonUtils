'''
A window that shows a report (*ReportWindow*): text that can be read and
copied, but not changed -- eg: what a command worked out -- with, above it,
any controls its maker adds (eg: buttons choosing what's reported).

Created on Nov 12, 2026

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
import tkinter as tk
from contextlib import contextmanager
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from typing import Any, Iterator
from util.utils import ownDialog

class ReportWindow:
  '''
  A window showing a report: its text (in a fixed-width font: reports line
  things up), which can be selected and copied but not changed; Copy (all of
  it, to the clipboard) and Close buttons; and, above it, *controls*, a frame
  its maker can put widgets in (eg: radio buttons choosing what's reported,
  that call *show()* with the new text). Not modal: it stays open while the
  user works in other windows (it's let go of by the window it's opened over,
  once shown: see *util.utils.ownDialog()*). Escape closes it too.
  '''
  def __init__(self, parent:Any, title:str, text:str="", width:int=72, height:int=28):
    '''
    :param parent: The window it's opened over, if any.
    :param title: Its title.
    :param text: The report (see *show()*).
    :param width: How wide its text is (characters).
    :param height: How tall (lines).
    '''
    self.top:tk.Toplevel = tk.Toplevel(parent)
    top = self.top
    ownDialog(top, parent, keep=False)
    top.title(title)
    frame = ttk.Frame(top, padding=10)
    frame.pack(fill=tk.BOTH, expand=True)
    self.controls:ttk.Frame = ttk.Frame(frame)
    "Where its maker puts its controls, above the text (empty, it takes no room)."
    self.controls.pack(fill=tk.X)
    self.text:ScrolledText = ScrolledText(frame, width=width, height=height, wrap=tk.NONE, font="TkFixedFont")
    self.text.pack(fill=tk.BOTH, expand=True, pady=(8, 8))
    bottom = ttk.Frame(frame)
    bottom.pack(fill=tk.X)
    ttk.Button(bottom, text="Close", command=self.close, default="active").pack(side=tk.RIGHT, padx=6)
    ttk.Button(bottom, text="Copy", command=self.copy).pack(side=tk.RIGHT, padx=6)
    top.bind("<Escape>", lambda _e: self.close())
    self.show(text)
    top.lift()
    top.focus_force()

  def show(self, text:str) -> None:
    '''
    Show *text* as the report, in place of what was there.

    :param text: The report.
    '''
    self.text.config(state="normal")
    self.text.delete("1.0", "end")
    self.text.insert("1.0", text)
    self.text.config(state="disabled")

  def report(self) -> str:
    ''':returns: The report shown.'''
    return self.text.get("1.0", "end-1c")

  def copy(self) -> None:
    '''Put the report on the clipboard.'''
    self.top.clipboard_clear()
    self.top.clipboard_append(self.report())

  @contextmanager
  def busy(self) -> Iterator[None]:
    '''While in it, the window shows a busy (watch) cursor: eg, while what it reports is worked out.'''
    self.top.config(cursor="watch")
    self.top.update_idletasks()
    try:
      yield
    finally:
      try:
        self.top.config(cursor="")
      except tk.TclError: # (closed meanwhile)
        pass

  def close(self) -> None:
    '''Close the window.'''
    self.top.destroy()
