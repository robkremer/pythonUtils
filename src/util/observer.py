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
An "extended" implementation of the observer/subject design pattern.  Instead to the
traditional subject calling *notify()* for every change (which may result in a lot of
unnecessary updates happening), we use the "with" clause to more elegantly 
manage updates:

.. code-block:: python
  :caption: *Within the the Subject's code...*
  :emphasize-lines: 1,4,6

  with Subject.ChangeMgr(self) as changeMgr:
    try:
      # make a change
      ...
      changeMgr.registerTopics(("topic1", (value [,...])), ("topic2", (value [,...])))
    except:
      changeMgr.cancel()

In the event the changes are nested (ie: the "<make a change>" section calls other methods
with updates), this results in saving up all the notifies until the outer update completes.
The *registerTopics()* method assures that the topics are passed in the eventual *notify()*
method. The *cancel()* method will suppress the final *notify()* if all nested updates also
resulted in a *cancel()*. 

There are two ways you can get event notifications from a *Subject* object.
The first is an *Observer* object must registers with the Subject as an *Observer*
which obligates the *Observer* to provide an *update()* method:

.. code-block:: python
  :caption: *Within the the Observer's code...*
  :emphasize-lines: 1,5

    subject.attach(self, "topic1", "topic2")
  
  ...
  
  def update(self, subject: Subject, *topics:Tuple[str, Tuple[Any, ...]]) -> None:
    topic:str
    params:tuple[Any, ...]
    for topic, params in topics:
      if topic == "topic1":
        # deal with topic1 and it's params
        ...
      elif topic == "topic2":
        ...
        
The second way to get a notification is through a callback:

