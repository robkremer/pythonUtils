'''
Tk command names that are never used twice (*uniqueCommandNames()*).

tkinter names the Tcl command it makes for each callback -- a binding, a
button's or menu item's command, a window-manager protocol handler, an
*after()* timer's callback -- by an address and the callback's name: eg,
"140312345678912<lambda>". When a widget is destroyed its commands are
deleted, but its pending timers aren't cancelled: each still holds its
command's name. That's usually harmless: the timer finds no such command.
But addresses are used again, so a callback of the same name registered
later (every lambda's name is "<lambda>") can get the very same command
name -- and then the destroyed widget's timer runs it: an unrelated
callback, when nobody asked for it (eg: a window's close handler -- the
window closes by itself).

With *uniqueCommandNames()*, each command's name has a serial number too: no
name is used twice, so a stale timer never finds anything to run.

Created on Nov 12, 2026

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''
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
from __future__ import annotations
import itertools
import tkinter as tk
from typing import Any, Callable

_serial = itertools.count(1)
"The serial numbers of the commands registered (see *uniqueCommandNames()*)."

_register:Callable[..., str]|None = None
"tkinter's own *Misc._register()*, once *uniqueCommandNames()* has replaced it."

def uniqueCommandNames() -> None:
  '''
  Have tkinter never use a Tcl command name twice (see the module doc): from
  now on, in every Tk interpreter of this process. Call it once, before the
  first window is made (again does nothing).

  It's done by registering, for each callback, a function that just calls
  it, named for the callback and a serial number: tkinter names the command
  after that. (Commands registered before this keep their names.)
  '''
  global _register
  if _register is not None:
    return
  original = _register = tk.Misc._register
  def register(self:tk.Misc, func:Callable[..., Any], subst:Callable[..., Any]|None=None, needcleanup:int=1) -> str:
    def call(*args:Any) -> Any:
      return func(*args)
    named = getattr(func, "__func__", func) # (a method's name is its function's, as tkinter has it)
    call.__name__ = f"{getattr(named, '__name__', type(func).__name__)}_{next(_serial)}"
    return original(self, call, subst, needcleanup)
  tk.Misc._register = register # type: ignore[method-assign]
