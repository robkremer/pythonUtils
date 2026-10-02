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
*Dirtyable*: a mix-in for objects that need to know whether they've changed
since they were last saved (a "dirty bit"), including through the objects they
contain.

Created on Sep 11, 2026

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''

class Dirtyable:
  '''
  A mixin class for object needing a dirty bit, using setDirty() and isDirty()
  '''

  def __init__(self, **kwargs) -> None:
    '''
    Set the _dirty property and initialize it to False.

    :param kwargs: Passed on to *super().__init__()*. *Dirtyable* is normally
      one link in a longer chain of cooperative *__init__* calls -- eg:
      *sn.view.graphics.vobjects.VObject* combines it with *Observer* and
      *ErrorReportingObject* via multiple inheritance. Calling
      *super().__init__(**kwargs)* here (instead of simply returning) ensures
      whatever comes after *Dirtyable* in that particular class's MRO still
      gets initialized, exactly once, with the constructor arguments meant
      for it, even though *Dirtyable* itself has no use for them. Not doing
      this used to silently strand every class listed after *Dirtyable* in
      such a chain -- eg: *ErrorReportingObject.__init__()* never ran for any
      *VObject*, because *Dirtyable.__init__()* was the cooperative chain's
      dead end.
    :type kwargs: Any
    '''
    super().__init__(**kwargs)
    self._dirty:bool = False
        
  def setDirty(self, dirty:bool=True):
    '''
    An object is dirty if it has been modified and should probably be
    saved on exit.  This should be called from all methods that modify
    the state of this object.
    
    Container classes should override this method to clear all child Dirtyables
    if the dirty bit is being cleared (presumably after a save opertation) with
    something like the following:
    
    .. code-block::
    
      if not dirty:
        obj:T
        for obj in self.values():  # LOCAL attributes only -- an inherited Attribute belongs to (and is tracked dirty by) its owning super object, not this one
          if obj.isDirty():
            obj.setDirty(False)
      super().setDirty(dirty)
    
    
    :param value: (default True) The value to set *dirty* to.
    :type value: bool
    :param dirty:
    :type dirty: bool
    '''
    self._dirty = dirty
    
  def isDirty(self) -> bool:
    '''
    Returns True iff the object has been modified and should probably
    be saved on exit. 
    
    Container classes should override this method to check all child Dirtyables
    if the its own dirty bit not already set with
    something like the following:
    
    .. code-block::
  
      if super().isDirty():
        return True
      obj:T
      for obj in self.values():  # LOCAL attributes only -- see setDirty()
        if obj.isDirty():
          super().setDirty(True)
          return True
      return False
    
    
    :returns: True iff this object is dirty.
    :rtype: bool
    '''
    return self._dirty