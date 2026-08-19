'''
Miscellaneous utility functions.
 
Created on Oct 14, 2024

.. codeauthor:: Rob Kremer <robkremer@me.com>

-------------
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
import os
import sys
from typing import Optional, Any, Iterable, Callable,\
  Union, Tuple, overload, Self, Generator, override, Type, get_origin
from enum import EnumMeta, Flag
from urllib.parse import urlparse, unquote, urlunparse, ParseResult
import requests
from pathlib import Path
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
import util
#from docutils.nodes import description
logger:util.Logger = util.getLogger(__name__)

def getSubMenu(menu:tk.Menu, name:str, makeIfNone:Optional[int]=tk.END) -> Optional[tk.Menu]:
  """
  Find a submenu in *menu* with label *name* .
  
  :param menu: The menu to search
  :param name: The label of the item we are searching for
  :param makeIfNone: [default: tk.END (insert at end)] if an *int* and *menu* does not contain any
      menu items named *name* then insert a new menu named *name* at position 
      *makeIfNone* .
  :return: Return a *tk.Menu* if it is found or created; if it is not found and
      *makeIfNone* is *None*, return *None* .
  """
  submenu = None      
  try:
    index = menu.index(name)
    assert menu.type(index) == "cascade"
    submenu = menu.entrycget(index,'menu')
    submenu = menu.winfo_toplevel().nametowidget(submenu)
  except Exception as ex:
    if makeIfNone is not None:
      assert isinstance(makeIfNone, int)
      submenu = tk.Menu(menu) #TODO: should probably make an effort to put this in the right place
      menu.insert_cascade(makeIfNone, label=name, menu=submenu)
  return submenu

def isGuiAvailable() -> bool:
  """Determine whether a graphical display environment appears to be available.

  :returns: True if a GUI environment is likely usable, False otherwise.
  :rtype: bool
  """
  if sys.platform.startswith("win") or sys.platform == "darwin":
    return True
  # On X11/Wayland Linux systems, check the relevant env vars.
  return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def askViaTk(prompt: str, title: str = "Input required") -> Optional[str]:
  """Prompt the user for input using a Tkinter dialog.

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
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    result = simpledialog.askstring(title, prompt, parent=root)
    root.destroy()
    return result
  except tk.TclError:
    # DISPLAY was set but no display server actually responded.
    return None


def askViaTerminal(prompt: str) -> Optional[str]:
  """Prompt the user for input via stdin/stdout.

  :param prompt: The message to display to the user.
  :type prompt: str
  :returns: The user's input, or None if stdin is not interactive.
  :rtype: Optional[str]
  """
  if not sys.stdin.isatty():
    return None
  try:
    return input(f"{prompt}: ")
  except (EOFError, KeyboardInterrupt):
    return None


def askUser(prompt: str, title: str = "Input required") -> Optional[str]:
  """Ask the user a question, using a GUI dialog if available and falling back to the terminal.

  :param prompt: The message to display to the user.
  :type prompt: str
  :param title: The dialog window title, used only in GUI mode.
  :type title: str
  :returns: The user's input, or None if no input method succeeded.
  :rtype: Optional[str]
  """
  if isGuiAvailable():
    result = askViaTk(prompt, title)
    if result is not None:
      return result
  return askViaTerminal(prompt)

class VerticalScrolledFrame(ttk.Frame):
    """
    A pure Tkinter scrollable frame that actually works!
    * Use the 'interior' attribute to place widgets inside the scrollable frame.
    * Construct and pack/place/grid normally.
    * This frame only allows vertical scrolling.
    """
    def __init__(self, parent, *args, **kw):
        ttk.Frame.__init__(self, parent, *args, **kw)

        # Create a canvas object and a vertical scrollbar for scrolling it.
        vscrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL)
        vscrollbar.pack(fill=tk.Y, side=tk.RIGHT, expand=tk.FALSE)
        canvas = tk.Canvas(self, bd=0, highlightthickness=0,
                           yscrollcommand=vscrollbar.set)
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
            canvas.config(scrollregion="0 0 %s %s" % size)
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # Update the canvas's width to fit the inner frame.
                canvas.config(width=interior.winfo_reqwidth())
        interior.bind('<Configure>', _configure_interior)

        def _configure_canvas(event):
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # Update the inner frame's width to fill the canvas.
                canvas.itemconfigure(interior_id, width=canvas.winfo_width())
        canvas.bind('<Configure>', _configure_canvas)

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
  :type typeHandlers
  :returns: 
  
  Limitations to be aware of:
  
    - Complex annotations (list[int], Optional[str], unions) need extra handling
  
    - *args / **kwargs don't map cleanly to argparse
  
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
    paramsDoc[p.arg_name] = f'({p.type_name}{"" if p.default is None else (", default="+p.default)}) {p.description}'
    
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


def resolveAliases(x:str, table:dict[str,str], raiseOnError:bool=True) -> str:
  """
  :param x: The string to analyze.
  :param table: The *dict* from which to lookup keys in.
  :param raiseOnError: If True a syntax error or a failed lookup in *table* will raise an exception, otherwise the $ expression will be left intact.
  
  From a string, substitute any contained <key> expressions "${<key>}" for *dict["key"]*. 
  Eg: *x* == *"a${b}c"* and *table* == *{"b":"BB"}* returns "aBBc".   
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
  '''
  if " " in s:
    return f'"{s}"'
  return s
   
