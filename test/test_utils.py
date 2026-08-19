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

    
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()