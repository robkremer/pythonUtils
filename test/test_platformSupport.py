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
from util.utils import urlPath, pathURL, displayURL, isWindowsPath, isValidURL, wheelSteps, s_CMD, s_ALT, openFile


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

  def test0250displayURL(self):
    self.assertEqual(displayURL("file:///Users/me/My%20Models/a.snm", home="/Users/me", windows=False), "~/My Models/a.snm")
    self.assertEqual(displayURL("file:///Users/meg/a.snm", home="/Users/me", windows=False), "/Users/meg/a.snm")
    self.assertEqual(displayURL("/tmp/a.snm", home="/Users/me", windows=False), "/tmp/a.snm")
    self.assertEqual(displayURL("https://example.org/m/a.snm", home="/Users/me", windows=False), "https://example.org/m/a.snm")
    self.assertEqual(displayURL("file:///C:/Users/me/a.snm", home="C:\\Users\\me", windows=True), r"C:\Users\me\a.snm")
    long = displayURL("file:///" + "x" * 100 + "/family.snv", maxLength=40, home="", windows=False)
    self.assertEqual(len(long), 40)
    self.assertTrue(long.startswith("/xxx") and long.endswith("x/family.snv") and "\u2026" in long)
    self.assertEqual(displayURL("file:///a/b.snm", maxLength=40, home="", windows=False), "/a/b.snm")

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