################################################################################
############################## Control keys ####################################
################################################################################

# State bits in events
def s_CMD(s:int) -> bool:
  ":return: *True* iff *s* has the Command key bit set."
  return (s&0x18) != 0
def s_SHIFT(s:int) -> bool: 
  ":return: *True* iff *s* has the Shift key bit set."
  return (s&0x1)  != 0
def s_CTL(s:int) -> bool: 
  ":return: *True* iff *s* has the Control key bit set."
  return (s&0x4)  != 0
def s_ALT(s:int) -> bool: 
  ":return: *True* iff *s* has the Alt or Option key bits set."
  return (s&0x88) != 0
s_OPT = s_ALT

# Graphical representations for control keys
CHAR_SHIFT = u'\u21E7'
CHAR_CTL   = u'\u2388'
CHAR_ALT   = u'\u2387'
CHAR_CMD   = u'\u2318'

def strToBool(b:str):
  b = b.lower()
  ln = len(b)
  if b in ("on", "true"[:min(4,ln)]):
    return True
  if b in ("off"[:min(3,max(2,ln))], "false"[:min(5,ln)]):
    return False
  raise ValueError(f'Cannot interpret "{b}" as a boolean value.')


################################################################################
###################################### URLs ####################################
################################################################################

def isValidURL(url:str) -> bool:
  '''
  :param url: A string to determine if it's a proper URL
  :return: *True* iff the str appears to be well-formed URL
  '''
  # from sn import BASE_URL
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

def urlExists(url:str) -> bool:
  '''
  :param url: A string to determine if it's an existant URL
  :return: *True* iff the str is a URL that references an existant place
  '''
  result = urlparse(unquote(url))
  if result.scheme == "file":
    return os.path.isfile(result.path)

  else:
    try:
      response = requests.get(url)
      if response.status_code == 200:
        return True
    except:
      return False
  return False

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
    decodedPath = Path(unquote(parsed.path))
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
    the default extension; if False, the default will extension will be 
    appended to the path if it's not already there; if None (the default), 
    the extension will only be added it the file does not already have an 
    extension.
  :type replaceExt: Optional[bool] (default: None)
  :param mode: 'r' will check if the file or URL exists; 'w' will try to determine
    if the fine or URL is writable; anything else will make no checks.
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
    
  path:Path = Path(parsedUrl.path)
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
  elif mode.lower() == 'w' and not canWriteUrl(url):
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
  ret:Optional[str] = urlparse(unquote(url)).path
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
    localPath: str = parsedUrl.netloc + parsedUrl.path
    absolutePath: str = os.path.abspath(localPath)
    with open(absolutePath, "rb") as fileHandle:
      return fileHandle.read()

  with urllib.request.urlopen(url) as response:
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

