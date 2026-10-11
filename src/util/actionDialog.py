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
A general-purpose popup dialog (*ActionDialog*) that renders a small,
dependency-free subset of HTML -- bold/italic/underline, line breaks, and
``<a id="...">`` action links -- inside a *tk.Text* widget, and invokes a
caller-supplied callback when an action link is clicked.
Motivating use case: a validation-error popup (eg: for *decorators.py*'s
error tag) that lists an object's errors, one per line, each with inline
"Fix" / "Delete" / "Ignore" links -- without needing a full HTML rendering
dependency (eg: *tkinterweb*) or a hand-rolled tag/click-binding scheme
every time such a popup is needed.

Created on Sep 18, 2026

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from html.parser import HTMLParser
from typing import Callable, Optional
from util.utils import ownDialog

ActionCallback = Callable[[], None]
'A zero-argument callback invoked when an action link is clicked.'

_STYLE_TAGS = {"b": "bold", "strong": "bold", "i": "italic", "em": "italic", "u": "underline"}
'Maps the small subset of supported inline HTML tags to the *tk.Text* tag name that renders them.'


class _RichTextParser(HTMLParser):
  '''
  Parses the small HTML subset *ActionDialog* understands -- ``<b>``/
  ``<strong>``, ``<i>``/``<em>``, ``<u>``, ``<br>``, ``<ol>``/``<ul>``/
  ``<li>``, plain text, and ``<a id="...">label</a>`` action links -- into a
  flat list of *(text, styleTags, actionId)* runs.

  Anything outside that subset (unknown tags, attributes other than *id* on
  ``<a>``) is silently ignored rather than raising: this is meant for small,
  hand-written strings composed by the caller, not for rendering arbitrary
  or untrusted HTML documents.
  '''

  def __init__(self) -> None:
    super().__init__(convert_charrefs=True)
    self.runs:list[tuple[str, tuple[str, ...], Optional[str]]] = []
    'Accumulated *(text, styleTags, actionId)* runs, in document order.'
    self._styleStack:list[str] = []
    self._linkId:Optional[str] = None
    self._listStack:list[dict[str, "int|str"]] = []
    'One entry per currently-open <ol>/<ul>, innermost last: {"kind": "ol"|"ul", "index": int}.'
    self._atLineStart:bool = True
    'Whether the run most recently emitted ended with a newline (or nothing has been emitted yet).'

  def _emit(self, text:str, actionId:Optional[str] = None) -> None:
    '''
    :param text:
    :type text: str
    :param actionId:
    :type actionId: Optional[str]
    '''
    if text == "":
      return
    self.runs.append((text, tuple(self._styleStack), actionId))
    self._atLineStart = text.endswith("\n")

  def handle_starttag(self, tag:str, attrs:list[tuple[str, Optional[str]]]) -> None:
    '''
    :param tag:
    :type tag: str
    :param attrs:
    :type attrs: list[tuple[str, Optional[str]]]
    '''
    if tag in _STYLE_TAGS:
      self._styleStack.append(_STYLE_TAGS[tag])
    elif tag == "br":
      self._emit("\n")
    elif tag == "a":
      self._linkId = dict(attrs).get("id")
    elif tag in ("ol", "ul"):
      self._listStack.append({"kind": tag, "index": 0})
    elif tag == "li":
      if not self._atLineStart:
        self._emit("\n")
      if self._listStack and self._listStack[-1]["kind"] == "ol":
        self._listStack[-1]["index"] += 1 # type: ignore[operator]
        self._emit(f'{self._listStack[-1]["index"]}. ')
      else:
        self._emit("• ") # a <li> outside any <ol>/<ul> still gets a bullet

  def handle_endtag(self, tag:str) -> None:
    '''
    :param tag:
    :type tag: str
    '''
    if tag in _STYLE_TAGS:
      styleName = _STYLE_TAGS[tag]
      if styleName in self._styleStack:
        self._styleStack.remove(styleName)
    elif tag == "a":
      self._linkId = None
    elif tag in ("ol", "ul"):
      if self._listStack:
        self._listStack.pop()
      if not self._atLineStart: # make sure whatever follows the list starts on its own line
        self._emit("\n")

  def handle_data(self, data:str) -> None:
    '''
    :param data:
    :type data: str
    '''
    self._emit(data, actionId=self._linkId)


