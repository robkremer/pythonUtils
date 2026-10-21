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
'''
Tests of what's done differently on macOS, Windows and Linux: util.platformSupport,
util.singleInstance, and the file-URL and event helpers in util.utils.

Created on Oct 21, 2026

@author: robkremer
'''
import os
import shutil
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest import mock
from util import platformSupport
from util.platformSupport import shortcut, altKey, MAC, WINDOWS, LINUX
from util.utils import urlPath, pathURL, isWindowsPath, isValidURL, wheelSteps, s_CMD, s_ALT, openFile


class TestURLs(unittest.TestCase):

  def test0100posix(self):
    self.assertEqual(urlPath("file:///Users/me/My%20Models/a.snm", windows=False), "/Users/me/My Models/a.snm")
    self.assertEqual(urlPath("file:///Users/me/My Models/a.snm", windows=False), "/Users/me/My Models/a.snm")
    self.assertEqual(urlPath("file://localhost/a.snm", windows=False), "/a.snm")
    self.assertIsNone(urlPath("https://example.org/a.snm", windows=False))
    self.assertIsNone(urlPath("sn:/sn", windows=False))
    self.assertEqual(pathURL("/a/My Models/b.snm", windows=False), "file:///a/My%20Models/b.snm")
    self.assertEqual(pathURL("/a/My Models/b.snm", quoted=False, windows=False), "file:///a/My Models/b.snm")
    self.assertFalse(isWindowsPath("x:/a", windows=False)) # (a URL, off Windows)

  def test0200windows(self):
    self.assertEqual(urlPath("file:///C:/Users/me/My%20Models/a.snm", windows=True), r"C:\Users\me\My Models\a.snm")
    self.assertEqual(urlPath("file://C:/Users/me/a.snm", windows=True), r"C:\Users\me\a.snm") # (as "file://" + a path makes)
    self.assertEqual(urlPath("file://server/share/a.snm", windows=True), r"\\server\share\a.snm")
    self.assertEqual(urlPath(r"C:\Users\me\a.snm", windows=True), r"C:\Users\me\a.snm")
    self.assertIsNone(urlPath("https://example.org/a.snm", windows=True))
    self.assertEqual(pathURL(r"C:\Users\me\My Models\a.snm", windows=True), "file:///C:/Users/me/My%20Models/a.snm")
    self.assertEqual(pathURL(r"C:\Users\me\My Models\a.snm", quoted=False, windows=True), "file:///C:/Users/me/My Models/a.snm")
    self.assertEqual(pathURL(r"\\server\share\a.snm", quoted=False, windows=True), "file://server/share/a.snm")
    for path in (r"C:\Users\me\a.snm", r"\\server\share\a.snm"):
      self.assertEqual(urlPath(pathURL(path, windows=True), windows=True), path)
      self.assertEqual(urlPath(pathURL(path, quoted=False, windows=True), windows=True), path)
    self.assertTrue(isWindowsPath(r"C:\a", windows=True))
    self.assertTrue(isWindowsPath("c:/a", windows=True))
    self.assertFalse(isWindowsPath("file:///C:/a", windows=True))
    self.assertFalse(isWindowsPath("https://a", windows=True))

  def test0300thisComputer(self):
    path = os.path.abspath(os.path.join("some folder", "a b.snm"))
    self.assertEqual(urlPath(pathURL(path)), path)
    self.assertEqual(urlPath(pathURL(path, quoted=False)), path)
    if WINDOWS:
      self.assertFalse(isValidURL(path))


class TestKeys(unittest.TestCase):

  def test0100shortcuts(self):
    if MAC:
      self.assertEqual(shortcut("z"), ("<Command-KeyPress-z>", "Command-Z"))
      self.assertEqual(shortcut("Z", shift=True), ("<Shift-Command-KeyPress-Z>", "Shift-Command-Z"))
      self.assertEqual(altKey("v"), ("<Option-KeyPress-v>", "Option-V"))
    else:
      self.assertEqual(shortcut("z"), ("<Control-KeyPress-z>", "Ctrl+Z"))
      self.assertEqual(shortcut("Z", shift=True), ("<Shift-Control-KeyPress-Z>", "Shift+Ctrl+Z"))
      self.assertEqual(shortcut("equal")[1], "Ctrl++")
      self.assertEqual(altKey("v"), ("<Alt-KeyPress-v>", "Alt+V"))

  def test0200masks(self):
    if MAC:
      self.assertTrue(s_CMD(0x8))
      self.assertTrue(s_ALT(0x10))
    else:
      self.assertTrue(s_CMD(0x4)) # (Control)
      self.assertFalse(s_CMD(0x10)) # (Num Lock, on X11: not a pan click)
      self.assertFalse(s_CMD(0x8))
      self.assertTrue(s_ALT(0x20000 if WINDOWS else 0x8))

  def test0300wheel(self):
    self.assertEqual(wheelSteps(SimpleNamespace(num=4, delta=0)), 1)
    self.assertEqual(wheelSteps(SimpleNamespace(num=5, delta=0)), -1)
    if MAC:
      self.assertEqual(wheelSteps(SimpleNamespace(num="??", delta=-3)), -3)
    else:
      self.assertEqual(wheelSteps(SimpleNamespace(num="??", delta=120)), 1)
      self.assertEqual(wheelSteps(SimpleNamespace(num="??", delta=-240)), -2)
      self.assertEqual(wheelSteps(SimpleNamespace(num="??", delta=-30)), -1) # (a fine-grained wheel: at least one step)


