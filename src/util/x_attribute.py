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
      AttributeFlags
      AttributeData
      Attribute
      AttributedObject
      HierarchicalAttributedObject
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

#TODO: make Attribute.typ also allow an object of type *GraphObject* such that it is treated as a type constraint as well.


from __future__ import annotations
from typing import Optional, Type, Any, Self, override, NoReturn, Tuple, List,\
  Dict, Union, Iterator, MutableMapping, Iterable
from types import NoneType
from abc import abstractmethod, ABC
import weakref
import importlib
import xml.etree.ElementTree as ET
import logging
from util.observer import Subject, Observer
from util.utils import getFullyQualifiedClass, getClassFromFullyQualifiedName, ExtendedFlag,\
  getFullClassName, getClass, xmlEscape
from util.persistence.persistence import Serializable

logger = logging.getLogger(__name__)

#KNOWN_TYPES = ["int", "float", "bool", "str", "text", "mtext", "color", "colour", "choices", "list", "dict"]
#KNOWN_STRING_TYPES = ["str", "text", "mtext", "color", "colour"]
TYPE_EQUIVALENTS = {"int": int, 
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
    
  if isinstance(typ, Type): # type: ignore[arg-type]
    t = getFullClassName(typ)
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
    
  if value is None:
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
    if isinstance(value, cls):
      return True
  except:
    pass
  try:
    cls = getClassFromFullyQualifiedName(t)
    if isinstance(value, cls):
      return True
  except:
    pass
  try:
    cls = getFullyQualifiedClass(t)
    if isinstance(value, cls):
      return True
  except:
    pass
  try:
    #TODO: Use of eval() is dangerous...
    #if not isinstance(value, (str,NoneType)) and value == (literal_eval(str(value))):
    clsPath = getFullClassName(cls)
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
  
def typeAsString(t:Union[Type,str], throw:bool=False) -> Type:
  '''
  Returns a either the string version of supported types or the
  the fully qualified class name of of any other types. If the non-supported
  type is in string form, it is converted to a type and back again to check
  it's validity, thus it could change from a mere type name to a fully qualifiered
  class name.
  '''
  if isinstance(t, str):
    if t in KNOWN_TYPES or t.startswith('choices'):
      return t
    cls = getFullyQualifiedClass(t)
    if cls is not None:
      return getFullClassName(cls)
  if isinstance(t, Type):
    ret = getFullClassName(t)
    if ret is not None:
      return ret
  if throw:
    raise TypeError(f'typeAsString({str(t)}): Types must be of claass Type or a string in str in {str(KNOWN_TYPES)}')
  return None
  
def typeAsCanonical(t:Union[Type,str], throw:bool=False) -> Union[Type, str]:
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
  if isinstance(t, Type):
    return t
  if throw:
    raise TypeError(f'typeAsString({str(t)}): Types must be of claass Type or a string in str in {str(KNOWN_TYPES)}')
  return None
  
class AttributeFlags(ExtendedFlag):
  NIL                   = 0
  FINAL                 = 1
  "The attribute value cannot be overridden"
  INSTANCE_FINAL        = 2
  "The attribute value cannot be overridden by instances (eg: names of individual relations) (class variable)"
  VALUE_NOT_INHERITABLE = 4
  "[Incompatable with INSTANCE_FINAL] (eg: names of nodes)"
  
    
#TODO: should an attribute also have a defaultValue?
class AttributeData:
  '''
  Functions as a "read-only" (immutable) data structure, convenient as a return from 
  *HierarchicalAttributedObject.getInhAttibute()* which returns the 
  immutable composite of it's *Attribute* and the any inherited properties of
  that *Attribute*. 
  '''

  def __init__(self, name:str, typ:Optional[Type]=None, value:Optional[Any]=None, qualifiers:Optional[AttributeFlags]=AttributeFlags.NIL):
    '''
    :param name:
    :param typ:
    :param value:
    :param qualifiers:
    '''
    assert isinstance(name, str), f'value "{name}" type = {name.__class__.__name__} s/b of type str'
    assert isValidType(typ), f'typ "{typ}" type = {typ.__class__.__name__} s/b of a legal Attrubute type.'
    if not isValidType(typ, value):
      raise TypeError(f'value "{value}" type = {value.__class__.__name__} s/b of type {typeAsString(typ)}')
    assert qualifiers is None or isinstance(qualifiers, AttributeFlags), f'value "{qualifiers}" type = {qualifiers.__class__.__name__} s/b of type AttributeFlags'
    self._name:str = name
    self._typ:Type = typ 
    self._value:Optional[Any] = value
    self._qual:AttributeFlags = None if qualifiers is None else AttributeFlags(qualifiers)
    
  @property
  def name(self) -> str: 
    '''Must be the same as the container index.'''
    return self._name
    
  @property
  def typ(self) -> Optional[Type]: 
    '''
    The value is constrained to conform to this type.
    '''
    return self._typ
    
  @property
  def value(self) -> Any: 
    return self._value
  
  @property
  def qualifiers(self) -> AttributeFlags: 
    return self._qual
  
  ### QUALIFIER HELPERS #######################################################
    
  def isInstanceFinal(self) -> bool:
    '''
    :return: True iff this Attribute's components may only be altered by a
      subtype (but NOT an inheriting individual). 
    '''
    return self.qualifiers is not None and self.qualifiers & AttributeFlags.INSTANCE_FINAL == AttributeFlags.INSTANCE_FINAL
  
  def isFinal(self) -> bool: 
    '''
    :return: True iff this Attribute is Final, meaning none of the
      attribute's components may be altered in a subtype (type of individual).
    '''
    return self.qualifiers is not None and self.qualifiers & AttributeFlags.FINAL == AttributeFlags.FINAL
    
  def isValueNotInheritable(self) -> bool:
    '''
    :return: True iff this Attribute's value cannot be inherited by on individual
      (but a subtype DOES inherit).
    ''' 
    return self.qualifiers is not None and self.qualifiers & AttributeFlags.VALUE_NOT_INHERITABLE == AttributeFlags.VALUE_NOT_INHERITABLE

  def _repr(self):
    '''Internal method used by *__repr__* .'''
    return ""
  
  def __repr__(self):
    if   self._value is None:             value = 'None'
    elif isinstance(self.value, str):     value = f'"{self.value}"'
    else:                                 value = str(self.value)
    return f'{self.__class__.__name__}(name={self._name}, typ={self._typ.__name__ if isinstance(self._typ, type) else str(self._typ)}, value={value}, qualifiers={str(self.qualifiers)}{self._repr()})' 


###############################################################################
### CLASS ATTRIBUTE ###########################################################
###############################################################################

class Attribute(AttributeData, Serializable):
  '''
  An individual attribute containing it's name, type, qualifiers, and value (as
  well as a back pointer to its owner). Designed to be used as a member for 
  *AttributedObject* and *HierarchicalAttributedObject*. The idea, in the
  case of *HierarchicalAttributedObject* , being that Attributes **inherit** 
  from other attributes.
  '''
  covarientTypes = [] #TODO: figure this out

  def __init__(self, name:str, typ:Optional[Type]=None, value:Optional[Any]=None, qualifiers:Optional[AttributeFlags]=None):
    '''
    Creates an Attribute and adds itself to the *owner* *HierarchicalAttributedObject*

    :param owner: MUST be an *HierarchicalAttributedObject*.
    :param name:
    :param typ:
    :param value:
    :param qualifiers:
    
    '''
#    #Used as a TEMPORARY cache for the value of the super attribute when doing
#    #consistency checks. Should be used like this:
#    # "x = _setSuperAttr(); ... if x: self.superAttr = None".
#    self._superAttr:Tuple[Optional[AttributeData],bool] = (None, False)
    
    self._owner = None
    super().__init__(name, typ, value, qualifiers)
    
#    assert not self._superAttr[1], "the superAttr flag should be False"
    
  ### PUBLIC PROPERtiES #######################################################
  
  @property
  @override
  def typ(self) -> Type: #only needed so @typ.setter will work
    return super().typ

  @typ.setter  
  def typ(self, newTyp:Type):
    if newTyp == "None":
      newTyp = None
    if not isValidType(newTyp):
      raise TypeError(f'Attribute typ must be a type or know special type string, but got {newTyp.__name__ if isinstance(newTyp, type) else ("*"+str(newTyp)+"*")}')
    if self.value is not None and not isValidType(newTyp, self.value):
      raise TypeError(f'Attribute typ "{newTyp.__name__ if isinstance(newTyp, type) else str(newTyp)}" is inconsistent with value "{self.value}".')
    self._typ = newTyp
    if self.owner is not None:
      self.owner.dirty()
      #TODO: notify the owner through ChangeMgr
  @property
  @override
  def value(self) -> Any: #only needed so @value.setter will work
    return super().value
  
  @value.setter
  def value(self, value):
    '''
    :raises TypeError: if *value* is not of subtype of *self.typ*
    
    Sends a Subject->Object update() from *owner* if appropriate.
    '''
    if self._value == value: # don't bother if nothing will change
      return
    assert not isinstance(value, PRObject), f'Attriubute.value.setter(): Value is type {value.__class__.__name__} which is a PRObject; use a POReference instead.'
    if self.typ not in (None, NoneType) and not isValidType(self.typ, value):
      raise TypeError(f'Attribute.value(): value argument must conform to the type given in the typ argument ({self.typ.__name__ if isinstance(self.typ, type) else str(self._typ)}:{type(self._typ).__name__}), but value "{value}" is of type {value.__class__.__name__}')
    self._value = value
    if self.owner is not None:
      self.owner.dirty()
      with self.owner.ChangeMgr(self.owner) as cm:
        cm.registerTopics(("setattr", self.name, value))
    
  @property
  @override
  def qualifiers(self) -> AttributeFlags: #only needed so @qualifiers.setter will work
    return super().qualifiers
  
  @qualifiers.setter
  def qualifiers(self, newQuals:Union[int, AttributeFlags]):
    assert isinstance(newQuals, (int, AttributeFlags))
    if isinstance(newQuals, int):
      newQuals = AttributeFlags(newQuals)
    self._quals = newQuals
    if self.owner is not None:
      self.owner.dirty()
      #TODO: notify the owner through ChangeMgr
    
  @property
  def owner(self) -> Any: 
    ":return: HierarchicalAttributedObject"
    return self._owner() if self._owner is not None else None
  
  #TODO: do we need this? or is owner just read-only?
  @owner.setter 
  def owner(self, newOwner) -> AttributedObject:
    '''
    Setter for *owner*.
    '''
    if newOwner is self.owner:
      return
    if newOwner is None:
      self._owner = None
      return
    if not isinstance(newOwner, AttributedObject):
      raise TypeError(f'owners must be of type HierarchicalAttributedObject, but got type {newOwner.__class__.__name__}')
    #set my owner
    if self._owner is None or self._owner() is None:
      self._owner = weakref.ref(newOwner)
    else:
      raise NotImplementedError("Attribute re-ownering not implemented.") #TODO: implement Attribute re-ownering

  ### Serializable overrides **************************************************
  
  @override      
  @classmethod
  def getArgs(cls, elem: ET.Element) -> Tuple[List[Any], Dict[str, Any]]:
    """
    :param elem: The *ElementTree* element from which we are unserializing.
    :return: An (\\*args, \\*\\*kwargs) tuple for the constructor of the class 
      found in the element's name.
    :note: *owner* is not actually in the file (*elem*) as it is assumed the owner
      itself will set (*elem.set("owner", self)*) as a reference to itself in the *elem*
      parameter when it passes it to *Serializable.makeObject()*.
    """
    # def unserializeOther(buf:str) -> Any:
    #   ''
    #   tup = literal_eval(buf)
    #   assert isinstance(tup, Tuple), f'Expected a Tuple, got a type {tup.__class__.__name__}, value "{tup}".'
    #   assert len(tup) == 2
    #   typ = getClass(tup[0])
    #   try:
    #     return typ(tup[1])
    #   except: # maybe it's a case like dict...
    #     return literal_eval(tup[1])
      
    owner = elem.get("owner")
    
    # name
    name = elem.get("name")
    
    #type
    typ = None
    typStr = elem.get("type", None)
    if typStr is not None:
      typ = getFullyQualifiedClass(typStr)

    if typ is None and typStr is not None:
      typ = typStr
    typehint = elem.get("typehint", None)
      
    #quals
    quals = elem.get("qualifiers", None)
    if quals is not None:
      try:
        quals = AttributeFlags.fromStr(quals)
      except:
        pass
      
    context = owner.referenceContext()
    if isinstance(context, POReference):
      context = context()

    #value
    value = elem.get("value", None) # simple elements are (x=) attributes, but this may be omitted in favour of subelements
    if value is not None:
      if typ is int or typehint is not None and typehint=="int":
        value = int(value)
      elif typ is float or typehint is not None and typehint=="float":
        value = float(value)
      elif typ is bool or typehint is not None and typehint=="bool":
        value = bool(value)
    else: # indicates we are dealing with an appended subelement or list of appended subelements
      subs = elem.findall('*')
      if len(subs) > 1:
        raise Exception(f'Attriubte.getArgs(): Expected only a single subelement for key "{name}".')
      if len(subs) == 0:
        raise Exception(f'Attriubte.getArgs(): Expected one subelement for key "{name}".')
      subs[0].set("owner", owner) # pass this attribute containter as the owner of the created attribute
      value = Serializable.makeObject(subs[0], context=context)

    return [name, typ, value, quals], dict()

  @override
  def serializeXML(self) -> ET.Element:
    """
    Returns the representation of this object as an Element object.
    Implementors should call *super().serializeXML()* **first** as the top-level method
    will construct the Element itself.
    """
    inheritedType = self.owner.getType(self.name)
      
    context=self.owner.referenceContext()
    if isinstance(context, POReference):
      context = context()

    # name
    elem:ET.Element = Serializable.serializeXML(self)
    elem.set("name", self.name)
    
    # value
    # <nothing>:         if there value is None
    # value=<xmlString>: if value is a POReference
    #                    if value is int, float, str, 
    # subelement:        if value is a Serializable, or a list
    value = self._value
    if value is None:
      pass
    # long strings as subelements
    elif isinstance(value, str) and len(value) > 60:
      elem.append(Serializable.serializeAllXML(value, context=context))
    # simple values as "value=..."
    elif isinstance(value, (bool, int, float, str)) and type(value) == inheritedType:
        elem.set("value", xmlEscape(str(value)))
    # more complex values as subelements
    elif Serializable.isSerializable(value.__class__): # append
      assert not isinstance(value, PRObject), f'Attribute.serializeXML(): value type "{value.__class__.__name__}" is a PRObject type, use POReference instead.'
      elem.append(Serializable.serializeAllXML(value, context=context))
    else: # set as an attribute
      raise Exception(f'Attribute.serializeXML(): Don\'t know how to serialize value "{value}":{value.__class__.__name__}.')
    
    # typ
    # type=self.typ:         if self.typ declared
    # valueTime=type(value): if self.typ is None and there is a self.value
    # <nothing>:             if self.typ is None and self.value is None
    if self.typ   is not None: 
      elem.set("type", getFullClassName(self._typ) if isinstance(self._typ,type) else str(self._typ))
    elif value is not None:
      elem.set("typehint", value.__class__.__name__)
      
    # qualifiers
    if self._qual is not None and self.qualifiers != AttributeFlags.NIL: 
      elem.set("qualifiers", str(self._qual))
    
    return elem

  @override
  def unserializeXML(self, elem: ET.Element):
    """
    :param elem: The *ElementTree* element from which we are unserializing.
    """
    #super().unserializeXML(elem)
    #owner = ctypes.cast(int(elem.get("owner")), ctypes.py_object).value
    owner = elem.get("owner")
    self._owner = weakref.ref(owner)
    
    
  # ### OBSERVER OVERRIDES ######################################################
  #
  # @override
  # def update(self, subject:Subject, **topics)->None:
  #   super().update(self, subject, **topics)
  #   #TODO: implement Attribute.update()
  
  ### UTILITY #################################################################

  def makeAttributeDataCopy(self) -> AttributeData:
    '''
    :return: An "immutable" *AttributeData* version copy of this *Attribute* .
    '''
    return AttributeData(
      self._name, 
      self._typ,
      self._value, 
      self._qual
      )
    
  ### HOUSEKEEPING ############################################################
  
  def _repr(self):
    return f'{super()._repr()}, owner={str(self.owner)}'
  
  ### VALIDATORS ############################################################## 
  # Internal functions that raise Exceptions if the given hypothetical 
  # situation violates instantiation rules.
  
  @staticmethod
  def validateType(owner, name:str, typ:Type, superAttr:Optional[Self]=None) -> list[str]:
    """
    :param typ: a proposed typ for this attribute with *superAttr* as its superAttribute.
    :param superAttr: the matching attribute obtained by inheritance, or None if this the 
      highest-level declaration of this attribute.
    :raises AssertionError: if the *typ* is not valid.
    """
    ret:list[str] = []
    if typ is None and superAttr is not None:
      typ = superAttr.typ
    if not isValidType(typ):
      ret.append(f'attribute "{name}": Type specification must be a Type or an app-specific type-string, but got {("(type-string)"+type) if isinstance(typ,str) else ("Type"+type.__name__)}')
#TODO: put this code back when ISA is implemented.
#    if superAttr is None:
#      assert typ is not None, 'Base attribute types cannot be None'
#    assert superAttr.typ is not None, 'Base attribute types cannot be None'
#    if isinstance(typ,  tuple(Attribute.covarientTypes)):
#      assert typ is None or issubclass(typ, superAttr.typ), f'Special attributes are covarient with respect to thier supertype attribute type ({superAttr.typ.__name__}), but attempt to overload with type {type.__name__}' 
#    else:
#      assert typ is None or typ == superAttr.typ, f'Ordinary attributes are invarient with respect to thier supertype attribute type ({superAttr.typ.__name__}), but attempt to overload with type {type.__name__}'
    return ret

  @staticmethod
  def validateValue(owner, name:str, value:Any, typ:Optional[Type], superAttr:Optional[Self]=None) -> list[str]:
    """
    :param typ: a proposed typ for this attribute with *superAttr* as its superAttribute.
    :param superAttr: the matching attribute obtained by inheritance, or None if this the 
      highest-level declaration of this attribute.
    :raises AssertionError: if the *typ* is not valid.
    """
    assert isinstance(typ, (Type, str, NoneType)), f'Attribute.validateValue(): expected typ argument of Type, but got "{str(typ)}:{typ.__class__.__name__}".'
    T = typ if typ is not None or superAttr is None else superAttr.typ
    ret:list[str] = Attribute.validateType(owner, name, T, superAttr) # if this returns, then there must be a typ in either typ or superAttr.typ
    if len(ret) == 0:
      V = value if value is None or superAttr is None else superAttr.value
      if not isValidType(T, V):
        ret.append(f'attribute "{name}" value ("{str(value)}" of type {value.__class__.__name__}) must be of type {T.__name__}.')
    return ret
    
  @staticmethod
  def validateCheck(owner, name:str, typ:Type, value:Optional[Any], qualifiers:AttributeFlags, superAttr:Optional[Self]) -> list[str]:
    ret:list[str] = Attribute.validateType(owner, name, typ, superAttr)
    if len(ret) == 0:
      ret += Attribute.validateValue(owner, name, value, typ, superAttr)
    return ret
    
  def validate(self, superAttr:Optional[Self]=None) -> list[str]:
    '''
    :param superAttr: for :class:`HierarchicalAttributedObject` 
    '''
    ret = Attribute.validateCheck(self.owner, self.name, self.typ, self.value, self.qualifiers, superAttr)
    if len(ret) == 0:
      if isinstance(self.value, HierarchicalAttributedObject) and \
          isinstance(self.owner, AttributedObject) and \
          not isinstance(self.owner, HierarchicalAttributedObject):
        return [f'attribute "{self.name}": Cannot nest a HierarchicalAttributedObject in a non-HierarchicalAttributedObject.']
    return ret
    

###############################################################################
### CLASS HierarchicalAttributedObject ##########################################
###############################################################################

class AttributedObject(Subject, Serializable, MutableMapping):
  '''
  Implements a dict-like container of attributes where:
  
   - __getitem__() returns the value as if it were a simple str:Any dict
   - __setitem__() takes either an Attribute to add a new or updated *Attribute* OR
                  some other type to update the value in an *Attribute*
   - keys(), items(), values(): standard dict-like methods
   - __len__(), __contains__(): standard dict methods for len() and 'in'
  
  Other useful methods are:
  
   - setRecord() adds an Attribute to the container (can be called by __setitem__())
   - setAttribute() convenience method calling setRecord() 
   - getRecord() like __getitem__() but returns an entire Attribute object
   - {get|set}{Value|Type|Qualifiers}() standard getters and setters
   
   **Subject->Observer** updates are sent from the *AttributedObject* object
   when the Attribute.value() setter changes a value.
  '''
  
  def __init__(self):
    Subject.__init__(self)
    Observer.__init__(self)
    Serializable.__init__(self)
    self._attrs:dict[str, Attribute] = dict()
  
  ### DICT-LIKE METHODS #######################################################
  
  def __getitem__(self, key:str) -> Any:
    '''
    :param key: The index string to retrieve
    :return: The *value* (NOT the Attribute record) associated with *key*.
    '''
    return self.getValue(key)
    
  def get(self, key:str, default:Any=None, storeDefault:Any=None, storeType:Any=None) -> Any:
    '''
    :param key: The index string to retrieve
    :param default: The value to return if index doesn't exist dictionary. Ignored
        if *storeDefault* is not *None.*
    :param storeDefault: Same as *default,* but the value is ALSO stored in the
        dictionary if the value is not *None.* Useful for applications like preferences.
        If *storeDefault* is present, *default* is ignored.
    :param storeType: Any legal *Attribute* value type. Saved as the type of *storeDefault*.
        Ignored if if key is found or *storeDefault* is *None*.
    :return: 
          - if the key is found, the value (NOT the Attribute record) associated with the key, or
          - if *storeDefault* is specified, the value of *storeDefault*, or 
          - if *default* is specified, the value of *default*, or
          - *None*.
    '''
    if key in self.keys():
      return self[key]
    if storeDefault is not None:
      if storeType is None:
        storeType = type(storeDefault)
      self.setAttribute(key, value=storeDefault, typ=storeType)
      return storeDefault
    return default
    
  def __setitem__(self, key:str, value:Union[Attribute, Any]):
    '''
    :param key: the key for which to set.
    :param value: if the type of *value* is *Attribute* that full attribute for *key* is set,
            otherwise for any other type an attempt is made to set the value in the attribute.
    '''
    if isinstance(value, Attribute):
      if key == value.name:
        self.setRecord(value)
      else:
        raise AttributeError(f'Key "{key}" does not match Attribute name "{value.name}".')
    else:
      self.setValue(key, value)
    self.dirty()
    
  def __delitem__(self, name:str):
    if not isinstance(name, str): raise TypeError("AttributedObject.__delitem__(): 1st parameter but be of type str.")
    del self._attrs[name]
    
  def __len__(self):
    return len(self._attrs)
    
  def __iter__(self):
    return self._attrs.__iter__()

  ### REPR() and STR() #######################################################
  
  def __repr__(self) -> str:
    '''
    :return: A multi-line string listing the key/ *Attribute* pairs.
    '''
    ret = f'{self.__class__.__name__}:'
    for k, a in self._attrs.items(): #self.items(): # using self.items() runs the risk of infinite recursion in the subclass
      ret += f'\n  {k}: {repr(a)}'
    return ret
    
  def __str__(self)->str:
    '''
    :return: string listing the key/value pairs.
    '''
    return f'{self.__class__.__name__} {("at "+str(id(self))) if not hasattr(self, "name") else self.name}'
    
  ### GETTERS AND SETTERS #####################################################
  
  def getRecord(self, key:str, _loopDetection=[]) -> Union[Attribute, AttributeData]:
    '''
    :return: The record associated with *key* . Many be either *Attribute*,
        or *AttributeData* if the record is locked (eg: inherited data).
    :raises KeyError: If the key does not currently exist.
    
    Analogous to __get_item__(), but returns a *AttributeData* instead of the value
    '''
    return self._attrs[key]
    
  def setRecord(self, rec:Attribute) -> Attribute:
    '''
    Adds *rec*, possibly replacing a previous record with the same name.
    
    :raises TypeError: If *rec* is not an *Attribute* .
    '''
    if not isinstance(rec, Attribute): 
      raise TypeError(f'AttributedObject.setRecord() parameter requires an Attribute type, got type {rec.__class__.__name__}')
    rec.owner = self
    ver = rec.validate() 
    if len(ver) > 0:
      raise TypeError('AttributedObject.setRecord(): failed validation:\n  '+'\n  '.join(ver))
    else:
      self._attrs[rec.name] = rec
      with self.ChangeMgr(self) as cm:
        cm.registerTopics(("setattr", rec.name, rec.value))
      self.dirty()
    return rec
       
    
  def setAttribute(self, name:str, typ:Optional[Type]=None, value:Optional[Any]=None, 
                   qualifiers:Optional[AttributeFlags]=AttributeFlags.NIL) -> Attribute:
    '''
    Convenience method that creates an attribute and calls self.setRecord().
    '''
    attr = Attribute(name, typ, value, qualifiers)
    self.setRecord(attr)
    return attr
    
  def getValue(self, key:str, _loopDetection=[]) -> Any:
    '''
    :return: Either the value of the Attribute associated with *key* or raises and exception if there is no association.
    :raises KeyError: If the key does not currently exist.
    '''
    return self.getRecord(key, _loopDetection=_loopDetection).value
    
  def setValue(self, key:str, value:Any):
    '''
    :raises KeyError: If the key does not currently exist.
    :raises TypeError: If the value does not conform to the type restriction of the record

    Sets value in the record associated with *key*.
    '''
    rec:Attribute = self.getRecord(key) # can raise TypeError or KeyError
    ver = Attribute.validateValue(self, key, value, rec.typ) 
    if len(ver) > 0:
      raise TypeError('AttributedObject.setValue(): failed validation:\n  '+'\n  '.join(ver))
    else:
      with self.ChangeMgr(self) as cm:
        rec.value = value # can raise TypeError or KeyError
        cm.registerTopics(("setattr", key, value)) #needed because we don't call setRecord()
      self.dirty()
    
  def getType(self, key:str, asString:bool=False) -> Type:
    '''
    :param key: The key
    :param asString: if True, return the type as a *str* otherwise return as it's stored.
    :return: Either the type of the Attribute associated with *key* or raises and 
        exception if there is no association. The type will be returned as a *Type*
        if *asString* isn't in effect and there is a class type (like not "mtext", 
        "color", or "choices").
    :raises KeyError: If the key does not currently exist.
    '''
    ret = self.getRecord(key).typ
    if asString and isinstance(ret, Type):
      ret = getFullClassName(ret)
    else:
      if ret is str and ret in TYPE_EQUIVALENTS:
        ret = TYPE_EQUIVALENTS[ret]
    return ret
    
  def setType(self, key:str, typ:Type):
    '''
    :raises KeyError: If the key does not currently exist.
    :raises TypeError: If the type does not conform to the type restriction of the record

    Sets value in the record associated with *key*.
    '''
    ver = Attribute.validateType(self, key, typ) 
    if len(ver) > 0:
      raise TypeError('AttributedObject.setType(): failed validation:\n  '+'\n  '.join(ver))
    else:
      with self.ChangeMgr(self) as cm:
        self.getRecord(key).typ = typ # can raise TypeError or KeyError
        cm.registerTopics(("attribute type change", key, typ))
      self.dirty()
    
  def getQualifiers(self, key:str) -> AttributeFlags:
    '''
    :return: Either the qualifiers of the Attribute associated with *key* or raises and exception if there is no association.
    :raises KeyError: If the key does not currently exist.
    '''
    return self.getRecord(key).qualifiers
  
  def setQualifiers(self, key:str, flags:AttributeFlags):
    '''
    :raises KeyError: If the key does not currently exist.
    :raises TypeError: If the flags are inconsistent or otherwise wrongl

    Sets value in the record associated with *key*.
    '''
    with self.ChangeMgr(self) as cm:
      self.getRecrod(key).qualifiers = flags # can raise TypeError or KeyError
      cm.registerTopics(("attribute qualifier change", key, flags))
    self.dirty()
    
  def updateWith(self, updates:dict[str,Attribute]):
    with self.ChangeMgr(self): # serves to gather all the changes together
      for k,v in updates.items():
        if v is None: # A deletion
          del self._attrs[k]
        else: # a new Attribute or an update
          # self._attrs[k] = v
          # self._attrs[k].owner = self
          self[k] = v
          self._attrs[k].owner = self
    self.dirty()
      
  ### Obligations from Serializable ############################################
  
  @classmethod
  @override
  def getArgs(cls, elem: ET.Element) -> Tuple[List[Any], Dict[str, Any]]:
    """
    :param elem: The *ElementTree* element from which we are unserializing.
    :return: An (\\*args, \\*\\*kwargs) tuple for the constructor of the class 
      found in the element's name.
    """
    return [], dict()

  @override
  def serializeXML(self) -> ET.Element:
    """
    Returns the representation of this object as an Element object.
    Implementors should call *super().serializeXML()* **first** as this top-level method
    will construct the Element itself.
    """
    elem = ET.Element(getFullClassName(self.__class__))
    n = 0
    for v in self._attrs.values():
      n += 1
      if isinstance(v, Serializable):
        elem.append(v.serializeXML())
      elif isinstance(v, list):
        for v1 in v:
          elem.append(v1.serializeXML())
      else:
        raise TypeError(f'{self.__class__.__name__}.serializeXML(): Attribute type must be Attribute or list of Attribute; got type {v.__class__.__name__}')    
    return elem

  @override
  def unserializeXML(self, elem: ET.Element):
    """
    :param elem: The *ElementTree* element from which we are unserializing.
    """
    if elem is not None:
      attrs = elem.findall(getFullClassName(Attribute))
      for attrElem in attrs:
        #attrElem.set("owner", id(self))
        attrElem.set("owner", self)
        self._attrs[attrElem.get("name")] = Serializable.makeObject(attrElem)
        
  def isTypeEditable(self, key:str) -> bool:
    '''
    For a simple AttributedObject, the type is always editable.
    '''
    return True  
    
  def isValueEditable(self, key:str) -> bool:
    '''
    For a simple AttributedObject, the type is always editable.
    '''
    return True
    
  def isQualifierEditable(self, key:str, qual:AttributeFlags) -> bool:
    '''
    For a simple AttributedObject, the type is always editable.
    '''
    return True    
    
  @abstractmethod
  def dirty(self):
    pass
    
  def referenceContext(self):
    return None
  
  def validate(self) -> list[str]:
    '''
    :return: A *list[str]* of error messages for all the values in the container.
    '''
    ret:list[str] = []
    for attr in self.values():
      ret += attr.validate()
    return ret

###############################################################################
### CLASS HierarchicalAttributedObject ######################################
###############################################################################

class HierarchicalAttributedObject(AttributedObject, ABC):
  '''
  A container for *Attribute* objects, embodying the concept of attribute inheritance.
  '''
  
  def __init__(self):
    AttributedObject.__init__(self)
    
  ### ABSTRACT METHODS ########################################################

  @abstractmethod
  def getParents(self, _loopDetection=[]) -> Iterable[Self]:
    return []
    
  @abstractmethod
  def isIndividual(self) -> bool:
    return False
    
  @abstractmethod
  def referenceContext(self):
    raise Exception("HierarchicalAttributedObject.referernceContext() should be overridden to return a PRDb object.")

  ### DICT-LIKE METHODS #######################################################
  
  # def __getitem__(self, name:str) -> Optional[AttributeData]: 
  # defined in superclass; it works there because getValue() is overridden in this class

  @override
  def __setitem__(self, name:str, item:Union[Attribute,Any]):
    #TODO: Must insure that if this not overriding, that it's a COMPLETE Attribute (without any None's in it)
    if not isinstance(name, str): raise TypeError("HierarchicalAttributedObject.__setitem__(): 1st parameter but be of type str.")
    if isinstance(item, Attribute):
      self.setLocalRecord(name, item)
    else:
      self.setValue(name, item)
    self.dirty()
      
  #def __delitem__(self, name:str):
  # defined in superclass; it works there because del [] can only delete the local record.
    
  @override
  def keys(self) -> list[str]:
    ret:set = set(self._attrs.keys())
    for p in self.getParents():
      newkeys:set = set(p.keys())
      if not newkeys.issubset(ret):
        ret.update(newkeys)
    return list(ret)
  
  @override
  def items(self) -> Iterator[Tuple[str, Any]]:
    for k in self.keys():
      yield k, self[k]
  
  @override
  def values(self) -> Iterator[Any]:
    for k in self.keys():
      yield self[k]

  ### GETTERS AND SETTERS #####################################################
  
  def getLocalRecord(self, name:str) -> Optional[Attribute]:
    ':return: The local attribute record or *None* if there isn\'t one.'
    if name in self._attrs.keys():
      return self._attrs[name]
    else:
      return None
  
  def setLocalRecord(self, name:str, value:Attribute):
    'Replace or add a local attribute record'
    if not isinstance(name, str): raise TypeError("HierarchicalAttributedObject.__set_item__(): 1st parameter but be of type str.")
    if not isinstance(value, Attribute): raise TypeError("HierarchicalAttributedObject.__set_item__(): 2nd parameter must be of type Attribute.")
    if name != value.name: raise AttributeError(f'HierarchicalAttributedObject.__set_item__(): 1st parameter ("{name}") must be the same as the attribute name field ("{value.name}").')
    if self.getInhRecord(name) is None:
      if value.qualifiers is None:
        value.qualifiers = AttributeFlags.NIL
      if not self.isRecordComplete(value):
        raise AttributeError(f"Top-level records must be complete records: {value}")
    self._attrs[name] = value
    if value.owner != self:
      value.owner = self
    self.dirty()
      
  def getLocalValue(self, name) -> Optional[Any]:
    ':return: The value from a local attribute, None otherwise.'
    raw = self.getLocalRecord(name)
    return None if raw is None else raw.value
    
  def getInhRecord(self, name:str, _loopDetection=[]) -> Optional[AttributeData]:
    '''
    :return: The inherited (not the local) *AttributeData* for *name* in the FIRST
      parent that has the named record.  Or *None* if no parent has such a record.
    '''
    #global x
    if id(self) in _loopDetection:
      raise RecursionError(f'Detected loop while searching for attribute "{name}" in object ({self.__class__.__name__})"{self}" at {id(self)}, _loopDetection={str(_loopDetection)}')
    for p in self.getParents(_loopDetection=_loopDetection):
      try:
        return p.getRecord(name, _loopDetection=_loopDetection+[id(self)])
      except KeyError:
        continue
      except Exception as ex:
        raise ex
    return None
  
  @override
  def getRecord(self, key:str, _loopDetection=[]) -> Union[Attribute, AttributeData]:
    '''
    :return: An *AttributeData* representation, NOT an *Attribute*.
    :raises KeyError: If the key does not currently exist.
    
    Analogous to __get_item__(), but returns a *AttributeData* instead of the value
    '''
    # if key in self._attrs.keys():
    #   ret = self.mergeWithSuperAttr(self.getLocalRecord(key))
    # else:
    #   ret = self._getSuperAttr(key)
    # assert ret is None or (not isinstance(ret, Attribute) and isinstance(ret, AttributeData))
    # return ret
    
    def merge(inh:AttributeData, local:Attribute) -> AttributeData:
      #TODO: fix qualifiers for semantic constraints
      q = local.qualifiers if local.qualifiers is not None else inh.qualifiers
      t = local.typ        if local.typ        is not None else inh.typ
      v = None
      if local.value is not None:
        v = local.value
      elif not (q&AttributeFlags.VALUE_NOT_INHERITABLE):
        v = inh.value
      return AttributeData(local.name, t, v, q)
      
    local = self.getLocalRecord(key)
    if local is not None and self.isRecordComplete(local):
      return local.makeAttributeDataCopy()
    inh = self.getInhRecord(key, _loopDetection=_loopDetection)
    if inh is not None and local is not None:
      return merge(inh, local)
    if local is not None:
      return local.makeAttributeDataCopy()
    if inh is not None:
      return AttributeData(inh.name,
                           inh.typ, 
                           None if inh.qualifiers is not None and inh.qualifiers&AttributeFlags.VALUE_NOT_INHERITABLE else inh.value, 
                           inh.qualifiers)
    #return None
    raise KeyError(f'HierarchicalAttributedObject.getRecord(): Key "{key}" not found."')
  
  @override
  def getValue(self, name, _loopDetection=[]) -> Any: 
    'Get a value, possibly inherited'
    local = self.getLocalRecord(name)
    if local is not None and local.value is not None:
      return local.value
    inh = self.getInhRecord(name, _loopDetection=_loopDetection)
    if inh is None:
      if local is None:
        raise KeyError(str(name))
    else: # inh is not None (and local has a None value)
      if inh.isValueNotInheritable(): # and self.isIndividual():
        return None
      else:
        return inh.value
  
  @override
  def setValue(self, name, value: Any) -> Any:
    '''
    Set a value, could be:
    
    - just replace the value in a local Attribute record
    
    - add a new local attribute record with default values
    
    - add a new local attribute record, deferring to the inherited details
    
    '''
    self._validateValueUpdate(name, value) # might raise exceptions
    with self.ChangeMgr(self) as changeMgr:
      try:
        if name in self._attrs:
          self._attrs[name].value = value
        else:
          sooper = self.getRecord(name)
          if sooper is None:
            self.setAttribute(name, value.__class__, value)
          else:
            self.setAttribute(name, None, value, None)
        changeMgr.registerTopics(("setattr", name, value))
        self.dirty()
      except Exception as ex:
        logger.exception(f'HierarchicalAttributedObject.setValue(): {ex}')
        changeMgr.cancel()
      
  ### OBSERVER OVERRIDES ######################################################
  
  @override
  def update(self, subject:Subject, **topics)->None:
    assert isinstance(subject, Subject)
    super().update(self, subject, **topics)
    #TODO: implement HierarchicalAttributedObject.update()
  
  ### Serializable OVERRIDES ############################################################
  
  @classmethod
  def getArgs(cls, elem:ET.Element) -> Tuple[List[Any], Dict[str, Any]]:
    return list(), dict()
    
  @override
  def serializeXML(self)->ET.Element:
    elem:ET.Element = ET.Element("HierarchicalAttributedObject") #= Serializable.serializeXML(self)
    self.serializeXML_inner(elem)
    return elem

  def serializeXML_inner(self, elem:ET.Element) -> int:
    """
    :param elem: An element to append the attribute elements to.
    :return: the number of elements appended.
    
    Inner body of serializeXML which appends the attribute elements to *elem*.
    Needed when a subclass wants wrap the attributes differently.
    """
    n = 0
    for v in self._attrs.values():
      n += 1
      if isinstance(v, Serializable):
        elem.append(v.serializeXML())
      elif isinstance(v, list):
        for v1 in v:
          elem.append(v1.serializeXML())
      else:
        raise TypeError(f'{self.__class__.__name__}.serializeXML(): Attribute type must be Attribute or list of Attribute; got type {v.__class__.__name__}')    
    return n

  @override
  def unserializeXML(self, elem:ET.Element):
    super().unserializeXML(elem)
    #TODO: implement HierarchicalAttributedObject.unserializeXML
  
  def unserializeXML_inner(self, elem:ET.Element):
    """
    :param elem: An element to append the attribute elements to
    :return: the number of elements appended.
    
    Inner body of serializeXML which appends the attribute elements to *elem*.
    Needed when a subclass wants wrap the attributes differently.
    """
    if elem is not None:
      attrs = elem.findall(getFullClassName(Attribute))
      for attrElem in attrs:
        #attrElem.set("owner", id(self))
        attrElem.set("owner", self)
        self._attrs[attrElem.get("name")] = Serializable.makeObject(attrElem)

  ### UTILITY #################################################################
  
  def isRecordComplete(self, attr:AttributeData) -> bool:
    '''
    Raises an Assert exception if *attr* contains any *None* fields.
    '''
    if attr.name       is None: return False
    if attr.typ        is None: return False
    if attr.value      is None: return False
    if attr.qualifiers is None: return False
    return True
    
  def _validateValueUpdate(self, attrName:str, value:Any) -> NoReturn:
    "Raises exceptions"
    ret = True
    superAttr = self.getInhRecord(attrName)
    isClassVar = superAttr is not None and superAttr.isInstanceFinal() 
    if isClassVar and self.isIndividual():
      raise PermissionError(f'{self.__class__.__name__}._validateValueUpdate(): individuals cannot modify class attributes.')
    attr = self.getRecord(attrName)
    if attr is not None: # will be None in the case of createing a new Attribute
      if attr.typ is not None and not isValidType(attr.typ, value):
        raise TypeError(f'{self.__class__.__name__}._validateValueUpdate(): Value argument must be of type {attr.typ.__name__ if isinstance(attr.typ, Type) else ("string type "+attr.typ)} but it\'s of type {value.__class__.__name__}')
    return ret
      
  @override
  def isTypeEditable(self, key:str) -> bool:
    '''
    Types of read/write variables are invariant, so if this key is inherited, the
    type is not editable.
    '''
    return self.getInhRecord(key) is None
    
  @override
  def isValueEditable(self, key:str) -> bool:
    '''
    The value is NOT editable if:
    
      - qualifiers.FINAL is inherited
      - qualifiers.INSTANCE_FINAL is inherited and the container is an individual
    '''
    inhRec:AttributeData = self.getInhRecord(key)
    if inhRec is None:
      return True
    if inhRec.isFinal():
      return False
    if inhRec.isInstanceFinal() and self.isIndividual():
      return False
    return True
    
  @override
  def isQualifierEditable(self, key:str) -> bool:
    '''
    Qualifiers are only editable if this is the defining attribute (not inherited)
    '''
    return self.getInhRecord(key) is None
    
  def validate(self) -> list[str]:
    '''
    :return: A *list[str]* of error messages for all the values in the container.
      This includes all *Attrubutes* which at least partially exist locally, but does
      NOT include items that are purely inherited. 
    '''
    ret:list[str] = []
    for attr in self._attrs.values():
      ret += attr.validate(superAttr=self.getInhRecord(attr.name))
    return ret

  def updateWith(self, updates:dict[str,Attribute]):
    logger.warning("HierarchicalAttributedObject.updateWith(): Method is not safe with hierarchical containers.")
    AttributedObject.updateWith(self, updates)
      
      
class NestedHierarchicalAttributedObject(HierarchicalAttributedObject):
  '''
  A container for *Attribute* objects, embodying the concept of attribute inheritance.
  '''
  
  def __init__(self, parentContainer:HierarchicalAttributedObject, attributeName:str):
    assert isinstance(parentContainer, HierarchicalAttributedObject)
    assert isinstance(attributeName, str)
    HierarchicalAttributedObject.__init__(self)
    self.parentAttributedObject:HierarchicalAttributedObject = parentContainer
    self.attrName = attributeName
    
  ### ABSTRACT METHODS ########################################################

  @override
  def getParents(self, _loopDetection=[]) -> Iterable[Self]:
    try:
      return self.parentAttributedObject[self.attrName]
    except:
      return []
    return 
    
  @override
  def isIndividual(self) -> bool:
    return self.parentAttributedObject.isIndividual()
    
  @override
  def referenceContext(self):
    return self.parentAttributedObject.referenceContext()

      