.. code-block:: python
  :caption: *No need for an Observer class...*

  subject.attachCallback(lambda topic, args: print(f'{topic}: {args}), \\
                         "topic1", 
                         "topic2")
  
In this case, the lambda function will be invoked whenever the topic event
happens. It could also have been an independent function or a method call.

There is an alternate version of *notify()*, *notifyLater()* that works similarly, 
but deferred until the current call stack unwinds (e.g.
until a constructor finishes) instead of firing observers synchronously,
mid-construction. Use this anywhere notify() would otherwise let an
Observer inspect a not-yet-fully-built object.

Updates (The arguments to Subject.notify() and Observer.update() are expected 
to be tuples with the first element being a "topic" of *str* type and the second
element being a tuple "arguments" to the topic. 

.. inheritance-diagram:: Subject Observer
    :parts: 3
    :private-bases:
    :top-classes: object

Created on Sep 17, 2024

.. codeauthor:: Rob Kremer <robkremer@me.com>

------------
'''

from __future__ import annotations
import sys
from copy import copy
import threading
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional
import util
import logging

logger:util.Logger = util.getLogger(__name__)

enabled:bool = True
'''
Use the enabled flag if you must disable all notifications, for example, during
initialization or reading in new data from a file.  Don't forget to restore it
to *True*.
'''

alwaysLater:bool = False
'''
Set this to *True* for force (application wide) ALL calls to *notify* to behave
as calls to *notifyLater*. 
'''

class Subject:
  """
  The Subject interface declares a set of methods for managing subscribers.
  """

  class ChangeMgr:
    '''
    A context manager that collects the topics registered during a change (see
    *registerTopics()*) and notifies the subject's observers once, when the
    outermost change ends -- unless it was cancelled.
    '''
    def __init__(self, owner:Subject, later:bool=False):
      '''
      :param owner: The subject doing the calling.
      :type owner: Subject
      :param later: Iff this is True, use *notifyLater()* instead of *notify()*.
        Default is False.
      :type later: bool
      '''
      assert isinstance(owner, Subject)
      self.owner:Subject = owner
      self.cancelled:bool = False
      self.later:bool = later
      if self.owner._changeDepth == 0:
        self.owner._topics = [] # [(topic, params)]
        self.owner._confirmedCount = 0
    def __enter__(self) -> Subject.ChangeMgr:
      '''
      :returns:
      :rtype: Subject.ChangeMgr
      '''
      self.owner._changeDepth += 1
      return self
    def __exit__(self, _exc_type, _exc_val, _exc_tb):
      '''
      :param _exc_type:
      :type _exc_type:
      :param _exc_val:
      :type _exc_val:
      :param _exc_tb:
      :type _exc_tb:
      '''
      self.owner._changeDepth -= 1
      if not self.cancelled:
        self.owner._confirmedCount += 1
      assert self.owner._changeDepth >= 0
      assert self.owner._confirmedCount >= 0
      if self.owner._changeDepth == 0 and self.owner._confirmedCount > 0:
        if self.later:
          self.owner.notifyLater(*self.owner._topics)
        else:
          self.owner.notify(*self.owner._topics)
    def cancel(self):
      self.cancelled = True
    def registerTopics(self, topics:list[tuple[str, tuple[Any, ...]]]|tuple[str, tuple[Any, ...]]):
      '''
      :param topics:
      :type topics: list[tuple[str, tuple[Any, ...]]] | tuple[str, tuple[Any, ...]]
      '''
      if not isinstance(topics, list):
        topics = [topics]
      for t in topics:
        assert isinstance(t, tuple), f'Subject.ChangeMgr.registerTopics() parameters should be tuples, got type {t.__class__.__name__}, value "{t}".'
        assert isinstance(t[0], str), f'Expected a string topic name as first item in a topic tuple, but got tuple "{t}".' 
      self.owner._topics += topics

  def __init__(self):
    super().__init__()
    self._topics:list[tuple[str, tuple[Any, ...]]] = []
    self._changeDepth:int = 0 # keeps track of the depth of calls to ChangeMgr
    self._confirmedCount:int = 0 # count of successful (not cancelled) 'with ChangeMgr' bodies
    self._observers:list[tuple[Observer, set[str]]] = []
    self.addObserver = self.attach # alias to match the pattern
    self._callbacks:list[tuple[Callable, set[str], int]] = []
    self.callbackCode = 0
  
  def attach(self, observer: Observer, *topics:str) -> None:
    '''
    :param observer:
    :type observer: Observer
    :param topics:
    :type topics: str
    '''
    assert isinstance(observer, Observer)
    o:tuple[Observer, set[str]]
    for o in self._observers:
      if o[0] is observer:
        for t in topics:
          o[1].add(t)
        #utils.removeDuplicatesInPlace(o[1])
        return      
    self._observers.append((observer, set(topics)))

  def detach(self, observer: Observer) -> int:
    '''
    :param observer: The observer object to stop send updates to.
    :return: The number of entries removed (there may be more than 1 if topics
        were registered on different occasions).
    '''
    removals = []
    for tup in self._observers:
      if tup[0] is observer:
        removals.append(tup)
    for r in removals:
      self._observers.remove(r)
    return len(removals)
  
  def attachCallback(self, callback:Callable[[str, tuple[Any, ...]],Any], *topics:str) -> int:
    '''
    :param callback: A function taking a str and a *args* parameter.
    :type callback: Callable[[str, tuple[Any, ...]],None]
    :param topics: [str] topics for which the callback should be called. If 
      omitted, all topics will be called.
    :type topics: *str*
    :return: An int that can be used to detach the callback.
    
    An implementation of an anonymous observer: The callback is called whenever a topic is matched 
    on an event.  Use *detachCallback()* with the return from this method to detach.
    '''
    assert isinstance(callback, Callable) # type: ignore[arg-type]
    ret = self.callbackCode
    self.callbackCode += 1
    self._callbacks.append((callback, set(topics), ret))
    return ret
    
  def detachCallback(self, code:int):
    '''
    :param code: An int (that was returned from *attachCallback()*) identifying the callback to remove.
    '''
    i = 0
    for t in self._callbacks:
      if t[2] == code:
        self._callbacks.pop(i)
        return
      i += 1   
    
  def notify(self, *topics:tuple[str, tuple[Any, ...]]) -> None:
    '''
    :param topics: list[Tuple[str, Any, ...]]: A \\*list of topicName/info tuple 
        describing the topic and any further info parameters.
        
    Trigger an update in each subscriber iff either it has no specific topics
    or one or more of it's topics matches.

    :returns:
    :rtype: None
    '''
    if enabled and (self._observers or self._callbacks):
      return self.notifyLater(*topics) if alwaysLater else self._notify(*topics)
    
      
  def _notify(self, *topics:tuple[str, tuple[Any, ...]], 
              observers:list[tuple[Observer, set[str]]]|None=None, 
              callbacks:list[tuple[Callable, set[str], int]]|None=None) -> None:
    '''
    :param topics: A \\*list of topicName/info tuple 
        describing the topic and any further info parameters.
    :type topics: list[Tuple[str, Any, ...]]
    :param observers: The list of observers to use.
    :type observers: list[Observer]
    :param callbacks: list[tuple[Callable, set[str], int]]
        
    Trigger an update in each subscriber iff either it has no specific topics
    or one or more of it's topics matches.
    
    NOTE: the observers and callbacks seem strange given that the object has them
    already. But if this method is called "later" (usually on the tk event loop),
    the observers and callbacks should be those AT THE TIME OF THE ORIGINAL NOTIFICATION,
    not at the time the notification actually eventually happens.
    '''
    if not enabled:
      return
      
    if observers is None:
      observers = self._observers
    if callbacks is None:
      callbacks = self._callbacks
      
    # check params
    for t in topics:
      if not isinstance(t,tuple):
        assert isinstance(t, tuple), f'Subject.notify() parameters should be tuples, got type {t.__class__.__name__}, value "{t}".'
      assert isinstance(t[0], str), f'Expected a string topic name as first item in a topic tuple, but got tuple "{t}".'
      
    # do the regular Observer updates       
    deleteList:list[int] = []
    #i = 0
    tup:tuple[Observer, set[str]]
    for tup in observers: # NOTE: this is the observers in the parameter, not from self.
      # collect the updates of interest for an Observer
      updates:list[tuple[str, tuple[Any, ...]]] = []
      obsTopics:set[str] = tup[1]
      if len(tup[1]) == 0:
        updates = list(topics)
      else:
        s:str
        for s in obsTopics: #tup[1]:
          for tup2 in topics:
            if s == tup2[1]:
              updates.append(tup2)
      if len(tup[1]) == 0 or len(updates) > 0:
        # send the batch updates to the Observer
        try:
          tup[0].update(self, *updates) 
        except NameError:
          # the Observer is no longer responding, so mark it for removal from our list
          logger.exception(f'{self}: Observer at "{tup[0]}" appears to have been destroyed, removing it from observers list.')
          deleteList.append(id(Observer))
        except Exception as ex:
          logger.exception(f'Supject.notify(): {ex}') # subject raised an exception, ignore it
      #i += 1
    for d in deleteList: # delete any unresponsive Observers from our list
      try: # this could fail because the lists may no longer be the same. Fail silently.
        # NOTE: this is the observers from self, not the parameter line
        self._observers[:] = [item for item in self._observers if id(item) != d]
      except:
        pass
    
    # do the callbacks
    deleteList = []
    #i = 0
    tup3:tuple[Callable, set[str], int]
    for tup3 in callbacks: # NOTE: this is the callbacks in the parameter, not from self.
      updates = []
      if len(tup3[1]) == 0:
        updates = list(topics)
      else:
        for s in tup3[1]:
          for tup4 in topics:
            if s == tup4[1]:
              updates.append(tup4)
      if len(tup3[1]) == 0 or len(updates) > 0:
        try:
          for u in updates: 
            tup3[0](u[0],u[1])
        except Exception as ex:
          logger.exception(f'{self}: Callback "{tup3[2]}" raised an exception and has been removed: {ex}')
          deleteList.append(id(tup3))
        except Exception as ex:
          pass # subject raised an exception, ignore it
      #i += 1
    for d in deleteList:
      try: # this could fail because the lists may no longer be the same. Fail silently.
        # NOTE: this is the observers from self, not the parameter line
        self._callbacks[:] = [item for item in self._callbacks if id(item) != d]
      except:
        pass

  # Optional override: a callable(func, *args) -> None that arranges for
  # func(*args) to run later rather than synchronously. Set at the class
  # level (Subject.scheduler = ...) to force a strategy app-wide, or per
  # instance if some Subjects live in a different environment than others.
  scheduler: Optional[Callable[..., None]] = None

  def notifyLater(self, *topics: tuple[str, tuple[Any, ...]]) -> None:
    '''
    Like notify(), but deferred until the current call stack unwinds (e.g.
    until a constructor finishes) instead of firing observers synchronously,
    mid-construction. Use this anywhere notify() would otherwise let an
    Observer inspect a not-yet-fully-built object.

    Tries, in order: an app-supplied scheduler (self.scheduler /
    Subject.scheduler); tkinter's default root's after_idle(), if tkinter
    is already imported and has a live root; an asyncio event loop's
    call_soon()/call_soon_threadsafe(), if one is running; and finally a
    threading.Timer(0, ...) as a last resort.

    *self._observers*/*self._callbacks* are snapshotted right here, before
    any of those schedulers run -- not read again when the deferred call
    actually fires -- since by then they may have changed (an Observer
    attached/detached in the meantime, say), and the whole point of
    deferring is to still deliver the notification this call was actually
    asked to send. None of the four scheduling mechanisms below reliably
    accepts extra keyword arguments to forward to the deferred call (Tk's
    after_idle() and asyncio's call_soon()/call_soon_threadsafe() only take
    ``*args`` at all; threading.Timer does take a kwargs= param, but there's no
    reason to special-case it), so the snapshot is captured as plain local
    variables and closed over by a single, argument-less _fireNow(), which
    every scheduler is just asked to call once, later, with nothing further
    to pass through.

    :param topics: Same as notify().
    :rtype: None
    '''
    if not enabled:
      return

    observers = copy(self._observers)
    callbacks = copy(self._callbacks)
    def _fireNow() -> None:
      self._notify(*topics, observers=observers, callbacks=callbacks)

    scheduler = self.scheduler or Subject.scheduler
    if scheduler is not None:
      scheduler(_fireNow)
      return

    tk = sys.modules.get("tkinter")
    if tk is not None and tk._default_root is not None:
      tk._default_root.after_idle(_fireNow)
      return

    aio = sys.modules.get("asyncio")
    if aio is not None:
      try:
        loop = aio.get_running_loop()
      except RuntimeError:
        loop = None
      if loop is not None:
        if threading.current_thread() is threading.main_thread():
          loop.call_soon(_fireNow)
        else:
          loop.call_soon_threadsafe(_fireNow)
        return

    threading.Timer(0, _fireNow).start()



class Observer(ABC):
  """
  The Observer interface declares the update method, used by subjects.
  """

  @abstractmethod
  def update(self, subject: Subject, *topics:tuple[str, tuple[Any, ...]]) -> None:
      """
      Receive update from subject.

      :param subject:
      :type subject: Subject
      :param topics:
      :type topics: tuple[str, tuple[Any, ...]]
      """
      pass
