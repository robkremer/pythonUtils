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
Created on Apr 17, 2026

@author: robkremer
'''
import unittest
from util.utils import splitOnSeparator, removeDuplicates


class Test(unittest.TestCase):


  def test_splitOnSeparator(self):
    self.assertEqual(splitOnSeparator("a.b.c"), ["a", "b", "c"])
    self.assertEqual(splitOnSeparator("a|b|c", separator="|"), ["a", "b", "c"])
    self.assertEqual(splitOnSeparator("'a.b'.c"), ["a.b", "c"])
    self.assertEqual(splitOnSeparator('"a.b".c'), ["a.b", "c"])
    with self.assertRaises(ValueError):
      splitOnSeparator("'a.b'b.c")
    self.assertEqual(splitOnSeparator('"a.b".c'), ["a.b", "c"])

  def test_removeDuplicates(self):
    self.assertEqual(removeDuplicates([1,2,1,1,2]), [1,2])
    self.assertEqual(removeDuplicates([1,2,1,1,2], asTree=True), [1,2])
    self.assertEqual(removeDuplicates([1,2,1,1,2,1], asTree=True), [1,2])
    self.assertEqual(removeDuplicates([1,2,[3,1],1,1,2], asTree=True), [1,2,[3]])
    self.assertEqual(removeDuplicates([1,2,[1],1,1,2], asTree=True), [1,2])
    self.assertEqual(removeDuplicates([1,2,[1,[3,4,2]],1,1,2], asTree=True), [1,2,[[3,4]]])
    self.assertEqual(removeDuplicates([1,2,[1,[3,4,2]],1,5,1,2], asTree=True), [1,2,[[3,4]],5])

  def test_findConcreteSubclasses(self):
    from abc import ABC, abstractmethod
    from util.utils import findConcreteSubclasses
    class Base(ABC):
      @abstractmethod
      def f(self): ...
    class Mid(Base): # still abstract
      pass
    class A(Mid):
      def f(self): pass
    class B(A):      # a concrete subclass of a concrete class
      pass
    class C(Base):
      def f(self): pass
    self.assertEqual(set(findConcreteSubclasses(Base)), {A, B, C})


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()

class TestURLProblem(unittest.TestCase):
  '''util.urlDialog.urlProblem(): what's wrong with a typed URL.'''

  def test0100urlProblem(self):
    from util.urlDialog import urlProblem
    self.assertIsNone(urlProblem("https://example.org/onto/animals.snm"))
    self.assertIsNone(urlProblem("file:///Users/me/animals.snm"))
    self.assertIsNotNone(urlProblem(""))
    self.assertIn("starts with", urlProblem("example.org/animals.snm") or "")
    self.assertIn("no host", urlProblem("https:///animals.snm") or "")
    self.assertIn("file:///", urlProblem("file:animals.snm") or "")
    self.assertIsNotNone(urlProblem("ftp://example.org/x", schemes=("http", "https")))


class TestWebCache(unittest.TestCase):
  '''util.utils.fetchURL(): copies of what's read from the web, used when the server can't be reached.'''

  def test0100cache(self):
    import os, tempfile, threading, functools, logging
    from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
    import util.utils as U
    with tempfile.TemporaryDirectory() as folder:
      os.makedirs(os.path.join(folder, "site", "onto"))
      with open(os.path.join(folder, "site", "onto", "a.xml"), "w") as f:
        f.write("<a/>")
      class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *args): pass
      server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=os.path.join(folder, "site")))
      threading.Thread(target=server.serve_forever, daemon=True).start()
      url = f"http://127.0.0.1:{server.server_address[1]}/onto/a.xml"
      saved = U.webCacheFolder
      U.webCacheFolder = os.path.join(folder, "cache")
      try:
        self.assertIsNone(U.cachedCopy(url))
        self.assertEqual(U.fetchURL(url), b"<a/>")
        self.assertIsNotNone(U.cachedCopy(url))
        with self.assertRaises(FileNotFoundError):
          U.fetchURL(url.replace("a.xml", "missing.xml"))
        server.shutdown(); server.server_close()
        with self.assertLogs("util.utils", level=logging.WARNING):
          self.assertEqual(U.fetchURL(url), b"<a/>")           # (from the copy, with a warning)
        self.assertTrue(U.urlExists(url))                       # (there's a copy)
        self.assertFalse(U.urlExists(url.replace("a.xml", "b.xml")))
      finally:
        U.webCacheFolder = saved


class TestAliases(unittest.TestCase):
  '''PRDb.aliases: exact, and for everything under a URL ending in "/".'''

  def test0100aliases(self):
    from util.persistence.pRef import PRDb
    saved = dict(PRDb.aliases)
    try:
      PRDb.aliases.update({"http://old.org/onto/": "https://new.org/ontologies/", "sn:/a": "sn:/b"}) # (not "x:/a": on Windows, that's a drive's path)
      self.assertEqual(PRDb.resolveURL("http://old.org/onto/family.snm"), "https://new.org/ontologies/family.snm")
      self.assertEqual(PRDb.resolveURL("http://old.org/other.snm"), "http://old.org/other.snm")
      self.assertEqual(PRDb.resolveURL("sn:/a"), "sn:/b")
    finally:
      PRDb.aliases.clear(); PRDb.aliases.update(saved)
