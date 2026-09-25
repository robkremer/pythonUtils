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
from __future__ import annotations
from util.persistence.pRef import PRDb, PRObject
from util.validatedList import ValidatedList
from typing import override
from util.utils import delOne
'''
Created on Sep 10, 2026

@author: robkremer
'''

class AbstractGraph[T:"AGObject", R:"AGRelation"](PRDb[T]):
  '''
  classdocs
  '''
  def  __init__(self, url:str, mode:str="w", memoryResident:bool=True, _reading:bool=False):
    PRDb.__init__(self, url, mode=mode, memoryResident=memoryResident, _reading=_reading)

        
class AGObject[TDB:AbstractGraph, R:"AGRelation"](PRObject[TDB]):
  
  def __init__(self, db:TDB, **kwargs):
    '''
    :param db: The db to which this object will belong.
    :type db: AbstractGraph
    :param kwargs: Passed on to *super().__init__()*. *AGObject* is normally
      shared as a common ancestor by two (or more) of a subclass's bases --
      eg: *sn.model.model.Relation* reaches *AGObject* through both
      *GraphObject* and *AGRelation*. Calling *super().__init__(db=db,
      **kwargs)* here (instead of naming *PRObject* directly, as this used
      to) lets the whole chain stay cooperative, so *PRObject.__init__()* --
      which registers this object with *db* -- runs exactly once no matter
      how many of the subclass's bases lead here, and *kwargs* is how a
      sibling base's own constructor arguments (eg: *AGRelation*'s *src*/
      *dst*, which *AGObject* itself has no use for) get carried through to
      it along that same chain.
    :type kwargs: Any
    '''
    super().__init__(db=db, **kwargs)

    incomingCheck = lambda r, slf=self: isinstance(r, AGRelation) and r.dst is slf
    self._incoming:ValidatedList[R] = ValidatedList(incomingCheck)
    "Should only be assigned by *Relation* objects where self is at the dst end."

    outgoingCheck = lambda r, slf=self: isinstance(r, AGRelation) and r.src is slf and not slf is None
    self._outgoing:ValidatedList[R] = ValidatedList(outgoingCheck)
    "Should only be assigned by *Relation* objects where self is at the src end and not write-locked."
    
  def _isConnected(self):
    return self.id in self.db

  def _disconnect(self, **kwargs) -> None:
    '''
    Disconnect this object from it's *Model* by:
    
      - unregistering it with the *Model*
      - unregistering (from other objects) the far ends of the relations, but keeping the close 
        ends intact so that they may be later restored if necessary
      - unregistering all the above relations with the *Model*
      
    .. Note::

      User this method when deleting an object with the potential to undo the 
      deletion.  Keep a pointer to the object and undo the deletion by calling
      its _reconnect() method.
    '''
    #TODO: This is a potential problem for chains of transitive relations.
    if not self._isConnected():
      raise RuntimeError("Trying to _disconnect() any already-disconnected object: {self}.")
    
    # disconnect from related-to objects
    for r in self._incoming:
      r._disconnect(keep=self)
    for r in self._outgoing:
      r._disconnect(keep=self)

    # unregister from the model
    self.db._unregister(self._id)
    
  def _reconnect(self, **kwargs):
    '''
    Reconnect this disconnected object to it's *Model* by:

      - reregistering it to the *Model*
      - reregistering (to other objects) the far ends of the relations
      - reregistering all the above relations with the *Model*

    .. Note::

      This method should only be used to undo a _disconnect() operation.

    .. Note::

      A relation *r* connecting two objects that are *both* being
      reconnected together (eg: a multi-selection undo of an erase, where
      *r* itself was one of the erased objects) gets reconnected as a side
      effect of whichever of the two objects is processed first: that
      object's own *r._reconnect(kept=self)* call both registers *r* and
      re-appends it onto the *other* (not-yet-reconnected) object's
      *_incoming*/*_outgoing* list, so that object sees *r* again once its
      own turn comes. Guarding with *r._isConnected()* below -- mirroring
      the *#TODO* on *_disconnect()* about chains of transitive relations
      -- is what keeps that second encounter from trying to reconnect (and
      re-*assert*) an already-reconnected *r*.

    '''
    assert not self._isConnected(), self

    # unregister from the model
    self.db._register(self, self._id)

    # disconnect from related-to objects
    for r in self._incoming:
      if not r._isConnected():
        r._reconnect(kept=self)
    for r in self._outgoing:
      if not r._isConnected():
        r._reconnect(kept=self)

        
class AGNode[TDB:AbstractGraph](AGObject[TDB, "AGRelation"]):
  pass


