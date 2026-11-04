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
  CONST_TYPEOVERRIDE, TYPENAME, LOCAL, TYPEONLY, UNINHERITED, PRIVATE, \
  Restriction, RestrictionTypes, restrictionTypesToString, restrictionTypesFromString
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

  def test07PrivateRestrictions(self):
    top = TestAttrs("top", False, [])
    second = TestAttrs("second", False, [top])
    obj = TestAttrs("obj", True, [second])
    top.setAttr("local", Attribute(1, int, LOCAL))
    top.setAttr("typeOnly", Attribute(2, int, TYPEONLY))
    top.setAttr("uninh", Attribute(3, int, UNINHERITED))
    # the defining object always sees its own attributes
    self.assertEqual((top["local"], top["typeOnly"], top["uninh"]), (1, 2, 3))
    # LOCAL: invisible to everything below
    for o in (second, obj):
      self.assertNotIn("local", o)
      self.assertNotIn("local", list(o.keys()))
      self.assertIsNone(o.getAttr("local"))
      self.assertIsNone(o.getInhAttr("local"))
      with self.assertRaises(KeyError):
        o["local"]
    # TYPEONLY: subtypes inherit it, individuals can't see it
    self.assertEqual(second["typeOnly"], 2)
    self.assertIsNotNone(second.getInhAttr("typeOnly"))
    self.assertNotIn("typeOnly", obj)
    self.assertNotIn("typeOnly", list(obj.keys()))
    # UNINHERITED: the key (slot) is visible, the value isn't
    for o in (second, obj):
      self.assertIn("uninh", o)
      self.assertIn("uninh", list(o.keys()))
      self.assertEqual(o["uninh"], NOVALUE)
      self.assertIsNotNone(o.getInhAttr("uninh")) # visible, unlike PRIVATE
    # keys(), items() and `in` agree
    for o in (top, second, obj):
      self.assertEqual(set(o.keys()), {k for k,_ in o.items()})
      self.assertTrue(all(k in o for k in o.keys()))

  def test08PrivateRedefinition(self):
    top = TestAttrs("top", False, [])
    second = TestAttrs("second", False, [top])
    obj = TestAttrs("obj", True, [second])
    top.setAttr("tag", Attribute(True, bool, LOCAL))
    # a hidden key can be defined afresh below; it's a new, unrelated attribute
    second["tag"] = "fresh"
    self.assertEqual(second["tag"], "fresh")
    self.assertIs(second.getLocalAttr("tag").type, str)
    self.assertEqual(obj["tag"], "fresh")
    self.assertIs(top["tag"], True)

  def test09PrivateMultipleInheritance(self):
    a = TestAttrs("a", False, [])
    b = TestAttrs("b", False, [])
    a.setAttr("x", Attribute(1, int, LOCAL))
    b.setAttr("x", Attribute(2, int, VAR_DEFAULTED))
    c = TestAttrs("c", False, [a, b])  # blind to a's x, so sees b's
    self.assertEqual(c["x"], 2)

  def test10PrivateLegality(self):
    top = TestAttrs("top", False, [])
    with self.assertRaises(PermissionError): # private to types but not individuals
      top.setAttr("bad", Attribute(1, int, Restriction(RestrictionTypes.UNRESTRICTED, PRIVATE)))
    top.setAttr("x", Attribute(1, int, VAR_DEFAULTED))
    second = TestAttrs("second", False, [top])
    with self.assertRaises(PermissionError): # the same, by merging with an inherited restriction
      second.setAttr("x", Attribute(2, None, Restriction(None, PRIVATE)))
    second.setAttr("x", Attribute(2, None, Restriction(PRIVATE, None))) # hide from individuals: fine
    self.assertNotIn("x", TestAttrs("obj", True, [second]))

  def test11RestrictionStrings(self):
    for r in (None, RestrictionTypes.UNRESTRICTED, PRIVATE, NOINHERIT, RestrictionTypes.ILLEGAL,
              NOINHERIT | PRIVATE, RestrictionTypes.NOOVERRIDE | PRIVATE, RestrictionTypes.ILLEGAL | PRIVATE):
      self.assertEqual(restrictionTypesFromString(restrictionTypesToString(r)), r)
    self.assertEqual(restrictionTypesFromString("NOINHERIT|PRIVATE"), NOINHERIT | PRIVATE)

  def test12CoerceValue(self):
    from util.attribute import coerceValue
    for typ, value, want in (("float", 30, 30.0), ("float", "2.5", 2.5), ("int", 3.0, 3), ("int", "3", 3),
                             ("bool", "Yes", True), ("bool", 0, False), ("color", "blue", "blue"), ("str", 7, "7"),
                             ("choices[a, b]", "b", "b"), (None, "x", "x")):
      got = coerceValue(typ, value)
      self.assertEqual(got, want)
      self.assertIs(type(got), type(want))
    for typ, value in (("int", 3.5), ("int", "abc"), ("bool", "maybe"), ("float", True), ("choices[a, b]", "c")):
      with self.assertRaises(ValueError):
        coerceValue(typ, value)

  def test13SetItemCoerces(self):
    'A value given for an inherited attribute is made its type, if it can be.'
    person = TestAttrs("person", False)
    person.setAttr("height", Attribute(1.5, float, Restriction.fromstring("VAR")))
    fred = TestAttrs("fred", True, [person])
    fred["height"] = "2"
    self.assertEqual(fred["height"], 2.0)
    self.assertIs(type(fred["height"]), float)

  def test14InheritedTypeEnforced(self):
    'A value for an inherited attribute must be (or be made) the inherited type: when it\'s first given, and when it\'s changed.'
    person = TestAttrs("person", False)
    person.setAttr("height", Attribute(1.5, float, Restriction.fromstring("VAR")))
    fred = TestAttrs("fred", True, [person])
    with self.assertRaises(ValueError):
      fred["height"] = "tall"                                    # (a new value-only attribute)
    self.assertNotIn("height", dict.keys(fred))
    with self.assertRaises(ValueError):
      fred.setAttr("height", Attribute("tall", None, None))
    fred.setAttr("height", Attribute(2, None, None))             # (coerced)
    self.assertIs(type(fred["height"]), float)
    with self.assertRaises(ValueError):
      fred["height"] = "tall"                                    # (changing the value-only attribute)
    self.assertEqual(fred["height"], 2.0)

  def test15InheritorsTold(self):
    'Those below an object that inherit an attribute from it are told when it changes (one with its own value, and those below it, are not); and when its supertypes change.'
    from util.observer import Observer
    class Kin(TestAttrs): # (knows what's below it)
      def __init__(self, name, individual=False, parents=[]):
        self.kids:list = []
        super().__init__(name, individual, list(parents))
        for p in parents:
          p.kids.append(self)
      @override
      def getSubs(self):
        return list(self.kids)
    class Watcher(Observer):
      def __init__(self):
        self.heard:list = []
      def update(self, subject, *topics):
        self.heard += [(subject["name"], t) for t in topics]
    thing = Kin("thing")
    animal = Kin("animal", parents=[thing])
    pet = Kin("pet", parents=[thing])
    dog = Kin("dog", parents=[animal, pet])                      # (the hierarchy joins up again)
    rex = Kin("rex", True, [dog])
    tom = Kin("tom", True, [animal])
    w = Watcher()
    for o in (thing, animal, pet, dog, rex, tom):
      o.attach(w)
    thing.setAttr("color", Attribute("grey", str, VAR))
    inherited = lambda: sorted(n for n, t in w.heard if t[0] == "mod inherited attribute")
    self.assertEqual(inherited(), ["animal", "dog", "pet", "rex", "tom"]) # (each once)
    self.assertTrue(all(t[1] == ("color",) for n, t in w.heard if t[0] == "mod inherited attribute"))
    animal["color"] = "brown"                                    # (its own value now)
    w.heard.clear()
    thing["color"] = "black"
    self.assertEqual(inherited(), ["dog", "pet", "rex"])         # (not animal, or tom below it; dog through pet)
    w.heard.clear()
    del animal["color"]
    self.assertEqual(inherited(), ["dog", "rex", "tom"])
    self.assertEqual(TestAttrs("loner").getSubs(), [])           # (by default: none)
    w.heard.clear()
    animal.notifySupersChanged()                                 # (eg: given another supertype)
    self.assertEqual(sorted(n for n, t in w.heard if t == ("mod supers", ())), ["animal", "dog", "rex", "tom"])

  def test16TypeWithSpacesRoundTrips(self):
    'A type written with spaces ("choices[yes, no]", as the attribute editor suggests) is saved as written, and read back.'
    from util.utils import getFullClassName
    self.assertEqual(getFullClassName("choices[a, b]"), "choices[a, b]")
    self.assertEqual(getFullClassName(int), "int")
    for typ in ("choices[yes, no]", "choices[error, warning]", "choices[yes,no]"):
      thing = TestAttrs("thing", False)
      thing.setAttr("answer", Attribute("no" if "no" in typ else "warning", typ, VAR_DEFAULTED))
      string = SerializationStrategy.tostringx(TEST_STRAT, thing)
      thing2 = SerializationStrategy.fromstringx(TEST_STRAT, string)
      assert isinstance(thing2, TestAttrs)
      self.assertEqual(thing2.getAttr("answer").type, typ)
      self.assertEqual(thing2["answer"], thing["answer"])
      self.assertFalse(thing2.isDirty())

  def test17UnreadableAttributeLeftOut(self):
    'An attribute that can\'t be read (eg: a type mangled by an older version) is left out, with a warning: the rest of the object is read.'
    thing = TestAttrs("thing", False)
    thing.setAttr("answer", Attribute("no", "choices[yes, no]", VAR_DEFAULTED))
    string = SerializationStrategy.tostringx(TEST_STRAT, thing)
    self.assertIn('choices[yes, no]', string)
    string = string.replace('choices[yes, no]', 'arnin') # (what the old getFullClassName() made of it)
    with self.assertLogs("util.attribute", level="WARNING") as logs:
      thing2 = SerializationStrategy.fromstringx(TEST_STRAT, string)
    assert isinstance(thing2, TestAttrs)
    self.assertEqual(thing2["name"], "thing")
    self.assertNotIn("answer", thing2)
    self.assertFalse(thing2.isDirty())
    self.assertIn('"answer"', "\n".join(logs.output))

  def test18OrphanedOverride(self):
    'An overriding value whose inherited attribute has gone (eg: its isa link removed) is the object\'s own value: \'in\' and getAttr() work.'
    person = TestAttrs("person", False)
    person.setAttr("hair", Attribute("brown", str, VAR_DEFAULTED))
    fred = TestAttrs("fred", True, [person])
    fred["hair"] = "red"                         # (a value-only override)
    self.assertIsNone(fred.getLocalAttr("hair").type)
    fred.parents.remove(person)                  # (its type gone)
    self.assertIn("hair", fred)
    self.assertEqual(fred["hair"], "red")
    a = fred.getAttr("hair")
    self.assertEqual((a.value, a.type, a.restriction), ("red", str, VAR_DEFAULTED))
    string = SerializationStrategy.tostringx(TEST_STRAT, fred)
    fred2 = SerializationStrategy.fromstringx(TEST_STRAT, string)
    self.assertIn("hair", fred2)
    self.assertEqual(fred2.getAttr("hair").value, "red")


if __name__ == "__main__":
  #import sys;sys.argv = ['', 'Test.testName']
  unittest.main()