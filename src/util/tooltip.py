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
""" 
  .. inheritance-diagram:: CreateToolTip
      :parts: 3
      :private-bases:
      :top-classes: util.commandParser.ParsableCommandDef, util.commandParser.ParsableQuery


tk_ToolTip_class101.py
gives a Tkinter widget a tooltip as the mouse is above the widget
tested with Python27 and Python34  by  vegaseat   09sep2014
www.daniweb.com/programming/software-development/code/484591/a-tooltip-class-for-tkinter

Modified to include a delay time by Victor Zaccardo, 25mar16

----------
"""

import tkinter as tk
from typing import Any, Union, Callable, Optional
from tkinter import Widget

def findCanvas(widget:tk.Widget) -> tk.Canvas|None:
  '''
  Walks up the Tk widget hierarchy from *widget* looking for an
  enclosing *tk.Canvas*. Works for any widget embedded via
  *canvas.create_window(...)*, since Tk requires such a widget's
  master to already be (or descend from) the canvas it's embedded in.

  :param widget: The widget to search upward from.
  :type widget: tk.Widget
  :returns: The nearest enclosing *tk.Canvas*, or None if there isn't one.
  :rtype: Optional[tk.Canvas]
  '''
  w:tk.Misc|None = widget
  while w is not None:
    if isinstance(w, tk.Canvas):
      return w
    w = w.master
  return None


