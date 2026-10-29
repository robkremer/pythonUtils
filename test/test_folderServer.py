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
*util.folderServer*: a folder's pages, and the files they refer to by
relative paths (eg: "../_static/x.css"), served on 127.0.0.1.

Created on Oct 29, 2026

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''
import os
import tempfile
import unittest
import urllib.request
import urllib.error
import urllib.parse
from unittest import mock
from util import folderServer
from util.folderServer import serveFolder, folderURL, openInBrowser, stopServing

class TestFolderServer(unittest.TestCase):

  def setUp(self):
    self.tmp = tempfile.TemporaryDirectory()
    self.folder = self.tmp.name
    os.makedirs(os.path.join(self.folder, "_static", "styles"))
    os.makedirs(os.path.join(self.folder, "user guide"))
    with open(os.path.join(self.folder, "_static", "styles", "furo.css"), "w") as f:
      f.write("body { color: red; }")
    with open(os.path.join(self.folder, "user guide", "shortcuts.html"), "w") as f:
      f.write('<link rel="stylesheet" href="../_static/styles/furo.css?v=1">')

  def tearDown(self):
    stopServing()
    self.tmp.cleanup()

  def get(self, url:str) -> str:
    with urllib.request.urlopen(url, timeout=5) as r:
      return r.read().decode()

  def test_serves(self):
    'A page and the stylesheet it refers to from its parent folder.'
    url = folderURL(self.folder, "user guide/shortcuts.html")
    self.assertTrue(url.startswith("http://127.0.0.1:"))
    self.assertIn("../_static/styles/furo.css", self.get(url))
    self.assertEqual(self.get(urllib.parse.urljoin(url, "../_static/styles/furo.css?v=1")), "body { color: red; }")

  def test_oneServerPerFolder(self):
    'The same folder reuses its server; another folder gets its own.'
    self.assertEqual(serveFolder(self.folder), serveFolder(self.folder + "/"))
    with tempfile.TemporaryDirectory() as other:
      self.assertNotEqual(serveFolder(other), serveFolder(self.folder))

  def test_onlyTheFolder(self):
    'Nothing outside the folder, and a missing page is a 404.'
    base = serveFolder(self.folder)
    with self.assertRaises(urllib.error.HTTPError) as cm:
      self.get(base + "../../../../etc/passwd")
    self.assertEqual(cm.exception.code, 404)
    with self.assertRaises(urllib.error.HTTPError) as cm:
      self.get(base + "nothing.html")
    self.assertEqual(cm.exception.code, 404)

  def test_notAFolder(self):
    with self.assertRaises(FileNotFoundError):
      serveFolder(os.path.join(self.folder, "missing"))

  def test_openInBrowser(self):
    'Opens the served URL.'
    with mock.patch.object(folderServer.webbrowser, "open") as op:
      url = openInBrowser(self.folder, "user guide/shortcuts.html")
    op.assert_called_once_with(url)
    self.assertTrue(url.endswith("/user%20guide/shortcuts.html"))
    self.assertIn("furo.css", self.get(url))

if __name__ == "__main__":
  unittest.main()
