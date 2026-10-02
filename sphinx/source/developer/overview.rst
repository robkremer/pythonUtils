
Overview
========

The library is the ``util`` package (in ``src/``). Its parts build on one
another:

.. graphviz::

   digraph layers {
     rankdir=BT;
     node [shape=box, style=rounded, fontname="Helvetica", fontsize=11];
     edge [color="gray40"];
     serialize [label="persistence.serialize\nSerializable, SerializationStrategy\n(XML, XML2, JSON, plist)"];
     pRef [label="persistence.pRef\nPRDb, PRObject, PReference"];
     observer [label="observer\nSubject, Observer"];
     dirtyable [label="dirtyable\nDirtyable"];
     attribute [label="attribute\nAttribute, AttributedObject"];
     prefs [label="prefs\nPrefs"];
     agraph [label="abstractGraph\nAbstractGraph, AGObject, AGRelation"];
     command [label="command\nCommand, DoList"];
     parser [label="commandParser\nCommandContext, TopCommandParser"];
     widgets [label="Tk widgets\nterminal, attributeEditor,\nactionDialog, tooltip, ..."];
     pRef -> serialize; pRef -> observer; pRef -> dirtyable;
     attribute -> serialize; attribute -> observer; attribute -> dirtyable;
     prefs -> attribute;
     agraph -> pRef;
     parser -> command;
     widgets -> attribute [style=dashed];
     widgets -> parser [style=dashed];
   }

:doc:`persistence`
  Objects that are saved to files and read back, with their references to
  one another intact -- even across files.

:doc:`attributes`
  Named, typed values attached to objects, inherited down a type hierarchy
  under per-attribute restrictions.

:doc:`commands`
  Commands that can be undone and redone, and a command-line parser that
  makes the methods of a class into typed commands.

:doc:`observer`
  Subjects that tell their observers what's changed -- in batches -- and a
  "dirty bit" for knowing what needs saving.

:doc:`widgets`
  Tk widgets for an application: a terminal, an attribute editor, dialogs
  and tooltips.

:doc:`utilities`
  Logging, preferences, graphs, and the miscellany in ``util.utils``.

Using it
--------

The library needs Python 3.14 (it uses the newer generic syntax, eg:
``class PRDb[T:PRObject]``), and Tk for the widgets. Put ``src`` on the
Python path, and import from ``util``::

  from util.persistence.pRef import PRDb, PRObject
  from util.attribute import AttributedObject, Attribute

Some parts need other packages: ``requests`` and ``urllib3`` (reading URLs),
``docstring_parser`` (the command parser takes its help text from docstrings),
and ``matplotlib`` (``util.rtValuesDialog`` only).

Logging
~~~~~~~

Every module gets its logger with ``util.getLogger(__name__)``. An
application can take over: if its top-level package has a ``getLogger()`` of
its own, that's used instead -- *Semantic Nets*' ``sn.getLogger()``, for
instance, makes every logger an ``SNLogger``. The application should also call
:py:func:`util.setupLogger` (with its logger class and log file name) *before*
importing anything else from ``util``: the modules get their loggers as
they're imported, and if logging isn't set up by then, ``util`` sets it up its
own way. A packaged application (eg: a .app) logs in
*~/Library/Logs/<program>/*.

Building the documentation
--------------------------

``build.xml`` builds this documentation with Sphinx (under Python 3.14, with
the *furo* theme and graphviz):

``rebuildAutoDoc``
  Regenerates the API reference, ``sphinx/source/dev/``, from the code with
  ``sphinx-apidoc``. The directory is wiped and rewritten each time, so don't
  put anything else there. (The old ``x_*`` modules and the scratch
  ``util/test.py`` are left out.)

``doc``
  Regenerates the API reference, builds the HTML into ``sphinx/build/html``,
  and copies it to the web server's folder. *Semantic Nets*' documentation
  links into this one (through intersphinx, reading
  ``sphinx/build/html/objects.inv``), so build this one first.

``logo``
  Redraws the logo and favicon (``sphinx/makeLogo.py``; it needs Pillow).

``test``
  Runs the unit tests, in ``test/``.

Docstrings are reStructuredText, with Sphinx's field lists for parameters
(``:param x:``, ``:type x:``, ``:returns:``, ``:rtype:``).
