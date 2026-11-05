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
Subject's notifications: an observer (or callback) that detaches itself while
it's told doesn't make the next one miss out.
'''
import unittest
from util.observer import Subject, Observer

class Watcher(Observer):
  def __init__(self, name:str, heard:dict, detachSelf:bool=False):
    self.name, self.heard, self.detachSelf = name, heard, detachSelf
  def update(self, subject, *topics):
    self.heard[self.name] = self.heard.get(self.name, 0) + 1
    if self.detachSelf:
      subject.detach(self)

class Test(unittest.TestCase):

  def test_selfDetachingObserver(self):
    s = Subject()
    heard:dict = {}
    for w in (Watcher("a", heard, detachSelf=True), Watcher("b", heard), Watcher("c", heard)):
      s.attach(w)
    s.notify(("ping", ()))
    self.assertEqual(heard, {"a": 1, "b": 1, "c": 1})
    s.notify(("ping", ()))
    self.assertEqual(heard, {"a": 1, "b": 2, "c": 2})

  def test_selfDetachingCallback(self):
    s = Subject()
    called:list = []
    codes:dict = {}
    def one(topic, info):
      called.append("one")
      s.detachCallback(codes["one"])
    codes["one"] = s.attachCallback(one)
    s.attachCallback(lambda topic, info: called.append("two"))
    s.notify(("ping", ()))
    self.assertEqual(called, ["one", "two"])
    s.notify(("ping", ()))
    self.assertEqual(called, ["one", "two", "two"])

if __name__ == "__main__":
  unittest.main()
