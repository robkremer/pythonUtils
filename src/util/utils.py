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
Miscellaneous utility functions.
 
Created on Oct 14, 2024

.. codeauthor:: Rob Kremer <robkremer@me.com>

-------------
'''

import os
import sys
from typing import Optional, Any, Iterable, Callable,\
  Union, Tuple, overload, Self, Generator, override, Type, get_origin
from enum import EnumMeta, Flag
from urllib.parse import urlparse, unquote, quote, urlunparse, ParseResult
import requests
from pathlib import Path, PurePosixPath
import re
from importlib import import_module
import subprocess
import inspect
import tkinter as tk
import tkinter.ttk as ttk
from xml.etree.ElementTree import Element
from xml.etree import ElementTree
from collections.abc import Sequence
import pkgutil


import logging
from types import GenericAlias
import importlib
from abc import ABC
import argparse
from pickle import NONE
#from docutils.nodes import description
#logger:util.Logger = util.getLogger(__name__)


def makeParserFromFunc(fn:Callable, 
                       ignoreParam:Callable[[str], bool]=lambda paramName: False, 
                       parser:Optional[argparse.ArgumentParser]=None,
                       typeHandlers:dict[str,Callable[[str],Any]]=dict(),
                      ) -> argparse.ArgumentParser:
  '''
  :param fn: The function to make a parser for.
  :type fn: Callable
  :param ignoreParam: A filter that, given the name of a parameter return True iff 
    the param SHOULD be ignored. By default, all params will be used.
  :type ignoreParam: Callable[[str], bool]
  :param parser: If specified, this parser will have the params of *fn* added. If
    *parser* is absent, a new :py:class:`argparse.ArgumentParser` will be created.
  :type parser: argparse.ArgumentParser
  :param typeHandlers:
  :type typeHandlers: dict[str, Callable[[str], Any]]
  :returns: The parser.
  :rtype: argparse.ArgumentParser

  Limitations to be aware of:
  
    - Complex annotations (list[int], Optional[str], unions) need extra handling
  
    - ``*args`` / ``**kwargs`` don't map cleanly to argparse
  
  But for straightforward typed functions it works well.
  '''
  from docstring_parser import parse
  
  # look for a dict called "optionSynonyms" in *fn*'s containing class expected to
  # be a dict containing dicts of paramNames to synonyms (methodName -> (paramName -> list[-or--prefixedSynonyms]))
  try:
    methodName = fn.__name__
    qualname:str = fn.__qualname__
    #containingClass:type = fn.__self__.__class__
    parts = qualname.split('.')
    className = parts[-2]   # the part just before the method name
    containingClass = getClass(className)
    if containingClass is None:
      methodName = className 
      className = parts[-3] # the containing class's containing class
      containingClass = getClass(className)
    os:dict[str,dict] = getattr(containingClass, "optionSynonyms")
    optionSynonyms = os[methodName]
    assert isinstance(optionSynonyms, dict)
  except:
    optionSynonyms = dict()

  # gather the doc info from the function, including the doc about each param
  doc = inspect.getdoc(fn)
  pdoc = parse(doc)
  description = pdoc.description
  if pdoc.returns is not None and (pdoc.returns.description is not None or pdoc.returns.type_name is not None):
    rtype:str|None = pdoc.returns.type_name
    rdesc:str|None = pdoc.returns.description
    rdesc = "." if rdesc is None else (":\n"+rdesc)
    if description is None:
      description = ""
    description += f'\n\nReturns {rtype if rtype is not None else ""}{rdesc}'
  # shortDescription  = description[:description.find(".")]+"."
    
  if parser is None:
    parser = argparse.ArgumentParser(description=description if description is not None else f'{fn.__name__} description')
  else:
    parser.description = description if description is not None else f'{fn.__name__} description'
  # parser = parserMakerFun(shortDescription)
    
  # collect the doc on each param  
  paramsDoc = dict()
  for p in pdoc.params:
    paramsDoc[p.arg_name] = f'({p.type_name}{"" if p.default is None else (", default="+p.default)}) {p.description or ""}'.rstrip() # (an empty description: no "None")
    
  sig = inspect.signature(fn)

  for paramName, param in sig.parameters.items():
    if ignoreParam(paramName):
      continue
    annotation:str = param.annotation
    annots:list[str] = annotation.split(" | ")
    default = param.default
    hasDefault = default is not inspect.Parameter.empty
    kind = param.kind

    kwargs:dict[str,Any] = {}

    if annotation is not inspect.Parameter.empty:
      if annotation == "bool":
        kwargs['action'] = 'store_true' if not hasDefault or not default  else 'store_false'    
      else:
        for annot in annots:
          if annot.startswith("list["):
            kwargs['nargs'] = "*"
            annots = [annot[5:-1]] #ignore all other types
            break
        for annot in annots:
          if annot == "int":
            kwargs['type'] = int
            break
          if annot == "float":
            kwargs['type'] = float
            break
          if annot == 'str':
            kwargs['type'] = str
            break
          # if annot in typeHandlers:
          #   kwargs['type'] = typeHandlers[annot]
          #   break
          
    if paramName in paramsDoc: # add help if we have some
      kwargs['help'] = paramsDoc[paramName]
      
    if kind == inspect.Parameter.POSITIONAL_ONLY:
      pass

    if hasDefault:
      kwargs['default'] = default
      if kind == inspect.Parameter.POSITIONAL_ONLY:
        if 'nargs' not in kwargs:
          kwargs['nargs'] = '?'
        flags = [paramName] # positional
      else: # optional
        flags = [f'--{paramName}']
        if paramName in optionSynonyms:
          flags += optionSynonyms[paramName]
      #kwargs['required'] = False
    else:
      flags = [paramName]  # positional

    parser.add_argument(*flags, **kwargs)

  return parser

def resolveAliases(x:str, table:dict[str,str], raiseOnError:bool=True) -> str:
  """
  :param x: The string to analyze.
  :param table: The *dict* from which to lookup keys in.
  :param raiseOnError: If True a syntax error or a failed lookup in *table* will raise an exception, otherwise the $ expression will be left intact.
  
  From a string, substitute any contained <key> expressions "${<key>}" for *dict["key"]*. 
  Eg: *x* == *"a${b}c"* and *table* == *{"b":"BB"}* returns "aBBc".

  :returns:
  :rtype: str
  """
  length = len(x)
  i = 0
  ret = ""
  while i < length:
    if x[i] == "$" and i+1 < length and x[i+1] == "{":
      dollar = i # for error reporting
      i += 2
      var = ""
      while i < length and x[i] != "}":
        var += x[i]
        i += 1
      if i >= length: # didn't find a closing "}"
        if raiseOnError:
          temp = "${...}"
          raise SyntaxError(f'"{x}": Malformed substitution expression at character {dollar}; expression must be "{temp}".')
        else:
          ret += "${" + var
      elif var not in table:
        if raiseOnError:
          raise KeyError(f'"{x}": Lookup of "{var}" failed in substitution expression at character {dollar}.')
        else:
          ret += "${" + var + "}"
      else:
        ret += table[var]
    else:   
      ret += x[i]
    i += 1
  return ret

from typing import List

def splitOnSeparator(s: str, separator:str=".") -> List[str]:
  """Split a string on '.' while respecting single- and double-quoted substrings.

  Dots inside quoted regions are treated as literal characters and do not
  trigger a split. Quotes are stripped from the output tokens. A quoted
  region must span an entire token — a quote may only open at the start of
  a token and must close at the end of a token (immediately before a '.' or
  end of string). Nested quotes of the opposite kind are allowed inside a
  quoted region.

  :param s: The input string to split.
  :type s: str
  :returns: A list of substrings split on unquoted dots, with quotes removed.
  :rtype: List[str]
  :raises ValueError: If a quote appears mid-token, a quoted block is not
      properly terminated, or characters follow a closing quote before the
      next '.' or end of string.
  :param separator:
  :type separator: str
  """
  tokens: List[str] = []
  current: List[str] = []
  quoteChar: str | None = None
  tokenStart: bool = True
  quoteDone: bool = False

  for ch in s:
    if quoteChar:
      if ch == quoteChar:
        quoteChar = None
        tokenStart = False
        quoteDone = True
      else:
        current.append(ch)
    elif quoteDone:
      if ch == separator:
        tokens.append(''.join(current))
        current = []
        tokenStart = True
        quoteDone = False
      else:
        raise ValueError(f"Character '{ch}' follows closing quote mid-token")
    elif ch in ('"', "'"):
      if not tokenStart:
        raise ValueError(f"Quote '{ch}' opened mid-token")
      quoteChar = ch
    elif ch == separator:
      tokens.append(''.join(current))
      current = []
      tokenStart = True
    else:
      tokenStart = False
      current.append(ch)

  if quoteChar is not None:
    raise ValueError("Unclosed quote at end of string")

  tokens.append(''.join(current))
  return tokens 

def quoteIfNecessary(s:str) -> str:
  '''
  If the string contains spaces return surrounded with quotes, otherwise just
  return the string.

  :param s:
  :type s: str
  :returns:
  :rtype: str
  '''
  if " " in s:
    return f'"{s}"'
  return s
   
################################################################################
# ---- Control keys ------------------------------------------------------------
################################################################################

# State bits in events
_MAC = sys.platform == "darwin"
_CMD_MASK = 0x8 if _MAC else 0x4
"""The bit of the key shortcuts are made with: Command (Mod1) on macOS, Control
elsewhere (see *util.platformSupport.SHORTCUT*). (Not Mod1 or Mod2 off the Mac:
on X11, Mod1 is Alt and Mod2 is usually Num Lock; on Windows, 0x8 is Num Lock.)"""
_ALT_MASK = 0x10 if _MAC else 0x20000 if sys.platform == "win32" else 0x8
"The Option (Mod2) bit on macOS; Alt's on Windows (0x20000) and on X11 (Mod1)."
def s_CMD(s:int) -> bool:
  """
  :return: *True* iff *s* has the Command key bit set (Control, off the Mac:
    the key shortcuts are made with there).
  :param s:
  :type s: int
  """
  return (s&_CMD_MASK) != 0
def s_SHIFT(s:int) -> bool: 
  """
  :return: *True* iff *s* has the Shift key bit set.
  :param s:
  :type s: int
  """
  return (s&0x1)  != 0
def s_CTL(s:int) -> bool: 
  """
  :return: *True* iff *s* has the Control key bit set.
  :param s:
  :type s: int
  """
  return (s&0x4)  != 0
def s_ALT(s:int) -> bool: 
  """
  :return: *True* iff *s* has the Alt or Option key bits set.
  :param s:
  :type s: int
  """
  return (s&_ALT_MASK) != 0
s_OPT = s_ALT

# Graphical representations for control keys
CHAR_SHIFT = u'\u21E7'
CHAR_CTL   = u'\u2388'
CHAR_ALT   = u'\u2387'
CHAR_CMD   = u'\u2318'

def strToBool(b:str):
  '''
  :param b:
  :type b: str
  :returns:
  :rtype:
  '''
  b = b.lower()
  ln = len(b)
  if b in ("on", "true"[:min(4,ln)], "yes"[:min(3,ln)]):
    return True
  if b in ("off"[:min(3,max(2,ln))], "false"[:min(5,ln)], "no"[:min(2,ln)]):
    return False
  raise ValueError(f'Cannot interpret "{b}" as a boolean value.')


################################################################################
# ---- URLs --------------------------------------------------------------------
################################################################################

WINDOWS = sys.platform == "win32"
"Whether this is Windows, where paths look like \"C:\\folder\\file\" (see *urlPath()*, *pathURL()*)."

_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")

def isWindowsPath(s:str, windows:bool=WINDOWS) -> bool:
  '''
  :param s: A path or URL.
  :param windows: Whether this is Windows (by default: whether it is). Elsewhere,
    there are no such paths: "x:/..." is a URL.
  :returns: Whether *s* is a Windows path with a drive letter (eg: "C:\\Users\\me",
    "C:/Users/me") or a network one ("\\\\server\\share\\..."): a path, not
    a URL whose scheme is one letter (as *urlparse()* takes it to be).
  '''
  return windows and (bool(_DRIVE_PATH.match(s)) or s.startswith("\\\\"))

def openFile(path:str, mode:str="r", **kwargs) -> Any:
  '''
  Like *open()*, but a path that can't be a file's (eg, one with a '"' in it,
  on Windows, which raises an *OSError* "Invalid argument") raises
  *FileNotFoundError*, as it does elsewhere: there's no such file.
  '''
  try:
    return open(path, mode, **kwargs)
  except OSError as ex:
    import errno
    if ex.errno == errno.EINVAL and not isinstance(ex, FileNotFoundError):
      raise FileNotFoundError(errno.ENOENT, f"No such file (not a possible file name): {ex.strerror}", path) from ex
    raise

def urlPath(url:str, windows:bool=WINDOWS) -> str|None:
  '''
  :param url: A "file:" URL (eg: "file:///Users/me/family.snm", or on Windows
    "file:///C:/Users/me/family.snm"), or a path.
  :param windows: Whether to make a Windows path (by default: on Windows).
  :returns: The path of the file *url* is of, on this computer ("%20" is a space,
    ...): eg: "/Users/me/family.snm", or "C:\\Users\\me\\family.snm" on
    Windows. A path is as it is (unquoted). None if *url* is some other URL (eg:
    "https:", "sn:").
  '''
  if isWindowsPath(url, windows):
    return url
  u = urlparse(url)
  if u.scheme not in ("file", ""):
    return None
  path = unquote(u.path)
  if not windows:
    return path
  host = u.netloc
  if re.match(r"^[A-Za-z]:$", host): # ("file://C:/...", as "file://" + a path makes)
    path = host + path
  elif host and host.lower() != "localhost": # a network share ("file://server/share/...")
    path = "//" + host + path
  elif re.match(r"^/[A-Za-z]:", path): # ("file:///C:/...")
    path = path[1:]
  return path.replace("/", "\\")

def pathURL(path:str, quoted:bool=True, windows:bool=WINDOWS) -> str:
  '''
  :param path: An absolute path.
  :param quoted: Whether characters not allowed in URLs are quoted (eg: a space
    as "%20"), as *Path.as_uri()* does; else they're as they are (as in
    "file://" + *path*).
  :param windows: Whether *path* is a Windows path (by default: on Windows).
  :returns: The "file:" URL of *path*: eg: "file:///Users/me/family.snm", or
    "file:///C:/Users/me/family.snm" for "C:\\Users\\me\\family.snm".
  '''
  q = quote if quoted else (lambda s: s)
  if windows:
    path = path.replace("\\", "/")
    return "file:" + q(path) if path.startswith("//") else "file:///" + path[:2] + q(path[2:]) # (the drive's "C:" as it is)
  return "file://" + q(path)

def displayURL(url:str, maxLength:int|None=None, home:str|None=None, windows:bool=WINDOWS) -> str:
  '''
  :param url: A URL or a path.
  :param maxLength: If given, the most characters the result may have: a longer
    one loses characters from its middle (shown as "\u2026"), keeping its start
    and its end (the file's name).
  :param home: The user's home folder (by default: this computer's), shown as
    "~" at the start of a path (but not on Windows).
  :param windows: Whether to make a Windows path (by default: on Windows).
  :returns: How to show *url* to the user (eg: in a menu): a "file:" URL's whole
    path (eg: "~/My Models/family.snm"), else the whole URL as it is.
  '''
  path = urlPath(url, windows)
  text = url if path is None else path
  if path is not None and not windows:
    home = (home if home is not None else os.path.expanduser("~")).rstrip("/")
    if home and (path == home or path.startswith(home + "/")):
      text = "~" + path[len(home):]
  if maxLength is not None and len(text) > maxLength:
    tail = (maxLength - 1) * 2 // 3 # (more of the end, which names the file)
    head = maxLength - 1 - tail
    text = text[:head] + "\u2026" + text[len(text) - tail:] if tail > 0 else text[:maxLength]
  return text

def isValidURL(url:str) -> bool:
  '''
  :param url: A string to determine if it's a proper URL
  :return: *True* iff the str appears to be well-formed URL (a Windows path,
    eg: "C:\\Users\\me", isn't one: see *isWindowsPath()*)
  '''
  # from sn import BASE_URL
  if isWindowsPath(url):
    return False
  try:
    # if url == BASE_URL:
    #   return True
    result = urlparse(url)
    if result.scheme == "file":
      return all([result.path, url.startswith("file:///")])
    elif result.scheme in result.scheme in ["http", "https"]:
      return all([result.netloc])
    else:
      return all([result.scheme, result.scheme != ""])
  except AttributeError:
    return False      

REMOTE_TIMEOUT = 30
"How long (seconds) to wait for a web server (see *fetchURL()*, *urlExists()*)."

webCacheFolder:str|None = None
'''Where copies of the files read from the web are kept, if anywhere (see
*fetchURL()*): set by an application (eg: Semantic Nets: *~/.sn/cache*).'''

_sslContext = None

def sslContext():
  '''
  :returns: The SSL context to check web servers' certificates with: the
    system's certificate authorities plus *certifi*'s (if it's installed: it
    comes with *requests*).
  :rtype: ssl.SSLContext

  Python's own context only has the system's, and the python.org macOS
  Python has none until its "Install Certificates.command" is run: every
  "https:" URL fails with CERTIFICATE_VERIFY_FAILED.
  '''
  global _sslContext
  if _sslContext is None:
    import ssl
    context = ssl.create_default_context()
    try:
      import certifi
      context.load_verify_locations(certifi.where())
    except (ImportError, OSError):
      logging.getLogger(__name__).debug("No certifi certificates: using only the system's.", exc_info=True)
    _sslContext = context
  return _sslContext

def openWebURL(url, timeout:float|None=REMOTE_TIMEOUT, **kwargs):
  '''
  :param url: A URL or a *urllib.request.Request*.
  :param timeout: How long (seconds) to wait for the server.
  :returns: *urllib.request.urlopen(url, ...)*, checking certificates with
    *sslContext()*.
  '''
  import urllib.request
  return urllib.request.urlopen(url, timeout=timeout, context=sslContext(), **kwargs)

def cachePath(url:str) -> str|None:
  '''
  :param url: A web URL ("http:" or "https:").
  :type url: str
  :returns: Where its copy is (or would be) in *webCacheFolder* -- by its
    host, then its path (a query string, if it has one, is part of the file's
    name) -- or None if there's no cache, or it isn't a web URL.
  :rtype: str | None
  '''
  u = urlparse(url)
  if webCacheFolder is None or u.scheme not in ("http", "https") or not u.netloc:
    return None
  parts = [p for p in unquote(u.path).split("/") if p not in ("", ".", "..")] or ["index"]
  if u.query:
    parts[-1] += "?" + u.query
  host = u.netloc.replace(":", "_")
  return os.path.join(webCacheFolder, u.scheme, host, *[p.replace(os.sep, "_") for p in parts])

def cachedCopy(url:str) -> str|None:
  ''':returns: The path of *url*'s copy in *webCacheFolder* (see *cachePath()*), if there is one.'''
  path = cachePath(url)
  return path if path is not None and os.path.isfile(path) else None

class OfflineWarning:
  '''*fetchURL()*'s warnings that it's using a cached copy: at most once per URL.'''
  warned:set[str] = set()

def fetchURL(url:str) -> bytes:
  '''
  :param url: A web URL ("http:" or "https:").
  :type url: str
  :returns: What's there. It's copied into *webCacheFolder* (if there is
    one); and if the server can't be reached (eg: offline), that copy is used
    instead (with a warning).
  :rtype: bytes
  :raises FileNotFoundError: If there's nothing there (HTTP 404 or 410).
  :raises urllib.error.URLError: If the server can't be reached, and there's
    no copy.
  '''
  import urllib.request, urllib.error, datetime
  try:
    with openWebURL(url) as response:
      data:bytes = response.read()
  except urllib.error.HTTPError as e:
    e.close()
    if e.code in (404, 410):
      raise FileNotFoundError(f'There\'s nothing at "{url}" (HTTP {e.code}).') from e
    raise
  except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
    copy = cachedCopy(url)
    if copy is None:
      raise
    if url not in OfflineWarning.warned:
      OfflineWarning.warned.add(url)
      when = datetime.datetime.fromtimestamp(os.path.getmtime(copy)).strftime("%Y-%m-%d %H:%M")
      logging.getLogger(__name__).warning(f'"{url}" can\'t be reached ({getattr(e, "reason", e)}): using the copy kept on {when}.')
    with open(copy, "rb") as f:
      return f.read()
  path = cachePath(url)
  if path is not None:
    try:
      os.makedirs(os.path.dirname(path), exist_ok=True)
      with open(path + ".part", "wb") as f:
        f.write(data)
      os.replace(path + ".part", path)
    except OSError:
      logging.getLogger(__name__).warning(f'Couldn\'t keep a copy of "{url}" (in "{path}").', exc_info=True)
  return data

def urlExists(url:str) -> bool:
  '''
  :param url: A string to determine if it's an existant URL
  :return: *True* iff the str is a URL that references an existant place --
    for a web URL whose server can't be reached, if there's a copy of it (see
    *fetchURL()*).
  '''
  if urlparse(url).scheme == "file":
    return os.path.isfile(urlPath(url) or "")

  else:
    try:
      response = requests.get(url, timeout=REMOTE_TIMEOUT)
      return response.status_code == 200
    except Exception:
      return cachedCopy(url) is not None

import os
import requests
from pathlib import Path
from urllib.parse import urlparse

def canWriteUrl(url: str) -> bool:
  '''
  :param url: A url in text format.
  :type url: str
  :returns: *True* iff you can write to that location (best guess).
  :rtype: bool
  
  The file: check is reliable; the HTTP check is best-effort only.
  '''
  parsed = urlparse(url)
  if parsed.scheme == "file":
    decodedPath = Path(urlPath(url) or "")
    return os.access(decodedPath.parent, os.W_OK)
  try:
    response = requests.options(url, timeout=5)
    allow = response.headers.get("Allow", "")
    return "PUT" in allow or "POST" in allow
  except requests.RequestException:
    return False

def fixURL(url:str, extension:Optional[str]=None, replaceExt:Optional[bool]=None, mode:str="w") -> tuple[str, ParseResult]:
  '''
  :param url: the URL to examine.
  :type url: str
  :param replaceExt: If True, any extension will be replace with
    the default extension; if False, the default extension will be 
    appended to the path even there's already another extension; if None (the default), 
    the extension will only be added it the file does not already have an 
    extension.
  :type replaceExt: Optional[bool] (default: None)
  :param mode: 'r' will check if the file or URL exists; 'w' will try to determine
    if the file is writable (not a URL other than a file's, eg: "https:" -- that
    can't be told without writing it: it may be only for reading, so writing
    it fails then); anything else will make no checks.
  :type mode: str
  :param extension: The file extension to use for a replacement or appendment; 
    if missing or *None* it defaults ".txt".  Ignored if *replaceExt* is *None*.
  :type extension: str
  :returns: 
  :rtype: tuple[str, urllib.parse.ParseResult]
  :raises FileNotFoundError: if *mode="r"* and the url/file does not exist for a read operation
  :raises PermissionError: if *mode="w"* and the url/file doesn't appear to be writeable.
  :raises ValueError: if the URL is empty.
  
  Sanitize the URL by making a filename a proper "file:///" URL, dealing with
  the path file extension, and verifying the file is accessible for read or 
  write. 
  '''
  if not url:
    raise ValueError("fixURL(): url must not be empty")
  
  # if we find a naked file name, change it to a URL
  if not isValidURL(url):
    #url = Path(url).expanduser().resolve().as_uri()
    url = Path(url).resolve().as_uri()
  
  parsedUrl:ParseResult = urlparse(url)
  
  if parsedUrl.scheme == '': # it's an apparent raw filename?
    parsedUrl = parsedUrl._replace(scheme='file')
    url = parsedUrl.geturl()
    
  path = PurePosixPath(parsedUrl.path) # (a URL's path: "/"-separated, whatever this computer's paths are like)
  if replaceExt is not None: # either replace or append an extension
    if not extension:
      extension = ".txt"
    if not extension.startswith('.'):
      extension = '.'+extension
    if path.suffix != extension:
      if replaceExt: # replace extention
        path = path.with_suffix(extension)
      else: # append extension
        path = path.with_suffix(path.suffix+extension)
      parsedUrl = parsedUrl._replace(path=str(path))
      url = parsedUrl.geturl()
  else:
    if path.suffix == "" and extension is not None:
      path = path.with_suffix(extension)#path.replace(suffix=extension)#, new, count)path.suffix = extension
      parsedUrl = parsedUrl._replace(path=str(path))
      url = parsedUrl.geturl()
    
  
  # check if we can access the url (don't bother if mode is something else)
  if mode.lower() == 'r' and not urlExists(url):
    raise FileNotFoundError(f'URL "{url}" not found.')
  elif mode.lower() == 'w' and parsedUrl.scheme == "file" and not canWriteUrl(url):
    raise PermissionError(f'Path does not exist or permission denied on url "{url}".')
  
  return url, parsedUrl

def fileToUrl(filename:str) -> str:
  '''
  :param filename: A string representing a file path (may be relative)
  :return: A proper URL referencing *filename*; it may or may not actually exist.
  '''
  return Path(filename).resolve().as_uri()
  
def urlToFile(url:str) -> Optional[str]:
  '''
  :param url: A string representing a URL 
  :return: A path string equivalent to *url*; it may or may not actually exist.
  '''
  ret:Optional[str] = urlPath(url) if urlparse(url).scheme in ("file", "") else urlparse(unquote(url)).path
  if ret == "": ret = None
  return ret

import os
import urllib.request
from urllib.parse import urlparse


def openUrl(url: str) -> bytes:
  """
  Fetch the contents of a URL and return them as bytes for XML parsing.

  Parses the given URL to detect its scheme. For ``file:`` URLs, the path is
  resolved to an absolute local path and read from the filesystem. All other
  schemes (e.g. ``http:``, ``https:``, ``ftp:``) are fetched via
  :py:func:`urllib.request.urlopen`.

  The raw bytes are returned without decoding so that the XML parser can read
  the encoding declaration from the document itself and decode accordingly.

  :param url: The URL to fetch. May use any scheme supported by
    :py:mod:`urllib.request`, plus the ``file:`` protocol for local filesystem
    paths.
  :type url: str
  :returns: Raw byte content of the resource, suitable for passing directly to
    an XML parser (e.g. :py:func:`xml.etree.ElementTree.fromstring` or
    :py:class:`lxml.etree.XMLParser`).
  :rtype: bytes
  :raises ValueError: If *url* is an empty string.
  :raises FileNotFoundError: If a ``file:`` URL points to a path that does not
    exist.
  :raises urllib.error.URLError: If a remote URL cannot be reached.

  Usage::

    >>> xmlBytes = openUrl("https://example.com/feed.xml")
    >>> import xml.etree.ElementTree as ET
    >>> root = ET.fromstring(xmlBytes)

    >>> xmlBytes = openUrl("file:///home/user/data.xml")
    >>> root = ET.fromstring(xmlBytes)

  <adapted from Claude>  
  """
  if not url:
    raise ValueError("openUrl(): url must not be empty")

  parsedUrl: ParseResult = urlparse(url)

  if parsedUrl.scheme == "file":
    absolutePath: str = os.path.abspath(urlPath(url) or "")
    with open(absolutePath, "rb") as fileHandle:
      return fileHandle.read()

  with openWebURL(url) as response:
    return response.read()
  
def addDefaultExtToURL(url:str, ext:str=".xml"):
  '''
  :param url: a legal url.
  :param ext: an extension to be added to <url> iff <url>'s path does not already have an extension.
  :return: <url> or a version of <url> with the extension added iff it did not already have an extension.
  
  A dot is added in front of <ext> if it is not already there.
  '''
  if not ext.startswith("."):
    ext = "."+ext
  parts = urlparse(url)
  path = parts.path
  file = os.path.basename(path)
  fileparts = file.split(".")
  if len(fileparts) == 1:
    url = urlunparse((parts.scheme, parts.netloc, parts.path+ext, parts.params, parts.query, parts.fragment))
  return url

def getNameAndExtFromURL(url:str, extension:str|None = None):
  '''
  :param url: a legal url, or if that fails will try to parse as a path.
  :param extension: (default:None) if the url does not have a file extension,
    use this one if it's given.  If there is an extension on the URL already,
    *extension* is ignored.
  :return: Just the filename (no path) and extension.
  '''
  try: # try to parse as a url
    parts = urlparse(url)
    path = parts.path
  except: # failed as a url, so try to parse as a path
    path = url
  file = os.path.basename(path)
  fileparts = file.rsplit(".",1)
  if len(fileparts) == 1:
    if extension is None:
      ext = ""
    else:
      ext = extension 
      if not ext.startswith('.'):
        ext = '.'+ext
  else:
    ext = '.'+fileparts[1]
  filename = fileparts[0]
  return filename+ext

def changeUrlExtension(url, new_extension):
    """
    Changes the file extension of a URL.

    Args:
        url (str): The original URL string.
        new_extension (str): The new extension (e.g., ".jpg", ".html").

    Returns:
        str: The URL with the modified extension.

    :param url:
    :type url:
    :param new_extension:
    :type new_extension:
    :returns:
    :rtype:
    """
    parsed_url = urlparse(url)
    path_without_ext, _ = os.path.splitext(parsed_url.path)
    new_path = path_without_ext + new_extension
    
    # Reconstruct the URL with the new path
    new_url = urlunparse(parsed_url._replace(path=new_path))
    return new_url
  
################################################################################
# ---- MUCKING WITH CLASSES ----------------------------------------------------
################################################################################

def makeConcrete[T: ABC](abstract_cls: type[T], implementations: dict[str, Callable]) -> type[T]:
  """
  Dynamically create a concrete subclass from an ABC.

  :param abstract_cls: The abstract base class to concretize.
  :type abstract_cls: type[T]
  :param implementations: A mapping of abstract method names to callables.
  :type implementations: dict[str, Callable]
  :returns: A new concrete subclass with all abstract methods implemented.
  :rtype: type[T]
  :raises TypeError: If you left out one or more abstract methods in *implementations*.

  .. code-block:: python
    :caption: **Usage**:
  
    class Shapes(ABC):
      @abstractmethod
      def area(self) -> float: ...
    
      @abstractmethod
      def perimeter(self) -> float: ...
    
    circle = make_concrete(Shape, {
      "area":      lambda self: 3.14159 * 5 ** 2,
      "perimeter": lambda self: 2 * 3.14159 * 5,
    })()
    
    print(circle.area())       # 78.53975
    print(circle.perimeter())  # 31.4159
  """
  missing = abstract_cls.__abstractmethods__ - implementations.keys()
  if missing:
    raise TypeError(f"Missing implementations for: {missing}")

  return type(f"_{abstract_cls.__name__}Impl", (abstract_cls,), implementations)


def getFullClassName(cls:type) -> str:
  """
  Unlike *obj.__class__.__name__* this returns the (period-deliminated) full class path of *subjectClass*

  :returns:
  :rtype: str
  """
  #return str(subjectClass)[8:-2]
  splt = str(cls).split()
  if len(splt) == 1: # it was a simple type like "int"
    return splt[0]
  return splt[1][1:-2] # it was a class type in the form of "<class 'module.name'>"
  
def getClass(className:str) -> Optional[type]:
  '''
  Searches the modules in the system for the first class that matches the 
  simple class name.  Use *getFullyqualifiedClass()* if you have a class path.

  :param className:
  :type className: str
  :returns:
  :rtype: Optional[type]
  '''
  cls:Optional[type] = None
  for _, mod in sys.modules.items():
    c = None
    try:
      c = getattr(mod, className)
    except:
      continue
    cls = c
    break
  return cls
    
_classesByPath:dict[str, type] = {}
"The classes *getFullyQualifiedClass()* has found, by their paths."

def getFullyQualifiedClass(classPath:str) -> Optional[type]:
  """
  :param classPath: A string representing the name of a class
  :return: Either a *Class* object or None
  
  Follows the class path down the modules in the system to return the matching class object.
  User *getClass()* if you only have a simple class name and want to search for it. 
  A class found is remembered (a class not found isn't: its module may be
  loaded later): reading a file asks for the same few classes thousands of
  times, and each search looks through every module loaded.
  """
  found = _classesByPath.get(classPath)
  if found is not None:
    return found
  cls = _findFullyQualifiedClass(classPath)
  if cls is not None:
    _classesByPath[classPath] = cls
  return cls

def _findFullyQualifiedClass(classPath:str) -> Optional[type]:
  "*getFullyQualifiedClass()*'s search."
  DEBUG = False
  pathList = classPath.split(".")
  className = pathList[-1]
  cls:Optional[type] = None
  for _, mod in sys.modules.items():
    c = None
    try:
      c = getattr(mod, className)
    except:
      continue
    if DEBUG:
      if cls is not None and c is not cls:
        raise TypeError(f'Ambiguous class name "{className}": found "{getFullClassName(cls)}" and "{getFullClassName(c)}"')
      else:
        if getFullClassName(c) == classPath:
          cls = c
    else:
      if getFullClassName(c) == classPath:
        cls = c
        break
  return cls

#TODO: decide between the 2 implementations of getFullyQualifiedClass()

def getClassFromFullyQualifiedName(classPath:str) -> Optional[type]:
  """
  :param className: A string representing the fully qualified name of a class
  :return: Either a *Class* object or None
  
  Uses the FULLY QUALIFIED class name to retrieve the actual class.

  :param classPath:
  :type classPath: str
  """
  cls:Optional[type] = None
  try:
    modname, _, clsname = classPath.rpartition('.')
    if modname is None or modname == "":
      cls = getClass(clsname)
    else:
      mod = import_module(modname)
      cls = getattr(mod, clsname)
  except:
    pass 
  return cls 
  
def findSubclasses[T](cls:Type[T]) -> set[Type[T]]:
  '''
  :param cls: a class object to find all its loaded (imported subclasses)
  :return: A *set* of all subclasses of *subjectClass*
  '''
  return set(_originOf(cls).__subclasses__()).union(
      [s for c in _originOf(cls).__subclasses__() for s in findSubclasses(c)]) # type: ignore[var-annotated]
  
def _originOf(cls: type) -> type:
  """Extract the bare origin type from any generic alias form.

  Handles legacy ``Generic[T]``, PEP 585 ``list[int]``-style aliases,
  PEP 695 ``class Foo[T]`` aliases, and plain classes.

  :param cls: A class or generic alias.
  :type cls: type
  :returns: The unwrapped origin type.
  :rtype: type
  """
  # typing.get_origin handles most cases
  origin = get_origin(cls)
  if origin is not None:
    return origin
  # Fallback: any alias object that carries __origin__
  origin = getattr(cls, '__origin__', None)
  if origin is not None:
    return origin
  # Last resort: types.GenericAlias (e.g. list[int], tuple[int,...])
  if isinstance(cls, GenericAlias):
    return cls.__origin__
  return cls

def findConcreteSubclasses[T](abstractClass: Type[T]) -> list[Type[T]]:
  """Return all concrete (non-abstract) subclasses of an abstract class.

  Recursively walks the subclass tree, collecting any class that is not
  itself abstract. Handles PEP 695 (``class Foo[T]``), legacy
  ``Generic[T]``, and plain classes.

  :param abstractClass: The abstract base class to inspect, optionally
      parameterized.
  :type abstractClass: Type[T]
  :returns: A list of concrete subclass types.
  :rtype: list[Type[T]]
  """
  origin = _originOf(abstractClass)
  result: list[Type[T]] = []
  for sub in origin.__subclasses__():
    if not inspect.isabstract(sub):
      result.append(sub)
    # a concrete class may have concrete subclasses of its own (eg: a strategy
    # that reuses another's encoding), so always keep walking down
    s:Type[T]
    for s in findConcreteSubclasses(sub):
      if s not in result: # (a class reachable by more than one path)
        result.append(s)
  return result

def importSubmodules(packageName: str, filtr:Optional[Callable[[str], bool]]=None) -> None:
  """Import all modules in a package to ensure subclasses are registered.

  :param packageName: The dotted package name, e.g. ``'myapp.strategies'``.
  :type packageName: str
  :param filtr: If given, the module will only be loaded if *filter()* called with
    a scanned module name returns *True*. If absent, all scanned modules will be 
    imported.
  :type filtr: Optional[Callable[[str], bool]]=None
  """
  package = importlib.import_module(packageName)
  for _, moduleName, _ in pkgutil.walk_packages(
    path=package.__path__,
    prefix=package.__name__ + '.',
    ):
    if filtr is None or filtr(moduleName):
      importlib.import_module(moduleName)

def getCallerIdInfoStr(stack:int=1, includeArgs=True) -> str:
  """
  :param stack: An integer indicating how far back in the call stack to go. The
    default is 1, which indicates the caller of this method's caller.
  :return: A string of the form "[<class>.]<method>([self=<self>]) [line <lineno>]".
  :param includeArgs:
  :type includeArgs: bool
  """
  curframe = inspect.currentframe()
  calframe = inspect.getouterframes(curframe, 2)
  caller = calframe[stack+1]
  method = caller[3]
  lineNo = caller[2]
  file = os.path.basename(caller[1])
  argStr = ""
  if includeArgs:
    argvalues = inspect.getargvalues(caller[0])
    args:list[tuple[str, Any]] = []
    for name in argvalues[0]:
      args.append((name,argvalues.locals[name]))
    for k,v in args:
      val = repr(v) if isinstance(v, tk.Misc) else str(v)
      argStr += f', {k}={val}'
    if len(argStr)>2: argStr = argStr[2:]
  if "self" in caller.frame.f_locals:
    slf = caller.frame.f_locals["self"]
    clas = type(slf).__name__
    if len(argStr) == 0:
      argStr = "" if str(slf).startswith(".") else ("self="+str(slf))
    return f'{clas}.{method}({argStr}) [{file}:{lineNo}]'
  else:
    return f'{method}({argStr}) [{file}:{lineNo}]'

def extendsDoc(base:type):
  '''
  A decorator to the decorated method's docstring its namesake's in *base*,
  followed by its own.  Works on plain methods, classmethods and staticmethods,
  whichever order the decorators are in. Usage:
  
  .. code-block:: python
     :emphasize-lines: 2,2
  
     class Sub(Base):
       @extendsDoc(Base)
       def place(self, node):
         """
         In addition: relation labels are placed only if "place labels" is on.
         """
         ...  
  '''
  def decorate(f):
    func = getattr(f, "__func__", f) # (a classmethod or staticmethod: the function inside it)
    inherited = inspect.getdoc(getattr(base, func.__name__)) or ""
    own = inspect.cleandoc(func.__doc__ or "")
    func.__doc__ = f"{inherited}\n\n{own}" if inherited and own else inherited or own
    if f is not func:
      f.__doc__ = func.__doc__ # (the wrapper copied the old docstring when it was made)
    return f
  return decorate

################################################################################
# ---- LIST MANIPULATION -------------------------------------------------------
################################################################################

def delOne[T](lst:list[T], val:T, 
              comparator:Callable[[T,T],bool]=lambda a,b: a is b, 
              throw:bool=True) -> bool:
  '''
  Deletes exactly one item for the list, specifically, the first one found.
  
  :param lst: The target list.
  :type lst: list[T]
  :param val: the value to remove from the list.
  :type val: T
  :param comparator: A function to use to compare the values in the list to *val*.
    By default, *is* is used as the comparator.
  :type comparator: Callable[[T,T],bool] 
  :param throw: If not set to False, will raise a KeyError exception if no values
    that satisfy *comparator(<item>, val)* are found in the list. By default, this
    function will raise an exception if *val* is not found.
  :type throw: bool
  :returns: True iff item *val* is successfully removed from the list.
  :rtype: bool
  :raises KeyError: iff no item in the list matches *val*.
  '''
  for i, item in enumerate(lst):
    if comparator(item, val):
      del lst[i]
      return True
  if throw:
    raise KeyError(f"delOne() failed. Can't find {val} in {lst}.")
  return False

def grouped[T](iterable:Iterable[T], n:int) -> Iterable[tuple[T,...]]:
    '''
    Return an iterable of n-tuples which is a n-partition the parameter iterable:
     
    s -> (s0,s1,s2,...sn-1), (sn,sn+1,sn+2,...s2n-1), (s2n,s2n+1,s2n+2,...s3n-1), ...
    
    Thus, list(grouped([1,2,3,4], 2)) -> [(1,2),(3,4)]
    
    :param iterable: The target iterable.
    :type iterable: Iterable[T]
    :param n: the size of the partitions, ie: the size of the tuples.
    :type n: int
    :returns: a iterable of n-Tuples.
    :rtype: Iterable[tuple[T,...]]
    '''
    return zip(*[iter(iterable)]*n)

def removeDuplicates(items:list, asTree:bool=False) -> list:
  '''
  Return a copy of the *items* list with any duplicates (determine by the "==" 
  operator) removed. The first of any duplicates are the ones that are kept.

  :param items:
  :type items: list
  :param asTree:
  :type asTree: bool
  :returns:
  :rtype: list
  '''
  def do(items:list, asTree:bool, seen:list):
    ret = []
    for i in range(len(items)):
      if items[i] not in seen:
        if asTree and isinstance(items[i], list):
          sublist = do(items[i], asTree, seen)
          if len(sublist) > 0:
            ret.append(sublist)
        else:
          ret.append(items[i])
        seen.append(items[i])
    return ret
  return do(items, asTree, [])

def removeDuplicatesInPlace(items:list, removeLater=True) -> None:
  '''
  :param list: The list to remove duplicates from.
  :param removeLater: [bool, default: True] Iff True, keep the first of any 
      duplicates, otherwise keep the last.
  
  Removes any duplicates from the *items* list (determine by the "==" operator)
  in place.

  :param items:
  :type items: list
  '''
  removals:list = []
  for i in range(len(items)):
    for j in range(i):
      if items[i] == items[j]:
        removals.append(i if removeLater else j)
  removals.sort(reverse=True) # make sure we do deletions starting from the end of the list
  for i in removals:
    del items[i]
    
def flattenPairs(pairs):
  """
  From a vector of pairs, return a simple vector. [(1,2),(3,4)] -> [1,2,3,4]

  :param pairs:
  :type pairs:
  :returns:
  :rtype:
  """
  ret = []
  for p in pairs:
    ret.append(p[0])
    ret.append(p[1])
  return ret
  
def treeFlatten(tree:list, _omit:list=[]) -> list:
  """
  Flatten a tree formed by nested lists into a single flat list eliminating duplicates.
  
  eg: [1 [2 [6], 3 [4 [6], 5 [6]]]] --> [1, 2, 6, 3, 4, 5]

  :param tree:
  :type tree: list
  :param _omit:
  :type _omit: list
  :returns:
  :rtype: list
  """
  ret:list = []
  for item in tree:
    if isinstance(item, list):
      ret += treeFlatten(item, _omit=ret)
    elif item not in _omit and item not in ret:
      ret.append(item)
  return ret
  
def treeSplit(tree:list, _omit:list=[]):
  """
  Split a tree list into roots and the children
  
  eg: [1 [2 [6], 3 [4 [6], 5 [6]]]] --> [1], [2 [6], 3 [4 [6], 5 [6]]] and
  
  [2 [6], 3 [4 [6], 5 [6]] --> [2, 3], [6, 4, 5], [6, 6] (note that [6, 4, 5] are the 
    immediate parents "1 in the example above)

  :param tree:
  :type tree: list
  :param _omit:
  :type _omit: list
  :returns:
  :rtype:
  """
  roots = []
  branches = []
  for item in tree:
    if isinstance(item, list):
      branches += item
    elif item not in _omit:
      roots.append(item)
  return roots, branches
  

################################################################################
# ---- FLAGS -------------------------------------------------------------------
################################################################################

class ExtendedEnumMeta(EnumMeta):
  '''
  A metaclass for *ExtendedFlag*: looking up a name with "|" in it (eg: ``Flags["A|B"]``) gives the combined flags.
  '''
  @override
  def __getitem__(self, name):
    '''
    :param name:
    :type name:
    :returns:
    :rtype:
    '''
    items = name.split('|')
    ret:int = self(0)
    for i in items:
      i = i.strip()
      ret |= super().__getitem__(i)
    return ret

class ExtendedFlag(Flag, metaclass=ExtendedEnumMeta):

  '''
  A *Flag* whose members can be looked up by combined names (see *ExtendedEnumMeta*).
  '''
  @staticmethod
  def fromStr(spec:str):
    '''
    This cannot be right...

    :param spec:
    :type spec: str
    :returns:
    :rtype:
    '''
    #TODO This can't be right...
    typeAndExp = spec.split(".")
    if len(typeAndExp) == 2:
      typStr = typeAndExp[0]
      typ = getFullyQualifiedClass(typStr)
      if typ is None:
        raise TypeError(f'ExtendedFlag.fromStr(): Unknown type {typStr}.')
      return typ(typeAndExp[1])
    if len(typeAndExp) == 1:
      return spec

  @override
  def __str__(self) -> str:
    '''
    :returns:
    :rtype: str
    '''
    result = super().__str__()
    resultList = result.split(".")
    result = ".".join([getFullClassName(self.__class__), resultList[1]])
    return result
    
################################################################################
# ---- SOUNDS ------------------------------------------------------------------
################################################################################

def play(soundFile:Optional[str]=None) -> None:
  """
  Plays a sound file: with *afplay* on macOS, *winsound* on Windows (a .wav
  file), and *paplay* or *aplay* on Linux (if there's one).
  
  :param soundFile: May have the following values:
  
    - None: plays an error beep (on macOS, "/System/Library/Sounds/Sosumi.aiff").
    - Just a file name: (not containing any slashes ("/")) on macOS, looks in
        /System/Library/Sounds/ for the file.
    - A path: (containing slashes ("/")) just tries to play that file.
    
  """
  import shutil
  if sys.platform == "win32":
    import winsound # @UnresolvedImport
    if soundFile:
      winsound.PlaySound(soundFile, winsound.SND_FILENAME | winsound.SND_ASYNC)
    else:
      winsound.MessageBeep(winsound.MB_ICONHAND)
    return
  if sys.platform != "darwin":
    player = shutil.which("paplay") or shutil.which("aplay")
    if soundFile and player is not None:
      subprocess.Popen([player, soundFile], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
      print("\a", end="", flush=True)
    return
  if soundFile is None or len(soundFile)==0:
    soundFile = '/System/Library/Sounds/Sosumi.aiff'
  elif soundFile.find('/') < 0:
    soundFile = '/System/Library/Sounds/'+soundFile
  subprocess.Popen(["afplay", soundFile])


################################################################################
# ---- XML ---------------------------------------------------------------------
################################################################################

def xmlEscape( strXML: str ) -> str:
  """
  Replaces the "&", "<", ">", and single and double quote characters with xml escape codes.

  :param strXML:
  :type strXML: str
  :returns:
  :rtype: str
  """
  return strXML  .replace("&", "&amp;") \
          .replace("<",  "&lt;") \
          .replace(">",  "&gt;") \
          .replace("\"", "&quot;") \
          .replace("'",  "&apos;") \
          .replace("\n", "&#10;") \
          .replace("\t", "&#9;") 

def xmlUnescape( strXML: str ) -> str:
  """
  Replaces XML escape codes with "&", "<", ">", and single and double quote characters.

  :param strXML:
  :type strXML: str
  :returns:
  :rtype: str
  """
  return strXML  .replace("&amp;", "&") \
          .replace("&lt;",   "<") \
          .replace("&gt;",   ">") \
          .replace("&quot;", "\"") \
          .replace("&apos;", "'") \
          .replace("&#10;",  "\n") \
          .replace("&#9;",   "\t") 

def xmlToStringIndented(elem:Element, **kwargs):
  '''
  Emulate an *ElementTree.tostring()* function, but with indents similar to
  what you get with the *ElementTree.indent()* method only for Elements.

  :param elem:
  :type elem: Element
  :param kwargs:
  :type kwargs:
  :returns:
  :rtype:
  '''
  if "encoding" not in kwargs:
    kwargs["encoding"] = "unicode"
  strings = ElementTree.tostringlist(elem, **kwargs)
  output = ""
  indent = 0
  tabWidth = 2
  for line in strings:
    if line.startswith(" "):
      output += line
    elif line.startswith("</"):
      indent -= tabWidth # the unindent plus cancel the > indent to come at then end of this <>.
      output += ("\n" if len(output)>0 else "") + (" " *indent) + line 
    elif line.startswith("<"):
      output += ("\n" if len(output)>0 else "") + (" " *indent) + line 
    elif line.startswith(">"):
      output += line
      indent += tabWidth
    elif line.startswith(" />"):
      output += line
      indent -= tabWidth
    else:
      print("not sure what to do with '"+line+"'")
  return output
      
################################################################################
# ----GRAPHIC UtiLItiES --------------------------------------------------------
################################################################################

PointIndici = float
'Use this globally to choose if *Points* and *Rects* store indices as *int* or *float* values.'

class Point(Sequence):
  '''
  Implementation of an (x,y) point in a flexible but constrained way. Whether
  indices are int or float depends on the value of *PointIndici*. 
  '''
  @overload
  def __init__(self, x:PointIndici, y:PointIndici) -> None: ...
  @overload
  def __init__(self, pair:Iterable[PointIndici]) -> None: ...
  def __init__(self, *args) -> None: # type: ignore[misc] # MyPy doesn't match *args to overloads
    '''
    Overloaded constructor that will take either to *PointInidici* arguments as
    *x* and *y*, or any *Iterator* of two *PointInidicis*.

    :param args:
    :type args:
    '''
    if len(args) == 1:
      if isinstance(args[0], Iterable):
        args = tuple(args[0])
      else:
        raise TypeError(f'Point() constructor with 1 argument must be a Sequence or Iterable type (got type {args[0].__class__.__name__}).')
    if len(args) != 2: 
      raise TypeError(f'Point() constructor takes 1 or 2 arguments ({len(args)} given).')
    self.x = PointIndici(args[0])
    self.y = PointIndici(args[1])
    if not isinstance(self.x, PointIndici) or not isinstance(self.y, PointIndici):
      raise TypeError(f'Point() constructor must take two {PointIndici.__name__} arguments (got types {self.x.__class__.__name__} and {self.y.__class__.__name__})')
  
  @overload
  def __getitem__(self, index:int)-> PointIndici: ...
  @overload
  def __getitem__(self, index:slice[Any, Any, Any], /) -> Sequence[PointIndici]: ...
  def __getitem__(self, index:Union[int,slice[Any, Any, Any]]) -> Union[PointIndici,Sequence[PointIndici]]:
    '''
    Implementation of indexing ([]). Works exactly like *tuple*[index]* 
    where index may be an *int* or a *slice*.

    :param index:
    :type index: Union[int, slice[Any, Any, Any]]
    :returns:
    :rtype: Union[PointIndici, Sequence[PointIndici]]
    '''
    x = self.asTuple()
    return x[index]

  def __len__(self) -> int:
    '''
    Implementation for *len()*. Always returns 2.

    :returns:
    :rtype: int
    ''' 
    return 2

  def __iter__(self) -> Generator:
    'Iterator implementation.'
    yield self.x
    yield self.y
    
  def asTuple(self) -> tuple:
    '''
    Returns *self* as a *tuple*.

    :returns:
    :rtype: tuple
    ''' 
    return (self.x, self.y)
  
  def asList(self)  -> list:
    '''
    Returns *self* as a *list*.

    :returns:
    :rtype: list
    ''' 
    return [self.x, self.y]
  
  def __add__(self, other:Union[Iterable,Self]):
    """
    None mutating overload of the + operator to add the corresponding indices.

    :param other:
    :type other: Union[Iterable, Self]
    :returns:
    :rtype:
    """
    if not isinstance(other, Point):
      other = Point(other) # will throw if the type of other is incompatible
    return Point(self.x + other.x, self.y + other.y)
  
  def moveBy(self, x:Optional[PointIndici]=None, y:Optional[PointIndici]=None):
    """
    Mutating version of adding the corresponding values of x and y

    :param x:
    :type x: Optional[PointIndici]
    :param y:
    :type y: Optional[PointIndici]
    """
    if x is not None:
      self.x += x 
    if y is not None:
      self.y += y
      
  def __eq__(self, other:Any) -> bool:
    '''
    Overload of the == operator where the second operand may be a *Point* or a
    two-element iterator of *PointIndici*.

    :param other:
    :type other: Any
    :returns:
    :rtype: bool
    '''
    if not isinstance(other, Point):
      try:
        other = Point(other)
      except:
        return False
    return (self.x == other.x) and (self.y == other.y)
       
  def __str__(self) -> str:
    '''
    Return the in "(<x>,<y>)" form.

    :returns:
    :rtype: str
    '''
    return f'({self.x},{self.y})'
  
# @dataclass
# class WHRect(Point):
#   w: PointIndici
#   h: PointIndici
#   @classmethod
#   def fromWHRect(cls, p:Iterable):
#     'User to construct a *Point* from an iterable like a tuple or a list'
#     plist = list(p)
#     assert len(plist) == 4
#     return WHRect(plist[0], plist[1], plist[2], plist[3])
#   @classmethod
#   def fromTkPoints(cls, p:Iterable):
#     'User to construct a *Point* from an iterable like a tuple or a list'
#     plist = list(p)
#     assert len(plist) == 4
#     plist = normalizeRect(plist)
#     return WHRect(plist[0], plist[1], plist[2]-plist[0], plist[3]-plist[1])
#   def __iter__(self):
#     yield self.x
#     yield self.y
#     yield self.w
#     yield self.h
#   def asTkTuple(self)     -> Tuple: return (self.x, self.y, self.x+self.w, self.y+self.h)
#   def asTkList(self)      -> list:  return [self.x, self.y, self.x+self.w, self.y+self.h]
#   def aspectRatio(self) -> float: return self.w/self.h
#   def centre(self)      -> Point: return Point(self.x+self.w/2.0, self.y+self.h/2.0)
#   def topLeft(self)     -> Point: return Point(self.x, self.y)
#   def resize(self, w:Optional[PointIndici]=None, h:Optional[PointIndici]=None):
#     if w is not None:
#       self.w = w 
#     if h is not None:
#       self.h = h 

def pointInRect(pt:Iterable[PointIndici], rect:Iterable[PointIndici]) -> bool:
  """
  :param pt: (x,y) 
  :param rect: (x,y,x1,y1)
  :return: *True* iff the give *pt* lies inside *rect*.
  """
  rlist:list[PointIndici] = list(rect)
  assert len(rlist) == 4
  plist:list[PointIndici] = list(pt)
  assert len(plist) == 2
  return pointInPoly(plist, [*(rlist[0], rlist[1]),
              *(rlist[2], rlist[1]),
              *(rlist[2], rlist[3]),
              *(rlist[0], rlist[3])])
              
def shiftRectToPoint(rect:Iterable[PointIndici], point:Iterable[PointIndici]) -> list[PointIndici]:
  """
  :param pt: (x,y) 
  :param rect: (x,y,x1,y1)
  :return: A new rectangle if the same size and aspect ratio as *rect*, but with the 
    upper left corner at *pt*
  :param point:
  :type point: Iterable[PointIndici]
  """
  rect = iterableToList(rect)
  point = iterableToList(point)  
  return [point[0], point[1], point[0]+rect[2]-rect[0], point[1]+rect[3]-rect[1]]
                    
def overlaps(rect1:Iterable[PointIndici], rect2:Iterable[PointIndici]) -> bool:
  """
  :param rect1: (x,y,x1,y1)
  :param rect2: (x,y,x1,y1)
  :return: *True* iff the two rectangles overlap.
  """
  def overlapDim(a1, a2, b1, b2):
    return not(a2 < b1 or b2 < a1)
  rect1 = iterableToList(rect1)
  rect2 = iterableToList(rect2)
  return overlapDim(rect1[0], rect1[2], rect2[0], rect2[2]) and \
          overlapDim(rect1[1], rect1[3], rect2[1], rect2[3])

def pointInPoly(pt:Iterable[PointIndici], poly:Iterable[PointIndici]) -> bool:
  """
  :param pt: (x,y) 
  :param poly: (x,y [,x1,y1]...)
  :return: *True* iff the give *pt* lies inside *poly*.
  """
  # Ray casting: count the polygon's edges crossed by a ray from *pt* to the
  # right; an odd number means it's inside. (Pure Python: this used to use
  # matplotlib, which a packaged app would then have to carry along.)
  x, y = iterableToList(pt)[:2]
  poly = iterableToList(poly)
  vertices = [(poly[i], poly[i+1]) for i in range(0, len(poly) - 1, 2)]
  inside = False
  for (x1, y1), (x2, y2) in zip(vertices, vertices[1:] + vertices[:1]):
    if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
      inside = not inside
  return inside

def midpoint(*pts:Iterable[PointIndici]) -> Tuple[PointIndici, PointIndici]:
  """
  :param pts: A list of point pairs
  :return: The point midway between all the *pts*
  """
  n = len(pts)
  sumX = sumY = 0
  try:
    for p in pts:
      p = iterableToList(p)
      sumX += p[0]
      sumY += p[1]
  except Exception as ex:
    raise ex
  return (sumX/n, sumY/n)
  
def expandRect(rect:Iterable[PointIndici], spacing:Iterable[PointIndici]|PointIndici) -> list[PointIndici]:
  """
  :param rect: The rectangle to expand.
  :param spacing: The vector of points to expand *rect* as [left, top, right, bottom]. May be of length
    1, 2, or 4 or an int or a float, with the obvious interpretations.
  :return: A new rectangle representing the expansion of *rect*
  """ 
  rect = list(rect)
  if isinstance(spacing, (int, float)):
    spacing = [spacing, spacing, spacing, spacing]
  else:
    spacing = list(spacing)
    if len(spacing) == 1:
      spacing.append(spacing[0])
    if len(spacing) == 2:
      spacing.append(spacing[0])
      spacing.append(spacing[1])
  return  [rect[0]-spacing[0],
       rect[1]-spacing[1],
       rect[2]+spacing[2],
       rect[3]+spacing[3]]
  
def normalizeRect(rect:Iterable[PointIndici]) -> list[PointIndici]:
  """
  Fix up a rect (x,y,x1,y1) such that x<x1 and y<y1, in conformance to tk rules.
  
  :param: rect:
  :return: A new rectangle same as *rect*, but s/t x<x1 and y<y1.
  :param rect:
  :type rect: Iterable[PointIndici]
  """
  rect = iterableToList(rect)
  return [rect[0] if rect[0]<rect[2] else rect[2],
      rect[1] if rect[1]<rect[3] else rect[3],
      rect[2] if rect[0]<rect[2] else rect[0],
      rect[3] if rect[1]<rect[3] else rect[1]]
      
def iterableToList(it: Iterable) -> list:
  '''
  :param it:
  :type it: Iterable
  :returns:
  :rtype: list
  '''
  return list(it)
  # if isinstance(it, (list,tuple)):
  #   return it
  # ret = []
  # for i in it: 
  #   ret.append(i)
  # return ret
    
    
################################################################################
# ---- TK USER INTERFACE ----------------------------------------------------------
################################################################################

def getSubMenu(menu:tk.Menu, name:str, makeIfNone:int|str|None=tk.END) -> Optional[tk.Menu]:
  """
  Find a submenu in *menu* with label *name* .

  :param menu: The menu to search
  :param name: The label of the item we are searching for
  :param makeIfNone: [default: tk.END (insert at end)] if not *None* and *menu* does not
      contain any menu items named *name* then insert a new menu named *name* at position
      *makeIfNone* -- either an *int* index or one of Tkinter's symbolic index constants
      (e.g. *tk.END*, which is itself just the *str* "end"; this is what *insert_cascade()*
      itself accepts, so we just pass it straight through).
  :return: Return a *tk.Menu* if it is found or created; if it is not found and
      *makeIfNone* is *None*, return *None* .
  """
  submenu = None
  try:
    index = menu.index(name)
    assert index is not None and menu.type(index) == "cascade"
    submenu = menu.entrycget(index,'menu')
    submenu = menu.winfo_toplevel().nametowidget(submenu)
  except Exception:
    if makeIfNone is not None:
      assert isinstance(makeIfNone, (int, str))
      submenu = tk.Menu(menu) #TODO: should probably make an effort to put this in the right place
      menu.insert_cascade(makeIfNone, label=name, menu=submenu)
  return submenu

def getToplevelWindows(root:tk.Tk):
  '''
  *root*'s top-level windows.
  '''
  return [x for x in root.winfo_children() if isinstance(x , tk.Toplevel)]

def getMenuBar() -> Optional[tk.Menu]:
  """
  Resolve the app's menu bar -- the configured menu of ``tk._default_root``.

  :return: The resolved *tk.Menu*, or *None* if there's no default root, or
      it has no menu bar configured.
  """
  root = tk._default_root  # type: ignore[attr-defined] # @UndefinedVariable
  if root is None:
    return None
  menuName = root.cget("menu")
  if not menuName:
    return None
  return root.nametowidget(menuName)

def _findEntry(menu:tk.Menu, label:str) -> tuple[Optional[int], Optional[str]]:
  """
  :param menu: The menu to search.
  :param label: The label of the item we are searching for.
  :return: *(index, type)* of the entry in *menu* labelled *label*, or
      *(None, None)* if there is no such entry.
  """
  try:
    # Menu.index(label) raises TclError (not "returns None") when no entry
    # matches -- e.g. on an otherwise-empty menu -- so absence has to be
    # caught, not tested for. Same gotcha getSubMenu() above works around.
    index = menu.index(label)
  except tk.TclError:
    return None, None
  if index is None:
    return None, None
  return index, menu.type(index)

_separatedItems:set[tuple[str, str]] = set()
"(menu, label) of the items added with a separator just above them (see *addToMenuBar()*'s *separatorBefore*)."

def _separate(menu:tk.Menu, label:str, separatorBefore:bool) -> None:
  '''
  If *separatorBefore*: make sure the item labelled *label* in *menu* has a
  separator just above it (unless it's the first), and note that it's the
  item's, to go with it (see *removeFromMenuBar()*).

  :param menu: The menu.
  :param label: The item's label.
  :param separatorBefore: Whether it has a separator above it.
  '''
  if not separatorBefore:
    return
  index, _ = _findEntry(menu, label)
  if index is None:
    return
  _separatedItems.add((str(menu), label))
  if index > 0 and menu.type(index - 1) != "separator":
    menu.insert_separator(index)

_lastItems:set[tuple[str, str]] = set()
"(menu, label) of the items kept at the end of their menus (see *keepLast()*)."

def keepLast(menu:tk.Menu, *labels:str) -> None:
  '''
  Keep the items labelled *labels* in *menu* at its end: items *addToMenuBar()*
  and *addCheckToMenuBar()* add later go above them (and above the separator
  just above them, if there is one) -- eg: "Quit" at the end of a File menu.

  :param menu: The menu.
  :param labels: Its items' labels.
  '''
  _lastItems.update((str(menu), label) for label in labels)

def _endIndex(menu:tk.Menu) -> int|str:
  '''
  :returns: Where a new item goes at the end of *menu*: *tk.END*, or above the
    items kept last (see *keepLast()*).
  '''
  last = menu.index(tk.END)
  if last is None:
    return tk.END
  for i in range(last + 1):
    if menu.type(i) not in ("separator", "tearoff") and (str(menu), menu.entrycget(i, "label")) in _lastItems:
      return i - 1 if i > 0 and menu.type(i - 1) == "separator" else i
  return tk.END

def afterMenu(command:Callable[[], Any]) -> Callable[[], None]:
  """
  *command*, to run as a menu item's command: on macOS, once the menu's done
  with -- from the event loop, not from inside AppKit's menu action. A
  command that waits there (eg: a modal dialog's *wait_window()*) hangs the
  app, with the spinning beachball, on recent macOS versions: the menu bar's
  action never finishes. Elsewhere, *command* itself.

  :param command: What the menu item does.
  :type command: Callable[[], Any]
  :return: The menu item's command.
  :rtype: Callable[[], None]
  """
  if not _MAC:
    return command
  def deferred() -> None:
    root = tk._default_root # type: ignore[attr-defined]
    if root is None:
      command()
    else:
      root.after_idle(command)
  return deferred

def addToMenuBar(path:str, command:Optional[Callable]=None, *, menu:Optional[tk.Menu]=None,
    accelerator:Optional[str]=None, cascadePositions:Optional[dict[str, int]]=None,
    separatorBefore:bool=False, enabled:bool=True) -> None:
  """
  Add -- or, if already present, replace -- an entry in the app's menu bar.

  Pass exactly one of *command* or *menu*: *command* adds/replaces a plain
  command entry that invokes *command* when chosen; *menu* adds/replaces a
  cascade entry whose submenu is *menu*. The top-level menu bar itself is
  always the app's own -- resolved from ``tk._default_root``'s configured
  menu (see *getMenuBar()*) -- there's no need to look it up and pass it in.

  :param path: A ``"|"``-separated path of cascade labels ending in the
      item's own label, e.g. ``"File|Save view"``. All but the last segment
      name cascade submenus, created via *getSubMenu()* if they don't
      already exist; the last segment is the item's own label.
  :param command: The callable to invoke when the item is chosen. Give this
      to add/replace a plain command item; mutually exclusive with *menu*.
      On macOS it's run once the menu's done with (see *afterMenu()*).
  :param menu: The submenu to show as a cascade. Give this to add/replace a
      cascade item; mutually exclusive with *command*.
  :param accelerator: Optional accelerator string to display (e.g. "Cmd+S").
  :param cascadePositions: Where to put any cascade that has to be made, by
      label, eg: ``{"Edit": 1}``; by default, at the end (as for *addCheckToMenuBar()*).
  :param separatorBefore: Put a separator just above the item (unless it's
      the first, or there's one there already): it starts a group of items.
      *removeFromMenuBar()* removes the separator with the item.
  :param enabled: Whether the item can be chosen; if not, it's greyed out
      (see *enableMenuBarItem()*, to change that later).
  :note: Safe to call repeatedly with the same *path* -- e.g. every time a
      window gains focus -- since an existing entry with the same final
      label is reconfigured in place rather than duplicated (and, if it was
      previously the other kind of entry -- command vs. cascade -- it's
      replaced in place, at the same position). So a window can add its
      items unconditionally whenever it gains focus.
  """
  assert (command is None) != (menu is None), \
      'addToMenuBar(): pass exactly one of command= (add/replace a command item) or menu= (add/replace a cascade item).'
  segments = path.split("|")
  assert len(segments) >= 1, 'addToMenuBar(): empty path.'
  target = getMenuBar()
  assert target is not None, \
      'addToMenuBar(): no default menu bar could be resolved (no default root, or it has no menu configured).'
  for seg in segments[:-1]:
    target = getSubMenu(target, seg, makeIfNone=(cascadePositions or {}).get(seg, tk.END))
    assert target is not None # (made if it isn't there)
  label = segments[-1]
  kwargs:dict[str, Any] = {} if accelerator is None else {"accelerator": accelerator}
  wantType = "command" if command is not None else "cascade"
  found, existingType = _findEntry(target, label)
  if found is not None and existingType != wantType:
    target.delete(found)  # entry exists but as the other kind -- replace it in place
  index:int|str = _endIndex(target) if found is None else found
  state = tk.NORMAL if enabled else tk.DISABLED
  if command is not None:
    command = afterMenu(command) # (on macOS, not from inside the menu's action)
    if existingType == wantType:
      target.entryconfig(index, command=command, state=state, **kwargs)
    else:
      target.insert_command(index, label=label, command=command, state=state, **kwargs)
  else:
    assert menu is not None
    if existingType == wantType:
      target.entryconfig(index, menu=menu, state=state, **kwargs)
    else:
      target.insert_cascade(index, label=label, menu=menu, state=state, **kwargs)
  _separate(target, label, separatorBefore)

def addCheckToMenuBar(path:str, variable:tk.Variable, command:Optional[Callable]=None, *,
                      cascadePositions:Optional[dict[str, int]]=None, separatorBefore:bool=False,
                      enabled:bool=True) -> None:
  """
  Add -- or, if already present, replace -- a check item in the app's menu
  bar: it shows (and sets) the boolean *variable*, and calls *command* when
  chosen. Like *addToMenuBar()*, safe to call repeatedly with the same *path*
  (eg: each time a window gains focus, rebinding it to that window's variable),
  and removed with *removeFromMenuBar()*.

  :param path: A ``"|"``-separated path of cascade labels ending in the
      item's own label, e.g. ``"View|Animation toolbar"``.
  :param variable: The (boolean) variable the item shows and sets.
  :param command: Called (after *variable* is set) when the item is chosen.
  :param cascadePositions: Where to put any cascade that has to be made, by
      label, eg: ``{"View": 1}`` (just after "File"); by default, at the end.
  :param separatorBefore: As for *addToMenuBar()*.
  :param enabled: As for *addToMenuBar()*.
  """
  segments = path.split("|")
  target = getMenuBar()
  assert target is not None, \
      'addCheckToMenuBar(): no default menu bar could be resolved (no default root, or it has no menu configured).'
  for seg in segments[:-1]:
    target = getSubMenu(target, seg, makeIfNone=(cascadePositions or {}).get(seg, tk.END))
    assert target is not None # (made if it isn't there)
  label = segments[-1]
  found, _existingType = _findEntry(target, label)
  if found is not None:
    target.delete(found) # (rebuilt: a check item's variable can't be rebound by entryconfig on every platform)
  index:int|str = _endIndex(target) if found is None else found
  target.insert_checkbutton(index, label=label, variable=variable, onvalue=True, offvalue=False,
                            command=command, state=tk.NORMAL if enabled else tk.DISABLED) # type: ignore[arg-type] # (command=None: tkinter leaves it out)
  _separate(target, label, separatorBefore)

def enableMenuBarItem(path:str, enabled:bool=True) -> None:
  """
  Let an entry (as added by *addToMenuBar()* or *addCheckToMenuBar()*) in the
  app's menu bar be chosen -- or grey it out, so it can't be, eg: while what
  it does can't be done. Safe to call even when the item isn't there (a
  no-op), as *removeFromMenuBar()* is.

  :param path: Same ``"|"``-separated path as passed to *addToMenuBar()*.
  :param enabled: Whether it can be chosen.
  """
  target = getMenuBar()
  for seg in path.split("|")[:-1]:
    if target is None:
      return
    target = getSubMenu(target, seg, makeIfNone=None)
  if target is None:
    return
  index, _ = _findEntry(target, path.split("|")[-1])
  if index is not None:
    target.entryconfig(index, state=tk.NORMAL if enabled else tk.DISABLED)

def removeFromMenuBar(path:str) -> None:
  """
  Remove an entry (as added by *addToMenuBar()*) from the app's menu bar --
  and the separator above it, if it was added with one (*separatorBefore*).

  Safe to call even when the item (or an intervening cascade) isn't
  currently present -- this is simply a no-op in that case, so callers
  (eg: a window's focus-out handler) don't need to track whether they
  actually added the item first.

  :param path: Same ``"|"``-separated path as passed to *addToMenuBar()*.
  """
  segments = path.split("|")
  assert len(segments) >= 1, 'removeFromMenuBar(): empty path.'
  target = getMenuBar()
  if target is None:
    return
  for seg in segments[:-1]:
    target = getSubMenu(target, seg, makeIfNone=None)
    if target is None:
      return
  label = segments[-1]
  index, _ = _findEntry(target, label)
  if index is not None:
    target.delete(index)
    # (the separator it was added with: see addToMenuBar()'s separatorBefore)
    if (str(target), label) in _separatedItems and index > 0 and target.type(index - 1) == "separator":
      target.delete(index - 1)

def isGuiAvailable() -> bool:
  """Determine whether a graphical display environment appears to be available.

  :returns: True if a GUI environment is likely usable, False otherwise.
  :rtype: bool
  """
  if sys.platform.startswith("win") or sys.platform == "darwin":
    return True
  # On X11/Wayland Linux systems, check the relevant env vars.
  return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def askViaTk(prompt: str, title: str = "Input required", check:Callable[[str],bool]=lambda s: True) -> Optional[str]:
  """Prompt the user for input using a Tkinter dialog: in the running Tk
  application, if there is one (over its focused window); otherwise in a Tk
  interpreter of its own, made for it and destroyed afterwards.

  :param prompt: The message to display to the user.
  :type prompt: str
  :param title: The dialog window title.
  :type title: str
  :returns: The user's input, or None if the dialog could not be created or was cancelled.
  :rtype: Optional[str]
  """
  try:
    import tkinter as tk
    from tkinter import simpledialog
  except ImportError:
    return None

  try:
    # In an app that's already running Tk, ask in it: a second Tk interpreter
    # shares the app's menu bar (on macOS), and destroying it can leave the
    # system's default menu bar in place of the app's.
    existing = tk._default_root # type: ignore[attr-defined] # @undefinedVariable
    if existing is not None:
      try:
        focused = existing.focus_get()
      except KeyError: # (eg: a menu's popdown, which isn't a Python widget)
        focused = None
      parent = focused.winfo_toplevel() if focused is not None else existing
      while True:
        ret = simpledialog.askstring(title, prompt, parent=parent)
        if ret is None or len(ret) == 0:
          return None
        if check(ret):
          return ret
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    
    while True:
      result = simpledialog.askstring(title, prompt, parent=root)
      if result is None or len(result) == 0:
        result = None
        break
      if check(result):
        break
    root.destroy()
    return result
  except tk.TclError:
    # DISPLAY was set but no display server actually responded.
    return None


def askViaTerminal(prompt: str, check:Callable[[str],bool]=lambda s: True) -> Optional[str]:
  """Prompt the user for input via stdin/stdout.

  :param prompt: The message to display to the user.
  :type prompt: str
  :returns: The user's input, or None if stdin is not interactive.
  :rtype: Optional[str]
  """
  if not sys.stdin.isatty():
    return None
  try:
    while True:
      ret = input(f"{prompt}: ")
      if ret is None or len(ret)==0:
        return None
      if check(ret):
        return ret
  except (EOFError, KeyboardInterrupt):
    return None


def askYesNo(question:str, title:str) -> bool:
  '''
  Ask the user a yes-or-no question: in a Yes/No dialog over the focused
  window, if the GUI is running; otherwise (eg: the terminal interface, or
  once the windows are gone at exit) as text (see *util.utils.askUser()*).

  :param question:
  :type question: str
  :param title: The dialog's title.
  :type title: str
  :returns: True iff the answer is yes.
  :rtype: bool
  '''
  import tkinter as tk
  root = tk._default_root # type: ignore[attr-defined] # @undefinedVariable
  if root is not None:
    from tkinter import messagebox
    try:
      focused = root.focus_get()
    except KeyError: # (eg: a menu's popdown, which isn't a Python widget)
      focused = None
    while True:
      return bool(messagebox.askyesno(title, question, parent=focused.winfo_toplevel() if focused is not None else root))
  def check(ans:str):
    return ans.strip().upper() in ("Y", "YES", "T", "TRUE", "N", "NO", "F", "FALSE")
  ans = askUser(f'{question}\n(Y/N):', title, check)
  return ans is not None and ans.strip().upper() in ("Y", "YES", "T", "TRUE")

def askUser(prompt: str, title: str = "Input required", check:Callable[[str],bool]=lambda s: True) -> Optional[str]:
  """Ask the user a question, using a GUI dialog if available and falling back to the terminal.

  :param prompt: The message to display to the user.
  :type prompt: str
  :param title: The dialog window title, used only in GUI mode.
  :type title: str
  :param check: A function to validate user input.
  :type check: check:Callable[[str],bool]
  :returns: The user's input, or None if no input method succeeded.
  :rtype: Optional[str]
  """
  if isGuiAvailable():
    result = askViaTk(prompt, title, check)
    if result is not None:
      return result
  return askViaTerminal(prompt)

class VerticalScrolledFrame(ttk.Frame):
    """
    A pure Tkinter scrollable frame that actually works!

    * Use the 'interior' attribute to place widgets inside the scrollable frame.
    * Construct and pack/place/grid normally.
    * This frame only allows vertical scrolling: with its scroll bar, the
      mouse wheel, or a shift-drag, anywhere over its interior.
    """
    SCROLL_TAG = "VerticalScrolledFrame.scroll"
    "The bindtag that makes the wheel and shift-drag scroll, put on everything in an interior (see *_scrollable()*)."

    def __init__(self, parent, *args, **kw):
        '''
        A frame that scrolls vertically: put widgets in its *interior*.
        '''
        ttk.Frame.__init__(self, parent, *args, **kw)

        # Create a canvas object and a vertical scrollbar for scrolling it.
        vscrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL)
        vscrollbar.pack(fill=tk.Y, side=tk.RIGHT, expand=tk.FALSE)
        canvas = tk.Canvas(self, bd=0, highlightthickness=0,
                           yscrollcommand=vscrollbar.set, yscrollincrement=20)
        self.canvas = canvas
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=tk.TRUE)
        vscrollbar.config(command=canvas.yview)

        # Reset the view
        canvas.xview_moveto(0)
        canvas.yview_moveto(0)

        # Create a frame inside the canvas which will be scrolled with it.
        self.interior = interior = ttk.Frame(canvas)
        interior_id = canvas.create_window(0, 0, window=interior,
                                           anchor=tk.NW)

        # Track changes to the canvas and frame width and sync them,
        # also updating the scrollbar.
        def _configure_interior(event):
            # Update the scrollbars to match the size of the inner frame.
            size = (interior.winfo_reqwidth(), interior.winfo_reqheight())
            canvas.config(scrollregion=(0, 0, size[0] ,size[1]))
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # Update the canvas's width to fit the inner frame.
                canvas.config(width=interior.winfo_reqwidth())
        interior.bind('<Configure>', _configure_interior)

        def _configure_canvas(event):
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # Update the inner frame's width to fill the canvas.
                canvas.itemconfigure(interior_id, width=canvas.winfo_width())
        canvas.bind('<Configure>', _configure_canvas)

        # The wheel and shift-drag scroll it over anything in it: widgets added
        # since are tagged when the interior grows, or the mouse comes in.
        if not self.bind_class(self.SCROLL_TAG):
            for sequence in wheelEvents():
                self.bind_class(self.SCROLL_TAG, sequence, VerticalScrolledFrame._onWheel)
            self.bind_class(self.SCROLL_TAG, "<Shift-Button-1>", VerticalScrolledFrame._onShiftPress)
            self.bind_class(self.SCROLL_TAG, "<Shift-B1-Motion>", VerticalScrolledFrame._onShiftDrag)
        interior.bind('<Configure>', lambda _e: self._scrollable(canvas), add="+")
        canvas.bind('<Enter>', lambda _e: self._scrollable(canvas), add="+")
        self._scrollable(canvas)

    def _scrollable(self, widget:tk.Misc) -> None:
        '''
        Let the wheel and shift-drag scroll this frame over *widget* and
        everything in it (see *SCROLL_TAG*).
        '''
        tags = widget.bindtags()
        if self.SCROLL_TAG not in tags:
            widget.bindtags((self.SCROLL_TAG, *tags))
        for child in widget.winfo_children():
            self._scrollable(child)

    @staticmethod
    def _frameOf(event:tk.Event) -> "VerticalScrolledFrame|None":
        ''':returns: The *VerticalScrolledFrame* *event*'s widget is in, if any.'''
        w = event.widget
        while w is not None and not isinstance(w, VerticalScrolledFrame):
            w = getattr(w, "master", None)
        return w

    @staticmethod
    def _onWheel(event:tk.Event) -> str|None:
        '''The mouse wheel, over the interior: scroll it.'''
        frame = VerticalScrolledFrame._frameOf(event)
        if frame is None:
            return None
        frame.canvas.yview_scroll(-wheelSteps(event), "units")
        return "break" # (not a combobox's or a spinbox's change too)

    @staticmethod
    def _onShiftPress(event:tk.Event) -> str|None:
        '''Shift-press, over the interior: start dragging it (see *_onShiftDrag()*).'''
        frame = VerticalScrolledFrame._frameOf(event)
        if frame is None:
            return None
        frame.canvas.scan_mark(0, event.y_root)
        return "break" # (not extending a text selection too)

    @staticmethod
    def _onShiftDrag(event:tk.Event) -> str|None:
        '''Shift-drag, over the interior: it follows the mouse.'''
        frame = VerticalScrolledFrame._frameOf(event)
        if frame is None:
            return None
        frame.canvas.scan_dragto(0, event.y_root, gain=1)
        return "break"