class ActionDialog(tk.Toplevel):
  '''
  A general-purpose popup dialog that renders a small subset of HTML (bold,
  italic, underline, line breaks, ordered/unordered lists, and
  ``<a id="...">`` action links) and invokes a caller-supplied callback when
  an action link is clicked.

  Typical use -- eg: from *decorators.py*'s error-tag popup -- is to build
  one *html* string per object with an ``<li>`` per validation error and a
  Fix/Ignore/Delete action link at the end of each item, and a matching
  *actions* dict mapping each link's id to the handler that should run when
  it's clicked. ``<li>`` items need no ``<br>`` between them -- each one
  starts its own line automatically, numbered if inside an ``<ol>`` or
  bulleted otherwise::

    ActionDialog(parent, "Validation errors",
      "<b>2 errors on 'Foo':</b>"
      "<ol>"
      "<li>Missing type &#8212; <a id='fix0'>Fix</a> <a id='ignore0'>Ignore</a></li>"
      "<li>Broken link &#8212; <a id='fix1'>Fix</a> <a id='delete1'>Delete</a></li>"
      "</ol>",
      actions={
        "fix0": lambda: fixMissingType(obj),
        "ignore0": lambda: ignoreError(obj, 0),
        "fix1": lambda: fixBrokenLink(obj),
        "delete1": lambda: deleteError(obj, 1),
      },
      closeOnAction=False)  # stay open so the remaining errors can still be acted on

  :param parent: The parent widget this dialog is transient for.
  :type parent: tk.Misc
  :param title: The dialog's window title.
  :type title: str
  :param html: The content, in the small HTML subset *_RichTextParser*
    understands (``<b>``, ``<strong>``, ``<i>``, ``<em>``, ``<u>``, ``<br>``,
    ``<ol>``, ``<ul>``, ``<li>``, and ``<a id="...">``).
  :type html: str
  :param actions: [default: None] Maps each ``<a id="...">`` link's id to the
    zero-argument callback to invoke when it's clicked. A link whose id has
    no entry here is still rendered (as a link) but is inert when clicked.
  :type actions: Optional[dict[str, ActionCallback]]
  :param closeOnAction: [default: True] If True, clicking *any* action link
    closes the dialog immediately after running its callback. Pass False for
    a dialog meant to stay open across several actions -- eg: fixing one
    error in a list and leaving the rest visible to act on next.
  :type closeOnAction: bool
  :param width: [default: 60] The text area's width, in characters.
  :type width: int
  :param maxHeight: [default: 25] The text area's height is sized to fit its
    content up to this many lines, then scrolls.
  :type maxHeight: int
  :rtype: None
  '''

  def __init__(self, parent:tk.Wm, title:str, html:str,
               actions:Optional[dict[str, ActionCallback]] = None, *,
               closeOnAction:bool = True, width:int = 80, maxHeight:int = 40) -> None:
    '''
    :param parent:
    :type parent: tk.Wm
    :param title:
    :type title: str
    :param html:
    :type html: str
    :param actions:
    :type actions: Optional[dict[str, ActionCallback]]
    :param closeOnAction:
    :type closeOnAction: bool
    :param width:
    :type width: int
    :param maxHeight:
    :type maxHeight: int
    '''
    super().__init__(parent) # type: ignore[arg-type]
    ownDialog(self, parent) # (over its parent's window, not full screen: see ownDialog())
    self.geometry("600x300")
    self.title(title)
    self._actions:dict[str, ActionCallback] = actions or {}
    self._closeOnAction:bool = closeOnAction
    self._linkTagCount:int = 0

    container = ttk.Frame(self)
    container.pack(fill="both", expand=True)

    self.text = tk.Text(container, width=width, height=1, wrap="word", relief="flat",
                         padx=10, pady=10, cursor="arrow", borderwidth=0,
                         highlightthickness=0)
    scroll = ttk.Scrollbar(container, orient="vertical", command=self.text.yview)
    self.text.configure(yscrollcommand=scroll.set)
    self.text.grid(column=0, row=0, sticky="nsew")
    scroll.grid(column=1, row=0, sticky="ns")
    container.grid_columnconfigure(0, weight=1)
    container.grid_rowconfigure(0, weight=1)

    self.text.tag_configure("bold", font=("TkDefaultFont", 0, "bold"))
    self.text.tag_configure("italic", font=("TkDefaultFont", 0, "italic"))
    self.text.tag_configure("underline", underline=True)

    self._render(html)
    self.text.configure(state="disabled")

    closeBtn = ttk.Button(self, text="Close", command=self.destroy)
    closeBtn.pack(pady=(4, 8))

    self.update_idletasks()
    lineCount = int(self.text.index("end-1c").split(".")[0])
    # max(lineCount, 2), not 1: a tk.Text widget configured to height=1 was
    # observed to leave its per-character display geometry uncomputed (bbox()
    # on the very first character returns a placeholder 1x1 rect instead of
    # the real glyph size), which breaks click-position hit-testing for a
    # single-line dialog's action links. height=2 sidesteps it entirely and
    # costs nothing visually -- a one-line dialog just gets a hair of extra
    # vertical room.
    self.text.configure(height=min(max(lineCount, 2), maxHeight))
    self.bind("<Escape>", lambda _e: self.destroy())

  def _render(self, html:str) -> None:
    '''
    Parse *html* and insert its runs into *self.text*, giving each distinct
    action link its own uniquely-named tag (so each link can be bound to,
    and later look up, its own callback independent of any other link that
    happens to share the same visible label).

    :param html: The markup to render -- see the class docstring for the
      supported subset.
    :type html: str
    :rtype: None
    '''
    parser = _RichTextParser()
    parser.feed(html)
    for text, styleTags, actionId in parser.runs:
      tags = list(styleTags)
      if actionId is not None:
        self._linkTagCount += 1
        linkTag = f"actionLink{self._linkTagCount}"
        self.text.tag_configure(linkTag, foreground="#1a73e8", underline=True)
        tags.append(linkTag)
        self.text.insert("end", text, tuple(tags))
        self._bindAction(linkTag, actionId)
      else:
        self.text.insert("end", text, tuple(tags))

  def _bindAction(self, tagName:str, actionId:str) -> None:
    '''
    Wire up one action link's click and hover behaviour: clicking it runs
    the caller's callback for *actionId* (if any was supplied) and then
    closes the dialog iff *self._closeOnAction*; hovering it swaps the
    cursor to a hand to signal it's clickable.

    :param tagName: This specific link occurrence's unique *tk.Text* tag.
    :type tagName: str
    :param actionId: The id from the ``<a id="...">`` markup, used to look
      up the callback in *self._actions*.
    :type actionId: str
    :rtype: None
    '''
    def onClick(_event:tk.Event) -> None:
      callback = self._actions.get(actionId)
      if callback is not None:
        callback()
      if self._closeOnAction:
        self.destroy()

    def onEnter(_event:tk.Event) -> None:
      self.text.configure(cursor="hand2")

    def onLeave(_event:tk.Event) -> None:
      self.text.configure(cursor="arrow")

    self.text.tag_bind(tagName, "<Button-1>", onClick)
    self.text.tag_bind(tagName, "<Enter>", onEnter)
    self.text.tag_bind(tagName, "<Leave>", onLeave)


