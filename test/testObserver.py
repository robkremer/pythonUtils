'''
Created on Oct 15, 2024

@author: kremer
'''
import unittest
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
      
    def test0500Callback(self):
      testList:list[Any] = []
      code = self.subject.attachCallback(lambda topic, args: [testList.append(topic), testList.append(args)]) # type: ignore[func-returns-value]
      self.subject.changetopics(("topicC", 12))
      print(f'testList={testList}')
      self.assertEqual(len(testList), 2)

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main() 