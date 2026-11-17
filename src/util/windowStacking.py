'''
The order an app's windows are stacked in on the screen, one in front of
another (*stackingOrder()*), and stacking them in an order again
(*restack()*): eg, so that an app that reopens the windows it had open when it
last quit can put them back one in front of another as they were -- not in the
order they happened to be opened in (each new one in front of the last, on the
Mac and Windows; on Linux, often each behind the last).

Both use Tk's own commands for it ("wm stackorder" and "raise"), which ask the
system's window manager: so they're the same on the Mac, Windows and Linux.

Created on Nov 17, 2026

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
import logging
import tkinter as tk
from typing import Iterable, Sequence, TypeVar

logger = logging.getLogger(__name__)

W = TypeVar("W", bound=tk.Wm)
"A top-level window: a *tk.Tk* or a *tk.Toplevel*."

OFF_SCREEN = ("withdrawn", "iconic", "icon")
"The states (see *tk.Wm.state()*) of a window that isn't on the screen -- hidden, or minimized: it has no place in the stack."

def onScreen(window:tk.Wm) -> bool:
  '''
  :param window: A top-level window.
  :returns: Whether *window* is on the screen: it hasn't been destroyed, and
    isn't hidden (withdrawn) or minimized (iconified).
  '''
  try:
    return bool(window.winfo_exists()) and window.state() not in OFF_SCREEN # type: ignore[attr-defined]
  except tk.TclError:
    return False

def stackingOrder(windows:Iterable[W]) -> list[W]:
  '''
  :param windows: Some of an app's top-level windows (its *tk.Tk*, its
    *tk.Toplevel*\\ s), all of the same Tk.
  :returns: *windows*, from the one at the back to the one in front, as
    they're stacked on the screen now. Those that aren't on the screen
    (hidden or minimized), and so aren't in the stack, come first, in the
    order given. (If the window manager can't say, they're as given.)
  '''
  windows = list(windows)
  if not windows:
    return windows
  try:
    root = windows[0]._root() # type: ignore[attr-defined]
    order = [str(name) for name in root.tk.splitlist(root.tk.call("wm", "stackorder", root))] # (back to front: every top-level window on the screen)
  except tk.TclError:
    logger.warning("Couldn't get the order the windows are stacked in.", exc_info=True)
    return windows
  place = {name: i for i, name in enumerate(order)}
  stacked = [w for w in windows if str(w) in place and onScreen(w)] # (one minimized can still be listed: eg, on Linux with no window manager)
  return [w for w in windows if w not in stacked] + sorted(stacked, key=lambda w: place[str(w)])

def restack(windows:Sequence[tk.Wm], focus:bool=True) -> None:
  '''
  Stack *windows* one in front of another, in the order given -- from the one
  at the back to the one in front, as *stackingOrder()* lists them -- in front
  of the app's other windows; and give the one in front the focus. Those that
  aren't on the screen (hidden or minimized) are left as they are. Windows just
  made (that Tk hasn't yet put on the screen: it does so when it's next idle)
  are put on the screen first, so that they can be stacked.

  :param windows: Some of an app's top-level windows, all of the same Tk.
  :param focus: Whether to give the window in front the focus (as when it's
    clicked on): so that it's the active window.
  '''
  windows = [w for w in windows if onScreen(w)]
  if not windows:
    return
  try:
    windows[0].update_idletasks() # type: ignore[attr-defined] # (a new window's put on the screen when Tk's idle: it can't be stacked until then)
    windows = [w for w in windows if onScreen(w)]
    for window in windows:
      window.lift() # type: ignore[attr-defined] # (in front of all: so each in front of the one before)
    if focus and windows:
      windows[-1].focus_force() # type: ignore[attr-defined]
  except tk.TclError: # (eg: one destroyed meanwhile)
    logger.warning("Couldn't stack the windows in order.", exc_info=True)
