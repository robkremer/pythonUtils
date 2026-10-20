
Observers and Changes
=====================

Two small modules let objects keep track of change: :py:mod:`util.observer`,
for telling others what's changed, and :py:mod:`util.dirtyable`, for knowing
what needs saving.

Subjects and observers
----------------------

A :py:class:`~util.observer.Subject` keeps a list of observers and tells them
about its changes. A change is described by *topics*: each a name and a tuple
of values, eg: ``("new", (12, obj))`` or ``("mod attribute", ("color",
"red"))``.

- ``subject.attach(observer, "new", "del")`` registers an
  :py:class:`~util.observer.Observer` -- an object with an ``update(subject,
  *topics)`` method -- for those topics (or, with none named, for all).
  ``attachCallback(fn, ...)`` registers a plain function instead.
- ``subject.notify(topic, ...)`` tells them, at once.
  ``subject.notifyLater(...)`` tells them once the current call stack has
  unwound -- eg: after a constructor finishes, so that an observer never sees
  a half-built object. It uses the application's scheduler if it has one,
  else Tk's or asyncio's, else a timer. Setting ``observer.alwaysLater`` makes
  every *notify* a *notifyLater*; ``observer.enabled`` turns notifications off
  altogether (eg: while reading a file).

The databases of :doc:`persistence` and the attributed objects of
:doc:`attributes` are subjects.

Batching changes
~~~~~~~~~~~~~~~~

A change often consists of smaller changes, each of which would otherwise
notify the observers -- and they'd see the change half done. Instead, the
subject's code wraps the change in a :py:class:`Subject.ChangeMgr
<util.observer.Subject.ChangeMgr>`::

  with Subject.ChangeMgr(self) as change:
    ...                                     # make the change
    change.registerTopics(("moved", (x, y)))

The topics are collected, not sent. Changes made inside the block -- including
by other methods that use a *ChangeMgr* of their own -- are collected too, and
the observers are notified once, with all of them, when the outermost block
ends. ``change.cancel()`` drops the notification (if every nested change was
cancelled too).

Dirty bits
----------

A :py:class:`~util.dirtyable.Dirtyable` object knows whether it has changed
since it was last saved: ``setDirty()`` when it changes, ``setDirty(False)``
when it's saved, ``isDirty()`` to ask. An object that contains other
*Dirtyable* objects is dirty if any of them is -- so a database is dirty if
any of its objects is, and an attributed object if any of its attributes is.
*Semantic Nets* uses this to save only what's changed: to ask about saving
modified models when quitting, and to save its preferences only when they've
changed.

:py:class:`~util.validatedList.ValidatedList`, a list that checks what's put
in it, is *Dirtyable* too.
