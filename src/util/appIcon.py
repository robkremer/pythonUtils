'''
The program's icon on its windows (*setAppIcon()*), so it's clear they're
the program's: every window and dialog gets it.

- On Windows and Linux it's in each window's title bar, and its entry in the
  task bar (Tk's own -- a feather -- otherwise, even in a packaged app: Tk
  takes it from its own library, not the program).
- On macOS windows have no icon: it's the app's icon instead -- the Dock's,
  and the one its alerts (*tkinter.messagebox*) show -- when the program's
  run from its source (with Python's -- a rocket -- otherwise). A packaged
  app's bundle has its own, sharper, so that's left as it is.

And the program's own message-style dialogs (a message and its buttons, a
question, an error report) show the icon the platform's own alerts do
(*alertIcon()*): on macOS the program's, inside the dialog at its top left
(where the system's alerts have it); elsewhere Tk's icon for what it says
(eg: "warning"), if anything, as *tkinter.messagebox*'s do.

Created on Nov 19, 2026

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
import base64
import logging
import sys
import tkinter as tk
from typing import Optional
from util.platformSupport import MAC

logger = logging.getLogger(__name__)

Picture = tk.PhotoImage|str|bytes
"A picture: one already made, a picture file's path, or its contents (PNG or GIF)."

ALERT_SIZE = 64
"How big (pixels square) *alertIcon()*'s icon is on macOS: the size of the system's alerts' icon."

TK_ICONS = {"error": "::tk::icons::error", "info": "::tk::icons::information",
            "question": "::tk::icons::question", "warning": "::tk::icons::warning"}
"Tk's own icons (its images' names, 32 pixels square), for what a message says: as *tkinter.messagebox*'s *icon* names them."

BADGES = ("error", "warning")
"The icons that *alertIcon()* shows at the corner of the program's icon on macOS: the ones that warn."

_icons:list[tk.PhotoImage] = []
"The program's icon, largest first, once it's set (see *setAppIcon()*): kept, since Tk forgets a picture Python no longer refers to."

_alertIcons:dict[Optional[str], tk.PhotoImage] = {}
"*alertIcon()*'s icons on macOS, by the icon at their corner (if any): kept, made once."

def photo(master:tk.Misc, picture:Picture) -> tk.PhotoImage:
  '''
  :param picture: A picture: one already made, a picture file's path, or its contents (PNG or GIF).
  :returns: It, as a picture to show.
  '''
  if isinstance(picture, tk.PhotoImage):
    return picture
  if isinstance(picture, bytes):
    return tk.PhotoImage(master=master, data=base64.b64encode(picture).decode("ascii"))
  return tk.PhotoImage(master=master, file=picture)

def packagedMacApp() -> bool:
  '''
  :returns: Whether this is a packaged macOS app (eg: PyInstaller's): its
    bundle has an icon of its own -- not Python's.
  '''
  return MAC and bool(getattr(sys, "frozen", False))

def setAppIcon(root:tk.Tk, *pictures:Optional[Picture]) -> list[tk.PhotoImage]:
  '''
  Give every window the program's icon (see above): *root*, and every window
  made after it. Call it once, as the program starts, before it makes any
  other window. Pictures that aren't there (None) are left out, and if
  none is, or Tk can't use them, nothing's changed.

  :param root: The program's root window (its *tk.Tk*).
  :param pictures: The icon at a size or two, largest first (eg: 128 and 32
    pixels square): on Windows and Linux the window manager uses the one
    nearest the size it shows (eg: the small one in title bars); macOS uses
    only the first.
  :returns: The icon's pictures, largest first (empty if there are none, or they couldn't be used).
  '''
  try:
    photos = [photo(root, p) for p in pictures if p is not None]
  except tk.TclError as ex:
    logger.warning(f"The program's icon couldn't be read: {ex}")
    return []
  if not photos:
    return []
  if not packagedMacApp(): # (a packaged Mac app's own is sharper: Tk's would replace it with the picture)
    try:
      root.wm_iconphoto(True, *photos)
    except tk.TclError as ex:
      logger.warning(f"The program's icon couldn't be set: {ex}")
      return []
  _icons[:] = photos
  _alertIcons.clear()
  return list(photos)

def appIcon(size:Optional[int]=None) -> Optional[tk.PhotoImage]:
  '''
  :param size: How big it's wanted (pixels square), if it matters.
  :returns: The program's icon, if it's been set (see *setAppIcon()*): its
    smallest picture that's at least *size* (a smaller copy of it looks
    better than a bigger one of a smaller), or its largest.
  '''
  if not _icons:
    return None
  big = [p for p in _icons if size is not None and p.width() >= size]
  return min(big, key=lambda p: p.width()) if big else max(_icons, key=lambda p: p.width())

def alertIcon(master:tk.Misc, icon:Optional[str]=None, tkIcon:bool=True) -> tk.PhotoImage|str|None:
  '''
  The icon for a message-style dialog (a message and its buttons, a question,
  an error report): the one the platform's own alerts show.

  - On macOS, the program's icon (see *setAppIcon()*), *ALERT_SIZE* pixels
    square, as the system's alerts show it (the program's -- the app's --
    icon at their top left), with Tk's icon for *icon* at its bottom right
    corner if it warns (*BADGES*). Until the program's icon's set, it's as
    elsewhere.
  - Elsewhere, Tk's icon for *icon*, as *tkinter.messagebox*'s show (and the
    program's icon is in the dialog's title bar).

  :param master: A widget of the dialog's (Tk's images are its interpreter's).
  :param icon: What the message says, if anything in particular: "error", "info",
    "question" or "warning" (see *TK_ICONS*), as *tkinter.messagebox*'s *icon* says.
  :param tkIcon: Whether there's Tk's icon for *icon* where the program's
    isn't shown (off macOS, or before it's set): else none there -- eg, for
    a dialog that's never had one.
  :returns: The icon (a picture, or the name of one of Tk's), or None for none.
  '''
  if icon is not None and icon not in TK_ICONS:
    raise ValueError(f'icon "{icon}" isn\'t one of {", ".join(TK_ICONS)}.')
  tkImage = TK_ICONS[icon] if icon is not None and tkIcon else None
  base = appIcon(ALERT_SIZE) if MAC else None
  if base is None:
    return tkImage
  badge = icon if icon in BADGES else None
  made = _alertIcons.get(badge)
  if made is None:
    try:
      made = tk.PhotoImage(master=master)
      factor = max(1, round(base.width() / ALERT_SIZE))
      made.tk.call(made, "copy", base, "-subsample", factor, factor) # (a smaller copy, if it's bigger)
      if badge is not None:
        name = TK_ICONS[badge]
        bw, bh = int(made.tk.call("image", "width", name)), int(made.tk.call("image", "height", name))
        made.tk.call(made, "copy", name, "-to", made.width() - bw, made.height() - bh) # (over it: Tk's copy overlays a picture with see-through parts)
    except tk.TclError as ex:
      logger.warning(f"The program's icon couldn't be made for its alerts: {ex}")
      return tkImage
    _alertIcons[badge] = made
  return made
