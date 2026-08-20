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
Created on Apr 18, 2026

@author: robkremer
'''
import unittest
from util.persistence.pRef import PRDb, PRObject, DuplicateNameError, PReference
from typing import override
from util.persistence.serialize import InstantiationInfo, PropertyInfo
from pathlib import Path
from isort.exceptions import ProfileDoesNotExist
import gc

class TestObject(PRObject):

  def __init__(self, db):
    PRObject.__init__(self, db)
    self._name = "?"

  @classmethod
  @override
  def getInstantiationInfo(cls)->InstantiationInfo:
    ret:InstantiationInfo = super().getInstantiationInfo()
    ret.postconSetters.append(PropertyInfo("_name", str))
    return ret

  @property
  @override
  def name(self) -> str:
    return self._name
  
  # @name.setter
  # @override
  # def name(self, newName:str):
  #   self._name = newName

class Test(unittest.TestCase):


  def setUp(self):
    pass


  def tearDown(self):
    PRDb.AllDBs = dict()


  def test_dbURLs(self):
    Path('temp.xml').unlink(missing_ok=True)
    db = PRDb("temp.xml")
    self.assertTrue(db.url.endswith(".xml"))
    Path('temp2.json').unlink(missing_ok=True)
    db = PRDb("temp2.json")
    self.assertTrue(db.url.endswith(".json"))
    Path('temp3.xml').unlink(missing_ok=True)
    db = PRDb("temp3")
    self.assertTrue(db.url.endswith(".xml"))
        
  def test_objectSaveAndRestore(self):
    Path('temp4.xml').unlink(missing_ok=True)
    db = PRDb("temp4")
    obj1 = TestObject(db)
    obj1._name = "fred"
    self.assertEqual(obj1.name, "fred")
    db.save()
    self.tearDown()
    db2 = PRDb("temp4")
    self.assertIsNot(db2, db)
    self.assertEqual(repr(db2), repr(db))
    self.assertIs(db2, PRDb("temp4")) # new() causes the existing object to be returned.
    self.assertEqual(db2[1].name, "fred")
    self.assertEqual(db2[1].db.url, db2.url)
    db = PRDb.getDB("temp4")
    self.assertEqual(db.url, db2.url)
    self.assertIs(db, db2)
    
  def test_pReference(self):
    Path('temp5.xml').unlink(missing_ok=True)
    db = PRDb("temp5.xml")
    obj1 = TestObject(db)
    obj1._name = "tarzan"
    obj2 = TestObject(db)
    obj2._name = "jane"
    ref1 = obj1.getPRef()
    self.assertIs(ref1(), obj1)
    ref2 = PReference("temp5.xml#jane")
    self.assertIs(ref2(), obj2)
    ref2 = PReference("temp5#jane")
    self.assertIs(ref2(), obj2)
    ref2 = PReference("temp5#'tarzan'")
    self.assertIs(ref2(), obj1)
    ref2 = PReference("temp5#1")
    self.assertIs(ref2(), obj1)
    db.save()
    self.tearDown()
    gc.collect()
    ref3 = PReference("temp5#1")
    self.assertIsNot(ref3(), obj1)
    self.assertEqual(ref3().name, obj1.name)
    
    # The below SHOULD work, but it depends on if the GC has cleared the original 
    # DB so that the weakref returns None...
    # print(f'{ref3()}:{id(ref3().db)}\n{obj1}:{id(obj1.db)}')
    # self.assertEqual(ref3(), obj1)
    
  def test_relativeRefs(self):
    Path('temp8.xml').unlink(missing_ok=True)
    db = PRDb("temp8.xml")
    obj1 = TestObject(db)
    obj1._name = "Alice"
    ref:PReference = PReference("1")
    self.assertEqual(ref(relativeTo=db).name, "Alice")
    self.assertIs(ref(relativeTo=db), obj1)
    
    ref2:PReference = PReference("1")
    with self.assertRaises(LookupError):
      ref2()
    self.assertIs(ref2(db), obj1)
    self.assertIs(ref2(), obj1)
    
    ref3:PReference = PReference("#Alice")
    with self.assertRaises(LookupError):
      ref3()
    self.assertIs(ref3(db), obj1)
    self.assertIs(ref3(), obj1)
    
  def test_saveas(self):
    Path('temp6.xml').unlink(missing_ok=True)
    Path('temp7.xml').unlink(missing_ok=True)
    db = PRDb("temp6.xml")
    obj1 = TestObject(db)
    obj1._name = "tarzan"
    obj2 = TestObject(db)
    obj2._name = "jane"
    db.save(saveas="temp7.xml")
    db2 = PRDb.getDB("temp7")
    self.assertEqual(db2[1].name, "tarzan")
    self.assertEqual(db[1].name, "tarzan")
    self.assertNotEqual(db[1], db2[1])
    
    
    


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.test_Name']
    unittest.main()