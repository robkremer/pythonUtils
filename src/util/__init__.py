import types
import sys
import logging
from pathlib import Path
import os
from typing import Callable
import importlib
from types import ModuleType

cachedGetLogger:Callable|None = None

##### LOGGING STUFF #######################################

class Logger(logging.Logger):
  def print(self, *args, **kwargs):
    '''
    Intended to mimic the print system command but allowing for redirection 
    and multiple destinations if necessary.
    '''
    print(*args, **kwargs)
    
def getLogger(name:str):
  '''
  Create or find a Logger for *name*.  This should be called as util.getLogger(__name__).
  '''
  global cachedGetLogger
  if cachedGetLogger is not None: # we've already cached the thing
    return cachedGetLogger(name)
  
  # try to find a getLogger() method in the __init__.py module of the package of the main program. 
  topModule:types.ModuleType|None = _getTopLevelPackageModule()
  print(f'topModule: {topModule}')
  if topModule is not None and topModule is not sys.modules[__name__]:
    getLogger = getattr(topModule, "getLogger", None)
    if callable(getLogger):
      ret = getLogger(name)
      if isinstance(ret, logging.Logger):
        cachedGetLogger = getLogger
        return ret
  
  # We couldn't find a getLogger, so make our own. 
  # In the case of not being able to access the main module (python REPL),
  # the logger class might have been changed by the main module: if so,
  # just go with that.
  if type(_getLogger(__name__)) is logging.Logger:
    setupLogger()
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
    appended.
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
    if '.' in logFileName:
      logFileName += ".log"
  if os.path.isfile(logFileName): os.remove(logFileName)
  fileHandler = logging.FileHandler(logFileName)
  fileHandler.setFormatter(logging.Formatter('**%(levelname)s: %(name)s: %(message)s\n  at %(filename)s, func=%(funcName)s, line=%(lineno)d', style='%'))
  #streamHandler = logging.StreamHandler(sys.stderr)
  streamHandler = DynamicStderrHandler()
  logging.basicConfig(force=True, level=logging.INFO, handlers=[fileHandler, streamHandler])
 

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

def _getTopLevelPackageModule() -> types.ModuleType|None:
  """Get the module object of the top-level package's __init__.py, if __main__
  was run as part of a package (e.g. via ``python -m pkg.sub.script``).

  :returns: The top-level package's module object, or None if __main__ was run
    as a standalone script or from an interactive session with no enclosing package.
  :rtype: types.ModuleType|None
  """
  def crawlUpDirs(currDir) -> ModuleType:
    topLevelDir = currentDir
    while (topLevelDir.parent / "__init__.py").exists():
      topLevelDir = topLevelDir.parent
  
    topLevelName = topLevelDir.name
    #print(f'topLevelName: {topLevelName}')
    if topLevelName in sys.modules:
      return sys.modules[topLevelName]
  
    # Make the parent of the top-level package dir importable, then import it.
    parentDir = str(topLevelDir.parent)
    if parentDir not in sys.path:
      sys.path.insert(0, parentDir)
    return importlib.import_module(topLevelName)
    
  mainModule = sys.modules.get("__main__")
  if mainModule is None:
    return None

  # This strategy assumes we've been launched with "python -m mypkg.sub.script"
  # but it will fail (__package__ is "") if this isn't the case.
  packageName = getattr(mainModule, "__package__", None)
  if packageName:
    topLevelName = packageName.split(".")[0]
    return sys.modules.get(topLevelName)
  
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

