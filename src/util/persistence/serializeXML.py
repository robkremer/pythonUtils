'''
.. inheritance-diagram:: XMLSerializationStrategy
    :parts: 3
    :private-bases:
    :top-classes: object


'''
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
from sys import intern
from typing import Any, override, Optional, cast
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element, ElementTree
from util.utils import getFullyQualifiedClass
from util.persistence.serialize import SerializationStrategy, Serializable, \
  ATTR_TYPE, TAG_KVPAIR, strdict_className

TAG_OBJECT = intern("object")
ATTR_VALUE = "value"
TAG_KEY = "key"
TAG_VALUE = "value"

class XMLSerializationStrategy(SerializationStrategy[Element]):
  
  SerializableTypesInAttrs = (int, float, bool, str)
  SerializableTypesInSubs = (Serializable, list, dict, tuple, set)

  @override
  @classmethod
  def protocolName(cls) -> str:
    return "XML"
    
  @override
  @classmethod
  def protocolVersion(self) -> str:
    return "1.0"
  
  @override
  @classmethod
  def defaultExtension(cls) -> str:
    return ".xml"

  @override
  def _encodeStr(self, obj:str) -> Element:
    return Element(TAG_OBJECT, {ATTR_TYPE: "str", 
                                ATTR_VALUE: obj})
    
  @override
  def _decodeStr(self, elem:Element) -> str:
    return elem.attrib[ATTR_VALUE]
    
  @override
  def _encodeList(self) -> Element:
      return Element(TAG_OBJECT, 
                     {ATTR_TYPE: "list"})
    
  @override
  def _decodeList(self, elem:Element) -> list[Element]:
    return elem.findall(f"./{TAG_OBJECT}")
    
  @override
  def _setAttr(self, elem:Element, name:str, value:str):
    elem.attrib[name] = value
  
  @override
  def _getAttr(self, elem:Element, name:str, default:Any=KeyError) -> Any:
    if name in elem.attrib:
      return elem.attrib[name]
    if default is KeyError:
      raise KeyError(f'No key "{name}" found.')
    else:
      return default
  
  @override
  def _appendItem(self, elem:Element, newItem:Element) -> None:
    assert elem.attrib[ATTR_TYPE] in ["list", "tuple", "set"], f'type must be one of "list", "tuple", "set", got "{elem.attrib["type"]}".'
    elem.append(newItem)
  
  @override
  def _getItems(self, elem:Element) -> list[Element]:
    assert elem.attrib[ATTR_TYPE] in ["list", "tuple", "set"]
    items:list[Element] = elem.findall('*')
    return items
    
  @override
  def _setKVPair(self, elem:Element, key:Element|str, value:Element) -> None:
    typ = elem.attrib[ATTR_TYPE]
    assert typ in ('dict', strdict_className) or issubclass(cast(type,getFullyQualifiedClass(typ)), Serializable)
    if typ == 'dict':
      assert isinstance(key, Element)
      prop = Element(TAG_KVPAIR)
      key.tag = TAG_KEY
      prop.append(key)
      value.tag = TAG_VALUE
      prop.append(value)
      elem.append(prop)
    else: # strdict and Serializable
      assert isinstance(key, str)
      prop = Element(TAG_KVPAIR, {TAG_KEY: key})
      prop.append(value)
      elem.append(prop)
  
  @override
  def _getKVPair(self, elem:Element, key:str) -> Optional[Element]:
    typ = elem.attrib[ATTR_TYPE]
    assert typ is not None
    cls = getFullyQualifiedClass(typ)
    assert cls is not None, f'Could not find class "{typ}".'
    assert typ in ('dict', strdict_className) or issubclass(cls, Serializable), f'method getKVPair() expected a dict or a Serializable, got {typ}'
    
    if cls is dict:
      prop = elem.find(f"./{TAG_KVPAIR}/{TAG_KEY}[@{ATTR_VALUE}='{key}']/..")
      if prop is None:
        return None
      ret = prop.find(f"./{TAG_VALUE}")
      return ret
    else: # strdict or Serializable
      prop = elem.find(f"./{TAG_KVPAIR}[@{TAG_KEY}='{key}']")
      if prop is None:
        return None
      ret = prop.find("*")
      return ret      
  
  @override
  def _getKVPairs(self, elem:Element) -> list[tuple[Element,Element]]|dict[str,Element]:
    typ = elem.attrib[ATTR_TYPE]
    assert typ is not None
    cls = getFullyQualifiedClass(typ)
    assert cls is not None
    assert typ in ('dict', strdict_className) or issubclass(cls, Serializable), f'method getKVPairs() expected a dict or a Serializable, got {typ}'

    subs:list[Element] = elem.findall(f'{TAG_KVPAIR}')
    
    if cls is dict:
      ret:list[tuple[Element, Element]] = []
      for s in subs:
        k = s.find(f"./{TAG_KEY}")
        v = s.find(f'./{TAG_VALUE}')
        assert k is not None
        assert v is not None
        ret.append((k,v))
      return ret
    else: # strdict or Serializable
      ret2:dict[str,Element] = dict()
      for s in subs:
        k2 = s.attrib[TAG_KEY]
        v = s.find('*')
        assert k2 is not None
        assert v is not None
        ret2[k2] = v
      return ret2
    
    
  
  def _tostring(self, elem:Element, kwargs:dict[str,Any]) -> str:
    """
    Return the data as a strategy-specific formatted string.
  
    :param elem: The *Element* to serialise and returned.
    :type elem: Element
    :param kwargs: Supports:
    
      - "indent":str|int|NoneType for "pretty print" indentation: A str is prefixed
        for every level, or an int indents that many spaces per level, or None
        will be a compace format.
        
    :type kwargs: dict[str,Any]
    :returns: The serialized object as a string.
    :rtype: str
    """
    # the indent param is a string to be passed to .indent(..., space=<indent> ) and is to be a string.
    # but let's also accept an integer like JSON does..
    indent = kwargs.get("indent", "  ")
    if indent is not None:
      itype = type(indent)
      if itype is int: 
        indent = " " * indent # type: ignore[operator] # mypy is confused here
      elif itype is not str:
        raise TypeError(f'The "indent" argument to _tostring() should be an str or an int, but got {itype}.')
    
    root:Element = elem
    tree:ElementTree = ElementTree(root)
    if indent is not None:
      ET.indent(tree, space=indent)
    xmlString:str = ET.tostring(
      cast(Element, tree.getroot()),
      encoding="unicode",
      xml_declaration=True,
      short_empty_elements=True,
    )
    return xmlString

  def _fromstring(self, string:str, kwargs:dict[str,Any]) -> Element:
    """
    Return an object made from a strategy-specific formatted string.
  
    :param string: The string to interpret.
    :type string: str
    :returns: The object interpreted from *string*.
    :rtype: SerializableTypes
    """
    root:Optional[Element] = ET.fromstring(string)
    if root is None:
      raise SyntaxError('Could not interpret given XML string.')
    assert isinstance(root, Element)

    return root

   