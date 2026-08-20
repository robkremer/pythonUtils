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
Created on Mar 21, 2026

@author: robkremer
'''
import unittest
from util.persistence.serialize import Serializable, InstantiationInfo, ParamInfo,\
  PropertyInfo, SerializationStrategy
# from  util.persistence.serializeXML import XMLSerializationStrategy
# from  util.persistence.serializeJSON import JSONSerializationStrategy

from typing import override
import os

strategies = SerializationStrategy.getAvailableStrategies()

class SamplePObject1(Serializable):

  def __init__(self, integer:int=1, floating:float=1.3, alist = [1,2.3,"Hello World"]):
    self.integer:int = integer
    self.floating:float = floating
    self.alist:list = alist
    self.static = ("constant",)
    
  @override
  @classmethod
  def getInstantiationInfo(cls) -> InstantiationInfo:
    info = InstantiationInfo(
            class_=cls, 
            conArgs=[ParamInfo("integer", int, lambda slf: slf.integer),
                     ParamInfo("floating", float, lambda slf: slf.floating)], 
            conKWArgs=[],
            postconSetters=[PropertyInfo("static", tuple)],
            #postconMethod=cls._post__init__,
            finalSetters=[PropertyInfo("alist", list)], 
            # finalMethod=cls._final__init__
            )
    return info
  
  def _post__init__(self, static:tuple):
    self.static = static
    
  def _final__init__(self, alist:list):
    self.alist = alist
    print(f'{str(self)}: _final__init__({alist})')
    
  def __eq__(self, other):
    if other.__class__ is SamplePObject1:
      return self.integer == other.integer and \
             self.floating == other.floating and \
             self.alist == other.alist and \
             self.static == other.static
    return False
  
class SamplePObject2(Serializable):

  @override
  @classmethod
  def getInstantiationInfo(cls) -> InstantiationInfo:
    info = InstantiationInfo(
      class_=cls, 
      conArgs=[ParamInfo("integer", int, lambda slf: slf.integer),
               ParamInfo("floating", float, lambda slf: slf.floating), 
               ParamInfo("alist", list, lambda slf: slf.alist)], 
      conKWArgs=[],
      postconSetters=[PropertyInfo("static", tuple, lambda slf: slf.static),
                   PropertyInfo("obj", SamplePObject1, lambda slf: slf.obj)],
      )
    return info
  
  def __init__(self, integer:int=2, floating:float=2.3, alist = [1,2.3,"Hello World"]):
    self.integer = integer
    self.floating = floating
    self.alist = alist
    self.static = ("constant",)
    self.obj = SamplePObject1()
    
  def _post__init__(self, static:tuple, obj:SamplePObject1):
    self.static = static
    self.obj = obj
  
  def __eq__(self, other):
    if isinstance(other, SamplePObject2):
      return self.integer == other.integer and \
             self.floating == other.floating and \
             self.alist == other.alist and \
             self.static == other.static and \
             self.obj == other.obj
    return False
  
#XMLinstantiator = XMLSerializationStrategy()

class Test(unittest.TestCase):

  def setUp(self):
    pass

  def tearDown(self):
    pass

  # def test_tostring_XML(self):
  #   self._test_tostring(XMLSerializationStrategy)
  #
  # # def test_tostring_JSON(self):
  # #   self._test_tostring(JSONSerializationStrategy)
  #
  # def _test_tostring[T:type](self, Strategy:T):
  #   obj = SamplePObject1()
  #   strategy = Strategy()
  #   print(f'1:\n-----\n{strategy.tostring(1)}\n-----')
  #   print(f'32.5:\n-----\n{strategy.tostring(32.5)}\n-----')
  #   print(f'Hello world:\n-----\n{strategy.tostring("Hello world!")}\n-----')
  #   print(f'list:\n-----\n{strategy.tostring([3, "Hello world!", 2.4, 3, 4, 4, 4, 4])}\n-----')
  #   print(f'tuple:\n-----\n{strategy.tostring((3, "Hello world!", 2.4))}\n-----')
  #   print(f'obj:\n-----\n{strategy.tostring(obj)}\n-----')
  #   strategy.write("file://"+os.getcwd()+"/temp", obj)
  #   obj2 = SamplePObject2()
  #   print(f'obj2:\n-----\n{strategy.tostring(obj2)}\n-----')
  #   strategy.write("file://"+os.getcwd()+"/temp2", obj2)
  #   print(f'nested list:\n-----\n{strategy.tostring([1,2,[3,4,[5,6]]])}\n-----')
  #   print(f'dict:\n-----\n{strategy.tostring({1:"one", "two":2})}\n-----')
    
  def test_ALL_writeReadback(self):
    print(f'\nWill test: {strategies}')
    for name, ext, strat in strategies:
      print(f'\n*** Testing writeReadback for strategy "{name}" ({ext}):')
      self._test_writeReadback(strat)
    
  # def test_writeReadback_XML(self):
  #   self._test_writeReadback(XMLSerializationStrategy)
  
  # def test_writeReadback_JSON(self):
  #   self._test_writeReadback(JSONSerializationStrategy)
  
  def _test_writeReadback[T:type](self, Strategy:T):
    stratName = Strategy.__name__
    url = "file://"+os.getcwd()+"/temp3"
    strategy = Strategy()
    
    # ints
    strategy.write(url, 1, wrap=None)
    x = strategy.read(url)
    self.assertEqual(x, 1, f'(strategy="{stratName}")')
    self.assertTrue(isinstance(x, int), f'(strategy="{stratName}")')
    
    # floats
    strategy.write(url, 14.5, wrap=None)
    x = strategy.read(url)
    self.assertEqual(x, 14.5, f'(strategy="{stratName}")')
    self.assertTrue(isinstance(x, float), f'(strategy="{stratName}")')
    
    # strs
    strategy.write(url, "hi", wrap=None)
    x = strategy.read(url)
    self.assertEqual(x, "hi", f'(strategy="{stratName}")')
    self.assertTrue(isinstance(x, str), f'(strategy="{stratName}")')
    
    # bools
    strategy.write(url, True, wrap=None)
    x = strategy.read(url)
    self.assertEqual(x, True, f'(strategy="{stratName}")')
    self.assertTrue(isinstance(x, bool), f'(strategy="{stratName}")')
    
    strategy.write(url, False, wrap=None)
    x = strategy.read(url)
    self.assertEqual(x, False, f'(strategy="{stratName}")')
    self.assertTrue(isinstance(x, bool), f'(strategy="{stratName}")')
    
    # lists
    strategy.write(url, [1,3,5], wrap=None)
    x = strategy.read(url)
    self.assertEqual(x, [1,3,5], f'(strategy="{stratName}")')
    self.assertTrue(isinstance(x, list), f'(strategy="{stratName}")')
    
    # tuples
    strategy.write(url, (1, "xx" ,5.9, True, False))
    x = strategy.read(url)
    self.assertEqual(x, (1, "xx" ,5.9, True, False), f'(strategy="{stratName}")')
    self.assertTrue(isinstance(x, tuple), f'(strategy="{stratName}")')
    
    #sets
    strategy.write(url, {"one", "three"})
    x = strategy.read(url)
    self.assertEqual(x, {"three", "one"}, f'(strategy="{stratName}")')
    self.assertTrue(isinstance(x, set), f'(strategy="{stratName}")')
    
    # dicts
    strategy.write(url, {"one":1, "three":3}, wrap=None)
    x = strategy.read(url)
    self.assertEqual(x, {"one":1, "three":3}, f'(strategy="{stratName}")')
    self.assertTrue(isinstance(x, dict), f'(strategy="{stratName}")')
    
    strategy.write(url, {1:"one", 3:"three"})
    x = strategy.read(url)
    self.assertEqual(x, {1:"one", 3:"three"}, f'(strategy="{stratName}")')
    self.assertTrue(isinstance(x, dict), f'(strategy="{stratName}")')
    
    # user defined objects
    obj = SamplePObject1()
    strategy.write(url, obj)
    x = strategy.read(url)
    self.assertEqual(x, obj, f'(strategy="{stratName}")')
    self.assertTrue(isinstance(x, SamplePObject1), f'(strategy="{stratName}")')
    
    # test finalMethod itialization
    obj = SamplePObject1()
    obj.alist = ['x', 'y'] # has a different alist that can only be restored by finalMethod.
    strategy.write(url, obj)
    x = strategy.read(url)
    self.assertEqual(x, obj, f'(strategy="{stratName}")')
    self.assertTrue(isinstance(x, SamplePObject1), f'(strategy="{stratName}")')
    
    obj2 = SamplePObject2()
    strategy.write(url, obj2)
    x = strategy.read(url)
    self.assertEqual(x, obj2, f'(strategy="{stratName}")')
    self.assertTrue(isinstance(x, SamplePObject2), f'(strategy="{stratName}")')
    
    obj2 = SamplePObject2()
    assert obj.alist == ['x', 'y']
    obj2.obj = obj
    assert obj2.obj.alist == ['x', 'y']   
    strategy.write(url, obj2)
    x = strategy.read(url)
    self.assertEqual(x, obj2, f'(strategy="{stratName}")')
    self.assertTrue(isinstance(x, SamplePObject2), f'(strategy="{stratName}")')
    self.assertEqual(x.obj, obj, f'(strategy="{stratName}")') # type: ignore[union-attr]
    self.assertTrue(isinstance(x.obj, SamplePObject1), f'(strategy="{stratName}")') # type: ignore[union-attr]

    # test a list with an element referencing that list (needs a Reference<:Serializable object)
    x = [1,2,3]
    x.append(x)
    x.append(5)
    strategy.write(url, x)
    y = strategy.read(url)
    self.assertIs(y, y[3], f'(strategy="{stratName}")')
    
    # test non-duplication of objects
    strategy.write(url, [obj2, obj2])
    x,y = strategy.read(url)
    self.assertIs(x, y, f'(strategy="{stratName}")')
    
    # test the header
    self.assertEqual(strategy.header["protocolVersion"], strategy.protocolVersion(), f'(strategy="{stratName}")')
    
    # # test the indentation (visually)
    # print(f'{stratName}:')
    # print(strategy.tostring(obj2))
    # print(strategy.tostring(obj2, indent="**"))
    
  def test_classMethods(self):
    url = "file://"+os.getcwd()+"/temp4"
    obj = SamplePObject2(6, 6.1, [3,4,5,6])
    SerializationStrategy.writex(url, obj, strategy="XML")
    x = SerializationStrategy.readx(url+".xml")
    self.assertEqual(x, obj)
    
    obj = SamplePObject2(7, 9.1, [2,3,4,5,6])
    SerializationStrategy.writex(url+".json", obj)
    x = SerializationStrategy.readx(url+".json")
    self.assertEqual(x, obj)
    
    print("\n"+SerializationStrategy.getAvailableStrategies(asString=True))
    
if __name__ == "__main__":
  #import sys;sys.argv = ['', 'Test.testName']
  unittest.main()