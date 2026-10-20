
Commands
========

Two modules make an application's operations into *commands*: objects that
can be done, undone and redone (:py:mod:`util.command`), and that can be
typed on a command line as well as called from code
(:py:mod:`util.commandParser`).

Commands and the undo list
--------------------------

A :py:class:`~util.command.Command` has a name, and ``do()`` and ``undo()``
methods. (Their base versions check they're called in turn -- not *do* twice
without an *undo* between -- so a subclass's should call them first.) For a
quick one, :py:class:`~util.command.LambdaCommand` takes the *do* and *undo*
as functions::

  inc = LambdaCommand("increment", lambda: counter.inc(), lambda: counter.dec())

A :py:class:`~util.command.DoList` is an undo history. ``doList.do(command)``
does the command and records it; ``undo()`` and ``redo()`` step back and
forward through the history, and doing a new command discards what could have
been redone. ``undoQueue()`` and ``redoQueue()`` describe what's there, eg: for
a menu's "Undo *move*" item.

Command contexts
----------------

A :py:class:`~util.commandParser.CommandContext` is a class whose methods are
commands -- callable from code, and parsable from a command line, both through
the same machinery, and so with the same undo history. Each public method
becomes a command:

- its name's words make the command's words: ``new_node`` is typed as ``new
  node`` (commands sharing a first word are grouped: ``new node``, ``new
  relation``, ...); a unique prefix of a word will do;
- its parameters without defaults are the command's arguments; those with
  defaults are its ``--options`` -- except positional-only ones (before
  ``/``), which are optional arguments. Their annotations give their types
  (a ``bool`` is a flag), and their docstring fields (``:param x:``) the help.

A method with a matching nested :py:class:`~util.command.Command` class --
``move()`` and ``_Move`` -- is an *undoable* command: calling it (or typing it)
makes a ``_Move`` with the arguments, and does it through the context's
:py:class:`~util.command.DoList`. The method itself is never run: it's a
*signature* for the command. A method without one is simply run, and isn't
undoable -- eg: a query.

.. code-block:: python

   from __future__ import annotations # (the parser reads the annotations as text)
   from util.command import Command
   from util.commandParser import CommandContext

   count = [0]

   class Counter(CommandContext):
     def add(self, n:int, /):
       """Add *n* to the count.

       :param n: How much to add.
       :type n: int
       """
     class _Add(Command):
       def __init__(self, n:int):
         super().__init__("add")
         self.n = n
       def do(self):
         super().do(); count[0] += self.n
       def undo(self):
         super().undo(); count[0] -= self.n

Then, with ``ctx = Counter()``, ``ctx.add(3)`` and the typed line
``ctx.parser.parseLine("add 3")`` do the same thing, and ``undo`` (or
``ctx.undo()``) undoes either. Every context has ``undo``,
``redo``, ``help``, ``debug`` and ``default`` commands of its own.

Two dictionaries complete the picture:

- the context's **decoders** turn typed text into the values the methods
  expect, by parameter type: eg: *Semantic Nets* decodes an object's name, or
  ``#12``, into the object itself;
- its **defaults** fill in missing arguments -- eg: the current model -- and
  can be set with the ``default`` command.

A :py:class:`~util.commandParser.TopCommandParser` is the root of a context's
command tree (built with :mod:`argparse`): ``parser.parseLine(text)`` splits
a line (respecting quotes) and runs the command.

Composite commands
~~~~~~~~~~~~~~~~~~

Several commands that make up one action are grouped with a
:py:class:`~util.commandParser.CompositeCommandMgr`::

  with CompositeCommandMgr(context):
    context.move(a, 10, 20)
    context.move(b, 30, 40)

Inside the block, the commands are *queued*, not done; when it ends, they're
done together as one :py:class:`~util.commandParser.CompositeCommand` -- one
entry in the undo history, undone in reverse order. Because they're queued, a
command in the group can't see the effects of the ones before it.
