'''
Whether this program's own files have been replaced since it started
(*changed()*): eg, a packaged app (made with PyInstaller) rebuilt, updated or
reinstalled -- or moved, or deleted -- while it's running.

Python loads a module when it's first imported, from the program's files as
they are then. A module in a zip archive -- the standard library's, in a
PyInstaller app's base_library.zip; the program's own, in the archive
PyInstaller appends to its executable; a zipapp's .pyz -- is found by where it
is in the archive, as the archive was when it was first opened, at start-up:
in a replaced archive, something else is there, or nothing. So a replaced
program goes wrong in odd ways, and not when it's replaced, but the next time
it needs something it hasn't used yet: eg, "LookupError: unknown encoding:
utf-8-sig" (the first file read in that encoding: the encoding's module can't
be loaded), or "No module named ...".

The files are noted when this module is first imported (see *record()*), so
import it at start-up. When something goes wrong, *changed()* then says
whether that may be why, and *advice()* what to tell the user: to quit the
program, and open it again.

Created on Nov 16, 2026

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
import os
import sys

_Identity = tuple[int, int, int, int]
"A file's device, inode, size and modification time (ns): a replaced file has another."

_recorded:dict[str, _Identity|None] = {}
"The program's files (see *programFiles()*), and what each was when *record()* noted it (None: it wasn't there)."

def programFiles() -> list[str]:
  '''
  :returns: The files this program loads its modules from that must stay as
    they were while it runs: its executable, if it's a packaged program (eg:
    made with PyInstaller, which appends an archive of the program's modules
    to it), and the zip archives on *sys.path* (eg: PyInstaller's
    base_library.zip, or a zipapp's .pyz). Not the folders on it: a module
    file there that's been replaced is just loaded as it now is.
  '''
  found = [sys.executable] if getattr(sys, "frozen", False) and sys.executable else []
  found += [p for p in sys.path if p and os.path.isfile(p)]
  ret:list[str] = []
  for f in (os.path.abspath(f) for f in found):
    if f not in ret:
      ret.append(f)
  return ret

def _identity(path:str) -> _Identity|None:
  try:
    st = os.stat(path)
  except OSError:
    return None
  return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)

def record(files:list[str]|None=None) -> None:
  '''
  Note what the program's files are now, for *changed()* to compare them
  with: done when this module's first imported.

  :param files: The files to note; by default, *programFiles()*.
  '''
  _recorded.clear()
  _recorded.update({f: _identity(f) for f in (programFiles() if files is None else files)})

def changed() -> list[str]:
  '''
  :returns: The program's files (as noted by *record()*) that have been
    replaced, changed, moved or deleted since: none, if they're all as they were.
  '''
  return [f for f, was in _recorded.items() if was is not None and _identity(f) != was]

def advice(name:str|None=None) -> str:
  '''
  :param name: The program's name, eg: "Semantic Nets"; by default, it's called "This program".
  :returns: What to tell the user when its files have *changed()*.
  '''
  return (f"{name or 'This program'} has been replaced or moved since it was opened (eg: by a new version, "
          "or a rebuild), so it can't load the parts of itself it hasn't used yet: they fail in odd ways "
          "(eg: \"unknown encoding\", or \"No module named ...\").\n\n"
          f"Quit {name or 'it'} and open it again.")

record()
