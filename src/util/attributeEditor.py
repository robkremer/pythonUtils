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
A Tk dialog for viewing and editing the attributes of an *AttributedObject*
(see *util.attribute*): one row per attribute -- its value, type and
inheritance restrictions -- with the values it inherits shown above it.
*editAttrsBox()* returns the edits; *applyEditAttrsBox()* applies them.

.. inheritance-diagram:: 
        AttrEditor
        ChangeDescr
        ColorEditor
        HierarchicalAttrEditor
      :parts: 3
      :private-bases:
      :top-classes: util.commandParser.ParsableCommandDef, util.commandParser.ParsableQuery

Created on Mar 17, 2025

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''
import util
from util.persistence.serialize import SerializationStrategy, strdict
from util.persistence.serialize import DEFAULT_STRATEGY
from util import attribute
from util.platformSupport import WINDOW_BACKGROUND

import logging
import tkinter as tk
import tkinter.font as tkfont
import re
from tkinter import colorchooser, ttk, messagebox, simpledialog
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Union, Optional, override, Type
from types import NoneType
from copy import copy

from util.attribute import AttributedObject, Attribute, \
  KNOWN_TYPES, isValidType, TYPE_EQUIVALENTS, VAR_DEFAULTED, Restriction,\
  NoValue, NOVALUE
from util.persistence.pRef import Serializable, PRObject
from util.utils import getFullClassName, xmlToStringIndented
from util.utils import VerticalScrolledFrame, ownDialog
from util.tooltip import CreateToolTip
from tkinter.ttk import Widget


logger:util.Logger = util.getLogger(__name__)

DOWN_ARROW = "\u2B07"
INHERIT_KEY_EXT = "-\u2193"

KIND_WIDTH = 10

GROUP_SEPARATOR = "/"
"Attribute names are grouped, like folders, by the parts of their names between these (eg: \"gui/label\")."
TRIANGLE_OPEN = "\u25BC"   # (a down-pointing triangle)
TRIANGLE_CLOSED = "\u25B6" # (a right-pointing triangle)
GROUP_BACKGROUND = "grey85"
"The background of a group's header line (see *AttrEditor.makeGroupHeader()*)."
TREE_INDENT = 18
"How far (in pixels) each level of the grouped attribute names is indented."

def isHiddenKey(key:str) -> bool:
  '''
  :param key: An attribute's name.
  :type key: str
  :returns: Whether the editor hides it: if any part of its name (see
    *GROUP_SEPARATOR*) starts with "." -- eg: ".openWindows" (hidden itself),
    "gui/.cache" (likewise, in the *gui* group), or ".internal/x" (in a hidden
    group). Such attributes are for the program, not the user, to edit.
  :rtype: bool
  '''
  return any(part.startswith(".") for part in key.split(GROUP_SEPARATOR))

def treeOrder(keys:list[str]) -> list[tuple[str, str, int]]:
  '''
  The order to show attributes in, grouped by the parts of their names (see
  *GROUP_SEPARATOR*), like a tree of folders: at each level, the names with no
  more separators first, then each group -- its header, and then its own
  contents, likewise -- all sorted (ignoring case). Eg: "a", "b", "a/a", "a/b",
  "a/a/a", "a/a/b", "b/a" are shown as::

    a
    b
    a/      (a group)
      a/a
      a/b
      a/a/    (a group)
        a/a/a
        a/a/b
    b/      (a group)
      b/a

  :param keys: The attribute names.
  :type keys: list[str]
  :returns: (kind, name, depth) for each line: kind is "key" (name is an
    attribute's name) or "group" (name is the group's path, eg: "a/a").
  :rtype: list[tuple[str, str, int]]
  '''
  out:list[tuple[str, str, int]] = []
  def build(prefix:str, names:list[str], depth:int) -> None:
    leaves = [k for k in names if GROUP_SEPARATOR not in k[len(prefix):]]
    groups:dict[str, list[str]] = {}
    for k in names:
      rest = k[len(prefix):]
      if GROUP_SEPARATOR in rest:
        groups.setdefault(rest.split(GROUP_SEPARATOR, 1)[0], []).append(k)
    for k in sorted(leaves, key=str.lower):
      out.append(("key", k, depth))
    for g in sorted(groups, key=str.lower):
      out.append(("group", prefix + g, depth))
      build(prefix + g + GROUP_SEPARATOR, groups[g], depth + 1)
  build("", keys, 0)
  return out

DOC_QUALIFIER = \
'''Qualifiers:
f:   final:
          The attribute many not be modified in subtypes.
if:  instance final:
          Instances of this type may not modify the attribute.
vni: value not inheritable:
          Instances of this type must override the attribute value.'''

def editAttrsBox(parent:tk.Misc, attrs:AttributedObject, title="Attributes Editor", 
                 editKey:Optional[str]=None, disabled:bool=False,
                 displayValues:Optional[dict[str,Any]]=None,
                 hideColumns:Iterable[str]=(),
                 listItemMakers:Optional[dict[str, ItemMaker]]=None) -> Optional[dict[str,Attribute]]:
  '''
  :param parent: The parent widget
  :param attrs: The *AttributedObject* object to be updated.
  :param title: The title of the dialog window. 
  :param displayValues: [Optional] Values to show (and edit) for some keys in
    place of their stored values -- eg: a fuller form of the value, which the
    caller interprets. A key counts as changed only if its value differs from
    what was shown.
  :return: An dict *str->Attribute* with any updates 
   
  displays an *AttrsEditor* or a *HierarchicalAttrsEditor* (depanding on whether 
  *attrs* is an *AttributedObject* or a *AttributedObject* ) and
  updates the result to *attrs* .

  :param editKey:
  :type editKey: Optional[str]
  :param disabled:
  :type disabled: bool
  :param hideColumns: The columns not to show (see *AttrEditor.HIDEABLE_COLUMNS*).
  :type hideColumns: Iterable[str]
  :param listItemMakers: For "list[str]" attributes: what their "Add..." does, by key (see *ListEditor*).
  :type listItemMakers: Optional[dict[str, ItemMaker]]
  '''
  if isinstance(attrs, AttributedObject):
    editor = HierarchicalAttrEditor(parent, attrs, title=title, disabled=disabled, displayValues=displayValues, hideColumns=hideColumns, listItemMakers=listItemMakers)
  else:  
    editor = AttrEditor(parent, attrs, title=title, disabled=disabled, displayValues=displayValues, hideColumns=hideColumns, listItemMakers=listItemMakers)
  editor.show(editKey=editKey)
  logger.debug(f'editAttrsBox(): updated: {editor.updatedKeys}')
  editor.destroy()
  return editor.updatedKeys
  
def applyEditAttrsBox(parent:tk.Misc, attrs:AttributedObject, title="Attributes Editor", 
                      editKey:Optional[str]=None, hideColumns:Iterable[str]=(),
                      listItemMakers:Optional[dict[str, ItemMaker]]=None) -> None:
  '''
  Same as *editAttrsBox*, but applies the changes.

  :param parent:
  :type parent: tk.Misc
  :param attrs:
  :type attrs: AttributedObject
  :param title:
  :type title: str
  :param editKey:
  :type editKey: Optional[str]
  :param hideColumns: The columns not to show (see *AttrEditor.HIDEABLE_COLUMNS*).
  :type hideColumns: Iterable[str]
  :param listItemMakers: As for *editAttrsBox()*.
  :type listItemMakers: Optional[dict[str, ItemMaker]]
  '''
  attrChangeList = editAttrsBox(parent, attrs, title, editKey, hideColumns=hideColumns, listItemMakers=listItemMakers)
  if attrChangeList is not None:
    with attrs.ChangeMgr(attrs) as cm:
      #attrs.updateWith(attrChangeList)
      #topics = []
      for k,v in attrChangeList.items():
        try:
          attrs.setAttr(k,v)
        except Exception as ex:
          logger.exception(f'applyEditAttrsBox() failed to update attribute "{k}".')
        #topics.append(("setattr", k, v))
      #cm.registerTopics(topics)
      
def _updateWith(attrs:AttributedObject, attrChangeList):
  '''
  :param attrs:
  :type attrs: AttributedObject
  :param attrChangeList:
  :type attrChangeList:
  '''
  pass
  
def _keyedMessage(key:str, ex:Exception) -> str:
  '''
  An error message that names *key* exactly once.

  :param key:
  :type key: str
  :param ex:
  :type ex: Exception
  :returns:
  :rtype: str
  '''
  msg = str(ex)
  return msg if msg.startswith(f'key "{key}"') else f'key "{key}": {msg}'

def getEditedAttrsCommandObj(parent:tk.Widget, attrs:AttributedObject, title="Attributes Editor", editKey:Optional[str]=None, disabled:bool=False):
  '''
  :return: An *UpdateAttrsCommand* object that displays an *AttrsEditor* or a
      *HierarchicalAttrsEditor* (depending on whether *attrs* is an *AttributedObject*
      or a *HierarchicalAttributedObject* ) with the appropriate do/undo properties.
  :param parent:
  :type parent: tk.Widget
  :param attrs:
  :type attrs: AttributedObject
  :param title:
  :type title: str
  :param editKey:
  :type editKey: Optional[str]
  :param disabled:
  :type disabled: bool
  '''
  updates = editAttrsBox(parent, attrs, title=title, editKey=editKey, disabled=disabled)
  return UpdateAttrsCommand(attrs, updates) if updates is not None else None
  
## Utility
def clearGrid(widget:tk.Widget, row=None, column=None):
  '''
  :param widget:
  :type widget: tk.Widget
  :param row:
  :type row:
  :param column:
  :type column:
  '''
  for w in widget.grid_slaves(row=row, column=column):
    w.destroy()

@dataclass
class ChangeDescr:
  '''
  The editor's record of one attribute's row: its Tk variable and widget, whether it's to be deleted, and how to save it.
  '''
  tkVar:tk.Variable|None #= None
  editor:tk.Widget|None #= None
  delete:bool #= False
  saveMethod:Callable #= lambda attr: attr.value
  
  typeLabel = None
  # editTypeButton = None
  # qualFinal:tk.BooleanVar = None # tk.BooleanVar()
  # qualInstanceFinal:tk.BooleanVar = None # tk.BooleanVar()
  # qualValueNotInherited:tk.BooleanVar = None # tk.BooleanVar()
  qual:Restriction|None = None
  
  def getValue(self) -> Any:
    '''
    :returns:
    :rtype: Any
    '''
    if isinstance(self.editor, tk.Text):
      return self.editor.get("1.0", tk.END)
    elif isinstance(self.editor, ListEditor):
      return self.editor.getList()
    else:
      return None if self.tkVar is None else self.tkVar.get()

  def setValue(self, val:Any):
    '''
    :param val:
    :type val: Any
    :returns:
    :rtype:
    '''
    if isinstance(self.editor, tk.Text):
      self.editor.delete("1.0", tk.END)
      self.editor.insert("1.0", val)
    elif isinstance(self.editor, ListEditor):
      self.editor.setList(list(val or []))
    else:
      return self.tkVar.set(val)

SYS_ATTRIBUTES = ['name']
"Used to highlight the 'system' labels on the grid"

ItemMaker = Union[Callable[[tk.Misc], Optional[str]], dict[str, Callable[[tk.Misc], Optional[str]]]]
'''What a list editor's "Add..." does (see *ListEditor*): given the editor, the item to add (or None); or
several such, by their buttons' labels (eg: "Add file...", "Add URL...").'''

