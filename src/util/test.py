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
Created on Apr 10, 2026

@author: robkremer
'''

import typing
from typing import Iterable, Any

class strdict(dict):
  def __init__(self, vals:Iterable[tuple[str, Any]]):
    '''
    :param vals:
    :type vals: Iterable[tuple[str, Any]]
    '''
    for k,_ in vals:
      if not isinstance(k, str):
        raise KeyError(f'strdict is restricted to keys of type str only; got key {k} or type {type(k)}.')
    super().__init__(vals)
  
  def __setitem__(self, key, value)->None:
    '''
    :param key:
    :type key:
    :param value:
    :type value:
    '''
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
