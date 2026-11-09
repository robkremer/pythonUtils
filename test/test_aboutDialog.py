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
*util.aboutDialog*: credits' versions and licences from the installed
distributions' metadata; the About box's two tabs; one shown at a time; and
"About <program>" in the menus -- first in the app's own menu on macOS
(Tk's "apple" cascade, and *tkAboutDialog* for Tk's default menu bar), last
in the Help menu elsewhere.

Created on Nov 9, 2026

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''
import unittest
from unittest import mock
import importlib.metadata as metadata
import tkinter as tk
import util.aboutDialog as about
from util.aboutDialog import Credit, AboutDialog, showAbout, installAbout, licenceFiles, licenceName, licenceTexts, version

def anInstalledDistribution() -> str|None:
  '''
  :returns: An installed distribution that names a licence file in its metadata, if there is one.
  '''
  for d in metadata.distributions():
    if d.metadata.get_all("License-File") and d.metadata.get("Name"):
      return d.metadata["Name"]
  return None

class TestCredits(unittest.TestCase):

  def test0100givenValuesWin(self):
    'A credit\'s own version and licence are used, whatever its distribution says.'
    c = Credit("x", version="9.9", licence="Mine", dist="no-such-distribution-xyz")
    self.assertEqual(version(c), "9.9")
    self.assertEqual(licenceName(c), "Mine")

  def test0200notInstalled(self):
    'A distribution that isn\'t installed has no version, licence or licence files.'
    c = Credit("x", dist="no-such-distribution-xyz")
    self.assertFalse(about.installed(c))
    self.assertIsNone(version(c))
    self.assertIsNone(licenceName(c))
    self.assertEqual(licenceFiles("no-such-distribution-xyz"), [])
    self.assertTrue(about.installed(Credit("y"))) # (not a distribution: it's there)

  def test0300fromMetadata(self):
    'An installed distribution\'s version, and its licence files\' texts, come from its metadata.'
    name = anInstalledDistribution()
    if name is None:
      self.skipTest("no installed distribution names a licence file")
    c = Credit(name, dist=name)
    self.assertEqual(version(c), metadata.version(name))
    files = licenceFiles(name)
    self.assertTrue(files, f"{name}'s licence files")
    self.assertTrue(all(text.strip() for _f, text in files))

  def test0400licenceTexts(self):
    'A credit\'s own text comes first, untitled; with more than one, the files are titled with their names.'
    self.assertEqual(licenceTexts(Credit("x", licenceText="Text")), [("", "Text")])
    with mock.patch.object(about, "licenceFiles", lambda _d: [("LICENSE", "L"), ("NOTICE", "N")]):
      self.assertEqual(licenceTexts(Credit("x", dist="d")), [("LICENSE", "L"), ("NOTICE", "N")])
      self.assertEqual(licenceTexts(Credit("x", dist="d", licenceText="T")), [("", "T"), ("LICENSE", "L"), ("NOTICE", "N")])
    with mock.patch.object(about, "licenceFiles", lambda _d: [("LICENSE", "L")]):
      self.assertEqual(licenceTexts(Credit("x", dist="d")), [("", "L")])

