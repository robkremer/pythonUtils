
Tk Widgets
==========

Several modules provide Tk widgets for an application's user interface. They
fit with the rest of the library -- the attribute editor edits
:doc:`attributes`, and the terminal runs :doc:`commands` -- but can be used
on their own.

The terminal
------------

:py:mod:`util.terminal` gives an application a command line:

:py:class:`~util.terminal.TerminalWidget`
  A Tk text widget that behaves like a terminal: a prompt, typed lines (with
  a history), and output. Each line typed is handed to an *onLine* callback --
  eg: a :py:class:`~util.commandParser.TopCommandParser`'s ``parseLine()`` --
  and the result printed.

:py:class:`~util.terminal.PlainTextTerminal`
  The same, on the real console: a read-evaluate-print loop.

:py:class:`~util.terminal.TerminalRegistry`, :py:func:`~util.terminal.installGlobalIORouting`
  An application with several windows, each with its own terminal, wants each
  window's output to go to *its* terminal. Installed once, the routing sends
  ``print()`` output, ``stderr``, logging and ``input()`` to the terminal of
  whichever window is active; :py:func:`~util.terminal.inputAsync` asks for
  input without blocking the GUI.

The attribute editor
--------------------

:py:mod:`util.attributeEditor` edits an
:py:class:`~util.attribute.AttributedObject`'s attributes in a dialog. Each
attribute gets a row -- its name (with its note as a tooltip), its value, its
type and its inheritance restrictions -- and each value an editor to suit its
type: a checkbox for a ``bool``, a colour swatch (opening the system's colour
chooser) for a ``color``, a menu for ``choices[...]``, a text box for text,
lists and dicts, and an entry otherwise.
:py:class:`~util.attributeEditor.HierarchicalAttrEditor` also shows the
values each attribute inherits, greyed, above its own. Attributes can be
added and deleted, and their types and restrictions changed. Each has a
**note** button, which opens its note (its description, also shown as its
name's tooltip) in a small pop-up editor.

Attributes whose names have a "/" in them are **grouped** like folders (see
:py:func:`~util.attributeEditor.treeOrder`): eg: ``gui/label`` and
``gui/colors/fill`` go under a *gui* group, the latter in a *colors* group
inside it. Each group has a grey header line with a triangle that collapses
or expands it (the collapsed groups are remembered for the next editor), and
each attribute is labelled with just the last part of its name, indented
under its group. Names without a "/" come first. Attributes the program uses
for itself are hidden from the editor by starting their name -- or the name of
a group they're in -- with "." (see :py:func:`~util.attributeEditor.isHiddenKey`):
eg: ``.openWindows``, ``gui/.cache``, or everything in ``.internal/``.

Columns can be left out with *hideColumns* -- any of ``"type"``,
``"qualifiers"`` (the restrictions, in a *HierarchicalAttrEditor*), ``"note"``
and ``"actions"`` (see :py:attr:`~util.attributeEditor.AttrEditor.HIDEABLE_COLUMNS`):
eg: preferences, whose types and restrictions are fixed and whose notes are
documentation, show just their names and values (the notes are still their
names' tooltips).

:py:func:`~util.attributeEditor.editAttrsBox` returns the edits (for the
caller to apply -- eg: as an undoable command); :py:func:`~util.attributeEditor.applyEditAttrsBox`
applies them itself (eg: for preferences).

Dialogs and tooltips
--------------------

:py:class:`~util.actionDialog.ActionDialog`
  A pop-up that renders a small subset of HTML -- bold, italic, underline,
  line breaks, lists -- with links that run actions.
  :py:class:`~util.errorReportingObject.ErrorReportingObject`, a mix-in for
  objects that check themselves, uses it to show a validation report whose
  entries offer to fix the problems they describe.

:py:class:`~util.tooltip.CreateToolTip`
  A tooltip for a widget -- or for one item on a canvas. Its text can be a
  function, so it's worked out when it's shown; it appears after a delay, and
  can be given a font (eg: a fixed-width one, to line up a table).

:py:class:`~util.rtValuesDialog.RTValueDialog`
  A dialog of sliders, each described by a :py:class:`~util.rtValuesDialog.Param`,
  for adjusting a running program's parameters. (It needs matplotlib.)
