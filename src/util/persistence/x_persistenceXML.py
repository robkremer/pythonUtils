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
from typing import Any, override, Optional, cast, Callable, Iterator, Generator
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element, ElementTree
from util.utils import getFullClassName, getClassFromFullyQualifiedName,\
  getFullyQualifiedClass
from util.persistence.serialize import SerializationStrategy, ParamInfo, PropertyInfo,\
  Serializable, InstantiationInfo, getInstantiationInfo, REF_CLASSNAME,\
  ATTR_TYPE, ATTR_NAME, TAG_PROPERTY
from pickle import NONE

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

    
  # @override
  # def _encodeSerializable(self, obj:Serializable, attrs:dict[str,SerializationStrategy.SerializableUnitTypes]=dict()) -> Element:
  #   elem = Element(TAG_OBJECT, 
  #                  {ATTR_TYPE: getFullClassName(type(obj))})
  #   info:InstantiationInfo = obj.getInstantiationInfo()
  #   for params in (info.conArgs, info.conKWArgs):
  #     for pinfo in params:
  #       e = self._encode_(pinfo.getter(obj))
  #       e.tag = TAG_PARAM
  #       e.attrib[ATTR_NAME] = pinfo.name
  #       assert issubclass(cast(type, getFullyQualifiedClass(e.attrib[ATTR_TYPE])), pinfo.typ) or e.attrib[ATTR_TYPE] == REF_CLASSNAME, f'{getFullClassName(pinfo.typ)} != {e.attrib[ATTR_TYPE]}'
  #       elem.append(e)
  #   for props in (info.postconSetters, info.finalSetters):
  #     for pinfo in props:
  #       e = self._encode_(pinfo.getter(obj))
  #       e.tag = TAG_PROPERTY
  #       e.attrib[ATTR_NAME] = pinfo.name
  #       assert issubclass(cast(type, getFullyQualifiedClass(e.attrib[ATTR_TYPE])), pinfo.typ) or e.attrib[ATTR_TYPE] == REF_CLASSNAME, f'{getFullClassName(pinfo.typ)} != {e.attrib[ATTR_TYPE]}'
  #       elem.append(e)
  #   return elem
  #
  # @override
  # def _decodeSerializable(self, elem:Element) -> Serializable:
  #
  #   def getSetters(desc:list[PropertyInfo]) -> list[tuple[str, Callable[[Serializable], None]]]: 
  #     ret:list[tuple[str, Callable[[Serializable], None]]] = []
  #     for p in desc:
  #       pinfo:PropertyInfo = p
  #       sub:Optional[Element] = elem.find(f"./{TAG_PROPERTY}[@{ATTR_NAME}='{pinfo.name}']")
  #       if sub is None:
  #         raise LookupError(f'Subelement property named "{pinfo.name}" not found in Element "{elem.tag}" of type {elem.attrib[ATTR_TYPE]}.')
  #       sub.tag = TAG_OBJECT
  #       assert issubclass(cast(type, getFullyQualifiedClass(sub.attrib[ATTR_TYPE])), pinfo.typ) or sub.attrib[ATTR_TYPE] == REF_CLASSNAME, f'{getFullClassName(pinfo.typ)} != {sub.attrib[ATTR_TYPE]}'
  #       ret.append((pinfo.name, \
  #                   lambda slf, method=pinfo.setter, # type: ignore[misc]
  #                     value=self._decode_(sub): 
  #                       method(slf, value))) 
  #     return ret
  #
  #   def getParams(desc:list[ParamInfo]) -> list[tuple[str, SerializableType]]: 
  #     ret:list[tuple[str, SerializableType]] = []
  #     for p in desc:
  #       pinfo:ParamInfo = p
  #       sub:Optional[Element] = elem.find(f"./{TAG_PARAM}[@{ATTR_NAME}='{pinfo.name}']")
  #       if sub is None:
  #         raise LookupError(f'Subelement parameter named "{pinfo.name}" not found in Element "{elem.tag}" of type {elem.attrib[ATTR_TYPE]}.')
  #       sub.tag = TAG_OBJECT
  #       #assert sub.attrib[ATTR_TYPE] == getFullClassName(pinfo.typ), f'{sub.attrib[ATTR_TYPE]} != {getFullClassName(pinfo.typ)}'
  #       assert issubclass(cast(type, getFullyQualifiedClass(sub.attrib[ATTR_TYPE])), pinfo.typ) or sub.attrib[ATTR_TYPE] == REF_CLASSNAME, f'{getFullClassName(pinfo.typ)} != {sub.attrib[ATTR_TYPE]}'
  #       ret.append((pinfo.name, \
  #                   self._decode_(sub)))
  #     return ret
  #
  #   assert elem.tag == TAG_OBJECT, f'Expecting element tag {TAG_OBJECT}, but got "{elem.tag}".'
  #   className = elem.attrib[ATTR_TYPE]
  #   cls = getClassFromFullyQualifiedName(className)
  #   if cls is None:
  #     raise TypeError(f'Could not find type "{className}"')
  #
  #   info:InstantiationInfo = getInstantiationInfo(className)
  #
  #
  #   params = getParams(info.conArgs)
  #   args:list = [x[1] for x in params] # convert from (name,setter) pairs to list of setters
  #   params = getParams(info.conKWArgs)
  #   kwargs:dict[str,Any] = dict(params) # convert from (name,setter) pairs to dict of {name:setter}
  #   ret = cls(*args, **kwargs) # call the constructor
  #   setters = getSetters(info.postconSetters)
  #   for _, meth in setters:
  #     meth(ret) 
  #   setters = getSetters(info.finalSetters)
  #   for _, meth in setters: 
  #     self.finalMethodsList.append(lambda slf=ret, method=meth : method(slf))
  #   return ret
    
  # @override
  # def _encodeInt(self, obj:int) -> Element:
  #   return Element(TAG_OBJECT, {ATTR_TYPE: "int", 
  #                               ATTR_VALUE: str(obj)})
  #
  # @override
  # def _decodeInt(self, elem:Element) -> int:
  #   return int(elem.attrib[ATTR_VALUE])
  #
  # @override
  # def _encodeFloat(self, obj:float) -> Element:
  #   return Element(TAG_OBJECT, {ATTR_TYPE: "float", 
  #                               ATTR_VALUE: str(obj)})
  #
  # @override
  # def _decodeFloat(self, elem:Element) -> float:
  #   return float(elem.attrib[ATTR_VALUE])
  #  
  # @override
  # def _encodeBool(self, obj:bool) -> Element:
  #   return Element(TAG_OBJECT, {ATTR_TYPE: "bool", 
  #                               ATTR_VALUE: str(obj)})
  #
  # @override
  # def _decodeBool(self, elem:Element) -> bool:
  #   s = elem.attrib[ATTR_VALUE]
  #   return s != "False"
    
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
    
  # @override
  # def _encodeTuple(self, obj:tuple) -> Element:
  #   elem:Element = self._encodeList(list(obj))
  #   elem.attrib[ATTR_TYPE] = "tuple"
  #   return elem
  #
  # @override
  # def _decodeTuple(self, elem:Element) -> tuple:
  #   lst = self._decodeList(elem)
  #   return tuple(lst)
  #
  # @override
  # def _encodeSet(self, obj:set) -> Element:
  #   elem:Element = self._encodeList(list(obj))
  #   elem.attrib[ATTR_TYPE] = "set"
  #   return elem
  #
  # @override
  # def _decodeSet(self, elem:Element) -> set:
  #   lst = self._decodeList(elem)
  #   return set(lst)
  #  
  # @override
  # def _encodeDict(self, obj:dict) -> Element:
  #   elem = Element(TAG_OBJECT, 
  #                  {ATTR_TYPE: obj.__class__.__name__})
  #   for k,v in obj.items():
  #     elem.append(self._encode_(k))
  #     elem.append(self._encode_(v))
  #   return elem
  #
  # @override
  # def _decodeDict(self, elem:Element) -> dict:
  #   items = elem.findall(f".{TAG_OBJECT}")
  #   if len(items) % 2 != 0:
  #     raise ValueError(f"List must have an even number of elements, got {len(items)}.")
  #   objs = [self._decode_(e) for e in items] # convert the elements in items to Python values
  #   return {objs[i]: objs[i + 1] for i in range(0, len(objs), 2)} #change pair-list to a dict
    
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
  def _setKVPair(self, elem:Element, key:Element, value:Element) -> None:
    typ = elem.attrib[ATTR_TYPE]
    assert typ == 'dict' or issubclass(cast(type,getFullyQualifiedClass(typ)), Serializable)
    prop = Element(TAG_PROPERTY)
    key.tag = TAG_KEY
    prop.append(key)
    value.tag = TAG_VALUE
    prop.append(value)
    elem.append(prop)
  
  @override
  def _getKVPair(self, elem:Element, key:str) -> Optional[Element]:
    typ = elem.attrib[ATTR_TYPE]
    assert typ is not None
    cls = getFullyQualifiedClass(typ)
    assert cls is not None, f'Could not find class "{typ}".'
    assert typ == 'dict' or issubclass(cls, Serializable), f'method +getKVPair() expected a dict or a Serializable, got {typ}'
    
    prop = elem.find(f"./{TAG_PROPERTY}/{TAG_KEY}[@{ATTR_VALUE}='{key}']/..")
    if prop is None:
      return None
    ret = prop.find(f"./{TAG_VALUE}")
    return ret
  
  @override
  def _getKVPairs(self, elem:Element) -> list[tuple[Element,Element]]:
    typ = elem.attrib[ATTR_TYPE]
    assert typ is not None
    cls = getFullyQualifiedClass(typ)
    assert cls is not None
    assert typ == 'dict' or issubclass(cls, Serializable)
    subs:list[Element] = elem.findall(f'{TAG_PROPERTY}')
    ret:list[tuple[Element, Element]] = []
    for s in subs:
      pair = s.findall('*')
      k = s.find(f"./{TAG_KEY}")
      v = s.find(f'./{TAG_VALUE}')
      assert k is not None
      assert v is not None
      ret.append((k,v))
    return ret
    
  
  def _tostring(self, obj:SerializableType, kwargs:dict[str,Any]) -> str:
    """
    Return the data as a strategy-specific formatted string.
  
    :param obj: The object to serialise and returned.
    :type obj: SerializableTypes
    :returns: The serialized object as a string.
    :rtype: str
    """
    indent = kwargs.get("indent", None)

    root:Element = self._encode_(obj)
    tree:ElementTree = ElementTree(root)
    ET.indent(tree)
    xmlString:str = ET.tostring(
      cast(Element, tree.getroot()),
      encoding="unicode",
      xml_declaration=True,
      short_empty_elements=True,
    )
    return xmlString

  def _fromstring(self, string:str, kwargs:dict[str,Any]) -> SerializableType:
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

    ret = self._decode_(root)
    
    return ret

   