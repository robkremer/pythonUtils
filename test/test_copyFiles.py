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
util.persistence.copyFiles: copying a set of files as a unit -- the copies
refer to one another, say where they are, and record where they came from.

Created on Nov 18, 2026

@author: robkremer
'''
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from util.persistence.copyFiles import Copier, layout, references, fileURL
from util.persistence.pRef import PRDb

EXT = (".snm", ".snv")

def xml3(url:str, body:str="", head:str="") -> str:
  "A file as the XML3 format writes it: *url* its own URL, *head* more of its head, *body* its objects' properties."
  return f'''<?xml version='1.0' encoding='utf-8'?>
<document>
  <head>
    <property key="format" value="XML3" />
    <property key="type" value="x.Model" />
    <property key="url" value="{url}" />
{head}  </head>
  <object type="x.Model" id="1">
    <property key="nextID" type="int" value="300" />
{body}  </object>
</document>
'''

def prop(key:str, value:str) -> str:
  return f'    <property key="{key}" type="str" value="{value}" />\n'


class Test(unittest.TestCase):

  def setUp(self):
    self._tmp = tempfile.TemporaryDirectory()
    self.root = Path(self._tmp.name).resolve() # (macOS: /var is /private/var)

  def tearDown(self):
    self._tmp.cleanup()

  def write(self, rel:str, text:str) -> str:
    path = self.root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)

  def url(self, rel:str) -> str:
    return fileURL(str(self.root / rel))

  def test0100layout(self):
    src = [str(self.root / p) for p in ("m/a.snm", "m/views/a.snv", "lib/onto.snm", "other/a.snm")]
    out = layout(src, str(self.root / "web"), base=str(self.root / "m"))
    self.assertEqual(out[src[0]], str(self.root / "web/a.snm"))
    self.assertEqual(out[src[1]], str(self.root / "web/views/a.snv")) # (below the base: kept so)
    self.assertEqual(out[src[2]], str(self.root / "web/onto.snm")) # (elsewhere: in the folder)
    self.assertEqual(out[src[3]], str(self.root / "web/a 2.snm")) # (the same name)

  def test0200references(self):
    self.write("m/onto.snm", xml3(self.url("m/onto.snm")))
    self.write("lib/far.snm", xml3(self.url("lib/far.snm")))
    path = self.write("m/a.snm", xml3(self.url("m/a.snm"),
      prop("isa", "onto.snm#12") + prop("far", self.url("lib/far.snm") + "#3") + prop("name", "notes.txt")
      + prop("web", "https://example.org/x.snm#4") + prop("gone", "gone.snm#5") + prop("local", "#7")
      + prop("sys", "sn:/sn#8") + prop("version", "1.2") + prop("self", self.url("m/a.snm")),
      head=f'    <property key="previousURL" value="{self.url("old/a.snm")}" />\n'))
    self.write("old/a.snm", "") # (where it came from: there, but not a reference)
    refs = references(path, EXT)
    self.assertEqual(refs.local, {self.url("m/onto.snm"): 1, self.url("lib/far.snm"): 1})
    self.assertEqual(refs.missing, {self.url("m/gone.snm"): 1})
    self.assertEqual(refs.web, {"https://example.org/x.snm": 1})

  def test0300copyRefersToCopies(self):
    onto = self.write("lib/onto.snm", xml3(self.url("lib/onto.snm")))
    other = self.write("m/other.snm", xml3(self.url("m/other.snm")))
    model = self.write("m/a.snm", xml3(self.url("m/a.snm"),
      prop("isa", self.url("lib/onto.snm") + "#12") + prop("also", "other.snm#2") + prop("still", "../lib/onto.snm#13"),
      head='    <property key="superDBs" type="list">\n      <item value="sn:/sn" />\n'
           f'      <item value="{self.url("lib/onto.snm")}" />\n    </property>\n'))
    view = self.write("m/a.snv", xml3(self.url("m/a.snv"), prop("modelObject", "#256") + prop("o", "a.snm#300"),
                                      head='    <property key="model" value="a.snm" />\n'))
    plan = layout([model, view, onto], str(self.root / "web"), base=str(self.root / "m"))
    copier = Copier(plan, EXT)
    self.assertEqual(copier.outside(), {model: {self.url("m/other.snm"): 1}})
    done = copier.run()
    self.assertEqual([c.copy for c in done], [str(self.root / p) for p in ("web/a.snm", "web/a.snv", "web/onto.snm")])
    text = (self.root / "web/a.snm").read_text()
    self.assertIn(f'<property key="url" value="{self.url("web/a.snm")}" />', text) # (where it is)
    self.assertIn(f'<property key="previousURL" value="{self.url("m/a.snm")}" />', text) # (where it came from)
    self.assertIn('<item value="onto.snm" />', text) # (the copy of its super-model)
    self.assertIn('value="onto.snm#12"', text)
    self.assertIn(f'value="{self.url("m/other.snm")}#2"', text) # (not copied: where it is, absolutely)
    self.assertIn('value="onto.snm#13"', text)
    self.assertIn('<item value="sn:/sn" />', text)
    self.assertEqual(done[0].references, 4)
    vtext = (self.root / "web/a.snv").read_text()
    self.assertIn('<property key="model" value="a.snm" />', vtext) # (still beside it)
    self.assertIn('value="a.snm#300"', vtext)
    self.assertIn('value="#256"', vtext)
    self.assertEqual(done[1].references, 0)
    os.remove(other)
    self.assertEqual(Path(onto).read_text(), xml3(self.url("lib/onto.snm"))) # (the originals as they were)

  def test0400servedFrom(self):
    onto = self.write("lib/onto.snm", xml3(self.url("lib/onto.snm")))
    model = self.write("m/a.snm", xml3(self.url("m/a.snm"), prop("isa", self.url("lib/onto.snm") + "#12"),
      head='    <property key="replacedModels" type="dict">\n'
           f'      <property key="{self.url("old/onto.snm")}" value="{self.url("lib/onto.snm")}" />\n'
           '    </property>\n'))
    site = "https://example.org/models"
    plan = layout([model, onto], str(self.root / "web"), base=str(self.root / "m"))
    plan[onto] = str(self.root / "web/shared/onto.snm")
    copier = Copier(plan, EXT, servedFrom=site, folder=str(self.root / "web"))
    self.assertEqual(copier.outside(), {}) # (the replaced model isn't referred to)
    copier.run()
    text = (self.root / "web/a.snm").read_text()
    self.assertIn('<property key="url" value="https://example.org/models/a.snm" />', text)
    self.assertIn('value="shared/onto.snm#12"', text)
    self.assertIn(f'<property key="{self.url("old/onto.snm")}" value="https://example.org/models/shared/onto.snm" />', text)
    with self.assertRaises(ValueError): # (not in the folder that's served)
      Copier({model: str(self.root / "elsewhere/a.snm")}, EXT, servedFrom=site, folder=str(self.root / "web"))

  def test0500xml2AndCopiedOnItsOwn(self):
    '''An older format (its URL in the header and the root), and a file that
    was itself copied on its own: its relative references are to what was
    beside it where it was.'''
    stored = self.url("first/v.snv")
    self.write("first/m.snm", xml3(self.url("first/m.snm")))
    text = f'''<?xml version='1.0' encoding='utf-8'?>
