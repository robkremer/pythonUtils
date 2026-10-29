#################################################################################
# (c) Copyright 2024-2026, Rob Kremer, MIT open source license.                 #
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
PRDb.relativeURL() -- relative URLs between files on this computer or on the
same web site, and those kept relative however far apart they are -- and
super-DBs saved relatively (PRDb.relativeSuperDBs).

Created on Oct 29, 2026

@author: robkremer
'''
import unittest
import tempfile
from pathlib import Path
from util.persistence.pRef import PRDb


class Test(unittest.TestCase):

  def test_files(self):
    base = "file:///home/a/b/c/web/main.snm"
    self.assertEqual(PRDb.relativeURL("file:///home/a/b/c/web/base.snm", base), "base.snm")
    self.assertEqual(PRDb.relativeURL("file:///home/a/b/c/web/sub/x.snm#12", base), "sub/x.snm#12")
    self.assertEqual(PRDb.relativeURL("file:///home/a/b/x.snm", base), "../../x.snm")
    far = "file:///home/lib/far.snm"
    self.assertEqual(PRDb.relativeURL(far, base), far) # (too far up: absolute)
    self.assertEqual(PRDb.relativeURL(far, base, keep={far}), "../../../../lib/far.snm")
    self.assertEqual(PRDb.relativeURL(far + "#3", base, keep={far}), "../../../../lib/far.snm#3")
    self.assertEqual(PRDb.relativeURL("file:///other/far.snm", base, keep={"file:///other/far.snm"}),
                     "../../../../../other/far.snm")

  def test_web(self):
    base = "https://example.org/models/web/main.snm"
    self.assertEqual(PRDb.relativeURL("https://example.org/models/web/base.snm", base), "base.snm")
    self.assertEqual(PRDb.relativeURL("https://example.org/models/x.snm", base), "../x.snm")
    for other in ("https://other.org/models/web/base.snm", # (another site)
                  "http://example.org/models/web/base.snm", # (another scheme)
                  "file:///models/web/base.snm"):
      self.assertEqual(PRDb.relativeURL(other, base), other)
      self.assertEqual(PRDb.relativeURL(other, base, keep={other}), other)

  def test_basedOnKeep(self):
    far = "file:///home/lib/far.snm"
    with PRDb.basedOn("file:///home/a/b/c/web/main.snm", keepRelative={far}):
      self.assertEqual(PRDb.relativeURL(far), "../../../../lib/far.snm")
      with PRDb.basedOn("file:///home/a/b/c/web/view.snv"): # (another file being written: not kept)
        self.assertEqual(PRDb.relativeURL(far), far)
      self.assertEqual(PRDb.relativeURL(far, base="file:///home/a/b/c/web/x.snm"), far) # (another base: not kept)

  def test_superDBsSavedRelatively(self):
    with tempfile.TemporaryDirectory() as folder:
      folder = Path(folder).resolve() # (macOS: /var is /private/var)
      (folder / "a/b/c/web").mkdir(parents=True)
      (folder / "lib").mkdir()
      near = PRDb(str(folder / "a/b/c/web/near.xml"))
      near.save()
      far = PRDb(str(folder / "lib/far.xml"))
      far.save()
      main = PRDb(str(folder / "a/b/c/web/main.xml"))
      main.addSuperDB(near)
      main.addSuperDB(far)
      self.assertEqual(main.superDBRef(far), far.url) # (absolute: far away)
      main.relativeSuperDBs.add(far.url)
      self.assertEqual(main.superDBRef(near), "near.xml")
      self.assertEqual(main.superDBRef(far), "../../../../lib/far.xml")
      main.save()
      text = (folder / "a/b/c/web/main.xml").read_text()
      self.assertIn('"near.xml"', text)
      self.assertIn('"../../../../lib/far.xml"', text)
      self.assertNotIn(far.url, text)
      url, nearURL, farURL = main.url, near.url, far.url
      for db in (main, near, far):
        del PRDb.AllDBs[db.url]
      del main, near, far

      main = PRDb.getDB(url) # (read: still relative, so saved so again)
      self.assertEqual([db.url for db in main.superDBs], [nearURL, farURL])
      self.assertIn(farURL, main.relativeSuperDBs)
      self.assertEqual(main.superDBRef(main.superDBs[1]), "../../../../lib/far.xml")
      main.removeSuperDB(main.superDBs[1])
      self.assertNotIn(farURL, main.relativeSuperDBs)
      for u in (url, nearURL, farURL):
        PRDb.AllDBs.pop(u, None)


if __name__ == "__main__":
  unittest.main()
