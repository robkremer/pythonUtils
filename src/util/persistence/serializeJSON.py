'''
.. inheritance-diagram:: JSONSerializationStrategy
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
from types import NoneType
from typing import Any, override, Union
from json import loads, dumps

from util.persistence.serialize import SerializationStrategy, Serializable, \
  ATTR_TYPE, strdict, strdict_className
from util.utils import getFullyQualifiedClass
  

JSONtypes = Union[dict, list, int, float, bool, str]
TAG_ATTRIBUTES = "attrs"
TAG_ITEMS = "items"
VALUE_OBJECT = "object"

class JSONSerializationStrategy(SerializationStrategy):

  '''
  The *SerializationStrategy* for JSON files.
  '''
  @override
  @classmethod
  def defaultExtension(self)->str:
    '''
    :returns:
    :rtype: str
    '''
    return ".json"


  @override
  @classmethod
  def protocolName(self)->str:
    '''
    :returns:
    :rtype: str
    '''
    return "JSON"


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
    :param elem:
    :type elem: JSONtypes
    :param kwargs:
    :type kwargs: dict[str, Any]
    :returns:
    :rtype: str
    '''
    indent = kwargs.get("indent", 2)
    if type(indent) not in (int, str, NoneType): 
      raise TypeError(f'The "indent" argument to _tostring() should be an str or an int, bot {type(indent)}.')
    return dumps(elem, indent=indent)

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
    return loads(string)

  @override
  def _encodeStr(self, obj:str) -> JSONtypes:
    '''
    :param obj:
    :type obj: str
    :returns:
    :rtype: JSONtypes
    '''
    return obj

  @override
  def _decodeStr(self, elem:JSONtypes)->str:
    '''
    :param elem:
    :type elem: JSONtypes
    :returns:
    :rtype: str
    '''
    assert isinstance(elem, str)
    return elem

  @override
  def _encodeInt(self, obj:int) -> JSONtypes:
    '''
    :param obj:
    :type obj: int
    :returns:
    :rtype: JSONtypes
    '''
    return obj
    
  @override
  def _decodeInt(self, elem:JSONtypes) -> int:
    '''
    :param elem:
    :type elem: JSONtypes
    :returns:
    :rtype: int
    '''
    assert isinstance(elem, int)
    return elem
    
  @override
  def _encodeFloat(self, obj:float) -> JSONtypes:
    '''
    :param obj:
    :type obj: float
    :returns:
    :rtype: JSONtypes
    '''
    return obj
    
  @override
  def _decodeFloat(self, elem:JSONtypes) -> float:
    '''
    :param elem:
    :type elem: JSONtypes
    :returns:
    :rtype: float
    '''
    assert isinstance(elem, float)
    return elem
    
  @override
  def _encodeBool(self, obj:bool) -> JSONtypes:
    '''
    :param obj:
    :type obj: bool
    :returns:
    :rtype: JSONtypes
    '''
    return obj
    
  @override
  def _decodeBool(self, elem:JSONtypes) -> bool:
    '''
    :param elem:
    :type elem: JSONtypes
    :returns:
    :rtype: bool
    '''
    assert isinstance(elem, bool)
    return elem
    
  @override
  def _encodeList(self)->JSONtypes:
    '''
    :returns:
    :rtype: JSONtypes
    '''
    return {TAG_ATTRIBUTES: {ATTR_TYPE: "list"}, TAG_ITEMS: []}


  @override
  def _decodeList(self, elem:JSONtypes)->list[JSONtypes]:
    '''
    :param elem:
    :type elem: JSONtypes
    :returns:
    :rtype: list[JSONtypes]
    '''
    assert isinstance(elem, dict)
    return elem[TAG_ITEMS]

  def _encodeStrdict(self) -> JSONtypes:
    '''
    :returns:
    :rtype: JSONtypes
    '''
    return {TAG_ATTRIBUTES: {ATTR_TYPE: strdict_className}, TAG_ITEMS: dict()}
    
  def _decodeStrdict(self, elem:JSONtypes) -> dict[str,JSONtypes]:
    '''
    :param elem:
    :type elem: JSONtypes
    :returns:
    :rtype: dict[str, JSONtypes]
    '''
    assert type(elem) is dict
    return elem[TAG_ITEMS]
    
  @override
  def _setAttr(self, elem:JSONtypes, name:str, value:str)->None:
    '''
    :param elem:
    :type elem: JSONtypes
    :param name:
    :type name: str
    :param value:
    :type value: str
    '''
    if isinstance(elem, (int, float, bool, str)):
      assert name == ATTR_TYPE
    else:
      assert isinstance(elem, dict), f'Expected a dict, got a {type(elem)}'
      elem[TAG_ATTRIBUTES][name] = value

  @override
  def _getAttr(self, elem:JSONtypes, name:str, default:Any=KeyError)->Any:
    '''
    :param elem:
    :type elem: JSONtypes
    :param name:
    :type name: str
    :param default:
    :type default: Any
    :returns:
    :rtype: Any
    '''
    if isinstance(elem, (int, float, bool, str)) and name == ATTR_TYPE:
      return type(elem).__name__
    assert type(elem) is dict
    if name in elem[TAG_ATTRIBUTES]:
      return elem[TAG_ATTRIBUTES][name]
    if default == KeyError:
      raise KeyError(f'Attribute "{name}" not found.')
    return default

  @override
  def _setKVPair(self, elem:JSONtypes, key:JSONtypes, value:JSONtypes)->None:
    '''
    :param elem:
    :type elem: JSONtypes
    :param key:
    :type key: JSONtypes
    :param value:
    :type value: JSONtypes
    '''
    assert isinstance(elem, dict)
    typeName = elem[TAG_ATTRIBUTES][ATTR_TYPE]
    if typeName in ("dict"):#, strdict_className):
      pass
    else:
      typ = getFullyQualifiedClass(typeName)
      assert typ is not None
      assert issubclass(typ, (Serializable, strdict)), f'Expected "dict" or the name of a subtype of Serializable, got {typeName}.'
    if typeName == 'dict':
      elem[TAG_ITEMS].append(key)
      elem[TAG_ITEMS].append(value)
    else:
      assert isinstance(key, str)
      elem[TAG_ITEMS][key] = value

  @override
  def _getKVPairs(self, elem:JSONtypes)->list[tuple[JSONtypes, JSONtypes]]|dict[str,JSONtypes]:
    '''
    :param elem:
    :type elem: JSONtypes
    :returns:
    :rtype: list[tuple[JSONtypes, JSONtypes]] | dict[str, JSONtypes]
    '''
    assert isinstance(elem, dict)
    typeName = elem[TAG_ATTRIBUTES][ATTR_TYPE]
    if typeName == "dict":
      pass
    else:
      typ = getFullyQualifiedClass(typeName)
      assert typ is not None
      assert issubclass(typ, (Serializable, strdict)), f'Expected "dict" or the name of a subtype of Serializable, got {typeName}.'
    kvList = elem[TAG_ITEMS]
    if typeName == 'dict':
      assert len(kvList) % 2 == 0
      ret:list[tuple[JSONtypes, JSONtypes]] = []
      for i in range(0,len(kvList), 2):
        ret.append((kvList[i], kvList[i+1]))
      return ret
    else:
      return kvList

  @override
  def _appendItem(self, elem:JSONtypes, newItem:JSONtypes)->None:
    '''
    :param elem:
    :type elem: JSONtypes
    :param newItem:
    :type newItem: JSONtypes
    '''
    assert isinstance(elem, dict)
    assert elem[TAG_ATTRIBUTES][ATTR_TYPE] in ("list", "tuple", "set")
    elem[TAG_ITEMS].append(newItem)

  @override
  def _getItems(self, elem:JSONtypes)->list[JSONtypes]:
    '''
    :param elem:
    :type elem: JSONtypes
    :returns:
    :rtype: list[JSONtypes]
    '''
    assert isinstance(elem, dict)
    assert elem[TAG_ATTRIBUTES][ATTR_TYPE] in ("list", "tuple", "set")
    return elem[TAG_ITEMS]

  pass
  

    