<object type="util.persistence.serialize.strdict">
  <property key="header">
    <object type="util.persistence.serialize.strdict">
      <property key="protocol" type="str" value="XML2" />
      <property key="url">
        <object type="str" value="{stored}" />
      </property>
    </object>
  </property>
  <property key="root">
    <object type="x.View" id="4779075840">
      <property key="url">
        <object type="str" value="{stored}" />
      </property>
      <property key="model" type="str" value="m.snm" />
      <property key="o" type="str" value="m.snm#3" />
    </object>
  </property>
</object>
'''
    view = self.write("second/v.snv", text)
    refs = references(view, EXT)
    self.assertEqual(refs.local, {self.url("first/m.snm"): 2})
    Copier({view: str(self.root / "third/v.snv")}, EXT).run()
    out = (self.root / "third/v.snv").read_text()
    self.assertEqual(out.count(f'value="{self.url("third/v.snv")}"'), 2)
    self.assertIn(f'value="{self.url("first/m.snm")}"', out)
    self.assertIn(f'value="{self.url("first/m.snm")}#3"', out)
    self.assertNotIn("previousURL", out) # (no head to put it in)

  def test0600notXML(self):
    path = self.write("m/a.snm", '{"url": "file:///x/a.snm"}')
    self.assertFalse(references(path, EXT).adjustable)
    done = Copier({path: str(self.root / "web/a.snm")}, EXT).run()
    self.assertFalse(done[0].adjusted)
    self.assertEqual((self.root / "web/a.snm").read_text(), '{"url": "file:///x/a.snm"}')

  def test0700refused(self):
    a = self.write("m/a.snm", xml3(self.url("m/a.snm")))
    b = self.write("n/a.snm", xml3(self.url("n/a.snm")))
    with self.assertRaises(ValueError):
      Copier({a: a}, EXT) # (onto itself)
    with self.assertRaises(ValueError):
      Copier({a: str(self.root / "w/a.snm"), b: str(self.root / "w/a.snm")}, EXT)

  def test0800realDBs(self):
    '''Super-DBs saved by PRDb -- one near, one far away (absolute) -- copied
    with it: the copy is read from where it is, builds on the copies, and isn't
    taken to have been copied.'''
    (self.root / "a/web").mkdir(parents=True)
    (self.root / "lib").mkdir()
    near = PRDb(str(self.root / "a/web/near.xml")); near.save()
    far = PRDb(str(self.root / "lib/far.xml")); far.save()
    main = PRDb(str(self.root / "a/web/main.xml"))
    main.addSuperDB(near); main.addSuperDB(far)
    main.save()
    srcs = [str(self.root / p) for p in ("a/web/main.xml", "a/web/near.xml", "lib/far.xml")]
    for db in (main, near, far):
      del PRDb.AllDBs[db.url]
    plan = layout(srcs, str(self.root / "copy"), base=str(self.root / "a/web"))
    Copier(plan, (".xml",)).run()
    shutil.rmtree(self.root / "a"); shutil.rmtree(self.root / "lib") # (the originals gone: only the copies can be found)
    with self.assertNoLogs("util.persistence.pRef", level="WARNING"): # (eg: not "... was copied or moved from ...")
      copy = PRDb.getDB(fileURL(str(self.root / "copy/main.xml")))
    self.assertEqual([db.url for db in copy.superDBs], [fileURL(str(self.root / "copy/near.xml")), fileURL(str(self.root / "copy/far.xml"))])
    self.assertEqual(copy.previousURL, fileURL(srcs[0]))
    for db in [copy, *copy.superDBs]:
      PRDb.AllDBs.pop(db.url, None)


if __name__ == "__main__":
  unittest.main()
