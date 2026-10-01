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
Created on Sep. 5, 2023

.. codeauthor:: Rob Kremer <robkremer@me.com>

-------------
'''
from __future__ import annotations
from typing import Callable, Any, override

import util
import util.attribute
from util.persistence.serialize import SerializableType

from util.attribute import AttributedObject, Attribute, VAR_DEFAULTED

logger:util.Logger = util.getLogger(__name__)

PREFS_VERSION = "0.0"

class Prefs(util.attribute.AttributedObject):
  '''
  classdocs
  '''
      
  def __init__(self): #, appname:str):
    '''
    Constructor
    '''
    super().__init__()
    self.prefsFileName:str # = f'{os.path.expanduser("~")}/.{appname}.xml'
    self.callbacks:dict[str, dict[int, Callable[[str, Any], None]]] = dict()
    self.nextCallbackID = 0

  @override
  def getSupers[Prefs](self) -> list[Prefs]:
    '''
    :returns: Always an empty list -- a *Prefs* object is a flat attribute
      store with no ISA/inheritance lattice of its own.
    :rtype: list[Prefs]
    '''
    return []

  @override
  def isIndividual(self) -> bool:
    '''
    :returns: Always *True* -- a *Prefs* object isn't a TYPE in
      *AttributedObject*'s type/individual sense, it's just a single flat
      attribute store, so it's treated as an individual throughout.
    :rtype: bool
    '''
    return True

  @classmethod
  def read(cls, file:str) -> Prefs:
    from util.persistence.serialize import SerializationStrategy
    ret = SerializationStrategy.readx(file)
    assert isinstance(ret, Prefs)
    ret.prefsFileName = file
    return ret

  
  def addCallback(self, key:str, callback:Callable[[str, Any], None]) -> int:
    """
    Registers a function to be called whenever the value of the *Attribute* named
    *key* has changed.
    
    :param key: The name of attribute to install the *callback* under.
    :param callback: A function taking a string (the *key*) and a value (the updated value)
      to be called when the value of the *key* attributed has changed.
    :return: An id *int* that can be used by *removeCallback()* to refer to this callback. 
    """
    assert isinstance(key, str)
    assert callable(callback)
    if key not in self.callbacks:
      self.callbacks[key] = dict()
    entries:dict[int, Callable[[str, Any], None]] = self.callbacks[key]
    ret = self.nextCallbackID
    entries[ret] = callback
    self.nextCallbackID += 1
    return ret    
    
  def removeCallback(self, key:str, ID:int):
    """
    Removes a callback function from the registered callbacks.
    
    :param key: The name of attribute under which the *callback* was originally installed
      by *addCallback()*.
    :param ID: The value returned from the original call to *addCallback()*.
    """
    try:
      entry = self.callbacks[key]
      del entry[ID]
      if len(self.callbacks) == 0:
        del self.callbacks[key]
    except Exception as ex:
      logger.warning(f'Prefs.removeCallback("{key}", {str(ID)}): Unexpected exception occurred: {ex.__class__.__name__}: {str(ex)}')
  
  def save(self, saveas:str|None=None, overwrite=True, format:str|None=None) -> None:
    '''
    :param format: The serialization strategy to save with (see
      *SerializationStrategy*); by default, *DEFAULT_STRATEGY*.
    '''
    from util.persistence.serialize import SerializationStrategy, DEFAULT_STRATEGY
    if format is None:
      format = DEFAULT_STRATEGY
    from util.utils import fixURL, isValidURL, urlExists
    if saveas is None:
      filename = self.prefsFileName
    else:
      filename = saveas

    url = fixURL(filename, extension=SerializationStrategy.findStrategy(format).defaultExtension(), replaceExt=None, mode="w")[0]
    if not isValidURL(url):
      raise ValueError(f'PRDb.save(): Malformed URL: "{url}"')
    if urlExists(url) and not overwrite:
      raise FileExistsError(f'PRDb.save(): URL already exists. Did you mean to use the *overwrite* option?')

    SerializationStrategy.writex(filename, self, format)
    self.setDirty(False)
      
  @override
  def __setitem__(self, key:str, value:SerializableType):
    '''
    Overrides *AttributedObject* [] assignment to accept a value, by creating
    and *Attribute* with the type of *value*. (AttributedObject's assignment
    only accepts *Attribute* arguments if there is no pre-existing Attribute.) 
    
    Also calls any registered callbacks with the key and value. If a callback
    raises and exception, it is removed from the callback list.
    '''
    # create an Attribute if necessary
    if not isinstance(value, Attribute):
      value = Attribute(value, type(value), VAR_DEFAULTED)
    
    oldValue = self.get(key, "AmIsSiNgVaLuE&")
    changed = oldValue != value.value
    if not changed:
      return
    AttributedObject.__setitem__(self, key, value)
    
    # do a callback if one is registered for this key, removing the callback if it fails.
    if changed and key in self.callbacks:
      entries = self.callbacks[key]
      removals = []
      for ID,callback in entries.items():
        try:
          callback(key, value.value)
        except Exception as ex:
          logger.warning(f'Callback for Preferences key "{key}", ID {ID}, failed with exception "{str(ex)}". Removing callback.')
          removals.append(ID)
      for ID in removals:
        del entries[ID]
      if len(entries) == 0:
        del self.callbacks[key]
  

    