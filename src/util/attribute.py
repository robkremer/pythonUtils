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
.. inheritance-diagram::
      RestrictionTypes
      Restriction
      Attribute
      AttributedObject
    :parts: 3
    :private-bases:
    :top-classes: util.commandParser.ParsableCommandDef, util.commandParser.ParsableQuery


1. Objects are either TYPES or INDIVIDUALS

  1. A TYPE T is identified by T->ISTYPE->Type, an INDIVIDUAL I is identified by I->ISINSTANCE->Type
  2. A TYPE T can be marked as ABSTRACT, meaning A->ISINSTANCE->T is disallowd (eg: ISINSTANCE<:ISA:>ISTYPE)
  
    1. A<-ISTYPE<-X->ISINSTANCE->B is illegal
    2. ISA: TOP->ISA->TOP, ISTYPE: [TYPE<:TOP]->(ISTYPE<:ISA)->[TYPE], ISINSTANCE: [IND<:TOP]->(ISINSTANCE<:ISA)->[TYPE] seems hopelessly circular if 1.1
     
TYPE-ATTRIBUtES' values can only be modified by TYPES (eg: fill-color) but the value is inherited by INDIVIDUALS

  Individual-attributes are only non-TYPE-ATTRIBUTES because TYPES are also individuals (eg: name) 

ROLE is an Attribute type that is covarient

non-ROLE Attribute types are invarient

Some VALUES are inherited (eg: color) and others are not (eg: name) 

Created on Oct 10, 2024

.. codeauthor:: Rob Kremer <robkremer@me.com>

