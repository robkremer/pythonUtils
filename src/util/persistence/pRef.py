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

.. inheritance-diagram:: PReference PRObject PRDb
    :parts: 3
    :private-bases:
    :top-classes: object


'''
from __future__ import annotations

from typing import Iterator, ItemsView, KeysView, ValuesView, Optional, Union,\
  override, cast, Callable, Self, ClassVar
from abc import abstractmethod
from weakref import ref, ReferenceType
from util.utils import openUrl, urlExists, isValidURL, fixURL
from urllib.parse import unquote, quote, urlparse
#import xml.etree.ElementTree as ET
from util.persistence.serialize import Serializable, InstantiationInfo,\
  ParamInfo, PropertyInfo, SerializationStrategy, strdict
from pathlib import Path
import re
import logging
from urllib3.util.url import parse_url
import util

logger:util.Logger = util.getLogger(__name__)

class DuplicateNameError(Exception):
  """Raised when a name lookup matches more than one PRObject."""

class MalformedIDError(Exception):
  """Raised a PReference is syntactically incorrect."""


class PRObject[DBT:"PRDb"](Serializable):
  '''
  An object with an immutable integer ID and a mutable name.
  '''

  def __init__(self, db:DBT) -> None:
    '''
    :param db: The db to which this object will belong.
    :type db: PRDb
    :raises PermissionError: If the DB is write locked.
    :raises TypeError: If the *value* is not of type *PRObject*.
    :raises MemoryError: if the DB has been deleted.
    '''
    if not isinstance(db, PRDb):
      raise TypeError(f"db must be an PRDb, got {type(id).__name__}")
    self._db:ReferenceType = ref(db) # weak reference as the db will maintain references to this object
    self._url = self.db.url
    self._id: int = db._register(self)

  @override
  @classmethod
  def getInstantiationInfo(cls) -> InstantiationInfo:
    return InstantiationInfo(
            cls, 
            conArgs=[ParamInfo("db", PRDb, lambda slf: cast(PRObject, slf)._db())])#,
            #postconSetters=[PropertyInfo("_id", int)])

  @property
  def id(self) -> int:
    '''
    :returns: this object\'s ID in its DB.
    :rtype: int
    '''
    return self._id

  @property
  def db(self) -> DBT:
    '''
    :returns: this object\'s ID.
    :rtype: :py:class:'`PRDb`
    :raises MemoryError: if the DB has been deleted.
    '''
    ret:DBT|None = self._db()
    # if ret is None:
    #   self._db = ref(PRDb.getDB(self._url))
    #   ret = self._db()
    #   if ret is None:
    #     raise MemoryError('Object\'s database has been deleted.')
    if ret is None:
      raise MemoryError('Object\'s database has been deleted.')
    return ret

  @property
  @abstractmethod
  def name(self) -> str:
    '''
    :returns: this object\'s (usually mutable) name.
    :rtype: str
    
    .. Note::
    
      This is an abstract method (property) used to resolve persistent references
      of the for <url>#<string-name>.
    '''
    pass
  
  def getPRef(self) -> PReference[Self]:
    '''
    Returns a new :py:class:`PReference` object referencing this object.
    '''
    if self.db is None:
      raise AttributeError("PRObject has no DB.")
    ret:PReference = PReference(f'{self.db.url}#{str(self.id)}')
    ret.obj = self # TODO: efficient, but do we want this?
    return ret
    
  @override
  def __repr__(self) -> str:
    return f'{self.__class__.__name__}({(self.db.url if self.db is not None else "None")}, ID={self.id!r}, name={self.name!r})'
  
  def torepr(self, relativeTo:DBT) -> str:
    url = self.db.url if self.db is not None else "None"
    return f'{self.__class__.__name__}({url}, ID={self.id!r}, name={self.name!r})'

  @override
  def __str__(self) -> str:
    return self.tostring()
  
  def tostring(self, relativeTo:DBT|None=None) -> str:
    return f'{self.__class__.__name__}({self.name}, {self.getPRef().tostring(relativeTo)})'
  
  @override
  def __eq__(self, other: object) -> bool:
    '''
    :returns: True iff the two are PRObjects with their *db* identical and *name*
    and *id* equal.
    :rtype: bool
    '''
    if isinstance(other, PRObject):
      return self.id == other.id and self.name == other.name and self.db is other.db
    return False
  
  @override
  def __hash__(self):
    return hash(str(self.getPRef()))


class PRContainer[DBT:"PRDb"](PRObject[DBT]):
  @abstractmethod
  def getMembers(self) -> Iterator[PRObject[DBT]]:
    pass

  
class PRDbContainer[DBT:"PRDb"](PRContainer[DBT]):
  @override
  def getMembers(self) -> Iterator[PRObject[DBT]]:
    for item in self.db.values():
      yield item
      
  @override
  @property
  def name(self)->str:
    return self.db.name
  
  
class PRDb[T:PRObject](Serializable):
  """
  A dict-like object whose keys are restricted to int and values to PRObject.

  __getitem__() and related lookup methods accept either:
    - an int  -> direct key lookup by ID
    - a str   -> lookup by PRObject.name (raises DuplicateNameError if ambiguous)
    
  METHODS PURPOSELY NOT IMPLEMENTED:
  
    - __setitem__() (index assignment) is NOT implemented.  Instead, the constructor
        of PRObject calls *PRDb._register()* to obtain an id and insert itself into
        the *PRDb*.
    - update()
  """
  
  AllDBs:ClassVar[dict[str, PRDb]] = dict()
  
  @classmethod
  def _initCache(cls):
    '''
    Re-initializes the cache. 
    
    .. Warning::
    
       This should only be used for testing purposes (eg: unit testing) as it wipes
       the DB cache and could cause bad pointers in any interface applications.
    
    .. Note::
    
      Subclasses should override to do whatever needs to be done for "blank" cache.
    '''
    cls.AllDBs = dict()
    
  @classmethod
  def getDB(cls, url:str, mode="w") -> Self:
    '''
    :param url: The name of the db as a file name or a URL.
    :type url: str
    :returns: The DB read from disk or from the web.
    :rtype: :py:class:`PRDb`
    :raises FileNotFoundError: If a ``file:`` URL points to a path that does not
      exist.
    :raises ValueError: if the *url* is malformed.
    :raises urllib.error.URLError: If a remote URL cannot be reached.

    Either return the DB from memory or attempt to read it from disk or 
    from the web.
    '''
    # process a path prefixed $ by looking it up in memory first
    assert url is not None
    if url.startswith("$") and len(url) > 1:
      path = url[1:] # strip the $
      for k in PRDb.AllDBs:
        p = urlparse(k).path # path part of the url
        p = p[p.rfind("/")+1:p.rfind(".")] # find just the "file name"
        if p == path:
          url = k # found a match, so carry on with the matched full path
          break
           
    url = fixURL(url, extension=".xml", replaceExt=None, mode="")[0] # get it without checking access
    if not isValidURL(url):
      raise ValueError(f'Malformed URL: "{url}"')
    if url in PRDb.AllDBs:
      return cast(Self, PRDb.AllDBs[url])
    return cls._read(url, mode=mode)
      
  @classmethod
  def _read(cls, url:str, mode="w") -> Self:
    '''
    :param url: The URL to fetch. May use any scheme supported by
      :mod:`urllib.request`, plus the ``file:`` protocol for local filesystem
      paths.
    :type url: str
    :returns: Raw byte content of the resource, suitable for passing directly to
      an XML parser (e.g. :func:`xml.etree.ElementTree._fromstring` or
      :class:`lxml.etree.XMLParser`).
    :rtype: bytes
    :raises ValueError: If *url* is an empty string.
    :raises FileNotFoundError: If a ``file:`` URL points to a path that does not
      exist.
    :raises urllib.error.URLError: If a remote URL cannot be reached.
    
    Read the DB from disk or from the web and instantiate it.
    Subclasses should implement this method to actually do the read; this 
    version merely raises the exception.
    '''
    url = fixURL(url, extension=".xml", replaceExt=None, mode=mode)[0]
    if not isValidURL(url):
      raise ValueError(f'Malformed URL: "{url}"')
    if url in PRDb.AllDBs:
      raise DuplicateNameError(f'PRDb._read(): A DB with name "{url}" already exists.')
    read = SerializationStrategy.readx(url, mode=mode)
    assert isinstance(read, cls)
    ret:Self = read
    if not isinstance(ret, PRDb):
      raise TypeError(f'PRDb._read(): Expected a PRDb in "{url}"; got type {str(type(ret))}.')
    if ret.url != url:
      logger.warning(f'DB read from "{url}" appears to have been copied from "{ret.url}". Changing its internal URL.')
      PRDb.AllDBs[url] = ret
      del PRDb.AllDBs[ret.url]
      ret.url = url
    return ret
  
  def __new__(cls, url:str, mode="w", _reading:bool=False):
    assert issubclass(cls, PRDb)
    url = fixURL(url, extension=".xml", replaceExt=None, mode=mode)[0]
    if not isValidURL(url):
      raise ValueError(f'PRDb.__init__(): Malformed URL: "{url}"')
    if url in PRDb.AllDBs:
      setattr(PRDb.AllDBs[url], "_initialized", True)
      return PRDb.AllDBs[url]
    if urlExists(url) and not _reading:
      ret = cls._read(url)
      PRDb.AllDBs[url] = ret
      setattr(ret, "_initialized", True)
      return ret
    return super().__new__(cls)
  
  def  __init__(self, url:str, mode="w", _reading:bool=False):
    '''
    :param url: The URL to associate with this object. Can be a filename, interpreted
      in the context of the current directory.
    :type url: str
    :param _reading: (default False) Should not be used. Used by the persistence system to get around
      the existence of the URL during construction. 
    :type _reading: bool
    :raises ValueError: If the URL is malformed.
    :raises DuplicateNameError: If the DB already exists in memory.
    :raises FileExistsError: If the URL already exists.
    
    Creates a **new** PRDb. If the url exists already, you should be using
    PRDb.getDB() to retrieve it.
    '''
    if hasattr(self, "_initialized"): # This means the __new__ method has returned an existing object, so don't truck over it!
      return
    
    self.reading:bool = _reading
    'Can be used by contained objects to determine if a read operation is taking place.'
     
    self.superDBs:list[Self] = []
    'List of other DBs that will be searched for indicies ([]) and get().'
    
    url = fixURL(url, extension=".xml", replaceExt=None, mode=mode)[0]
    if not isValidURL(url):
      raise ValueError(f'PRDb.__init__(): Malformed URL: "{url}"')
    if url in PRDb.AllDBs:
      raise DuplicateNameError(f'PRDb.__init__(): A DB with name "{url}" already exists in memory.')
    if urlExists(url) and not _reading:
      raise FileExistsError(f'PRDb.__init__(): URL already exists. Use PRDb.getDB("{url}") to open it.')
    self.url:str = url
    self._db:dict[int, T] = dict()
    self.nextID:int = 1
    PRDb.AllDBs[self.url] = self
    self._writeLocked = False
    
  @classmethod
  @override
  def getInstantiationInfo(cls)->InstantiationInfo:
    def convertDictToStrdict(d:dict[int, T]) -> strdict:
      ret:strdict = strdict()
      for k,v in d.items():
        ret[str(k)] = v
      return ret
    def convertStrdictToDict(d:dict[str, T]) -> dict[int, T]:
      ret:dict[int, T] = dict()
      for k,v in d.items():
        ret[int(k)] = v
      return ret
    def fixDBElems(slf:PRDb, d:strdict):
      slf._db = convertStrdictToDict(cast(strdict,d))
      for k,v in slf._db.items():
        v._id = k
    return InstantiationInfo(
            cls, 
            conArgs=[ParamInfo("url", str)],
            conKWArgs=[ParamInfo("_reading", bool, lambda _slf: True)],
            postconSetters=[PropertyInfo("nextID", int),
                            PropertyInfo("_db", strdict, 
                                         lambda slf: convertDictToStrdict(cast(PRDb, slf)._db),
                                         fixDBElems)])#lambda slf, d: setattr(slf, "_db", convertStrdictToDict(cast(strdict,d))))])

  @property
  def name(self):
    url = urlparse(self.url)
    path:Path = Path(url.path)
    return path.name
    
  def save(self, saveas:Optional[str]=None, overwrite=False, format:str="XML") -> None:
    if saveas is not None:
      url = fixURL(saveas, extension=f".{format.lower()}", replaceExt=None, mode="w")[0]
      if not isValidURL(url):
        raise ValueError(f'PRDb.save(): Malformed URL: "{url}"')
      if url in PRDb.AllDBs:
        raise DuplicateNameError(f'PRDb.save(): A DB with name "{url}" already exists in memory.')
      if urlExists(url) and not overwrite:
        raise FileExistsError(f'PRDb.save(): URL already exists. Did you mean to use the *overwrite* option?')
      oldURL = self.url 
      self.url = url
      SerializationStrategy.writex(url, self, format)
      self.url = oldURL
    else:
      SerializationStrategy.writex(self.url, self, format)
      
    
    
  # ── Write-side enforcement ────────────────────────────────────────────────

  def writeLocked(self) -> bool:
    '''
    :returns: True iff and the DB is write-locked.
    :rtype: bool
    '''
    return self._writeLocked
  
  def _register(self, value: T, _id:Optional[int]=None) -> int:
    '''
    :param value: The PRObject to be added to this DB.
    :type value: PRObject
    :param _id: Normally (and defaulted to) *None*. But if *value* is an
      object that has previously been unregistered, this value is the the
      original ID (that had been returned from this method) and will be 
      restored to this ID.
    :type _id: Optional[int]
    :return: A new (locally) unique id for this object.
    :raises PermissionError: If the DB is write locked.
    :raises TypeError: If the *value* is not of type *PRObject*.
    
    Generate a (locally) unique id for this object and add it the this DB.
    
    The method is private, but is used in the constructor of *PRObject*.
    '''
    if self.writeLocked():
      raise PermissionError(f'DB "{self}" is write locked.')
    if not isinstance(value, PRObject):
      raise TypeError(f"PRDb._register(): Values must be PRObject, got {type(value).__name__}")
    if isinstance(value, PRDbContainer):
      # assert self._db.get(0, None) is None, f'Unexpectedly found {self._db.get(0)} at index 0.' # this happens twice in the constructor
      self._db[0] = value
      return 0
    if _id is None:
      key = self.nextID
      self.nextID += 1
      self._db[key] = value
      return key
    else:
      self._db[_id] = value
      return _id

  def _unregister(self, _id:int) -> None:
    '''
    :param value: The PRObject to be added to this DB.
    :type value: PRObject
    :param _id: Normally (and defaulted to) *None*. But if *value* is an
      object that has previously been unregistered, this value is the the
      original ID (that had been returned from this method) and will be 
      restored to this ID.
    :type _id: Optional[int]
    :return: A new (locally) unique id for this object.
    :raises ValueError: if *_id* does not exist.
    
    Generate a (locally) unique id for this object and add it the this DB.
    
    The method is private, but is used in the constructor of *PRObject*.
    '''
    if self.writeLocked():
      raise PermissionError(f'DB "{self}" is write locked.')
    if self._db.get(_id, None) is None:
      raise ValueError(f'PRDB._unregister(): indici {_id} does not exist.')
    del self._db[_id]
  
  # ── Name-resolution helper ────────────────────────────────────────────────

  def findByName(self, name:str) -> list[T]:
    return [v for v in self._db.values() if v.name == name]
    
  def _resolve(self, key: int | str) -> int:
    """
    Return the integer key for *key*, without necessarily checking for it's existence.

      - int  -> returned as-is (existence check deferred to caller)
      - str  -> scanned for a matching .name; DuplicateNameError if >1 match
    
    :param key: The index or name of the object.
    :type key: int|str
    :returns: the int index of the object.
    :rtype: int
    :raises DuplicateNameError: if a str index is not unique.
    :raises KeyError: if the str index is not found.
    :raises TypeError: if the key is not either an int of a str.
    """
    if isinstance(key, int):
      return key
    if isinstance(key, str):
      matches:list[int] = [k for k, v in list(self._db.items()) if v.name == key]
      if len(matches) > 1:
        raise DuplicateNameError(f"PRDb._resolve(): Name {key!r} matches multiple entries: {matches}")
      if len(matches) == 0:
        raise KeyError(key)
      return matches[0]
    raise TypeError(f"PRDb._resolve(): Key must be int or str, got {type(key).__name__}")

  # ── Read-side overrides ───────────────────────────────────────────────────

  def __getitem__(self, key: int | str) -> T:
    try:
      index:int = self._resolve(key)
      if index == 0 and not self._db.get(0, None):
        self._makeDBContainer()
      return self._db.__getitem__(index)
    except KeyError as ex:
      for sdb in self.superDBs:
        if isinstance(key, str) or isinstance(key, int) and key < 256:
          obj = sdb.get(key, None)
          if obj is not None:
            return obj
      raise ex
    
  def _makeDBContainer(self) -> PRDbContainer[Self]:
    return PRDbContainer(self)

  def __contains__(self, key: object) -> bool:
    if isinstance(key, str):
      try:
        self._resolve(key)
        return True
      except KeyError:
        return False
    if isinstance(key, int):
      return self._db.__contains__(key)
    return False

  def getall(self, key:int|str, 
             filtr:Callable[[T],bool]=lambda o: True,
             throw:bool=False) \
                -> list[T]:
    """
    Return the integer key for *key*.

    - int  -> returned as-is (existence check deferred to caller)
    - str  -> scanned for a matching .name; DuplicateNameError if >1 match
    """
    # if key == 0:
    #   raise KeyError(f'getall(): Key 0 is illegal.')
    if isinstance(key, int):
      ret = [self[key]]
    elif isinstance(key, str):
      ret = [v for v in self._db.values() if v.name == key]
    else:
      raise TypeError(f"PRDb._resolve(): Key must be int or str, got {type(key).__name__}")
    ret = [o for o in ret if filtr(o)] #type: ignore[arg-type]
    if throw and len(ret) == 0:
      raise KeyError(f'No match for key "{key}".')
    return ret #type: ignore[return-value]
    
  def get(self, key:int|str, default:T|None=None) -> T|None:
    try:
      return self[key]
    except KeyError:
      return default

  def __iter__(self) -> Iterator[int]:
    return self._db.__iter__()

  def keys(self) -> KeysView[int]:
    return self._db.keys()

  def values(self) -> ValuesView[T]:
    return self._db.values()

  def items(self) -> ItemsView[int, T]:
    return self._db.items()

  # ── Representation ────────────────────────────────────────────────────────

  @override
  def __repr__(self) -> str:
    return self.torepr()
  
  def torepr(self, relativeTo:Self|None=None) -> str:
    members = "\n  ".join(f"{k}: {v.tostring(relativeTo=relativeTo)}" for k, v in self.items())
    return f'{self.tostring(relativeTo=relativeTo)}\n  {members}'
  
  @override
  def __str__(self) -> str:
    return self.tostring()

  def tostring(self, relativeTo:Self|None=None) -> str:
    return f'{self.__class__.__name__}({self.url}, <{len(self._db)} items>)'


class PReference[T:PRObject]:
  """
  A reference to a persistent object implementing the __call__() method for 
  resolving the referernce into a pointer.
  """
  def __init__(self, text:str):
    '''
    :param text: A string in the form of <URL>#<id>, where <id> can be an int,
      a string with no spaces or a quoted string.
    :type text: str
    :raises MalformedIDError: if the form of the ID is not valid.
    :raises ValueError: If it isn't a valid URL.
    :raises FileNotFoundError: If the file or URL does not exist.
      
    Creates a reference to a PRObject without actually trying to instantiate the
    PRObject or checking on it's existence. To instantiate the object, use
    a call on this object.
    '''
    self.id:int
    self.name:Optional[str]
    self.url:Optional[str]
    _id:Optional[int]
    self.url, _id, self.name = self._isValidID(text) # throws if not valid

    # if not given, id==-1 means we go by name, but if we don't have a name either,
    # id==0 means we are to return the whole db.
    self.id = _id if _id is not None else -1
    # if self.id == -1 and self.name is None:
    #   self.id = 0 
    
    self.obj:Optional[T|PRDb[T]] = None
    
  def __call__(self, relativeTo:PRDb[T]|str|None=None) -> T|PRDb[T]:
    '''
    :return: the resolved *PRObject*.
    :raises LookupError: if the reference cannot be resolved.
    '''
    if self.obj is None:
      
      theID:Optional[str|int] = self.id if self.id != -1 else self.name
      if theID is None: # return the DB itself
        assert self.url is not None
        self.obj = PRDb.getDB(self.url)
      else:
        if self.url is not None: # absolute id
          db:PRDb[T] = PRDb.getDB(self.url)
          self.obj = db[theID]
        else: # relative id
          if relativeTo is not None:
            if isinstance(relativeTo, str):
              relativeTo = PRDb.getDB(relativeTo)
            self.obj = relativeTo[theID]
          else:
            raise LookupError(f'Relative reference requires a *relativeTo* parameter.') 

    assert self.obj is not None
    return self.obj
  
  def tostring(self, relativeTo:PRDb[T]|None=None) -> str:
    return self.formatForURL(self, contextDB=relativeTo)
  
  @override
  def __str__(self) -> str:
    #return f'{self.url}#{self.id}: {("resolved to "+str(self.obj)) if self.obj is not None else "unresolved"}'
    #return f'{self.url}?{("id="+str(self.id)) if self.id>0 else ""}{"&" if self.id>0 and self.name is not None else ""}{("name="+quote(self.name)) if self.name is not None else ""}'
    return self.tostring()
    
  @override
  def __repr__(self) -> str:
    return self.torepr()
  
  def torepr(self, relativeTo:PRDb[T]|None=None) -> str:
    return f'{self.tostring(relativeTo)}: {("resolved to "+self.obj.tostring(relativeTo)) if self.obj is not None else "unresolved"}'
  
  @classmethod
  def formatForURL[T1:PRObject](cls, ref:str|Self|T1, contextDB:Optional[PRDb[T1]]=None, includeName=True) -> str:
    '''
    :param ref: A string or *PReference* or *PRObject*.
    :type ref: str|PReference|PRObject
    :param contextDB: A db to generate a relative reference string to. To shorten
      the string. This with a "x?id=10: will be "http:///x?id=10" with a context and
      merely "?id=10" with context=x 
    :type contextDB: PRDb
    :returns: The canonical for an ID. Since URL-fragment parts are not transmitted
      to the server in requests, they cannot be used to request fragment parts
      of an object, so where "#<id>" might be expected to be used, "?id=<id>" is
      used instead.
      
    Format:
    
      <url>?{id=<id_int>}{{&}name=<name>}
    '''
    if ref is None:
      return "None"
    if isinstance(ref, str):
      url, ID, name = PReference._isValidID(ref)
    else:
      if isinstance(ref, PRObject):
        r:PReference = ref.getPRef()
      else:
        assert isinstance(ref, PReference)
        r = ref
      assert isinstance(r, PReference)
      url = r.url
      ID = r.id
      name = r.name
    if url is not None:
      if contextDB is not None and url == contextDB.url:
        url = None
    return f'{url if url is not None else ""}{("#"+str(ID)) if ID is not None else ""}{("?name="+quote(name)) if name is not None and (includeName or ID is None) else ""}'
  
  @classmethod
  def eval[T1:PRObject](cls, text:str, contextDB:Optional[PRDb[T1]]=None, 
                        filtr:Callable[[T1],bool]=lambda o: True) -> T1|PRDb[T1]:
    '''
    Evaluate the text expression as a PReference to an object.  But be friendly 
    in interpreting the expression by assuming a # prefix is missing if we can't
    find the db in memory, file system, or web.
    
    :param text: A valid string representing a *PReference*.
    :type text: str
    :param contextDB: A *PRDb* in which to evaluate *text*.
    :type contextDB: Optional[PRDb]
    :param filtr: An optional PRObject->bool function to use to disambiguate between
      multiple possible return values if necessary. It should return True for a
      possible candidate.
    :type filtr: Callable[[PRObject],bool]|None
    :returns: A *PRObject* represented by *text*.
    :rtype: PRObject
    '''
    # Be lax in evaluating PReference obects: if we get FineNotFound, assume we're missing the # prefix...
    try:
      ref:PReference = PReference(text)
    except FileNotFoundError as ex:
      if "#" not in text:
        return PReference.eval('#'+text, contextDB, filtr)
      raise ex
      
    # if filtr is None:
    #   return ref(contextDB)
    
    #ref = PReference(text)
    theID:Optional[str|int] = ref.id if ref.id != -1 else ref.name
    if theID is None:
      assert ref.url is not None
      return PRDb.getDB(ref.url)
    if ref.url is not None: # absolute id
      db:PRDb[T1] = PRDb.getDB(ref.url)
    else: # relative id
      if contextDB is not None:
        if isinstance(contextDB, str):
          db = PRDb.getDB(contextDB)
        else:
          db = contextDB
      else:
        raise LookupError(f'Relative reference requires a *relativeTo* parameter.')
    
    def search(dbs:list[PRDb[T1]]) -> list[T1]:
      for db in dbs:
        ret = db.getall(theID, filtr=filtr, throw=False)
        if ret == []:
          ret = search(db.superDBs)
        if len(ret) > 0:
          return ret
      raise KeyError(text)
      
    #ret = db.getall(theID, filtr=filtr, throw=True) # can throw KeyError
    ret = search([db])
    
    if len(ret) > 1:
      raise DuplicateNameError(f'PReference "{text}" resolves to multiple objects. {[o.id for o in ret]}.')
    return ret[0]
    
  
  @classmethod
  def _isValidID_old(cls, text:str) -> tuple[Optional[str], Union[int,str]]:
    '''
    :param text: The text of a PReference in the form <URL>#[<int>|<str>].
    :type text: str
    :returns: A 2-tuble [url, id] where url is a valid URL or *None*, and id
      is either an int or a string
    :raises MalformedIDError: if the form of the ID is not valid.
    :raises ValueError: If it isn't a valid URL.
    :raises FileNotFoundError: If the file or URL does not exist.
    
    Splits the id into a URL part and an ID part. Validates the existence of
    the URL but makes no attempt to validate the ID. The ID may be either an int
    or a string name.
    
      <validID> := <absoluteURL> | <relativeURL>
      
      <absoluteURL> := <existing-URL>#<id>
      
      <relativeURL> := {#}<id>
      
      <id> := int | <str-without-whatespace> | <quoted-str>
      
      -------
      
      <validID> := <absoluteURL> | <relativeURL>
      
      <absoluteURL> := <existing-URL>{?<parameters>}#<id>
      
      <parameters> := name=<name> | id=<int>
      
      <relativeURL> := {#}<id>
      
      <id> := <int> | <str-without-whatespace> | <quoted-str>
    '''
    id_:str
    url:Optional[str]
    text = text.strip()
    parts:list[str] = text.split('#')
    if len(parts) > 2:
      raise MalformedIDError(f'More than one "#" found in id "{text}')
    if len(parts) < 2: # means a relative reference, maybe...
      id_ = text[1:] if text.startswith("#") else text
      url = None
    elif parts[0] == "":
      id_ = text[1:]
      url = None
    else: # exactly two parts: an absolute path
      url = fixURL(parts[0], extension=".xml", replaceExt=None, mode="")[0]
      if not isValidURL(url):
        raise ValueError(f'Malformed URL: "{url}"')
      if url not in PRDb.AllDBs and not urlExists(url):
        raise FileNotFoundError(f'URL "{url}" does not exist.')
      if url not in PRDb.AllDBs and not urlExists(url):
        raise FileNotFoundError(f'No URL "{text}" exists')
      id_ = parts[1]
      
    retID:Union[int,str]
    try:
      retID = int(id_)
    except:
      if id_.startswith('"') and id_.endswith('"') or id_.startswith("'") and id_.endswith("'"):
        retID = unquote(id_[1:-1])
      else:
        for c in id_: 
          if c.isspace():
            raise MalformedIDError(f'ID "{text}" object part must be an int, or non-space string, or a quoted string.')
        retID = unquote(id_) # strip out any %20's, etc. 
    return url, retID
    
  @classmethod
  def _isValidID(cls, s: str) -> tuple[str | None, int | None, str | None]:
    """Split a string into path, id, and name components.
  
    Respects single and double quoted substrings and backslash escapes.
    The '#' and '?' delimiters may appear in any order, but are expected
    to appear at most once each outside of quoted regions.
  
    Query string must be of the form 'name=<str>' or 'id=<int>', where
    <str> may be a quoted string or an HTML percent-encoded string.
  
    Fragment is a convenience for gracious interpretation of user input only. It
    must be an integer, a quoted string, or an HTML percent-encoded string.
    And if it's a an integer, will be interpreted as an id; if it's an string,
    will be interpreted as name.  If it disagrees with the query field, a ValueError
    exception is thrown.
    
    Locations are specified by standard http: https: or file: URLs, however
    the special notation "$<name>" looks up a DB in memory by it's name alone
    as a user interface convenience.
  
    :param s: The string to split, e.g. a URL or path with query/fragment.
    :type s: str
    :returns: A 3-tuple of (path, name, id). `name` is a str or None,
              `id` is an int or None.
    :rtype: tuple[str, str | None, int | None]
    :raises ValueError: If the query or fragment cannot be parsed or one of the
      query fields doesn't match the fragment field.
    
      <validID> := <absoluteID> | <relativeID>
      
      <absoluteID> := <existing-URL>{"?"<parameters>} | "#"<id>
      
      <locationSpec> := <existing-URL> | "$"<dbName>
      
      <parameters> := name=<name> | id=<int>
      
      <relativeID> := {#}<id>
      
      <id> := <int> | <str-without-whatespace> | <quoted-str>
    """
    
    def _unquoteStr(s: str) -> str:
      """Decode a string value: strip quotes (respecting escapes) or HTML-decode.
    
      :param s: A quoted string literal or percent-encoded string.
      :type s: str
      :returns: The decoded Python string.
      :rtype: str
      :raises ValueError: If the string is not a valid quoted or percent-encoded value.
      """
      s = s.strip()
      if (s.startswith('"') and s.endswith('"')) or \
         (s.startswith("'") and s.endswith("'")):
        # Strip quotes and decode backslash escapes
        inner = s[1:-1]
        return re.sub(r'\\(.)', r'\1', inner)
      if '%' in s or re.match(r'^[\w\-._~:@!$&\'()*+,;=]*$', s):
        # Treat as percent-encoded (also handles plain unquoted tokens)
        return unquote(s)
      raise ValueError(f'Invalid string value: {s!r}')
    
    def _parseQuery(raw: str | None) -> tuple[str | None, int | None]:
      """Parse a query string with optional 'name=<str>' and/or 'id=<int>' fields.
    
      Fields may appear in either order, separated by '&'.
    
      :param raw: The raw query string, or None if absent.
      :type raw: str | None
      :returns: A 2-tuple of (name, id), each None if not present.
      :rtype: tuple[str | None, int | None]
      :raises ValueError: If any field is not in the expected format.
      """
      if not raw or not raw.strip():
        return None, None
    
      name: str | None = None
      idVal: int | None = None
    
      for field in raw.split('&'):
        field = field.strip()
        if not field:
          continue
        if field.startswith('name='):
          name = _unquoteStr(field[5:])
        elif field.startswith('id='):
          try:
            idVal = int(field[3:].strip())
          except ValueError:
            raise ValueError(f'id must be an integer, got: {field[3:]!r}')
        else:
          raise ValueError(f'Unknown query field: {field!r}')
    
      return name, idVal
        
    def _parseFragment(raw: str | None) -> str | int | None:
      """Parse a fragment that must be an int, quoted string, or percent-encoded string.
    
      :param raw: The raw fragment string, or None if absent.
      :type raw: str | None
      :returns: An int, str, or None.
      :rtype: str | int | None
      :raises ValueError: If the fragment is not in the expected format.
      :raises FileNotFoundError: If the URL isn't in memory and it doesn't match a existing file or URL path.
      """
      if raw is None:
        return None
      raw = raw.strip()
      if not raw:
        return None
    
      # Try int first
      try:
        return int(raw)
      except ValueError:
        pass
    
      return _unquoteStr(raw)
    
    # actual method starts here...
    
    idVal:int
    try: # handle a simple int as an id.
      idVal = int(s)
      return None, idVal, None
    except:
      pass
      
    token_re = re.compile(r'''
      \\. |                        # backslash escape (any char)
      " (?: \\. | [^"\\] )* " |   # double-quoted string
      ' (?: \\. | [^'\\] )* ' |   # single-quoted string
      [#?] |                       # delimiter
      [^#?'"\\]+                   # plain text
    ''', re.VERBOSE)
  
    parts: list[str] = [] #list of string parts: [path, #-part, ?-part]
    delimiters: list[str] = []
    current: list[str] = [] # just used as an accumulator
  
    for match in token_re.finditer(s):
      tok = match.group()
      if tok in ('#', '?'):
        parts.append(''.join(current))
        delimiters.append(tok)
        current = []
      else:
        current.append(tok)
    parts.append(''.join(current))
  
    path:Optional[str] = parts[0].strip()
    
    if delimiters.count("#") > 1:
      raise ValueError(f'URLs can contain only one "#" fragment delimiter: {s}') 
    if delimiters.count("?") > 1:
      raise ValueError(f'URLs can contain only one "?" query delimiter: {s}') 
    
    # process a path prefixed $ by looking it up in memory first
    assert path is not None
    if path.startswith("$") and len(path) > 1:
      path = path[1:] # strip the $
      for k in PRDb.AllDBs:
        p = urlparse(k).path # path part of the url
        p = p[p.rfind("/")+1:p.rfind(".")] # find just the "file name"
        if p == path:
          path = k # found a match, so carry on with the matched full path 
          
    if path == "":
      path = None
    if path is not None:
      path = fixURL(path, extension=".xml", replaceExt=None, mode="")[0]
      if not isValidURL(path):
        raise ValueError(f'Malformed url: "{path}"')
      if path not in PRDb.AllDBs and not urlExists(path):
        raise FileNotFoundError(f'path "{path}" does not exist.')
    
    raw_query:str|None = None
    raw_fragment:str|None = None
  
    for i, delim in enumerate(delimiters):
      if delim == '?':
        raw_query = parts[i + 1]
      else:
        raw_fragment = parts[i + 1]
  
    iv:Optional[int]
    name, iv = _parseQuery(raw_query)
    idVal = -1 if iv is None else iv
    fragment:str|int|None = _parseFragment(raw_fragment)
    v:int|None = None
    if fragment is not None:
      try:
        v = int(fragment)
      except Exception as ex:
        assert type(fragment) is str, f'Expected type str, got {fragment.__class__.__name__}:{fragment}.'
        if name is None:
          name = fragment
        else:
          if fragment!=name:
            raise ValueError(f'Conflicting query (?id={quote(name)}) and fragment (#{quote(fragment)}) parts.')
      if v is not None:
        if idVal == -1:
          idVal = v
        else:
          if v!=idVal:
            raise ValueError(f'Conflicting query (?id={idVal}) and fragment (#{v}) parts (2).')
        
  
    return path, idVal, name



# ── Demo ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
  
  class CPObject(PRObject): # concrete PRObject
    def __init__(self, db:PRDb, name:str):
      super().__init__(db)
      self._name:str = name
      
    @property
    def name(self) -> str:
      return self._name

    # @name.setter
    # def name(self, name:str):
    #   self._name = name
      
  db: PRDb = PRDb("db")
  

  print("=== PRObject ===\n")

  a: CPObject = CPObject(db, "Alice")
  b: CPObject = CPObject(db, "Bob")
  c: CPObject = CPObject(db, "Carol")

  print(a, b, c)

  # ID is immutable
  try:
    a.id = 99  # type: ignore[misc]
  except AttributeError as e:
    print(f"Immutability enforced: {e}")

  # name is mutable
  a._name = "Alicia"
  print(f"Renamed: {a}")

  print("\n=== PRDb ===\n")

  print("DB:", db, "; repr():", repr(db))

  # Lookup by ID
  print("\nLookup by ID:")
  print("  db[2]          →", db[2])

  # Lookup by name
  print("\nLookup by name:")
  print("  db['Carol']    →", db["Carol"])

  # get() by name
  print("  db.get('Bob')  →", db.get("Bob"))
  print("  db.get('Zara') →", db.get("Zara", None))

  # contains
  print("\nContains:")
  print("  1 in db        →", 1 in db)
  print("  'Bob' in db    →", "Bob" in db)
  print("  'Zara' in db   →", "Zara" in db)

  # Duplicate name triggers DuplicateNameError
  print("\nDuplicate name test:")
  CPObject(db, "Bob")  # second "Bob" at index 4
  try:
    db["Bob"]
  except DuplicateNameError as e:
    print(f"  DuplicateNameError: {e}")

  # Type enforcement
  print("\nType enforcement:")
  try:
    db[1.4] # type: ignore[index]
  except TypeError as e:
    print(f"  Bad key type:   {e}")
  try:
    db[5] = db[4]  # type: ignore[index]
  except TypeError as e:
    print(f"  Bad value type: {e}")
