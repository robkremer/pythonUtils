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
The attribute editor doesn't change the object while it's open: an attribute
added (or an inherited one overridden) there is only returned by Save, for the
caller to set (eg: as an undoable command); Cancel leaves the object as it was.
'''
import gc
import unittest
import tkinter as tk
from typing import Sequence, override
from util.attribute import AttributedObject, Attribute, VAR_DEFAULTED
from util.attributeEditor import editAttrsBox, HierarchicalAttrEditor
import util.attributeEditor as attributeEditor

class Obj(AttributedObject):
  def __init__(self, name:str, parents:Sequence[AttributedObject]=(), individual:bool=False):
    AttributedObject.__init__(self)
    self.parents, self.individual = list(parents), individual
    self["name"] = name
  @override
  def getSupers(self) -> Sequence[AttributedObject]:
    return self.parents
  @override
  def isIndividual(self) -> bool:
    return self.individual

class TestAttributeEditor(unittest.TestCase):

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
    del cls.root
    gc.collect() # (the editors' Tk variables go now, in this thread: else a later collection in another thread -- eg: a test's server -- deletes them there, which Tcl can't do)

  def setUp(self):
    self.person = Obj("person")
    self.person.setAttr("hair", Attribute("brown", str, VAR_DEFAULTED))
    self.fred = Obj("fred", [self.person], individual=True)
    self.fred.setDirty(False)
    self.person.setDirty(False)

  def edit(self, act, editKey:str|None=None) -> dict|None:
    'Show the editor on fred, and do *act* to it once it\'s up: the edits it returns.'
    original = HierarchicalAttrEditor.show
    def show(editor, editKey=None):
      editor.after(50, lambda: act(editor))
      original(editor, editKey=editKey)
    HierarchicalAttrEditor.show = show # type: ignore[method-assign]
    try:
      return editAttrsBox(self.root, self.fred, title="fred", editKey=editKey)
    finally:
      HierarchicalAttrEditor.show = original # type: ignore[method-assign]

  def assertUnchanged(self):
    self.assertEqual(sorted(dict.keys(self.fred)), ["name"])
    self.assertFalse(self.fred.isDirty())

  def test_addCancelled(self):
    edits = self.edit(lambda e: (e._addNewAttribute2(None, "newA"), e.dismiss()))
    self.assertIsNone(edits)
    self.assertUnchanged()

  def test_addSaved(self):
    def act(e):
      e._addNewAttribute2(None, "newA")
      self.assertUnchanged()                   # (not while the dialog's open)
      e.vars["newA"].setValue("hello")
      e.save()
    edits = self.edit(act)
    self.assertUnchanged()                     # (the caller sets it)
    assert edits is not None
    a = edits["newA"]
    self.assertEqual((a.value, a.type, a.restriction), ("hello", "str", VAR_DEFAULTED))

  def test_addSavedWithoutAValue(self):
    edits = self.edit(lambda e: (e._addNewAttribute2(None, "newA"), e.save()))
    assert edits is not None
    self.assertIn("newA", edits)
    self.assertEqual(edits["newA"].value, "")

  def test_addDeletedAgain(self):
    def act(e):
      e._addNewAttribute2(None, "newA")
      e.vars["newA"].delete = True
      e.save()
    self.assertIsNone(self.edit(act))
    self.assertUnchanged()

  def test_overrideCancelled(self):
    def act(e):
      e._override("hair", self.person.getAttr("hair"), 2, tk.Button(e))
      e.dismiss()
    self.assertIsNone(self.edit(act))
    self.assertUnchanged()

  def test_overrideSaved(self):
    def act(e):
      e._override("hair", self.person.getAttr("hair"), 2, tk.Button(e))
      e.vars["hair"].setValue("red")
      e.save()
    edits = self.edit(act)
    self.assertUnchanged()
    assert edits is not None
    a = edits["hair"]
    self.assertEqual((a.value, a.type, a.restriction), ("red", None, None)) # (value-only: the type's inherited)

  def test_editKeyCancelled(self):
    self.assertIsNone(self.edit(lambda e: e.dismiss(), editKey="hair"))
    self.assertUnchanged()


if __name__ == "__main__":
  unittest.main()
