'''
A more compact XML serialization: like :py:class:`XMLSerializationStrategy
<util.persistence.serializeXML.XMLSerializationStrategy>`, but a property whose
value is simple -- a bool, int, float, or a str of fewer than
*XML2SerializationStrategy.MAX_PACKED_STR* characters -- is written in one
tag::

  <property key="filetype" type="str" value=".xml" />

rather than::

  <property key="filetype">
    <object type="str" value=".xml" />
  </property>

A reference to an object written elsewhere in the file (a *_Reference*) is
packed too, as its id::

  <property key="db" ref="4453244544" />

Anything else (lists, dicts, other *Serializable* objects, long strings, None)
is written as before. It reads both forms, so it reads what
*XMLSerializationStrategy* writes; it always writes the short form.

.. inheritance-diagram:: XML2SerializationStrategy
    :parts: 3
    :private-bases:
    :top-classes: object
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
from typing import Any, override, Optional
from xml.etree.ElementTree import Element
from util.persistence import serialize
from util.persistence.serialize import ATTR_TYPE, TAG_KVPAIR, strdict_className
from util.persistence.serializeXML import XMLSerializationStrategy, TAG_OBJECT, ATTR_VALUE, TAG_KEY

class XML2SerializationStrategy(XMLSerializationStrategy):
  '''
  The compact XML strategy (see the module doc): the default strategy.
  '''

  preferred = True
  "Chosen over *XMLSerializationStrategy* for the \".xml\" extension (it reads both forms)."

  PACKED_TYPES = ("bool", "int", "float", "str")
  "The (type attribute values of the) simple types written packed into their property tag."

  MAX_PACKED_STR = 60
  "Strings at least this long are written in their own tag."

  ATTR_REF = "ref"
  "The attribute of a property tag holding the id of the object it refers to (see *_Reference*)."
  REF_ID = "referenceID"
  "The property of a *_Reference* holding the id."

  @override
  @classmethod
  def protocolName(cls) -> str:
    return "XML2"

  @override
  @classmethod
  def protocolVersion(self) -> str:
    return "1.0"

  @classmethod
  def _refID(cls, value:Element) -> Optional[str]:
    'If *value* (an encoded object) is a *_Reference*, its id (as text); else None.'
    if value.tag != TAG_OBJECT or value.attrib.get(ATTR_TYPE) != serialize.REF_CLASSNAME or len(value) != 1:
      return None
    prop = value[0]
    if prop.tag != TAG_KVPAIR or prop.attrib.get(TAG_KEY) != cls.REF_ID:
      return None
    idElem = cls._unpacked(prop)
    if idElem is None or idElem.attrib.get(ATTR_TYPE) != "int":
      return None
    return idElem.attrib.get(ATTR_VALUE)

  @classmethod
  def _packable(cls, value:Element) -> bool:
    'Whether *value* (an encoded object) is simple enough to pack into its property tag.'
    if value.tag != TAG_OBJECT or len(value) or set(value.attrib) != {ATTR_TYPE, ATTR_VALUE}:
      return False
    typ = value.attrib[ATTR_TYPE]
    return typ in cls.PACKED_TYPES and (typ != "str" or len(value.attrib[ATTR_VALUE]) < cls.MAX_PACKED_STR)

  @classmethod
  def _unpacked(cls, prop:Element) -> Optional[Element]:
    '''
    The value of property *prop*: its child, or, if it's packed, the object tag
    it stands for (made from its type and value, or its reference id).
    '''
    child = prop.find("*")
    if child is not None:
      return child
    if cls.ATTR_REF in prop.attrib:
      ref = Element(TAG_OBJECT, {ATTR_TYPE: serialize.REF_CLASSNAME}) # (not imported by name: serialize loads this module before defining it)
      ref.append(Element(TAG_KVPAIR, {TAG_KEY: cls.REF_ID, ATTR_TYPE: "int", ATTR_VALUE: prop.attrib[cls.ATTR_REF]}))
      return ref
    if ATTR_TYPE in prop.attrib:
      return Element(TAG_OBJECT, {ATTR_TYPE: prop.attrib[ATTR_TYPE], ATTR_VALUE: prop.attrib.get(ATTR_VALUE, "")})
    return None

  @override
  def _setKVPair(self, elem:Element, key:Element|str, value:Element) -> None:
    packs = isinstance(key, str) and elem.attrib[ATTR_TYPE] != 'dict'
    if packs and self._packable(value):
      elem.append(Element(TAG_KVPAIR, {TAG_KEY: key, ATTR_TYPE: value.attrib[ATTR_TYPE], ATTR_VALUE: value.attrib[ATTR_VALUE]}))
    elif packs and (ref := self._refID(value)) is not None:
      elem.append(Element(TAG_KVPAIR, {TAG_KEY: key, self.ATTR_REF: ref}))
    else:
      super()._setKVPair(elem, key, value)

  @override
  def _getKVPair(self, elem:Element, key:str) -> Optional[Element]:
    if elem.attrib[ATTR_TYPE] == 'dict':
      return super()._getKVPair(elem, key)
    prop = elem.find(f"./{TAG_KVPAIR}[@{TAG_KEY}='{key}']")
    return None if prop is None else self._unpacked(prop)

  @override
  def _getKVPairs(self, elem:Element) -> list[tuple[Element,Element]]|dict[str,Element]:
    if elem.attrib[ATTR_TYPE] == 'dict':
      return super()._getKVPairs(elem)
    ret:dict[str,Element] = {}
    for prop in elem.findall(TAG_KVPAIR):
      v = self._unpacked(prop)
      assert v is not None, f'property "{prop.attrib.get(TAG_KEY)}" has no value.'
      ret[prop.attrib[TAG_KEY]] = v
    return ret