class CreateToolTip:
  """
  create a tooltip for a given widget
  """
  def __init__(self, widget:Widget, text:Union[str,Callable[[],str]]='', canvasID:Optional[int]=None, 
        waitTime:int=500, wrapLength:int=240, 
        shouldDisplay:Optional[Callable]=None,
        background="#ffffff", font:Any=None):
    """
    :param widget:    The widget at attach this tooltip to
    :param text:    Either a string to display or a no-argument function returning a *str*
    :param canvasID:  A required item ID if *widget* is a tk.Canvas, otherwise ignored.
    :param waitTime:  The time to wait in msec. [default=500]
    :param wrapLength:  The width to wrap at in pixels (0: no wrapping) -- or a
              no-argument function giving it, asked each time it's shown. [default=240]
    :param shouldDisplay: A function taking this object as an argument returning a bool
              indicating that this text tool is to be displayed (asked when
              the pointer comes in). Either way, the tooltip isn't displayed
              if its text is empty (asked once, when it's about to be shown:
              so a function giving it isn't called just for passing over).
    :type shouldDisplay: Optional[Callable[[Self],bool]]
    :param font: The font for the text (eg: "TkFixedFont", so text laid out with
      spaces stays aligned); by default, Tk's default -- or a no-argument
      function giving it (None for the default), asked each time it's shown.
    :throws TypeError:
    :throws ValueError:
    :param background:
    :type background: str
    """
    self.waittime = waitTime   #miliseconds
    self.wraplength = wrapLength   #pixels
    self.background = background
    self.font = font
    if isinstance(text, Callable):
      self.text = text
    elif isinstance(text, str):
      self.text = lambda text=text: text
    else:
      raise TypeError(f'CreateToolTip: Expected parameter "text" to be a function, f()->str, or a str; but got {type(text).__name__}.')
    self.shouldDisplay = shouldDisplay if shouldDisplay is not None else lambda o: True
    self.widget = widget
    self.canvasID = canvasID
    self.isCanvas = isinstance(widget, tk.Canvas)
    if self.isCanvas:
      if self.canvasID is None: raise ValueError('CreateToolTip: When parameter "widget" is a tk.Canvas, parameter "canvasID" must be specified.')
      self.widget.tag_bind(self.canvasID, "<Enter>", self.enter)
      self.widget.tag_bind(self.canvasID, "<Leave>", self.leave)
      self.widget.tag_bind(self.canvasID, "<ButtonPress>", self.leave)
    else:
      self.widget.bind("<Enter>", self.enter)
      self.widget.bind("<Leave>", self.leave)
      self.widget.bind("<ButtonPress>", self.leave)
    self.id = None
    self.tw = None
    self.watchID = None
    
  def delete(self):
    self.unschedule()
    self.hidetip()
    if self.isCanvas:
      assert self.canvasID is not None
      self.widget.tag_unbind(self.canvasID, "<Enter>")
      self.widget.tag_unbind(self.canvasID, "<Leave>")
      self.widget.tag_unbind(self.canvasID, "<ButtonPress>")
    else:
      self.widget.unbind("<Enter>")
      self.widget.unbind("<Leave>")
      self.widget.unbind("<ButtonPress>")
    self.widget = None
    self.text = None
    self.shouldDisplay = None

  def enter(self, event=None):
    '''
    :param event:
    :type event:
    '''
    if self.shouldDisplay(self):
      self.schedule()

  def leave(self, event=None):
    '''
    :param event:
    :type event:
    '''
    self.unschedule()
    self.hidetip()

  def schedule(self):
    self.unschedule()
    self.id = self.widget.after(self.waittime, self.showtip)

  def unschedule(self):
    id = self.id
    self.id = None
    if id:
      self.widget.after_cancel(id)

  def showtip(self, event=None):
    '''
    :param event:
    :type event:
    '''
    self.id = None
    if not self.stillWanted():
      return
    text = self.text()
    if not text:
      return
    font = self.font() if callable(self.font) else self.font
    wraplength = self.wraplength() if callable(self.wraplength) else self.wraplength
    x = y = 0
    if self.isCanvas:
      x, y, cx, cy = self.widget.bbox(self.canvasID)
      screenX = self.widget.winfo_rootx() + (cx - self.widget.canvasx(0))
      screenY = self.widget.winfo_rooty() + (cy - self.widget.canvasy(0))
    else:
      #x, y, cx, cy = self.widget.bbox("insert")
      screenX = self.widget.winfo_rootx() + self.widget.winfo_width()
      screenY = self.widget.winfo_rooty() + self.widget.winfo_height()
    # creates a toplevel window
    self.tw = tk.Toplevel(self.widget)
    # Leaves only the label and removes the app window
    self.tw.wm_overrideredirect(True)
    self.tw.wm_geometry("+%d+%d" % (screenX, screenY))
    label = tk.Label(self.tw, text=text, justify='left',
             background=self.background, relief='solid', borderwidth=1,
             wraplength = wraplength, **({} if font is None else {"font": font}))
    label.pack(ipadx=1)
    # An overrideredirect window is NOT managed by the window manager, so
    # nothing protects its stacking position once created -- if anything
    # else (the WM/window server itself, or this app raising/focusing
    # another window shortly after, e.g. during the waitTime delay)
    # restacks in the meantime, this window can end up behind it.
    #
    # -topmost alone asks the window manager/window server to keep this
    # window above normal-level windows -- but that's not enough when
    # *self.widget* lives in a dialog that itself holds an active grab
    # (e.g. AttrEditor.show()'s grab_set_global() for the snPrefs
    # editor): plain "-topmost" says "stay above normal windows" without
    # reference to any particular one, and that's apparently not a
    # strong enough claim while another window holds the grab. transient()
    # is the more specific, and on Aqua more reliable, fix: it tells the
    # window server this tooltip belongs directly above *this specific*
    # window -- the tooltip's owning toplevel, i.e. the actual dialog the
    # widget lives in (AttrEditor's Toplevel in the snPrefs case, an
    # AppWindow in the ordinary case) -- not whatever this widget's
    # ultimate root happens to be, which for a widget inside a dialog
    # raised from a hidden/withdrawn root would otherwise be that hidden
    # root. Guarded by winfo_viewable() for the same reason as the
    # AttrEditor/exception-dialog fixes elsewhere in this codebase:
    # marking a window transient-for something not actually viewable can
    # misbehave on macOS/Aqua rather than just being a no-op.
    owner = self.widget.winfo_toplevel()
    if owner.winfo_viewable():
      self.tw.transient(owner)
    # -topmost must be requested BEFORE update_idletasks()/lift() are
    # given a chance to process the window, or the request can silently
    # fail to stick (verified empirically: requesting -topmost after
    # those calls left it unset; requesting it first works reliably).
    # lift() afterwards then puts it on top of the CURRENT stacking
    # order too, in case -topmost/transient alone aren't honoured
    # immediately.
    self.tw.attributes('-topmost', True)
    self.tw.update_idletasks()
    self.tw.lift()
    self.watchID = self.widget.after(self.WATCH_INTERVAL, self.watch)

  WATCH_INTERVAL = 250
  "How often (msec) a tooltip that's shown checks it's still wanted (see *watch()*)."

  def appActive(self) -> bool:
    '''
    :returns: Whether this program is the one in front (the user's working in
      it): one of its windows has the keyboard focus.
    '''
    try:
      return self.widget.focus_displayof() is not None
    except (tk.TclError, KeyError): # (KeyError: the focus is in a window Tkinter didn't make -- eg: a native dialog)
      return True

  def pointerOver(self) -> bool:
    '''
    :returns: Whether the pointer's over what this is the tooltip of: the
      widget -- or, on a canvas, its item -- within a few pixels.
    '''
    w = self.widget
    try:
      px, py = w.winfo_pointerxy()
      if self.isCanvas:
        box = w.bbox(self.canvasID)
        if not box:
          return False
        x0 = w.winfo_rootx() + box[0] - w.canvasx(0)
        y0 = w.winfo_rooty() + box[1] - w.canvasy(0)
        x1, y1 = x0 + box[2] - box[0], y0 + box[3] - box[1]
      else:
        x0, y0 = w.winfo_rootx(), w.winfo_rooty()
        x1, y1 = x0 + w.winfo_width(), y0 + w.winfo_height()
    except tk.TclError:
      return False
    m = 3
    return x0 - m <= px <= x1 + m and y0 - m <= py <= y1 + m

  def stillWanted(self) -> bool:
    '''
    :returns: Whether a tooltip should be shown (or stay shown): this program's
      in front, and the pointer's over what it's the tooltip of. (It's
      -topmost: shown when the program isn't in front -- eg: a double-click
      opened another program, or the pointer left while it was busy -- it'd
      float over the other programs' windows; and a <Leave> can be missed: eg:
      when the item's redrawn, moved or deleted under the pointer.)
    '''
    return self.widget is not None and self.appActive() and self.pointerOver()

  def watch(self) -> None:
    '''While the tooltip's shown: hide it as soon as it's no longer wanted (see *stillWanted()*).'''
    self.watchID = None
    if self.tw is None or self.widget is None:
      return
    if not self.stillWanted():
      self.hidetip()
      return
    self.watchID = self.widget.after(self.WATCH_INTERVAL, self.watch)

  def hidetip(self):
    watchID, self.watchID = self.watchID, None
    if watchID and self.widget is not None:
      try:
        self.widget.after_cancel(watchID)
      except tk.TclError:
        pass
    tw = self.tw
    self.tw= None
    if tw:
      tw.destroy()

# testing ...
if __name__ == '__main__':
  root = tk.Tk()
  btn1 = tk.Button(root, text="button 1")
  btn1.pack(padx=10, pady=5)
  button1_ttp = CreateToolTip(btn1, \
   'Neque porro quisquam est qui dolorem ipsum quia dolor sit amet, '
   'consectetur, adipisci velit. Neque porro quisquam est qui dolorem ipsum '
   'quia dolor sit amet, consectetur, adipisci velit. Neque porro quisquam '
   'est qui dolorem ipsum quia dolor sit amet, consectetur, adipisci velit.')

  btn2 = tk.Button(root, text="button 2")
  btn2.pack(padx=10, pady=5)
  button2_ttp = CreateToolTip(btn2, lambda: \
  "First thing's first, I'm the realest. Drop this and let the whole world "
  "feel it. And I'm still in the Murda Bizness. I could hold you down, like "
  "I'm givin' lessons in  physics. You should want a bad Vic like this.")

  btn3 = tk.Button(root, text="button 3")
  btn3.pack(padx=10, pady=5)
  button3_ttp = CreateToolTip(btn3, lambda: "")
  
  root.mainloop()