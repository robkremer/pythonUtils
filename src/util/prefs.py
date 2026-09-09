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
#    self.owner = owner
#    self.openFiles:List[FileData] = []
    self.prefsFileName:str # = f'{os.path.expanduser("~")}/.{appname}.xml'
    #self.xmlTag = f"{tygra.APP_SHORT_NAME.lower()}-prefs"
    self._dirty = False
    self.callbacks:dict[str, dict[int, Callable[[str, Any], None]]] = dict()
    self.nextCallbackID = 0
    # try:
    #   self.read()
    # except FileNotFoundError:
    #   logger.warning(f'Preference file "{self.prefsFileName}" not found.')
    # except:
    #   logger.exception(f'Failed to read prefs file "{self.prefsFileName}"')

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
  
  def save(self, saveas:str|None=None, overwrite=True, format:str="XML") -> None:
    from util.persistence.serialize import SerializationStrategy
    from util.utils import fixURL, isValidURL, urlExists
    if saveas is None:
      filename = self.prefsFileName
    else:
      filename = saveas

    url = fixURL(filename, extension=f".{format.lower()}", replaceExt=None, mode="w")[0]
    if not isValidURL(url):
      raise ValueError(f'PRDb.save(): Malformed URL: "{url}"')
    if urlExists(url) and not overwrite:
      raise FileExistsError(f'PRDb.save(): URL already exists. Did you mean to use the *overwrite* option?')

    SerializationStrategy.writex(filename, self, format)
    self.setDirty(False)
      
  # def save(self):
  #   """
  #   Saves preferences **and** for each open file, brings up an "save file"
  #   dialog to give the user a chance to save the file before closing. Then
  #   saves each of files and the window geometry for it's file window and
  #   each of its open view windows.
  #   """
  #   topElem = et.Element(self.xmlTag)
  #   topElem.set("version", PREFS_VERSION)
  #
  #   # # open files
  #   # openFiles = et.Element("openfiles")
  #   # #for viewWindow in TygraContainer._instances:
  #   # children = loggingPanedWindow.APP_WINDOW.winfo_children()
  #   # viewChildren = [child for child in children if isinstance(child, loggingPanedWindow.TGViewWindow)]
  #   # for viewWindow in viewChildren: # all the subwindows (TopLevel) of the AppWindow
  #   #   viewWindow.saveFile() 
  #   #   if viewWindow.filename is None:
  #   #     continue
  #   #   fileInfo = et.Element("file")
  #   #   fileInfo.set("name", os.path.abspath(viewWindow.filename))
  #   #   fileInfo.set("geometry", viewWindow.geometry())
  #   #   for dirViewID, dirViewRec in viewWindow.getViewsFromDirectory().items():
  #   #     if isinstance(dirViewRec.viewData, TGView):
  #   #       viewInfo = et.Element("openview")
  #   #       viewInfo.set("id", dirViewID)
  #   #       viewInfo.set("geometry", dirViewRec.viewData.winfo_toplevel().geometry())
  #   #       fileInfo.append(viewInfo)
  #   #   openFiles.append(fileInfo)
  #   # topElem.append(openFiles)
  #
  #   # prefs
  #   topElem.append(super().serializeXML())
  #
  #   tree = et.ElementTree(element=topElem)
  #   et.indent(tree, space='  ', level=0)
  #   tree.write(self.prefsFileName, xml_declaration=True, encoding="utf-8")
  #   logger.debug(f'Prefs.save(): saved "{self.prefsFileName}"')
  #   self._dirty = False
    

  # def read(self):
  #   if not os.path.isfile(self.prefsFileName):
  #     raise FileNotFoundError(f'Prefs.read(): {self.prefsFileName} not found.')
  #   SerializationStrategy.readx(self.prefsFileName)
  #   # tree = et.parse(self.prefsFileName)
  #   # root = tree.getroot()
  #   # if root.tag != self.xmlTag:
  #   #   raise TypeError(f'Prefs.read(): {self.prefsFileName} is not a {self.xmlTag} file.')
  #   # elemTag = getFullClassName(self.__class__)
  #   # elem = root.find(elemTag)
  #   # self.unserializeXML(elem)
    
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
  
#   def edit(self, parentWindow, title=None):
#     """
#     Put up a GUI dialog to edit the *Attributes*
#
#     :param parentWindow: A parent for dialog.
#     :param title: A title to put on the dialog window.
#     """
#     editor = PrefsEditor(parentWindow, self, self.prefs, title=title)
#     editor.show()
# #    editor.destroy()
    

    