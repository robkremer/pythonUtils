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
*util.appIcon.setAppIcon()*: every window gets the program's icon (Tk's
*wm iconphoto -default*), largest picture first; pictures that aren't there
are left out; a packaged Mac app keeps its bundle's own; and a picture Tk
can't read changes nothing. *alertIcon()*: the program's icon in alert-like
dialogs on macOS (with a warning's or an error's at its corner), Tk's for
what it says elsewhere -- in *ChoiceDialog*, *ActionDialog*, *askString()*'s
prompt and *showExceptionDialog()*.

Created on Nov 19, 2026

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''
import os
import tempfile
import unittest
from unittest import mock
import tkinter as tk
import util.appIcon as appIcon
from util.appIcon import setAppIcon

class TestAppIcon(unittest.TestCase):

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

  def setUp(self):
    appIcon._icons.clear()
    self.big = tk.PhotoImage(master=self.root, width=64, height=64)
    self.small = tk.PhotoImage(master=self.root, width=16, height=16)

  def png(self) -> bytes:
    'A PNG file\'s contents (32 pixels square).'
    img = tk.PhotoImage(master=self.root, width=32, height=32)
    img.put("#ffd426", to=(0, 0, 32, 32))
    path = os.path.join(tempfile.mkdtemp(), "icon.png")
    img.write(path, format="png")
    with open(path, "rb") as f:
      return f.read()

  def test_setsEveryWindows(self):
    'Every window\'s (-default), largest first; then it\'s the app\'s icon.'
    with mock.patch.object(appIcon, "packagedMacApp", return_value=False), \
         mock.patch.object(self.root, "wm_iconphoto") as iconphoto:
      self.assertEqual(setAppIcon(self.root, self.big, None, self.small), [self.big, self.small])
    iconphoto.assert_called_once_with(True, self.big, self.small)
    self.assertIs(appIcon.appIcon(), self.big)

  def test_reallySets(self):
    'Tk takes it, and windows made after it are made as usual.'
    self.assertEqual(setAppIcon(self.root, self.big, self.small), [self.big, self.small])
    top = tk.Toplevel(self.root)
    top.update_idletasks()
    top.destroy()

  def test_contents(self):
    'A picture can be its file\'s contents, or its path.'
    data = self.png()
    with mock.patch.object(appIcon, "packagedMacApp", return_value=False), \
         mock.patch.object(self.root, "wm_iconphoto"):
      icons = setAppIcon(self.root, data)
      self.assertEqual((icons[0].width(), icons[0].height()), (32, 32))
      path = os.path.join(tempfile.mkdtemp(), "icon.png")
      with open(path, "wb") as f:
        f.write(data)
      icons = setAppIcon(self.root, path)
      self.assertEqual(icons[0].width(), 32)

  def test_nothingThere(self):
    'No pictures: nothing\'s changed.'
    with mock.patch.object(self.root, "wm_iconphoto") as iconphoto:
      self.assertEqual(setAppIcon(self.root, None, None), [])
    iconphoto.assert_not_called()
    self.assertIsNone(appIcon.appIcon())

  def test_unreadable(self):
    'A picture Tk can\'t read: nothing\'s changed.'
    with mock.patch.object(self.root, "wm_iconphoto") as iconphoto, self.assertLogs(appIcon.logger, "WARNING"):
      self.assertEqual(setAppIcon(self.root, b"not a picture"), [])
    iconphoto.assert_not_called()
    self.assertIsNone(appIcon.appIcon())

  def test_packagedMacApp(self):
    'A packaged Mac app keeps its bundle\'s own icon -- but it\'s still the program\'s icon.'
    with mock.patch.object(appIcon, "packagedMacApp", return_value=True), \
         mock.patch.object(self.root, "wm_iconphoto") as iconphoto:
      self.assertEqual(setAppIcon(self.root, self.big), [self.big])
    iconphoto.assert_not_called()
    self.assertIs(appIcon.appIcon(), self.big)

  def test_packagedMacAppIsMacOnly(self):
    'Only a frozen program on macOS.'
    with mock.patch.object(appIcon, "MAC", True), mock.patch.object(appIcon.sys, "frozen", True, create=True):
      self.assertTrue(appIcon.packagedMacApp())
    with mock.patch.object(appIcon, "MAC", False), mock.patch.object(appIcon.sys, "frozen", True, create=True):
      self.assertFalse(appIcon.packagedMacApp())
    with mock.patch.object(appIcon, "MAC", True):
      if not hasattr(appIcon.sys, "frozen"):
        self.assertFalse(appIcon.packagedMacApp())

  def test_nearest(self):
    'The smallest picture at least the size wanted, else the largest; the largest if it doesn\'t matter.'
    mid = tk.PhotoImage(master=self.root, width=32, height=32)
    with mock.patch.object(self.root, "wm_iconphoto"):
      setAppIcon(self.root, self.big, mid, self.small)
    self.assertIs(appIcon.appIcon(), self.big)
    self.assertIs(appIcon.appIcon(64), self.big)
    self.assertIs(appIcon.appIcon(100), self.big)
    self.assertIs(appIcon.appIcon(33), self.big)
    self.assertIs(appIcon.appIcon(32), mid)
    self.assertIs(appIcon.appIcon(17), mid)
    self.assertIs(appIcon.appIcon(8), self.small)

