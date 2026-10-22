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
  override, cast, Callable, Self, ClassVar, Any
from abc import abstractmethod
from weakref import ref, ReferenceType
from util.utils import openUrl, urlExists, isValidURL, fixURL, isWindowsPath
from urllib.parse import unquote, quote, urlparse, urljoin
from contextlib import contextmanager
#import xml.etree.ElementTree as ET
from util.persistence.serialize import Serializable, InstantiationInfo,\
  ParamInfo, PropertyInfo, SerializationStrategy, strdict, SerializableType, HeadValue
from util.persistence.serialize import DEFAULT_STRATEGY
from pathlib import Path
import os
import re
import logging
from urllib3.util.url import parse_url
import util
from util.observer import Subject
from util.dirtyable import Dirtyable

logger:util.Logger = util.getLogger(__name__)

class DuplicateNameError(Exception):
  """Raised when a name lookup matches more than one PRObject."""

class MalformedIDError(Exception):
  """Raised a PReference is syntactically incorrect."""

class CircularReferenceError(Exception):
  """Raised when a PRDb document (directly or via a chain of other documents
  currently being read) ends up referencing its own URL while that URL's
  *PRDb._read()* is still in progress. Without this check, such a document
  would otherwise send *PRDb.__new__()* into unbounded recursion -- each
  nested attempt to load the same not-yet-finished URL passing every earlier
  guard (it's not yet in *AllDBs*; the file exists; it's not the top-level
  *_reading* call) -- until the interpreter's call stack is exhausted."""