------------
'''
from __future__ import annotations
from typing import Optional, override, Union, Any
from types import NoneType
import importlib
from enum import Flag
from dataclasses import dataclass
from abc import abstractmethod
from collections.abc import KeysView, ValuesView, ItemsView

from util.utils import getFullClassName, getFullyQualifiedClass, getClass,\
  getClassFromFullyQualifiedName
from util.observer import Subject
from util.persistence.serialize import Serializable, SerializableType, strdict,\
  InstantiationInfo, ParamInfo, PropertyInfo

class RestrictionTypes(Flag):
  UNRESTRICTED = 0
  NOINHERIT = 1
  NOOVERRIDE = 2
  ILLEGAL = 3
  
UNRESTRICTED = RestrictionTypes.UNRESTRICTED
NOINHERIT    = RestrictionTypes.NOINHERIT
NOOVERRIDE   = RestrictionTypes.NOOVERRIDE
ILLEGAL      = RestrictionTypes.ILLEGAL

@dataclass
class Restriction:
  global RESTRICTION_TYPES
  individual:Optional[RestrictionTypes]
  type:Optional[RestrictionTypes]
  @classmethod
  def fromstring(cls, name:str) -> Restriction:
    choices =[x for x in RESTRICTION_TYPES if x.startswith(name.upper())]
    if len(choices) > 1:
      if "VAR" in choices and len(choices)==2:
        choices = ["VAR_DEFAULTED"]
      elif "CONST" in choices and len(choices)==2:
        choices = ["CONST_TYPEOVERRIDE"]
      else:
        raise ValueError("Restriction string is not unique.")
    if len(choices) == 0:
      raise ValueError("Illegal restriction string.")
    return RESTRICTION_TYPES[choices[0]]
  def tostring(self) -> str:
    for k,v in RESTRICTION_TYPES.items():
      if self == v:
        return k
    return f'ILLEGAL: {self}'
  
VAR_DEFAULTED      = Restriction(UNRESTRICTED, UNRESTRICTED)
'Restriction: Normal variable with a default. Eg: "degree" field with default "None".'
VAR                = Restriction(NOINHERIT, UNRESTRICTED)
'Restriction: Normal variable, individuals must assign as value. Eg: name of an object.'
CONST_TYPEOVERRIDE = Restriction(NOOVERRIDE, UNRESTRICTED)
'Restriction: Constant that types can change.'
# ILLEGAL1           = Restriction(UNRESTRICTED, NOINHERIT)
# 'Illegal'
LOCAL              = Restriction(NOINHERIT, NOINHERIT)
'Restriction: Types must change but individuals can\'t. Eg: name of a relation.'
TYPENAME           = Restriction(NOOVERRIDE, NOINHERIT)
'Restriction: Types must change but individuals can\'t. Eg: name of a relation.'
# ILLEGAL2           = Restriction(UNRESTRICTED, NOOVERRIDE) 
# 'Illegal'
# ILLEGAL3           = Restriction(NOINHERIT, NOOVERRIDE) 
# 'Illegal'
CONST              = Restriction(NOOVERRIDE, NOOVERRIDE) 
'Restriction: Constant'

RESTRICTION_TYPES:dict[str,Restriction] = {
  "VAR": VAR,
  "VAR_DEFAULTED": VAR_DEFAULTED,
  "CONST": CONST,
  "CONST_TYPEOVERRIDE": CONST_TYPEOVERRIDE,
  "TYPENAME": TYPENAME,
  "LOCAL": LOCAL}    

class NoValue(Serializable): 
  '''
  A singleton null class (similar) to *None* that can be used in situations 
  where you'd want *None*, but *None* is a legitimate value. Any call to the
  constructor returns the one *NOVALUE* object.
  '''
  NOVALUE = None
  @classmethod
  def getInstantiationInfo(cls) -> InstantiationInfo:
    return InstantiationInfo(cls)
  def __new__(cls) -> "NoValue":
    if cls.NOVALUE is None:
      cls.NOVALUE = super().__new__(cls)
    return cls.NOVALUE
  def __repr__(self)->str:
    return "NOVALUE"
  
NOVALUE = NoValue()
  
AttributeValueTypes = type|str
  
TYPE_EQUIVALENTS:dict[str, AttributeValueTypes|None] = \
                   {"int": int, 
                    "float": float, 
                    "bool": bool, 
                    "str": str, 
                    "text": str, 
                    "mtext": str, 
                    "color": str, 
                    "colour": str, 
                    "list": list, 
                    "dict": dict,
                    "choices[": None,
                    }
KNOWN_TYPES = list(TYPE_EQUIVALENTS.keys())
KNOWN_STRING_TYPES = [k for k,v in TYPE_EQUIVALENTS.items() if v is str]

def isValidType(typ, value=None) -> bool:
  '''
  :param typ: a type spec with may be subtype to *Type* or a string describing a app-specific type.
  :param value: A value that is expected to be a legitimate instance the *typ*
  :return: True iff the type *typ* argument is a valid type specification and *value* is *None* or a valid instance of *typ*.
  
  A valid type is:
  
    - "choices[" <listOfStrings> "]"
    - a member of *KNOWN_STRING_TYPES* ("str", "text", "mtext", "color", "colour")
    - a member of *KNOWN_TYPES* ("int", "float", "bool", "str", "text", "mtext", "color", "colour", "choices", "list", "dict", "attrs")
    - a subclass of :class:`~util.persistence.Serializable` or it's fully-qualified string representation.
    
  '''
  if typ is None:
    return True

  ret = False
  t = "not a type"
    
  if isinstance(typ, type): 
    t = getFullClassName(typ) #typ.__name__
    if t in KNOWN_TYPES or issubclass(typ, Serializable):
      ret = True
  elif isinstance(typ, str):
    t = typ
    
  if t.startswith("choices[") and t.endswith("]"):
    ret = True
  elif t in KNOWN_STRING_TYPES:
    ret = True
  elif t in KNOWN_TYPES:
    ret = True
  else: # string repr of a Serializable class?
    cls = getFullyQualifiedClass(t)
    if cls is not None and issubclass(cls, Serializable):
      ret = True

    
  if not ret:
    return False
    
  if value is None or value is NOVALUE:
    return ret

  # test the string types
  if t in KNOWN_STRING_TYPES:
    return isinstance(value, str)
  if t.startswith('choices[') and t.endswith(']'):
    choices = typ[8:-1].split(",")
    for i in range(len(choices)):
      choices[i] = choices[i].strip()
    return isinstance(value, str) and value.strip() in choices

  # test against the given value
  try:
    cls = getClass(t)
    assert cls is not None
    if isinstance(value, cls):
      return True
  except:
    pass
  try:
    cls = getClassFromFullyQualifiedName(t)
    assert cls is not None
    if isinstance(value, cls):
      return True
  except:
    pass
  try:
    cls = getFullyQualifiedClass(t)
    assert cls is not None
    if isinstance(value, cls):
      return True
  except:
    pass
  try:
    #TODO: Use of eval() is dangerous...
    #if not isinstance(value, (str,NoneType)) and value == (literal_eval(str(value))):
    assert cls is not None
    clsPath = getFullClassName(cls)
    assert clsPath is not None
    path, name = clsPath.rsplit('.', 1)
    #locate(clsPath) # forces the class to be loaded if it's not already
    module = importlib.import_module(path)
    my_class = getattr(module, name)
    # if not isinstance(value, (str,NoneType)) and value == (eval(str(value), {name: my_class})):
    if not isinstance(value, (str,NoneType)) and isinstance(value, my_class):
      return True
  except Exception:
    return False
  return False
  
def typeAsString(t:AttributeValueTypes, throw:bool=False) -> AttributeValueTypes|None:
  '''
  Returns a either the string version of supported types or the
  the fully qualified class name of of any other types. If the non-supported
  type is in string form, it is converted to a type and back again to check
  it's validity, thus it could change from a mere type name to a fully qualified
  class name.
  '''
  if isinstance(t, str):
    if t in KNOWN_TYPES or t.startswith('choices'):
      return t
    cls = getFullyQualifiedClass(t)
    if cls is not None:
      return getFullClassName(cls)
  if isinstance(t, type):
    ret = getFullClassName(t)
    if ret is not None:
      return ret
  if throw:
    raise TypeError(f'typeAsString({str(t)}): Types must be of claass Type or a string in str in {str(KNOWN_TYPES)}')
  return None
  
def typeAsCanonical(t:AttributeValueTypes, throw:bool=False) -> AttributeValueTypes|None:
  '''
  Attempts to return the given type t as an actual class.  Note that a string may
  also be returned in the case of the few supported "types" that do not correspond 
  to actual classes, currently "mtext", "color", "colour", "choices".
  '''
  if isinstance(t, str):
    if t in TYPE_EQUIVALENTS:
      return TYPE_EQUIVALENTS[t]
    if t in KNOWN_TYPES:
      return t
    cls = getFullyQualifiedClass(t)
    if cls is not None:
      return cls
  if isinstance(t, type):
    return t
  if throw:
    raise TypeError(f'typeAsString({str(t)}): Types must be of claass Type or a string in str in {str(KNOWN_TYPES)}')
  return None
  

class Attribute(Serializable):
  def __init__(self, value:Union[SerializableType, NoValue], 
                     typ:Optional[AttributeValueTypes], 
                     restriction:Optional[Restriction|tuple[int,int]|tuple[RestrictionTypes,RestrictionTypes]],
                     note:str|None=None):
    assert value is NOVALUE or typ is None or isValidType(typ, value), f'Invalid Attribute type/value: {typ}/{value}.'
    self._value:Union[SerializableType, NoValue] = value
    self._type:Optional[AttributeValueTypes] = typ
    self._restriction:Optional[Restriction]
    if isinstance(restriction, tuple):
      self._restriction = Restriction(restriction[0] if isinstance(restriction[0], RestrictionTypes) else RestrictionTypes(restriction[0]), \
                                     restriction[1] if isinstance(restriction[1], RestrictionTypes) else RestrictionTypes(restriction[1]))
    else:
      assert isinstance(restriction, (Restriction,NoneType)), f'Expected Restriction or NoneType type, got {type(restriction)}:{rest}'
      self._restriction = restriction
    self.note = note
    self._dirty:bool = False
    
  @property
  def value(self) -> SerializableType|NoValue:
    return self._value

  @value.setter
  def value(self, value:SerializableType|NoValue):
    assert self.type is None or isValidType(self.type, value)
    if value != self._value:
      self.setDirty()
      self._value = value
  
  @property
  def type(self) -> AttributeValueTypes|None:
    return self._type

  @type.setter
  def type(self, value:AttributeValueTypes|None):
    if value != self._type:
      if isValidType(value, self.value):
        self.setDirty()
        self._type = value
      else:
        raise TypeError(f'New type "{value}" is incompatible with current value "{self.value}".')
  
  @property
  def restriction(self) -> Restriction|None:
    return self._restriction

  @restriction.setter
  def restriction(self, value:Restriction|None):
    if value != self._restriction:
      self.setDirty()
      self._restriction = value
  
  def setDirty(self, value:bool=True):
    '''
    An object is dirty if it has been modified and should probably be
    saved on exit.  This should be called from all methods that modify
    the state of this object.
    
    :param value: (default True) The value to set *dirty* to.
    :type value: bool
    '''
    self._dirty = value
    
  def isDirty(self) -> bool:
    '''
    Returns True iff the object has been modified and should probably
    be saved on exit. 
    '''
    return self._dirty
  
  def isComplete(self) -> bool: return self.value is not NOVALUE and \
                                       self.type is not None and \
                                       self.restriction is not None and \
                                       self.restriction.individual is not None and \
                                       self.restriction.type is not None
  
  @classmethod
  def getInstantiationInfo(cls) -> InstantiationInfo:
    def saveRest(r:Restriction) -> str:
      return f'{r.individual.name if r.individual is not None else "None"}:{r.type.name if r.type is not None else "None"}'
    def restoreRest(string:str) -> Restriction:
      i,t = string.split(":")
      return Restriction(RestrictionTypes[i] if i != "None" else None, RestrictionTypes[t] if t != "None" else None)
    def getType(name:str) -> type|str|None:
      if name == "None":
        return None
      else:
        ret = getFullyQualifiedClass(name)
        if ret is None:
          return name
        else:
          return ret
    return InstantiationInfo(
      cls,
      conArgs=[ParamInfo("value", None), \
               ParamInfo("type", str, \
                                 lambda slf: getFullClassName(slf.type) if slf.type is not None else "None", #type: ignore[attr-defined]
                                 getType), #type: ignore[arg-type]
               ParamInfo("restriction", str, \
                                        lambda slf: saveRest(slf.restriction) if slf.restriction is not None else "None",  #type: ignore[attr-defined]
                                        lambda restStr: restoreRest(restStr) if restStr != "None" else None) #type: ignore[arg-type]
              ])

  def __str__(self)->str:
    return f'Attribute({self.value}, {self._type}, {self.restriction}, {self.note})'
  
class AttributedObject(Serializable, strdict[Attribute], Subject):

  @override
  @classmethod
  def getInstantiationInfo(cls)->InstantiationInfo:
    return InstantiationInfo(cls,
                postconSetters=[PropertyInfo("attributes", strdict,
                                            lambda slf: strdict({k:dict.get(slf,k) for k in dict.keys(slf)}), #type: ignore[call-overload,arg-type,var-annotated]
                                            lambda slf, dic: [slf.update(dic), slf.setDirty(False)], #type: ignore[attr-defined,arg-type]
                                            unique=True)])

  def __init__(self):
    Subject.__init__(self)
    strdict.__init__(self)
    Serializable.__init__(self)
    self._dirty:bool = False

  def setDirty(self, value:bool=True) -> None:
    '''
    An object is dirty if it has been modified and should probably be
    saved on exit.  This should be called from all methods that modify
    the state of this object.
    
    If *value* is False, resets all the contained *Attributes* to False.
    
    :param value: (default True) The value to set *dirty* to.
    :type value: bool
    '''
    assert type(value) is bool
    if not value:
      obj:Attribute
      for obj in super().values():  # LOCAL attributes only -- an inherited Attribute belongs to (and is tracked dirty by) its owning super object, not this one
        if obj.isDirty():
          obj.setDirty(False)
    self._dirty = value

  def isDirty(self) -> bool:
    '''
    Returns True iff the object (or an of it's contained *Attributes*) have
    been modified and should probably be saved on exit.
    '''
    if self._dirty:
      return True
    obj:Attribute
    for obj in super().values():  # LOCAL attributes only -- see setDirty()
      if obj.isDirty():
        self._dirty = True
        return True
    return False
  
  # @override
  # def get(self, key:str, default:Any=NOVALUE) -> SerializableType | NoValue:
  #   '''
  #   Return the *value* of the attribute at the key. If it isn't found locally,
  #   search the inheritance lattice.
  #
  #   :param key: The key to access.
  #   :type key: str
  #   :param default: The value to return if *key* is not found. Default is *NoValue*.
  #   :type default: Any
  #   :returns: The value field of the *Attribute* object at *key* if found.
  #   :rtype: SerializeableType|NoValue
  #   '''
  #   attr = self.getAttr(key)
  #   if attr == None:
  #     return default
  #   return attr.value

  @override
  def get(self, key:str, default:Any=NOVALUE, storeDefault:Any=NOVALUE, storeType:AttributeValueTypes|None=None) -> SerializableType | NoValue:
    '''
    Return the *value* of the attribute at the key. If it isn't found locally,
    search the inheritance lattice.

    :param key: The index string to retrieve.
    :type key: str
    :param default: The value to return if index doesn't exist in the dictionary. Ignored
        if *storeDefault* is not *None.*
    :type default: Any
    :param storeDefault: Same as *default,* but the value is ALSO stored in the
        dictionary if the value is not *None.* Useful for applications like preferences.
        If *storeDefault* is present, *default* is ignored.
    :type storeDefault: Any
    :param storeType: Any legal *Attribute* value type. Saved as the type of *storeDefault*.
        Ignored if if key is found or *storeDefault* is *None*.
    :type storeType: AttributeValueTypes|None=None
    :return: 
          - if the key is found, the value (NOT the Attribute record) associated with the key, or
          - if *storeDefault* is specified, the value of *storeDefault*, or 
          - if *default* is specified, the value of *default*, or
          - *None*.
    '''
    attr = self.getAttr(key)
    if attr != None:
      return attr.value
    if storeDefault is NOVALUE:
      return default
    if storeType is None:
      storeType = type(storeDefault)
    self.setAttr(key, Attribute(value=storeDefault, typ=storeType, restriction=VAR_DEFAULTED))
    return storeDefault
    
  def getLocal(self, key:str, default:Any=NOVALUE) -> SerializableType | Any:
    '''
    Return the LOCAL (not inherited) *value* of the attribute at the key.
    
    :param key: The key to access.
    :type key: str
    :param default: The value to return if *key* is not found. Default is *NoValue*.
    :type default: Any
    :returns: The value field of the *Attribute* object at *key* if found.
    :rtype: SerializeableType|NoValue
    '''
    attr:Attribute = super().get(key, None)
    if attr is None:
      return default
    return attr.value if attr.value is not NOVALUE else default

  def getLocalAttr(self, key:str) -> Attribute | None:
    '''
    Return the LOCAL (not inherited) *Attribute* of the attribute at the key.
    
    :param key: The key to access.
    :type key: str
    :param default: The value to return if *key* is not found. Default is *NoValue*.
    :type default: Any
    :returns: The value field of the *Attribute* object at *key* if found.
    :rtype: Attribute
    '''
    return super().get(key, None)

  def getInh(self, key:str, default:Any=NOVALUE) -> SerializableType | Any:
    '''
    Return the INHERITED (not local) *value* of the attribute at the key.
    
    :param key: The key to access.
    :type key: str
    :param default: The value to return if *key* is not found. Default is *NoValue*.
    :type default: Any
    :returns: The value field of the *Attribute* object at *key* if found.
    :rtype: SerializeableType|NoValue
    '''
    attr:Attribute|None = self.getInhAttr(key)
    if attr is None:
      return default
    return attr.value if attr.value is not NOVALUE else default

  def getInhAttr(self, key:str) -> Attribute | None:
    '''
    Return the INHERITED (not local) *Attribute* of the attribute at the key.
    
    :param key: The key to access.
    :type key: str
    :param default: The value to return if *key* is not found. Default is *NoValue*.
    :type default: Any
    :returns: The value field of the *Attribute* object at *key* if found.
    :rtype: Attribute
    '''
    p:AttributedObject
    for p in self.getSupers():
      r:Attribute = p.getAttr(key)
      if r is not None:
        return r
    return None

  def getAttr(self, key:str) -> Attribute | None:
    '''
    Return the *Attribute* object at the key. If it isn't found locally,
    search the inheritance lattice.
    
    :param key: The key to access.
    :type key: str
    :returns: The *Attribute* object at *key* or *None* if it isn't found.
    :rtype: Attribute|None
    '''
    myAttr:Optional[Attribute] = super().get(key)
    if myAttr is None: # we only inherit
      ret = self._getSuperAttr(key)
      if ret is None:
        return None
      myRest:Optional[RestrictionTypes]
      myRest, override = self._getRestriction(self.isIndividual(), ret.restriction, None)#ret.restriction.individual if self.isIndividual() else ret.restriction.type
      value = ret.value if myRest is None or not (myRest & NOINHERIT) else NOVALUE
      return Attribute(value, ret.type, ret.restriction, ret.note)
    
    complete = myAttr.isComplete()
    if complete and myAttr.note is not None: # we only have local
      return Attribute(myAttr.value, myAttr.type, myAttr.restriction, myAttr.note)
    
    superAttr:Optional[Attribute] = self._getSuperAttr(key)
    if complete:
      return Attribute(myAttr.value, myAttr.type, myAttr.restriction, None if superAttr is None else superAttr.note)
    else:  
      note = myAttr.note if myAttr.note is not None else (None if superAttr is None else superAttr.note) 
      if not(superAttr is not None and superAttr.isComplete()):
        raise ValueError(f'Attribute "{key}": Inherited Attribute is not complete.')
      # type is invariant
      assert myAttr.type is None, f'Attribute "{key}": Type is invariant in read/write values, so type cannot be overridden.'
      typ = superAttr.type
      # restrictions
      myR = myAttr.restriction
      superR = superAttr.restriction
      assert superR is not None
      if myR is None:
        restriction = superR
      else:
        restriction = Restriction(superR.individual if myR.individual is None else myR.individual,
                                  superR.type       if myR.type       is None else myR.type)
      # value
      myRest, override = self._getRestriction(self.isIndividual(), superAttr.restriction, myAttr.restriction)#restriction.individual if self.isIndividual() else restriction.type
      if myRest is not None and (myRest & NOINHERIT):
        value = myAttr.value
      else:
        value = superAttr.value if myAttr.value is NOVALUE else myAttr.value
      return Attribute(value, typ, restriction, note) 

  @override
  def __getitem__(self, key:str) -> SerializableType:
    '''
    The override for the indici access method.
    
    :param key: The attribute name.
    :type key: str
    :returns: The value associated with *key*, which could be *NOVALUE* if the
      the key exists, but here is not value associated with it (ie: the value
      was not inherited via the *NOINHERIT* restriction.
    :rtype: SerializableType
    :raises KeyError: if the key doesn't exist.
    
    Calls *self.getAttr()* and returns the value it finds (if any)
    '''
    attr = self.getAttr(key)
    if attr is None:
      raise KeyError(key)
    val = attr.value
    # if isinstance(val, NoValue):
    #   raise KeyError(key)
    return val

  @override
  def __setitem__(self, key:str, value:SerializableType) -> None:
    '''
    :param key: The attribute name.
    :type key: str
    :param value: The value to record under *key*.
    :type value: SerializableType
    :raises: 
    
    Can do one of 3 things:
    
      - if there is already a local attribute, its value is updated
      - if there is no local attribute but there is a super attribute, create
        a value-only attribute and associate that with *key*.
      - if there is no local attribute and no super attribute, create a complete
        (default) local attribute.
        
    In all cases, this method will throw if the value does not pass validation
    checks.
    '''
    if isinstance(value, Attribute):
      self.setAttr(key, value)
      return 
    
    current = super().get(key)
    if current is None: # not local attribute, so we need to create one to hold this value
      superAttr = self._getSuperAttr(key)
      if superAttr is None: # create a complete default local attribute with the value
        attr = Attribute(value, type(value), Restriction(RestrictionTypes.UNRESTRICTED, RestrictionTypes.UNRESTRICTED))
        verb = "new"
      else: # there is a super attribute (and no local) so create a value-only one locally
        attr = Attribute(value, None, None)
        verb = "mod"
      self.setAttr(key, attr)
    else: # simply change the value of the local attribute
      current.value = value
      verb = 'mod'
    self.notify((f"{verb} attribute", (key, value)))
      
  @override
  def __delitem__(self, key:str)->None:
    super().__delitem__(key)
    self.notify(("del attribute", (key,)))

  def __iter__(self):
    '''
    Iterates over the union of this object's LOCAL and INHERITED attribute
    keys, each exactly once. (Order is otherwise unspecified — unlike a
    plain *dict*, this isn't insertion order.)
    '''
    keys:set = set(super().keys())
    s:AttributedObject
    for s in self.getSupers():
      keys.update(s)  # iterates s itself, i.e. s.__iter__() -- s's own local+inherited keys
    for k in keys:
      yield k

  def __len__(self) -> int:
    '''
    :returns: The number of distinct LOCAL + INHERITED attribute keys.
    :rtype: int

    Note this is *not* simply the number of items physically stored in this
    *dict* (that would ignore inheritance) -- it agrees with
    ``len(list(self))``, consistent with :py:meth:`__iter__`.
    '''
    return sum(1 for _ in self)

  def __contains__(self, key:str) -> bool:
    '''
    :param key: The attribute name to test.
    :type key: str
    :returns: *True* iff *key* has an effective value, local or inherited.
    :rtype: bool

    Overridden because *dict*'s native ``__contains__`` only tests locally
    stored keys, which would disagree with :py:meth:`__iter__`/
    :py:meth:`__getitem__` (both of which account for inheritance).
    '''
    return self.getAttr(key) is not None

  def keys(self) -> KeysView:
    '''
    :returns: A live, set-algebra-capable :py:class:`~collections.abc.KeysView`
      over this object's LOCAL and INHERITED attribute keys.
    :rtype: KeysView

    Unlike plain *dict.keys()* (which reads the underlying storage directly
    and so would silently ignore inheritance), this is backed by
    :py:meth:`__iter__`/:py:meth:`__contains__`/:py:meth:`__len__`, so it
    stays consistent with ``iter(self)``, ``key in self`` and ``len(self)``.
    As with a real *dict.keys()*, the view is *live*: it reflects later
    changes to this object (or its supers) rather than being a frozen
    snapshot, and supports set operations (``&``, ``|``, ``-``, ``^``)
    against other key sets/views.
    '''
    return KeysView(self)

  def values(self) -> ValuesView:
    '''
    :returns: A live :py:class:`~collections.abc.ValuesView` over this
      object's LOCAL and INHERITED attribute values -- each one fully
      resolved through the inheritance lattice (i.e. via
      :py:meth:`__getitem__`/:py:meth:`getAttr`, not the raw stored
      *Attribute* record).
    :rtype: ValuesView
    '''
    return ValuesView(self)

  def items(self) -> ItemsView:
    '''
    :returns: A live :py:class:`~collections.abc.ItemsView` of
      ``(key, value)`` pairs, *value* fully resolved through inheritance
      (as with :py:meth:`values`).
    :rtype: ItemsView
    '''
    return ItemsView(self)

  def setAttr(self, key:str, attr:Attribute) -> Attribute:
    '''
    :param key: The attribute name.
    :type key: str
    :param attr: The candate attribute to associate with *key*.
    :type attr: Attribute
    :returns: The parameter *attr*
    :rtype: Attribute
    :raises:
    
    Set a local attribute if it passes validation rules. Throws if the rules 
    are violated. 
    '''
    self._validateOverride(key, self.isIndividual(), attr, self._getSuperAttr(key)) # will throw if *attr* is not legal
    super().__setitem__(key, attr)
    self.setDirty()
    self.notify(("new attribute", (key, attr.value)))
    return attr
    
  @abstractmethod
  def getSupers[T:AttributedObject](self) -> list[T]:
    '''
    :returns: A list of all super types to this object in mro order.
    :rtype: list[AttributedObject]
    
    Concrete subclasses must override to return a list of super types to this object.
    '''
    raise NotImplementedError('AttributedObject.getSupers() not implemented.')
  
  @abstractmethod
  def isIndividual(self) -> bool:
    '''
    :returns: *True* iff this object is an individual.
    :rtype: bool
    
    Concrete subclasses must override to return *True* if this object is a
    **individual** or *False* if this obejct is a **type**.
    '''
    raise NotImplementedError('AttributedObject.getSupers() not implemented.')
  
  def isType(self) -> bool:
    '''
    :returns: *True* iff this object is a type.
    :rtype: bool
    '''
    return not self.isIndividual()
  
  def isValueEditable(self, key:str) -> bool:
    '''
    :param key: The key for which to check.
    :type key: str
    :returns: *True* iff the value for that key is editable.
    :rtype: bool
    '''
    #TODO: implement isValueEditable()
    return True

  def isTypeEditable(self, key:str) -> bool:
    '''
    :param key: The key for which to check.
    :type key: str
    :returns: *True* iff the type for that key is editable.
    :rtype: bool
    '''
    #TODO: implement isTypeEditable()
    return True

  def isQualifierEditable(self, key:str) -> bool:
    '''
    :param key: The key for which to check.
    :type key: str
    :returns: *True* iff the restrictions for that key is editable.
    :rtype: bool
    '''
    #TODO: implement isTypeEditable()
    return True

  @classmethod
  def _validateOverride(cls, key:str, isIndividual:bool, attr:Attribute, superAttr:Optional[Attribute]):
    '''
    :param key: The attribute name.
    :type key: str
    :param attr: The candate attribute to validate against the inherited attribute.
    :type attr: Attribute
    :raises ValueError: If the value is of the wrong type.
    :raises TypeError: If the type field is incorrect.
    :raises PermissionError: If the inheritance restrictions are incorrect.
    
    Validates the *attr* against the inherited attribute. If *attr* is not legal
    against the inherited attribute, an exception will be raised.
    '''
    #superAttr = self._getSuperAttr(key)
    # no super attribute
    if superAttr is None:
      if attr.isComplete():
        assert attr.type is not None
        if not isValidType(attr.type, attr.value): #isinstance(attr.value, attr.type):
          raise ValueError(f'key "{key}": Value of type {type(attr.value)} is not an instance of {attr.type}.')
        assert attr.restriction is not None
        if attr.restriction.individual == RestrictionTypes.ILLEGAL:
          raise PermissionError(f'key "{key}": Over restricted individual.')
        if attr.restriction.type == RestrictionTypes.ILLEGAL:
          raise PermissionError(f'key "{key}": Over restricted type.')
      else:
        raise ValueError(f'key "{key}": A new attribute must be complete.')
    
    else: # we have a superAttr
      # type
      assert superAttr.type is not None
      if attr.type is not None:
        raise TypeError(f'key "{key}": A subtype or instance may not override a type (read/write values are invariant).')
      
      # value
      if attr.value is not NOVALUE and not isValidType(attr.type, attr.value): #isinstance(attr.value, superAttr.type):
        raise ValueError(f'key "{key}": Value of type {type(attr.value)} is not an instance of {attr.type}.')
      
      # inheritance restrictions (themselves over inheritance)
      assert superAttr.restriction is not None
      if attr.restriction is not None:
        if superAttr.restriction.individual is not None \
              and attr.restriction.individual is not None:
          if (superAttr.restriction.individual | attr.restriction.individual) == RestrictionTypes.ILLEGAL:
            raise PermissionError(f'key "{key}": Bad individual inheritance restrictions {attr.restriction.individual} <: {superAttr.restriction.individual}.')
          if superAttr.restriction.individual.value > attr.restriction.individual.value:
            raise PermissionError(f'key "{key}": Bad individual inheritance restrictions {attr.restriction.individual} <: {superAttr.restriction.individual}.')
        if superAttr.restriction.type is not None \
              and attr.restriction.type is not None:
          if (superAttr.restriction.type | attr.restriction.type == RestrictionTypes.ILLEGAL):
            raise PermissionError(f'key "{key}": Bad type inheritance restrictions {attr.restriction.type} <: {superAttr.restriction.type}.')
          if superAttr.restriction.type.value > attr.restriction.type.value:
            raise PermissionError(f'key "{key}": Bad type inheritance restrictions {attr.restriction.type} <: {superAttr.restriction.type}.')
      
    # inheritance restrictions (enforcement)
    restriction, override = cls._getRestriction(isIndividual, 
                                       None if superAttr is None else superAttr.restriction, 
                                       attr.restriction)
    if override and restriction & RestrictionTypes.NOOVERRIDE and attr.value is not NOVALUE:
      raise PermissionError(f'key "{key}": Cannot override value on NOOVERIDE field.')
    if restriction & RestrictionTypes.NOINHERIT and attr.value is NOVALUE:
      raise PermissionError(f'key "{key}": Value required on NOINHERIT field.')
  
  @classmethod  
  def _getRestriction(cls, 
                      isIndividual:bool, 
                      superRestriction:Optional[Restriction], 
                      thisRestriction:Optional[Restriction]) \
                        -> tuple[RestrictionTypes, bool]:
    '''
    Resolve the actual restriction on the object with respect to it being an
    individual/type and its inheritance. 
    
    :param isIndividual:
    :type isIndividual: bool
    :param superRestriction:
    :type superRestriction: Optional[Restriction]
    :param thisRestriction: 
    :type thisRestriction: Optional[Restriction]
    :returns: A *typle* pair of the :py:class:`RestrictionTypes` and a bool 
      indicating whether of not it is an override (True) or original (False).
    :rtype: tuple[RestrictionTypes, bool]
    '''
    assert not (superRestriction is None and thisRestriction is None) 
    if isIndividual:
      superRes = None if superRestriction is None else superRestriction.individual
      thisRes  = None if thisRestriction  is None else thisRestriction.individual
    else:
      superRes = None if superRestriction is None else superRestriction.type
      thisRes  = None if thisRestriction  is None else thisRestriction.type
    ret:RestrictionTypes  
    if superRes is None:
      assert thisRes is not None
      ret = thisRes
    elif thisRes is None:
      ret = superRes
    else:
      ret = superRes | thisRes
    return ret, superRes is not None
  
  def _getSuperAttr(self, key:str) -> Optional[Attribute]:
    '''
    :param key: The attribute name.
    :type key: str
    :param default: (default: *None*) The value returned if they items isn't found.
    :type default: *None*
    :returns: The *Attribute* object from the first parent it's found in
    :rtype: Optional[Attribute]
    '''
    s:AttributedObject
    for s in self.getSupers():
      a:Optional[Attribute] = s.getAttr(key)
      if a is not None:
        return a
    return None
        