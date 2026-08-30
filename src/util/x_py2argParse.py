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
from typing import Any, Callable
'''
Created on May 14, 2026

.. codeauthor:: Rob Kremer <robkremer@me.com>

'''

import inspect
import argparse

def my_func(name: str, count: int = 5, verbose: bool = False):
  """Does something useful."""
  pass

def test():
  '''
  Output:
  
  name <class 'str'> <class 'inspect._empty'>
  count <class 'int'> 5
  verbose <class 'bool'> False
  From that you can derive:
  
  param.annotation → argparse type (e.g. int, str)
  param.default → whether the arg is required (inspect.Parameter.empty = no default = required)
  param.kind → positional vs keyword (POSITIONAL_OR_KEYWORD, VAR_POSITIONAL, KEYWORD_ONLY, etc.)
  inspect.getdoc(fn) → docstring for the parser description
  '''
  sig = inspect.signature(my_func)
  
  for paramName, param in sig.parameters.items():
    print(paramName, param.annotation, param.default)
  
def makeParserFromFunc(fn:Callable, predicate:Callable[[str], bool]=lambda paramName: True) -> argparse.ArgumentParser:
  '''
  :param fn: The function to make a parser for.
  :type fn: Callable
  :param predicate: A filter that, given the name of a parameter return True iff 
    the param SHOULD be used (if False the param is ignored).
  :type predciate: Callable[[str], bool]
  Limitations to be aware of:
  
  Complex annotations (list[int], Optional[str], unions) need extra handling
  *args / **kwargs don't map cleanly to argparse
  Bool detection via action='store_true' is a simplification — you might want --no-X flags too
  Docstring param descriptions (:param name:) need separate parsing (e.g. with docstring_parser) to wire up help= per argument
  But for straightforward typed functions it works well.
  '''
  parser = argparse.ArgumentParser(description=inspect.getdoc(fn))
  sig = inspect.signature(fn)

  for paramName, param in sig.parameters.items():
    if not predicate(paramName):
      continue
    annotation = param.annotation
    default = param.default
    hasDefault = default is not inspect.Parameter.empty

    kwargs:dict[str,Any] = {}

    if annotation is not inspect.Parameter.empty:
      if annotation is bool:
        kwargs['action'] = 'store_true'
      else:
        kwargs['type'] = annotation

    if hasDefault:
      kwargs['default'] = default
      kwargs['required'] = False
      flagName = f'--{paramName}'
    else:
      flagName = paramName  # positional

    parser.add_argument(flagName, **kwargs)

  return parser

    