def wheelSteps(event:tk.Event) -> int:
  '''
  :param event: A mouse wheel event (see *wheelEvents()*).
  :returns: How far it goes, in the wheel's steps: positive up (away from the
    user), negative down. On macOS, Tk's *delta* (a trackpad's small steps); on
    Windows and X11, *delta* / 120 (a notch), at least 1 either way; for X11's
    buttons 4 and 5 (Tk before 8.7), 1 and -1.
  '''
  num = getattr(event, "num", None)
  if num == 4:
    return 1
  if num == 5:
    return -1
  delta = int(event.delta)
  if _MAC or delta == 0:
    return delta
  steps = max(1, abs(delta) // 120)
  return steps if delta > 0 else -steps

def wheelEvents(shift:bool=False) -> list[str]:
  '''
  :param shift: The events with Shift held (on most systems, a sideways scroll).
  :returns: The event sequences a mouse wheel makes, to bind: "<MouseWheel>";
    and with Tk before 8.7 on X11, where the wheel is buttons 4 and 5,
    "<Button-4>" and "<Button-5>" too. (See *wheelSteps()*.)
  '''
  prefix = "Shift-" if shift else ""
  ret = [f"<{prefix}MouseWheel>"]
  if tk.TkVersion < 8.7 and not _MAC and sys.platform != "win32":
    ret += [f"<{prefix}Button-4>", f"<{prefix}Button-5>"]
  return ret

def _rightMouseEvents(window) -> list[str]:
  '''
  :returns: The event sequences of a right click in *window*. On macOS, Tk 8.6 calls the right
    button 2 and Tk 9 calls it 3 (as X11 and Windows do), and a trackpad's secondary click
    comes as whichever the running Tk uses, so both are bound, and Control-click too.
  '''
  if window.tk.call("tk", "windowingsystem") == 'aqua':
    return ["<2>", "<3>", "<Control-1>"]
  return ["<3>"]

def bindRightMouse(window, func):
  '''
  Bind *func* to a right click in *window*: also Control-click, on macOS.
  '''
  for seq in _rightMouseEvents(window):
    window.bind(seq, func)

def tag_bindRightMouse(window, id_, func):
  '''
  Bind *func* to a right click on canvas item *id_* (see *bindRightMouse()*).
  '''
  for seq in _rightMouseEvents(window):
    window.tag_bind(id_, seq, func)

def tag_unbindRightMouse(window, id_):
  '''
  Unbind a right click on canvas item *id_* (see *tag_bindRightMouse()*).
  '''
  for seq in _rightMouseEvents(window):
    window.tag_unbind(id_, seq)

def eventEqual(e1, e2):
  '''
  Whether *e1* and *e2* are the same event: of the same type, at the same place on the screen.
  '''
  return isinstance(e1, tk.Event) and isinstance(e2, tk.Event) and \
      e1.x_root == e2.x_root and \
      e1.y_root == e2.y_root and \
      e1.type   == e2.type
      
import traceback
import tkinter as tk
from tkinter import scrolledtext

def dialogOwner(parent:Any) -> tk.Misc|None:
  """
  :param parent: What a dialog is opened from (any widget), if anything.
  :type parent: tk.Misc | tk.Wm | None
  :returns: The window the dialog belongs over: *parent*'s own window, if
    it's on screen; else the app's window that has the focus, or failing that
    one that's full screen, or any that's on screen -- eg: when *parent* is
    an app's hidden root window; or None if none is.
  :rtype: tk.Misc | None
  """
  if parent is None:
    return None
  try:
    top = parent.winfo_toplevel()
    if top.winfo_viewable():
      return top
    try:
      focus = parent.focus_get()
    except (KeyError, tk.TclError): # (focus_get() can't name some widgets: eg: a menu's clone)
      focus = None
    if focus is not None and focus.winfo_toplevel().winfo_viewable():
      return focus.winfo_toplevel()
    root = parent._root() #type: ignore[attr-defined]
    shown = [w for w in [root, *root.winfo_children()] if isinstance(w, (tk.Tk, tk.Toplevel)) and w.winfo_viewable()]
    full = [w for w in shown if str(w.attributes("-fullscreen")) in ("1", "True", "true")]
    return full[0] if full else shown[0] if shown else None
  except tk.TclError:
    return None

def ownDialog(dialog:tk.Toplevel, parent:Any, keep:bool=True) -> None:
  """
  Make *dialog* transient for the window it belongs over (see
  *dialogOwner()*): it's then shown over that window, at its own size. Call
  it before *dialog* is first shown: on macOS, a window that isn't transient
  for another opens full screen -- in a space of its own -- when the app's
  in full screen, and making it transient once it's been shown doesn't
  undo that. (Never transient for a window that isn't on screen: on
  macOS/Aqua that can leave the dialog blank, or never shown: see
  *showExceptionDialog()*.)

  A window that stays open while the user works in others (eg: a tool's
  window, not a modal dialog) is better let go of once it's shown
  (not *keep*): on macOS a transient window is its owner's child window --
  dragged to another display, it can be left hidden, and it's never in the
  Command-` window cycle -- and if its owner's closed it's left with none.

  :param dialog: A dialog: a new window, not shown yet.
  :type dialog: tk.Toplevel
  :param parent: What it's opened from, if anything.
  :type parent: tk.Misc | tk.Wm | None
  :param keep: Whether it stays transient for that window; else only until it's first shown.
  :type keep: bool
  """
  owner = dialogOwner(parent)
  if owner is not None and owner is not dialog:
    try:
      dialog.transient(owner) #type: ignore[call-overload]
    except tk.TclError:
      return
    if not keep:
      def letGo(event:tk.Event) -> None:
        if event.widget is not dialog:
          return
        dialog.unbind("<Map>", bound)
        def free() -> None:
          try:
            if dialog.winfo_exists():
              dialog.transient("") #type: ignore[call-overload]
          except tk.TclError:
            pass
        dialog.after_idle(free)
      bound = dialog.bind("<Map>", letGo, add="+")

def showExceptionDialog(parent: tk.Toplevel|tk.Tk|None = None, title: str = "Error", text:str|None=None) -> None:
  """Display the currently-handled exception's traceback (as returned by
  traceback.format_exc()) in a scrollable, resizable dialog. Call this
  from within an `except:` block, the same place you'd call
  traceback.print_exc().

  :param parent: The parent widget/window this dialog is transient to.
  :type parent: tk.Misc | None
  :param title: The dialog's window title.
  :type title: str
  :param text: The full text of the traceback (presumably form *traceback.format_exc()*).
  :type text: str
  :rtype: None
  """
  if text is None:
    text = traceback.format_exc()

  dialog = tk.Toplevel(parent)
  dialog.title(title)
  # Only mark this dialog transient to *parent* if parent is actually an
  # on-screen window. A dialog transient to a withdrawn window (e.g. an
  # app's hidden root Tk instance, used only to host Toplevels — see
  # guiApp2.Application) may itself never get mapped by the window manager,
  # since some WMs treat "transient for a hidden window" as "also stay
  # hidden." That's exactly the case when this is called to report an
  # exception raised while constructing a new window: there's no finished
  # window yet to be transient to, only the (permanently withdrawn) root.
  ownDialog(dialog, parent) # (over a window on screen: see ownDialog())

  body = scrolledtext.ScrolledText(dialog, width=100, height=25, font=("Courier", 10), wrap="none")
  body.insert("1.0", text)
  body.configure(state="disabled")
  body.pack(fill="both", expand=True, padx=8, pady=8)

  tk.Button(dialog, text="OK", command=dialog.destroy).pack(pady=(0, 8))

  # grab_set() requires the dialog itself to already be mapped/viewable —
  # force that now rather than relying on it happening to already be true.
  dialog.update_idletasks()
  try:
    dialog.grab_set()    # modal — blocks interaction with parent
  except tk.TclError:
    # Extremely unlikely once update_idletasks() has run, but degrade to a
    # non-modal dialog rather than losing the error report entirely.
    print("showExceptionDialog(): grab_set() failed; showing non-modally")#, exc_info=True)
  dialog.wait_window()   # blocks the caller until the dialog is closed
          
################################################################################
# ---- INTROSPECTION -----------------------------------------------------------
################################################################################

def allSubclasses(cls) -> set:
  """Returns the set of all descendants of *subjectClass*

  :returns:
  :rtype: set
  """
  return set(cls.__subclasses__()).union([s for c in cls.__subclasses__() for s in allSubclasses(c)])

def allConcreteSubclasses(cls) -> set:
  """Returns the set of all non-abstract descendants of *subjectClass*

  :returns:
  :rtype: set
  """
  subclasses = allSubclasses(cls)
  return set([c for c in subclasses if not inspect.isabstract(c)])
  
################################################################################
# ---- CATEGORIES --------------------------------------------------------------
################################################################################

class Categories[T]:
  
  '''
  Named categories of objects, each defined by a test: *isCategory()* says
  whether an object is in any of the named categories.
  '''
  def __init__(self):
    self.categories:dict[str, Callable[[T],bool]] = dict()
    
  def addCategory(self, name:str, test:Callable[[T], bool]):
    '''
    :param name:
    :type name: str
    :param test:
    :type test: Callable[[T], bool]
    '''
    self.categories[name] = test
    
  def deleteCategory(self, name:str):
    '''
    :param name:
    :type name: str
    '''
    if name in self.categories:
      del self.categories[name]
      
  def isCategory(self, obj:T, categories:Union[Iterable[str], str]):
    '''
    :param obj:
    :type obj: T
    :param categories:
    :type categories: Union[Iterable[str], str]
    :returns:
    :rtype:
    '''
    if isinstance(categories, str): categories = [categories]
    for c in categories:
      if c in self.categories:
        if self.categories[c](obj):
          return True
      else:
        raise AttributeError(f'Categories.isCategory(): Unknown category "{c}"')
    return False
    
  def keys(self):
    '''
    :returns:
    :rtype:
    '''
    return self.categories.keys()

