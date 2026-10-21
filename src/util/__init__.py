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
The *util* package: general-purpose building blocks for Python applications --
persistence, attributes with inheritance, commands with undo and a command-line
parser, the observer pattern, preferences, and some Tk widgets (a terminal, an
attribute editor, dialogs, tooltips). It came out of *Semantic Nets*, but
doesn't depend on it.

This module sets up logging. Modules get their loggers with
``util.getLogger(__name__)``: an application can supply its own *getLogger()*
in its top-level package, which is then used instead (see *getLogger()*), and
set up the log file with *setupLogger()*.
'''
import types
import sys
import logging
from pathlib import Path
import os
from typing import Callable

cachedGetLogger:Callable|None = None

_loggingSetUp:bool = False
"Whether *setupLogger()* has been called (by the application, or by *getLogger()* for want of it)."

##### LOGGING STUFF #######################################

class Logger(logging.Logger):
  '''
  A *logging.Logger* with a *print()* method too (see *util.getLogger()*).
  '''
  def print(self, *args, **kwargs):
    '''
    Intended to mimic the print system command but allowing for redirection 
    and multiple destinations if necessary.

    :param args:
    :type args:
    :param kwargs:
    :type kwargs:
    '''
    print(*args, **kwargs)
    
def getLogger(name:str):
  '''
  Create or find a Logger for *name*.  This should be called as util.getLogger(__name__).

  :param name:
  :type name: str
  :returns:
  :rtype:
  '''
  global cachedGetLogger
  if cachedGetLogger is not None: # we've already cached the thing
    return cachedGetLogger(name)

  # Try to find a getLogger() method in the __init__.py module of the package of the
  # main program -- but only if that package has ALREADY been imported somewhere else
  # in the normal course of the program. We deliberately do NOT try to import it
  # ourselves here (see _getTopLevelPackageName()'s docstring): this function gets
  # called from module-level code all over pythonUtils (e.g. util.persistence.serialize
  # calls util.getLogger(__name__) at import time, before it's finished defining its own
  # classes), so forcing an import of the caller's enclosing app package as a side effect
  # of "just checking for a custom getLogger" can re-enter that very module's own
  # still-in-progress import and blow up with a "partially initialized module"
  # ImportError.
  topLevelName:str|None = _getTopLevelPackageName()
  topModule:types.ModuleType|None = sys.modules.get(topLevelName) if topLevelName else None
  if topModule is not None and topModule is not sys.modules[__name__]:
    getLogger = getattr(topModule, "getLogger", None)
    if callable(getLogger):
      ret = getLogger(name)
      if isinstance(ret, logging.Logger):
        cachedGetLogger = getLogger
        return ret

  # We couldn't find a getLogger, so make our own for THIS call -- setting up
  # logging our own way first, if nothing has yet. (Only if nothing has: an
  # application that's called setupLogger() itself, with its own logger class
  # -- eg: sn's SNLogger -- mustn't have that undone by the next util module
  # to be imported.)
  if not _loggingSetUp:
    setupLogger()
  if topLevelName is not None and topModule is None:
    # There IS a plausible top-level package (e.g. "sn") -- it just hasn't
    # finished importing yet (we're likely running very early during its own
    # bootstrap). Don't lock this fallback in via cachedGetLogger: leave it
    # uncached so a later call, once that package has actually loaded, can
    # still find and delegate to its custom getLogger().
    return _getLogger(name)
  cachedGetLogger = _getLogger
  return _getLogger(name)

def setupLogger(loggerClass:type|None=None, logFileName:str|None=None):
  '''
  Set up the logger to log to a log file and to stderr.
  
  :param loggerClass: A logging.Logger subtype to set the loggerClass to.
  :type loggerClass: type(logging.Logger)|None
  :param logFileName: The name of the file to log to.  By default it will
    be the stem (filename only) of current executable, and it will be in
    the current directory.  If it doesn't have a file extension, ".log" will be
    appended. A relative name is put in the user's log folder instead (eg:
    *~/Library/Logs/<program>/*: see *util.platformSupport.logFolder()*) when
    the program is packaged (eg: a .app) or the current directory can't be
    written.
  :type logFileName: str|None
  '''
  if loggerClass is None:
    loggerClass = Logger
  assert issubclass(loggerClass, logging.Logger)    
  logging.setLoggerClass(loggerClass)
  
  if logFileName is None:
    name = Path(sys.argv[0]).stem
    logFileName = name+'.log'
  else:
    if '.' not in logFileName:
      logFileName += ".log"
  if not os.path.isabs(logFileName) and (getattr(sys, "frozen", False) or not os.access(os.getcwd(), os.W_OK)):
    # A packaged app (eg: a .app started from the Finder, whose current
    # directory is "/") -- or anywhere the current directory can't be written:
    # log in the user's log folder instead, eg: ~/Library/Logs/Semantic Nets/
    # (see util.platformSupport.logFolder()).
    from util.platformSupport import logFolder
    folder = logFolder(Path(sys.argv[0]).stem)
    os.makedirs(folder, exist_ok=True)
    logFileName = os.path.join(folder, logFileName)
  global _loggingSetUp
  _loggingSetUp = True
  logFileName = _freshLogFile(logFileName)
  fileHandler = logging.FileHandler(logFileName)
  fileHandler.setFormatter(logging.Formatter('**%(levelname)s: %(name)s: %(message)s\n  at %(filename)s, func=%(funcName)s, line=%(lineno)d', style='%'))
  streamHandler = DynamicStderrHandler()
  logging.basicConfig(force=True, level=logging.INFO, handlers=[fileHandler, streamHandler])
 

def _freshLogFile(logFileName:str) -> str:
  '''
  :returns: *logFileName*, emptied (the last run's log is removed); or, if it
    can't be removed because another copy of the program has it open (as on
    Windows, where an open file can't be removed), the first of "<name>-2.log",
    "<name>-3.log", ... that can.
  '''
  stem, ext = os.path.splitext(logFileName)
  for n in range(1, 10):
    name = logFileName if n == 1 else f"{stem}-{n}{ext}"
    try:
      if os.path.isfile(name):
        os.remove(name)
      return name
    except PermissionError:
      continue
  return f"{stem}-{os.getpid()}{ext}"


class DynamicStderrHandler(logging.StreamHandler):
  """A StreamHandler that always writes to the CURRENT sys.stderr at emit time,
  rather than whatever sys.stderr was when this handler was constructed.

  Useful when sys.stderr is reassigned later (e.g. redirected into a GUI
  terminal widget or a LoggerWriter) and you want log output to follow it.
  """

  def __init__(self, *args: object, **kwargs: object) -> None:
    # Pass a placeholder; StreamHandler.__init__ requires *some* stream, but
    # we override .stream to always resolve dynamically, so this initial
    # value is never actually used for writing.
    '''
    :param args:
    :type args: object
    :param kwargs:
    :type kwargs: object
    '''
    super().__init__(sys.stderr, *args, **kwargs)

  @property
  def stream(self) -> object:
    """Always return the current sys.stderr, not a frozen reference.

    :returns: The live sys.stderr object.
    :rtype: object
    """
    return sys.stderr

  @stream.setter
  def stream(self, value: object) -> None:
    """Ignore attempts to set .stream directly — StreamHandler.__init__ tries
    to assign self.stream = stream, which would otherwise shadow the property.

    :param value: Ignored.
    :type value: object
    :rtype: None
    """
    pass

def _getTopLevelPackageName() -> str|None:
  """Determine the NAME of __main__'s top-level enclosing package, purely by
  inspecting sys.modules and walking the file system -- this never imports
  anything as a side effect.

  This used to also resolve (and, if necessary, *import*) the module object
  itself, but that's exactly what caused a nasty bootstrapping hazard: this
  gets called (via getLogger()) from module-level code all over pythonUtils,
  e.g. util.persistence.serialize calls ``util.getLogger(__name__)`` while
  IT is still being imported, and if the app's own top-level package (e.g.
  "sn") is the thing needing pythonUtils to finish loading in the first
  place, forcing an import of "sn" right here re-enters that same
  still-in-progress import chain and blows up with a "partially initialized
  module" ImportError. Callers now do their own ``sys.modules.get(name)``
  lookup (see getLogger()) so a not-yet-imported top-level package is simply
  reported as "not available yet" rather than force-imported.

  :returns: The top-level package's name, or None if __main__ was run as a
    standalone script or from an interactive session with no enclosing
    package.
  :rtype: str|None
  """
  def crawlUpDirs(currDir) -> str:
    topLevelDir = currDir
    while (topLevelDir.parent / "__init__.py").exists():
      topLevelDir = topLevelDir.parent
    return topLevelDir.name

  mainModule = sys.modules.get("__main__")
  if mainModule is None:
    return None

  # This strategy assumes we've been launched with "python -m mypkg.sub.script"
  # but it will fail (__package__ is "") if this isn't the case.
  packageName = getattr(mainModule, "__package__", None)
  if packageName:
    return packageName.split(".")[0]

  # Try by crawling up the file system as far as we can find __init__.py files.
  mainFile = getattr(mainModule, "__file__", None)
  if mainFile is not None:
    currentDir = Path(mainFile).resolve().parent
    if not (currentDir / "__init__.py").exists():
      #print(f'__main__\'s own directory isn\'t a package at all: {currentDir}')
      return None  # __main__'s own directory isn't a package at all
    return crawlUpDirs(currentDir)

  # Interactive REPL, frozen exe without a file, etc.
  #print('interactive REPL, frozen exe without a file, etc.')
  spec = getattr(mainModule, "__spec__", None)
  if spec is not None and spec.origin and spec.origin != "built-in":
    mainFile = spec.origin

  if mainFile is None:
    #print('truly no file to work from — e.g. interactive REPL.')
    return None  # truly no file to work from — e.g. interactive REPL

  currentDir = Path(mainFile).resolve().parent
  if not (currentDir / "__init__.py").exists():
    return None
  return crawlUpDirs(currentDir)

def _getLogger(name:str) -> logging.Logger:
  '''
  Return a properly typed SNLogger for the molule who's __name__ is given in *name*.
  This may be either created of just returned, depending on if it exists already.
  
  :param name: Always call this with the __name__ variable for the file.
  :type name: str
  :returns: The properly typed SNLogger for created.
  :rtype: SNLogger
  '''
  if name == "__main__":
    mainModuleFile = sys.modules["__main__"].__file__
    assert mainModuleFile is not None
    path = os.path.splitext(os.path.basename(mainModuleFile))[0]
    path = 'sn.'+path
  else:
    path = name
  logger = logging.getLogger(path)
  assert isinstance(logger, logging.Logger), f'Expected type Logger, got {type(logger)}'
  return logger

