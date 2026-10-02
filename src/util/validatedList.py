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
*ValidatedList*: a list that checks every item put in it against a predicate,
and that's *Dirtyable* (see *util.dirtyable*).

Created on Jul 13, 2026

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''
import inspect
from typing import SupportsIndex, override
from util.dirtyable import Dirtyable

from collections.abc import Callable, Iterable


class ValidatedList[T](list[T], Dirtyable):
  """
  A list subclass that enforces a predicate on every item inserted.

  :param f: Predicate function; an item is rejected if ``f(item)`` is falsy.
  :type f: Callable[[T], bool]
  :param iterable: Initial items to populate the list with.
  :type iterable: Iterable[T]
  :raises ValueError: If any item (initial or later inserted) fails the predicate.
  """

  def __init__(self, f: Callable[[T], bool], iterable: Iterable[T] = ()) -> None:
    '''
    :param f:
    :type f: Callable[[T], bool]
    :param iterable:
    :type iterable: Iterable[T]
    '''
    Dirtyable.__init__(self)
    self._f: Callable[[T], bool] = f
    initial = list(iterable)
    for i in initial:
      self._check(i)
    self._checking:bool = True
    super().__init__(initial)
    
  def _check(self, i: T) -> None:
    """
    Validate a single item against the predicate.

    :param i: Item to validate.
    :type i: T
    :raises ValueError: If ``f(i)`` is falsy.
    """
    if not self._checking:
      return
    if not self._f(i):
      raise ValueError(f"Item {i!r} does not satisfy predicate:\n  {inspect.getsource(self._f)}")

  def checking(self, check:bool|None=None) -> bool:
    """
    Enable, Disable, or find the value of running the validation function on
    data entry.
    
    :param check: if None, merely return the checking status, otherwise set the
      checking status on (True) or off (False).
    :type check: bool|None
    :returns: True if entries are now being validated, False if not.
    :rtype: bool
    """
    if check is not None:
      self._checking = check
    return self._checking
    
  @override
  def append(self, i: T) -> None:
    """
    :param i: Item to append.
    :type i: T
    :raises ValueError: If ``f(i)`` is falsy.
    """
    self._check(i)
    super().append(i)
    self.setDirty()

  @override
  def extend(self, iterable: Iterable[T]) -> None:
    """
    :param iterable: Items to extend the list with.
    :type iterable: Iterable[T]
    :raises ValueError: If any item fails the predicate.
    """
    items = list(iterable)
    for i in items:
      self._check(i)
    super().extend(items)
    self.setDirty()

  @override
  def insert(self, index: SupportsIndex, i: T) -> None:
    """
    :param index: Position to insert at.
    :type index: int
    :param i: Item to insert.
    :type i: T
    :raises ValueError: If ``f(i)`` is falsy.
    """
    self._check(i)
    super().insert(index, i)
    self.setDirty()

  @override
  def __setitem__(self, index, value) -> None:  # noqa: ANN001
    """
    Handle both single-index and slice assignment.

    :param index: Index or slice to assign to.
    :param value: Value(s) to assign.
    :raises ValueError: If any assigned item fails the predicate.
    """
    if isinstance(index, slice):
      values = list(value)
      for v in values:
        self._check(v)
      super().__setitem__(index, values)
    else:
      self._check(value)
      super().__setitem__(index, value)
    self.setDirty()

  @override
  def __iadd__(self, other: list[T]) -> "ValidatedList[T]":
    """
    :param other: Items to append via ``+=``.
    :type other: Iterable[T]
    :returns: This list, mutated in place.
    :rtype: ValidatedList[T]
    :raises ValueError: If any item fails the predicate.
    """
    self.extend(other)
    self.setDirty()
    return self
  
  @override
  def __delitem__(self, key:SupportsIndex | slice)->None:
    '''
    :param key:
    :type key: SupportsIndex | slice
    '''
    super().__delitem__(key)
    self.setDirty()
    