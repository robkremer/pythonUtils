'''
Tests of *util.swiProlog*: finding SWI-Prolog's home for janus-swi.

Created on Nov 6, 2026

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from util import swiProlog
from util.swiProlog import isHome, libraryFolders, homeNear, findHome, setHome, HOME_VARIABLE

class TestSwiProlog(unittest.TestCase):

  def setUp(self):
    tmp = tempfile.TemporaryDirectory(prefix="swiProlog-")
    self.addCleanup(tmp.cleanup)
    self.root = Path(tmp.name).resolve()

  def home(self, folder:Path) -> Path:
    'Make an SWI-Prolog home in *folder*.'
    folder.mkdir(parents=True)
    (folder / "boot.prc").write_bytes(b"")
    return folder

  def module(self, *paths:Path) -> Path:
    'A compiled module that names *paths* (as its rpath would).'
    f = self.root / "_swipl.cpython-314-darwin.so"
    f.write_bytes(b"\xcf\xfa\xed\xfe\x00" + b"".join(str(p).encode() + b"\x00\x0c\x00\x00\x00" for p in paths) + b"\x00")
    return f

  def test_isHome(self):
    self.assertTrue(isHome(self.home(self.root / "a")))
    (self.root / "b" / "library").mkdir(parents=True)
    (self.root / "b" / "library" / "lists.pl").write_text("")
    self.assertTrue(isHome(self.root / "b"))
    self.assertFalse(isHome(self.root))

  def test_macApp(self):
    'The Mac app: its library in Contents/Frameworks, its home in Contents/Resources/swipl.'
    contents = self.root / "SWI-Prolog.app" / "Contents"
    (contents / "Frameworks").mkdir(parents=True)
    home = self.home(contents / "Resources" / "swipl")
    module = self.module(Path("/usr/lib"), contents / "Frameworks", self.root / "swipl" / "gone")
    self.assertEqual(libraryFolders(module), [contents / "Frameworks"]) # (not one without "swipl" in it, nor one that's gone)
    self.assertEqual(homeNear(contents / "Frameworks"), home)

  def test_unixLayout(self):
    'Homebrew, Linux and conda: the library in <home>/lib/<arch>.'
    home = self.home(self.root / "lib" / "swipl")
    (home / "lib" / "arm64-darwin").mkdir(parents=True)
    self.assertEqual(homeNear(home / "lib" / "arm64-darwin"), home)
    self.assertIsNone(homeNear(self.root))

  def test_findHome(self):
    'The home beside the library janus was built against comes first; else a swipl program\'s.'
    home = self.home(self.root / "lib" / "swipl")
    (home / "lib" / "x86_64-linux").mkdir(parents=True)
    module = self.module(home / "lib" / "x86_64-linux")
    with mock.patch.object(swiProlog, "_janusModules", return_value=[module]), \
         mock.patch.object(swiProlog, "executables", side_effect=AssertionError("not needed")):
      self.assertEqual(findHome(), (home, None))
    other = self.home(self.root / "other")
    with mock.patch.object(swiProlog, "_janusModules", return_value=[self.module()]), \
         mock.patch.object(swiProlog, "executables", return_value=["/x/swipl"]), \
         mock.patch.object(swiProlog, "homeOf", return_value=other):
      self.assertEqual(findHome(), (other, "/x/swipl"))
    with mock.patch.object(swiProlog, "_janusModules", return_value=[]), \
         mock.patch.object(swiProlog, "executables", return_value=[]):
      self.assertIsNone(findHome())

  def test_homeOf(self):
    'A swipl program says where its home is.'
    exe = self.root / "swipl"
    exe.write_text(f'#!/bin/sh\necho \'PLBASE="{self.root}";\'\necho \'PLVERSION="90209";\'\n')
    exe.chmod(0o755)
    if sys.platform != "win32":
      self.assertEqual(swiProlog.homeOf(str(exe)), self.root)
    self.assertIsNone(swiProlog.homeOf(str(self.root / "no such swipl")))

  def test_setHome(self):
    'SWI_HOME_DIR is set, unless it already is, or janus isn\'t installed.'
    home = self.home(self.root / "home")
    with mock.patch.dict(os.environ, {HOME_VARIABLE: "/mine"}), \
         mock.patch.object(swiProlog, "findHome", side_effect=AssertionError("not looked for")):
      self.assertIsNone(setHome())
      self.assertEqual(os.environ[HOME_VARIABLE], "/mine")
    with mock.patch.dict(os.environ), \
         mock.patch.object(swiProlog, "_janusModules", return_value=[]):
      os.environ.pop(HOME_VARIABLE, None)
      self.assertIsNone(setHome())
      self.assertNotIn(HOME_VARIABLE, os.environ)
    with mock.patch.dict(os.environ), \
         mock.patch.object(swiProlog, "_janusModules", return_value=[self.root / "_swipl.so"]), \
         mock.patch.object(swiProlog, "findHome", return_value=(home, None)):
      os.environ.pop(HOME_VARIABLE, None)
      self.assertEqual(setHome(), home)
      self.assertEqual(os.environ[HOME_VARIABLE], str(home))

if __name__ == "__main__":
  unittest.main()
