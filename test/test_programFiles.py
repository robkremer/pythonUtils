'''
Tests of *util.programFiles*: noticing that the running program's own files
have been replaced since it started -- and that a replaced zip archive of
modules really does stop the modules not yet imported from it loading (eg: as
"unknown encoding", for an encoding's module).

Created on Nov 16, 2026

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''
import importlib
import os
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

from util import programFiles

class TestProgramFiles(unittest.TestCase):

  def setUp(self):
    self.tmp = tempfile.TemporaryDirectory(prefix="programFiles-")
    self.addCleanup(self.tmp.cleanup)
    recorded = dict(programFiles._recorded)
    self.addCleanup(lambda: (programFiles._recorded.clear(), programFiles._recorded.update(recorded)))

  def file(self, name:str, text:str="x") -> str:
    path = os.path.join(self.tmp.name, name)
    with open(path, "w", encoding="utf-8") as f:
      f.write(text)
    return path

  def replace(self, path:str, text:str) -> None:
    'Replace *path* by a new file (as a rebuild, or a reinstall, does).'
    new = self.file("new", text)
    os.replace(new, path)

  def test_unchanged(self):
    a, b = self.file("a"), self.file("b")
    programFiles.record([a, b])
    self.assertEqual(programFiles.changed(), [])

  def test_replaced(self):
    'Replaced (even by the same contents), changed, or deleted: each counts.'
    a, b, c, d = self.file("a"), self.file("b"), self.file("c"), self.file("d")
    programFiles.record([a, b, c, d])
    self.replace(a, "x")
    with open(b, "a", encoding="utf-8") as f:
      f.write("more")
    os.remove(c)
    self.assertEqual(programFiles.changed(), [a, b, c])

  def test_moved(self):
    'The program moved somewhere else: its files are gone from where it found them.'
    a = self.file("a")
    programFiles.record([a])
    os.rename(a, a + "-moved")
    self.assertEqual(programFiles.changed(), [a])

  def test_notThereToStartWith(self):
    'A file that wasn\'t there when they were noted doesn\'t count.'
    missing = os.path.join(self.tmp.name, "missing")
    programFiles.record([missing])
    self.file("missing")
    self.assertEqual(programFiles.changed(), [])

  def test_programFiles(self):
    'The zip archives on sys.path (not its folders); and a packaged program\'s executable.'
    archive = self.file("modules.zip")
    with mock.patch.object(sys, "path", ["", self.tmp.name, archive, archive]):
      self.assertEqual(programFiles.programFiles(), [archive])
      with mock.patch.object(sys, "frozen", True, create=True), mock.patch.object(sys, "executable", self.file("app")):
        self.assertEqual(programFiles.programFiles(), [sys.executable, archive])

  def test_advice(self):
    self.assertIn("Semantic Nets has been replaced", programFiles.advice("Semantic Nets"))
    self.assertIn("Quit Semantic Nets and open it again.", programFiles.advice("Semantic Nets"))
    self.assertIn("This program has been replaced", programFiles.advice())
    self.assertIn("Quit it and open it again.", programFiles.advice())

  def test_replacedArchive(self):
    '''Why it matters: once a zip archive of modules has been opened, a
    module not yet imported from it can't be, if it's been replaced by one
    laid out differently (eg: a rebuilt app's base_library.zip) -- and an
    encoding whose module can't be is "unknown": "LookupError: unknown
    encoding: ...".'''
    import codecs, encodings
    archive = os.path.join(self.tmp.name, "modules.zip")
    names = ["pfcodecone", "pfcodectwo"] # (encodings no Python has)
    def make(path:str, order:list[str]) -> None:
      with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as z:
        for name in order:
          z.writestr(f"encodings/{name}.py", "import codecs\n"
                     "def getregentry():\n"
                     f"  return codecs.CodecInfo(name={name!r}, encode=codecs.utf_8_encode, decode=codecs.utf_8_decode)\n"
                     + "# padding\n" * (300 if name == names[0] else 1)) # (in the other order, they're somewhere else)
    make(archive, names)
    folder = os.path.join(archive, "encodings")
    path, encodingsPath = list(sys.path), list(encodings.__path__)
    def restore():
      sys.path[:] = path
      encodings.__path__[:] = encodingsPath
      for name in names:
        sys.modules.pop(f"encodings.{name}", None)
      for p in (archive, folder):
        sys.path_importer_cache.pop(p, None)
    self.addCleanup(restore)
    sys.path.append(archive)
    encodings.__path__.append(folder) # (as if it were where the standard library's encodings are)
    programFiles.record()
    self.assertIn(archive, programFiles._recorded)
    self.assertEqual(codecs.lookup("pfcodecone").name, "pfcodecone")
    self.assertEqual(programFiles.changed(), [])
    new = os.path.join(self.tmp.name, "new.zip")
    make(new, list(reversed(names)))
    os.replace(new, archive) # (the program's replaced while it runs)
    self.assertEqual(programFiles.changed(), [archive])
    with self.assertRaisesRegex(LookupError, "unknown encoding: pfcodectwo"):
      codecs.lookup("pfcodectwo")

class TestExceptionDialog(unittest.TestCase):
  'util.utils.showExceptionDialog() says first that the program\'s been replaced, if it has.'

  @classmethod
  def setUpClass(cls):
    import tkinter as tk
    try:
      cls.root = tk.Tk()
    except tk.TclError as ex:
      raise unittest.SkipTest(f"no display: {ex}")
    cls.root.withdraw()

  @classmethod
  def tearDownClass(cls):
    cls.root.destroy()

  def shown(self, changed:list[str]) -> list[str]:
    'The texts of the labels showExceptionDialog() shows, with *changed* the program\'s changed files.'
    import tkinter as tk
    from util.utils import showExceptionDialog
    texts:list[str] = []
    def wait(dialog):
      texts.extend(w.cget("text") for w in dialog.winfo_children() if isinstance(w, tk.Label))
      dialog.destroy()
    with mock.patch.object(programFiles, "changed", return_value=changed), \
         mock.patch.object(tk.Toplevel, "wait_window", wait), mock.patch.object(tk.Toplevel, "grab_set"):
      showExceptionDialog(self.root, text="Traceback ...")
    return texts

  def test_replaced(self):
    self.assertEqual(self.shown(["/somewhere/base_library.zip"]), [programFiles.advice()])

  def test_notReplaced(self):
    self.assertEqual(self.shown([]), [])

if __name__ == "__main__":
  unittest.main()
