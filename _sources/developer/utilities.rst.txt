
Preferences, Graphs and Utilities
=================================

Preferences
-----------

A :py:class:`~util.prefs.Prefs` holds an application's preferences: it's an
:py:class:`~util.attribute.AttributedObject` (see :doc:`attributes`), with no
supertypes, saved to a file of its own. An application typically reads it
when it starts, and saves it when it quits::

  try:
    prefs = MyPrefs.read(path)        # (a subclass of Prefs)
  except Exception:
    prefs = MyPrefs()
  ...
  width = prefs.get("gui/width", storeDefault=600, storeType=int,
                    note="The width of a new window.")

Declaring a preference where it's first used -- with *storeDefault*, its
type and a note -- adds it, with its default, to the file, where the user can
see and change it. :py:func:`~util.attributeEditor.applyEditAttrsBox` makes a
preferences dialog of it with no further work (see :doc:`widgets`).
``prefs.addCallback(key, fn)`` registers a function to call whenever a
preference changes. Since *Prefs* is :py:class:`~util.dirtyable.Dirtyable`, an
application can save it only if it's changed.

Graphs
------

:py:mod:`util.abstractGraph` is the basis for persistent graphs: an
:py:class:`~util.abstractGraph.AbstractGraph` is a database (see
:doc:`persistence`) of :py:class:`~util.abstractGraph.AGObject`\ s, each of
which keeps the relations that come in to it and go out from it. A relation,
:py:class:`~util.abstractGraph.AGRelation`, is itself an object, with a
*src* and a *dst* -- either of which may be a node, another relation, or
None -- and keeps its ends' lists up to date as it's connected, reconnected
and disconnected. (*Semantic Nets*' models and views are both
*AbstractGraph*\ s.)

The utilities module
--------------------

:py:mod:`util.utils` is a miscellany. Among other things:

URLs and files
  :py:func:`~util.utils.fixURL` (make a file path or URL into a URL, with an
  extension), :py:func:`~util.utils.isValidURL`,
  :py:func:`~util.utils.urlExists`, :py:func:`~util.utils.fileToUrl`,
  :py:func:`~util.utils.urlToFile`, :py:func:`~util.utils.changeUrlExtension`.

Classes
  :py:func:`~util.utils.getFullClassName` and
  :py:func:`~util.utils.getClassFromFullyQualifiedName` (how saved files name
  classes), :py:func:`~util.utils.findConcreteSubclasses`,
  :py:func:`~util.utils.importSubmodules`.

Geometry
  :py:class:`~util.utils.Point`, :py:func:`~util.utils.pointInRect`,
  :py:func:`~util.utils.pointInPoly`, :py:func:`~util.utils.overlaps`,
  :py:func:`~util.utils.expandRect`, :py:func:`~util.utils.normalizeRect`,
  :py:func:`~util.utils.midpoint`.

Tk helpers
  :py:func:`~util.utils.bindRightMouse` (a right click, or Control-click on a
  Mac), :py:func:`~util.utils.askUser` (asks in a Tk dialog if there's a GUI,
  or else on the terminal), :py:func:`~util.utils.showExceptionDialog`,
  :py:class:`~util.utils.VerticalScrolledFrame`.

Lists and text
  :py:func:`~util.utils.grouped`, :py:func:`~util.utils.flattenPairs`,
  :py:func:`~util.utils.removeDuplicates`, :py:func:`~util.utils.strToBool`,
  :py:func:`~util.utils.quoteIfNecessary`,
  :py:func:`~util.utils.resolveAliases` (``${name}`` substitutions).

Commands
  :py:func:`~util.utils.makeParserFromFunc`: an :mod:`argparse` parser from
  a function's signature and docstring -- what the command parser is built on
  (see :doc:`commands`).

:py:class:`~util.utils.Categories`
  Named categories of objects, each defined by a test (*Semantic Nets* uses
  them to hide or erase categories of objects in a view).

:py:class:`~util.utils.ExtendedFlag`
  A *Flag* whose members can be looked up by combined names, eg:
  ``Flags["A|B"]``.