class TestAboutDialog(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    try:
      cls.root = tk.Tk()
    except tk.TclError as ex:
      raise unittest.SkipTest(f"no display: {ex}")
    cls.root.withdraw()

  @classmethod
  def tearDownClass(cls):
    cls.root.destroy()

  def tearDown(self):
    if AboutDialog.current is not None and AboutDialog.current.winfo_exists():
      AboutDialog.current.destroy()
    AboutDialog.current = None

  SECTIONS = [("People", [Credit("Ann", "Thanks.", url="https://example.com/ann")]),
              ("Libraries", [Credit("lib", "A library.", licence="MIT", licenceText="The MIT text."),
                             Credit("gone", dist="no-such-distribution-xyz", licence="BSD"),
                             Credit("lib", "Again: listed once.", licence="MIT")])]

  def show(self) -> AboutDialog:
    return showAbout(self.root, "Prog", version="1.2", details=["Python 3"], copyright="© me", url="https://example.com",
                     intro="It does things.", sections=self.SECTIONS, licence="MIT", licenceText="Prog's licence.")

  def test0100tabs(self):
    'The acknowledgements show each credit, its licence, and whether it\'s installed; the licences list the program\'s first, each credit\'s once.'
    d = self.show()
    self.assertEqual(d.title(), "About Prog")
    credits = d.creditsView.get("1.0", tk.END)
    for text in ("People", "Ann", "Thanks.", "Libraries", "lib", "Licence: MIT.", "gone  (not installed)", "Licence: BSD."):
      self.assertIn(text, credits)
    self.assertEqual([c.name for c in d.licences], ["Prog", "lib", "gone"])
    self.assertIn("Prog's licence.", d.licenceView.get("1.0", tk.END))
    d.licenceList.selection_clear(0, tk.END)
    d.licenceList.selection_set(1)
    d._showLicence()
    self.assertIn("The MIT text.", d.licenceView.get("1.0", tk.END))
    d.licenceList.selection_clear(0, tk.END)
    d.licenceList.selection_set(2)
    d._showLicence()
    self.assertIn("isn't installed", d.licenceView.get("1.0", tk.END))

  def test0200oneAtATime(self):
    'Showing it again brings the one that\'s shown to the front; once it\'s closed, a new one\'s made.'
    d = self.show()
    self.assertIs(self.show(), d)
    d.destroy()
    self.assertIsNot(self.show(), d)

  def test0300closes(self):
    'Escape closes it.'
    d = self.show()
    d.event_generate("<Escape>")
    self.root.update()
    self.assertFalse(d.winfo_exists())

class TestInstallAbout(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    try:
      cls.root = tk.Tk()
    except tk.TclError as ex:
      raise unittest.SkipTest(f"no display: {ex}")
    cls.root.withdraw()

  @classmethod
  def tearDownClass(cls):
    cls.root.destroy()

  def menubar(self) -> tuple[tk.Menu, tk.Menu]:
    menubar = tk.Menu(self.root)
    menubar.add_cascade(label="File", menu=tk.Menu(menubar, name="file"))
    helpMenu = tk.Menu(menubar, name="help")
    helpMenu.add_command(label="User Guide")
    menubar.add_cascade(label="Help", menu=helpMenu)
    return menubar, helpMenu

  def test0100helpMenu(self):
    'Off the Mac, "About <program>" is last in the Help menu, after a separator.'
    menubar, helpMenu = self.menubar()
    with mock.patch.object(about, "MAC", False):
      self.assertIsNone(installAbout(menubar, "Prog", lambda: None, helpMenu))
    self.assertEqual(helpMenu.type(1), "separator")
    self.assertEqual(helpMenu.entrycget(2, "label"), "About Prog")
    self.assertEqual(menubar.index(tk.END), 1) # (no menu added to the menu bar)

  def test0200macAppMenu(self):
    'On the Mac, it\'s in the "apple" cascade, first in the menu bar (the app\'s own menu); and Tk\'s own About item runs it too (tkAboutDialog).'
    menubar, helpMenu = self.menubar()
    shown:list[str] = []
    with mock.patch.object(about, "MAC", True), mock.patch.object(about, "afterMenu", lambda c: c):
      appMenu = installAbout(menubar, "Prog", lambda: shown.append("about"), helpMenu)
    try:
      assert appMenu is not None
      self.assertEqual(str(appMenu).rsplit(".", 1)[-1], "apple")
      self.assertEqual(menubar.entrycget(0, "menu"), str(appMenu))
      self.assertEqual(appMenu.entrycget(0, "label"), "About Prog")
      self.assertEqual(helpMenu.index(tk.END), 0) # (not in the Help menu)
      appMenu.invoke(0)
      self.root.tk.call("tkAboutDialog")
      self.assertEqual(shown, ["about", "about"])
    finally:
      self.root.tk.deletecommand("tkAboutDialog")

if __name__ == "__main__":
  unittest.main()
