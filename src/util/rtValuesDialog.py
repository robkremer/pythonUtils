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
*RTValueDialog*: a dialog of sliders for adjusting a running program's
parameters (each described by a *Param*) as it runs. (It uses matplotlib for its
scales.)

Created on Nov 28, 2025

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''
from typing import Type, Any, Callable
from matplotlib.widgets import Widget
from math import log10, isfinite, floor
from dataclasses import dataclass
from matplotlib.scale import LogScale
from util.tooltip import CreateToolTip
import tkinter as tk
from tkinter import ttk, N, S, E, W
from util.utils import ownDialog

@dataclass
class Param[T]:
  '''
  Class used by the *WorkerProcess* objects to describe each parameter that can
  be modified at run time. *min*, *max*, *help*, and *log* are used primarily 
  in conjuction with the *RTValuesDialog* dialog to implement an
  interface in the main process to allow a user to control these parameters
  in real time.
  '''
  default:T
  min:T
  max:T
  help:str = ""
  log:bool = False
  
  def __post_init__(self):
    t = type(self.default)
    assert t in (int, float), \
      f'Param.__init__(): Parameter values can be either int or float only.'
    assert type(self.min) is t and self.default >= self.min, \
      f'Param.__init__(): Bad *min* parameter ({self.min}): *min* must be the same type as *default*, and *default* >= *min*.' 
    assert type(self.max) is t and self.default <= self.max and self.min <= self.max, \
      f'Param.__init__(): Bad *max* parameter ({self.max}): *max* must be the same type as *default*, and *default* <= *max*, and *min* <= *max*.' 
    self.type = t
  
@dataclass
class SliderInfo:
  '''
  A slider in an *RTValueDialog*, with its value's type and whether its scale is logarithmic.
  '''
  slider:ttk.Scale
  typ:Type
  log:bool
  