class ListEditor(tk.Frame):
  '''
  An editor for a list of strings (an attribute of type "list[str]"): the items
  in order, in a list box, with buttons to add one, remove the selected one,
  and move it up or down (the order may matter: eg: super-models are searched
  in order). Double-click an item to edit it.
  '''
  MAX_HEIGHT = 6
  "The most items shown at once (the rest scroll)."

  def __init__(self, master, items:list[str], newItem:Optional[ItemMaker]=None):
    '''
    :param master:
    :type master:
    :param items: The list (not changed: see *getList()*).
    :type items: list[str]
    :param newItem: What "Add..." does: given this editor (as a parent for any
      dialog), returns the item to add, or None to add nothing. By default, it
      asks for a string. Or several ways to add one, by their buttons' labels
      (eg: {"Add file...": ..., "Add URL...": ...}): a button each.
    :type newItem: Optional[ItemMaker]
    '''
    tk.Frame.__init__(self, master)
    adders:dict[str, Optional[Callable[[tk.Misc], Optional[str]]]] = dict(newItem) if isinstance(newItem, dict) else {"Add...": newItem}
    self.newItem = next(iter(adders.values()))
    self.state:str = tk.NORMAL
    self.listbox = tk.Listbox(self, height=self._height(len(items)), exportselection=False, activestyle="none")
    self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.listbox.yview)
    self.listbox.configure(yscrollcommand=self.scrollbar.set)
    self.listbox.grid(row=0, column=0, sticky="NSEW")
    self.scrollbar.grid(row=0, column=1, sticky="NS")
    self.columnconfigure(0, weight=1)
    buttons = tk.Frame(self)
    buttons.grid(row=0, column=2, sticky="N", padx=(4, 0))
    self.buttons:dict[str, ttk.Button] = {}
    width = max(7, *(len(label) for label in adders))
    def adding(maker:Optional[Callable[[tk.Misc], Optional[str]]]) -> Callable[[], None]:
      return lambda: self.add(maker)
    commands:list[tuple[str, str, Callable[[], None]]] = [(f"add{i}" if i else "add", label, adding(maker)) for i, (label, maker) in enumerate(adders.items())]
    commands += [("remove", "Remove", self.remove), ("up", "\u25B2", lambda: self.move(-1)), ("down", "\u25BC", lambda: self.move(1))]
    for name, text, command in commands:
      b = ttk.Button(buttons, text=text, width=width if len(text) > 1 else 3, command=command)
      b.pack(side=tk.TOP if not name in ("up", "down") else tk.LEFT, anchor="w")
      self.buttons[name] = b
    self.listbox.bind("<Double-Button-1>", lambda _e: self.editSelected())
    self.listbox.bind("<<ListboxSelect>>", lambda _e: self._updateButtons())
    self.setList(items)

  def _height(self, n:int) -> int:
    return max(2, min(n, self.MAX_HEIGHT))

  def getList(self) -> list[str]:
    '''
    :returns: The items, in order.
    :rtype: list[str]
    '''
    return [str(x) for x in self.listbox.get(0, tk.END)]

  def setList(self, items:list[str]) -> None:
    '''
    :param items: The items to show, in order.
    :type items: list[str]
    '''
    self.listbox.delete(0, tk.END)
    for x in items:
      self.listbox.insert(tk.END, str(x))
    self.listbox.configure(height=self._height(len(items)))
    self._updateButtons()

  def _selected(self) -> Optional[int]:
    sel = self.listbox.curselection()
    return int(sel[0]) if sel else None

  def _select(self, i:int) -> None:
    self.listbox.selection_clear(0, tk.END)
    self.listbox.selection_set(i)
    self.listbox.see(i)
    self._updateButtons()

  def _updateButtons(self) -> None:
    enabled = self.state != tk.DISABLED
    i = self._selected()
    n = self.listbox.size()
    states = {**{name: enabled for name in self.buttons if name.startswith("add")}, "remove": enabled and i is not None,
              "up": enabled and i is not None and i > 0, "down": enabled and i is not None and i < n - 1}
    for name, on in states.items():
      self.buttons[name].state(["!disabled"] if on else ["disabled"])

  def add(self, maker:Optional[Callable[[tk.Misc], Optional[str]]]=None) -> None:
    '''
    "Add...": add an item (see *newItem*) after the selected one, or at the end.

    :param maker: What makes it (one of *newItem*'s, if it has several); by
      default, the first.
    :type maker: Optional[Callable[[tk.Misc], Optional[str]]]
    '''
    if self.state == tk.DISABLED:
      return
    maker = maker or self.newItem
    if maker is not None:
      item = maker(self)
    else:
      item = simpledialog.askstring("Add", "New item:", parent=self)
    if item is None:
      return
    i = self._selected()
    at = self.listbox.size() if i is None else i + 1
    self.listbox.insert(at, str(item))
    self.listbox.configure(height=self._height(self.listbox.size()))
    self._select(at)

  def remove(self) -> None:
    '''"Remove": remove the selected item.'''
    i = self._selected()
    if self.state == tk.DISABLED or i is None:
      return
    self.listbox.delete(i)
    self.listbox.configure(height=self._height(self.listbox.size()))
    if self.listbox.size() > 0:
      self._select(min(i, self.listbox.size() - 1))
    else:
      self._updateButtons()

  def move(self, step:int) -> None:
    '''
    Move the selected item up (*step* -1) or down (1).

    :param step: -1 or 1.
    :type step: int
    '''
    i = self._selected()
    if self.state == tk.DISABLED or i is None or not 0 <= i + step < self.listbox.size():
      return
    item = self.listbox.get(i)
    self.listbox.delete(i)
    self.listbox.insert(i + step, item)
    self._select(i + step)

  def editSelected(self) -> None:
    '''Edit the selected item's text (on a double-click).'''
    i = self._selected()
    if self.state == tk.DISABLED or i is None:
      return
    text = simpledialog.askstring("Edit", "Item:", initialvalue=self.listbox.get(i), parent=self)
    if text is not None:
      self.listbox.delete(i)
      self.listbox.insert(i, text)
      self._select(i)

  def config(self, **conf):
    '''
    "state" ("normal" or "disabled") applies to the whole editor; colours to the
    list box; anything else to the frame.
    '''
    if "state" in conf:
      state = conf.pop("state")
      self.state = tk.DISABLED if str(state) in (tk.DISABLED, "disabled") else tk.NORMAL
      self.listbox.configure(state=self.state)
      self._updateButtons()
    for k in ("foreground", "fg", "background", "bg"):
      if k in conf:
        self.listbox.configure(**{k: conf.pop(k)})
    if conf:
      tk.Frame.config(self, **conf)
  configure = config # type: ignore[assignment]

class ColorEditor(tk.Frame):
  '''
  An editor for a colour value: a swatch that opens the system colour chooser, and a button to make it transparent.
  '''
  def __init__(self, master, var:tk.StringVar, color:str):
    '''
    :param master:
    :type master:
    :param var:
    :type var: tk.StringVar
    :param color:
    :type color: str
    '''
    self.var = var
    #self.style = ttk.Style()
    #self.style.configure('My.TFrame', background="purple")#color)
    self.c = WINDOW_BACKGROUND if color=="" else color
    tk.Frame.__init__(self, master)
    self.colorButton = tk.Button(self, text=str(color), command=self.colorChooser)#, highlightbackground=None if color=="" else color, padx=-15)
    self.colorButton.pack(side="left", expand=0)#), fill="x")
    self.transButton = tk.Button(self, text="\u2A37", command=self.setTransparent)#, highlightbackground=None if color=="" else color, padx=-30)
    self.transButton.pack(side="right", expand=0)
    self.swatch = tk.Canvas(self, background=self.c, height=3, width=5, borderwidth=2, relief="groove")
    #self.swatch.pack(side="left", after=self.colorButton, expand=1, anchor="center", fill="both", ipadx=0, ipady=0, padx=0, pady=0)
    self.swatch.pack(side="bottom", expand=1, anchor="center", fill="both", ipadx=0, ipady=0, padx=0, pady=0)

    # self.colorButton.config(command=self.colorChooser)
    # self.transButton.config(command=self.setTransparent)
    self.config(bg=self.c)
    
  def setTransparent(self):
    self.colorButton.configure(text="", highlightbackground=None)
    self.var.set("")
    self.config(bg="")
    
  def colorChooser(self):
    # askcolor() returns (rgb, hex)
    color =self.var.get()
    if color is None:
      color = "black"
    if color == "": # colorchooser() can't handle "" (transparent)
      color = "gray"
    color = colorchooser.askcolor(initialcolor=color, parent=self)
    if color is not None:
      color = color[1]
      self.var.set(color)
      self.config(bg=color)
      self.colorButton.config(text=str(color))
    
  def config(self, **conf):
    
    '''
    :param conf:
    :type conf:
    '''
    def setSwatch(key:str):
      self.c = WINDOW_BACKGROUND if conf[key]=="" else conf[key]
      d = {key: self.c}
      self.swatch.configure(**d)
      del conf[key]
      
    if "bg" in conf:
      setSwatch("bg")
    if "background" in conf: 
      setSwatch("background")
    if "highlightbackground" in conf: 
      setSwatch("highlightbackground")
    if "highlightcolor" in conf: 
      setSwatch("highlightcolor")
    if len(conf) > 0:
      if "!disabled" in conf:
        conf["normal"] = "normal"
        del conf["!disabled"]
      self.colorButton.configure(**conf)
      self.transButton.configure(**conf)
    
