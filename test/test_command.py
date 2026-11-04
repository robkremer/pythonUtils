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
DoList: a command that fails to undo (or redo) stays where it was in the queue.
'''
import unittest
from util.command import Command, DoList, LambdaCommand

class Logged(Command):
  def __init__(self, name:str, log:list, failUndo:bool=False, failDo:bool=False):
    super().__init__(name)
    self.log, self.failUndo, self.failDo = log, failUndo, failDo
  def do(self):
    super().do()
    if self.failDo and self.log.count(f"do {self.name}"):
      raise RuntimeError("boom")
    self.log.append(f"do {self.name}")
  def undo(self):
    super().undo()
    if self.failUndo:
      raise RuntimeError("boom")
    self.log.append(f"undo {self.name}")

class Test(unittest.TestCase):

  def test_failedUndoStays(self):
    log:list = []
    dl = DoList()
    dl.do(Logged("one", log))
    bad = Logged("bad", log, failUndo=True)
    dl.do(bad)
    with self.assertRaises(RuntimeError):
      dl.undo()
    self.assertEqual(dl.getUndoDesc(), "bad")       # (still the one to undo)
    self.assertEqual(dl.getRedoDesc(), "<nothing to redo>")
    self.assertTrue(bad.done)
    bad.failUndo = False
    dl.undo()                                        # (it can be undone again, once it works)
    self.assertEqual(log, ["do one", "do bad", "undo bad"])
    self.assertEqual(dl.getUndoDesc(), "one")

  def test_failedRedoStays(self):
    log:list = []
    dl = DoList()
    dl.do(Logged("one", log))
    bad = Logged("bad", log, failDo=True)
    dl.do(bad)
    dl.undo()
    with self.assertRaises(RuntimeError):
      dl.redo()
    self.assertEqual(dl.getRedoDesc(), "bad")       # (still the one to redo)
    self.assertEqual(dl.getUndoDesc(), "one")
    self.assertFalse(bad.done)

  def test_lambdaThatChangesNothingIsntKept(self):
    dl = DoList()
    dl.do(LambdaCommand("look", lambda: None, lambda: None, changesState=False))
    self.assertEqual(dl.getUndoDesc(), "<nothing to undo>")
    dl.do(LambdaCommand("change", lambda: None, lambda: None))
    self.assertEqual(dl.getUndoDesc(), "change")

if __name__ == "__main__":
  unittest.main()
