'''
Created on Apr 10, 2026

@author: robkremer
'''

import typing
from typing import Iterable, Any

class strdict(dict):
  def __init__(self, vals:Iterable[tuple[str, Any]]):
    for k,_ in vals:
      if not isinstance(k, str):
        raise KeyError(f'strdict is restricted to keys of type str only; got key {k} or type {type(k)}.')
    super().__init__(vals)
  
  def __setitem__(self, key, value)->None:
    if not isinstance(key, str):
      raise KeyError(f'strdict is restricted to keys of type str only; got key {key} or type {type(key)}.')
    super().__setitem__(key, value)

d = strdict([("x",1)])
try:
  e = strdict([(1,1)])
  print("oops")
except:
  pass
try:
  d[1] = 3
  print("oops2")
except:
  pass