class AGRelation[TDB:AbstractGraph, T:AGObject](AGObject[TDB, "AGRelation"]):
  def __init__(self, db:TDB,
               src:T|None=None,
               dst:T|None=None,
               **kwargs):
    '''
    :param db: The db to which this object will belong.
    :type db: AbstractGraph
    :param src: The source *AGObject* of this relation, or *None*.
    :type src: Optional[T]
    :param dst: The destination *AGObject* of this relation, or *None*.
    :type dst: Optional[T]
    :param kwargs: Passed on to *super().__init__()* -- see *AGObject.__init__()*'s
      *kwargs* param for why. *AGRelation* is normally combined with a sibling
      class (eg: *sn.model.model.GraphObject*, via *sn.model.model.Relation*)
      through multiple inheritance, so this carries through whatever
      constructor arguments that sibling needs that *AGRelation* itself
      doesn't consume.
    :type kwargs: Any
    '''
    super().__init__(db=db, **kwargs)
    self._dst:T|None = None
    self._src:T|None = None
    if db.reading:
      self._dst = dst
      self._src = src
    else:
      self.connect(source=src, destination=dst)

  @property
  def dst(self, localOnly:bool=False) -> T|None: #AGObject|None:
    '''
    :return: The **calculated* destination of this relation; ie: if this relation
      does not have a specific destination, look it up in the ISA hierarchy.
    '''
#    if localOnly or self._dst is not None:
    return self._dst
#    else:
#      obj:AGObject
#      supers = self.getSupers()
#      for obj in supers:
#        assert isinstance(obj, AGRelation)
#        if obj._dst is not None:
#          return obj._dst
#    return None
  
  @dst.setter
  def dst(self, obj:T|None):
#    # if self._legalDst(obj):
#    #   self._dst = obj
#    self.connect(destination=obj)
#    assert self._dst is obj
#    self.setDirty()
    if self._dst is obj: # don't do anything if it's already done.
      return
    if self._dst is not None:
      delOne(self._dst._incoming, self)
    self._dst = obj
    if obj is not None:
      obj._incoming.append(self)
      assert self in obj._incoming
    self.setDirty()
    
  @property
  def src(self, localOnly:bool=False) -> T|None: #AGObject|None:
    '''
    :return: The **calculated* source of this relation; ie: if this relation
      does not have a specific source, look it up in the ISA hierarchy.
    '''
#    if localOnly or self._src is not None:
    return self._src
#    else:
#      obj:AGObject
#      supers = self.getSupers()
#      for obj in supers:
#        assert isinstance(obj, Relation)
#        if obj._src is not None:
#          return obj._src
#    return None
  
  @src.setter
  def src(self, obj:T|None):
#    # if self._legalSrc(obj):
#    #   self._src = obj
#    self.connect(source=obj)
#    assert self._src is obj
#    self.setDirty()
    if self._src is obj: # don't do anything if it's already done.
      return
    if self._src is not None:
      delOne(self._src._outgoing, self)
    self._src = obj
    if obj is not None:
      obj._outgoing.append(self)
      assert self in obj._outgoing
    self.setDirty()
      
  def connect(self, source:T|None=None, destination:T|None=None):
    '''
    Connects or re-assigns the *src* and/or *dst* links by removing any existing
    links and setting the pointers in both this *Relation* and the target
    *GraphObjects*.
    
    .. Note::
    
      Use this method during Relation construction or when modifying the source 
      and/or destination of the Relation. This method ONLY applies to *Relations*.
      (contrast :py:method:`AGObject._disconnect` and 
      :py:method:`AGObject._reconnect`) 
    
    :param source: The :py:class:`AGObject` for the *src* link.
    :type source: AGObject
    :param destination: The :py:class:`AGObject` for the *dst* link.
    :type destination: AGObject
    '''
    if self.view.reading or self.modelObject is None:
      return
    if source is not None:
      if self._src is not source: # don't do anything if it's already done.
        self.src = source
        # if self in source._outgoing:
        #   raise RuntimeError(f'Reinserting self ({self}) into {source}.')
        # source._outgoing.append(self)
    if destination is not None:
      if self._dst is not destination: # don't do anything if it's already done.
        self.dst = destination
        # if self in destination._incoming:
        #   raise RuntimeError(f'Reinserting self ({self}) into {destination}.')
        # destination._incoming.append(self)
    
  @override
  def _reconnect(self, kept:T|None=None, **kwargs):
    super()._reconnect(**kwargs)
    if self._src is not None and self._src is not kept:
      self._src._outgoing.append(self) 
    if self._dst is not None and self._dst is not kept:
      self._dst._incoming.append(self)
    self.setDirty()
   
  @override
  def _disconnect(self, keep:T|None=None, **kwargs) -> None: #type: ignore[override]
    '''
    Disconnects this relation from it's src and dst by removing the pointers
    from the src and dst objects. The pointers **to** these object (in this
    relation) are kept intact. This relation is also removed from it's
    containing *Model* object (it is removed from the Model's list, but
    it's *db* pointer remains intact.
    
    This is typically useful for undo operations where, for example, a delete
    operation on an object can be undone by disconnecting the object, saving
    it, and if it on deletion and then re-connecting it if the delete is undone.
    
    :param source: [default: *False*] Iff True the *src* side is disconnected.
    :type source: bool  
    :param destination: [default: *False*] Iff True the *dst* side is disconnected.
    :type destination: bool  
    '''
    if self._src is not None and self._src is not keep:
      delOne(self._src._outgoing, self) 
    if self._dst is not None and self._dst is not keep:
      delOne(self._dst._incoming, self) 
    if "keep" in kwargs:
      del kwargs["keep"]
    super()._disconnect(**kwargs)
    self.setDirty()
    
    