def imageOf(label:tk.Misc) -> str:
  'The name of the picture *label* shows ("" for none): a ttk label\'s is a tuple.'
  image = label.cget("image")
  return str(image[0]) if isinstance(image, tuple) and image else str(image)

class TestAlertIcon(unittest.TestCase):

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

  def setUp(self):
    appIcon._icons.clear()
    appIcon._alertIcons.clear()
    self.big = tk.PhotoImage(master=self.root, width=128, height=128)
    self.big.put("#ffd426", to=(0, 0, 128, 128))
    self.small = tk.PhotoImage(master=self.root, width=16, height=16)

  def setIcon(self) -> None:
    with mock.patch.object(appIcon, "packagedMacApp", return_value=False), mock.patch.object(self.root, "wm_iconphoto"):
      setAppIcon(self.root, self.big, self.small)

  def mac(self, mac:bool=True):
    return mock.patch.object(appIcon, "MAC", mac)

  def test_elsewhere(self):
    'Off macOS: Tk\'s icon for what it says (as tkinter.messagebox\'s), even with the program\'s set; none for nothing.'
    self.setIcon()
    with self.mac(False):
      self.assertEqual(appIcon.alertIcon(self.root, "warning"), "::tk::icons::warning")
      self.assertEqual(appIcon.alertIcon(self.root, "info"), "::tk::icons::information")
      self.assertIsNone(appIcon.alertIcon(self.root))
      self.assertIsNone(appIcon.alertIcon(self.root, "error", tkIcon=False))
    for name in appIcon.TK_ICONS.values(): # (they're all Tk's)
      self.assertEqual(int(self.root.tk.call("image", "width", name)), 32, name)

  def test_unknown(self):
    with self.assertRaises(ValueError):
      appIcon.alertIcon(self.root, "stop")

  def test_macNotSet(self):
    'On macOS, till the program\'s icon\'s set: as elsewhere.'
    with self.mac():
      self.assertEqual(appIcon.alertIcon(self.root, "question"), "::tk::icons::question")
      self.assertIsNone(appIcon.alertIcon(self.root))

  def test_mac(self):
    'On macOS: the program\'s icon, ALERT_SIZE square (made from the nearest picture), whatever it says; made once.'
    self.setIcon()
    with self.mac():
      icon = appIcon.alertIcon(self.root)
      assert isinstance(icon, tk.PhotoImage)
      self.assertEqual((icon.width(), icon.height()), (appIcon.ALERT_SIZE, appIcon.ALERT_SIZE))
      self.assertEqual(icon.get(63, 63), self.big.get(127, 127))
      self.assertIs(appIcon.alertIcon(self.root, "info"), icon)
      self.assertIs(appIcon.alertIcon(self.root, "question"), icon)
      self.assertIs(appIcon.alertIcon(self.root, "error", tkIcon=False), appIcon.alertIcon(self.root, "error"))

  def test_macBadge(self):
    'On macOS, a warning or an error: Tk\'s icon for it at the bottom right corner of the program\'s.'
    self.setIcon()
    with self.mac():
      plain = appIcon.alertIcon(self.root)
      warning = appIcon.alertIcon(self.root, "warning")
      error = appIcon.alertIcon(self.root, "error")
    assert isinstance(plain, tk.PhotoImage) and isinstance(warning, tk.PhotoImage) and isinstance(error, tk.PhotoImage)
    self.assertEqual(len({str(plain), str(warning), str(error)}), 3)
    self.assertEqual((warning.width(), warning.height()), (appIcon.ALERT_SIZE, appIcon.ALERT_SIZE))
    self.assertEqual(warning.get(4, 4), plain.get(4, 4), "the top left's the program's")
    corner = [(x, y) for x in range(32, 64) for y in range(32, 64)]
    self.assertTrue(any(warning.get(x, y) != plain.get(x, y) for x, y in corner), "the bottom right has the warning")
    self.assertTrue(any(warning.get(x, y) != error.get(x, y) for x, y in corner))

  def test_choiceDialog(self):
    'A ChoiceDialog shows it: on macOS the program\'s icon; elsewhere Tk\'s for what it says ("info" too).'
    from tkinter import ttk
    from util.choiceDialog import ChoiceDialog
    def images(d) -> list[str]:
      frame = d.winfo_children()[0]
      return [imageOf(w) for w in frame.winfo_children() if isinstance(w, ttk.Label) and imageOf(w)]
    self.setIcon()
    with self.mac(False):
      d = ChoiceDialog(self.root, "Title", "Which?", ["OK"], icon="info")
      self.assertEqual(images(d), ["::tk::icons::information"])
      d.destroy()
      d = ChoiceDialog(self.root, "Title", "Which?", ["OK"])
      self.assertEqual(images(d), [])
      d.destroy()
    with self.mac():
      d = ChoiceDialog(self.root, "Title", "Which?", ["OK"], icon="warning")
      self.assertEqual(images(d), [str(appIcon.alertIcon(self.root, "warning"))])
      d.destroy()
      d = ChoiceDialog(self.root, "Title", "Which?", ["OK"])
      self.assertEqual(images(d), [str(appIcon.alertIcon(self.root))])
      d.destroy()

  def icons(self, top:tk.Misc) -> list[str]:
    'The pictures shown by the labels that are *top*\'s own.'
    from tkinter import ttk
    return [imageOf(w) for w in top.winfo_children() if isinstance(w, ttk.Label) and imageOf(w)]

  def test_actionDialog(self):
    'An ActionDialog: on macOS the program\'s icon, at its left; none elsewhere.'
    from util.actionDialog import ActionDialog
    self.setIcon()
    with self.mac(False):
      d = ActionDialog(self.root, "Title", "Something <b>to do</b>.")
      self.assertEqual(self.icons(d), [])
      d.destroy()
    with self.mac():
      d = ActionDialog(self.root, "Title", "Something <b>to do</b>.")
      self.assertEqual(self.icons(d), [str(appIcon.alertIcon(self.root))])
      self.assertEqual(d.pack_slaves()[0].winfo_class(), "TLabel", "packed first, at the left")
      d.destroy()

  def test_exceptionDialog(self):
    'showExceptionDialog(): on macOS the program\'s icon, with an error\'s at its corner; none elsewhere.'
    from util.utils import showExceptionDialog
    shown:list[list[str]] = []
    def wait(dialog):
      shown.append(self.icons(dialog))
      dialog.destroy()
    self.setIcon()
    for mac in (False, True):
      with self.mac(mac), mock.patch.object(tk.Toplevel, "wait_window", wait), mock.patch.object(tk.Toplevel, "grab_set"):
        showExceptionDialog(self.root, text="Traceback ...")
    with self.mac():
      self.assertEqual(shown, [[], [str(appIcon.alertIcon(self.root, "error"))]])

  def test_askString(self):
    'askString(): on macOS the program\'s icon, at the left; elsewhere tkinter.simpledialog.askstring() itself.'
    from tkinter import simpledialog
    from util.utils import askString
    self.setIcon()
    with self.mac(False), mock.patch.object(simpledialog, "askstring", return_value="typed") as asked:
      self.assertEqual(askString("Title", "Type:", parent=self.root, initialvalue="x"), "typed")
    asked.assert_called_once_with("Title", "Type:", parent=self.root, initialvalue="x")
    seen:list[list[str]] = []
    def answer():
      d = [w for w in self.root.winfo_children() if isinstance(w, simpledialog._QueryString)][0] # type: ignore[attr-defined]
      seen.append(self.icons(d))
      self.assertEqual(d.entry.get(), "x")
      d.entry.delete(0, tk.END)
      d.entry.insert(0, "typed")
      d.ok()
    with self.mac():
      self.root.after(200, answer)
      self.assertEqual(askString("Title", "Type:", parent=self.root, initialvalue="x"), "typed")
      self.assertEqual(seen, [[str(appIcon.alertIcon(self.root))]])

if __name__ == "__main__":
  unittest.main()