class RTValueDialog(tk.Toplevel):
  '''
  A dialog of sliders, one per *Param*, for adjusting a running program's parameters.
  '''

  COL_NAME = 0
  COL_VALUE = 1
  COL_VAL_DISP = 2
  COL_DEF = 3
  
  def __init__(self, parent, title="Attribute Editor", disabled=False):
    '''
    :param parent:
    :type parent:
    :param title:
    :type title: str
    :param disabled:
    :type disabled: bool
    '''
    super().__init__(parent)
    ownDialog(self, parent) # (over its parent's window, not full screen: see ownDialog())
    self.title(title)
    self.parent = parent
    
    self.numRows = 0
    self.pairs:dict[str,SliderInfo] = dict()
    
    self.columnconfigure(0, weight=1)
    self.rowconfigure(0, weight=1)
    self.rowconfigure(1, weight=0)

    self.frame = ttk.Frame(master=self)
    self.frame.grid(column=0, row=0, sticky=N+S+E+W)
        
    self.frame.columnconfigure(RTValueDialog.COL_NAME, weight=0)
    self.frame.columnconfigure(RTValueDialog.COL_VALUE, weight=1, minsize=120)
    self.frame.columnconfigure(RTValueDialog.COL_VAL_DISP, weight=0)
    self.frame.columnconfigure(RTValueDialog.COL_DEF, weight=0)
    font = ('Helvetica', 14, 'bold')
    label = ttk.Label(self.frame, text="PARAMETER", font=font)
    label.grid(column=RTValueDialog.COL_NAME, row=self.numRows, ipadx=0, padx=5, pady=3)
    label = ttk.Label(self.frame, text="VALUE", font=font)
    label.grid(column=RTValueDialog.COL_VALUE, columnspan=2, row=self.numRows, ipadx=0, padx=5, pady=3)
    label = ttk.Label(self.frame, text="DEFAULT", font=font)
    label.grid(column=RTValueDialog.COL_DEF, row=self.numRows, ipadx=0, padx=5, pady=3)
    self.numRows += 1
    ruler = ttk.Separator(master=self.frame)
    ruler.grid(column=RTValueDialog.COL_NAME, row=self.numRows, sticky="EW", padx=5)
    ruler = ttk.Separator(master=self.frame)
    ruler.grid(column=RTValueDialog.COL_VALUE, columnspan=2, row=self.numRows, sticky="EW", padx=5)
    ruler = ttk.Separator(master=self.frame)
    ruler.grid(column=RTValueDialog.COL_DEF, row=self.numRows, sticky="EW", padx=5)
    self.numRows += 1

    self.ctlFrame = ttk.Frame(master=self)
    self.ctlFrame.columnconfigure(0, weight=1)
    self.ctlFrame.grid(column=0, row=1, sticky='SWE')
    ruler = ttk.Separator(master=self.ctlFrame)
    ruler.grid(column=0, row=0, sticky="EW")
    ok_button = tk.Button(self.ctlFrame, text="Dismiss", command=self.on_dismiss)
    ok_button.grid(column=0, row=1, pady=5)

  def show(self):
    #self.grab_set()  # Make the dialog modal
    #self.wm_attributes("-topmost", True) 
    #self.geometry(f'500x{self.winfo_height()}')
    self.wait_window(self) # Wait until the dialog is closed
    
  def on_dismiss(self):
    self.destroy()
  
  def makeEntries(self, entries:dict[str, Param]):
    '''
    Convenience method to construct entries from a simple dictionary of entries.

    :param entries:
    :type entries: dict[str, Param]
    '''
    
  def appendSlider(self, name:str, typ:Type, value:Any, default:Any, minValue:Any, maxValue:Any, fun:Callable[[str,Any], Any], helpText:str="", logScale:bool=False):
    '''
    :param name:
    :type name: str
    :param typ:
    :type typ: Type
    :param value:
    :type value: Any
    :param default:
    :type default: Any
    :param minValue:
    :type minValue: Any
    :param maxValue:
    :type maxValue: Any
    :param fun:
    :type fun: Callable[[str, Any], Any]
    :param helpText:
    :type helpText: str
    :param logScale:
    :type logScale: bool
    '''
    font = ('Helvetica', 14, 'normal')
    label = ttk.Label(self.frame, text=name+":", font=font)
    label.grid(column=RTValueDialog.COL_NAME, row=self.numRows, sticky=tk.E, ipadx=0, padx=5, pady=0)
    CreateToolTip(label, helpText+("\n" if len(helpText)>0 else "")+f'(default={default}, min={minValue}, max={maxValue})', background="yellow", wrapLength=300)

    valField = ttk.Label(self.frame, text=str(value), font=font)
    valField.grid(column=RTValueDialog.COL_VAL_DISP, row=self.numRows, sticky=tk.W, ipadx=0, padx=5, pady=0)

    # slider = tk.Scale(master=self.frame, orient=tk.HORIZONTAL, from_=minValue, to=maxValue, showvalue=0) \
    #          if type(value) == int else \
    #          ttk.Scale(master=self.frame, orient=tk.HORIZONTAL, from_=minValue, to=maxValue)
    slider = ttk.Scale(master=self.frame, orient=tk.HORIZONTAL, 
                       from_=log10(minValue) if logScale else minValue, 
                       to=log10(maxValue) if logScale else maxValue)
    #slider.configure(command=lambda val, fun=fun, name=name, ctl=slider, disp=valField: (fun(name, ctl.get()), disp.configure(text=f'{ctl.get():.3g}')))
    slider.configure(command=lambda val, fun=fun, name=name, ctl=slider, disp=valField, typ=typ, log=logScale: \
                     self.sliderCallbackHandler(val, fun, name, ctl, disp, typ, log))
    slider.grid(column=RTValueDialog.COL_VALUE, row=self.numRows, sticky=tk.E+tk.W, ipadx=0, padx=0, pady=0)
    slider.set(log10(value) if logScale else value)

    defButton = tk.Button(master=self.frame, text=f'{default}', command=lambda ctl=slider, val=value: ctl.set(log10(val) if LogScale else val))
    defButton.grid(column=RTValueDialog.COL_DEF, row=self.numRows, sticky=tk.E+tk.W, ipadx=0, padx=0, pady=0)
    self.pairs[name] = SliderInfo(slider, typ, logScale)
    self.numRows += 1
    
  def sliderCallbackHandler(self, _, fun:Callable, name:str, ctl:ttk.Scale, disp:ttk.Label, typ:Type, log:bool):
    '''
    :param _:
    :type _:
    :param fun:
    :type fun: Callable
    :param name:
    :type name: str
    :param ctl:
    :type ctl: ttk.Scale
    :param disp:
    :type disp: ttk.Label
    :param typ:
    :type typ: Type
    :param log:
    :type log: bool
    '''
    def round_to_N_sig_figs(x, N):
      if x == 0 or not isfinite(x):
        return x
      return round(x, N - int(floor(log10(abs(x)))))
    val = ctl.get()
    if log:
      val = 10 ** val
    val = int(val) if typ is int else float(val)
    fun(name, val)
    disp.configure(text=f'{val:.3g}' if val < 0.000001 or val > 1000000.0 else str(round_to_N_sig_figs(val, 6)))
  
  def __setitem__(self, key:str, value:Any)->None:
    '''
    :param key:
    :type key: str
    :param value:
    :type value: Any
    '''
    if self.pairs[key].log:
      value = log10(value)
    value = int(value) if self.pairs[key].typ is int else float(value)
    self.pairs[key].slider.set(value)
    
  def __getitem__(self, key:str):
    '''
    :param key:
    :type key: str
    :returns:
    :rtype:
    '''
    ret = self.pairs[key].slider.get()
    if self.pairs[key].log:
      ret = 10 ** ret
    ret = int(ret) if self.pairs[key].typ is int else float(ret)
    return ret

if __name__ == "__main__":
  
  def showDialog():
    w = RTValueDialog(root, title="test")
    w.appendSlider("test", float, 10.0, 0.0, 100.0, fun=lambda s, k, v: print(f'(({s.__class__.__name__}){s}) {k} = ({v.__class__.__name__}){v}'), helpText="help1") 
    w.appendSlider("test2", int, 10, 0, 100, fun=lambda s, k, v: print(f'(({s.__class__.__name__}){s}) {k} = ({v.__class__.__name__}){v}')) 
    w.appendSlider("test", float, 10.0, 0.0, 100.0, fun=lambda s, k, v: print(f'(({s.__class__.__name__}){s}) {k} = ({v.__class__.__name__}){v}'), helpText="help1") 
    w.appendSlider("test2", int, 10, 0, 100, fun=lambda s, k, v: print(f'(({s.__class__.__name__}){s}) {k} = ({v.__class__.__name__}){v}')) 
    w.appendSlider("test", float, 10.0, 0.0, 100.0, fun=lambda s, k, v: print(f'(({s.__class__.__name__}){s}) {k} = ({v.__class__.__name__}){v}'), helpText="help1") 
    w.appendSlider("test2", int, 10, 0, 100, fun=lambda s, k, v: print(f'(({s.__class__.__name__}){s}) {k} = ({v.__class__.__name__}){v}')) 
    w.show() 
  
  root = tk.Tk() 
  root.title("Custom Dialog Example")

  custom_button = tk.Button(root, text="Show RTValueDialog", command=showDialog)
  custom_button.pack(pady=20)

  root.mainloop()
  
    