class PRObject[DBT:"PRDb"](Serializable, Dirtyable):
  '''
  An object with an immutable integer ID and a mutable name.
  '''

  def __init__(self, db:DBT, **kwargs) -> None:
    '''
    :param db: The db to which this object will belong.
    :type db: PRDb
    :param kwargs: Passed on to *super().__init__()*. *PRObject* is often one
      link in a longer chain of cooperative *__init__* calls -- eg: a class
      combining *AbstractGraph*'s *AGRelation* with a sibling class via
      multiple inheritance (see *sn.model.model.Relation*) reaches *PRObject*
      through more than one base. Calling *super().__init__(**kwargs)* here
      (instead of simply returning) ensures whatever comes after *PRObject* in
      that particular class's MRO -- eg: *AttributedObject*, for a *Relation*
      or plain *GraphObject* -- still gets initialized, exactly once, with the
      constructor arguments meant for it, even though *PRObject* itself has no
      use for them.
    :type kwargs: Any
    :raises PermissionError: If the DB is write locked.
    :raises TypeError: If the *value* is not of type *PRObject*.
    :raises MemoryError: if the DB has been deleted.

    :note: This used to call ``Serializable.__init__(self)`` and
      ``Dirtyable.__init__(self)`` directly, up here, before the
      *super().__init__(**kwargs)* call below. *Serializable* has no
      *__init__* of its own so that call was a no-op, but the explicit
      *Dirtyable* call meant *Dirtyable* got initialized via a hardcoded
      direct call rather than via this class's cooperative *super()* chain
      -- and, since a class combining *PRObject* with something listed
      *after* *Dirtyable* in its own MRO (eg:
      *sn.view.graphics.vobjects.VObject*, which also mixes in
      *ErrorReportingObject*) relies on that same chain to reach the classes
      *after* *Dirtyable* too, this dead end silently meant
      *ErrorReportingObject.__init__()* -- and anything else listed after
      *Dirtyable* -- never ran at all for any such object. Removing the
      explicit calls and letting *Dirtyable* (now itself cooperative -- see
      its own *__init__*) be reached exactly once via *super()* below fixes
      that for every current and future user of this class, not just this
      one case.
    '''
    if not isinstance(db, PRDb):
      raise TypeError(f"db must be an PRDb, got {type(id).__name__}")
    self._db:ReferenceType = ref(db) # weak reference as the db will maintain references to this object
    self._url = self.db.url
    self._id: int = db._register(self)
    super().__init__(**kwargs)

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

    :returns:
    :rtype: PReference[Self]
    '''
    if self.db is None:
      raise AttributeError("PRObject has no DB.")
    ret:PReference = PReference(f'{self.db.url}#{str(self.id)}')
    ret.obj = self # TODO: efficient, but do we want this?
    return ret
    
  @override
  def __repr__(self) -> str:
    '''
    :returns:
    :rtype: str
    '''
    return f'{self.__class__.__name__}({(self.db.url if self.db is not None else "None")}, ID={self.id!r}, name={self.name!r})'
  
  def torepr(self, relativeTo:DBT) -> str:
    '''
    :param relativeTo:
    :type relativeTo: DBT
    :returns:
    :rtype: str
    '''
    url = self.db.url if self.db is not None else "None"
    return f'{self.__class__.__name__}({url}, ID={self.id!r}, name={self.name!r})'

  @override
  def __str__(self) -> str:
    '''
    :returns:
    :rtype: str
    '''
    return self.tostring()
  
  def tostring(self, relativeTo:DBT|None=None) -> str:
    '''
    :param relativeTo:
    :type relativeTo: DBT | None
    :returns:
    :rtype: str
    '''
    return f'{self.__class__.__name__}({self.name}, {self.getPRef().tostring(relativeTo)})'
  
  @override
  def __eq__(self, other: object) -> bool:
    '''
    :returns: True iff the two are PRObjects with the same *id* in DBs with the
      same URL -- the same identity *__hash__()* uses. (Not *name*: names
      needn't be unique, and in subclasses may be computed -- eg: inherited --
      in ways that themselves compare objects.)
    :rtype: bool
    :param other:
    :type other: object
    '''
    if self is other:
      return True
    if isinstance(other, PRObject):
      same = self._id == other._id and self._dbUrl() == other._dbUrl()
      if same: # identity and == should agree; if not, something made a duplicate
        logger.warning(f'Duplicate objects for {self._dbUrl()}#{self._id}: {id(self):#x} and {id(other):#x}')
      return same
    return False

  def _dbUrl(self) -> str:
    '''
    The URL of our DB, or the one it had when we were created if it has gone.

    :returns:
    :rtype: str
    '''
    db = self._db()
    return self._url if db is None else db.url
  
  @override
  def __hash__(self):
    '''
    :returns: The hash of *id* alone: objects equal by *__eq__()* (the same
      *id* in DBs with the same URL) hash the same. Not of the URL too, which
      would cost much more (it was *str(getPRef())*: about 500 times *id()*)
      and would change if the DB's URL does (eg: saved under another name).
      Objects of different DBs with the same *id* just share a hash.
      (*id* changes only while a DB is read -- see *fixDBElems* in
      *PRDb.getInstantiationInfo()* -- before the objects are in any set or
      dict.)
    :rtype: int
    '''
    return hash(self._id)


class PRContainer[DBT:"PRDb"](PRObject[DBT]):
  '''
  A *PRObject* that contains other objects (see *getMembers()*).
  '''
  @abstractmethod
  def getMembers(self) -> Iterator[PRObject[DBT]]:
    '''
    :returns:
    :rtype: Iterator[PRObject[DBT]]
    '''
    pass

  
class PRDbContainer[DBT:"PRDb"](PRContainer[DBT]):
  '''
  The object standing for its whole database (as object 0): its members are all the database's objects.
  '''
  @override
  def getMembers(self) -> Iterator[PRObject[DBT]]:
    for item in self.db.values():
      yield item
      
  @override
  @property
  def name(self)->str:
    '''
    :returns:
    :rtype: str
    '''
    return self.db.name
  
  
class PRDb[T:PRObject](Serializable, Subject, Dirtyable):
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
  
  #- ---- Class variables ---------------------------------------------------------
  
  AllDBs:ClassVar[dict[str, PRDb]] = dict()

  aliases:ClassVar[dict[str, str]] = dict()
  '''Other URLs for DBs -- eg: their old names, or where they were before they
  were moved -- and the URLs they stand for (see *resolveURL()*): eg,
  "sn:/sn.xml" -> "sn:/sn". One ending in "/" stands for everything under it
  (see *_alias()*).'''

  namedURLs:ClassVar[dict[str, Callable[[], str]]] = dict()
  '''Names -- pseudo-URLs, eg: "sn:/baseRules" -- of DBs whose actual URLs are
  only known when the program runs (eg: a temporary copy of a file that comes
  with it), and how to get each one's URL -- reading the DB, if need be (see
  *resolveURL()*). A reference to one is written as its name (see
  *relativeURL()*).'''

  _namesOf:ClassVar[dict[str, str]] = dict()
  "The names of the *namedURLs* that have been resolved, by their actual URLs."

  readProgress:ClassVar[Callable[[PRDb, int], None]|None] = None
  '''If set, called as a file's objects are read -- every *READ_PROGRESS_STEP*
  of them -- with the DB being read and how many of its objects have been
  read so far (eg: to show a progress bar: its *nextID* is about how many
  there'll be).'''

  READ_PROGRESS_STEP:ClassVar[int] = 250
  "How many objects are read between calls of *readProgress*."

  _readingURLs:ClassVar[set[str]] = set()
  '''URLs for which a *PRDb._read()* call is currently in progress (see
  *__new__()* below). A URL is added just before its *_read()* starts and
  removed as soon as that call returns or raises. *__new__()* checks this
  set before starting a new read so that a document which (directly, or
  through a chain of other documents it references) ends up loading its own
  URL again fails fast with a *CircularReferenceError* instead of recursing
  until the stack overflows: *AllDBs* alone can't catch this, since a URL is
  only added there *after* its read completes.'''

  #- ---- Class methods -----------------------------------------------------------

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
    cls._readingURLs = set()
    
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

    :param mode:
    :type mode: str
    '''
    # process a path prefixed $ by looking it up in memory first
    assert url is not None
    if url.startswith("$") and len(url) > 1:
      path = url[1:] # strip the $
      for k in PRDb.AllDBs:
        p = os.path.splitext(urlparse(k).path.rsplit("/", 1)[-1])[0] # just the "file name", without an extension
        if p == path:
          url = k # found a match, so carry on with the matched full path
          break
           
    url = cls.resolveURL(url) # (without checking access)
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

    :param mode:
    :type mode: str
    '''
    url = fixURL(url, extension=".xml", replaceExt=None, mode=mode)[0]
    if not isValidURL(url):
      raise ValueError(f'Malformed URL: "{url}"')
    if url in PRDb.AllDBs:
      raise DuplicateNameError(f'PRDb._read(): A DB with name "{url}" already exists.')
    # replaceExt=None is essential here (and not merely SerializationStrategy.readx()'s
    # own default -- that default is True): *url* commonly carries a subclass-specific
    # extension (.snm/.snv for sn.model.model.Model/sn.view.graphics.sngView.SNGView;
    # plain .xml for a generic PRDb) that no registered SerializationStrategy's
    # defaultExtension() matches. readx() then falls back to trying every known
    # strategy's .read() in turn, and .read() unconditionally rewrites the path via
    # fixURL(url, replaceExt=replaceExt, extension=<that strategy's own extension>)
    # before ever opening the file. Leaving replaceExt at readx()'s True default would
    # silently replace e.g. "temp2.snv" with "temp2.xml" -- opening (or creating) a
    # completely different file instead of raising -- the moment the XML strategy
    # happens to be tried. Passing None here preserves *url*'s actual extension, same
    # as every other read/write call site in this codebase already does.
    ret:Self = cls.readFile(url, mode=mode)
    if not isinstance(ret, cls):
      raise TypeError(f'PRDb._read(): Expected a {cls.__name__} in "{url}"; got type {str(type(ret))}.')
    return ret

  @classmethod
  def readFile(cls, url:str, mode="w") -> Any:
    '''
    Read the object in the file (or at the URL) *url* -- usually a PRDb, but not
    necessarily -- and return it. Use this rather than
    *SerializationStrategy.readx()* to read a PRDb, as it takes care of files
    that have been copied or moved:

    A copied or moved file still has its old URL in it. That's found out first
    (without reading the file), so that while it's read it's taken as being the
    file it was actually read from -- never confused with the original (which
    may be open) -- and so are its references to files that were next to it, if
    they've been copied along with it (see *_relocate()*). Its *previousURL* is
    the URL it was copied from (written in the header the next time it's saved).

    :param url:
    :type url: str
    :param mode:
    :type mode: str
    :returns:
    :rtype: Any
    '''
    if not isValidURL(url): # (a plain path, eg: from a file dialog: as the URL it's stored and kept under)
      url = fixURL(url, None, replaceExt=None, mode=mode)[0]
    try:
      stored = SerializationStrategy.peekStringx(url, "root", "url", mode=mode)
      previous = SerializationStrategy.peekStringx(url, "header", "previousURL", mode=mode)
    except Exception:
      stored = previous = None
    moved = stored is not None and stored != url
    if moved:
      assert stored is not None
      logger.warning(f'"{url}" was copied or moved from "{stored}": it\'s now taken to be "{url}" (and will be saved there).')
      PRDb._readFrames.append((stored, url))
    try:
      with PRDb.basedOn(url): # (relative references in it are relative to where it actually is)
        read = SerializationStrategy.readx(url, replaceExt=None, mode=mode)
    finally:
      if moved:
        PRDb._readFrames.pop()
    ret = read
    if not isinstance(ret, PRDb):
      return ret
    if ret.url != url: # (shouldn't happen any more: see above)
      logger.warning(f'DB read from "{url}" appears to have been copied from "{ret.url}". Changing its internal URL.')
      PRDb.AllDBs[url] = ret
      if PRDb.AllDBs.get(ret.url) is ret:
        del PRDb.AllDBs[ret.url]
      ret.url = url
    ret.previousURL = stored if moved else previous
    ret._wasRead(url)
    return ret

  def _wasRead(self, url:str) -> None:
    '''
    Called once this DB has been read from *url* (see *readFile()*): for
    subclasses to do whatever's needed then. (Here, nothing.)

    :param url: Where it was read from.
    :type url: str
    '''
    pass

  _bases:list[str] = []
  '''
  The URLs of the files being read or written just now, innermost last: relative
  URLs in a file are relative to the file (see *relativeURL()*, *absoluteURL()*).
  '''

  @classmethod
  @contextmanager
  def basedOn(cls, url:str|None):
    '''
    Within this context, relative URLs are relative to *url* (eg: the file being
    read or written) -- unless *url* is None.

    :param url:
    :type url: str | None
    '''
    if url is None:
      yield
      return
    cls._bases.append(url)
    try:
      yield
    finally:
      cls._bases.pop()

  @staticmethod
  def isRelativeURL(url:str) -> bool:
    '''
    Whether *url* is a relative URL, eg: "pets.snm" or "shared/animals.snm" (not "file:...", "sn:...", "/...", "$name", "#12").

    :param url:
    :type url: str
    :returns:
    :rtype: bool
    '''
    return bool(url) and urlparse(url).scheme == "" and not url.startswith(("/", "$", "~", "#", "?")) and not isWindowsPath(url)

  @classmethod
  def absoluteURL(cls, url:str, base:str|None=None) -> str:
    '''
    *url*, if it's relative, made absolute against *base* -- by default the file
    being read or written (see *basedOn()*); otherwise *url* as is (eg: a path
    typed by the user, relative to the current directory).

    :param url:
    :type url: str
    :param base:
    :type base: str | None
    :returns:
    :rtype: str
    '''
    base = base if base is not None else (cls._bases[-1] if cls._bases else None)
    if base is None or not cls.isRelativeURL(url):
      return url
    ret = urljoin(base, url)
    path = ret.partition("#")[0].partition("?")[0]
    if path not in PRDb.AllDBs and not urlExists(path):
      # A file copied on its own: what it referred to isn't next to it -- so
      # it's what was next to it where it was copied from.
      for stored, actual in reversed(cls._readFrames):
        if actual == base:
          alt = urljoin(stored, url)
          altPath = alt.partition("#")[0].partition("?")[0]
          if altPath in PRDb.AllDBs or urlExists(altPath):
            if (path, altPath) not in cls._relocated:
              cls._relocated.add((path, altPath))
              logger.warning(f'"{actual}" refers to "{url}", which isn\'t there (as "{path}"), but was where it was copied from: taking it to be "{altPath}".')
            return alt
          break
    return ret

  MAX_UP:int = 2
  "The most folders up (\"../\") a relative URL goes (see *relativeURL()*): further than that, URLs stay absolute."

  @classmethod
  def relativeURL(cls, url:str, base:str|None=None) -> str:
    '''
    *url* relative to *base* -- by default the file being read or written (see
    *basedOn()*) -- if it's a file in the same folder, below it, or at most
    *MAX_UP* folders up from it, eg: "pets.snm", "shared/animals.snm" or
    "../animals.snm"; otherwise *url* as is (eg: a file in an unrelated folder,
    or anything not a file). So a block of files copied together keeps referring
    to one another. (A file copied on its own still finds what it referred to:
    see *absoluteURL()*.)

    :param url:
    :type url: str
    :param base:
    :type base: str | None
    :returns:
    :rtype: str
    '''
    if url in cls._namesOf: # (a named DB: by its name -- see namedURLs)
      return cls._namesOf[url]
    base = base if base is not None else (cls._bases[-1] if cls._bases else None)
    if base is None or not url:
      return url
    u, b = urlparse(url), urlparse(base)
    if u.scheme != "file" or b.scheme != "file" or u.netloc != b.netloc:
      return url
    target, folder = u.path.split("/"), b.path.split("/")[:-1] # (the target's path; the base's folder)
    common = 0
    while common < min(len(target) - 1, len(folder)) and target[common] == folder[common]:
      common += 1
    up = len(folder) - common
    if up > cls.MAX_UP or common <= 1: # (too far up, or nothing in common but the root)
      return url
    rel = "/".join([".."] * up + target[common:])
    return rel + (f"?{u.query}" if u.query else "") + (f"#{u.fragment}" if u.fragment else "")

  _readFrames:list[tuple[str, str]] = []
  "(stored URL, actual URL) for each copied or moved file being read just now (see _read())."
  _relocated:set[tuple[str, str]] = set()
  "(from, to) relocations already reported."

  FILE_SCHEMES:ClassVar[tuple[str, ...]] = ("", "file", "http", "https")
  '''The schemes of URLs of files (on this computer or elsewhere). Others --
  eg: "sn:" -- are pseudo-URLs: names of DBs in memory (see *namedURLs*),
  taken as they are.'''

  @classmethod
  def resolveURL(cls, url:str, mode:str="") -> str:
    '''
    :param url: A DB's URL, as given: perhaps relative (see *absoluteURL()*),
      an alias (see *aliases*), or a name (see *namedURLs*).
    :type url: str
    :param mode: As for *fixURL()*: what to check it's there for ("w":
      writing; "": nothing).
    :type mode: str
    :returns: The URL it stands for: made absolute, given the default
      extension if it's a file's without one (see *fixURL()*), and relocated
      if it's in a file that's been copied or moved (see *_relocate()*). A
      pseudo-URL (see *FILE_SCHEMES*) is as it is (but for aliases and names).
    :rtype: str
    '''
    url = cls._alias(url)
    if url in cls.namedURLs:
      actual = cls.namedURLs[url]()
      cls._namesOf[actual] = url
      return actual
    if urlparse(url).scheme.lower() not in cls.FILE_SCHEMES and not isWindowsPath(url): # (a Windows path, eg: "C:\\x.snm", isn't a "c:" URL)
      return url
    url = cls._relocate(fixURL(cls._relocate(cls.absoluteURL(url)), extension=".xml", replaceExt=None, mode=mode)[0])
    return cls._alias(url)

  @classmethod
  def _alias(cls, url:str) -> str:
    '''
    :returns: What *url* is an alias for (see *aliases*), if it is; else
      *url*. An alias ending in "/" stands for everything under it: eg, with
      "http://old.org/onto/" -> "https://new.org/ontologies/",
      "http://old.org/onto/family.snm" is "https://new.org/ontologies/family.snm".
    '''
    if url in cls.aliases:
      return cls.aliases[url]
    for old, new in cls.aliases.items():
      if old.endswith("/") and url.startswith(old):
        return new + url[len(old):]
    return url

  @classmethod
  def _relocate(cls, url:str) -> str:
    '''
    While a copied or moved file is being read (see *_read()*): its old URL is
    taken to be the one it was read from; and a URL of a file that was next to
    it (eg: the model of a copied view) is taken to be the same file next to
    it now -- if that file is there. Otherwise, *url*.

    :param url:
    :type url: str
    :returns:
    :rtype: str
    '''
    base, hash_, frag = url.partition("#")
    for stored, actual in reversed(cls._readFrames):
      if base == stored:
        return actual + hash_ + frag
      oldDir, newDir = stored.rsplit("/", 1)[0], actual.rsplit("/", 1)[0]
      if oldDir != newDir and base.startswith(oldDir + "/") and "/" not in base[len(oldDir) + 1:]:
        candidate = newDir + base[len(oldDir):]
        if candidate in PRDb.AllDBs or urlExists(candidate):
          if (base, candidate) not in cls._relocated:
            cls._relocated.add((base, candidate))
            logger.warning(f'"{actual}" refers to "{base}", which was next to it: taking it to be "{candidate}", which is next to it now.')
          return candidate + hash_ + frag
    return url

  def serializationHeader(self) -> dict[str, HeadValue]:
    '''
    What to put in the head of its document when this is written (see
    *SerializationStrategy.tostring()*), besides its URL and super-DBs (see
    *getInstantiationInfo()*): the URL it was copied or moved from, if it
    was; and how many objects are in it (see *objectCount()*).

    :returns:
    :rtype: dict[str, HeadValue]
    '''
    ret:dict[str, HeadValue] = {"objects": self.objectCount()}
    if getattr(self, "previousURL", None):
      ret["previousURL"] = str(self.previousURL)
    return ret

  def objectCount(self) -> int:
    '''
    :returns: How many objects are written when this is (see
      *serializationHeader()*): by default, all of them (not its container).
    :rtype: int
    '''
    return sum(1 for k in self._db if k != 0)
  
  #- ---- Initialization -------------------------------------------------------
  
  def __new__(cls, url:str, mode="w", memoryResident:bool=True, _reading:bool=False):
    '''
    :param url:
    :type url: str
    :param mode:
    :type mode: str
    :param memoryResident:
    :type memoryResident: bool
    :param _reading:
    :type _reading: bool
    :returns:
    :rtype:
    '''
    assert issubclass(cls, PRDb)
    # (relocated before fixURL() too: a copied or moved file's old URL may not exist any more -- eg: a
    # placeholder it's stored as being in -- and after it, for a URL that only matches once it's fixed)
    url = cls.resolveURL(url, mode)
    if not isValidURL(url):
      raise ValueError(f'PRDb.__init__(): Malformed URL: "{url}"')
    if memoryResident and url in PRDb.AllDBs:
      setattr(PRDb.AllDBs[url], "_initialized", True)
      return PRDb.AllDBs[url]
    if urlExists(url) and not _reading:
      if url in PRDb._readingURLs:
        raise CircularReferenceError(
          f'PRDb.__new__(): "{url}" references itself -- directly, or through a '
          f'cycle of other documents currently being loaded ({", ".join(sorted(PRDb._readingURLs))}) '
          f'-- while its own read is still in progress. Refusing to recurse further; '
          f'check that document\'s persisted references for a bad/self URL.'
        )
      PRDb._readingURLs.add(url)
      try:
        ret = cls._read(url)
      finally:
        PRDb._readingURLs.discard(url)
      PRDb.AllDBs[url] = ret
      setattr(ret, "_initialized", True)
      return ret
    return super().__new__(cls)
  
  def  __init__(self, url:str, mode:str="w", memoryResident:bool=True, _reading:bool=False):
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

    :param mode:
    :type mode: str
    :param memoryResident:
    :type memoryResident: bool
    '''
    if hasattr(self, "_initialized"): # This means the __new__ method has returned an existing object, so don't truck over it!
      return
    
    Serializable.__init__(self)
    Subject.__init__(self)
    Dirtyable.__init__(self)
    
    self.reading:bool = _reading
    'Can be used by contained objects to determine if a read operation is taking place.'
     
    self.superDBs:list[Self] = []
    '''List of other DBs that will be searched for indicies ([]) and get(): what
    this one builds on, as though their contents were its own (but not
    changed through it). Saved with it (see *getInstantiationInfo()*); change
    it with *addSuperDB()* and *removeSuperDB()*.'''
    self._missingSuperDBs:list[str] = []
    '''The (saved) URLs of super-DBs that couldn't be read when this was: kept,
    and saved again, so that they're used once they're there again.'''
    
    url = self.resolveURL(url, mode) # (as in __new__())
    if not isValidURL(url):
      raise ValueError(f'PRDb.__init__(): Malformed URL: "{url}"')
    if url in PRDb.AllDBs:
      raise DuplicateNameError(f'PRDb.__init__(): A DB with name "{url}" already exists in memory.')
    if urlExists(url) and not _reading:
      raise FileExistsError(f'PRDb.__init__(): URL already exists. Use PRDb.getDB("{url}") to open it.')
    self.url:str = url
    class NoNoneDict[_KT,_VT](dict):
      def __setitem__(self, key:_KT, value:_VT)->None:
        if value is None:
          raise ValueError(f'None not allowed as a value. (key="{key}")')
        super().__setitem__(key, value)
    self._db:NoNoneDict[int, T] = NoNoneDict()
    self.nextID:int = 1
    if memoryResident:
      PRDb.AllDBs[self.url] = self
    self._writeLocked = False
    self.previousURL:str|None = None
    "The URL this was copied or moved from, if it was (see _read()); written in the header."
    
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
    def fixDBElems(slf:Serializable, d:SerializableType):
      assert isinstance(d, dict), f'Expected strdict for param 2, got {type(d)}.'
      assert isinstance(slf, PRDb), f'Expected PRDb for param 1, got {type(slf)}.'
      slf._db = convertStrdictToDict(cast(strdict,d)) # type: ignore[assignment]
      for k,v in slf._db.items():
        if v is not None:
          v._id = k
    def clearReading(slf:Serializable, _:SerializableType):
      assert isinstance(slf, PRDb), f'Expected PRDb for param 1, got {type(slf)}.'
      slf.reading = False
    def superDBURLs(slf:Serializable) -> list[str]:
      # (relative to this one's file where they're near it -- see relativeURL() -- so a folder of them can be moved together)
      assert isinstance(slf, PRDb)
      return [PRDb.relativeURL(db.url) for db in slf.superDBs] + list(slf._missingSuperDBs)
    def readSuperDBs(slf:Serializable, urls:SerializableType):
      assert isinstance(slf, PRDb)
      for u in cast(list, urls) or []:
        try:
          db:PRDb[T] = PRDb.getDB(str(u)) # (from memory, or read: relative to this one's file -- see basedOn())
        except Exception as ex:
          logger.error(f'"{slf.url}": its super-DB "{u}" couldn\'t be read ({type(ex).__name__}: {ex}); '
                       f'carrying on without it (it\'s kept, for when it\'s there again).')
          slf._missingSuperDBs.append(str(u))
          continue
        try:
          slf.addSuperDB(db)
        except ValueError as ex:
          logger.error(f'"{slf.url}": not using "{u}" as a super-DB: {ex}')
    return InstantiationInfo(
            cls, 
            conArgs=[ParamInfo("url", str, inHead=True)],
            conKWArgs=[ParamInfo("_reading", bool, lambda _slf: True)],
            postconSetters=[PropertyInfo("nextID", int),
                            # (before the objects: they may refer to the super-DBs' objects)
                            PropertyInfo("superDBs", list, superDBURLs, readSuperDBs, optional=True, inHead=True), # optional: older files don't have it
                            PropertyInfo("_db", strdict, 
                                         lambda slf: convertDictToStrdict(cast(PRDb, slf)._db),
                                         fixDBElems)],
            finalSetters=[PropertyInfo("_", bool, setter=clearReading)]
            )

  #- ---- Super-DBs -------------------------------------------------------------

  def allSuperDBs(self) -> list[PRDb]:
    '''
    :returns: This one's super-DBs, theirs, and so on (each once), nearest first.
    :rtype: list[PRDb]
    '''
    ret:list[PRDb] = []
    pending:list[PRDb] = list(self.superDBs)
    while pending:
      db = pending.pop(0)
      if db not in ret and db is not self:
        ret.append(db)
        pending.extend(db.superDBs)
    return ret

  def addSuperDB(self, db:PRDb) -> None:
    '''
    Make *db* a super-DB of this one (see *superDBs*), if it isn't already.

    :param db: The DB.
    :type db: PRDb
    :raises ValueError: if *db* is this one, or builds on it (directly or not):
      a cycle.
    '''
    if db is self or self in db.allSuperDBs():
      raise ValueError(f'"{db.url}" can\'t be a super-DB of "{self.url}": it is, or builds on, "{self.url}".')
    if db in self.superDBs:
      return
    self.superDBs.append(db) #type: ignore[arg-type]
    if not self.reading:
      self.setDirty()

  def removeSuperDB(self, db:PRDb) -> None:
    '''
    Stop *db* being a super-DB of this one (see *superDBs*), if it is.

    :param db: The DB.
    :type db: PRDb
    '''
    if db in self.superDBs:
      self.superDBs.remove(db) #type: ignore[arg-type]
      self.setDirty()

  #- ---- Properities ----------------------------------------------------------
  
  @property
  def name(self):
    '''
    :returns:
    :rtype:
    '''
    url = urlparse(self.url)
    path:Path = Path(url.path)
    return path.name
    
  #- ---- Methods -------------------------------------------------------
  
  def save(self, saveas:Optional[str]=None, overwrite=False, format:str=DEFAULT_STRATEGY) -> None:
    '''
    :param saveas:
    :type saveas: Optional[str]
    :param overwrite:
    :type overwrite: bool
    :param format:
    :type format: str
    '''
    if saveas is not None:
      url = fixURL(saveas, extension=SerializationStrategy.findStrategy(format).defaultExtension(), replaceExt=None, mode="w")[0]
      if not isValidURL(url):
        raise ValueError(f'PRDb.save(): Malformed URL: "{url}"')
      if url in PRDb.AllDBs:
        raise DuplicateNameError(f'PRDb.save(): A DB with name "{url}" already exists in memory.')
      if urlExists(url) and not overwrite:
        raise FileExistsError(f'PRDb.save(): URL already exists. Did you mean to use the *overwrite* option?')
      oldURL = self.url 
      self.url = url
      with PRDb.basedOn(url): # (references to files next to it are written relative to it)
        SerializationStrategy.writex(url, self, format, replaceExt=None)
      self.url = oldURL
    else:
      with PRDb.basedOn(self.url):
        SerializationStrategy.writex(self.url, self, format, replaceExt=None)
      
    
    
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
      ret = key
    else:
      self._db[_id] = value
      ret = _id
    self.setDirty()
    if PRDb.readProgress is not None and getattr(self, "reading", False):
      count = self.__dict__["_readCount"] = self.__dict__.get("_readCount", 0) + 1
      if count % PRDb.READ_PROGRESS_STEP == 0:
        PRDb.readProgress(self, count)
    #self.notify(("new", (ret, value)))
    with Subject.ChangeMgr(self, later=True) as cm:
      cm.registerTopics(("new", (ret, value)))
    return ret
  
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
    self.setDirty()
    with Subject.ChangeMgr(self, later=True) as cm:
      cm.registerTopics(("del", (_id,)))
    del self._db[_id]
  
  @override
  def setDirty(self, dirty:bool=True) -> None:
    '''
    An object is dirty if it has been modified and should probably be
    saved on exit.  This should be called from all methods that modify
    the state of this object.
    
    If *dirty* is False, resets all the contained *Attributes* to False.
    
    :param dirty: (default True) The dirty to set *dirty* to.
    :type dirty: bool
    '''
    assert type(dirty) is bool
    if not dirty:
      obj:PRObject
      for obj in self._db.values():  # LOCAL attributes only -- an inherited Attribute belongs to (and is tracked dirty by) its owning super object, not this one
        if obj is not None and obj.isDirty():
          obj.setDirty(False)
    super().setDirty(dirty)

  @override
  def isDirty(self) -> bool:
    '''
    Returns True iff the object (or an of it's contained *Attributes*) have
    been modified and should probably be saved on exit.

    :returns:
    :rtype: bool
    '''
    if super().isDirty():
      return True
    obj:PRObject
    for obj in self._db.values():  # LOCAL attributes only -- see setDirty()
      if obj.isDirty():
        super().setDirty(True)
        return True
    return False
  
  # ── Name-resolution helper ────────────────────────────────────────────────

  def findByName(self, name:str) -> list[T]:
    '''
    :param name:
    :type name: str
    :returns:
    :rtype: list[T]
    '''
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
    '''
    :param key:
    :type key: int | str
    :returns:
    :rtype: T
    '''
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
    '''
    :returns:
    :rtype: PRDbContainer[Self]
    '''
    return PRDbContainer(self)

  def __contains__(self, key: object) -> bool:
    '''
    :param key:
    :type key: object
    :returns:
    :rtype: bool
    '''
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

    :param key:
    :type key: int | str
    :param filtr:
    :type filtr: Callable[[T], bool]
    :param throw:
    :type throw: bool
    :returns:
    :rtype: list[T]
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
    '''
    :param key:
    :type key: int | str
    :param default:
    :type default: T | None
    :returns:
    :rtype: T | None
    '''
    try:
      return self[key]
    except KeyError:
      return default

  def __iter__(self) -> Iterator[int]:
    '''
    :returns:
    :rtype: Iterator[int]
    '''
    return self._db.__iter__()

  def keys(self) -> KeysView[int]:
    '''
    :returns:
    :rtype: KeysView[int]
    '''
    return self._db.keys()

  def values(self) -> ValuesView[T]:
    '''
    :returns:
    :rtype: ValuesView[T]
    '''
    return self._db.values()

  def items(self) -> ItemsView[int, T]:
    '''
    :returns:
    :rtype: ItemsView[int, T]
    '''
    return self._db.items()
  
  def __len__(self) -> int:
    '''
    :returns:
    :rtype: int
    '''
    return len(self._db)

  # ── Representation ────────────────────────────────────────────────────────

  @override
  def __repr__(self) -> str:
    '''
    :returns:
    :rtype: str
    '''
    return self.torepr()
  
  def torepr(self, relativeTo:Self|None=None) -> str:
    '''
    :param relativeTo:
    :type relativeTo: Self | None
    :returns:
    :rtype: str
    '''
    members = "\n  ".join(f"{k}: {v.tostring(relativeTo=relativeTo)}" for k, v in self.items())
    return f'{self.tostring(relativeTo=relativeTo)}\n  {members}'
  
  @override
  def __str__(self) -> str:
    '''
    :returns:
    :rtype: str
    '''
    return self.tostring()

  def tostring(self, relativeTo:Self|None=None) -> str:
    '''
    :param relativeTo:
    :type relativeTo: Self | None
    :returns:
    :rtype: str
    '''
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
    :param relativeTo:
    :type relativeTo: PRDb[T] | str | None
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
    '''
    :param relativeTo:
    :type relativeTo: PRDb[T] | None
    :returns:
    :rtype: str
    '''
    return self.formatForURL(self, contextDB=relativeTo)
  
  @override
  def __str__(self) -> str:
    #return f'{self.url}#{self.id}: {("resolved to "+str(self.obj)) if self.obj is not None else "unresolved"}'
    #return f'{self.url}?{("id="+str(self.id)) if self.id>0 else ""}{"&" if self.id>0 and self.name is not None else ""}{("name="+quote(self.name)) if self.name is not None else ""}'
    '''
    :returns:
    :rtype: str
    '''
    return self.tostring()
    
  @override
  def __repr__(self) -> str:
    '''
    :returns:
    :rtype: str
    '''
    return self.torepr()
  
  def torepr(self, relativeTo:PRDb[T]|None=None) -> str:
    '''
    :param relativeTo:
    :type relativeTo: PRDb[T] | None
    :returns:
    :rtype: str
    '''
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

    :param includeName:
    :type includeName: bool
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
      else: # (relative to the file being written -- or else to the context db -- if it's next to it)
        url = PRDb.relativeURL(url, None if PRDb._bases else (contextDB.url if contextDB is not None else ""))
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
    contextURL = contextDB if isinstance(contextDB, str) else getattr(contextDB, "url", None)
    with PRDb.basedOn(None if PRDb._bases else contextURL): # (a relative URL is relative to the file being read, or else to the context db)
      ref:PReference = PReference(text)
    try: # if the DB can't be found, then maybe the user left a prefix "#" off a relative name spec
      theID:str|int|None = ref.id if ref.id != -1 else ref.name
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
    except FileNotFoundError as ex:
      if "#" not in text:
        return PReference.eval('#'+text, contextDB, filtr)
      raise ex
    
    def search(dbs:list[PRDb[T1]]) -> list[T1]:
      for db in dbs:
        ret = db.getall(theID, filtr=filtr, throw=False)
        if ret == []:
          ret = search(db.superDBs)
        if len(ret) > 0:
          return ret
      raise KeyError(text)
      
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
      url = PRDb.resolveURL(parts[0])
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
        p = os.path.splitext(urlparse(k).path.rsplit("/", 1)[-1])[0] # just the "file name", without an extension
        if p == path:
          path = k # found a match, so carry on with the matched full path 
          
    if path == "":
      path = None
    if path is not None:
      path = PRDb.resolveURL(path)
      if not isValidURL(path):
        raise ValueError(f'Malformed url: "{path}"')
      # This no longer applies as db's can be non-memory resident
      # if path not in PRDb.AllDBs and not urlExists(path):
      #   raise FileNotFoundError(f'path "{path}" does not exist.')
    
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
      '''
      :param db:
      :type db: PRDb
      :param name:
      :type name: str
      '''
      super().__init__(db)
      self._name:str = name
      
    @property
    def name(self) -> str:
      '''
      :returns:
      :rtype: str
      '''
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