class AttrEditor(tk.Toplevel):
  '''
  Implements a graphical editor for an *AttributedObject* of the form:
  
  +--------------------------------+
  | <editor lines> ...             |
  +--------------------------------+
  | [<Message line>]               |
  +--------------------------------+
  | [<Answer line>]                |
  +--------------------------------+
  | <Add New Attribute button>     |
  +--------------------------------+
  | <Cancel button>  <Save button> |
  +--------------------------------+

  where <editor lines> look like this:
  
  +------+---------+----------------+--------+--------+----------------------+
  |<stat>| <label> | <value editor> | <type> | <note> | <button> <button>... |
  +------+---------+----------------+--------+--------+----------------------+
  |<stat>| <label> | <value editor> | <type> | <note> | <button> <button>... |
  +------+---------+----------------+--------+--------+----------------------+

  If any attribute's name has a "/" in it, the lines are grouped by the parts of
  the names, like folders (see *treeOrder()*): each group has a header line with
  a triangle that collapses or expands it, and each attribute is labelled with
  just the last part of its name, indented under its group.
  
  The <Message line> and <Answer iine> are only visiable when the *setMessage()* 
  or *ask()* methods are called.
  
  '''
  collapsedGroups:set[str] = set()
  "The groups collapsed when an editor was last closed: the next one starts with them collapsed too."

  #TODO: Implement "disabled" param
  HIDEABLE_COLUMNS:dict[str, str] = {"type": "cKind", "qualifiers": "cQuals", "note": "cNote", "actions": "cDel"}
  '''The columns that can be hidden (see *hideColumns*), by name: name -> the
  attribute holding the column's number. ("qualifiers" -- the inheritance
  restrictions -- is only in a *HierarchicalAttrEditor*.)'''

  def __init__(self, parent, attrs:AttributedObject, title="Attribute Editor", disabled=False,
               displayValues:Optional[dict[str,Any]]=None, hideColumns:Iterable[str]=(),
               listItemMakers:Optional[dict[str, ItemMaker]]=None):
    '''
    :param parent:
    :type parent:
    :param attrs:
    :type attrs: AttributedObject
    :param title:
    :type title: str
    :param disabled:
    :type disabled: bool
    :param displayValues:
    :type displayValues: Optional[dict[str, Any]]
    :param hideColumns: The columns not to show, by name (see
      *HIDEABLE_COLUMNS*): eg: ("type", "qualifiers", "note") for settings,
      whose notes are their documentation -- still shown as their names'
      tooltips.
    :type hideColumns: Iterable[str]
    :param listItemMakers: For "list[str]" attributes: what their "Add..."
      does, by key -- eg: a file chooser (see *ListEditor*). By default, it
      asks for a string.
    :type listItemMakers: Optional[dict[str, ItemMaker]]
    '''
    super().__init__(parent)
    self.parent = parent
    self.listItemMakers:dict[str, ItemMaker] = dict(listItemMakers or {})
    unknown = set(hideColumns) - set(self.HIDEABLE_COLUMNS)
    assert not unknown, f'AttrEditor: unknown columns to hide: {sorted(unknown)} (expected some of {list(self.HIDEABLE_COLUMNS)}).'
    self.hideColumns:set[str] = set(hideColumns)
    "The columns not shown (see *_applyHiddenColumns()*)."
    self.displayValues:dict[str,Any] = dict(displayValues or {})
    "Values shown for some keys in place of their stored ones (see *editAttrsBox()*)."
    self.title(title if title else "Attribute Editor")
    self.attrs:AttributedObject = attrs
    #self.changes = dict() # name:Item
    self.vars:dict[str,ChangeDescr] = dict() # name:ChangeDescr
    
    self.hide = lambda attr: False
    self.disabled:bool = disabled
    #self.editable = lambda attr: not self.disabled
    self.updatedKeys = None
    self.rows:int = 0 # The total number of rows in the editors list grid.
    
    self.editKey:Optional[str] = None
    self.editWidget:Optional[Widget] = None

    self.noteEdits:dict[str, str] = {}
    "Attributes' notes as edited (see *editNote()*), by key: only those that have been."
    self.treeMode:bool = False
    "Whether the attributes are shown grouped by the parts of their names (see *treeOrder()*)."
    self._labels:dict[str, tuple[str, int]] = {}
    "Each attribute's label, and its depth in the tree (see *makeNewEntry()*)."
    self._groupSpans:dict[str, tuple[int, int]] = {}
    "Each group's rows in the grid -- the first and the one after the last -- below its header."
    self._groupHeaders:dict[str, tk.Label] = {}
    self._hiddenWidgets:dict[str, list[tk.Widget]] = {}
    "The widgets each collapsed group hid (see *toggleGroup()*), to show again when it's expanded."
    
    #TODO: move these to the class level
    # "constants" for the outer grid
    self.rEditors:int = 0
    self.rMessage:int = 2
    self.rEnter:int = 3
    self.rButtons1:int = 6
    self.rButtons2:int = 8

    # "constants" for the columns in the Editors grid
    self.rowsPerEntry:int = 1
    self.EntryOffset:int = 0
    self.cStatus:int = 0
    self.cLabel:int = 1
    self.cEdit:int = 2
    self.cKind:int = 3
    self.cNote:int = 4
    self.cDel:int = 5
    self.cspan:int = 6
    
    self.outerSpan:int = 2
    

  def show(self, editKey:Optional[str]=None): #, disabled=False):
    '''
    :param editKey: [Optional str] If present, set the edit focus to the *editKey* 
      creating a local attribute if necessary.
    '''
    self.editKey = editKey
    
    self.geometry("820x600")
    #self.title('Attributes')
    self.resizable(1, 1)

    # configure the outer grid
    self.columnconfigure(0, weight=1)
    self.columnconfigure(1, weight=1)
    self.rowconfigure(0, weight=2)
    self.rowconfigure(1, weight=0)

    scrollFrame = VerticalScrolledFrame(self)
    scrollFrame.grid(column=0, row=self.rEditors, columnspan=self.outerSpan, sticky=tk.W+tk.E+tk.N+tk.S, padx=0, pady=0)
    self.editorsListFrame = scrollFrame.interior
    #self.editorsListFrame.pack()

    # configure list of editor's grid
    self.editorsListFrame.columnconfigure(self.cStatus, weight=0)
    self.editorsListFrame.columnconfigure(self.cLabel, weight=0)
    self.editorsListFrame.columnconfigure(self.cEdit,  weight=2, minsize=200)
    self.editorsListFrame.columnconfigure(self.cKind,  weight=0)
    self.editorsListFrame.columnconfigure(self.cNote,  weight=0)
    self.editorsListFrame.columnconfigure(self.cDel,   weight=0)
    
    self.makeHeader(0)
    ttk.Separator(self.editorsListFrame, orient=tk.HORIZONTAL) \
      .grid(column=0, row=1, columnspan=self.cspan, sticky=tk.W+tk.E, padx=0, pady=0)
    i = 2
    keys = list(self.attrs.keys())
    keys = [k for k in keys if not isHiddenKey(k)] # (eg: ".openWindows", or anything in a ".internal" group)
    self.treeMode = any(GROUP_SEPARATOR in k for k in keys)
    if self.treeMode:
      items = treeOrder(keys)
    else:
      items = [("key", k, 0) for k in sorted(keys, key=str.lower)]
    starts:list[tuple[str, str, int, int]] = [] # (kind, name, depth, first row) of each line shown
    for kind, name, depth in items:
      try:
        if kind == "group":
          starts.append((kind, name, depth, i+self.EntryOffset))
          self.makeGroupHeader(name, depth, i+self.EntryOffset)
          i += 1
          continue
        k = name
        v  = self.attrs.getAttr(k)
        self.vars[k] = ChangeDescr(None, None, False, str)
        row = i+self.EntryOffset
        if self.hide(v): continue # hide system attributes
        shortName = k.rsplit(GROUP_SEPARATOR, 1)[-1] if self.treeMode else k
        self._labels[k] = (shortName or k, depth)
        starts.append((kind, k, depth, row))
        self.makeNewEntry(k, v, row, self.disabled, "")
        i += self.rowsPerEntry
      except:
        logger.exception(f'Failed to load on key "{name}"')
      
    self.rows = i
    self._applyHiddenColumns() # (before collapsing: a collapsed group only puts back what it hid)
    # each group's rows: from below its header to the next line no deeper than it
    end = i+self.EntryOffset
    for n, (kind, name, depth, row) in enumerate(starts):
      if kind == "group":
        nxt = next((r for kd, nm, d, r in starts[n+1:] if d <= depth), end)
        self._groupSpans[name] = (row + 1, nxt)
    # collapse the groups that were collapsed when an editor was last shown (deepest first,
    # so that expanding a group leaves its collapsed subgroups collapsed)
    for name in sorted(self._groupSpans, key=lambda g: -g.count(GROUP_SEPARATOR)):
      if name in AttrEditor.collapsedGroups and not (editKey is not None and editKey.startswith(name + GROUP_SEPARATOR)):
        self.toggleGroup(name, remember=False)
      
    ttk.Separator(self, orient=tk.HORIZONTAL) \
      .grid(column=0, row=self.rMessage-1, columnspan=self.outerSpan, sticky=tk.W+tk.E, padx=0, pady=0)
      
    ttk.Separator(self, orient=tk.HORIZONTAL) \
      .grid(column=0, row=self.rButtons1-2, columnspan=self.outerSpan, sticky=tk.W+tk.E, padx=0, pady=0)
    ttk.Separator(self, orient=tk.HORIZONTAL) \
      .grid(column=0, row=self.rButtons1-1, columnspan=self.outerSpan, sticky=tk.W+tk.E, padx=0, pady=2)
    if not self.disabled:
      ttk.Button(self, text="Add New Attribute", command=self.addNewAttribute) \
        .grid(column=0, row=self.rButtons1, columnspan=self.outerSpan, padx=20, pady=2) #, sticky=tk.W

    ttk.Separator(self, orient=tk.HORIZONTAL) \
      .grid(column=0, row=self.rButtons2-1, columnspan=self.outerSpan, sticky=tk.W+tk.E, padx=0, pady=0)
    ttk.Button(self, text="Dismiss" if self.disabled else "Cancel", command=self.dismiss,
               default="active" if self.disabled else "normal") \
      .grid(column=0, row=self.rButtons2, columnspan=1, sticky=tk.W, padx=20, pady=10)
    if not self.disabled:
      ttk.Button(self, text="Save Changes", command=self.save, default="active") \
        .grid(column=1, row=self.rButtons2, columnspan=1, sticky=tk.E, padx=20, pady=10)

    self.protocol("WM_DELETE_WINDOW", self.dismiss) # intercept close button
    self.bind("<Escape>", lambda _e: self.dismiss()) # (a way out, always)
    self.bind("<Return>", self._onReturn)            # the default button: Save Changes (Dismiss, if it can't be edited)
    self.bind("<KP_Enter>", self._onReturn)
    #self.overrideredirect(1) # deletes the title bar
    self._placeOverParent()
    # Over its parent's window -- before it's shown: on macOS, a window shown
    # first and made transient afterwards opens full screen when the app is
    # (see util.utils.ownDialog(): only ever over a window that's on screen).
    ownDialog(self, self.parent)

    # make this window modal
    # Force the widget tree built above to actually be laid out and drawn
    # before we wait/grab/transient — otherwise the window can be mapped
    # with nothing yet painted into it.
    self.update_idletasks()
    try: # this wait sometimes fails with "TclError: <window> was deleted before its visibility changed"
      self.wait_visibility() # can't grab until window appears, so we wait
    except:
      pass
    # In front, with the focus: it takes all the input (below), so if it were
    # behind its parent -- or anywhere it can't be seen -- the app would seem
    # to have hung.
    try:
      self.lift()
      self.focus_force()
    except tk.TclError:
      pass
    #self.grab_set()       # ensure all input goes to our window
    try:
      self.grab_set_global() #   used this version because grab_set() doesn't actually work.
    except:
      logger.exception("AttrEditor.show() failed on grab_set_global():")
    try:
      if self.editKey is None:
        self.focus_set()
      else:
        self.editWidget = self.vars[self.editKey].editor
        self.editWidget.focus_set()
    except:
      logger.exception("AttrEditor.show() failed on focus_set():")
      
    try:
      self.wait_window()     # block until window is destroyed
    except:
      logger.exception("AttrEditor.show() failed on wait_window():")
    
  def _validateUpdates(self) -> list[str]:
    '''
    Dry-run the validation *setAttr()* will apply to each changed attribute.

    :returns: A message for each change that would be rejected.
    '''
    if not isinstance(self.attrs, AttributedObject) or not self.updatedKeys:
      return []
    errors:list[str] = []
    for k, attr in self.updatedKeys.items():
      if attr is None: # a deletion
        continue
      try:
        self.attrs._validateOverride(k, self.attrs.isIndividual(), attr, self.attrs._getSuperAttr(k))
      except Exception as ex:
        errors.append(_keyedMessage(k, ex))
    return errors

  def _onReturn(self, event:tk.Event) -> str|None:
    '''
    <Return>: the default button -- "Save Changes" (or "Dismiss", if nothing
    can be edited) -- except in a multi-line text (where it's a new line), or
    while answering a question (see *ask()*: the answer's own <Return>).

    :param event:
    :type event: tk.Event
    :returns: "break" if it was dealt with.
    :rtype: str | None
    '''
    w = event.widget
    if isinstance(w, tk.Text) or w is getattr(self, "askWidget", None):
      return None
    if self.disabled:
      self.dismiss()
    else:
      self.save()
    return "break"

  def _placeOverParent(self) -> None:
    '''
    Put this window over the middle of its parent's window, so it's seen
    where it was asked for -- not at the window system's default place, which
    may be behind the parent, or on another screen or desktop.
    '''
    try:
      top = self.parent.winfo_toplevel()
      if not top.winfo_viewable():
        return
      self.update_idletasks()
      w, h = self.winfo_reqwidth(), self.winfo_reqheight()
      geo = self.geometry().split("+")[0] # (eg: "820x600", set by show())
      if "x" in geo:
        gw, gh = (int(v) for v in geo.split("x"))
        if gw > 1 and gh > 1:
          w, h = gw, gh
      # (not above or left of the parent's top left, so its title bar's on the
      # parent's screen: Tk knows only the main screen's size, so it can't be
      # kept inside another one)
      x = top.winfo_rootx() + max(0, (top.winfo_width() - w) // 2)
      y = top.winfo_rooty() + max(0, (top.winfo_height() - h) // 3)
      self.geometry(f"{w}x{h}+{x}+{y}")
    except (tk.TclError, ValueError):
      pass

  def dismiss(self):
    '''
    Call this method to destroy the window. It will also release the modal window.
    '''
    self.grab_release()
    self.destroy()

  ### HANDLERS #################################################################
  
  def addNewAttribute(self):
    self.ask("Enter the new key:", lambda event, ans: self._addNewAttribute2(event, ans), bg="yellow")

  def _addNewAttribute2(self, event, name:str):
    '''
    :param event:
    :type event:
    :param name:
    :type name: str
    '''
    self.clearMessage()
    if name is None:
      return
    if name in list(self.attrs.keys()):
      self.setMessage(f'Attribute name "{name}" is already in use.', bg="red", fg="yellow")
      return
    newAttr = Attribute("", str, VAR_DEFAULTED)
    self.attrs[name] = newAttr
    self.makeNewEntry(name, newAttr, self.rows+self.EntryOffset, False, keyExt="")
    self.rows += self.rowsPerEntry
    self._applyHiddenColumns()
    self._showEntry(name)

  def _showEntry(self, key:str) -> None:
    '''
    Scroll the list of attributes to show *key*'s row, and put the focus in
    its value: eg: a new attribute, to type its value.

    :param key:
    :type key: str
    '''
    descr = self.vars.get(key)
    editor = getattr(descr, "editor", None)
    if not isinstance(editor, tk.Widget):
      return
    interior = self.editorsListFrame
    canvas = interior.master
    self.update_idletasks()
    if isinstance(canvas, tk.Canvas):
      height = max(1, interior.winfo_height())
      y = editor.winfo_rooty() - interior.winfo_rooty() # (its place in the list)
      view = canvas.winfo_height()
      if not (canvas.canvasy(0) <= y and y + editor.winfo_height() <= canvas.canvasy(0) + view): # (not already in sight)
        canvas.yview_moveto(max(0.0, (y - view / 2) / height))
    try:
      editor.focus_set()
    except tk.TclError:
      pass
    
  def deleteAttr(self, key, item, editor, row, button):
    '''
    :param key:
    :type key:
    :param item:
    :type item:
    :param editor:
    :type editor:
    :param row:
    :type row:
    :param button:
    :type button:
    '''
    text = button.config()['text'][-1]
    logger.debug(f"deleteAttr: text = '{text}'")
    if text == 'delete':
      button.config(text='undel')
      editor.config(state="disabled")
      self.vars[key].delete = True
    else:
      button.config(text='delete')
      editor.config(state="!disabled")
      self.vars[key].delete =  False

  def typeInconsistent(self, event, ans, key, row, newType):
    '''
    :param event:
    :type event:
    :param ans:
    :type ans:
    :param key:
    :type key:
    :param row:
    :type row:
    :param newType:
    :type newType:
    '''
    ans = (ans or "").strip().upper()
    if ans not in ["Y", "N"]:
      return # give up
    if ans == "Y": # the new type, with its default value (not "", which may not be one)
      self.resetKind(newType, key, row, value=_defaultValue(newType))
    self.clearMessage()
       
  def resetKind(self, kind, key, row, value:Any=NOVALUE):
    '''
    Change *key*'s type to *kind*, with *value* (default: its current one) --
    which must suit *kind* (see *_convertValue()*).

    :param kind:
    :type kind:
    :param key:
    :type key:
    :param row:
    :type row:
    :param value:
    :type value: Any
    '''
    clearGrid(self.editorsListFrame, column=self.cKind, row=row)
    self.makeKind(self.editorsListFrame, key, kind, self.cKind, row, None, False, "")
    self._applyHiddenColumns()
    if value is NOVALUE:
      value = self.vars[key].getValue()
    typeLabel = self.vars[key].typeLabel
    #tempAttr = copy(self.attrs._attrs[key])
    tempAttr = copy(self.attrs.getLocalAttr(key))
    #tempAttr.owner = None
    assert tempAttr is not None
    tempAttr._type = kind # (not via .type: that checks the new type against the OLD value)
    tempAttr.value = value
    self.makeEditor(self.editorsListFrame, key, tempAttr, self.cEdit, row, False, "")
    self.vars[key].setValue(str(value) if isinstance(value, bool) else value) # (a checkbox's on/off values are "True"/"False"; Tk would make a bool 1/0)
    self.vars[key].typeLabel = typeLabel
    
  def editTypeAnswer(self, button, event, ans, key, row): 
    '''
    :param button:
    :type button:
    :param event:
    :type event:
    :param ans:
    :type ans:
    :param key:
    :type key:
    :param row:
    :type row:
    '''
    if ans is None:
      return
    ans = ans.strip()
    if not isValidType(ans):
      self.clearMessage()
      self.ask(f'Invalid type for key "{key}". Please enter one of the following known types:\n{KNOWN_TYPES}:', 
               lambda event, ans, b=button, key=key, row=row: self.editTypeAnswer(b, event, ans, key, row),
               default=ans, bg="red", fg="yellow")
      return
    # The editor holds values as text: convert it to the new type if it can be
    # (eg: "true" -> True, "3" -> 3). An empty value just takes the new type's
    # default; only a value that would be lost needs asking about.
    current = self.vars[key].getValue()
    current = "" if current is None else str(current).strip()
    value = _convertValue(ans, current)
    if value is NOVALUE and current == "":
      value = _defaultValue(ans)
    if value is NOVALUE:
      self.clearMessage()
      self.ask(f'The value "{current}" of key "{key}" is not of type {ans}.\n  Do you want to keep this type and replace the value with a default? [Y/N]:', 
               lambda event, ans, key=key, row=row, newType=ans: self.typeInconsistent(event, ans, key, row, newType),
               default="Y", bg="red", fg="white") 
      return
    self.resetKind(ans, key, row, value=value)
    self.clearMessage()
    
  def editType(self, b:tk.Button, parent, key, typ, column, row):
    '''
    :param b:
    :type b: tk.Button
    :param parent:
    :type parent:
    :param key:
    :type key:
    :param typ:
    :type typ:
    :param column:
    :type column:
    :param row:
    :type row:
    '''
    self.ask(f'Enter new type for key "{key}":', 
             lambda event, ans, b=b, key=key, row=row: self.editTypeAnswer(b, event, ans, key, row),
             default=self.vars[key].typeLabel["text"], bg="yellow") 

  def hasChanged(self, k:str) -> bool:
    '''
    :param k:
    :type k: str
    :returns:
    :rtype: bool
    '''
    if k not in strdict.keys(self.attrs): # not local definition
      return False
    try:
      origAttr:Attribute = self.attrs.getLocalAttr(k) if k in list(strdict.keys(self.attrs)) else None
      v = self.vars[k]
      if origAttr is None:
        typeStr = "str"
        origValue = None
      else:
        origValue = self.displayValues.get(k, origAttr.value) # (compared with what was shown)
        origType = origAttr.type
        if origType is None: # a value-only override: the label shows the inherited type
          inhRec = self.attrs.getInhAttr(k)
          origType = None if inhRec is None else inhRec.type
        if isinstance(origType, type):
          typeStr = getFullClassName(origType)
        else:
          typeStr = str(origType)
          
      valueChanged = True # assume it's changed and try to disprove it
      if v.editor is None:
        valueChanged = False
      elif v.editor is tk.Label:
        valueChanged = False
      elif "state" in v.editor.keys() and v.editor["state"]==tk.DISABLED:
        valueChanged = False
      if valueChanged:
        strValue = v.getValue()
        value = v.saveMethod(strValue)
        if value == origValue:
          valueChanged = False
        
      #TODO: check this
      typeChanged = (v.typeLabel["text"] != typeStr) if v.typeLabel is not None else False

      noteChanged = k in self.noteEdits and self.noteEdits[k] != ((origAttr.note if origAttr is not None else None) or "")
  
      return valueChanged or typeChanged or noteChanged
      
    except:
      logger.exception(f"AttributeEditor.hasChanged('{k}'):")
      return False
    
  def _saveKey(self, k:str, origAttr:Attribute):
    '''
    :param k:
    :type k: str
    :param origAttr:
    :type origAttr: Attribute
    '''
    logger.info(f'AttribueEditor changeing: "{k}"')
    v:ChangeDescr = self.vars[k]
    self.updatedKeys[k] = copy(origAttr) if origAttr is not None else Attribute(k)
    a:Attribute = self.updatedKeys[k]
    t = v.typeLabel["text"]
    if t == "None":
      t = None
    a._type = t
    strValue = v.getValue()
    value = v.saveMethod(strValue)
    a.value = value
    if k in self.noteEdits: # (a note written here is the user's: it's saved, and the program's won't replace it -- see Attribute.userNote)
      a.note = self.noteEdits[k] or None
      a.userNote = bool(self.noteEdits[k]) # (cleared: back to the program's own note)
    if self.attrs.getInhAttr(k) is None: # we need to return a complete Attribute..
      if a.value is NOVALUE:
        logger.warning(f'AttrEditor adding None value for key "{k}".')
        a.value = None
      if a.type is None:
        logger.warning(f'AttrEditor adding str type for key "{k}".')
        a.type = str
      if a.restriction is None:
        logger.warning(f'AttrEditor adding VAR_DEFAULTED restriction for key "{k}".')
        a.restriction = VAR_DEFAULTED
    else:
      if a.type is not None:
        logger.warning(f'AttrEditor removing {a.type} type for key "{k}".')
        a.type = None
      if a.restriction is not None:
        logger.warning(f'AttrEditor removing {a.restriction} restriction for key "{k}".')
        a.restriction = None
    logger.info(f'AttribueEditor changed: "{k}": {self.updatedKeys[k]}')
          
  def save(self):
    '''
    Stores a key/Attribute dictionary of all attributes that have been modified
    in the *self.updatedKeys* dictionary.  In the case of deleted Attributes, 
    the key maps to *None* .
    '''
    if self.disabled:
      return
    
    self.updatedKeys:dict[str, Optional[Attribute]] = dict()
    errors:list[str] = []
    for k,v in self.vars.items():
      #ignore the records just used to display inherited items
      if k.endswith(INHERIT_KEY_EXT):
        continue
        
      #handle deletion
      if v.delete:
        self.updatedKeys[k] = None
        logger.debug(f'save(): deleting "{k}"')
        continue
        
      #handle changes
      if k not in self.attrs.keys(): # 
        continue
      origAttr:Attribute|None = self.attrs.getLocalAttr(k) if k in list(strdict.keys(self.attrs)) else None
      if origAttr is None:
        logger.debug(f'key "{k}" has not changed')
        continue
      try:
        if self.hasChanged(k):
          logger.debug(f'save(): saving "{k}"')
          self._saveKey(k, origAttr)
      except Exception as ex:
        logger.exception(f'Failed on key {k}, value {v.getValue()}: {ex.__class__.__name__}: {ex}')
        errors.append(_keyedMessage(k, ex))

    for k in getattr(self, "assertedKeys", ()): # (inferred ones made given: see assertAttr())
      origAttr = self.attrs.getLocalAttr(k)
      if origAttr is not None and getattr(origAttr, "inferred", False) and k not in self.updatedKeys:
        attr = Attribute(origAttr.value, origAttr.type, origAttr.restriction, origAttr.note)
        attr.userNote = origAttr.userNote
        self.updatedKeys[k] = attr

    # Check the changes against the inheritance rules now, while the user can
    # still fix them: once the dialog is gone, a rejected setAttr() would only
    # be logged, and the change silently lost.
    errors += self._validateUpdates()
    if errors:
      messagebox.showerror(self.title() or "Attribute Editor",
                           "These changes can't be saved:\n\n" + "\n".join(errors), parent=self)
      self.updatedKeys = None # nothing is saved unless the user fixes them and saves again
      return
        
    if len(self.updatedKeys) == 0:
      self.updatedKeys = None
      
    self.dismiss()
    return
    
    # for k,v in self.vars.items():
    #   if v.delete: # flagged for deletion
    #     self.attrs.remove(k)
    #     continue
    #
    #   # get the kind and the new value
    #   kind = self.attrs._get(k).typ
    #   if kind == 'mtext':
    #     newValue = v.tkVar.get('1.0', 'end').rstrip() # the Text widget is tk, and doesn't use a a ttk.Variable.
    #   else:
    #     newValue = v.tkVar.get() 
    #
    #   if kind == 'int':
    #     try:
    #       newValue = int(newValue)
    #     except:
    #       print(f'WARNING: AttrEditor.save(): attribute {k} of kind int has value {newValue}, which failed the int test.  Not saving.')
    #       continue
    #   if kind == 'float':
    #     try:
    #       newValue = float(newValue)
    #     except:
    #       print(f'WARNING: AttrEditor.save(): attribute {k} of kind float has value {newValue}, which failed the float test.  Not saving.')
    #       continue
    #   elif kind == 'bool':
    #     try:
    #       newValue = newValue.lower() in ['true', 't', 'yes', 'y']
    #     except:
    #       print(f'WARNING: AttrEditor.save(): attribute {k} of kind bool has value {newValue}, which failed the bool test.  Not saving.')
    #       continue
    #
    #   if v.oldValue != newValue:
    #     print(f"AttrEditor.save(): {k} changed from '{v.oldValue}' ({type(v.oldValue).__name__}) to '{newValue}' ({type(newValue).__name__}). Observers={self.attrs.observers}.")
    #     try:
    #       self.attrs.config(k, newValue)
    #     except KeyError:
    #       self.attrs[k] = Attribute(k, newValue)
    #       # need to copy all the details from the inherited record to the new value...
    #       inhRec = self.attrs._get(k, includeLocals=False)
    #       inhRec.value = newValue
    #       inhRec.editable = True # the editable attribute does not inherit
    #       self.attrs.config(k, _record=inhRec)
    #
    #     self.attrs.notifyObservers(k, newValue)
    # self.grab_release()
    # self.destroy()

    
  
  ### UTILITY METHODS ########################################################
  
  def getEditorForType(self, parent:Any, key:str, typ:Union[type, str, NoneType], value:Any, keyExt, inhType:str|type|None=None) -> Any:
    
    '''
    :param parent:
    :type parent: Any
    :param key:
    :type key: str
    :param typ:
    :type typ: Union[type, str, NoneType]
    :param value:
    :type value: Any
    :param keyExt:
    :type keyExt:
    :param inhType:
    :type inhType: str | type | None
    :returns:
    :rtype: Any
    '''
    def getHeight(text:str):
      return min(text.count('\n')+1, 4)
      
    editor = None

    if typ is None:
      typ = inhType
    if typ is None:  
      typ = type(value)
      
    # Change the standard type string into actual types to save code below.
    if isinstance(typ, str) and typ not in ["color", "colour", "list[str]"] and typ in TYPE_EQUIVALENTS:
      typ = TYPE_EQUIVALENTS[typ]

    if isinstance(typ, str):
      if typ == 'mtext': # Anomalous in that there is NO textvariable. 
        editor = tk.Text(parent, height=getHeight(value))
        editor.insert('1.0', value)
        self.vars[key+keyExt] = ChangeDescr(None, editor, False, str)
      elif typ == 'list[str]':
        editor = ListEditor(parent, [str(x) for x in (value or [])], self.listItemMakers.get(key))
        self.vars[key+keyExt] = ChangeDescr(None, editor, False, lambda val: list(val))
      elif typ in ['color', 'colour']:
        if value is None:
          value = "black"
        v = tk.StringVar(value=str(value))
        # editor = tk.Button(parent, text=str(value), highlightbackground=None if value=="" else value, padx=-15)#, highlightthickness=4)
        # editor.config(command=lambda v=v, e=editor: self.colorChooser(v, e))
        # self.vars[key+keyExt] = ChangeDescr(v, editor, False, str)
        editor = ColorEditor(parent, v, value)
        self.vars[key+keyExt] = ChangeDescr(v, editor, False, str)
      elif typ.startswith('choices['):
        choices = None
        if not typ.endswith(']'):
          logger.error(f'{self.__class__.__name__}.getEditorForType(): Malfored "choices" type: "{typ}" (syntox is "choices[choice, choice, ...]")')
        else:
          choices = typ[8:-1].split(",")
          for i in range(len(choices)):
            choices[i] = choices[i].strip()
        v = tk.StringVar(value=str(value))
        if choices is not None:
          editor = ttk.Combobox(parent, textvariable=v, state="readonly")
          #editor['values'] = validator(None)
          editor['values'] = choices
          #editor.state(["readonly"])
          self.vars[key+keyExt] = ChangeDescr(v, editor, False, str)
      elif typ == 'unknown':
        editor = ttk.Label(parent, text=str(value), foreground="brown")
    elif isinstance(typ, Type):
      if typ is int:
        checkWrapper = (self.winfo_toplevel().register(self.checkInt), '%P')
        v = tk.StringVar(value=str(value))
        editor = ttk.Entry(parent, textvariable=v, validate='key', validatecommand=checkWrapper)
        self.vars[key+keyExt] = ChangeDescr(v, editor, False, int)
      elif typ is float:
        checkWrapper = (self.winfo_toplevel().register(self.checkFloat), '%P')
        v = tk.StringVar(value=str(value))
        editor = ttk.Entry(parent, textvariable=v, validate='key', validatecommand=checkWrapper)
        self.vars[key+keyExt] = ChangeDescr(v, editor, False, float)
      elif typ is bool:
        v = tk.StringVar(value=str(value))
        editor = ttk.Checkbutton(parent, text="", variable=v, onvalue='True', offvalue='False')
        self.vars[key+keyExt] = ChangeDescr(v, editor, False, lambda b: str(b).strip().lower() in ("true", "1", "yes"))
      elif typ is str:
        v = tk.StringVar(value=str("" if value is None else value))
        editor = ttk.Entry(parent, textvariable=v)
        self.vars[key+keyExt] = ChangeDescr(v, editor, False, str)
      elif typ is list:
        buf = SerializationStrategy.tostringx(DEFAULT_STRATEGY, value)#(Serializable.serializeAllXML(value, typ))
        editor = tk.Text(parent, height=getHeight(buf))
        editor.insert('1.0', buf)
        self.vars[key+keyExt] = ChangeDescr(None, editor, False, lambda val: SerializationStrategy.fromstringx(DEFAULT_STRATEGY, val))
      elif issubclass(typ, PRObject):
        buf = SerializationStrategy.tostringx(DEFAULT_STRATEGY, value)
        editor = tk.Text(parent, height=getHeight(buf))
        editor.insert('1.0', buf)
        self.vars[key+keyExt] = ChangeDescr(None, editor, False, lambda val: SerializationStrategy.fromstringx(DEFAULT_STRATEGY, val))
      elif issubclass(typ, Serializable):
        buf = SerializationStrategy.tostringx(DEFAULT_STRATEGY, value)
        editor = tk.Text(parent, height=getHeight(buf))
        editor.insert('1.0', buf)
        self.vars[key+keyExt] = ChangeDescr(None, editor, False, lambda val: SerializationStrategy.fromstringx(DEFAULT_STRATEGY, val))
    else:
      logger.error(f'AttributeEditor on key "{key}": Types must be strings or Types, got typ {str(typ)} or type {type(typ).__name__}')

    if editor is None: # type not known, try generic methods
      #check if x==(literal_eval(str(x)) -- we can use that blindly if so.
      try:
        if value == (eval(str(value))):
          v = tk.StringVar(value=str(value))
          editor = ttk.Entry(parent, textvariable=v)
          self.vars[key+keyExt] = ChangeDescr(v, editor, False, eval)
      except:
        pass
    if editor is None: # last ditch, just use an uneditable field with the str() representation
      v = tk.StringVar(value=str(value))
      editor = ttk.Label(parent, textvariable=v, foreground="brown")
      #self.vars[key+keyExt] = ChangeDescr(v, editor, False, str)
      self.vars[key+keyExt] = ChangeDescr(v, editor, False, str)

    return editor

  def makeNewEntry(self, k, v, row, disabled, keyExt, inhType:type|str|None=None):
    '''
    :param k:
    :type k:
    :param v:
    :type v:
    :param row:
    :type row:
    :param disabled:
    :type disabled:
    :param keyExt:
    :type keyExt:
    :param inhType:
    :type inhType: type | str | None
    '''
    shortName, depth = self._labels.get(k, (k, 0))
    if self.treeMode: # left-aligned, indented under its group (lined up with the groups' names, after their triangles)
      label = self.makeLabel(self.editorsListFrame, k, shortName+":", self.cLabel, row, justify=tk.W,
                             padx=(depth*TREE_INDENT + TREE_INDENT, 4), foreground="grey" if disabled else "black")
    else:
      label = self.makeLabel(self.editorsListFrame, k, k+":", self.cLabel, row, foreground="grey" if disabled else "black")
    note = self._noteFor(k, v, keyExt)
    self.addTooltip(label, f"{k}\n\n{note}" if note and shortName != k else (k if shortName != k else note))
    self.makeNoteButton(k, v, row, readonly=disabled or keyExt != "", keyExt=keyExt)
    ed = self.makeEditor(self.editorsListFrame, k, v, self.cEdit, row, disabled or not self.attrs.isValueEditable(k), keyExt, inhType=inhType)
    frame = tk.Frame(self.editorsListFrame)
    frame.grid(column=self.cDel, row=row, sticky=tk.W, padx=0, pady=0)
    if not disabled:
      self.makeButton(frame, k, v, "delete", command=lambda b, k1=k, v1=v, ed1=ed, row=row: self.deleteAttr(k1, v1, ed1, row, b), width=4.2)
    kind = self.makeKind(self.editorsListFrame, k, v.type, self.cKind, row, None, disabled or not self.attrs.isTypeEditable(k), keyExt, inhType=inhType)
    #TODO: isn't this redundant?
    if disabled or not self.attrs.isTypeEditable(k):
      kind.configure(state=tk.DISABLED)
    
  ### GROUPS (see treeOrder()) ##################################################

  def makeGroupHeader(self, path:str, depth:int, row:int) -> tk.Label:
    '''
    The header line for a group of attributes (see *treeOrder()*): a triangle
    and the group's name, indented by its depth. Clicking it collapses or
    expands the group (see *toggleGroup()*).

    :param path: The group's path, eg: "gui/colors".
    :type path: str
    :param depth: How deep the group is in the tree (0 at the top).
    :type depth: int
    :param row: Its row in the grid.
    :type row: int
    :returns: The header's text (the triangle and name).
    :rtype: tk.Label
    '''
    name = path.rsplit(GROUP_SEPARATOR, 1)[-1]
    band = tk.Frame(self.editorsListFrame, background=GROUP_BACKGROUND, cursor="hand2") # (a grey band across the whole line)
    band.grid(column=self.cStatus, row=row, columnspan=self.cspan, sticky=tk.W+tk.E, padx=0, pady=(4, 0))
    header = tk.Label(band, text=f"{TRIANGLE_OPEN} {name}", font=('Helvetica', 14, 'bold'), background=GROUP_BACKGROUND,
                      foreground="black", cursor="hand2")
    header.pack(side=tk.LEFT, padx=(depth*TREE_INDENT + 2, 0), pady=1)
    for w in (band, header):
      w.bind("<Button-1>", lambda _e, p=path: self.toggleGroup(p))
    self.addTooltip(header, f"{path}{GROUP_SEPARATOR}\n\nClick to collapse or expand the group.")
    self._groupHeaders[path] = header
    return header

  def toggleGroup(self, path:str, remember:bool=True) -> None:
    '''
    Collapse the group *path* -- hide all the rows below its header, up to the
    end of the group -- or, if it's collapsed, expand it: show again what it
    hid. (A collapsed subgroup's rows were hidden by the subgroup, so they stay
    hidden until it's expanded too.)

    :param path: The group's path.
    :type path: str
    :param remember: Whether to remember the change for the next editor shown
      (see *collapsedGroups*).
    :type remember: bool
    '''
    header = self._groupHeaders.get(path)
    name = path.rsplit(GROUP_SEPARATOR, 1)[-1]
    if path in self._hiddenWidgets: # expand
      for w in self._hiddenWidgets.pop(path):
        w.grid()
      if header is not None:
        header.config(text=f"{TRIANGLE_OPEN} {name}")
      if remember:
        AttrEditor.collapsedGroups.discard(path)
    else: # collapse
      start, end = self._groupSpans[path]
      hidden:list[tk.Widget] = []
      for r in range(start, end):
        for w in self.editorsListFrame.grid_slaves(row=r):
          w.grid_remove() # (grid() puts it back as it was)
          hidden.append(w)
      self._hiddenWidgets[path] = hidden
      if header is not None:
        header.config(text=f"{TRIANGLE_CLOSED} {name}")
      if remember:
        AttrEditor.collapsedGroups.add(path)

  ### NOTES ######################################################################

  def _noteFor(self, key:str, attr:Attribute, keyExt:str="") -> str:
    '''
    :param key: The attribute's name.
    :type key: str
    :param attr: The attribute shown on the line (its own, or the inherited one).
    :type attr: Attribute
    :param keyExt: "" for the attribute's own line; *INHERIT_KEY_EXT* for its inherited one.
    :type keyExt: str
    :returns: The note to show for the line: as edited, if it has been; else the
      attribute's own note, or failing that the one it inherits.
    :rtype: str
    '''
    if keyExt == "" and key in self.noteEdits:
      return self.noteEdits[key]
    note = getattr(attr, "note", None)
    if not note and keyExt == "" and isinstance(self.attrs, AttributedObject):
      inh = self.attrs.getInhAttr(key)
      note = None if inh is None else inh.note
    return note or ""

  def makeNoteButton(self, key:str, attr:Attribute, row:int, readonly:bool, keyExt:str="") -> ttk.Button:
    '''
    The button in the NOTE column, which shows the note in a pop-up (see
    *editNote()*): "note" if there is one, "+" if not. Its tooltip shows the note.

    :param key: The attribute's name.
    :type key: str
    :param attr: The attribute shown on the line.
    :type attr: Attribute
    :param row: The line's row in the grid.
    :type row: int
    :param readonly: Whether the note can only be read (eg: an inherited one).
    :type readonly: bool
    :param keyExt: "" for the attribute's own line; *INHERIT_KEY_EXT* for its inherited one.
    :type keyExt: str
    :returns: The button.
    :rtype: ttk.Button
    '''
    note = self._noteFor(key, attr, keyExt)
    button = ttk.Button(self.editorsListFrame, text="note" if note else ("" if readonly else "+"), width=4, padding=-15)
    button.config(command=lambda: self.editNote(key, attr, button, readonly, keyExt))
    if readonly and not note:
      button.state(["disabled"])
    button.grid(column=self.cNote, row=row, padx=2, pady=0)
    font = tkfont.nametofont("TkFixedFont")
    CreateToolTip(button, lambda: self._noteFor(key, attr, keyExt) or "(no note)", background="yellow", wrapLength=720, font=font)
    return button

  def editNote(self, key:str, attr:Attribute, button:ttk.Button, readonly:bool, keyExt:str="") -> None:
    '''
    Show the attribute's note in a small pop-up text editor -- or, if
    *readonly*, viewer. OK keeps the edited note (it's saved with the other
    changes: see *save()*).

    :param key: The attribute's name.
    :type key: str
    :param attr: The attribute shown on the line.
    :type attr: Attribute
    :param button: The line's note button (its text is updated).
    :type button: ttk.Button
    :param readonly: Whether the note can only be read.
    :type readonly: bool
    :param keyExt: "" for the attribute's own line; *INHERIT_KEY_EXT* for its inherited one.
    :type keyExt: str
    '''
    current = self._noteFor(key, attr, keyExt)
    win = tk.Toplevel(self)
    win.title(f'Note: {key}' + (" (inherited)" if keyExt else ""))
    win.transient(self)
    win.columnconfigure(0, weight=1)
    win.rowconfigure(0, weight=1)
    text = tk.Text(win, width=64, height=10, wrap="word", font=tkfont.nametofont("TkFixedFont"), undo=True)
    text.grid(column=0, row=0, columnspan=2, sticky="NSEW", padx=6, pady=6)
    text.insert("1.0", current)
    if readonly:
      text.config(state=tk.DISABLED)
    def close(keep:bool) -> None:
      if keep:
        edited = text.get("1.0", "end-1c").rstrip()
        if edited != current:
          self.noteEdits[key] = edited
          button.config(text="note" if edited else "+")
      win.grab_release()
      win.destroy()
    if readonly:
      ttk.Button(win, text="Close", command=lambda: close(False)).grid(column=1, row=1, sticky=tk.E, padx=6, pady=6)
    else:
      ttk.Button(win, text="Cancel", command=lambda: close(False)).grid(column=0, row=1, sticky=tk.W, padx=6, pady=6)
      ttk.Button(win, text="OK", command=lambda: close(True)).grid(column=1, row=1, sticky=tk.E, padx=6, pady=6)
    win.protocol("WM_DELETE_WINDOW", lambda: close(False))
    # (this editor holds the grab: lend it to the pop-up, then take it back)
    try:
      self.grab_release()
      win.wait_visibility()
      win.grab_set()
    except tk.TclError:
      pass
    text.focus_set()
    self.wait_window(win)
    try:
      self.grab_set_global()
    except tk.TclError:
      pass

  def makeTitle(self, col:int, text:str, helpText:str, row:int, **kwargs):
    # Note: background= option doesn't work on aqua
    '''
    :param col:
    :type col: int
    :param text:
    :type text: str
    :param helpText:
    :type helpText: str
    :param row:
    :type row: int
    :param kwargs:
    :type kwargs:
    '''
    label = ttk.Label(self.editorsListFrame, text=text, font=('Helvetica', 12, 'bold'), relief=tk.GROOVE, anchor=tk.CENTER, background="blue", **kwargs)
    label.grid_configure(column=col, row=row, sticky=tk.W+tk.E)
    self.addTooltip(label, helpText)
    
  def addTooltip(self, widget:Widget, helpText:str):
    '''
    :param widget:
    :type widget: Widget
    :param helpText:
    :type helpText: str
    '''
    if helpText is None or helpText == "":
      return
    # A fixed-width font, so notes that line things up with spaces display as
    # written; wide enough for the longest line (up to a limit, then wrapped).
    font = tkfont.nametofont("TkFixedFont")
    width = min(max(font.measure(line) for line in helpText.split("\n")) + 8, 720)
    CreateToolTip(widget, helpText, background="yellow", wrapLength=width, font=font)

  def _applyHiddenColumns(self) -> None:
    '''
    Take the widgets in the hidden columns (see *hideColumns*) off the grid --
    those made since last time too (eg: a new attribute's row). Only widgets
    in just that column: not ones spanning it, like the separators and the
    groups' header bands.
    '''
    for name in self.hideColumns:
      column = getattr(self, self.HIDEABLE_COLUMNS[name], None)
      if column is None: # (eg: "qualifiers" in a plain AttrEditor)
        continue
      for w in self.editorsListFrame.grid_slaves(column=column):
        info = w.grid_info()
        if int(info.get("column", -1)) == column and int(info.get("columnspan", 1)) == 1:
          w.grid_remove()

  def makeHeader(self, row, **kwargs):
    '''
    :param row:
    :type row:
    :param kwargs:
    :type kwargs:
    '''
    self.makeTitle(self.cLabel, "ATTR NAME", f'The name of the Attribute (NOT the value).', row, **kwargs)
    self.makeTitle(self.cEdit, "VALUE", f'The value of the Attribute.', row, **kwargs)
    self.makeTitle(self.cDel, "ACTIONS", f'The actions you can perform on the Attribute.', row, **kwargs)
    self.makeTitle(self.cKind, "TYPE", f'The type of the value.', row, **kwargs)
    self.makeTitle(self.cNote, "NOTE", 'The note describing the Attribute (shown as its name\'s tooltip): click to see or edit it.', row, **kwargs)
    
  def makeEditor(self, parent, key, item, column, row, disabled, keyExt, inhType:str|type|None=None):
    '''
    :param parent:
    :type parent:
    :param key:
    :type key:
    :param item:
    :type item:
    :param column:
    :type column:
    :param row:
    :type row:
    :param disabled:
    :type disabled:
    :param keyExt:
    :type keyExt:
    :param inhType:
    :type inhType: str | type | None
    :returns:
    :rtype:
    '''
    value = self.displayValues[key] if keyExt == "" and key in self.displayValues else item.value
    editor = self.getEditorForType(parent, key, item.type, value, keyExt, inhType=inhType)
    editor.grid(column=column, row=row, sticky='EW', padx=0, pady=0)
    if disabled:
      self.conf(editor, state= "disabled")#, foreground="blue")
      if not isinstance(editor, ColorEditor): # This would blank out a ColorEditor's color swatch
        self.conf(editor, foreground="gray", background="gray95")
    return editor

  def makeButton(self, parent, key, item, text, command=None, **kwargs):#, width=4):
    '''
    Unlike the other "make*() methods, this one takes a parent that is a frame that
    will be used as a *pack()* frame as opposed to the others that take a parent
    that's a *grid()* frame.

    :param parent:
    :type parent:
    :param key:
    :type key:
    :param item:
    :type item:
    :param text:
    :type text:
    :param command:
    :type command:
    :param kwargs:
    :type kwargs:
    :returns:
    :rtype:
    '''
    if item.type == 'unknown':
      return
    button = ttk.Button(parent, text=text, padding=-15, **kwargs)
    button.pack(side=tk.LEFT, anchor=tk.W, padx=0, pady=0)
    if command: 
      button.config(command=lambda b=button: command(b))
    return button

  def makeLabel(self, parent, key, text, column, row, justify=tk.E, padx:int|tuple[int,int]=0, **kwargs):
    '''
    :param parent:
    :type parent:
    :param key:
    :type key:
    :param text:
    :type text:
    :param column:
    :type column:
    :param row:
    :type row:
    :param justify:
    :type justify:
    :param padx: Space to the left and right of it (eg: an indent).
    :type padx: int | tuple[int, int]
    :param kwargs:
    :type kwargs:
    :returns:
    :rtype:
    '''
    font = ('Helvetica', 14, 'bold italic') if key in SYS_ATTRIBUTES else ('Helvetica', 14, 'normal')
    label = ttk.Label(parent, text=text, font=font, **kwargs)
    label.grid(column=column, row=row, sticky=justify, ipadx=0, padx=padx, pady=0)
    return label

  def makeKind(self, parent, key, typ:Union[type,str], column, row, command, disabled, keyExt, inhType:str|type|None=None, **kwargs):
    #typeDisabled = disabled
    '''
    :param parent:
    :type parent:
    :param key:
    :type key:
    :param typ:
    :type typ: Union[type, str]
    :param column:
    :type column:
    :param row:
    :type row:
    :param command:
    :type command:
    :param disabled:
    :type disabled:
    :param keyExt:
    :type keyExt:
    :param inhType:
    :type inhType: str | type | None
    :param kwargs:
    :type kwargs:
    :returns:
    :rtype:
    '''
    command = None    
    if not disabled:
      command = command=lambda b, parent=self, key=key, typ=typ, column=self.cKind, row=row: \
                                self.editType(b, parent, key, typ, column, row)
    # else:
    #   typeDisabled = True      
    font = ('Helvetica', 8, 'bold') if typ=="unknown" else ('Helvetica', 8, 'normal')
    tname = getFullClassName(typ) if isinstance(typ, type) else str(typ)
    if tname == "None": 
      tname = inhType.__name__ if isinstance(inhType, type) else str(inhType) 
      if inhType is not None:
        disabled = True
    if disabled:
      label = ttk.Label(parent, text=tname, width=KIND_WIDTH, foreground="grey50", **kwargs)
    else:
      label = ttk.Button(parent, text=tname, padding=-15, width=KIND_WIDTH, **kwargs)
      if command is not None:
        label.config(command=lambda b=label: command(b))
    label.grid(column=column, row=row, padx=0, pady=0)#, sticky="sw")
    self.vars[key+keyExt].typeLabel = label
    return label
    
  def setStatus(self, parent, key, text, column, row, command=None, button=None, **kwargs):
    '''
    :param parent:
    :type parent:
    :param key:
    :type key:
    :param text:
    :type text:
    :param column:
    :type column:
    :param row:
    :type row:
    :param command:
    :type command:
    :param button:
    :type button:
    :param kwargs:
    :type kwargs:
    '''
    if button is not None:
      button.grid(column=column, row=row, padx=0, pady=0)#, sticky="sw")
    else:
      label = ttk.Label(parent, text=text, **kwargs)
      label.grid(column=column, row=row, padx=0, pady=0)#, sticky="sw")
      
    
  def setMessage(self, text, hideButton=True, **kwargs):
    '''
    :param text:
    :type text:
    :param hideButton:
    :type hideButton: bool
    :param kwargs:
    :type kwargs:
    '''
    self.messageFrame = tk.Frame(self)
    self.messageFrame.grid(column=0, row=self.rMessage, columnspan=2, sticky=tk.E+tk.W)
    self.messageFrame.columnconfigure(0, weight=1)
    self.messageFrame.columnconfigure(1, weight=0)
    self.messageWidget = tk.Text(self.messageFrame, height=1+text.count('\n'))
    self.messageWidget.insert('1.0', text)
    self.messageWidget.configure(state=tk.DISABLED, **kwargs)
    self.messageWidget.grid(column=0, row=0, sticky=tk.E+tk.W)
    if hideButton:
      tk.Button(self.messageFrame, bitmap="error", command=self.messageFrame.destroy)\
        .grid(column=1, row=0, sticky=tk.E+tk.W)
    
  def clearMessage(self, *args): # args are ignored: it's only here so we can call this an tk event.
    '''
    :param args:
    :type args:
    '''
    try:
      self.messageFrame.destroy()
    except:
      pass
    try:
      self.askWidget.destroy()
    except:
      pass
  
  def ask(self, question:str, handler:Callable[[tk.Event, str], Any], default=None, **kwargs):
    '''
    Asks a question and waits for an answer input within the window. The user
    is expected to fill in the answer and hit <Return> (or <Tab>) to answer.  If the focus
    is shifted to another widget, the question is removed (as if a "cancel"
    button was pressed.
    
    If the user hits return, *self.answer* will be called, and the user's input
    can be obtained using *self.var.get()*
    
    :param question: The text of the question.
    :param handler: A *Callable* taking an event argument and a string argument containing the answer
    :param kwargs: A dictionary of legal arguments to *ttk.Text()* which controls
        the attributes of the question Text widget.
    :param default:
    :type default:
    '''
    self.setMessage(question, hideButton=False, **kwargs)
    # Doesn't check anything, just clears the question (like a "cancel" button)
    # when the ask dialog looses focus
    checkWrapper = (self.winfo_toplevel().register(self.clearMessage), '%P')
    _var = tk.StringVar()
    if default is not None:
      if isinstance(default, type): default = default.__name__
      _var.set(str(default))
    self.askWidget = ttk.Entry(self, textvariable=_var, validate='focusout', validatecommand=checkWrapper)
    self.askWidget.grid(row=self.rEnter, column=0, columnspan=2, sticky=tk.W+tk.E)
    if default is not None:
      self.askWidget.icursor(len(default))
    def h(event):
      handler(event, _var.get())
      #self.clearMessage()
    def answered(event): # (and no further: eg: <Tab> doesn't move the focus on as well)
      h(event)
      return "break"
    self.askWidget.bind('<Return>', answered)
    self.askWidget.bind('<Tab>', answered) # (the same: eg: the new key's typed, on to its value)
    self.askWidget.focus()
      
  def checkInt(self, newval):
    '''
    :param newval:
    :type newval:
    :returns:
    :rtype:
    '''
    return re.match(r'^[0-9]*$', newval) is not None and len(newval) <= 20

  def checkFloat(self, newval):
    '''
    :param newval:
    :type newval:
    :returns:
    :rtype:
    '''
    return re.match(r'^[0-9]*(\.[0-9]*)?$', newval) is not None and len(newval) <= 20

  # def colorChooser(self, tkVar, button):
  #   # askcolor() returns (rgb, hex)
  #   color = tkVar.get()
  #   if color is None:
  #     color = "black"
  #   if color == "": # colorchooser() can't handle "" (transparent)
  #     color = "gray"
  #   color = colorchooser.askcolor(initialcolor=color, parent=self)
  #   if color is not None:
  #     color = color[1]
  #     tkVar.set(color)
  #     button.config(highlightbackground=color, text=str(color))
    
  def conf(self, tkObj, **kwargs):
    '''
    Configure the tk widget *tkObj* with each of the key/value pairs in *kwargs*
    one at a time catching printing any exceptions but otherwise ignoring failures.

    :param tkObj:
    :type tkObj:
    :param kwargs:
    :type kwargs:
    '''
    for k,v in kwargs.items():
      if isinstance(tkObj, tk.Button) and k=="state" and v == "!disabled":  
        v = "normal"
      d = dict()
      d[k] = v
      try: 
        tkObj.config(**d)
      except: 
        if k not in ["foreground", "background", "bg", "fg"]:
          logger.warning(f'AttrEditor.show.conf(): Couldn\'t set attr "{k}" to "{v}" on tk type {type(tkObj).__name__}')

  # def isTypeEditable(self, key:str) -> bool:
  #   '''
  #   Returns *True* if the key is an editable. ie: The editor was not declared
  #   read only and the *AttributedObject* is editable on the *key* parameter.
  #   '''
  #   return  self.editable \
  #           and self.attrs.isTypeEditable(key) \
  #           and self.attrs.getType(key, asString=True) != "list"
                
class HierarchicalAttrEditor(AttrEditor):
  
  '''
  An *AttrEditor* for an *AttributedObject* with supertypes: it shows each
  attribute's inherited values (greyed, above its own) and its inheritance
  restrictions, which can be edited too.
  '''
  def __init__(self, parent, attrs:AttributedObject, title="Attribute Editor", disabled=False,
               displayValues:Optional[dict[str,Any]]=None, hideColumns:Iterable[str]=(),
               listItemMakers:Optional[dict[str, ItemMaker]]=None):
    '''
    :param parent:
    :type parent:
    :param attrs:
    :type attrs: AttributedObject
    :param title:
    :type title: str
    :param disabled:
    :type disabled: bool
    :param displayValues:
    :type displayValues: Optional[dict[str, Any]]
    :param hideColumns: As for *AttrEditor*.
    :type hideColumns: Iterable[str]
    :param listItemMakers: As for *AttrEditor*.
    :type listItemMakers: Optional[dict[str, ItemMaker]]
    '''
    self.assertedKeys:set[str] = set()
    "The keys of the inferred attributes whose \"assert\" button was pressed (see *assertAttr()*)."
    super().__init__(parent, attrs, title=title, disabled=disabled, displayValues=displayValues, hideColumns=hideColumns, listItemMakers=listItemMakers)
    
    # "constants" for the columns in the Editors grid
    self.rowsPerEntry = 3 # from 1
    self.EntryOffset = 1 # from 0
    self.cStatus = 0
    self.cLabel = 1
    self.cEdit = 2
    self.cKind = 3
    self.cQuals = 4
    self.cNote = 5
    self.cDel = 6
    self.cspan = 7
    
    self.iEntryOffset = 0
    self.sepOffset = 2
  
  @override
  def makeNewEntry(self, k, v, row, disabled, keyExt, inhType:str|type|None=None):
    '''
    :param k:
    :type k:
    :param v:
    :type v:
    :param row:
    :type row:
    :param disabled:
    :type disabled:
    :param keyExt:
    :type keyExt:
    :param inhType:
    :type inhType: str | type | None
    '''
    localRec = self.attrs.getLocalAttr(k)
    inhRec = self.attrs.getInhAttr(k)
    if self.editKey == k and localRec == None:
      self.attrs.setAttr(k, Attribute(None, None if inhRec is None else inhRec.type, None if inhRec is None else inhRec.restriction))
      localRec = self.attrs.getLocalAttr(k)
    if localRec is not None: # (an inherited note is shown for it -- see _noteFor() -- but not copied into it)
      inferred = getattr(localRec, "inferred", False) # (concluded, not given: greyed out, with an "assert" button -- see Attribute.inferred)
      super().makeNewEntry(k, localRec, row+self.EntryOffset, disabled or inferred, keyExt="", inhType=None if inhRec is None else inhRec.type)
      #super().makeNewEntry(k, v, row+self.EntryOffset, disabled, keyExt="", inhType=None if inhRec is None else inhRec.type)
      #assert localRec.restriction is not None
      self.makeQuals(self.editorsListFrame, k, localRec.restriction, self.cQuals, row+self.EntryOffset, disabled=disabled or inferred or not self.attrs.isQualifierEditable(k), keyExt="")
      if inferred:
        self.setStatus(self.editorsListFrame, k, "I", self.cStatus, row+self.EntryOffset, foreground="gray")
        if not disabled:
          frame = tk.Frame(self.editorsListFrame)
          frame.grid(column=self.cDel, row=row+self.EntryOffset, sticky=tk.E+tk.W, padx=0, pady=0)
          self.makeButton(frame, k, localRec, "assert", command=lambda b, k=k: self.assertAttr(k, b))
    if inhRec is not None:
      super().makeNewEntry(k, inhRec, row+self.iEntryOffset, disabled=True, keyExt=INHERIT_KEY_EXT)
      assert inhRec.restriction is not None
      self.makeQuals(self.editorsListFrame, k, inhRec.restriction, self.cQuals, row+self.iEntryOffset, disabled=True, keyExt=INHERIT_KEY_EXT)
      # self.makeLabel(self.editorsListFrame, k, k+":",        self.cLabel, row+self.iEntryOffset, foreground="gray")
      # self.makeLabel(self.editorsListFrame, k, inhRec.value, self.cEdit,  row+self.iEntryOffset, justify=tk.W, foreground="gray")
      # self.makeKind (self.editorsListFrame, k, inhRec.type,   self.cKind,  row+self.iEntryOffset, foreground="gray")
      self.setStatus(self.editorsListFrame, k, DOWN_ARROW,    self.cStatus,row+self.iEntryOffset, foreground="gray")
      if localRec is None:
        # action frame
        frame = tk.Frame(self.editorsListFrame)
        frame.grid(column=self.cDel, row=row+self.iEntryOffset, sticky=tk.E+tk.W, padx=0, pady=0)
        #attr =  Attribute(k, inhRec.type, inhRec.value, None)
        #self.attrs.setRecord(attr)
        if not disabled:
          self.makeButton(frame, k, inhRec, "override", \
                          command=lambda b, k=k, inhRec=inhRec, r=row, slf=self: (slf.makeNewEntry(k, slf.attrs.__setitem__(k, inhRec.value), r, disabled=False, keyExt="", inhType=inhRec.type), b.destroy(), slf._applyHiddenColumns()))
    ttk.Separator(self.editorsListFrame, orient=tk.HORIZONTAL) \
        .grid(column=0, row=row+self.sepOffset, columnspan=self.cspan, sticky=tk.W+tk.E, padx=0, pady=2)
   
  def assertAttr(self, key:str, button:ttk.Button) -> None:
    '''
    The "assert" button of an inferred attribute (see *Attribute.inferred*) was
    pressed: saving makes it an ordinary (given) attribute, with the same value
    (see *save()*).

    :param key: The attribute's key.
    :type key: str
    :param button: The button pressed.
    :type button: ttk.Button
    '''
    self.assertedKeys.add(key)
    button.configure(text="asserted", state=tk.DISABLED)

  @override
  def makeHeader(self, row, **kwargs):
    '''
    :param row:
    :type row:
    :param kwargs:
    :type kwargs:
    '''
    self.makeTitle(self.cStatus, "S", f'Status:\n  {DOWN_ARROW}: inherited record (not editable)\n  I: inferred (concluded, not given: "assert" makes it given)', row, **kwargs)
    AttrEditor.makeHeader(self, row, **kwargs)
    self.makeTitle(self.cQuals, "QUALIFIERS", DOC_QUALIFIER, row, **kwargs)
    
  def makeQuals(self, parent, key, quals:Restriction, column, row, disabled, keyExt, **kwargs):
    '''
    :param parent:
    :type parent:
    :param key:
    :type key:
    :param quals:
    :type quals: Restriction
    :param column:
    :type column:
    :param row:
    :type row:
    :param disabled:
    :type disabled:
    :param keyExt:
    :type keyExt:
    :param kwargs:
    :type kwargs:
    '''
    if quals is None:
      inhRec = self.attrs.getInhAttr(key)
      if inhRec is not None:
        quals = inhRec.restriction
    if quals is None:
      quals = VAR_DEFAULTED
      
    mb = tk.Menubutton(parent, text="=", padx=-15, **kwargs)
    # def postLabelText() -> str:
    #   self.vars[key+keyExt].
    #   label = ("+f" if self.vars[key+keyExt].qualFinal.get()               else "") + \
    #         ("+if" if self.vars[key+keyExt].qualInstanceFinal.get()        else "") + \
    #         ("+vni" if self.vars[key+keyExt].qualValueNotInheritable.get() else "")
    #   if len(label) == 0:
    #     label = "-"
    #   mb.config(text=label)
    #   return label
    menu = tk.Menu(mb)
    state = tk.DISABLED if disabled else tk.NORMAL
    # self.vars[key+keyExt].qualFinal = tk.BooleanVar(value=bool(quals&AttributeFlags.FINAL))
    # menu.add_checkbutton(label="final", variable=self.vars[key+keyExt].qualFinal, command=postLabelText, state=state)
    # self.vars[key+keyExt].qualInstanceFinal = tk.BooleanVar(value=bool(quals&AttributeFlags.INSTANCE_FINAL))
    # menu.add_checkbutton(label="instance final", variable=self.vars[key+keyExt].qualInstanceFinal, command=postLabelText, state=state)
    # self.vars[key+keyExt].qualValueNotInheritable = tk.BooleanVar(value=bool(quals&AttributeFlags.VALUE_NOT_INHERITABLE))
    # menu.add_checkbutton(label="value not inheritable", variable=self.vars[key+keyExt].qualValueNotInheritable, command=postLabelText, state=state)
    self.vars[key+keyExt].qual = quals
    def updateIt(k, restriction) -> None:
      mb.config(text=k)
      self.vars[key+keyExt].qual = restriction
    k:str
    v:Restriction
    for k,v in attribute.RESTRICTION_TYPES.items():
      menu.add_command(label=k, command=lambda k=k, v=v: updateIt(k,v)) #type: ignore[misc]
    mb.config(menu=menu, text=quals.tostring())#=postLabelText())
    mb.grid(column=column, row=row, sticky=tk.E)
    if disabled:
      mb.config(foreground="gray")
    
  @override
  def hasChanged(self, k:str)->bool:
    '''
    :param k:
    :type k: str
    :returns:
    :rtype: bool
    '''
    if AttrEditor.hasChanged(self, k):
      return True
    origAttr:Attribute|None = self.attrs.getLocalAttr(k) if k in list(strdict.keys(self.attrs)) else None
    if origAttr is None:
      return True
    # origQual:AttributeFlags = origAttr.restriction
    # if origQual is None:
    #   origQual = AttributeFlags.NIL
    v = self.vars[k]
    # return  v.qualFinal is not None and v.qualFinal.get() != origAttr.isFinal() or \
    #         v.qualInstanceFinal is not None and v.qualInstanceFinal.get() != origAttr.isInstanceFinal() or \
    #         v.qualValueNotInherited is not None and v.qualValueNotInherited.get() != origAttr.isValueNotInheritable()
    return self._restrictionChanged(k, origAttr)

  def _effectiveRestriction(self, k:str, origAttr:Attribute|None) -> Restriction|None:
    '''
    :returns: The restriction the qualifier menu started with: the local one,
      or failing that the inherited one (see *makeQuals()*).
    :param k:
    :type k: str
    :param origAttr:
    :type origAttr: Attribute | None
    '''
    if origAttr is not None and origAttr.restriction is not None:
      return origAttr.restriction
    inhRec = self.attrs.getInhAttr(k)
    return None if inhRec is None else inhRec.restriction

  def _restrictionChanged(self, k:str, origAttr:Attribute|None) -> bool:
    '''
    :param k:
    :type k: str
    :param origAttr:
    :type origAttr: Attribute | None
    :returns:
    :rtype: bool
    '''
    qual = self.vars[k].qual
    return qual is not None and qual != self._effectiveRestriction(k, origAttr)
    
  @override
  def _saveKey(self, k:str, origAttr:Attribute):
    '''
    :param k:
    :type k: str
    :param origAttr:
    :type origAttr: Attribute
    '''
    AttrEditor._saveKey(self, k, origAttr) # drops the restriction on inherited overrides
    assert self.updatedKeys is not None
    if self._restrictionChanged(k, origAttr):
      self.updatedKeys[k].restriction = self.vars[k].qual
              # AttributeFlags(
              # (AttributeFlags.FINAL if v.qualFinal is not None and v.qualFinal.get() else AttributeFlags.NIL) |
              # (AttributeFlags.INSTANCE_FINAL if v.qualInstanceFinal is not None and v.qualInstanceFinal.get() else AttributeFlags.NIL) |
              # (AttributeFlags.VALUE_NOT_INHERITABLE if v.qualValueNotInherited is not None and v.qualValueNotInheritable.get() else AttributeFlags.NIL))

if __name__ == "__main__":
  class MyAttributedObject(AttributedObject):
    @override
    def getSupers(self): return []
    @override
    def isIndividual(self)->bool: return False
  attrs = MyAttributedObject()
  attrs.setAttr("int", Attribute(6, int, VAR_DEFAULTED))
  attrs.setAttr("float", Attribute(3.14, float, VAR_DEFAULTED))
  attrs.setAttr("colors", Attribute("blue", "choices[red,blue,green]", VAR_DEFAULTED))
  
  root = tk.Tk()
  #op2 = tk.Toplevel(root)
  def onClosing():
    root.destroy()
  root.protocol("WM_DELETE_WINDOW", onClosing)
  root.createcommand('::tk::mac::Quit', onClosing)
  def edit(parent, attrs):
    '''
    :param parent:
    :type parent:
    :param attrs:
    :type attrs:
    '''
    command = getEditedAttrsCommandObj(parent, attrs)
    if command is None:
      print("cancelled")
    else:
      command.do()
      print(repr(attrs))
  # but = tk.Button(root, text="show edit window", command=lambda parent=root, attrs=attrs: edit(parent, attrs))
  # but.pack()
  edit(root, attrs)
  root.mainloop()
  


def _convertValue(typ:str, text:str) -> Any:
  '''
  :returns: *text* (an editor's value) as a value of the type named *typ*, or
    NOVALUE if it can't be one. Text types take any text; "" isn't a number or
    boolean.
  :param typ:
  :type typ: str
  :param text:
  :type text: str
  '''
  t = TYPE_EQUIVALENTS.get(typ) if typ in TYPE_EQUIVALENTS else None
  if t is str:
    return text
  if typ.startswith("choices[") and typ.endswith("]"):
    choices = [c.strip() for c in typ[8:-1].split(",")]
    return text if text in choices else NOVALUE
  try:
    if t is bool:
      return {"true": True, "t": True, "yes": True, "y": True, "1": True,
              "false": False, "f": False, "no": False, "n": False, "0": False}[text.lower()]
    if t is int:
      return int(text)
    if t is float:
      return float(text)
  except (KeyError, ValueError):
    return NOVALUE
  return NOVALUE

def _defaultValue(typ:str) -> Any:
  '''
  A reasonable starting value for the type named *typ*.

  :param typ:
  :type typ: str
  :returns:
  :rtype: Any
  '''
  if typ.startswith("choices[") and typ.endswith("]"):
    return typ[8:-1].split(",")[0].strip()
  t = TYPE_EQUIVALENTS.get(typ) if typ in TYPE_EQUIVALENTS else None
  return {bool: False, int: 0, float: 0.0, str: "", list: []}.get(t, None) if isinstance(t, type) else None
