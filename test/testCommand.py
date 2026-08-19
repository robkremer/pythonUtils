'''
Created on Oct 13, 2024

.. codeauthor:: Rob Kremer <robkremer@me.com>
----
'''
import unittest
from util.command import Command, RedoError, UndoError, LambdaCommand, DoList
from typing import Any

class integer():
  def __init__(self, val):
    self.i:int = val
  def __add__(self, y):
    self.i += y;
    return self
  def __sub__(self, y):
    self.i -= y;
    return self
  def __str__(self):
    return str(self.i)
  def __call__(self):
    return self.i

#test do and undo on Command
class IncCmd(Command):
  def __init__(self, name, obj:Any, n:Any):
    super().__init__(name)
    assert hasattr(obj, "__add__")
    assert hasattr(obj, "__sub__")
    self.obj = obj
    self.n = n
  def do(self):
    super().do()
    self.obj += self.n
  def undo(self):
    super().undo()
    self.obj -= self.n
  def __str__(self):
    return f'IncCmd'
      

class TestCommand(unittest.TestCase):


  def setUp(self):
    pass


  def tearDown(self):
    pass


  def test0100Command(self):
    #test that Command is abstract
    with self.assertRaises(Exception):
      _ = Command("test") #type: ignore[abstract]
    
      
    val = integer(0)
    x = IncCmd("inc", val, 1)
    self.assertEqual(val(), 0)
    x.do()
    self.assertEqual(val(), 1)
    x.undo()
    self.assertEqual(val(), 0)
    x.do()
    self.assertEqual(val(), 1)
    x2 = IncCmd("inc2", val, 2)
    self.assertEqual(val(), 1)
    x2.do()
    self.assertEqual(val(), 3)
    x2.undo()
    self.assertEqual(val(), 1)
    x.undo()
    self.assertEqual(val(), 0)    
    
    #test LambdaCommand
    num = integer(0)
    incr = LambdaCommand("incr", lambda x=num: x+1, lambda x=num: x-1) #type: ignore[misc]
    self.assertEqual(num(), 0)
    incr.do()
  
    self.assertEqual(num(), 1)
    with self.assertRaises(RedoError):
      incr.do()  
    incr.undo()
    self.assertEqual(num(), 0)
    with self.assertRaises(UndoError):
      incr.undo()  
   
    #test DoQueue
    q = DoList()
    q.do(x)
    self.assertEqual(val(), 1)
    q.do(x2)
    self.assertEqual(val(), 3)
    q.undo()
    self.assertEqual(val(), 1)
    self.assertEqual(q.getUndoDesc(), "inc")
    self.assertEqual(q.getRedoDesc(), "inc2")
    q.redo()
    self.assertEqual(val(), 3)
    self.assertEqual(q.getUndoDesc(), "inc2")
    self.assertEqual(q.getRedoDesc(), "<nothing to redo>")
    q.undo()
    self.assertEqual(val(), 1)
    q.undo()
    self.assertEqual(val(), 0)
    self.assertEqual(q.getUndoDesc(), '<nothing to undo>')
    self.assertEqual(q.getRedoDesc(), "inc")
    # with self.assertRaises(UndoError):
    #   q.undo()
    q.redo()
    self.assertEqual(val(), 1)
    q.redo()
    self.assertEqual(val(), 3)
    # with self.assertRaises(RedoError):
    #   q.redo()
  

if __name__ == "__main__":
  #import sys;sys.argv = ['', 'Test.testName']

  unittest.main()