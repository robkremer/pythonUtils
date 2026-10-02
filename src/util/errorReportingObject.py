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
*ErrorReportingObject*: a mix-in for objects that check themselves. Problems
found while validating are added to the object's *status report* (with a
severity, and optional actions to fix them), which can then be shown in an
*ActionDialog* (see *util.actionDialog*).

Created on Sep 18, 2026

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''
from util.actionDialog import ActionDialog
import tkinter as tk
from typing import Callable

class ErrorReportingObject(object):
  
  '''
  A mix-in for objects that check themselves: *validate()* fills the object's
  status report (see *assertToStatusReport()*), whose entries can be listed
  (*statusReport()*) or shown, with their actions, in an *ActionDialog*.
  '''
  def __init__(self, **kwargs):
    '''
    :param kwargs: Passed on to *super().__init__()*. *ErrorReportingObject*
      is meant to be combined with other classes via multiple inheritance
      (see *sn.view.graphics.vobjects.VObject*), so calling
      *super().__init__(**kwargs)* here -- rather than simply returning --
      keeps this class from becoming a dead end in that cooperative chain if
      something is ever listed after it in some future class's MRO.
    :type kwargs: Any
    '''
    super().__init__(**kwargs)
    self._statusReport:list[tuple[str, str, dict[str,Callable[[],None]]]] = []
    
  def assertToStatusReport(self, cond:bool, msg:str, severity:str='E', actions:dict[str,Callable[[],None]]=dict()) -> None:
    '''
    Conditionally logs an line in the status report for the object.
    
    :param cond: A conditional expression that if False will cause an entry in
      the status report.
    :type cond: bool:
    :param msg: A message to print in the status report if *cond* is False.
    :type msg: str
    :param severity: A one-character severity code: F (fatal), E (error), 
      W (warning), I (informational)
    :type severity: str
    :param actions: A dict of str:Callable indicating actions such as fix:<function>,
      or "delete:<function>" for use in a ActionDialog later.
    :type actions: dict[str:Callable[[],None]]
    :returns: None
    '''
    if not cond:
      self._statusReport.append((severity, msg, actions))
    
  def validate(self) -> list[str]:
    '''
    :returns:
    :rtype: list[str]
    '''
    self.assertToStatusReport(True, "This message should never be displayed", 'E', []) # type: ignore[arg-type]
    return self.statusReport()
  
  def statusReport(self) -> list[str]:
    '''
    :returns:
    :rtype: list[str]
    '''
    ret:list[str] = []
    for sev, text, _actions in self._statusReport:
      ret.append(f'{sev}: {text}')
    return ret
  
  def clearStatusReport(self) -> None:
    self._statusReport = []
    
  def showErrorActionDialog(self, parentWidget:tk.Wm):
    '''
    :param parentWidget:
    :type parentWidget: tk.Wm
    '''
    name:str|None = str(self.name) if hasattr(self, "name") else None
    subject:str = "" if name is None else f' on "{name}"'
    text:str = f'For <b>{str(self)}:</b><br><br><ol>'
    actions:dict[str, Callable[[],None]] = dict()
    i:int = 0
    for errdata in self._statusReport:
      text += f'<li><b>{errdata[0]}:</b> {errdata[1]}'
      for fixName, fun in errdata[2].items():
        text += f' <a id="{fixName}-{i}">[{fixName}]</a>'
        actions[f'{fixName}-{i}'] = fun
      text += "</li>"
      i += 1
    text += "</ol>"
    ActionDialog(parentWidget, f'Validation errors{subject}',
      text,
      actions=actions,
      closeOnAction=False)
    
  def status(self) -> str:
    '''
    :returns:
    :rtype: str
    '''
    stats:list[tuple[str,str,dict[str,Callable[[],None],]]] = self._statusReport
    priority = 'IWEF'
    pos:int = -1
    if not stats:
      return ''
    for s,_,_ in stats:
      p = priority.find(s) 
      if p > pos:
        pos = p
    assert pos>=0
    return priority[pos]
  
  _STATUS:dict[str,int] = {
    '':0,
    'E':-1,
    'F':-2,
    'I':1,
    'W':2
    }
  
  def statsInt(self):
    '''
    :returns:
    :rtype:
    '''
    return self._STATUS[self.status()]    
    
        