class TestFiles(unittest.TestCase):

  def setUp(self):
    self.folder = tempfile.mkdtemp()

  def tearDown(self):
    shutil.rmtree(self.folder, ignore_errors=True)

  def test0100logFolder(self):
    folder = platformSupport.logFolder("Some Program")
    self.assertIn("Some Program", folder)
    if MAC:
      self.assertIn(os.path.join("Library", "Logs"), folder)

  def test0150openFile(self):
    # a name that can't be a file's is no file (on Windows, '"' isn't allowed in one: an OSError "Invalid argument")
    with self.assertRaises(FileNotFoundError):
      openFile(os.path.join(self.folder, '"no body".xml'))
    import errno
    with mock.patch("builtins.open", side_effect=OSError(errno.EINVAL, "Invalid argument")):
      with self.assertRaises(FileNotFoundError):
        openFile("x")
    with mock.patch("builtins.open", side_effect=PermissionError(errno.EACCES, "Permission denied")):
      with self.assertRaises(PermissionError):
        openFile("x")

  @unittest.skipUnless(LINUX, "the freedesktop.org trash is Linux's")
  def test0200trashFreedesktop(self):
    data = os.path.join(self.folder, "data")
    f = os.path.join(self.folder, "a b.txt")
    with open(f, "w") as out:
      out.write("x")
    with mock.patch.dict(os.environ, {"XDG_DATA_HOME": data}), mock.patch.object(platformSupport.shutil, "which", return_value=None):
      platformSupport.moveToTrash(f)
      self.assertFalse(os.path.exists(f))
      self.assertTrue(os.path.isfile(os.path.join(data, "Trash", "files", "a b.txt")))
      with open(os.path.join(data, "Trash", "info", "a b.txt.trashinfo")) as info:
        text = info.read()
      self.assertIn("Path=" + f.replace(" ", "%20"), text)
      with open(f, "w") as out: # (another of the same name: a name of its own in the trash)
        out.write("y")
      platformSupport.moveToTrash(f)
      self.assertTrue(os.path.isfile(os.path.join(data, "Trash", "files", "a b 2.txt")))
    with self.assertRaises(FileNotFoundError):
      platformSupport.moveToTrash(f)


class TestTerminalRouting(unittest.TestCase):

  def test0100closedWindowsTerminal(self):
    # a terminal whose window was closed with no FocusOut (as on Windows) isn't printed to
    import tkinter as tk
    from util.terminal import TerminalRegistry
    try:
      root = tk.Tk()
    except tk.TclError:
      self.skipTest("there's no display")
    try:
      root.withdraw()
      registry = TerminalRegistry()
      terminal = tk.Text(root)
      registry.onFocusIn(terminal) # type: ignore[arg-type]
      self.assertIs(registry.resolveTerminal(), terminal)
      terminal.destroy()
      self.assertIsNone(registry.resolveTerminal())
    finally:
      root.destroy()


class TestSingleInstance(unittest.TestCase):

  def test0100handOff(self):
    import tkinter as tk
    from util.singleInstance import SingleInstance
    folder = tempfile.mkdtemp()
    try:
      try:
        root = tk.Tk()
      except tk.TclError:
        self.skipTest("there's no display")
      root.withdraw()
      first = SingleInstance("test", folder)
      self.assertFalse(first.handOff(["x"])) # (nothing's running)
      got:list[list[str]] = []
      first.listen(root, got.append)
      second = SingleInstance("test", folder)
      self.assertTrue(second.handOff(["a.snv", "https://example.org/b.snv"]))
      deadline = time.time() + 5
      while not got and time.time() < deadline:
        root.update()
        time.sleep(0.05)
      self.assertEqual(got, [[os.path.abspath("a.snv"), "https://example.org/b.snv"]])
      with open(first.portFile) as f: # (a wrong secret's ignored)
        port = f.read().split()[0]
      with open(first.portFile, "w") as f:
        f.write(f"{port} wrong\n")
      self.assertFalse(second.handOff(["c.snv"]))
      first.close()
      root.destroy()
    finally:
      shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
  unittest.main()
