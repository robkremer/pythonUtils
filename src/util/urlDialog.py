'''
Asking for a URL (*askURL()*): the counterpart, for a file somewhere other than
this computer (eg: on the web), of *tkinter.filedialog.askopenfilename()* -- as
"Open Location..." is to "Open..." in a web browser. (The file dialogs are the
platform's own -- on macOS, its open panel -- and can't be extended to take a
URL.)

Created on Oct 12, 2026

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
from tkinter import ttk
from typing import Callable, Optional
from urllib.parse import urlparse
from util.utils import ownDialog

SCHEMES = ("http", "https", "file")
"The kinds of URL *askURL()* takes, unless told otherwise."

def urlProblem(url:str, schemes:tuple[str, ...]=SCHEMES) -> Optional[str]:
  '''
  :param url:
  :type url: str
  :param schemes: The kinds of URL that will do.
  :type schemes: tuple[str, ...]
  :returns: What's wrong with *url* as a URL (eg: no "https://"), or None if
    it looks right. (Whether there's anything there isn't checked.)
  :rtype: Optional[str]
  '''
  if not url:
    return "Type a URL."
  parsed = urlparse(url)
  if parsed.scheme.lower() not in schemes:
    return f'A URL starts with {" or ".join(s + ":" for s in schemes)}, eg: "https://example.org/folder/name".'
  if parsed.scheme.lower() == "file":
    if not parsed.path.startswith("/"):
      return 'A "file:" URL is "file:///" followed by the file\'s path.'
  elif not parsed.netloc:
    return f'There\'s no host in it: "{parsed.scheme}://host/path".'
  return None

class URLDialog(tk.Toplevel):
  '''
  A URL to type (or paste), checked before it's taken (see *askURL()*). Modal:
  *show()* returns it, if OK'd.
  '''

  def __init__(self, parent:tk.Misc, title:str, prompt:str="", initial:str="", recent:list[str]=[],
               check:Optional[Callable[[str], Optional[str]]]=None, schemes:tuple[str, ...]=SCHEMES):
    super().__init__(parent)
    ownDialog(self, parent) # (over its parent's window, not full screen: see ownDialog())
    self.parent = parent
    self.title(title)
    self.check = check
    self.schemes = schemes
    self.result:Optional[str] = None
    frame = ttk.Frame(self, padding=10)
    frame.pack(fill=tk.BOTH, expand=True)
    if prompt:
      ttk.Label(frame, text=prompt, wraplength=480, justify=tk.LEFT).pack(anchor=tk.W, pady=(0, 6))
    self.var = tk.StringVar(value=initial)
    self.entry = ttk.Combobox(frame, textvariable=self.var, values=list(recent), width=64)
    self.entry.pack(fill=tk.X)
    self.message = ttk.Label(frame, foreground="red3", wraplength=480, justify=tk.LEFT)
    self.message.pack(anchor=tk.W, pady=(4, 0))
    buttons = ttk.Frame(frame)
    buttons.pack(fill=tk.X, pady=(8, 0))
    self.okButton = ttk.Button(buttons, text="OK", command=self.ok, default="active")
    self.okButton.pack(side=tk.RIGHT, padx=(6, 0))
    ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)
    self.bind("<Return>", lambda _e: self.ok())
    self.bind("<Escape>", lambda _e: self.destroy())
    self.var.trace_add("write", lambda *_: self.message.configure(text=""))

  def ok(self) -> None:
    '''
    Take the URL -- if it looks right (see *urlProblem()*), and *check* (if
    there is one) finds nothing wrong with it; else say what's wrong.
    '''
    url = self.var.get().strip()
    problem = urlProblem(url, self.schemes)
    if problem is None and self.check is not None:
      self.message.configure(text="Checking...", foreground="gray35")
      self.okButton.state(["disabled"])
      self.update_idletasks()
      try:
        problem = self.check(url)
      except Exception as e:
        problem = str(e) or type(e).__name__
      finally:
        if self.winfo_exists():
          self.okButton.state(["!disabled"])
    if problem is not None:
      self.message.configure(text=problem, foreground="red3")
      return
    self.result = url
    self.destroy()

  def show(self) -> Optional[str]:
    ''':returns: The URL, if OK'd; else None.'''
    try:
      self.wait_visibility()
      self.grab_set()
      self.lift()
      self.entry.focus_set()
      self.entry.icursor(tk.END)
    except tk.TclError:
      pass
    self.wait_window()
    return self.result

def askURL(parent:tk.Misc, title:str="Open URL", prompt:str="", initial:str="", recent:list[str]=[],
           check:Optional[Callable[[str], Optional[str]]]=None, schemes:tuple[str, ...]=SCHEMES) -> Optional[str]:
  '''
  Ask for a URL.

  :param parent: The window it's over.
  :type parent: tk.Misc
  :param title:
  :type title: str
  :param prompt: Said above where it's typed.
  :type prompt: str
  :param initial: What's there to start with.
  :type initial: str
  :param recent: URLs to choose from (eg: those used recently).
  :type recent: list[str]
  :param check: Given the URL, what's wrong with it (eg: there's nothing
    there, or it isn't the kind of file that's wanted), or None if it'll do:
    until it is, it's asked for again. (Exceptions it raises are what's wrong.)
  :type check: Optional[Callable[[str], Optional[str]]]
  :param schemes: The kinds of URL that will do.
  :type schemes: tuple[str, ...]
  :returns: The URL, or None if cancelled.
  :rtype: Optional[str]
  '''
  return URLDialog(parent, title, prompt, initial, recent, check, schemes).show()