class TestPermissions(unittest.TestCase):
  'Unlocking files, and telling (and saying) that the Mac\'s privacy protection stopped one being used.'

  def setUp(self):
    self.folder = tempfile.mkdtemp()
    self.file = os.path.join(self.folder, "a.txt")
    with open(self.file, "w") as out:
      out.write("x")

  def tearDown(self):
    for path in (self.file, self.folder):
      if os.path.exists(path):
        platformSupport.makeWritable(path)
    shutil.rmtree(self.folder, ignore_errors=True)

  def test0100makeWritableReadOnly(self):
    import stat
    os.chmod(self.file, 0o444)
    self.assertTrue(platformSupport.makeWritable(self.file))
    self.assertTrue(os.stat(self.file).st_mode & stat.S_IWUSR)
    self.assertFalse(platformSupport.makeWritable(self.file)) # (nothing more to do)
    self.assertFalse(platformSupport.makeWritable(os.path.join(self.folder, "none.txt")))

  @unittest.skipUnless(hasattr(os, "chflags"), "file flags are the Mac's (and BSD's)")
  def test0150makeWritableLocked(self):
    import stat
    os.chflags(self.file, stat.UF_IMMUTABLE) # type: ignore[attr-defined] # (as the Finder's Get Info "Locked") @UndefinedVariable
    self.assertTrue(platformSupport._locked(self.file))
    with self.assertRaises(PermissionError):
      open(self.file, "w").close()
    self.assertTrue(platformSupport.makeWritable(self.file))
    self.assertFalse(platformSupport._locked(self.file))
    with open(self.file, "w") as out:
      out.write("y")

  def test0200privacyBlocked(self):
    import errno
    eperm = PermissionError(errno.EPERM, "Operation not permitted", self.file)
    with mock.patch.object(platformSupport, "MAC", True):
      self.assertTrue(platformSupport.privacyBlocked(eperm))
      self.assertTrue(platformSupport.privacyBlocked(PermissionError(errno.EPERM, "Operation not permitted"), self.file))
      self.assertFalse(platformSupport.privacyBlocked(PermissionError(errno.EACCES, "Permission denied", self.file)))
      with mock.patch.object(platformSupport, "_locked", lambda path: path == self.file):
        self.assertFalse(platformSupport.privacyBlocked(eperm)) # (it's locked: that's why)
      with mock.patch.object(platformSupport, "_locked", lambda path: path == self.folder):
        self.assertFalse(platformSupport.privacyBlocked(eperm)) # (its folder is)
    with mock.patch.object(platformSupport, "MAC", False):
      self.assertFalse(platformSupport.privacyBlocked(eperm))

  def test0250privacyError(self):
    'The error the privacy protection caused, in what was raised because of it.'
    import errno
    eperm = PermissionError(errno.EPERM, "Operation not permitted", self.file)
    with mock.patch.object(platformSupport, "MAC", True):
      self.assertIs(platformSupport.privacyError(eperm), eperm)
      try:
        try:
          raise eperm
        except OSError as e:
          raise ValueError(f"Can't read it: {e}") from e
      except ValueError as wrapped:
        self.assertIs(platformSupport.privacyError(wrapped), eperm)
      try:
        try:
          raise eperm
        except OSError:
          raise LookupError("No strategy succeeded") # (while handling it)
      except LookupError as during:
        self.assertIs(platformSupport.privacyError(during), eperm)
      self.assertIsNone(platformSupport.privacyError(PermissionError(errno.EACCES, "Permission denied", self.file)))
      self.assertIsNone(platformSupport.privacyError(ValueError("no")))
      a, b = ValueError("a"), ValueError("b")
      a.__context__, b.__context__ = b, a # (a loop: still an answer)
      self.assertIsNone(platformSupport.privacyError(a))
    with mock.patch.object(platformSupport, "MAC", False):
      self.assertIsNone(platformSupport.privacyError(eperm))

  def test0300privacyHelp(self):
    home = os.path.join(self.folder, "home")
    with mock.patch.dict(os.environ, {"HOME": home, "USERPROFILE": home}):
      text = platformSupport.privacyHelp(os.path.join(home, "Documents", "Semantic Nets Examples"), app="Eclipse")
      self.assertIn("isn't letting Eclipse use your Documents folder", text)
      self.assertIn('turn on "Documents Folder" under Eclipse', text)
      self.assertIn("Full Disk Access", text)
      self.assertIn("your Desktop folder", platformSupport.privacyHelp(os.path.join(home, "Desktop"), app="X"))
      other = os.path.join(self.folder, "elsewhere", "a.snm")
      text = platformSupport.privacyHelp(other, app="X")
      self.assertIn(f'"{os.path.dirname(other)}"', text)
      self.assertNotIn("Documents", text)
      with mock.patch.object(platformSupport, "responsibleApp", return_value=None):
        self.assertIn("isn't letting this program use", platformSupport.privacyHelp(other))

  def test0400responsibleApp(self):
    me = os.getpid()
    ps = (f"  1     0 /sbin/launchd\n"
          f"500     1 /Applications/Utilities/Terminal.app/Contents/MacOS/Terminal\n"
          f"510   500 login\n"
          f"520   510 -zsh\n"
          f"{me}   520 /Library/Frameworks/Python.framework/Versions/3.14/Resources/Python.app/Contents/MacOS/Python\n")
    run = lambda out: mock.patch.object(platformSupport.subprocess, "run", return_value=SimpleNamespace(stdout=out))
    with mock.patch.object(platformSupport, "MAC", True):
      with run(ps):
        self.assertEqual(platformSupport.responsibleApp(), "Terminal") # (not Python's own app)
      with run(ps.replace("/Applications/Utilities/Terminal.app/Contents/MacOS/Terminal",
                          "/Applications/Visual Studio Code.app/Contents/Frameworks/Code Helper.app/Contents/MacOS/Code Helper")):
        self.assertEqual(platformSupport.responsibleApp(), "Visual Studio Code")
      with run(f"  1     0 /sbin/launchd\n{me}     1 /Applications/Semantic Nets.app/Contents/MacOS/Semantic Nets\n"):
        self.assertEqual(platformSupport.responsibleApp(), "Semantic Nets")
      with run(""):
        self.assertIsNone(platformSupport.responsibleApp())
      with mock.patch.object(platformSupport.subprocess, "run", side_effect=OSError("no ps")):
        self.assertIsNone(platformSupport.responsibleApp())
    with mock.patch.object(platformSupport, "MAC", False):
      self.assertIsNone(platformSupport.responsibleApp())
    platformSupport.responsibleApp() # (the real one: no error, whatever's running the tests -- maybe no app)

  def test0500openPrivacySettings(self):
    with mock.patch.object(platformSupport, "_launch") as launch:
      with mock.patch.object(platformSupport, "MAC", True):
        platformSupport.openPrivacySettings()
      launch.assert_called_once_with(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_FilesAndFolders"])
      with mock.patch.object(platformSupport, "MAC", False):
        platformSupport.openPrivacySettings()
      launch.assert_called_once()


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
