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
Created on Apr 25, 2026

@author: robkremer
'''
import unittest
from util.attribute import AttributedObject, Attribute, \
  NOVALUE, NOINHERIT, UNRESTRICTED, VAR, VAR_DEFAULTED, CONST,\
  CONST_TYPEOVERRIDE, TYPENAME
from typing import Optional, override, Sequence
from util.persistence.serialize import ParamInfo, InstantiationInfo, SerializationStrategy

TEST_STRAT = "XML"

class TestAttrs(AttributedObject):
  def __init__(self, name:Optional[str]=None, individual:bool=False, parents:list=[]):
    AttributedObject.__init__(self)
    self.individual = individual
    self.parents:list[TestAttrs] = parents
    if name is not None:
      self["name"] = name

  @classmethod
  def getInstantiationInfo(cls)->InstantiationInfo:
    ret = super().getInstantiationInfo()
    ret.conKWArgs.append(ParamInfo("individual", bool))             
    ret.conKWArgs.append(ParamInfo("parents", list))
    return ret          

  @override
  def getSupers(self) -> Sequence[AttributedObject]:
    return self.parents

  @override
  def isIndividual(self) -> bool:
    return self.individual
  
  @override
  def __repr__(self):
    return f'{self.__class__.__name__}({self["name"]}, individual={self.individual}, parents={[x["name"] for x in self.parents]})@{id(self)}'


class Test(unittest.TestCase):


  def setUp(self):
    pass


  def tearDown(self):
    pass

  def setupHierarchy(self):
    self.thing = TestAttrs("thing", False)
    self.animal = TestAttrs("animal", False, [self.thing])
    self.person = TestAttrs("person", False, [self.animal])
    self.fred = TestAttrs("fred", True, [self.person])

    profession = TestAttrs("profession", False, [self.thing])
    profession["degree"] = "BSc"
    self.fred.parents.append(profession)
    self.animal["intelligence"] = "low"
    self.person["intelligence"] = "high"
    
  def test00InheritanceValues(self):
    thing = TestAttrs("thing", False)
    self.assertEqual(thing["name"], "thing")
    animal = TestAttrs("animal", False, [thing])
    self.assertEqual(thing["name"], "thing")
    self.assertEqual(animal["name"], "animal")
    person = TestAttrs(None, False, [animal])
    self.assertFalse(person.isIndividual())
    
    self.assertEqual(person["name"], "animal")
    person["name"] = "person"
    self.assertEqual(person["name"], "person")
    fred = TestAttrs("fred", True, [person])
    self.assertEqual(fred["name"], "fred")
    profession = TestAttrs("profession", False, [thing])
    profession["degree"] = "BSc"
    self.assertIs(profession["degree"], "BSc")
    fred.parents.append(profession)
    self.assertEqual(fred["degree"], "BSc")
    animal["intelligence"] = "low"
    self.assertEqual(fred["intelligence"], "low")
    person["intelligence"] = "high"
    self.assertEqual(fred["intelligence"], "high")
    with self.assertRaises(KeyError):
      person["hair"]
    
  def test01InheritanceAttr(self):
    thing = TestAttrs("thing", False)
    thing.setAttr("name", Attribute("thing", str, VAR))
    self.assertEqual(thing["name"], "thing")
    animal = TestAttrs("animal", False, [thing])
    self.assertEqual(thing["name"], "thing")
    self.assertEqual(animal["name"], "animal")
    with self.assertRaises(PermissionError): # can't weaken inheritance restrictions
      animal.setAttr("name", Attribute(NOVALUE, None, VAR_DEFAULTED))
    person = TestAttrs(None, False, [animal])
    self.assertEqual(person["name"], "animal")
    person["name"] = "person"
    self.assertEqual(person["name"], "person")
    fred = TestAttrs("fred", True, [person])
    self.assertEqual(fred["name"], "fred")
    profession = TestAttrs("profession", False, [thing])
    profession.setAttr("degree", Attribute("x", str, (NOINHERIT, UNRESTRICTED))) # same as VAR
    self.assertIs(profession["degree"], "x")
    fred.parents.append(profession)
    self.assertEqual(fred["degree"], NOVALUE)
    fred["degree"] = "MSc"
    self.assertEqual(fred["degree"], "MSc")
    animal["intelligence"] = "low"
    self.assertEqual(fred["intelligence"], "low")
    person["intelligence"] = "high"
    self.assertEqual(fred["intelligence"], "high")
    with self.assertRaises(KeyError):
      person["hair"]
      
  def test02Persistance(self):
    self.setupHierarchy()
    #print(strdict(self.person))
    self.assertEqual(self.person["name"], "person")
    string = SerializationStrategy.tostringx(TEST_STRAT, self.person)
    #print(string)
    person2 = SerializationStrategy.fromstringx(TEST_STRAT, string)
    assert isinstance(person2, TestAttrs)
    self.assertEqual(person2["name"], "person")
    
  def test03Persistance(self):
    self.setupHierarchy()
    #print(strdict(self.person))
    self.assertEqual(self.fred["name"], "fred")
    string = SerializationStrategy.tostringx(TEST_STRAT, self.fred)
    #print(string)
    person2 = SerializationStrategy.fromstringx(TEST_STRAT, string)
    assert isinstance(person2, TestAttrs)
    self.assertEqual(person2["name"], "fred")
    
  def test04PersistanceUniqueness(self):
    self.setupHierarchy()
    self.assertEqual(self.fred["name"], "fred")
    mary = TestAttrs("mary", True, [self.person])
    string = SerializationStrategy.tostringx(TEST_STRAT, (self.fred, mary))
    #print(string)
    res = SerializationStrategy.fromstringx(TEST_STRAT, string)
    assert isinstance(res, tuple)
    f,m = res
    self.assertIs(f.parents[0], m.parents[0])
    
  def test05InheritanceConstantRestrictions(self):
    top = TestAttrs("top", False, [])
    second = TestAttrs("second", False, [top])
    obj = TestAttrs("obj", True, [second])
    top.setAttr("constant", Attribute(100, int, CONST))
    top.setAttr("constOverride", Attribute(101, int, CONST_TYPEOVERRIDE))
    with self.assertRaises(PermissionError):
      second.setAttr("constant", Attribute(99, None, None))
    second.setAttr("constOverride", Attribute(99, None, None))
    self.assertEqual(second["constant"], 100)
    self.assertEqual(second["constOverride"], 99)
    with self.assertRaises(PermissionError):
      obj["constant"] = 0
    with self.assertRaises(PermissionError):
      obj["constOverride"] = 0
    self.assertEqual(obj["constant"], 100)
    self.assertEqual(obj["constOverride"], 99)
          
  def test06InheritanceVarRestrictions(self):
    top = TestAttrs("top", False, [])
    second = TestAttrs("second", False, [top])
    obj = TestAttrs("obj", True, [second])
    top.setAttr("var", Attribute(100, int, VAR))
    top.setAttr("varDef", Attribute(101, int, VAR_DEFAULTED))
    second.setAttr("var", Attribute(99, None, None))
    second.setAttr("varDef", Attribute(98, None, None))
    self.assertEqual(second["var"], 99)
    self.assertEqual(second["varDef"], 98)
    self.assertEqual(obj["var"], NOVALUE)
    self.assertEqual(obj["varDef"], 98)
    obj["var"] = 1
    obj["varDef"] = 0
    self.assertEqual(obj["var"], 1)
    self.assertEqual(obj["varDef"], 0)
          
  def test06InheritanceTypenameRestrictions(self):
    top = TestAttrs("top", False, [])
    second = TestAttrs("second", False, [top])
    obj = TestAttrs("obj", True, [second])
    top.setAttr("var", Attribute(100, int, TYPENAME))
    second["var"] = 99
    self.assertEqual(second["var"], 99)
    self.assertEqual(obj["var"], 99)
    with self.assertRaises(PermissionError):
      obj["var"] = 1
    self.assertEqual(obj["var"], 99)
          
    

if __name__ == "__main__":
  #import sys;sys.argv = ['', 'Test.testName']
  unittest.main()