'''
.. inheritance-diagram:: PlistSerializationStrategy
    :parts: 3
    :private-bases:
    :top-classes: object

Serialization to Apple's property list (plist) format, in its XML form.

A plist can hold dicts (with string keys), arrays, strings, integers, reals
and booleans -- exactly the structure :py:class:`JSONSerializationStrategy
<util.persistence.serializeJSON.JSONSerializationStrategy>` builds -- so this
strategy reuses that encoding wholesale and only replaces the final step:
the structure is written and read with :py:mod:`plistlib` instead of
:py:mod:`json`. Everything the JSON strategy supports, including
:py:class:`Serializable <util.persistence.serialize.Serializable>` classes,
works here too.

Plists can't hold *None* (the JSON strategy never produces one: *None* is
encoded as a tagged string), integers beyond 64 bits, or strings containing
characters XML forbids (eg: most control characters); :py:mod:`plistlib`
raises an exception for those.

Created on Sep 28, 2026

.. codeauthor:: Rob Kremer <robkremer@me.com>

'''
#################################################################################
# (c) Copyright 2026, Rob Kremer, MIT open source license.                      #
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
import plistlib
from typing import Any, override

from util.persistence.serializeJSON import JSONSerializationStrategy, JSONtypes


class PlistSerializationStrategy(JSONSerializationStrategy):
  '''
  Reads and writes Apple XML property lists, using the JSON strategy's
  encoding of objects (see the module documentation).
  '''

  @override
  @classmethod
  def defaultExtension(self)->str:
    '''
    :returns:
    :rtype: str
    '''
    return ".plist"

  @override
  @classmethod
  def sniff(cls, start:bytes) -> int:
    ":returns: 2 for a property list (XML or binary)."
    return 2 if b"<!DOCTYPE plist" in start[:300] or start.startswith(b"bplist") else 0

  @override
  @classmethod
  def protocolName(self)->str:
    '''
    :returns:
    :rtype: str
    '''
    return "Plist"

  @override
  @classmethod
  def protocolVersion(self)->str:
    '''
    :returns:
    :rtype: str
    '''
    return "1.0"

  @override
  def _tostring(self, elem:JSONtypes, kwargs:dict[str,Any])->str:
    '''
    :param kwargs: "sort_keys" (default False, so dicts keep their order, as
      in the other formats) is passed on to :py:func:`plistlib.dumps`.
    :param elem:
    :type elem: JSONtypes
    :returns:
    :rtype: str
    '''
    try:
      return plistlib.dumps(elem, fmt=plistlib.FMT_XML, sort_keys=bool(kwargs.get("sort_keys", False))).decode("utf-8")
    except (TypeError, ValueError, OverflowError) as ex:
      raise TypeError(f'Cannot represent this object as a plist: {ex}') from ex

  @override
  def _fromstring(self, string:str, kwargs:dict[str,Any])->JSONtypes:
    '''
    :param string:
    :type string: str
    :param kwargs:
    :type kwargs: dict[str, Any]
    :returns:
    :rtype: JSONtypes
    '''
    return plistlib.loads(string.encode("utf-8"), fmt=plistlib.FMT_XML)