if __name__ == "__main__":
  root = tk.Tk()
  root.title("ActionDialog demo host")
  tk.Label(root, text="(host window -- the dialog should appear on top)").pack(padx=20, pady=20)

  def onFix(name:str) -> None:
    '''
    :param name:
    :type name: str
    '''
    print(f"fix: {name}")

  def onIgnore(name:str) -> None:
    '''
    :param name:
    :type name: str
    '''
    print(f"ignore: {name}")

  def onDelete(name:str) -> None:
    '''
    :param name:
    :type name: str
    '''
    print(f"delete: {name}")

  ActionDialog(root, "Validation errors on 'Foo'",
    "<b>2 errors on 'Foo':</b>"
    "<ol>"
    "<li>Missing type &#8212; <a id='fix0'>Fix</a> <a id='ignore0'>Ignore</a></li>"
    "<li>Broken link to <i>Bar</i> &#8212; <a id='fix1'>Fix</a> <a id='delete1'>Delete</a></li>"
    "</ol>",
    actions={
      "fix0": lambda: onFix("missing type"),
      "ignore0": lambda: onIgnore("missing type"),
      "fix1": lambda: onFix("broken link"),
      "delete1": lambda: onDelete("broken link"),
    },
    closeOnAction=False)

  root.mainloop()
