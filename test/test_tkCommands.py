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
*util.tkCommands.uniqueCommandNames()*: no Tcl command name is used twice, so
a destroyed widget's timer can't run a callback registered later; and
callbacks -- timers, bindings, commands, methods, partials -- still work.

Created on Nov 12, 2026

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''
import functools
import unittest
import tkinter as tk
from util.tkCommands import uniqueCommandNames

class TestUniqueCommandNames(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    try:
      cls.root = tk.Tk()
    except tk.TclError as ex:
      raise unittest.SkipTest(f"no display: {ex}")
    cls.root.withdraw()
    uniqueCommandNames()
    uniqueCommandNames() # (again: nothing)

  @classmethod
  def tearDownClass(cls):
    cls.root.destroy()

  def wait(self, ms:int) -> None:
    'Run the event loop for *ms* milliseconds.'
    done = tk.BooleanVar(self.root, False)
    self.root.after(ms, lambda: done.set(True))
    self.root.wait_variable(done)

  def test_namesNotUsedTwice(self):
    '''
    Callbacks of the same name registered one after another, each deleted
    before the next (so its address is free to be used again): every
    command name is different, and each says what it's for.
    '''
    names = []
    for _ in range(500):
      name = self.root._register(lambda: None)
      names.append(name)
      self.root.deletecommand(name)
    self.assertEqual(len(set(names)), len(names))
    self.assertTrue(all("<lambda>_" in n for n in names), names[:3])
    name = self.root._register(self.wait)
    self.addCleanup(self.root.deletecommand, name)
    self.assertIn("wait_", name) # (a method: its function's name)
    name = self.root._register(functools.partial(print, "x"))
    self.addCleanup(self.root.deletecommand, name)
    self.assertIn("partial_", name) # (no name of its own: its class's)

  def test_staleTimerRunsNothing(self):
    '''
    A destroyed widget's pending timer doesn't run a callback registered
    later (tkinter's own names would have it run the first lambda registered
    after the widget went: see the module doc).
    '''
    fired:list[str] = []
    frame = tk.Frame(self.root)
    frame.after(60, lambda: fired.append("the destroyed widget's"))
    stale = frame._tclCommands[-1]
    frame.destroy()
    self.assertFalse(self.root.tk.call("info", "commands", stale)) # (deleted: but its timer's still pending)
    later = [self.root._register(lambda: fired.append("one registered later")) for _ in range(50)]
    self.addCleanup(lambda: [self.root.deletecommand(n) for n in later])
    self.assertNotIn(stale, later)
    report = self.root.report_callback_exception
    self.root.report_callback_exception = lambda *_: None
    self.addCleanup(setattr, self.root, "report_callback_exception", report)
    self.wait(200)
    self.assertEqual(fired, [])

  def test_callbacksStillWork(self):
    'Timers (with arguments, and cancelled), bindings (with their event), commands and protocol handlers.'
    got:list = []
    self.root.after(10, got.append, "timer")
    self.root.after(10, functools.partial(got.append, "partial"))
    cancelled = self.root.after(10, got.append, "cancelled")
    self.root.after_cancel(cancelled)
    self.root.after_idle(lambda: got.append("idle"))
    self.wait(100)
    self.assertEqual(sorted(got), ["idle", "partial", "timer"])
    top = tk.Toplevel(self.root)
    self.addCleanup(top.destroy)
    button = tk.Button(top, text="b", command=lambda: got.append("command"))
    button.pack()
    button.invoke()
    top.bind("<<Custom>>", lambda e: got.append(type(e).__name__))
    top.update()
    top.event_generate("<<Custom>>")
    top.update()
    top.protocol("WM_DELETE_WINDOW", lambda: got.append("close"))
    self.root.tk.call(top.protocol("WM_DELETE_WINDOW"))
    self.assertEqual(got[3:], ["command", "Event", "close"])
    self.root.bind_all("<<Broken>>", lambda e: got.append("all"))
    self.addCleanup(self.root.unbind_all, "<<Broken>>")
    top.bind("<<Broken>>", lambda e: "break") # (a binding that breaks: its result gets through, so the rest aren't run)
    top.event_generate("<<Broken>>")
    top.update()
    self.assertNotIn("all", got)
    scrollbar = tk.Scrollbar(top)
    text = tk.Text(top, yscrollcommand=scrollbar.set) # (a callback Tk passes arguments to)
    text.pack()
    text.insert("end", "line\n" * 200)
    top.update()
    self.assertNotEqual(scrollbar.get(), (0.0, 1.0))

if __name__ == "__main__":
  unittest.main()
