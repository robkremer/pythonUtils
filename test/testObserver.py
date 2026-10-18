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
Created on Oct 15, 2024

@author: kremer
'''
import unittest
from util import observer
from util.observer import Subject, Observer
from typing import Any, Optional

class ConcreteSubject(Subject):
  """
  The Subject owns some important state and notifies observers when the state
  changes.
  """

  _state:Optional[int] = None
  _states:dict[str,Any] = dict()
  """
  For the sake of simplicity, the Subject's state, essential to all
  subscribers, is stored in this variable.
  """

  def changeGeneric(self, val:int) -> None:
    with Subject.ChangeMgr(self):
      self._state = val

  def changeCancelled(self, val:int) -> None:
    with Subject.ChangeMgr(self) as changeMgr:
      self._state = val
      changeMgr.cancel() # shouldn't normally do this (with above) as it leads to inconsistencies.

  def changetopics(self, *topics) -> None:
    assert isinstance(topics, tuple), f"Expected a tuple, got {topics.__class__.__name__}"
    with Subject.ChangeMgr(self) as changeMgr:
      t = dict()
      for topic in topics:
        t[topic[0]] = topic[1]
      self._states.update(t)
      changeMgr.registerTopics(list(topics))

class ConcreteObserverA(Observer):
  def __init__(self):
    self.updateCount = 0
    self._state = None
    self._states = dict()
  def update(self, subject: Subject, *topics) -> None:
    assert isinstance(subject, ConcreteSubject)
    self.updateCount += 1
    self._state = subject._state
    self._states.update(topics)


class ConcreteObserverB(Observer):
  def __init__(self):
    self.updateCount = 0
    self._state = None
    self._states = dict()
  def update(self, subject: Subject, *topics) -> None:
    assert isinstance(subject, ConcreteSubject)
    self.updateCount += 1
    self._state = subject._state
    self._states.update(topics)



class RecordingObserver(Observer):
  "Keeps every topic it's sent, in order."
  def __init__(self):
    self.updateCount = 0
    self.received:list[tuple[str, Any]] = []
  def update(self, subject: Subject, *topics) -> None:
    self.updateCount += 1
    self.received += topics


class TestObserver(unittest.TestCase):

    def setUp(self):
      self.subject = ConcreteSubject()
      self.observer_a = ConcreteObserverA()
      self.subject.attach(self.observer_a)
      self.observer_b = ConcreteObserverB()
      self.subject.attach(self.observer_b)
      self.subject.changeGeneric(1)

    def tearDown(self):
        pass


    def test01002Observers(self):
      self.assertEqual(self.observer_a._state, 1)
      self.assertEqual(self.observer_b._state, 1)
      self.subject.changeGeneric(3)
      self.assertEqual(self.observer_a._state, 3)
      self.assertEqual(self.observer_b._state, 3)

    def test0200detach(self):
      self.subject.detach(self.observer_a)
      self.subject.changeGeneric(5)
      self.assertEqual(self.observer_a._state, 1)
      self.assertEqual(self.observer_b._state, 5)

    def test0300Cancel(self):
      self.subject.detach(self.observer_a)
      self.subject.changeGeneric(3)
      self.subject.changeCancelled(6)
      self.assertEqual(self.subject._state, 6)
      self.assertEqual(self.observer_a._state, 1)
      self.assertEqual(self.observer_b._state, 3)
      
    def test0400Topic(self):
      self.subject.attach(self.observer_a, "topicA")
      self.assertEqual(self.observer_a.updateCount, 1)
      self.assertEqual(self.observer_b.updateCount, 1)
      self.subject.changetopics(("topicB", 33))
      self.assertEqual(self.observer_b.updateCount, 2)
      self.assertEqual(self.observer_a.updateCount, 1)
      with self.assertRaises(KeyError):
        _ = self.observer_a._states["topicB"]
      self.assertEqual(self.observer_b._states["topicB"], 33)

    def test0410TopicsAttachedForArrive(self):
      watcher = RecordingObserver()
      self.subject.attach(watcher, "topicA", "topicC")
      self.subject.changetopics(("topicC", 3), ("topicB", 2), ("topicA", 1))
      self.assertEqual(watcher.received, [("topicC", 3), ("topicA", 1)]) # (in the order they came)
      self.subject.changetopics(("topicB", 4))
      self.assertEqual(watcher.updateCount, 1)

    def test0420NameErrorRemovesTheObserver(self):
      class Gone(Observer):
        def update(self, subject, *topics): raise NameError("gone")
      gone = Gone()
      self.subject.attach(gone)
      with self.assertLogs(observer.logger, level="ERROR"):
        self.subject.changeGeneric(7)
      self.assertFalse(any(o is gone for o, _ in self.subject._observers))
      self.assertTrue(any(o is self.observer_a for o, _ in self.subject._observers))
      self.assertEqual(self.observer_a._state, 7)

    def test0430OtherExceptionsKeepTheObserver(self):
      class Broken(Observer):
        def update(self, subject, *topics): raise ValueError("broken")
      broken = Broken()
      self.subject.attach(broken)
      with self.assertLogs(observer.logger, level="ERROR"):
        self.subject.changeGeneric(8)
      self.assertTrue(any(o is broken for o, _ in self.subject._observers))
      self.assertEqual(self.observer_b._state, 8)
      
    def test0500Callback(self):
      testList:list[Any] = []
      code = self.subject.attachCallback(lambda topic, args: [testList.append(topic), testList.append(args)]) # type: ignore[func-returns-value]
      self.subject.changetopics(("topicC", 12))
      print(f'testList={testList}')
      self.assertEqual(len(testList), 2)

    def test0510CallbackTopics(self):
      got:list[tuple[str, Any]] = []
      self.subject.attachCallback(lambda topic, args: got.append((topic, args)), "topicA", "topicC")
      self.subject.changetopics(("topicC", 3), ("topicB", 2), ("topicA", 1))
      self.assertEqual(got, [("topicC", 3), ("topicA", 1)])

    def test0520RaisingCallbackRemoved(self):
      def bad(topic, args): raise ValueError("bad")
      code = self.subject.attachCallback(bad)
      with self.assertLogs(observer.logger, level="ERROR"):
        self.subject.changetopics(("topicC", 1))
      self.assertFalse(any(c[2] == code for c in self.subject._callbacks))

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main() 