'''
An About box (*AboutDialog*, shown with *showAbout()*): the program's icon,
name, version and copyright, over two tabs -- its acknowledgements (*Credit*:
the people, libraries and tools it's made with, each with its web page, its
version and its licence's name) and the licences' texts -- and
*installAbout()*, which puts "About <program>" in the menus where each
platform has it.

On macOS, Tk's own "About <program>" item (first in the app's menu, the one
named after the program, next to the Apple menu) shows the standard About
panel, filled in from the running program's bundle: a packaged app's own
(its *Info.plist* and icon), but Python's when the program's run from source
(by Python). *installAbout()* replaces it with the program's own, in both.

A licence's text comes from its credit (*Credit.licenceText*: eg, Python's or
Tcl/Tk's, which aren't Python distributions), or from the files its Python
distribution's metadata names (*License-File*: eg, LICENSE, NOTICE) when it's
installed (see *licenceFiles()*): a packaged app must carry their metadata for
that (eg: PyInstaller's *copy_metadata()*).

Created on Nov 9, 2026

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
import importlib.metadata as metadata
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk
import webbrowser
from typing import Any, Callable, NamedTuple, Optional, Sequence
from util.platformSupport import MAC, shortcut
from util.utils import afterMenu, keepLast, ownDialog, placeDialog

LINK_COLOUR = "#1a73e8"
"The colour of a link (as *util.actionDialog*'s)."

DIM_COLOUR = "gray45"
"The colour of the less important text: versions, licences' names, details."

class Credit(NamedTuple):
  '''
  Something an About box acknowledges: a person, a library, a tool, ...
  '''
  name: str
  "What's acknowledged: eg, a library's name, or a person's."
  note: str = ""
  "What it is, or what it's for."
  url: Optional[str] = None
  "Its web page."
  licence: Optional[str] = None
  "Its licence's name, eg: \"MIT\"; if None, what its distribution's metadata says (see *dist*), if anything."
  dist: Optional[str] = None
  "Its Python distribution's name, as pip knows it (eg: \"nemo-python\"), if it's one: its version, and its licence's name and texts, are read from its metadata, when it's installed."
  licenceText: Optional[str] = None
  "Its licence's text, if it isn't in *dist*'s metadata (eg: Python's own, or Tcl/Tk's)."
  version: Optional[str] = None
  "Its version, if it isn't *dist*'s."

def _distribution(name:str) -> Optional[metadata.Distribution]:
  '''
  :param name: A Python distribution's name.
  :returns: Its metadata, if it's installed.
  '''
  try:
    return metadata.distribution(name)
  except (metadata.PackageNotFoundError, ValueError):
    return None

def installed(credit:Credit) -> bool:
  '''
  :param credit: Something acknowledged.
  :returns: Whether it's there: True unless it's a Python distribution (see *Credit.dist*) that isn't installed.
  '''
  return credit.dist is None or _distribution(credit.dist) is not None

def version(credit:Credit) -> Optional[str]:
  '''
  :param credit: Something acknowledged.
  :returns: Its version: *credit.version*, or its distribution's installed version, if either.
  '''
  if credit.version:
    return credit.version
  d = _distribution(credit.dist) if credit.dist else None
  return d.version if d is not None else None

def licenceName(credit:Credit) -> Optional[str]:
  '''
  :param credit: Something acknowledged.
  :returns: Its licence's name: *credit.licence*, or what its distribution's
    metadata says (its *License-Expression*, a short *License*, or its
    "License ::" classifier), if anything.
  '''
  if credit.licence:
    return credit.licence
  d = _distribution(credit.dist) if credit.dist else None
  if d is None:
    return None
  m = d.metadata
  if m.get("License-Expression"):
    return m["License-Expression"]
  short = (m.get("License") or "").strip()
  if short and len(short) <= 40 and "\n" not in short:
    return short
  for c in m.get_all("Classifier") or []:
    if c.startswith("License :: "):
      return c.rsplit(" :: ", 1)[-1]
  return None

LICENCE_FILE_WORDS = ("LICEN", "COPYING", "NOTICE")
"What a licence file's name has in it (eg: LICENSE.txt, COPYING, NOTICE), for metadata that doesn't name them (see *licenceFiles()*)."

def _read(d:metadata.Distribution, path:str) -> Optional[str]:
  '''
  :param d: A distribution's metadata.
  :param path: A file's path in its metadata folder (eg: "licenses/LICENSE").
  :returns: Its text, if it's there: as UTF-8, or else Latin-1 (some licences
    are: eg, some of pypdfium2's).
  '''
  try:
    return d.read_text(path)
  except UnicodeDecodeError:
    pass
  except OSError:
    return None
  for f in d.files or []:
    if len(f.parts) >= 2 and f.parts[0].endswith(".dist-info") and "/".join(f.parts[1:]) == path:
      try:
        return f.read_binary().decode("latin-1").replace("\r\n", "\n") # (as read_text() reads them)
      except OSError:
        return None
  return None

def licenceFiles(dist:str) -> list[tuple[str, str]]:
  '''
  :param dist: A Python distribution's name (eg: "requests").
  :returns: The licence files in its metadata, as (name, text): the files its
    *License-File* entries name (eg: "LICENSE", "NOTICE"), in their order; or,
    if it names none, the files in its metadata folder whose names look like
    licences' (see *LICENCE_FILE_WORDS*). None if it isn't installed.
  '''
  d = _distribution(dist)
  if d is None:
    return []
  ret:list[tuple[str, str]] = []
  for name in d.metadata.get_all("License-File") or []:
    for path in (f"licenses/{name}", name): # (metadata 2.4 puts them in licenses/; older, at the top)
      text = _read(d, path)
      if text is not None:
        ret.append((name, text))
        break
  if not ret:
    for f in d.files or []:
      if len(f.parts) >= 2 and f.parts[0].endswith(".dist-info") and any(w in f.name.upper() for w in LICENCE_FILE_WORDS):
        text = _read(d, "/".join(f.parts[1:]))
        if text is not None:
          ret.append((f.name, text))
  return ret

def _photo(master:tk.Misc, icon:tk.PhotoImage|str|bytes) -> tk.PhotoImage:
  '''
  :param icon: A picture: one already made, a picture file's path, or its contents (PNG or GIF).
  :returns: It, as a picture to show.
  '''
  if isinstance(icon, tk.PhotoImage):
    return icon
  if isinstance(icon, bytes):
    return tk.PhotoImage(master=master, data=base64.b64encode(icon).decode("ascii"))
  return tk.PhotoImage(master=master, file=icon)

class AboutDialog(tk.Toplevel):
  '''
  An About box: the program's icon, name, version and details (eg: the
  versions of what it runs on), its copyright and web page, an introduction,
  and two tabs: "Acknowledgements" -- *sections*, each a heading and its
  credits: each credit's name (a link to its web page), version, note and
  licence's name -- and "Licences": the program's own licence and the credits'
  licences, a list on the left, the chosen one's text on the right (see
  *licenceTexts()*). Not modal: it stays until it's closed (Close, Escape,
  Return, or Command/Control-W). Show it with *showAbout()*: there's one at a time.

  :param parent: What it's opened from, if anything.
  :param name: The program's name.
  :param version: Its version.
  :param icon: Its icon (a picture, a picture file's path, or its contents), if any.
  :param details: Lines under the version, less prominently: eg, "Python 3.14.0, Tk 8.6.16".
  :param copyright: Its copyright line: eg, "© 2023-2026 Rob Kremer".
  :param url: Its web page, if any.
  :param intro: A few words about it, if any.
  :param sections: The acknowledgements: headings, and their credits.
  :param licence: The program's own licence's name (eg: "MIT"), if any: the first in the list of licences.
  :param licenceText: That licence's text.
  '''

  current:Optional[AboutDialog] = None
  "The About box that's shown, if any (see *showAbout()*)."

  def __init__(self, parent:Optional[tk.Misc], name:str, *, version:str="", icon:tk.PhotoImage|str|bytes|None=None,
               details:Sequence[str]=(), copyright:str="", url:Optional[str]=None, intro:str="",
               sections:Sequence[tuple[str, Sequence[Credit]]]=(), licence:Optional[str]=None,
               licenceText:Optional[str]=None):
    super().__init__(parent)
    ownDialog(self, parent, keep=False) # (stays while the user works in other windows: see ownDialog())
    self.title(f"About {name}")
    self.name = name
    self.sections = sections
    self._links = 0
    self._fonts:list[tkfont.Font] = []
    frame = ttk.Frame(self, padding=(18, 14, 18, 12))
    frame.pack(fill=tk.BOTH, expand=True)

    head = ttk.Frame(frame)
    head.pack(fill=tk.X)
    if icon is not None:
      self.icon = _photo(self, icon) # (kept: Tk forgets a picture Python no longer refers to)
      ttk.Label(head, image=self.icon).pack()
    ttk.Label(head, text=name, font=self._font(1.6, bold=True)).pack(pady=(6, 0))
    if version:
      ttk.Label(head, text=f"Version {version}").pack(pady=(2, 0))
    small = self._font(0.85)
    for d in details:
      ttk.Label(head, text=d, font=small, foreground=DIM_COLOUR).pack()
    if copyright:
      ttk.Label(head, text=copyright, font=small).pack(pady=(6, 0))
    if url:
      link = ttk.Label(head, text=url, font=small, foreground=LINK_COLOUR, cursor="hand2")
      link.pack()
      link.bind("<Button-1>", lambda _e: webbrowser.open(url))
    if intro:
      ttk.Label(head, text=intro, wraplength=500, justify=tk.CENTER).pack(pady=(10, 0))

    notebook = ttk.Notebook(frame)
    notebook.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
    self.creditsView = self._scrolledText(notebook)
    notebook.add(self.creditsView.master, text="Acknowledgements") #type: ignore[arg-type]
    self._fillCredits()

    self.licences:list[Credit] = ([Credit(name, licence=licence, licenceText=licenceText, version=version or None)]
                                  if licence or licenceText else [])
    "The licences listed: the program's own, then the credits' (see *licenceTexts()*)."
    seen = {c.name for c in self.licences}
    for _heading, credits in sections:
      for c in credits:
        if c.name not in seen and (c.licenceText or c.dist or licenceName(c)):
          self.licences.append(c)
          seen.add(c.name)
    licences = ttk.Frame(notebook, padding=(0, 6, 0, 0))
    licences.columnconfigure(1, weight=1)
    licences.rowconfigure(0, weight=1)
    self.licenceList = tk.Listbox(licences, width=18, exportselection=False, activestyle="none")
    for c in self.licences:
      self.licenceList.insert(tk.END, c.name)
    self.licenceList.grid(row=0, column=0, sticky=tk.NSEW)
    self.licenceView = self._scrolledText(licences, wrap=False)
    self.licenceView.master.grid(row=0, column=1, sticky=tk.NSEW, padx=(6, 0)) #type: ignore[attr-defined]
    self.licenceList.bind("<<ListboxSelect>>", lambda _e: self._showLicence())
    notebook.add(licences, text="Licences")
    if self.licences:
      self.licenceList.selection_set(0)
      self._showLicence()

    buttons = ttk.Frame(frame)
    buttons.pack(fill=tk.X, pady=(10, 0))
    ttk.Button(buttons, text="Close", command=self.destroy, default="active").pack(side=tk.RIGHT)
    for key in ("<Escape>", "<Return>", "<KP_Enter>", shortcut("w")[0]):
      self.bind(key, lambda _e: self.destroy())
    self.protocol("WM_DELETE_WINDOW", self.destroy)
    self.minsize(460, 520)
    placeDialog(self, parent) # (centred over its parent's window, or the screen: wholly on screen)

  def _font(self, scale:float=1.0, bold:bool=False) -> tkfont.Font:
    '''
    :returns: The default font, *scale* times its size, perhaps bold (kept
      while the dialog is: Tk forgets a font Python no longer refers to).
    '''
    f = tkfont.nametofont("TkDefaultFont", root=self).actual()
    f["size"] = round(int(f["size"]) * scale) # (negative sizes are pixels: scaling them is the same)
    if bold:
      f["weight"] = "bold"
    font = tkfont.Font(self, **f) #type: ignore[arg-type]
    self._fonts.append(font)
    return font

  def _scrolledText(self, master:tk.Misc, wrap:bool=True) -> tk.Text:
    '''
    :param wrap: Whether its lines wrap (at words); else it scrolls sideways
      too, and it's sized for a licence's lines in the fixed-width font (see
      *_showLicence()*): they're broken where their authors broke them.
    :returns: A read-only text, with scroll bars, in a frame of its own (its *master*).
    '''
    frame = ttk.Frame(master)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    text = tk.Text(frame, wrap=tk.WORD if wrap else tk.NONE, width=60 if wrap else 74, height=16, padx=10, pady=8,
                   borderwidth=0, highlightthickness=0, cursor="arrow", font="TkDefaultFont" if wrap else "TkFixedFont")
    scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=text.yview)
    text.configure(yscrollcommand=scroll.set, state=tk.DISABLED)
    text.grid(row=0, column=0, sticky=tk.NSEW)
    scroll.grid(row=0, column=1, sticky=tk.NS)
    if not wrap:
      across = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=text.xview)
      text.configure(xscrollcommand=across.set)
      across.grid(row=1, column=0, sticky=tk.EW)
    text.tag_configure("heading", font=self._font(1.15, bold=True), spacing1=16, spacing3=2)
    text.tag_configure("first", spacing1=2) # (the first heading: none above it)
    text.tag_configure("name", font=self._font(bold=True), spacing1=5)
    text.tag_configure("dim", foreground=DIM_COLOUR)
    text.tag_configure("note", lmargin1=16, lmargin2=16)
    text.tag_configure("prose", font="TkDefaultFont")
    return text

  def _link(self, text:tk.Text, url:str) -> str:
    '''
    :returns: A new tag for *text* that makes what it tags a link to *url*.
    '''
    self._links += 1
    tag = f"link{self._links}"
    text.tag_configure(tag, foreground=LINK_COLOUR, underline=True)
    text.tag_bind(tag, "<Button-1>", lambda _e: webbrowser.open(url))
    text.tag_bind(tag, "<Enter>", lambda _e: text.configure(cursor="hand2"))
    text.tag_bind(tag, "<Leave>", lambda _e: text.configure(cursor="arrow"))
    return tag

  def _fillCredits(self) -> None:
    '''
    Show the acknowledgements (*self.sections*): each heading, then its
    credits: name (a link to its web page), version (or "not installed"),
    note, and licence.
    '''
    t = self.creditsView
    t.configure(state=tk.NORMAL)
    for i, (heading, credits) in enumerate(self.sections):
      t.insert(tk.END, heading + "\n", ("heading",) if i else ("heading", "first"))
      for c in credits:
        t.insert(tk.END, c.name, ("name", self._link(t, c.url)) if c.url else ("name",))
        v = version(c)
        if v:
          t.insert(tk.END, f"  {v}", ("dim",))
        elif not installed(c):
          t.insert(tk.END, "  (not installed)", ("dim",))
        t.insert(tk.END, "\n")
        lic = licenceName(c)
        if c.note or lic:
          t.insert(tk.END, c.note, ("note",))
          if lic:
            t.insert(tk.END, (" " if c.note else "") + f"Licence: {lic}.", ("note", "dim"))
          t.insert(tk.END, "\n")
    t.configure(state=tk.DISABLED)

  def _showLicence(self) -> None:
    '''
    Show the text of the licence chosen in the list (see *licenceTexts()*).
    '''
    chosen = self.licenceList.curselection()
    if not chosen:
      return
    c = self.licences[chosen[0]]
    t = self.licenceView
    t.configure(state=tk.NORMAL)
    t.delete("1.0", tk.END)
    v = version(c)
    t.insert(tk.END, c.name + (f"  {v}" if v else "") + "\n", ("heading", "first"))
    lic = licenceName(c)
    if lic:
      t.insert(tk.END, f"Licence: {lic}\n", ("prose", "dim"))
    if c.url:
      t.insert(tk.END, c.url, ("prose", self._link(t, c.url)))
      t.insert(tk.END, "\n")
    t.insert(tk.END, "\n")
    texts = licenceTexts(c)
    if texts:
      for title, body in texts:
        if title:
          t.insert(tk.END, title + "\n", ("name",))
        t.insert(tk.END, body.rstrip() + "\n\n") # (as it's laid out: fixed width, not wrapped)
    elif not installed(c):
      t.insert(tk.END, "It isn't installed, so its licence's text isn't here: see its web page.\n", ("prose",))
    else:
      t.insert(tk.END, "Its licence's text didn't come with it: see its web page.\n", ("prose",))
    t.configure(state=tk.DISABLED)
    t.yview_moveto(0)
    t.xview_moveto(0)

def licenceTexts(credit:Credit) -> list[tuple[str, str]]:
  '''
  :param credit: Something acknowledged.
  :returns: Its licence's texts, as (title, text): *credit.licenceText* (with
    no title), then the files in its distribution's metadata (see
    *licenceFiles()*), titled with their names if there's more than one text.
  '''
  ret:list[tuple[str, str]] = [("", credit.licenceText)] if credit.licenceText else []
  ret += licenceFiles(credit.dist) if credit.dist else []
  if len(ret) == 1:
    return [("", ret[0][1])]
  return ret

def showAbout(parent:Optional[tk.Misc], name:str, **kwargs:Any) -> AboutDialog:
  '''
  Show an About box (see *AboutDialog*, for the arguments): the one that's
  already shown, brought to the front, if there is one.

  :param parent: What it's opened from, if anything.
  :param name: The program's name.
  :returns: The About box.
  '''
  shown = AboutDialog.current
  try:
    if shown is not None and shown.winfo_exists():
      shown.deiconify()
      shown.lift()
      shown.focus_force()
      return shown
  except tk.TclError:
    pass
  AboutDialog.current = AboutDialog(parent, name, **kwargs)
  AboutDialog.current.focus_force()
  return AboutDialog.current

def installAbout(menubar:tk.Menu, name:str, command:Callable[[], Any], helpMenu:Optional[tk.Menu]=None) -> Optional[tk.Menu]:
  '''
  Put "About *name*" in the menus, for *command*: on macOS, first in the app's
  own menu (the one named after the program, next to the Apple menu), in place
  of Tk's (which shows the standard About panel, filled in from the running
  program's bundle: Python's, when it's run from source); elsewhere, at the
  end of *helpMenu*, after a separator (and kept there: see *util.utils.keepLast()*).

  On macOS, Tk makes that menu from the menu bar's first cascade if it's named
  "apple" (its items first, then Tk's own: Settings..., Services, Hide, Quit):
  so call this before the menu bar's first made the root's (*menu=*) -- it
  puts that cascade first. It also has Tk's own About item, in the default
  menu bar Tk shows while a window with none of its own is in front (eg: a
  dialog, with Tk 9), run *command*: through the Tcl command *tkAboutDialog*.
  (The menu bar's bold title is still the program's name as macOS knows it:
  "Python", when it's run from source.)

  :param menubar: The app's menu bar.
  :param name: The program's name.
  :param command: What shows its About box: eg, ``lambda: showAbout(root, name, ...)``.
  :param helpMenu: The Help menu, for platforms other than macOS.
  :returns: The app's own menu, on macOS (where more items can go, below
    "About"); else None.
  '''
  label = f"About {name}"
  if MAC:
    menubar.tk.createcommand("tkAboutDialog", afterMenu(command))
    appMenu = tk.Menu(menubar, name="apple")
    appMenu.add_command(label=label, command=afterMenu(command))
    menubar.insert_cascade(0, label=name, menu=appMenu)
    return appMenu
  if helpMenu is not None:
    if helpMenu.index(tk.END) is not None:
      helpMenu.add_separator()
    helpMenu.add_command(label=label, command=command)
    keepLast(helpMenu, label) # (items added later go above it: see util.utils.addToMenuBar())
  return None
