'''
Asking the user to choose one of several things to do (*askChoice()*): a
message, with a button for each choice -- for when OK/Cancel or Yes/No/Cancel
(*tkinter.messagebox*) doesn't say what the choices are (eg: "Update",
"Replace", "Cancel").

Created on Oct 24, 2026

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
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Optional
from util.utils import ownDialog

ICONS = ("error", "info", "question", "warning")
"The icons a *ChoiceDialog* can show (Tk's own: as *tkinter.messagebox* shows)."

class ChoiceDialog(tk.Toplevel):
  '''
  A message, with a button for each choice, right to left: the first choice
  is the right-most (where the default button goes on macOS and Windows).
  Modal: *show()* returns the choice made.
  '''

  def __init__(self, parent:tk.Misc|None, title:str, message:str, choices:list[str], default:Optional[str]=None,
               cancel:Optional[str]=None, detail:str="", icon:Optional[str]=None):
    super().__init__(parent)
    ownDialog(self, parent) # (over its parent's window, not full screen: see ownDialog())
    self.title(title)
    self.resizable(False, False)
    self.cancelChoice = cancel
    self.result:Optional[str] = None
    frame = ttk.Frame(self, padding=14)
    frame.pack(fill=tk.BOTH, expand=True)
    frame.columnconfigure(1, weight=1)
    if icon is not None:
      if icon not in ICONS:
        raise ValueError(f'icon "{icon}" isn\'t one of {", ".join(ICONS)}.')
      ttk.Label(frame, image=f"::tk::icons::{icon}").grid(row=0, column=0, rowspan=2, sticky=tk.N, padx=(0, 12))
    ttk.Label(frame, text=message, wraplength=440, justify=tk.LEFT).grid(row=0, column=1, sticky=tk.W)
    if detail:
      ttk.Label(frame, text=detail, wraplength=440, justify=tk.LEFT, foreground="gray35") \
        .grid(row=1, column=1, sticky=tk.W, pady=(8, 0))
    buttons = ttk.Frame(frame)
    buttons.grid(row=2, column=0, columnspan=2, sticky=tk.E, pady=(14, 0))
    self.buttons:dict[str, ttk.Button] = {}
    for c in choices:
      b = ttk.Button(buttons, text=c, command=lambda c=c: self.choose(c), default="active" if c == default else "normal") #type: ignore[misc]
      b.pack(side=tk.RIGHT, padx=(6, 0))
      self.buttons[c] = b
    if default is not None:
      self.bind("<Return>", lambda _e: self.choose(default))
    self.bind("<Escape>", lambda _e: self.choose(cancel))
    self.protocol("WM_DELETE_WINDOW", lambda: self.choose(cancel))

  def choose(self, choice:Optional[str]) -> None:
    ''':param choice: The choice made (None: none -- eg: the window was closed with no *cancel* choice).'''
    self.result = choice
    self.destroy()

  def show(self) -> Optional[str]:
    ''':returns: The choice made: the *cancel* choice if it was closed (or Escape), or None if there's no *cancel* choice.'''
    try:
      self.wait_visibility()
      self.grab_set()
      self.lift()
      self.focus_force()
    except tk.TclError:
      pass
    self.wait_window()
    return self.result

def askChoice(parent:tk.Misc|None, title:str, message:str, choices:list[str], default:Optional[str]=None,
              cancel:Optional[str]=None, detail:str="", icon:Optional[str]=None) -> Optional[str]:
  '''
  Ask the user to choose one of *choices*: eg:
  ``askChoice(window, "Save", "There's a file of that name.", ["Update", "Replace", "Cancel"], "Update", "Cancel", icon="warning")``.

  :param parent: The window it's over, if any.
  :type parent: tk.Misc | None
  :param title:
  :type title: str
  :param message: What it's about.
  :type message: str
  :param choices: The buttons' texts: the first is the right-most.
  :type choices: list[str]
  :param default: The choice Return makes (its button is shown as the default), if any.
  :type default: Optional[str]
  :param cancel: The choice Escape, or closing the window, makes, if any.
  :type cancel: Optional[str]
  :param detail: More about it, under *message*, less prominently.
  :type detail: str
  :param icon: One of *ICONS*, if any.
  :type icon: Optional[str]
  :returns: The choice made -- *cancel* if it was closed (None, if there's no *cancel*).
  :rtype: Optional[str]
  '''
  return ChoiceDialog(parent, title, message, choices, default, cancel, detail, icon).show()
