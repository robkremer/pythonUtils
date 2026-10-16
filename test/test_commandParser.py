#################################################################################
# (c) Copyright 2026, Rob Kremer,      MIT open source license.                 #
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
import unittest
from typing import Any
from util.commandParser import fixKwargs

class Model:
  def __init__(self, name:str):
    self.name = name
    self.objects = {"alice":"ALICE", "bob":"BOB"}

class GraphObject: pass

models = {"m": Model("m")}

def decodeModel(s:str) -> Model:
  return models[s] # KeyError on an unknown name

def decodeGraphObject(s:str, **kwargs) -> Any:
  model = kwargs.get("model")
  if not isinstance(model, Model):
    raise ValueError("no model")
  if s not in model.objects:
    raise KeyError(f'There\'s no object named "{s}"')
  return model.objects[s]

decoders = {"Model":decodeModel, "GraphObject":decodeGraphObject}

# (the GraphObject param comes before model, so it can't be decoded in signature order)
def connect(destination:GraphObject, model:Model, others:list[GraphObject]|None=None, label:str|GraphObject|None=None): pass
def query(names:list[str|GraphObject], model:Model): pass

def fix(fun, **kwargs):
  return fixKwargs(fun=fun, args=[], kwargs=kwargs, defaults={}, decoders=decoders)[1]

class TestFixKwargs(unittest.TestCase):
  def test_dependencyOrder(self):
    kw = fix(connect, destination="alice", model="m", others=["alice", "bob"], label="bob")
    self.assertIs(kw["model"], models["m"])
    self.assertEqual(kw["destination"], "ALICE")
    self.assertEqual(kw["others"], ["ALICE", "BOB"])
    self.assertEqual(kw["label"], "BOB")

  def test_badNameRaises(self):
    with self.assertRaises(ValueError) as cm:
      fix(connect, destination="nobody", model="m")
    self.assertEqual(str(cm.exception), 'destination: There\'s no object named "nobody"') # (positional: no default)
    self.assertIsInstance(cm.exception.__cause__, KeyError)

  def test_badListElementRaises(self):
    with self.assertRaisesRegex(ValueError, '^--others: There\'s no object named "nobody"$'):
      fix(connect, destination="alice", model="m", others=["bob", "nobody"])

  def test_badModelRaises(self):
    with self.assertRaisesRegex(ValueError, "^model: x$"):
      fix(connect, destination="alice", model="x")

  def test_optionLabelled(self):
    def option(label:Model|None=None): pass
    def positional(label:Model|None=None, /): pass # (positional-only, even with a default)
    with self.assertRaisesRegex(ValueError, '^--label: '):
      fix(option, label="x")
    with self.assertRaisesRegex(ValueError, '^label: '):
      fix(positional, label="x")

  def test_strAllowedKeepsStr(self):
    kw = fix(connect, destination="alice", model="m", label="nobody")
    self.assertEqual(kw["label"], "nobody")
    kw = fix(query, names=["alice", "nobody"], model="m")
    self.assertEqual(kw["names"], ["alice", "nobody"])

  def test_noneAndDefaultsUntouched(self):
    kw = fixKwargs(fun=connect, args=[], kwargs=dict(destination="alice", model="m", others=None, label=None),
                   defaults={"label":"zed"}, decoders=decoders)[1]
    self.assertIsNone(kw["others"])
    self.assertEqual(kw["label"], "zed")

if __name__ == "__main__":
  unittest.main()
