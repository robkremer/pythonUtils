'''
This module represents a Strategy pattern (Gamma et al) class 
(:py:class:`SerializationStrategy`) that serves to serialize
and unserialize Python objects with proper support for multiple references to
the same object. Thus, if *[a, b]* where *a is b* is stored, then when *[a, b]* is
read back, *a is b* will still be true (although the read-back *a* will not likely
have the same *id* as the original *a*). 

This module contains the following classes/functions:

  :class: :py:class:`SerializationStrategy`: The main class programs use to write and read
      persistent data to files or URLs. It serves both as an abstract superclass
      to all specific strategies/protocols (eg: XML, JSON) and it's class methods support
      easy access to these specific strategies.
  :class: :py:class:`Serializable`: If you want to store user-defined classes, you 
      must include this abstract class as a superclass. This obligates defining
      the :py:meth:`Serializable.getInstantiationInfo` method.
  :class: :py:class:`InstantiationInfo`: A data class the is returned by the above
      method.
  :class: :py:class:`ParamInfo` and :py:class:`PropertyInfo`: A data class that forms
      part of the information in :py:class:`InstantiationInfo`.
  :class: :py:class:`strdict`: A direct sublclass of *dict* that restricts keys to 
      *str*. Many of the serialization protocols use such a structure and you can
      significantly reduce the size of files by storing dictionary-type data
      using this class rather than *dict* whenever you have a *dict* with string
      keys. 
  :func: :py:func:`getInstantiationInfo`: A utility function to retrieve the 
      instantiation information from a :py:class:`Serializable` subclass.

:py:class:`SerializationStrategy`
is an abstract class that supports various storage formats
such as **XML** or **JSON** through concrete subclasses. 
Other possibilities are **plist**, **marshal**, and **pickle**.  
This an application can hold
a reference to *SerializationStrategy* witch could, for example, be either a concrete 
:py:class:`SerializeXML <util.persistence.SerializeXML>`
or :py:class:`SerializeJSON <util.persistence.SerializeJSON>` 
and use the :py:meth:`write() <SerializationStrategy.write>`
and :py:meth:`read() <SerializationStrategy.read>` methods
to write/read data in the relevant data formats.

Object types supported:
  
  - int
  - float
  - str
  - list
  - tuple
  - set
  - dict
  - :py:class:`strdict`: a subclass of *dict* restricted to *str* keys.
  - Any properly implemented subclass of 
    :py:class:`Serializable`.

Any user-defined class to be stored using 
:py:class:`SerializationStrategy <util.persistence.SerializationStrategy>`
must inherit from
:py:class:`Serializable`, which 
obligates it to override the 
:py:meth:`getInstantiationInfo() <util.persistence.Serializable.getInstantiationInfo>`
method.  This method must return a :py:class:`InstantiationInfo`
object, which has five properties:

  :cls: [type] The *class* of the object
  :conArgs: [Optional[list[ParamInfo]]] Information about the each of the 
    positional arguments to the object's constructor.
  :conKWArgs: [Optional[list[ParamInfo]]] Information about the each of the 
    keyword arguments to the object's constructor.
  :postconSetters: [Optional[list[PropertyInfo]]] Information about each of the
    updates to be done immediately after the constructor is called
    (other "sibling" objects may not have been created yet).
  :finalSetters: [Optional[list[PropertyInfo]]]  Information about the each of the 
    updates to be done after ALL of the "sibling" objects have been created.

where :py:class:`ParamInfo` and 
:py:class:`PropertyInfo` are data classes defining:

    :name: [str] The name of the parameter in the class's constructor (*__init__()*).
    :typ: [type] The fully qualified class name.
    :getter: [getter: Optional[Callable[[:py:class:`Serializable`], :py:class:`SerializableType`]]=None] 
      A function taking a this object as a parameter and returning
      a value to be passed to the constructor. If this is *None* or not given, 
      *name* will be taken to the a property of this object and will be taken
      as the value to pass to the constructor.
    :setter: (*PropertyInfo* only) [Optional[Callable[[:py:class:`Serializable`, :py:class:`SerializableType`], None]]=None]
      A function taking two arguments: a newly constructed version
      of this object, and the object produced by *getter()*.  This is applied 
      on restoration of the object either immediately
      after the constructor or after all objects entailed by the construction of
      the object are complete. If this is *None* or not given, 
      *name* will be taken to the a property of this object that property will
      be updated with the restored *getter()* object at the appropriate time.

Programs using concrete :py:class:`SerializationStrategy` objects have the following interface
(the "public" methods without prefix underscores):

  - :py:meth:`writex() <SerializationStrategy.writex>`: (class method) Looks up a protocol to write an object to a file or URL.
  - :py:meth:`readx() <SerializationStrategy.readx>`: (class method) Looks up a protocol to read an object from a file or URL.
  - :py:meth:`tostringx() <SerializationStrategy.tostringx>`: (class method) Looks up a protocol to convert an object to a serialized string.
  - :py:meth:`fromstringx() <SerializationStrategy.fromstringx>`: (class method) Looks up a protocol to convert a serialized string to an object.
  - :py:meth:`getAvailableStrategies() <SerializationStrategy.getAvailableStrategies>`: (class method) \
      Retrieves basic information about all known available concrete persistent strategies.  
  - :py:meth:`write() <SerializationStrategy.write>`: Writes an object to a file or URL.
  - :py:meth:`read() <SerializationStrategy.read>`: Reads an object from a file or URL.
  - :py:meth:`tostring() <SerializationStrategy.tostring>`: Converts an object to a serialized string.
  - :py:meth:`fromstring() <SerializationStrategy.fromstring>`: Converts a serialized string to an object.
  - :py:meth:`defaultExtension() <SerializationStrategy.defaultExtension>`: Returns the default file extension for the strategy.
  - :py:meth:`protocolName() <SerializationStrategy.protocolName>`: Returns the name of the concrete strategy.
  - :py:meth:`protocoVersion() <SerializationStrategy.protocolVersion>`: Returns the version of the concrete strategy in n.n... form as a string.
  - :py:attr:`header <SerializationStrategy.header>`: A *dict* containing header info from the last file, URL, or string read.
  - :py:attr:`appName <SerializationStrategy.appName>`: Apps should set this string to the name of the app at initialization. To be recorded in file headers.
  - :py:attr:`appVersion <SerializationStrategy.appName>`: Apps should set this string to the version of the app at initialization. To be recorded in file headers.
  - :py:attr:`version <SerializationStrategy.version>`: (read only) The <appVersion>:<serializationVersion>:<protocolVersion> string. 
  
.. inheritance-diagram:: SerializationStrategy Serializable InstantiationInfo ParamInfo PropertyInfo strdict 
    :parts: 3
    :private-bases:
    :top-classes: object

--------------

Created on Mar 20, 2026

.. codeauthor:: Rob Kremer <robkremer@me.com>

---------------
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
from __future__ import annotations
import os
import sys
import urllib.request
from urllib.parse import ParseResult, urlparse, unquote
from abc import abstractmethod, ABC
from typing import Any, Callable, Optional, Union, override, cast, Iterable,\
  final, NamedTuple, ClassVar
import datetime
from types import NoneType
from dataclasses import dataclass, field
import weakref

import util
from util.utils import getFullClassName, getClassFromFullyQualifiedName,\
  fixURL, getFullyQualifiedClass, findConcreteSubclasses, \
  importSubmodules

logger:util.Logger = util.getLogger(__name__)

VERSION = "2.0"
'''The version of this framework (*SerializationStrategy*): of what's common to
all strategies -- eg: a document being a head and one object (see
*SerializationStrategy.tostring()*: since 2.0). (Each strategy has its own
version too: see *SerializationStrategy.protocolVersion()*.)'''

HEAD = "head"
"A document's head (see *SerializationStrategy.tostring()*)."
BODY = "object"
"A document's object -- its body (see *SerializationStrategy.tostring()*)."
OLD_HEADER, OLD_ROOT = "header", "root"
"The head and object of a document written before *VERSION* 2.0."

HEAD_FORMAT = "format"
"In a head: the strategy that wrote it (see *SerializationStrategy.protocolName()*)."
HEAD_FORMAT_VERSION = "formatVersion"
"In a head: its version (see *SerializationStrategy.protocolVersion()*)."
HEAD_SERIALIZATION_VERSION = "serializationVersion"
"In a head: the framework's version (*VERSION*)."
HEAD_APPLICATION = "application"
"In a head: the application that wrote it (see *SerializationStrategy.appName*)."
HEAD_APPLICATION_VERSION = "applicationVersion"
"In a head: its version (see *SerializationStrategy.appVersion*)."
HEAD_TYPE = "type"
"In a head: the class of the document's object (its fully qualified name)."
HEAD_SAVED = "saved"
"In a head: when it was written (ISO 8601, with the time zone)."

HeadValue = Union[str, int, float, bool, list, dict]
'''What a head holds: strings, numbers, booleans; lists of those; and tables
(dicts with str keys) of those. Nothing else -- no None, no objects, no
references -- so any format can hold it, and anything can read it.'''

def isHeadValue(value:Any, depth:int=0) -> bool:
  '''
  :param value:
  :type value: Any
  :returns: Whether *value* can be in a head (see *HeadValue*).
  :rtype: bool
  '''
  if type(value) in (str, int, float, bool):
    return True
  if depth == 0 and type(value) in (list, tuple):
    return all(isHeadValue(v, 1) for v in value)
  if depth == 0 and isinstance(value, dict):
    return all(isinstance(k, str) and isHeadValue(v, 1) for k, v in value.items())
  return False
APP = (lambda: [spec := sys.modules['__main__'].__spec__,
                spec.name if spec is not None else sys.argv[0]][1])()
TAG_FILETYPE = "filetype"
ATTR_TYPE = "type"
TAG_KVPAIR = "property"
ATTR_NAME = "name"

# from util.persistence.serialize import SerializationStrategy
# SerializationStrategy.appName = f'{NAME} ({SHORT_NAME})'
# SerializationStrategy.appVerion = VERSION



class Serializable:
  '''
  Defines the required protocol (one class method) for any user-defined objects
  being saved under the framework. 
  '''
  @classmethod
  @abstractmethod
  def getInstantiationInfo(cls) -> InstantiationInfo:
    '''
    :returns: A :py:class:`InstantiationInfo <util.persistence.serialize.InstantiationInfo>` 
      structure describing the constructor parameters and how to fill them
      (conArgs, conKWArgs), and a further description of any additional data to
      be filled after immediately after the constructor (postconSetters) and 
      more after any contained objects have been fully constructed (finalSetters),
      both how to write them and read them.
    :rtype: :py:class:`util.persistence.serialize.InstantiationInfo`
    '''
    raise NotImplementedError("Abstract method Serializable.getInstantiationInfo() not implemented.")



class strdict[T](dict[str, T]): # should really be dict[str, SerializableType] but that runs into forward declaration problems...
  '''
  A simple subclass of *dict* that restricts the type of keys to type *str*.
  '''
  def __init__(self, *args, **kwargs):
    '''
    :param args:
    :type args:
    :param kwargs:
    :type kwargs:
    '''
    incoming = dict(*args, **kwargs)
    for k,v in incoming.items():
      if not isinstance(k, str):
        raise KeyError(f"Keys must be str, got {type(k).__name__!r} for key {k!r}")
      if not (type(v) in SerializableTypes or type(v) is strdict or isinstance(v, Serializable)):
        raise ValueError(f'strdict is restricted to values of types {SerializableType} only; got value of type {type(v)}.')
    self.update(incoming)
      
  def __setitem__(self, key, value)->None:
    '''
    :param key:
    :type key:
    :param value:
    :type value:
    '''
    if not isinstance(key, str):
      raise KeyError(f'strdict is restricted to keys of type str only; got key {key} of type {type(key)}.')
    if not (type(value) in SerializableTypes or isinstance(value, Serializable)):
      raise ValueError(f'strdict is restricted to values of types {SerializableType} only; got value of type {type(value)}.')
    super().__setitem__(key, value)

strdict_className = getFullClassName(strdict)

SerializableType = Union[Serializable, int, float, bool, str, list, dict, strdict, tuple, set, None]
SerializableTypes = (Serializable, int, float, bool, str, list, dict, strdict, tuple, set, NoneType)
SerializableUnitTypes = Union[int, float, bool, str, None]
SerializableCompositeTypes = Union[Serializable, list, dict, strdict, tuple, set]


@dataclass
class InstantiationInfo:
  '''
  The data structure for information for storing and retrieving user-defined 
  persistent objects (:py:class:`Serializable` subclasses).
  '''
  class_:type
  'The type of the class'
  conArgs:list[ParamInfo] = field(default_factory=list) # param types
  'An ordered list of :py:class:`ParamInfo` structures describing the positional parameters of the constructor.'
  conKWArgs:list[ParamInfo] = field(default_factory=list)
  'An *dict* of :py:class:`ParamInfo` structures describing the keyword parameters of the constructor.'
  postconSetters:list[PropertyInfo] = field(default_factory=list)
  'An *dict* of :py:class:`PropertyInfo` structures describing the storing and restoring of object data occurring immediately after the constructor.'
  finalSetters:list[PropertyInfo] = field(default_factory=list)
  'An *dict* of :py:class:`PropertyInfo` structures describing the storing and restoring of object data occurring after all other objects implied by the object construction have been restored.'
  
  def __post_init__(self):
    '''
    Check that no name is duplicated in and between the any of args lists. 
    '''
    names:list[str] = []
    for args in (self.conArgs, self.conKWArgs, self.postconSetters, self.finalSetters):
      for pinfo in args:
        if pinfo.name in names:
          raise NameError(f'Duplicate name "{pinfo.name}".')
        names.append(pinfo.name)
        
  @property
  def className(self):
    '''
    :returns: the fully qualified class name of the described class.
    '''
    return getFullClassName(self.class_)
  

def getInstantiationInfo(className:str) -> InstantiationInfo:
  '''
  :param className: The name of a *Serializable* subclass. 
  :type className: str   
  :returns: the *InstantiationInfo* structure for *className*.
  :rtype: InstantiationInfo
  :raises TypeError: if the class cannot be found or  
  
  Look up the *InstantiationInfo* structure for *className* and return it.
  '''
  cls:Optional[type] = getClassFromFullyQualifiedName(className)
  if cls is None:
    raise TypeError(f'Cannot find type "{className}".')
  if not issubclass(cls, Serializable):
    raise TypeError(f'Class "{className}" is not a subtype of PersisentObject.')
  return cls.getInstantiationInfo()


class ParamInfo:
  '''
  A data class to describe how to construct an object.
  '''
  def __init__(self, name:str, typ:Optional[type], 
               getter:Optional[Callable[[Serializable], SerializableType]]=None,
               setter:Optional[Callable[[SerializableType], Any]]=None,
               unique:bool=False, optional:bool=False, inHead:bool=False):
    '''
    :param name: The name of the parameter in the classes constructor (*__init__()*).
    :type name: str
    :param typ: The fully qualified class name **for the saved type** (which
      *could* be different from the actual type used in the constructor).
    :type typ: type
    :param getter: A function taking a this object as a parameter and returning
      a value to be passed to the constructor. If this is *None* or not given, 
      *name* will be taken to the a property of this object and will be taken
      as the value to pass to the constructor.
    :type getter: Optional[Callable[[Serializable], SerializableType]]=None
    :param setter: A function called just before restoring this object that takes
      the object stored by *getter()* and returns an object to be applied as
      the relevant argument in the constructor.
    :param unique:
    :type unique: bool
    :param optional:
    :type optional: bool
    '''
    self.name:str = name
    'the name of the parameter'
    assert typ is None or typ in SerializableTypes or issubclass(typ, (Serializable, strdict)), f'typ == {typ}'
    self.typ:Optional[type] = typ
    'the type of the parameter'
    
    self.getter:Callable[[Serializable], SerializableType]
    'A function taking 1 "self" parameter and returning the run-time value of this parameter.'
    if getter is None:
      self.getter = lambda slf: getattr(slf, self.name)
    else:
      self.getter = getter
    self.setter:Callable[[SerializableType], Any]
    if setter is None:
      self.setter = lambda obj: obj
    else:
      self.setter = setter
    self.unique:bool = unique
    self.optional:bool = optional
    'Iff True, a file without this parameter still loads: it is left out of the constructor call (so its default applies). For parameters added after files were saved.'
    self.inHead:bool = inHead
    '''Iff True, when the object is a document's object (see *SerializationStrategy.tostring()*),
    this is written in the document's head, not with the object -- eg: a reference to another
    document. Its value must be a *HeadValue*.'''
    

class PropertyInfo():
  '''
  A data class to describe how to construct and restore an object.
  '''
  def __init__(self, name:str, typ:type, 
               getter:Optional[Callable[[Serializable], SerializableType]]=None,
               setter:Optional[Callable[[Serializable, SerializableType], None]]=None,
               unique:bool=False, optional:bool=False, omitIfNone:bool=False, inHead:bool=False):
    '''
    :param name: The name of the property in the class's definition. You may
      also use the value "_" in order the just execute the *setter* function
      without reference to any property (eg: you want to set a property to
      a constant **after** the constructor has completed).
    :type name: str
    :param typ: The fully qualified class name **for the saved type** (which
      *could* be different from the actual type in the object).
    :type typ: type
    :param getter: A function taking a this object as a parameter and returning
      a value to be passed to the constructor. If this is *None* or not given, 
      *name* will be taken to the a property of this object and will be taken
      as the value to pass to the constructor.
    :type getter: Optional[Callable[[Serializable], SerializableType]]=None
    :param setter: A function taking two arguments: a newly constructed version
      of this object, and the object saved by *getter()*.  This is applied on restoration
      of the object either immediately
      after the constructor or after all objects entailed by the construction of
      the object are complete. If this is *None* or not given, 
      *name* will be taken to the a property of this object that property will
      be updated with the restored *getter()* object at the appropriate time.
    :type setter: Optional[Callable[[Serializable, SerializableType], None]]=None
    :param unique:
    :type unique: bool
    :param optional: Whether it may be missing from a file (eg: one written
      before the property existed): the setter is then not called.
    :type optional: bool
    :param omitIfNone: Whether to leave it out of the file when its value is
      None -- eg: a property that's almost always None, so as not to fill every
      file with it. (It's then *optional* too.)
    :type omitIfNone: bool
    '''
    self.name:str = name
    'the name of the parameter'
    assert typ is None or typ in SerializableTypes or issubclass(typ, (Serializable, strdict)), f'typ == {typ}'
    self.typ:Optional[type] = typ
    'the type of the parameter'
    
    self.getter:Callable[[Serializable], SerializableType]
    'A function taking 1 "self" parameter and returning the run-time value of this parameter.'
    if getter is None:
      self.getter = (lambda self: None) if self.name == "_" else (lambda slf: getattr(slf, self.name))
    else:
      self.getter = getter
    self.setter: Callable[[Serializable, SerializableType], None]
    if setter is None:
      self.setter = lambda slf, value: setattr(slf, self.name, value)
    else:
      self.setter = setter
    self.unique:bool = unique
    self.optional:bool = optional or omitIfNone
    self.omitIfNone:bool = omitIfNone
    "Whether it's left out of the file when its value is None (see *__init__()*)."
    self.inHead:bool = inHead
    "Whether it's written in the document's head (see *ParamInfo.inHead*)."
    'Iff True, a file without this property still loads: it just isn\'t set. For properties added after files were saved.'



DEFAULT_STRATEGY = "XML3"
"The name of the strategy things are saved with unless told otherwise (see util.persistence.serializeXML2)."

class SerializationStrategy[T](ABC):
  '''
  A Strategy pattern class designed to save objects in a manner that allows for
  multiple storage formats (eg: XML, JSON, etc). This class proposes to support
  build-in data types: *int, float, bool, str, list, dict, tuple, set*, as
  well as any (properly constructed) user-defined subclass of *Serializable*.
  
  **For subclass (concrete protocol) developers:**
  
  The T generic type is the artifact type used by the concrete protocol (subclass). For
  example, for XML implemented with *etree* package, it's *Element* and for 
  JSON implemented with the *json* package, it's
  *Union[dict, list, int, float, bool, str]*.
  
  Subclasses (defining specific strategies) must override (minimally) the following
  abstract methods:
  
    - :py:meth:`_tostring() <SerializationStrategy._tostring>`: given an eligible object, return a serialized *str* version of the object.
    - :py:meth:`_fromstring() <SerializationStrategy._fromstring>`: given a serialized *str*, return the corresponding Python object.
    - :py:meth:`_setAttr() <SerializationStrategy._setAttr>`: 
    - :py:meth:`_getAttr() <SerializationStrategy._getAttr>`: 
    - :py:meth:`_setKVPair() <SerializationStrategy._setProperty>`: 
    - :py:meth:`_getKVPair() <SerializationStrategy._getProperty>`: 
    - :py:meth:`_getKVPairs() <SerializationStrategy._getProperties>`: 
    - :py:meth:`_appendItem() <SerializationStrategy._appendItem>`: 
    - :py:meth:`_getItems() <SerializationStrategy._getItems>`: 
    - :py:meth:`_encodeStr() <SerializationStrategy._encodeStr>`: for a *str* object, return the corresponding T object.
    - :py:meth:`_decodeStr() <SerializationStrategy._decodeStr>`: for a T object, return the corresponding *str* object.
    - :py:meth:`_encodeList() <SerializationStrategy._encodeList>`: return the T object corresponding to an empty list.
    - :py:meth:`_decodeList() <SerializationStrategy._decodeList>`: for a T object representing a list, return a *list* of T objects. 
  
  Subclasses **may** override the following concrete methods (by default they are
  implmented in terms of the methods above):
  
    - :py:meth:`_encodeInt() <SerializationStrategy._encodeInt>`: 
    - :py:meth:`_decodeInt() <SerializationStrategy._decodeInt>`: 
    - :py:meth:`_encodeFloat() <SerializationStrategy._encodeFloat>`: 
    - :py:meth:`_decodeFloat() <SerializationStrategy._decodeFloat>`: 
    - :py:meth:`_encodeBool() <SerializationStrategy._encodeBool>`: 
    - :py:meth:`_decodeBool() <SerializationStrategy._decodeBool>`: 
    - :py:meth:`_encodeTuple() <SerializationStrategy._encodeTuple>`: 
    - :py:meth:`_decodeTuple() <SerializationStrategy._decodeTuple>`: 
    - :py:meth:`_encodeSet() <SerializationStrategy._encodeSet>`: 
    - :py:meth:`_decodeSet() <SerializationStrategy._decodeSet>`: 
    - :py:meth:`_encodeDict() <SerializationStrategy._encodeDict>`: 
    - :py:meth:`_decodeDict() <SerializationStrategy._decodeDict>`: 
    - :py:meth:`_encodeStrdict() <SerializationStrategy._encodeStrdict>`: Encode a :py:class:`strdict` object; 
        useful as so many protocols (eg: **JSON**, **plist**) have "native" dictionaries
        restricted to *str* keys. 
    - :py:meth:`_decodeStrdict() <SerializationStrategy._decodeStrdict>`: Decode a :py:class:`strdict` object
    - :py:meth:`_encodeSerializable() <SerializationStrategy._encodeSerializable>`: 
    - :py:meth:`_decodeSerializable() <SerializationStrategy._decodeSerializable>`: 
  
  Subclasses should **NOT** override the following methods as they encapsulate all
  the housekeeping involved in keeping track of object pointers. However, subclasses
  should **USE** these methods (rather than the _encode*() and _decode*() methods
  above when storing objects for that same reason:
  
    - :py:meth:`_encode_() <SerializationStrategy._encode_>`: 
    - :py:meth:`_decode_() <SerializationStrategy._decode_>`: 
  
  '''

  
  class Strategy(NamedTuple):
    '''
    A serialization strategy's name, file extension and class.
    '''
    name:str
    extension:str
    cls:type
    
  @dataclass
  class _MemStrategy():
    '''
    A known serialization strategy (see *knownStrategies*), with its instance.
    '''
    name:str
    extension:str
    cls:type
    obj:SerializationStrategy # weakref.ReferenceType[SerializationStrategy]|SerializationStrategy
    
  knownStrategies:list[SerializationStrategy._MemStrategy] = []
  '''The list of known persistent strategies. Populated incrementally as
  strategies are constructed (see *__init__()* below) -- but also, as of
  module load time, pre-populated with every concrete strategy findable in
  this package (*util.persistence*), even ones nothing has imported yet.
  See *_populateKnownStrategiesAtLoad()* at the bottom of this module.'''
    
  def __init__(self):
    '''
    Create an object from a byte array.
    '''
    self._finalMethodsList:list[Callable] = []
    
    self.header:dict[str, Any] = dict()
    'The header information from the last file, url, or string read.'
    
    self.knownStrategies.insert(0, self._MemStrategy(self.protocolName(), self.defaultExtension(), type(self), self)) # weakref.ref(self)))
    
  ### PUBLIC METHODS ###########################################################
  
  @classmethod
  def getAvailableStrategies(cls, 
                             packages:Iterable[str]=[], 
                             filtr:Optional[Callable[[str], bool]]=None,
                             asString:bool=False) \
                                -> list[SerializationStrategy.Strategy]|str:
    '''
    :param packages: A list of package names to scan for concrete strategy 
      classes to be loaded. 
    :type packages: Iterable[str]
    :param filtr: If given, the module will only be loaded if *filter()* called with
      a scanned module name returns *True*. All scanned modules who's name 
      starts with "serialize" will be loaded as well.
    :type filtr: Optional[Callable[[str], bool]]=None
    :param asString: if *True*, return a user-readable string listing the names and extensions. 
    :type asString: bool (default: *False*)
    :returns: A tuple [strategy-name. default-file-extension, strategy-class].
    :rtype: list[tuple[str, str, type]]
    
    Returns a list of name/class/extension 3-tuples of available strategies. That is,
    all the concrete subtypes of this abstract class. 
    '''
    
    for p in list(packages)+["util.persistence"]:
      importSubmodules(p, 
        filtr=lambda mod, f=filtr: mod.split(".")[-1].startswith("serialize") or (f is not None and f(mod))) # type: ignore[misc]
  
    ret:list[SerializationStrategy.Strategy] = []
    for strat in findConcreteSubclasses(cls):
      ret.append(SerializationStrategy.Strategy(strat.protocolName(), strat.defaultExtension(), strat))
      
    if asString:
      width = 13 
      for s in ret:
        if len(s.name) > width:
          width = len(s.name)
      form = '{:>'+str(width)+'} | {}\n' 
      retStr = form.format("Protocol Name", "Extension")+ \
               form.format("-"*width, "---------")
      for s in ret:
        retStr += form.format(s.name, s.extension)
      return retStr
    else:
      return ret

  preferred:bool = False
  '''
  If *True*, this strategy is chosen when a file extension is matched by more
  than one strategy (see *findStrategy()*) -- eg: one that can read what the
  others write.
  '''

  appName = APP
  'The name of the Application -- should be reassigned by the application at startup.'
  
  appVersion = 'Unknown'
  'The version of the Application -- should be reassigned by the application at startup.'
  
  @property
  @final
  def serializationStrategyVersion(self):
    '''
    :returns: The version string of this class.
    
    .. Note::
      This is different from the :py:meth:`protocolVersion() <SerializationStrategy.protocolVersion>`
      method that returns the version string of the actual concrete strategy.
    '''
    return VERSION
  
  @property
  @final
  def version(self):
    '''
    :returns:
    :rtype:
    '''
    return f'{self.appVersion}:{self.serializationStrategyVersion}:{self.protocolVersion()}'
  
  @classmethod
  def _byPreference(cls) -> list[SerializationStrategy.Strategy]:
    '''
    The available strategies (see *getAvailableStrategies()*), preferred ones first.

    :returns:
    :rtype: list[SerializationStrategy.Strategy]
    '''
    strats = cls.getAvailableStrategies()
    assert isinstance(strats, list)
    return sorted(strats, key=lambda s: not getattr(s.cls, "preferred", False))

  @classmethod
  def findStrategy(cls, strategy:str) -> SerializationStrategy:
    # an extension matched by several strategies: the preferred one
    '''
    :param strategy:
    :type strategy: str
    :returns:
    :rtype: SerializationStrategy
    '''
    if strategy.startswith("."):
      for s0 in cls._byPreference():
        if s0.extension == strategy:
          strategy = s0.name
          break
    #search for a relevant strategy in memory... 
    deleteRecs = []
    strat:Optional[SerializationStrategy] = None
    s: SerializationStrategy._MemStrategy
    for s in cls.knownStrategies:
      if (strategy == s.extension) if strategy.startswith(".") else (strategy == s.name):
        if isinstance(s.obj, weakref.ReferenceType):
          assert isinstance(s.obj, weakref.ReferenceType) 
          strat = s.obj()  
        else:
          assert isinstance(s.obj, SerializationStrategy), type(s.obj)
          strat = s.obj # accessing the weakref will return None 
        if strat is None:
          deleteRecs.append(s)
        else:
          s.obj = strat # keep this object in memory
          break
    for d in deleteRecs: # clean up any deallocated items we happened to encounter
      cls.knownStrategies.remove(d)

    #search for a relavant strategy in other modules, and put it in memory...
    if strat is None:
      strats = cls.getAvailableStrategies()
      for s2 in strats:
        assert type(s2) is SerializationStrategy.Strategy
        if (strategy == s2.extension) if strategy.startswith(".") else (strategy == s2.name):
          strat = s2.cls() # The constructor will add it's record to the cls.knownStrategies list.
          cls.knownStrategies[0].obj = strat # keep this strat in memory
      
    if strat is None:
      raise LookupError(f'Cannot find protocol "{strategy}"')
    
    return strat
    
  @classmethod
  def tostringx(cls, strategy:str, obj:SerializableType, *, wrap:Union[bool,dict]=False, assume:list[Any]=[], **kwargs) -> str:
    """
    Return the data in *obj* as a strategy-specific formatted string. the 
  
    :param strategy: The name or extension (starting with a dot) of some 
      protocol-specific strategy (a concrete subclass of this class) to use to 
      encode *obj*. If *strategy* is an extension and there is more than one 
      strategy with that extension, the last matching one used will
      be selected, of if this is the first one, the selection is unspecified.
    :type strategy: str
    :param obj: The object to serialise and returned.
    :type obj: SerializableType
    :param wrap: If *wrap* is False there is not wrapping, if True or a *dict* a
      dictionary is created containing keys "header" (which is mapped to *wrap* if
      it's a *dict* or a default header if it's *True*) and "root" (which maps
      to (*obj).  The *fromstring()* method will automatically unwrap and save
      the header info (if it's there) as the property *self.header:dict*.
    :type wrap: Union[bool,dict[
    :returns: The serialized object as a string.
    :rtype: str
    :param assume:
    :type assume: list[Any]
    :param kwargs:
    :type kwargs:
    """
    strat = cls.findStrategy(strategy)
    return strat.tostring(obj, wrap=wrap, assume=assume, **kwargs)
    
  @classmethod
  def fromstringx(cls, strategy:str, string:str, **kwargs) -> SerializableType:
    """
    Return an object made from a strategy-specific formatted string.
  
    :param strategy: The name or extension (starting with a dot) of some 
      protocol-specific strategy (a concrete subclass of this class) to use to 
      encode *obj*. If *strategy* is an extension and there is more than one 
      strategy with that extension, the last matching one used will
      be selected, of if this is the first one, the selection is unspecified.
    :param string: The string to interpret.
    :type string: str
    :param kwargs: A set of keyword arguments to be passed to concrete subclass.
    :type kwargs: dict[str, Any]
    :returns: The object interpreted from *string*.
    :rtype: SerializableType
    """
    strat = cls.findStrategy(strategy)
    return strat.fromstring(string, **kwargs)

  @classmethod
  def writex(cls, url:str, obj:SerializableType, strategy:Optional[str]=None, 
             replaceExt:Optional[bool]=True, wrap:Union[bool,dict]=True, 
             **kwargs) -> None:
    """
    Write an the data to a URL.
  
    For ``file:`` URLs the data is written directly to the local filesystem path.
    For all other schemes (e.g. ``http:``, ``https:``) the XML is uploaded via
    :func:`urllib.request.urlopen` as an HTTP PUT request with content-type
    ``application/xml``.
  
    :param url: The destination URL. Use ``file:///absolute/path`` or
      ``file://relative/path`` for local files.
    :type url: str
    :param obj: The object to serialise and write.
    :type obj: SerializableType
    :param strategy: (default=None) The name or extension (starting with a dot) of some 
      protocol-specific strategy (a concrete subclass of this class) to use to 
      encode *obj*. If *strategy* is an extension and there is more than one 
      strategy with that extension, the last matching one used will
      be selected, of if this is the first one, the selection is unspecified. If
      *strategy* is missing or None, the strategy will be inferred from the 
      extension in *url* as though it had been given in the *strategy* parameter.
    :type strategy: Optional[str] 
    :param replaceExt: If True, (the default) any extension will be replace with
      the default extension; if False, the default will extension will be 
      appended to the path if it's not already there; if None, nothing will
      be done to the path.
    :type replaceExt: Optional[bool]
    :param kwargs: A set of keyword arguments to be passed to concrete subclass.
    :type kwargs: dict[str, Any]
    :returns: None
    :rtype: None
    :raises ValueError: If *url* is an empty string.
    :raises FileNotFoundError: If the parent directory of a ``file:`` URL path
      does not exist.
    :raises urllib.error.URLError: If a remote URL cannot be reached.
  
    Usage::
  
      >>> tree = ET.parse("data.xml")
      >>> write("file:///tmp/output.xml", tree)
      >>> write("https://example.com/api/document", tree)

    :param wrap:
    :type wrap: Union[bool, dict]
    """
    strat:Optional[SerializationStrategy] = None
    if strategy is not None:
      strat = cls.findStrategy(strategy)
      if strat is None:
        raise LookupError(f'No strategy matching "{strategy}" found.')
    else:
      parsed = urlparse(url)
      filename = os.path.basename(parsed.path)
      ext = filename.split(".")[-1]
      strat = cls.findStrategy('.'+ext)
      if strat is None:
        raise LookupError(f'No strategy matching ".{ext}" found.')
    return strat.write(url, obj, replaceExt=replaceExt, wrap=wrap, **kwargs)
  
  @classmethod
  def readx(cls, url:str, strategy:Optional[str]=None, replaceExt:bool|None=True, mode="w", **kwargs) -> SerializableType:
    '''
    :param url: The destination URL. Use ``file:///absolute/path`` or
      ``file://relative/path`` for local files.
    :type url: str
    :param strategy: (default=None) The name or extension (starting with a dot) of some 
      protocol-specific strategy (a concrete subclass of this class) to use to 
      encode *obj*. If *strategy* is an extension matched by more than one
      strategy, the preferred one (see *preferred*) is used. If *strategy* is
      missing or None, each strategy is tried in turn until one succeeds: those
      for *url*'s extension first (preferred ones first), then the rest (see
      *_tryInOrder()*).
    :type strategy: Optional[str] 
    :param kwargs: A set of keyword arguments to be passed to concrete subclass.
    :type kwargs: dict[str, Any]
    :returns: An object read from *url* 
    :rtype: SerializableType
    :raises NotImlementedError: If the subclass failed to implement one of its
      required methods.
    
    Converts a byte array to an object using *_decode_()* and 
    *_speicializeBytes()*.

    :param replaceExt:
    :type replaceExt: bool | None
    :param mode:
    :type mode: str
    '''
    strat:Optional[SerializationStrategy] = None
    if strategy is not None:
      strat = cls.findStrategy(strategy)
      if strat is None:
        raise LookupError(f'SerializationStrategy.readx({url}): No strategy matching "{strategy}" found.')
    else:
      # (replaceExt=None: the file as named, whichever strategy reads it -- not one with that strategy's extension)
      return cls._tryInOrder(url, "readx", lambda strat: strat.read(url, replaceExt=None, mode=mode, **kwargs))
    return strat.read(url, replaceExt=replaceExt, mode=mode, **kwargs)

  @classmethod
  def _tryInOrder[R](cls, url:str, caller:str, action:Callable[[SerializationStrategy], R]) -> R:
    '''
    Try *action* with each available strategy in turn until one succeeds: those
    for *url*'s file extension first (preferred ones first: see *preferred*),
    then the rest -- eg: a ".xml" file written by one of several XML strategies,
    or a file whose extension isn't any strategy's.

    :raises OSError: At once, if *url* can't be opened (eg: it doesn't exist):
      no other strategy would do better.
    :raises LookupError: If every strategy fails; the message says why each did.
    :param url:
    :type url: str
    :param caller:
    :type caller: str
    :param action:
    :type action: Callable[[SerializationStrategy], R]
    :returns:
    :rtype: R
    '''
    parsed = urlparse(url)
    filename = os.path.basename(parsed.path)
    ext = "." + filename.rsplit(".", 1)[-1] if "." in filename else ""
    strats = cls._byPreference()
    order = [s for s in strats if s.extension == ext] + [s for s in strats if s.extension != ext]
    start = cls._start(url)
    if start:
      order.sort(key=lambda s: -cast(type[SerializationStrategy], s.cls).sniff(start)) # (stable: those surest they wrote it first, otherwise as they were)
    tried:str = ""
    for s in order:
      try:
        logger.debug(f'SerializationStrategy.{caller}({url}): Trying strategy {s.name}...')
        ret = action(cls.findStrategy(s.name))
      except (FileNotFoundError, IsADirectoryError, PermissionError):
        raise
      except Exception as ex:
        logger.debug(f'SerializationStrategy.{caller}({url}): {s.name}: failed: {ex.__class__.__name__}: {ex}.')
        tried += f'\n  {s.name}: {ex.__class__.__name__}: {ex}'
        continue
      if tried:
        logger.info(f'SerializationStrategy.{caller}({url}): read with {s.name} (after:{tried})')
      return ret
    raise LookupError(f'SerializationStrategy.{caller}({url}): No strategy succeeded. Tried:{tried}')

  @classmethod
  def _start(cls, url:str) -> bytes:
    '''
    :returns: The start of the file at *url* (see *SNIFF_SIZE*), if it's on
      this computer; else b"" (it isn't fetched just for this).
    '''
    parsed = urlparse(url)
    if parsed.scheme not in ("", "file"):
      return b""
    try:
      with open(unquote(parsed.path), "rb") as f:
        return f.read(cls.SNIFF_SIZE)
    except OSError:
      return b""

  @classmethod
  def peekTypex(cls, url:str, strategy:Optional[str]=None, mode:str="w", **kwargs) -> type:
    '''
    :param url: The URL to inspect. Use ``file:///absolute/path`` or
      ``file://relative/path`` for local files.
    :type url: str
    :param strategy: (default=None) The name or extension (starting with a dot) of some
      protocol-specific strategy to use. If missing or *None*, the strategy is
      inferred from *url*'s extension -- falling back to trying every known
      strategy in turn, exactly as :py:meth:`readx() <SerializationStrategy.readx>`
      does -- since a URL using a domain-specific extension (e.g. ".snv") won't
      match any registered strategy's own extension.
    :type strategy: Optional[str]
    :param kwargs: A set of keyword arguments to be passed to *_fromstring()*.
    :type kwargs: dict[str, Any]
    :returns: The class of the top-level object stored at *url*.
    :rtype: type
    :raises LookupError: If no strategy matches (or, when none is named, if
      every known strategy fails to peek at *url*).

    Classmethod counterpart to :py:meth:`readx() <SerializationStrategy.readx>`:
    resolves which strategy to use the same way, but calls
    :py:meth:`peekType() <SerializationStrategy.peekType>` instead of
    :py:meth:`read() <SerializationStrategy.read>` -- returning the top-level
    object's class WITHOUT constructing it (or anything it contains).

    :param mode:
    :type mode: str
    '''
    strat:Optional[SerializationStrategy] = None
    if strategy is not None:
      strat = cls.findStrategy(strategy)
      if strat is None:
        raise LookupError(f'SerializationStrategy.peekTypex({url}): No strategy matching "{strategy}" found.')
      return strat.peekType(url, mode=mode, **kwargs)
    else:
      return cls._tryInOrder(url, "peekTypex", lambda strat: strat.peekType(url, mode=mode, **kwargs))

  @classmethod
  @abstractmethod
  def defaultExtension(self) -> str:
    '''
    :returns:
    :rtype: str
    '''
    raise NotImplementedError("Call on abstract method SerializationStrategy.defaultExtension()")
  
  @classmethod
  @abstractmethod
  def protocolName(self) -> str:
    '''
    :returns:
    :rtype: str
    '''
    raise NotImplementedError("Call on abstract method SerializationStrategy.name()")
  
  @classmethod
  @abstractmethod
  def protocolVersion(self) -> str:
    '''
    :returns:
    :rtype: str
    '''
    raise NotImplementedError("Call on abstract method SerializationStrategy.version()")
  
  def write(self, url:str, obj:SerializableType, replaceExt:Optional[bool]=True, wrap:Union[bool,dict]=True, **kwargs) -> None:
    """
    Write an the data to a URL.
  
    For ``file:`` URLs the data is written directly to the local filesystem path.
    For all other schemes (e.g. ``http:``, ``https:``) the XML is uploaded via
    :func:`urllib.request.urlopen` as an HTTP PUT request with content-type
    ``application/xml``.
  
    :param url: The destination URL. Use ``file:///absolute/path`` or
      ``file://relative/path`` for local files.
    :type url: str
    :param obj: The object to serialise and write.
    :type obj: SerializableType
    :param replaceExt: If True, (the default) any extension will be replace with
      the default extension; if False, the default will extension will be 
      appended to the path if it's not already there; if None, nothing will
      be done to the path.
    :type replaceExt: Optional[bool]
    :param kwargs: A set of keyword arguments to be passed to concrete subclass.
    :type kwargs: dict[str, Any]
    :returns: None
    :rtype: None
    :raises ValueError: If *url* is an empty string.
    :raises FileNotFoundError: If the parent directory of a ``file:`` URL path
      does not exist.
    :raises urllib.error.URLError: If a remote URL cannot be reached.
  
    Usage::
  
      >>> tree = ET.parse("data.xml")
      >>> write("file:///tmp/output.xml", tree)
      >>> write("https://example.com/api/document", tree)

    :param wrap:
    :type wrap: Union[bool, dict]
    """
    parsedUrl:ParseResult
    url, parsedUrl = fixURL(url, replaceExt=replaceExt, mode="w", extension=self.defaultExtension())
    
    if parsedUrl.scheme == "file":
      localPath: str = parsedUrl.netloc + parsedUrl.path
      absolutePath: str = os.path.abspath(localPath)
      with open(unquote(absolutePath), "w", encoding="utf-8") as f:
        f.write(self.tostring(obj, wrap=wrap, **kwargs))
      return
  
    buf:bytes = self.tostring(obj, wrap=wrap, **kwargs).encode("utf-8")
    request:urllib.request.Request = urllib.request.Request(
      url,
      data=buf,
      method="PUT",
      headers={"Content-Type": "application/xml; charset=utf-8"},
    )
    with urllib.request.urlopen(request):
      pass
    
  def read(self, url:str, replaceExt:bool|None=True, mode="w", **kwargs) -> SerializableType:
    '''
    :param url: The source URL. Use ``file:///absolute/path`` or
      ``file://relative/path`` for local files.
    :type url: str
    :param replaceExt: If True, (the default) any extension will be replace with
      the default extension; if False, the default extension will be 
      appended to the path if it's not already there; if None, nothing will
      be done to the path.
    :type replaceExt: Optional[bool]
    :param kwargs: A set of keyword arguments to be passed to concrete subclass.
    :type kwargs: dict[str, Any]
    :returns: An object read from *buf* 
    :rtype: Any
    :raises NotImlementedError: If the subclass failed to implement one of its
      required methods.
    
    Converts a byte array to an object using *_decode_()* and
    *_speicializeBytes()*.

    :param mode:
    :type mode: str
    '''
    parsedUrl:ParseResult
    url, parsedUrl = fixURL(url, replaceExt=replaceExt, mode=mode, extension=self.defaultExtension())
    contents:str = self._fetchContents(url, parsedUrl)

    return self.fromstring(contents, **kwargs) # (which runs the final methods)

  def _fetchContents(self, url:str, parsedUrl:ParseResult) -> str:
    '''
    :param url: A URL already normalized by *fixURL()*.
    :type url: str
    :param parsedUrl: Its parsed form, as returned alongside it by *fixURL()*.
    :type parsedUrl: ParseResult
    :returns: The raw text found at *url*.
    :rtype: str
    :raises ValueError: If the URL's scheme isn't "file", "http", or "https".

    Shared by *read()* and *peekType()*: fetches the raw text a URL points
    to, with no interpretation of its content at all -- not even far enough
    to know what strategy it's meant for.
    '''
    scheme:str = parsedUrl.scheme.lower() if parsedUrl.scheme else "file"

    if scheme == "file":
      localPath:str = parsedUrl.path if parsedUrl.path else url
      localPath = unquote(localPath)
      with open(localPath, "r", encoding="utf-8") as f:
        return f.read()
    elif scheme in ("http", "https"):
      with urllib.request.urlopen(url) as response:
        rawBytes: bytes = response.read()
      return rawBytes.decode(encoding="utf-8")
    else:
      raise ValueError(f"Unsupported URL scheme: '{scheme}'. Use 'file', 'http', or 'https'.")

  def peekType(self, url:str, mode:str="w", **kwargs) -> type:
    '''
    :param url: The source URL to inspect.
    :type url: str
    :param mode: Passed through to *fixURL()* exactly as *read()* does.
    :type mode: str
    :param kwargs: Passed through to *_fromstring()*.
    :type kwargs: dict[str, Any]
    :returns: The class of the top-level ("root") object stored at *url*.
    :rtype: type
    :raises TypeError: If the declared type name can't be resolved to an
      actual class.
    :raises ValueError: If the URL's scheme isn't "file", "http", or "https".

    Learns what's stored at *url* WITHOUT constructing it -- or anything it
    contains: parses just far enough to read the top-level object's declared
    "type" attribute, using exactly the same structural primitives
    (*_fromstring()*, *_getKVPair()*, *_getAttr()*) that *_decode_()* itself
    uses for that same lookup; it simply stops there instead of going on to
    call any constructor. *_fromstring()* returns a lightweight
    strategy-specific representation of the parsed document (an
    *ElementTree.Element* for XML, a plain *dict* for JSON) -- turning
    *bytes* into that shape, not into *Serializable* objects, so nothing in
    this method has any side effect on the object graph the document
    describes.

    This exists so callers who only need to know what a file *is* (e.g.
    :py:meth:`Application.openWindow() <sn.view.graphics.guiApp.Application.openWindow>`,
    which must tell a Model file from a SNGView file before deciding what to
    do) don't have to fully read -- and thereby construct and register --
    the object just to find out.

    .. Important::
      This default implementation is only correct for a strategy whose
      *_fromstring()* returns a representation that doesn't itself construct
      any *Serializable* object -- true of :py:class:`XMLSerializationStrategy
      <util.persistence.serializeXML.XMLSerializationStrategy>` and
      :py:class:`JSONSerializationStrategy
      <util.persistence.serializeJSON.JSONSerializationStrategy>`, both of
      which only ever produce an inert data structure at the *_fromstring()*
      stage. A strategy for which parsing and object construction are
      inherently fused -- e.g. one based on Python's *pickle* protocol,
      where finding a class name ordinarily means unpickling -- MUST
      override this method with its own cheap, format-specific technique
      (for *pickle*, overriding *Unpickler.find_class()* to record the class
      and raise before any GLOBAL/REDUCE opcode actually builds anything is
      the standard trick). Inheriting this default for such a strategy would
      silently make *peekType()* just as expensive, and just as
      side-effecting, as a full *read()* -- defeating its purpose.
    '''
    className = self.readHead(url, mode=mode, **kwargs).get(HEAD_TYPE)
    if not isinstance(className, str):
      raise TypeError(f'SerializationStrategy.peekType({url}): it doesn\'t say what\'s in it.')
    cls:Optional[type] = getClassFromFullyQualifiedName(className)
    if cls is None:
      raise TypeError(f'SerializationStrategy.peekType({url}): Could not find type "{className}".')
    return cls
  
  def peekString(self, url:str, section:str, key:str, mode:str="w", **kwargs) -> Optional[str]:
    '''
    :returns: The value of string property *key* of the *section* ("header" or
      "root") of the document at *url* -- eg: ("root", "url") for a stored
      PRDb's URL -- or None if there isn't one (or it isn't a string). Like
      *peekType()*, nothing in the document is constructed.
    :param url:
    :type url: str
    :param section:
    :type section: str
    :param key:
    :type key: str
    :param mode:
    :type mode: str
    :param kwargs:
    :type kwargs:
    '''
    headValue = self.readHead(url, mode=mode, **kwargs).get(key) # (since VERSION 2.0, what's of interest is in the head)
    if isinstance(headValue, str):
      return headValue
    if section in (HEAD, OLD_HEADER):
      return None
    url, parsedUrl = fixURL(url, replaceExt=None, mode=mode, extension=self.defaultExtension())
    contents:str = self._fetchContents(url, parsedUrl)
    top:T = self._fromstring(contents, kwargs)
    part:Optional[T] = self._getKVPair(top, section)
    if part is None:
      if section != "root":
        return None
      part = top # not a "header"/"root"-wrapped document -- the top-level element IS the object.
    try:
      value = self._getKVPair(part, key)
      if value is None or self._getAttr(value, ATTR_TYPE) != "str":
        return None
      return self._decodeStr(value)
    except Exception:
      return None

  @classmethod
  def peekStringx(cls, url:str, section:str, key:str, mode:str="w", **kwargs) -> Optional[str]:
    '''
    Like *peekString()*, choosing the strategy as *readx()* does.

    :param url:
    :type url: str
    :param section:
    :type section: str
    :param key:
    :type key: str
    :param mode:
    :type mode: str
    :param kwargs:
    :type kwargs:
    :returns:
    :rtype: Optional[str]
    '''
    return cls._tryInOrder(url, "peekStringx", lambda strat: strat.peekString(url, section, key, mode=mode, **kwargs))

  def tostring(self, obj:SerializableType, *, wrap:Union[bool,dict]=False, assume:list[Any]=[], **kwargs) -> str:
    """
    Return the data as a strategy-specific formatted string.

    :param obj: The object to serialise and returned.
    :type obj: SerializableType
    :param wrap: If False, just *obj* is written. Otherwise it's written as a
      **document**: a head, then *obj* (the document's object). The head is a
      table of plain values (see *HeadValue*) -- the format, the versions, the
      application, *obj*'s class, when it was written (see *makeHead()*); what
      *obj* adds (its *serializationHeader()*, if it has one); its parameters
      and properties marked *inHead* (see *ParamInfo.inHead*), which aren't
      written with it; and *wrap*'s, if it's a *dict*. It's written first, so
      it can be read without reading the rest (see *readHead()*). The
      strategy decides how (see *_tostringDocument()*).
    :type wrap: Union[bool,dict]
    :returns: The serialized object as a string.
    :rtype: str
    :param assume:
    :type assume: list[Any]
    :param kwargs:
    :type kwargs:
    """
    self.writeDB:dict[int, Optional[T]] = dict()
    for o in assume:
      self.writeDB[id(o)] = None
    try:
      if not wrap:
        return self._tostring(self._encode_(obj), kwargs)
      head = self.makeHead(obj)
      if isinstance(wrap, dict):
        head.update(wrap)
      own:dict[str, HeadValue] = {}
      self._writingHead:Optional[tuple[Any, dict[str, HeadValue]]] = (obj, own) # (see _encode_(): its inHead properties go in it)
      body = self._encode_(obj)
      self._writingHead = None
      first = [HEAD_FORMAT, HEAD_FORMAT_VERSION, HEAD_SERIALIZATION_VERSION, HEAD_APPLICATION, HEAD_APPLICATION_VERSION, HEAD_TYPE]
      head = {**{k: head[k] for k in first if k in head}, **own, **{k: v for k, v in head.items() if k not in first}}
      for k, v in head.items():
        if not isHeadValue(v):
          raise TypeError(f'"{k}" can\'t be in a head: {v!r} isn\'t a plain value (see HeadValue).')
      return self._tostringDocument(head, body, kwargs)
    finally:
      self._writingHead = None
      self.writeDB = dict()

  def makeHead(self, obj:SerializableType) -> dict[str, HeadValue]:
    '''
    :param obj: A document's object (see *tostring()*).
    :type obj: SerializableType
    :returns: Its document's head: the format and the versions, the
      application, *obj*'s class, the time; and what *obj* adds (its
      *serializationHeader()*, if it has one).
    :rtype: dict[str, HeadValue]
    '''
    head:dict[str, HeadValue] = {
      HEAD_FORMAT: self.protocolName(),
      HEAD_FORMAT_VERSION: self.protocolVersion(),
      HEAD_SERIALIZATION_VERSION: VERSION,
      HEAD_APPLICATION: str(self.appName),
      HEAD_APPLICATION_VERSION: str(self.appVersion),
      HEAD_TYPE: getFullClassName(type(obj)),
      HEAD_SAVED: datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
      }
    extra = getattr(obj, "serializationHeader", None) # (the object's own head fields, eg: PRDb's url)
    if callable(extra):
      head.update({k: v for k, v in extra().items() if v is not None})
    return head

  def _tostringDocument(self, head:dict[str, HeadValue], body:T, kwargs:dict[str, Any]) -> str:
    '''
    Write a document (see *tostring()*). By default, as a table of two
    entries, head first: *HEAD* (a table of the head's values) and *BODY*.
    A strategy may write it its own way (eg: two values one after another;
    see *XML3SerializationStrategy*), so long as *_fromstringDocument()*
    reads it, and the head comes first.

    :param head:
    :type head: dict[str, HeadValue]
    :param body: The document's object, encoded.
    :type body: T
    :param kwargs:
    :type kwargs: dict[str, Any]
    :returns:
    :rtype: str
    '''
    doc = self._encodeStrdict()
    self._setKVPair(doc, HEAD, self._encode_(strdict(head)))
    self._setKVPair(doc, BODY, body)
    return self._tostring(doc, kwargs)

  def _fromstringDocument(self, string:str, kwargs:dict[str, Any]) -> tuple[dict[str, HeadValue], T]:
    '''
    Read a document (see *tostring()*, *_tostringDocument()*) -- or an old one
    (*OLD_HEADER*, *OLD_ROOT*), or just an object (an empty head, then).

    :param string:
    :type string: str
    :param kwargs:
    :type kwargs: dict[str, Any]
    :returns: Its head, and its object (still encoded).
    :rtype: tuple[dict[str, HeadValue], T]
    '''
    top = self._fromstring(string, kwargs)
    return self._documentParts(top)

  def _documentParts(self, top:T) -> tuple[dict[str, HeadValue], T]:
    '''
    :param top: The top of a document read with *_fromstring()*.
    :type top: T
    :returns: Its head, and its object (still encoded): see *_fromstringDocument()*.
    :rtype: tuple[dict[str, HeadValue], T]
    '''
    try:
      isTable = self._getAttr(top, ATTR_TYPE, None) == strdict_className
    except Exception:
      isTable = False
    if isTable:
      for headKey, bodyKey in ((HEAD, BODY), (OLD_HEADER, OLD_ROOT)):
        headElem, bodyElem = self._getKVPair(top, headKey), self._getKVPair(top, bodyKey)
        if headElem is not None and bodyElem is not None:
          decoded = self._decode_(headElem)
          return (dict(decoded) if isinstance(decoded, dict) else {}), bodyElem
    return {}, top

  def fromstring(self, string:str, **kwargs) -> SerializableType:
    """
    Return an object made from a strategy-specific formatted string: a
    document's object, if it's a document (see *tostring()*) -- its head is
    then *header*.

    :param string: The string to interpret.
    :type string: str
    :param kwargs: A set of keyword arguments to be passed to concrete subclass.
    :type kwargs: dict[str, Any]
    :returns: The object interpreted from *string*.
    :rtype: SerializableType
    """
    # (re-entrant: reading one document can read another -- eg: a PRDb's
    # super-DBs -- with this same strategy object, so the outer read's state
    # is kept aside, and put back afterwards)
    outer = (getattr(self, "readDB", dict()), self._finalMethodsList, getattr(self, "_readingHead", None))
    self.readDB:dict[int, SerializableType] = dict()
    self._finalMethodsList = []
    try:
      head, body = self._fromstringDocument(string, kwargs)
      self.header = head
      self._readingHead:Optional[tuple[Any, dict[str, HeadValue]]] = (body, head) # (see _decode_(): inHead properties are read from it)
      obj = self._decode_(body)
      for finalMethod in self._finalMethodsList:
        finalMethod()
    finally:
      self.readDB, self._finalMethodsList, self._readingHead = outer
    return obj

  def readHead(self, url:str, mode:str="", **kwargs) -> dict[str, HeadValue]:
    '''
    :param url: Where a document is.
    :type url: str
    :param mode: As for *fixURL()*.
    :type mode: str
    :returns: Its head (see *tostring()*) -- for an old document, its header,
      and its object's class (*HEAD_TYPE*). By default, the whole document is
      read (but no object in it is made); a strategy that can read just the
      start of it does (see *XML3SerializationStrategy*).
    :rtype: dict[str, HeadValue]
    '''
    url, parsedUrl = fixURL(url, replaceExt=None, mode=mode, extension=self.defaultExtension())
    head, body = self._fromstringDocument(self._fetchContents(url, parsedUrl), kwargs)
    head = dict(head)
    if HEAD_TYPE not in head:
      try:
        head[HEAD_TYPE] = self._getAttr(body, ATTR_TYPE)
      except Exception:
        pass
    return head

  @classmethod
  def readHeadx(cls, url:str, mode:str="", **kwargs) -> dict[str, HeadValue]:
    '''
    Like *readHead()*, choosing the strategy as *readx()* does.

    :param url:
    :type url: str
    :param mode:
    :type mode: str
    :returns:
    :rtype: dict[str, HeadValue]
    '''
    return cls._tryInOrder(url, "readHeadx", lambda strat: strat.readHead(url, mode=mode, **kwargs))

  SNIFF_SIZE:ClassVar[int] = 2048
  "How much of the start of a file is looked at to tell its format (see *sniff()*)."

  @classmethod
  def sniff(cls, start:bytes) -> int:
    '''
    :param start: The start of a file (see *SNIFF_SIZE*).
    :type start: bytes
    :returns: How sure this strategy is that it wrote it: 0 (not at all, or
      can't tell) up -- eg: 1 for the right kind of file (XML), 2 for one in
      its own format. Strategies that are surer are tried first (see
      *_tryInOrder()*).
    :rtype: int
    '''
    return 0

  ### PRIVATE METHODS _MUST_ BE IMPLEMENTED BY CONCRETE SUBCLASSES #####################
  
  @abstractmethod
  def _tostring(self, obj:T, kwargs:dict[str,Any]) -> str:
    """
    :param obj: The object to be serialized.
    :type obj: SerializableType
    :param kwargs: A set of keyword arguments to be passed to concrete subclass.
      This is passed as dict rather than with the ** syntax so that concrete
      subclasses can ignore unexpected arguments gracefully (as they should).
    :type kwargs: dict[str, Any]
    :returns: The serialized object as a string. 
    :rtype: str

    Return the data as a strategy-specific formatted string. Called by 
    :py:meth:`tostring() <SerializationStrategy.tostring>`.
  
    """
    raise NotImplementedError("Call on abstract method SerializationStrategy._tostring()")
    
  @abstractmethod
  def _fromstring(self, string:str, kwargs:dict[str,Any]) -> T:
    """
    Return an object made from a strategy-specific formatted string. Called by 
    :py:meth:`fromstring() <SerializationStrategy.fromstring>`.
  
    :param string: The string to interpret.
    :type string: str
    :param kwargs: A set of keyword arguments to be passed to concrete subclass.
      This is passed as dict rather than with the ** syntax so that concrete
      subclasses can ignore unexpected arguments gracefully (as they should).
    :type kwargs: dict[str, Any]
    :returns: The object interpreted from *string*.
    :rtype: SerializableType
    """
    raise NotImplementedError("Call on abstract method SerializationStrategy._fromstring()")
  
  @abstractmethod
  def _encodeStr(self, obj:str) -> T:
    '''
    :param obj:
    :type obj: str
    :returns:
    :rtype: T
    '''
    raise NotImplementedError(f'Class {self.__class__.__name__} failed to implement abstract method _encodeStr().')
    
  @abstractmethod
  def _decodeStr(self, readerObj:T) -> str:
    '''
    :param readerObj:
    :type readerObj: T
    :returns:
    :rtype: str
    '''
    raise NotImplementedError(f'Class {self.__class__.__name__} failed to implement abstract method _decodeStr().')
    
  @abstractmethod
  def _encodeList(self) -> T:
    '''
    :returns:
    :rtype: T
    '''
    raise NotImplementedError(f'Class {self.__class__.__name__} failed to implement abstract method _encodeList().')
    
  @abstractmethod
  def _decodeList(self, readerObj:T) -> list[T]:
    '''
    :param readerObj:
    :type readerObj: T
    :returns:
    :rtype: list[T]
    '''
    raise NotImplementedError(f'Class {self.__class__.__name__} failed to implement abstract method _decodeList().')
    
  ## PRIMITIVES USED BY OTHER OPTIONAL IMPLEMENTATIONS
  # It may not be necessary to implement them if you override the methods the use them.
  
  @abstractmethod
  def _setAttr(self, elem:T, name:str, value:str) -> None:
    '''
    Contract: _setAttr(elem, name, value) -> _getAttr(elem, naem) == value
    
    This method **must** be implemented if any of *_encodeInt(), _encodeFloat(), 
    _encodeBool(), _encodeTuple(), _encodeSet()*, or *_encodeSerializable()*
    are left the default implementations in this class. 
    
    May be called for ANY type.

    :param elem:
    :type elem: T
    :param name:
    :type name: str
    :param value:
    :type value: str
    '''
    raise NotImplementedError(f'Class {self.__class__.__name__} failed to implement abstract method _addAttr().')
    
  @abstractmethod
  def _getAttr(self, elem:T, name:str, default:Any=KeyError) -> Any:
    '''
    Contract: _setAttr(elem, name, value) -> _getAttr(elem, naem) == value
    
    This method **must** be implemented if any of *_decodeInt(), _decodeFloat(), 
    _decodeBool(), _decodeTuple(), _decodeSet()*, or *_decodeSerializable()*
    are left the default implementations in this class.
    
    May be called for ANY type.

    :param elem:
    :type elem: T
    :param name:
    :type name: str
    :param default:
    :type default: Any
    :returns:
    :rtype: Any
    '''
    raise NotImplementedError(f'Class {self.__class__.__name__} failed to implement abstract method _getAttr().')
    
  @abstractmethod
  def _appendItem(self, elem:T, newItem:T) -> None:
    '''
    May be called for list, tuple, and set types only.

    :param elem:
    :type elem: T
    :param newItem:
    :type newItem: T
    '''
    raise NotImplementedError(f'Class {self.__class__.__name__} failed to implement abstract method _appendItem().')
  
  @abstractmethod
  def _getItems(self, elem:T) -> list[T]:
    '''
    May be called for list, tuple, and set types only.

    :param elem:
    :type elem: T
    :returns:
    :rtype: list[T]
    '''
    raise NotImplementedError(f'Class {self.__class__.__name__} failed to implement abstract method _getItems().')
  
  @abstractmethod
  def _setKVPair(self, elem:T, key:T|str, value:T) -> None:
    '''
    :param elem: The T object to add the *key/value pair to. Must be a *dict* type, 
      *strdict* type, or a subtype of *Serializable* representation. 
    :type elem: T
    :param key: The key part, not that if *elem* is a regular *dict* representation,
      key must be a T type; but if *elem* is a *strdict* or subtype of *Serializable*,
      key must be a *str*.
    :type key: T|str
    :param value: The value part.
    :type value: T
    
    May be called for dict types, strdict types, and Serializable subtypes only. 
    '''
    raise NotImplementedError(f'Class {self.__class__.__name__} failed to implement abstract method _setKVPair().')
  
  @abstractmethod
  def _getKVPairs(self, elem:T) -> list[tuple[T,T]]|dict[str,T]:
    '''
    :param elem: The T object to deserialize to a *key/value pair. Must be a *dict* type, 
      *strdict* type, or a subtype of *Serializable* representation. 
    :type elem: T
    :returns: If elem represents a *dict* object, then the return must be a *tuple*;
      if *elem* represents a *strdict* or a subtype of *Serializable*, then
      the return must be a dict.
    :rtype: list[tuple[T,T]]|dict[str,T]
    
    May be called for dict types, strdict types, and Serializable subtypes only. 
    '''
    raise NotImplementedError(f'Class {self.__class__.__name__} failed to implement abstract method _getKVPair().')
  
  ## PRIVATE METHODS IMPLEMENTED HERE, BUT SHOULD PROBABLY BE IMPLEMENTED MORE
  ## EFFICIENTLY IN THE SUBCLASS

  def _getKVPair(self, elem:T, key:str) -> Optional[T]:
    '''
    May be called for strdict types Serializable subtypes only.

    :param elem:
    :type elem: T
    :param key:
    :type key: str
    :returns:
    :rtype: Optional[T]
    '''
    props = self._getKVPairs(elem)
    for k,v in props if isinstance(props, list) else props.items():
      if k == key:
        return v
    return None
  
  def _encodeInt(self, obj:int) -> T:
    '''
    :param obj:
    :type obj: int
    :returns:
    :rtype: T
    '''
    ret = self._encodeStr(str(obj))
    self._setAttr(ret, ATTR_TYPE, "int")
    return ret
    
  def _decodeInt(self, elem:T) -> int:
    '''
    :param elem:
    :type elem: T
    :returns:
    :rtype: int
    '''
    assert self._getAttr(elem, ATTR_TYPE) == "int"
    self._setAttr(elem, ATTR_TYPE, "str")
    return int(self._decodeStr(elem))
    
  def _encodeNone(self) -> T:
    '''
    :returns:
    :rtype: T
    '''
    ret = self._encodeStr("None")
    self._setAttr(ret, ATTR_TYPE, "NoneType")
    return ret
    
  def _decodeNone(self, elem:T) -> None:
    '''
    :param elem:
    :type elem: T
    '''
    assert self._getAttr(elem, ATTR_TYPE) == "NoneType"
    return None
    
  def _encodeFloat(self, obj:float) -> T:
    '''
    :param obj:
    :type obj: float
    :returns:
    :rtype: T
    '''
    ret = self._encodeStr(str(obj))
    self._setAttr(ret, ATTR_TYPE, "float")
    return ret
    
  def _decodeFloat(self, elem:T) -> float:
    '''
    :param elem:
    :type elem: T
    :returns:
    :rtype: float
    '''
    assert self._getAttr(elem, ATTR_TYPE) == "float"
    self._setAttr(elem, ATTR_TYPE, "str")
    return float(self._decodeStr(elem))
    
  def _encodeBool(self, obj:bool) -> T:
    '''
    :param obj:
    :type obj: bool
    :returns:
    :rtype: T
    '''
    ret = self._encodeStr(str(obj))
    self._setAttr(ret, ATTR_TYPE, "bool")
    return ret
    
  def _decodeBool(self, elem:T) -> bool:
    '''
    :param elem:
    :type elem: T
    :returns:
    :rtype: bool
    '''
    assert self._getAttr(elem, ATTR_TYPE) == "bool"
    self._setAttr(elem, ATTR_TYPE, "str")
    return self._decodeStr(elem) != "False"
    
  def _encodeTuple(self) -> T:
    '''
    :returns:
    :rtype: T
    '''
    elem:T = self._encodeList()
    self._setAttr(elem, ATTR_TYPE, "tuple")
    return elem
    
  def _decodeTuple(self, elem:T) -> tuple[T,...]:
    '''
    :param elem:
    :type elem: T
    :returns:
    :rtype: tuple[T, ...]
    '''
    assert self._getAttr(elem, ATTR_TYPE) == "tuple"
    self._setAttr(elem, ATTR_TYPE, "list")
    lst = self._decodeList(elem)
    return tuple(lst)
    
  def _encodeSet(self) -> T:
    '''
    :returns:
    :rtype: T
    '''
    elem:T = self._encodeList()
    self._setAttr(elem, ATTR_TYPE, "set")
    return elem
    
  def _decodeSet(self, elem:T) -> set[T]:
    '''
    :param elem:
    :type elem: T
    :returns:
    :rtype: set[T]
    '''
    assert self._getAttr(elem, ATTR_TYPE) == "set"
    self._setAttr(elem, ATTR_TYPE, "list")
    lst = self._decodeList(elem)
    return set(lst)
    
  def _encodeDict(self) -> T:
    '''
    :returns:
    :rtype: T
    '''
    elem = self._encodeList()
    self._setAttr(elem, ATTR_TYPE, "dict")
    return elem
    
  def _decodeDict(self, elem:T) -> list[tuple[T,T]]:
    '''
    :param elem:
    :type elem: T
    :returns:
    :rtype: list[tuple[T, T]]
    '''
    assert self._getAttr(elem, ATTR_TYPE) == "dict"
    ret = self._getKVPairs(elem)
    assert isinstance(ret, list)
    return ret
    
  def _encodeStrdict(self) -> T:
    '''
    :returns:
    :rtype: T
    '''
    elem = self._encodeList()
    self._setAttr(elem, ATTR_TYPE, strdict_className)
    return elem
    
  def _decodeStrdict(self, elem:T) -> dict[str,T]:
    '''
    :param elem:
    :type elem: T
    :returns:
    :rtype: dict[str, T]
    '''
    assert self._getAttr(elem, ATTR_TYPE) == strdict_className
    ret = self._getKVPairs(elem)
    assert isinstance(ret, dict)
    return ret
    
  def _encodeSerializable(self) -> T:
    '''
    :returns:
    :rtype: T
    '''
    ret = self._encodeStrdict()
    self._setAttr(ret, ATTR_TYPE, getFullClassName(Serializable))
    return ret
    
  def _decodeSerializable(self, elem:T) -> dict[str,T]:
    '''
    :param elem:
    :type elem: T
    :returns:
    :rtype: dict[str, T]
    '''
    typeName = self._getAttr(elem, ATTR_TYPE)
    typ = getFullyQualifiedClass(typeName)
    assert typ is not None
    assert issubclass(typ, Serializable)
    self._setAttr(elem, ATTR_TYPE, strdict_className)
    ret = self._decodeStrdict(elem)
    self._setAttr(elem, ATTR_TYPE, typeName)
    return ret
    
  ### METHODS THE MOST NOT BE OVERRIDDEN BY CONCRETE SUBCLASSES ################

  def _encode_(self, obj:SerializableType, unique:bool=False) -> T:
    '''
    ..note:
      Tuple members referencing the tuple **are NOT** supported.

    :param obj:
    :type obj: SerializableType
    :param unique:
    :type unique: bool
    :returns:
    :rtype: T
    '''
    def encodeClass(obj:Serializable, unique:bool) -> T:
      elem = self._encodeSerializable()
      if not isinstance(obj, _Reference):
        #self.writeDB[id(obj)] = elem
        registerMaybe(obj, elem, unique)
      self._setAttr(elem, ATTR_TYPE, getFullClassName(type(obj)))
      
      info:InstantiationInfo = obj.getInstantiationInfo()
      writing = getattr(self, "_writingHead", None)
      head = writing[1] if writing is not None and writing[0] is obj else None # (the document's object: its inHead ones go in the head)
      for lists in (info.conArgs, info.conKWArgs):
        for pinfo in lists:
          sub = pinfo.getter(obj)
          if head is not None and pinfo.inHead:
            head[pinfo.name] = list(sub) if isinstance(sub, tuple) else sub
            continue
          e = self._encode_(sub, pinfo.unique)
          self._setKVPair(elem, pinfo.name, e)

      for props in (info.postconSetters, info.finalSetters):
        for pinfo2 in props:
          sub = pinfo2.getter(obj)
          if sub is None and getattr(pinfo2, "omitIfNone", False):
            continue
          if head is not None and pinfo2.inHead:
            head[pinfo2.name] = list(sub) if isinstance(sub, tuple) else sub
            continue
          e = self._encode_(sub, pinfo2.unique)
          self._setKVPair(elem, pinfo2.name, e)
      return elem
    
    def registerMaybe(obj:SerializableType, elem:T, unique:bool):
      if not unique:
        self.writeDB[id(obj)] = elem
    #------     
    # interned types: we don't have to worry about multiple references... 
    if obj is None:
      return self._encodeNone()
    elif type(obj) is int:
      return self._encodeInt(obj)
    elif type(obj) is float:
      return self._encodeFloat(obj)
    elif type(obj) is str:
      return self._encodeStr(obj)
    elif type(obj) is bool:
      return self._encodeBool(obj)

    # non-interned types: There might be multiple references to these, 
    # so we need to keep track and subsitute a reference if necessary
    id_ = id(obj)
    value = self.writeDB.get(id_, 0)
    elem:T
    if value == 0:
      # there is no entry, so record its id and make the T object,
      # or this is a reference to a previously stored object so always record those
      if isinstance(obj, Serializable):
        elem = encodeClass(obj, unique)
      elif type(obj) is list:
        elem = self._encodeList()
        #self.writeDB[id_] = elem
        registerMaybe(obj, elem, unique)
        for o in obj:
          self._appendItem(elem, self._encode_(o, unique))
      elif type(obj) is tuple:
        elem = self._encodeTuple()
        #self.writeDB[id_] = elem
        registerMaybe(obj, elem, unique)
        for o in obj:
          self._appendItem(elem, self._encode_(o))
      elif type(obj) is set:
        elem = self._encodeSet()
        #self.writeDB[id_] = elem
        registerMaybe(obj, elem, unique)
        for o in obj:
          self._appendItem(elem, self._encode_(o))
      elif isinstance(obj, strdict):
        elem = self._encodeStrdict()
        #self.writeDB[id_] = elem
        registerMaybe(obj, elem, unique)
        for k,v in obj.items():
          self._setKVPair(elem, k, self._encode_(v))
      elif type(obj) is dict:
        elem = self._encodeDict()
        #self.writeDB[id_] = elem
        registerMaybe(obj, elem, unique)
        for k,v in obj.items():
          self._setKVPair(elem, self._encode_(k), self._encode_(v))
      else:
        raise TypeError(f'Unsupported type: "{obj.__class__.__name__}".') 
    else: # we have seen this object before: make a reference to it
      assert not isinstance(obj, _Reference)
      if value is not None: # this is the first reference seen (after the original)
        self._setAttr(cast(T, value), "id", str(id_))
        #self.writeDB[id_] = None # clear the element so that we don't record it's id again
      elem = self._encode_(_Reference(id_), True) # return a reference object referring to the original   
    return elem
    
  def _decode_(self, elem:T) -> SerializableType:

    '''
    :param elem:
    :type elem: T
    :returns:
    :rtype: SerializableType
    '''
    def decodeClass(elem:T):
      reading = getattr(self, "_readingHead", None)
      head = reading[1] if reading is not None and reading[0] is elem else None # (the document's object: see tostring())

      def getParams(desc:list[ParamInfo]) -> list[tuple[str, SerializableType]]: 
        ret:list[tuple[str, SerializableType]] = []
        pinfo:ParamInfo
        for pinfo in desc:
          if head is not None and pinfo.inHead and pinfo.name in head: # (an old document has it with the object)
            ret.append((pinfo.name, pinfo.setter(head[pinfo.name])))
            continue
          sub:Optional[T] = self._getKVPair(elem, pinfo.name)
          if sub is None:
            if getattr(pinfo, "optional", False):
              continue
            raise LookupError(f'Subelement parameter named "{pinfo.name}" not found.')# in Element "{elem.tag}" of type {elem.attrib[ATTR_TYPE]}.')
          if not (pinfo.typ is None or \
                 issubclass(cast(type, getFullyQualifiedClass(self._getAttr(sub, ATTR_TYPE))), pinfo.typ) \
                 or self._getAttr(sub, ATTR_TYPE) == REF_CLASSNAME):
            raise AssertionError(f'{pinfo.name}: not ({getFullClassName(pinfo.typ)} <: {self._getAttr(sub, ATTR_TYPE)})')
          value = self._decode_(sub)
          assert not isinstance(value, _Reference)
          ret.append((pinfo.name, pinfo.setter(value)))
        return ret
      
      def getSetters(desc:list[PropertyInfo]) -> list[tuple[str, Callable[[Serializable], None]]]: 
        ret:list[tuple[str, Callable[[Serializable], None]]] = []
        pinfo:PropertyInfo
        for pinfo in desc:
          if head is not None and pinfo.inHead and pinfo.name in head: # (an old document has it with the object)
            ret.append((pinfo.name, lambda slf, method=pinfo.setter, value=head[pinfo.name]: method(slf, value))) # type: ignore[misc]
            continue
          if pinfo.name == '_':
            sub:Optional[T] = None
          else:
            sub = self._getKVPair(elem, pinfo.name)
            if sub is None:
              if getattr(pinfo, "optional", False):
                continue
              raise LookupError(f'Subelement property named "{pinfo.name}" not found.')# in Element "{elem.tag}" of type {elem.attrib[ATTR_TYPE]}.')
          assert pinfo.typ is None or sub is None or \
                 issubclass(cast(type, getFullyQualifiedClass(self._getAttr(sub, ATTR_TYPE))), pinfo.typ) \
                 or self._getAttr(sub, ATTR_TYPE) == REF_CLASSNAME, \
                 f'not ({getFullClassName(pinfo.typ)} <: {self._getAttr(sub, ATTR_TYPE)})'
          value = self._decode_(sub) if sub is not None else None
          assert not isinstance(value, _Reference)
          # if isinstance(value, _Reference):
          #   self._decode_(sub)
          ret.append((pinfo.name, \
                      lambda slf, method=pinfo.setter, # type: ignore[misc]
                        value=value: 
                          method(slf, value))) 
        return ret
      
      className = self._getAttr(elem, ATTR_TYPE)
      cls = getClassFromFullyQualifiedName(className)
      if cls is None:
        raise TypeError(f'Could not find type "{className}"')
      
      info:InstantiationInfo = getInstantiationInfo(className)
      
      
      params = getParams(info.conArgs)
      args:list = [x[1] for x in params] # convert from (name,setter) pairs to list of setters
      params = getParams(info.conKWArgs)
      kwargs:dict[str,Any] = dict(params) # convert from (name,setter) pairs to dict of {name:setter}
      
      try:
        ret = cls(*args, **kwargs) # call the constructor
        # if this object has an id attribute, put it's address in the readDB
        registerMaybe(elem, ret)
      except Exception as ex:
        #these exceptions will be trapped by argparse and will be dumped, so log them here.
        className = cls.__name__
        logger.exception(f'Failed to instantiate object of class {className}')
        return None
       
      setters = getSetters(info.postconSetters)
      for vname, meth in setters:
        try:
          meth(ret) 
        except Exception as ex:
          #these exceptions will be trapped by argparse and will be dumped, so log them here.
          className = cls.__name__
          logger.exception(f'Failed to get postconSetter "{className}.{vname}"')

      setters = getSetters(info.finalSetters)
      for _, meth in setters: 
        self._finalMethodsList.append(lambda slf=ret, method=meth : method(slf))
      return ret
    
    def registerMaybe(elem:T, obj:SerializableType):
      # if this object has an id attribute, put it's address in the readDB
      id_ = self._getAttr(elem, "id", None)
      if id_ is not None:
        if isinstance(obj, _Reference):
          assert False
        self.readDB[int(id_)] = obj      
    
    #---------
    
    className = self._getAttr(elem, ATTR_TYPE)
    cls = getClassFromFullyQualifiedName(className)
    if cls is None:
      raise TypeError(f'Could not find type "{className}"')
  
    # interned types: we don't have to worry about multiple references... 
    if cls is NoneType:
      return self._decodeNone(elem) # type: ignore[func-returns-value]
    elif cls is int:
      return self._decodeInt(elem)
    elif cls is float:
      return self._decodeFloat(elem)
    elif cls is str:
      return self._decodeStr(elem)
    elif cls is bool:
      return self._decodeBool(elem)
    
    # non-interned types: There might be multiple references to these, so we need to keep track.
    obj:SerializableType
    if issubclass(cls, Serializable):
      obj = decodeClass(elem)#self._decodeSerializable(elem)
      if isinstance(obj, _Reference):
        try:
          ret = self.readDB[obj.referenceID]
          if isinstance(ret, _Reference): # make sure a ref doesn't refer to another ref
            assert False
          return ret
        except KeyError:
          raise KeyError(f'Cannot find key "{obj.referenceID}" in {self.readDB}')
        
    elif cls is list:
      obj = []
      registerMaybe(elem, obj)
      elems:list = self._decodeList(elem)
      obj.extend([self._decode_(e) for e in elems])
    elif cls is tuple:
      # objects within tuples referencing the tuple ARE NOT SUPPORTED!
      obj = tuple([self._decode_(e) for e in self._decodeTuple(elem)])
      registerMaybe(elem, obj) # not helpful for the contained objects, but needed for the rare interned tuple 
    elif cls is set:
      obj = set()
      registerMaybe(elem, obj)
      elemsSet:set = self._decodeSet(elem)
      obj.update([self._decode_(e) for e in elemsSet])
    elif cls is dict:
      obj = dict()
      registerMaybe(elem, obj)
      pairs = self._decodeDict(elem)
      for k,v in pairs:
        obj[self._decode_(k)] = self._decode_(v)
    elif cls is strdict:
      obj = dict()
      registerMaybe(elem, obj)
      dic:dict[str,T] = self._decodeStrdict(elem)      
      for k1,v1 in dic.items():
        obj[k1] = self._decode_(v1)
    else:
      raise TypeError(f'Unsupported type: "{className}".')
    
    return obj


def _populateKnownStrategiesAtLoad() -> None:
  '''
  Discover and instantiate every concrete :py:class:`SerializationStrategy`
  subclass in this package (*util.persistence*) right now, at module load
  time -- so :py:attr:`SerializationStrategy.knownStrategies` already lists
  e.g. *JSONSerializationStrategy* and *XMLSerializationStrategy* the
  moment this module finishes importing, rather than only lazily, the
  first time something calls :py:meth:`getAvailableStrategies()
  <SerializationStrategy.getAvailableStrategies>` or constructs a strategy
  directly.

  Delegates entirely to :py:meth:`getAvailableStrategies()
  <SerializationStrategy.getAvailableStrategies>` for the actual package
  scan -- it already does exactly the "import every not-yet-loaded module
  in *util.persistence* whose name starts with 'serialize', then collect
  every concrete *SerializationStrategy* subclass" work this needs (e.g.
  *serializeJSON.py*/*serializeXML.py*, sibling modules of this one that
  subclass *SerializationStrategy* but, at this point in loading THIS
  module, haven't been imported by anything yet). Modules like
  *x_persistenceXML.py*, whose name doesn't start with "serialize", are
  left alone, same as they are for *getAvailableStrategies()* itself.

  Each discovered class is instantiated once. Its own *__init__()* has
  already inserted a record for it at *knownStrategies[0]* holding a
  *weak* reference (see *__init__()* above) -- which, with nothing else
  in the program yet holding a reference to this just-created instance,
  would make it eligible for garbage collection the instant this function
  returns, silently emptying the record back out from under
  *knownStrategies*. So that record's *obj* is upgraded here to hold the
  instance directly instead -- the same "keep this strat in memory" idiom
  *findStrategy()*'s own fallback path above already uses when IT
  discovers and instantiates a strategy this way.

  Called once, immediately below, then discarded -- this is a one-shot
  module-load bootstrap step, not part of the class's ongoing API.

  :rtype: None
  '''
  for strat in SerializationStrategy.getAvailableStrategies():
    assert isinstance(strat, SerializationStrategy.Strategy)
    instance = strat.cls()
    SerializationStrategy.knownStrategies[0].obj = instance

_populateKnownStrategiesAtLoad()
del _populateKnownStrategiesAtLoad


class _Reference(Serializable):
  '''
  A reference to an object already written, by its id: how an object referred to more than once is written only once.
  '''
  def __init__(self, referenceID:int) -> None:
    '''
    :param referenceID:
    :type referenceID: int
    '''
    super().__init__()
    self.referenceID:int = referenceID
    
  @override
  @classmethod
  def getInstantiationInfo(cls)->InstantiationInfo:
    return InstantiationInfo(cls, [ParamInfo("referenceID", int)])
  
  @override
  def __repr__(self) -> str:
    '''
    :returns:
    :rtype: str
    '''
    return f'_Reference({self.referenceID})@{id(self)}'


REF_CLASSNAME = getFullClassName(_Reference)