def changeUrlExtension(url, new_extension):
    """
    Changes the file extension of a URL.

    Args:
        url (str): The original URL string.
        new_extension (str): The new extension (e.g., ".jpg", ".html").

    Returns:
        str: The URL with the modified extension.
    """
    parsed_url = urlparse(url)
    path_without_ext, _ = os.path.splitext(parsed_url.path)
    new_path = path_without_ext + new_extension
    
    # Reconstruct the URL with the new path
    new_url = urlunparse(parsed_url._replace(path=new_path))
    return new_url
  
################################################################################
########################### MUCKING WITH CLASSES ###############################
################################################################################

def getFullClassName(cls:type) -> str:
  "Unlike *obj.__class__.__name__* this returns the (period-deliminated) full class path of *subjectClass*"
  #return str(subjectClass)[8:-2]
  splt = str(cls).split()
  if len(splt) == 1: # it was a simple type like "int"
    return splt[0]
  return splt[1][1:-2] # it was a class type in the form of "<class 'module.name'>"
  
def getClass(className:str) -> Optional[type]:
  '''
  Searches the modules in the system for the first class that matches the 
  simple class name.  Use *getFullyqualifiedClass()* if you have a class path.
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
    
def getFullyQualifiedClass(classPath:str) -> Optional[type]:
  """
  :param classPath: A string representing the name of a class
  :return: Either a *Class* object or None
  
  Follows the class path down the modules in the system to return the matching class object.
  User *getClass()* if you only have a simple class name and want to search for it. 
  """
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
    if inspect.isabstract(sub):
      result.extend(findConcreteSubclasses(sub))
    else:
      result.append(sub)
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


################################################################################
############################ LIST MANIPULATION #################################
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
    raise KeyError(f'delOne() failed. Can\'t find {item} in {lst}.')
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
###################################### FLAGS ###################################
################################################################################

class ExtendedEnumMeta(EnumMeta):
  @override
  def __getitem__(self, name):
    items = name.split('|')
    ret:int = self(0)
    for i in items:
      i = i.strip()
      ret |= super().__getitem__(i)
    return ret

class ExtendedFlag(Flag, metaclass=ExtendedEnumMeta):

  @staticmethod
  def fromStr(spec:str):
    'This cannot be right...'
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
    result = super().__str__()
    resultList = result.split(".")
    result = ".".join([getFullClassName(self.__class__), resultList[1]])
    return result
    
################################################################################
########## SOUNDS ##############################################################
################################################################################

def play(soundFile:Optional[str]=None) -> None:
  """
  Plays a sound file. So far, this is only implemented for mac.
  
  :param soundFile: May have the following values:
  
    - None: plays "/System/Library/Sounds/Sosumi.aiff" (an error beep).
    - Just a file name: (not containing any slashes ("/")) looks in /System/Library/Sounds/
        for the file.
    - A path: (containing slashes ("/")) just tries to play that file.
    
  """
  if soundFile is None or len(soundFile)==0:
    soundFile = '/System/Library/Sounds/Sosumi.aiff'
  elif soundFile.find('/') < 0:
    soundFile = '/System/Library/Sounds/'+soundFile
  subprocess.Popen(["afplay", soundFile])


##########################################################################################
########## XML ###########################################################################
##########################################################################################

def xmlEscape( strXML: str ) -> str:
  """
  Replaces the "&", "<", ">", and single and double quote characters with xml escape codes.
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
      logger.error("not sure what to do with '"+line+"'")
  return output
      
##########################################################################################
########## GRAPHIC UtiLItiES #############################################################
##########################################################################################

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
    '''
    x = self.asTuple()
    return x[index]

  def __len__(self) -> int:
    'Implementation for *len()*. Always returns 2.' 
    return 2

  def __iter__(self) -> Generator:
    'Iterator implementation.'
    yield self.x
    yield self.y
    
  def asTuple(self) -> tuple:
    'Returns *self* as a *tuple*.' 
    return (self.x, self.y)
  
  def asList(self)  -> list:
    'Returns *self* as a *list*.' 
    return [self.x, self.y]
  
  def __add__(self, other:Union[Iterable,Self]):
    "None mutating overload of the + operator to add the corresponding indices."
    if not isinstance(other, Point):
      other = Point(other) # will throw if the type of other is incompatible
    return Point(self.x + other.x, self.y + other.y)
  
  def moveBy(self, x:Optional[PointIndici]=None, y:Optional[PointIndici]=None):
    "Mutating version of adding the corresponding values of x and y"
    if x is not None:
      self.x += x 
    if y is not None:
      self.y += y
      
  def __eq__(self, other:Any) -> bool:
    '''
    Overload of the == operator where the second operand may be a *Point* or a
    two-element iterator of *PointIndici*.
    '''
    if not isinstance(other, Point):
      try:
        other = Point(other)
      except:
        return False
    return (self.x == other.x) and (self.y == other.y)
       
  def __str__(self) -> str:
    'Return the in "(<x>,<y>)" form.'
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
  import matplotlib.path as mplPath
  from numpy import array
  pt = iterableToList(pt)
  poly = iterableToList(poly)
  arr = []
  for i in range(0, len(poly), 2):
    arr.append([poly[i], poly[i+1]])
  bbPath = mplPath.Path(array(arr))
  return bbPath.contains_point(tuple(pt))

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
  """
  rect = iterableToList(rect)
  return [rect[0] if rect[0]<rect[2] else rect[2],
      rect[1] if rect[1]<rect[3] else rect[3],
      rect[2] if rect[0]<rect[2] else rect[0],
      rect[3] if rect[1]<rect[3] else rect[1]]
      
def iterableToList(it: Iterable) -> list:
  return list(it)
  # if isinstance(it, (list,tuple)):
  #   return it
  # ret = []
  # for i in it: 
  #   ret.append(i)
  # return ret
    
    
##########################################################################################
########## USER INTERFACE ################################################################
##########################################################################################

def bindRightMouse(window, func):
  if window.winfo_toplevel().tk.call("tk", "windowingsystem") == 'aqua':
    window.bind("<2>", func)
    window.bind("<Control-1>", func)
  else:
    window.bind("<3>", func)

def tag_bindRightMouse(window, id_, func):
  if window.tk.call("tk", "windowingsystem") == 'aqua':
    window.tag_bind(id_, "<2>", func)
    window.tag_bind(id_, "<Control-1>", func)
  else:
    window.tag_bind(id_, "<3>", func)

def tag_unbindRightMouse(window, id_):
  if window.tk.call("tk", "windowingsystem") == 'aqua':
    window.tag_unbind(id_, "<2>")
    window.tag_unbind(id_, "<Control-1>")
  else:
    window.tag_unbind(id_, "<3>")

def eventEqual(e1, e2):
  return isinstance(e1, tk.Event) and isinstance(e2, tk.Event) and \
      e1.x_root == e2.x_root and \
      e1.y_root == e2.y_root and \
      e1.type   == e2.type
      
##########################################################################################
########## INTROSPECTION #################################################################
##########################################################################################

def allSubclasses(cls) -> set:
  """Returns the set of all descendants of *subjectClass*"""
  return set(cls.__subclasses__()).union([s for c in cls.__subclasses__() for s in allSubclasses(c)])

def allConcreteSubclasses(cls) -> set:
  """Returns the set of all non-abstract descendants of *subjectClass*"""
  subclasses = allSubclasses(cls)
  return set([c for c in subclasses if not inspect.isabstract(c)])
  
##########################################################################################
########## CATEGORIES ####################################################################
##########################################################################################

class Categories[T]:
  
  def __init__(self):
    self.categories:dict[str, Callable[[T],bool]] = dict()
    
  def addCategory(self, name:str, test:Callable[[T], bool]):
    self.categories[name] = test
    
  def deleteCategory(self, name:str):
    if name in self.categories:
      del self.categories[name]
      
  def isCategory(self, obj:T, categories:Union[Iterable[str], str]):
    if isinstance(categories, str): categories = [categories]
    for c in categories:
      if c in self.categories:
        if self.categories[c](obj):
          return True
      else:
        raise AttributeError(f'Categories.isCategory(): Unknown category "{c}"')
    return False
    
  def keys(self):
    return self.categories.keys()

