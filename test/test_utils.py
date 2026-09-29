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