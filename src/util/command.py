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
Command objects serve to encapsulate actions so that they may be used in an
undo/redo list, typically mapped to cmd-z and shift-cmd-Z keys (or ctl-z for non-Mac).
They are also extended in the :mod:`~util.commandParser` for use in command line applications using
the :mod:`argparse` module. 

This module defines the following command hierarchy:

  .. inheritance-diagram:: 
                Command
                LambdaCommand 
                CommandWrapper
                DoList
      :parts: 1
      :private-bases:
      :top-classes: util.command.Command
    

  :class:`~util.command.Command` *abstract* (requires *do(), undo(), __str__()*)
  
      - :meth:`~util.command.Command.do()` defines execution of the command
      - :meth:`~util.command.Command.undo()` defines the undoing of the command
      - :meth:`~util.command.Command.__str__()`

    :class:`~util.command.LambdaCommand` 

    :class:`~util.command.CommandWrapper` 

  :class:`~util.command.DoList`
  
Created on Sep 16, 2024

.. codeauthor:: Rob Kremer <robkremer@me.com>

-------------------
'''

from abc import abstractmethod, ABC
from typing import Callable, NoReturn, override, Any, Optional
import util
import logging

logger:util.Logger = util.getLogger(__name__)

class RedoError(RuntimeError): pass
class UndoError(RuntimeError): pass

################################################################################
################################# Command ######################################
################################################################################    

class Command(ABC):
  '''
  The top-level object for do/undo command objects. The minimal interface for these are
  are and __init__(name:str) constructor and the zero-parameter *do()* and *undo()* methods.
  The *do()* and *undo()* methods are specified as abstract; however, they have implementations
  that check to so they are not called back-to-back without the other between them and that
  *do()* is called before *undo()*, so you may want to call the relevant *super()* methods. 
  '''

  def __init__(self, name:str):
    '''
    Constructor

    :param name:
    :type name: str
    '''
    self.name = name
    self.done:bool = False
    self.mutatedData:bool = True

  @abstractmethod
  def do(self) -> Any:
    """
    The execution of this command. This isn't really abstract in the you can (should?) call this
    method as the first instruction of your *do()* method to check that the *do()* isn't being called
    twice in a row without an *undo()* in between (a problem in the code logic?).

    :returns:
    :rtype: Any
    """
    if self.done: raise RedoError(f'Can\'t do command "{self.name}" a second time without an undo() in between.')
    self.done = True
    self.mutatedData = True
    return None

  @abstractmethod
  def undo(self) -> Any:
    """
    The undoing of this command. This isn't really abstract in the you can (should?) call this
    method as the first instruction of your *undo()* method to check that the *undo()* isn't being called
    twice in a row without an *do()* in between (a problem in the code logic?).

    :returns:
    :rtype: Any
    """
    if not self.done: raise UndoError(f'Can\'t undo command "{self.name}" without it first having been done (do()).')
    self.done = False
    self.mutatedData = True
    return None
    
  def delete(self):
    '''
    Override to destroy any data when the the command becomes unreachable. Called
    from *DoList* when new commands override the tail of the do-queue.
    '''
    pass    
    
  def __str__(self):
    '''
    :returns:
    :rtype:
    '''
    return self.name

################################################################################
################################# LambdaCommand ################################
################################################################################
    
class LambdaCommand(Command):
  """
  A alternative to implementing a new class overriding the *do()* and *undo()* methods.
  Instead this class's constructor takes "do" and "undo" zero-parameter function references
  (typically lambda functions) and merely calls them in the *do()* and *undo()* methods.
  Typical instantiation:
  
    incr = LambdaCommand("inc", lambda x=num: x.inc(), lambda x=num: x.dec())
  """

  def __init__(self, name:str, do:Callable[[], NoReturn], undo:Callable[[], NoReturn], changesState=True):
    '''
    :param name:
    :type name: str
    :param do:
    :type do: Callable[[], NoReturn]
    :param undo:
    :type undo: Callable[[], NoReturn]
    :param changesState:
    :type changesState: bool
    '''
    super().__init__(name)
    self.myDo = do
    self.myUndo = undo
    
  @override
  def do(self) -> Any:
    '''
    :returns:
    :rtype: Any
    '''
    super().do()
    return self.myDo()
    
  @override
  def undo(self) -> Any:
    '''
    :returns:
    :rtype: Any
    '''
    super().undo()
    return self.myUndo()
    
  @override
  def __str__(self):
    '''
    :returns:
    :rtype:
    '''
    return "LambdaCommand:"+self.name
    

################################################################################
################################# CommandWrapper ################################
################################################################################
    
class CommandWrapper(Command):
  """
  A *Command* wrapper that always executes a setup function before a *do()* and *undo()*
  and a teardown function after (if the setup and teardown are supplied).
  """

  def __init__(self, command:Command, name:Optional[str]=None, 
               setup:Optional[Callable]=None, teardown:Optional[Callable]=None,
               initSetup:Optional[Callable]=None, initTeardown:Optional[Callable]=None):
    '''
    :param command: A *Command* to wrap.
    :param name: [Optional] The name of the command; provided by *Command* if *None*.
    :param setup: [Optional] A function to execute before a *do()* or *undo()* call on *command*
    :param teardown: [Optional] A function to execute after a *do()* or *undo()* call on *command*
    :param initSetup: [Optional] Like *setup* but only called on the first *do()* (before *setup* )
    :param initTeardown: [Optional]  Like *teardown* but only called on the first *do()* (after *teardown* )
    '''
    super().__init__(name if name is not None else command.name)
    self.command:Command = command
    self.setup:Optional[Callable] = setup
    self.teardown:Optional[Callable] = teardown
    self.initSetup:Optional[Callable] = initSetup
    self.initTeardown:Optional[Callable] = initTeardown
    self.firstTimeDone = False
    
  @override
  def do(self) -> Any:
    """
    Calls the following functions specified in this object's constructor (if the are not *None*):
    
      - *initSetup()* if this is the first call to *do()*
      - *setup()* always
      - *command.do()* always
      - *teardown()* always
      - *initTeardown()* if this is the first call to *do()*

    :returns:
    :rtype: Any
    """
    super().do()
    if self.initSetup is not None and not self.firstTimeDone:
      self.initSetup()
    if self.setup is not None:
      self.setup()
    ret = self.command.do()
    if self.teardown is not None:
      self.teardown()
    if self.initTeardown is not None and not self.firstTimeDone:
      self.initTeardown()
    self.firstTimeDone = True
    return ret
    
  @override
  def undo(self) -> Any:
    """
    Calls the following functions specified in this object's constructor (if the are not *None*):
    
      - *setup()* 
      - *command.undo()* 
      - *teardown()*

    :returns:
    :rtype: Any
    """
    super().undo()
    if self.setup is not None:
      self.setup()
    ret = self.command.undo()
    if self.teardown is not None:
      self.teardown()
    return ret

  def __str__(self):
    '''
    :returns:
    :rtype:
    '''
    return "WrappedCommand: "+self.name

    
################################################################################
################################# DoList #######################################
################################################################################
    
class DoList():
  """
  A do/undo list responsible to execute *Commands*, keeping track of do's and undo's.
  """
  def __init__(self):
    self.queue:list[Command] = list()
    self.index = -1 # This is the index of the current item in the queue
    
  def do(self, c:Command) -> Any:
    """
    Appends a new *Command* after the current place in the queue and
    calls *do()* on that *Command*, possibly
    removing the tail of the queue if the current index is not past the 
    end of the queue (eg: we have done one or more *undo()*'s).

    :param c:
    :type c: Command
    :returns:
    :rtype: Any
    """
    if self.index+1 > len(self.queue):
      logger.error(f'DoList.do(): index ({self.index}) is past the end of queue (length {len(self.queue)})')
      return
    result = c.do()
    if c.mutatedData:
      # if the index is not at the end of the queue, truncate the queue
      if self.index+1 < len(self.queue):
        for old in self.queue[self.index+1:]:
          old.delete() 
        self.queue = self.queue[:self.index+1]
      self.queue.append(c)
      self.index += 1 # the current index: the index of the last command executed.
    return result
    
  def redo(self) -> Any:
    """
    :raises RedoError: if trying to redo past the end of the command queue.
    :returns:
    :rtype: Any
    """
    if self.index+1 > len(self.queue):
      logger.error(f'DoList.redo(): index ({self.index}) is past the end of queue (length {len(self.queue)})')
      return
    if self.index+1 == len(self.queue): # at the end of the queue
      logger.error("Cannot redo past the end of the command queue")
      return
    try:
      result = self.queue[self.index+1].do()
    finally: self.index += 1
    return result
    
  def undo(self) -> Any:
    """
    :raises UndoError: if trying to undo an empty command queue.
    :returns:
    :rtype: Any
    """
    if self.index < 0: # at the end of the queue
      logger.error("Cannot undo past the beginning of the command queue")
      return
    try:
      result = self.queue[self.index].undo()
    finally:
      self.index -= 1
    return result
    
  def getRedoDesc(self) -> str:
    """
    Returns a description of the command that will be executed on a *redo()*, or *None* if nothing to redo.

    :returns:
    :rtype: str
    """
    if self.index+1 == len(self.queue): # at the end of the queue
      return "<nothing to redo>"
    return self.queue[self.index+1].name
    
  def getUndoDesc(self) -> str:
    """
    Returns a description of the command that will be executed on a *undo()*, or *None* if nothing to undo.

    :returns:
    :rtype: str
    """
    if self.index < 0: # at the end of the queue
      return "<nothing to undo>"
    return self.queue[self.index].name

  def undoQueue(self) -> list[str]:
    """
    Returns a list of string representation of the commands in the undo list starting with the next to the undone.

    :returns:
    :rtype: list[str]
    """
    if self.index<0: return []
    ret = []
    for i in range(self.index, -1, -1):
      ret.append(str(self.queue[i]))
    return ret

  def redoQueue(self) -> list[str]:
    """
    Returns a list of string representation of the commands in the redo list starting with the next to the redone.

    :returns:
    :rtype: list[str]
    """
    size = len(self.queue)
    if self.index>size: return []
    ret = []
    for i in range(self.index+1, size):
      ret.append(str(self.queue[i]))
    return ret
    
  def nextUndo(self) -> str:
    """
    Returns the string representation of the next command to be undone.

    :returns:
    :rtype: str
    """
    q = self.undoQueue()
    return "<nothing to undo>" if len(q)==0 else q[0]
    
  def nextRedo(self):
    """
    Returns the string representation of the next command to be redone.

    :returns:
    :rtype:
    """
    q = self.redoQueue()
    return None if len(q)==0 else q[0]
  