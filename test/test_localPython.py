'''
Tests of *util.localPython*: finding a Python like the running one, and borrowing its packages.

Created on Nov 5, 2026

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''
import os
import sys
import unittest
from unittest import mock

from util import localPython
from util.localPython import LocalPython, describe, findCompatible, addPackages, candidates

class TestLocalPython(unittest.TestCase):

  def setUp(self):
    self.addCleanup(localPython._added.clear)
    path = list(sys.path)
    self.addCleanup(lambda: sys.path.__setitem__(slice(None), path))

  def like(self, **changes) -> LocalPython:
    'A Python like this one, but for *changes*.'
    me = describe(sys.executable)
    assert me is not None
    return LocalPython(**{**me.__dict__, **changes})

  def test_describe(self):
    'The running Python, asked as another would be, is compatible with itself, and says where its packages are.'
    me = describe(sys.executable)
    assert me is not None
    self.assertEqual(me.version, tuple(sys.version_info[:2]))
    self.assertTrue(me.compatible())
    self.assertTrue(all(os.path.isdir(p) for p in me.paths))

  def test_notAPython(self):
    self.assertIsNone(describe(os.path.join(os.path.dirname(__file__), "no such python")))

  def test_compatible(self):
    'Another version, build or processor won\'t do: its compiled packages wouldn\'t load.'
    self.assertFalse(self.like(version=(3, 1)).compatible())
    self.assertFalse(self.like(suffix=".cpython-31-elsewhere.so").compatible())
    self.assertFalse(self.like(machine="pdp11").compatible())

  def test_candidates(self):
    'Not the running program itself (in a packaged program, that\'s the program), and each only once.'
    with mock.patch.object(localPython.shutil, "which", lambda name: sys.executable if name != "py" else None):
      found = candidates()
    self.assertNotIn((sys.executable,), found)
    self.assertEqual(len(found), len(set(found)))

  def test_findCompatible(self):
    'The first compatible one; one asked for that isn\'t compatible means none.'
    other, good = self.like(version=(3, 1)), self.like(command=("good",))
    with mock.patch.object(localPython, "candidates", lambda: [("other",), ("good",)]), \
         mock.patch.object(localPython, "describe", lambda c: {("other",): other, ("good",): good}[tuple(c)]):
      self.assertEqual(findCompatible(), good)
      self.assertIsNone(findCompatible("other"))

  def test_addPackages(self):
    'A compatible Python\'s folders go at the end of the path, once.'
    with self.subTest("found"):
      folder = os.path.dirname(__file__)
      found = self.like(paths=(folder,))
      sys.path[:] = [p for p in sys.path if p != folder]
      with mock.patch.object(localPython, "findCompatible", return_value=found) as finding:
        self.assertEqual(addPackages("x"), [folder])
        self.assertEqual(addPackages("x"), [folder])
      self.assertEqual(finding.call_count, 1)
      self.assertEqual(sys.path[-1], folder)
    with self.subTest("none, then one"): # (eg: one's installed meanwhile)
      with mock.patch.object(localPython, "findCompatible", return_value=None):
        self.assertEqual(addPackages("y"), [])
      with mock.patch.object(localPython, "findCompatible", return_value=found):
        self.assertEqual(addPackages("y"), [folder])

  def test_environment(self):
    'A packaged program\'s library path (PyInstaller\'s) isn\'t passed on: the one before it is.'
    with mock.patch.dict(os.environ, {"LD_LIBRARY_PATH": "/app/lib", "LD_LIBRARY_PATH_ORIG": "/usr/lib", "PYTHONPATH": "x"}):
      env = localPython._environment()
    self.assertEqual(env["LD_LIBRARY_PATH"], "/usr/lib")
    self.assertNotIn("LD_LIBRARY_PATH_ORIG", env)
    self.assertNotIn("PYTHONPATH", env)

if __name__ == "__main__":
  unittest.main()
