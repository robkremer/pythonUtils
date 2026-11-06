'''
Where SWI-Prolog is installed, for janus-swi -- its Python interface -- to
load it. Call *setHome()* before importing *janus_swi*.

When janus loads SWI-Prolog's library, SWI-Prolog looks for its home folder
(its boot file and libraries): in the SWI_HOME_DIR environment variable, next
to a ``swipl`` program in the current folder, and where it was built (and, on
Windows, in the registry). A program started from an IDE or the Finder, or one
installed by a tool that skipped the registry (eg: Chocolatey on Windows),
often gets none of those right -- and then SWI-Prolog stops the whole
process ("FATAL: could not find SWI-Prolog home", "Could not find system
resources"). *setHome()* sets SWI_HOME_DIR first, unless it's set already, to
the home of:

1. the SWI-Prolog janus was built against: its compiled module names the
   folder of SWI-Prolog's library (its rpath: not on Windows), read from the
   file without loading it, and the home is beside it (eg: in the Mac app,
   ``Contents/Frameworks`` and ``Contents/Resources/swipl``);
2. or else the ``swipl`` on the PATH, or in one of the places SWI-Prolog's
   installers put it (eg: ``/Applications/SWI-Prolog.app``, Homebrew's,
   ``C:\\Program Files\\swipl``), which says where its home is
   (``swipl --dump-runtime-variables``). On Windows, its folder is also put on
   the PATH, where janus looks for SWI-Prolog's DLLs.

Created on Nov 6, 2026

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
import importlib.util
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

logger = logging.getLogger(__name__)

HOME_VARIABLE = "SWI_HOME_DIR"
"The environment variable SWI-Prolog looks in first for its home."

def isHome(folder:str|Path) -> bool:
  '''
  :returns: Whether *folder* is an SWI-Prolog home: it has SWI-Prolog's boot
    file, or its library.
  '''
  folder = Path(folder)
  return (folder / "boot.prc").is_file() or (folder / "library" / "lists.pl").is_file()

def _janusModules() -> list[Path]:
  ''':returns: janus-swi's compiled module (its file), if janus is installed: none if it isn't.'''
  try:
    spec = importlib.util.find_spec("janus_swi")
  except (ImportError, ValueError):
    return []
  if spec is None:
    return []
  return [f for folder in spec.submodule_search_locations or [] for f in sorted(Path(folder).glob("_swipl*"))
          if f.suffix in (".so", ".pyd", ".dylib")]

_PATH = re.compile(rb"(?<=\x00)(?:/|[A-Za-z]:[\\/])[\x20-\x7e]+(?=\x00)")
"An absolute path in a compiled file (eg: \"/usr/lib/swipl\", \"C:\\\\Program Files\\\\swipl\"): a NUL-terminated string, after another one."

def libraryFolders(module:str|Path) -> list[Path]:
  '''
  :param module: A compiled module linked to SWI-Prolog's library (eg: janus-swi's).
  :returns: The SWI-Prolog folders that *module* names (eg: the rpath it was
    linked with, where it finds the library), read from the file without
    loading it: those that exist.
  '''
  try:
    data = Path(module).read_bytes()
  except OSError:
    return []
  found = dict.fromkeys(m.decode("ascii") for m in _PATH.findall(data) if b"swipl" in m.lower() or b"swi-prolog" in m.lower())
  return [Path(f) for f in found if Path(f).is_dir()]

def homeNear(folder:str|Path) -> Path|None:
  '''
  :param folder: A folder of an SWI-Prolog installation (eg: its library's).
  :returns: The installation's home: *folder* or one up to three folders
    above it, or the ``Resources/swipl`` or ``swipl`` folder in one of those
    (as in the Mac app); None if there's none.
  '''
  folder = Path(folder)
  for above in [folder, *list(folder.parents)[:3]]:
    for home in (above, above / "Resources" / "swipl", above / "swipl"):
      if isHome(home):
        return home
  return None

def executables() -> list[str]:
  '''
  :returns: The ``swipl`` programs that exist: the one on the PATH, then
    those in the places SWI-Prolog's installers (and Homebrew, MacPorts and
    Linux distributions) put it.
  '''
  ret = [shutil.which("swipl")]
  if sys.platform == "darwin":
    ret += [str(Path(apps).expanduser() / "SWI-Prolog.app" / "Contents" / "MacOS" / "swipl") for apps in ("/Applications", "~/Applications")]
    ret += ["/opt/homebrew/bin/swipl", "/usr/local/bin/swipl", "/opt/local/bin/swipl"]
  elif sys.platform == "win32":
    ret += [os.path.join(os.environ[v], "swipl", "bin", "swipl.exe") for v in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432") if os.environ.get(v)]
  else:
    ret += ["/usr/bin/swipl", "/usr/local/bin/swipl"]
  return [str(Path(e)) for e in dict.fromkeys(e for e in ret if e) if os.path.isfile(e)]

def homeOf(executable:str) -> Path|None:
  '''
  :param executable: An SWI-Prolog program (``swipl``).
  :returns: Its home, as it says (``swipl --dump-runtime-variables``'s PLBASE):
    None if it can't be run, or the folder doesn't exist.
  '''
  try:
    out = subprocess.run([executable, "--dump-runtime-variables"], capture_output=True, text=True, timeout=60,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
  except (OSError, subprocess.SubprocessError):
    return None
  home = re.search(r'^PLBASE="(.*)";\s*$', out, re.M)
  return Path(home.group(1)) if home is not None and Path(home.group(1)).is_dir() else None

def findHome() -> tuple[Path, str|None]|None:
  '''
  :returns: SWI-Prolog's home (see the module doc): the one janus-swi was
    built against, or else a ``swipl`` program's -- with that program, if it
    came from one -- or None if there's none.
  '''
  for module in _janusModules():
    for folder in libraryFolders(module):
      home = homeNear(folder)
      if home is not None:
        return home, None
  for executable in executables():
    home = homeOf(executable)
    if home is not None:
      return home, executable
  return None

def setHome() -> Path|None:
  '''
  Tell SWI-Prolog where it's installed (the SWI_HOME_DIR environment variable:
  see the module doc), unless that's set already, before janus-swi is
  imported -- if it's installed. On Windows, the ``swipl`` found is also put on
  the PATH, if it isn't there, for janus to find SWI-Prolog's DLLs with.

  :returns: The home it's set to; None if it was set already, janus isn't
    installed, or no home was found.
  '''
  if os.environ.get(HOME_VARIABLE) or not _janusModules():
    return None
  found = findHome()
  if found is None:
    logger.info("SWI-Prolog's home wasn't found: SWI-Prolog will look for it itself")
    return None
  home, executable = found
  os.environ[HOME_VARIABLE] = str(home)
  if sys.platform == "win32" and executable is not None and shutil.which("swipl") is None:
    os.environ["PATH"] = os.pathsep.join([os.path.dirname(executable), *[p for p in [os.environ.get("PATH")] if p]])
  logger.debug(f"{HOME_VARIABLE}={home}")
  return home
