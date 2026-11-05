'''
Packages from the Pythons installed on this computer, for a packaged program
-- one with its own Python inside (eg: made with PyInstaller) -- to use: an
optional package it doesn't include, installed by the user for a Python of
their own (eg: ``python3.14 -m pip install somepackage``), can be imported
once that Python's package folders are on *sys.path* (see *addPackages()*).

Only a Python whose compiled modules the running one can load will do (see
*LocalPython.compatible()*): the same version (eg: 3.14), the same build of
it (its compiled modules have the same file name suffix: eg,
".cpython-314-darwin.so", which says the version and the ABI) and the same
processor (eg: arm64). Its folders go at the end of the path, so the
program's own modules always come first.

On macOS, a program signed with the hardened runtime can't load compiled code
signed by someone else unless it has the
com.apple.security.cs.disable-library-validation entitlement. An ad hoc signed
one without the hardened runtime (eg: PyInstaller's default) can.

Created on Nov 5, 2026

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
from dataclasses import dataclass
import importlib.machinery
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import threading

logger = logging.getLogger(__name__)

_PROBE = (
  "import importlib.machinery, json, platform, site, sys\n"
  "paths = list(getattr(site, 'getsitepackages', lambda: [])())\n"
  "user = site.getusersitepackages()\n"
  "paths += [user] if isinstance(user, str) else []\n"
  "print(json.dumps({'version': list(sys.version_info[:2]), 'suffix': importlib.machinery.EXTENSION_SUFFIXES[0],\n"
  "                  'machine': platform.machine(), 'executable': sys.executable, 'paths': paths}))\n"
)
"What *describe()* runs in a Python: what it is, and where its packages are."

@dataclass(frozen=True)
class LocalPython:
  '''A Python on this computer: see *describe()*.'''
  command:tuple[str, ...]
  "How it's run: eg, (\"/usr/local/bin/python3.14\",), or (\"py\", \"-3.14\") on Windows."
  executable:str
  "Its executable, as it says (eg: a venv's, or the one a launcher runs)."
  version:tuple[int, int]
  "Its version: eg, (3, 14)."
  suffix:str
  "Its compiled modules' file name suffix: eg, \".cpython-314-darwin.so\"."
  machine:str
  "The processor it runs as: eg, \"arm64\"."
  paths:tuple[str, ...]
  "Its package folders (site-packages, and the user's), those that exist."

  def compatible(self) -> bool:
    ''':returns: Whether the running Python can load this one's compiled packages.'''
    return (self.version == tuple(sys.version_info[:2]) and self.suffix == importlib.machinery.EXTENSION_SUFFIXES[0]
            and self.machine == platform.machine())

def candidates() -> list[tuple[str, ...]]:
  '''
  :returns: The commands that may run a Python of the running one's version,
    in the order they're tried: those on the PATH, then where its installers
    put it (a program opened from the Finder, on macOS, has only the
    system's folders on its PATH). Not the running program itself (in a
    packaged program, *sys.executable* is the program).
  '''
  major, minor = sys.version_info[:2]
  version, home = f"{major}.{minor}", os.path.expanduser("~")
  found:list[tuple[str, ...]] = []
  for name in (f"python{version}", f"python{major}", "python"):
    path = shutil.which(name)
    if path:
      found.append((path,))
  if sys.platform == "win32":
    launcher = shutil.which("py")
    if launcher:
      found.append((launcher, f"-{version}"))
    for base, parts in ((os.environ.get("LOCALAPPDATA"), ("Programs", "Python")), (os.environ.get("ProgramFiles"), ())):
      if base:
        found.append((os.path.join(base, *parts, f"Python{major}{minor}", "python.exe"),))
  else:
    folders = ["/usr/local/bin", "/usr/bin", os.path.join(home, ".local", "bin")]
    if sys.platform == "darwin":
      folders[:0] = [f"/Library/Frameworks/Python.framework/Versions/{version}/bin", "/opt/homebrew/bin"]
    found += [(os.path.join(folder, f"python{version}"),) for folder in folders]
  me = os.path.realpath(sys.executable)
  ret, seen = [], set()
  for command in found:
    if len(command) == 1 and not os.path.isfile(command[0]):
      continue
    key = (os.path.realpath(command[0]), *command[1:])
    if key[0] == me and len(command) == 1 or key in seen:
      continue
    seen.add(key)
    ret.append(command)
  return ret

def _environment() -> dict[str, str]:
  '''
  The environment to run another Python in: this one's, but with the library
  path as it was before a packaged program changed it (PyInstaller's points at
  the program's own libraries, and keeps the original in *_ORIG), and without
  Python's own variables (*describe()* runs it isolated anyway).
  '''
  env = dict(os.environ)
  for key in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
    if f"{key}_ORIG" in env:
      env[key] = env.pop(f"{key}_ORIG")
    elif getattr(sys, "frozen", False):
      env.pop(key, None)
  for key in ("PYTHONHOME", "PYTHONPATH"):
    env.pop(key, None)
  return env

def describe(command:tuple[str, ...]|list[str]|str, timeout:float=10) -> LocalPython|None:
  '''
  Ask a Python what it is, and where its packages are (isolated: its
  PYTHON* variables, and the current folder, don't count).

  :param command: How to run it: its executable, or that and arguments (eg: ("py", "-3.14")).
  :param timeout: How long to wait for it, in seconds.
  :returns: What it said, or None if it couldn't be run or didn't answer.
  '''
  command = (command,) if isinstance(command, str) else tuple(command)
  try:
    done = subprocess.run([*command, "-I", "-c", _PROBE], capture_output=True, text=True, timeout=timeout,
                          env=_environment(), stdin=subprocess.DEVNULL,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)) # (no console window flashing up, on Windows)
    if done.returncode != 0:
      return None
    d = json.loads(done.stdout.strip().splitlines()[-1])
    return LocalPython(command, str(d["executable"]), (int(d["version"][0]), int(d["version"][1])), str(d["suffix"]),
                       str(d["machine"]), tuple(str(p) for p in d["paths"] if os.path.isdir(p)))
  except (OSError, ValueError, KeyError, IndexError, TypeError, subprocess.SubprocessError):
    return None

def findCompatible(python:str|None=None) -> LocalPython|None:
  '''
  :param python: A Python to use (its executable): eg, one the user chose. If it
    isn't compatible (see *LocalPython.compatible()*), none is.
  :returns: The first compatible Python of *candidates()* (or *python*), or None.
  '''
  for command in [(python,)] if python else candidates():
    found = describe(command)
    if found is not None and found.compatible():
      return found
    if found is not None:
      logger.debug(f"{command}: Python {found.version}, {found.machine} ({found.suffix}): not this one's kind")
  return None

_added:dict[str|None, list[str]] = {}
_lock = threading.Lock()

def addPackages(python:str|None=None) -> list[str]:
  '''
  Put a compatible Python's package folders (see *findCompatible()*) at the
  end of *sys.path*, so its packages can be imported. Once one's found for
  *python*, later calls return the same; until then, each looks again (eg:
  the user may have installed one since).

  :param python: A Python to use (its executable); by default, the first compatible one found.
  :returns: The folders added (or already there): none if there's no compatible Python.
  '''
  with _lock:
    if python not in _added:
      found = findCompatible(python)
      if found is None:
        return []
      folders = list(found.paths)
      sys.path.extend(f for f in folders if f not in sys.path)
      import importlib
      importlib.invalidate_caches()
      logger.info(f"Using the packages of {found.executable} (Python {found.version[0]}.{found.version[1]}): {folders}")
      _added[python] = folders
    return list(_added[python])
