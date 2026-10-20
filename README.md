# pythonUtils

*pythonUtils* is a library of building blocks for Python applications:
persistent objects that refer to one another across files, attributes that are
inherited down a type hierarchy, commands that can be undone and typed at a
command line, the observer pattern, preferences, and some Tk widgets (a
terminal, an attribute editor, dialogs and tooltips).

It grew out of [Semantic Nets](https://github.com/robkremer/semanticNets),
which is built on it, but it doesn't depend on Semantic Nets and can be used on
its own.

## What's in it

Everything is in the `util` package, under `src/`.

| Module | What it provides |
| --- | --- |
| `util.persistence.pRef` | Databases of persistent objects (`PRDb`, `PRObject`) that refer to one another by reference (`PReference`), even across files and URLs. |
| `util.persistence.serialize` | Serialization strategies that keep shared references intact, in several formats: XML (`serializeXML`, `serializeXML2`, `serializeXML3`), JSON (`serializeJSON`) and Apple plist (`serializePlist`). |
| `util.attribute` | Named, typed attributes (`Attribute`, `AttributedObject`) inherited from types to individuals under per-attribute restrictions. |
| `util.command` | Undoable/redoable commands (`Command`, `DoList`). |
| `util.commandParser` | A command-line parser that turns a class's methods into typed commands, taking their help text from docstrings. |
| `util.observer` | Subjects and observers, with changes batched in a `with` block. |
| `util.dirtyable` | A "dirty bit" mix-in for knowing what needs saving. |
| `util.prefs` | Application preferences saved to a file, with change callbacks. |
| `util.abstractGraph` | Graphs whose nodes and relations are persistent objects. |
| `util.errorReportingObject` | A mix-in for objects that validate themselves and report problems. |
| `util.validatedList` | A list that checks each item against a predicate. |
| `util.utils` | Miscellaneous helpers (list utilities, URL handling, docstring inheritance, rectangle geometry, Tk menu-bar and mouse helpers, and more). |
| `util.terminal` | A terminal widget for Tk and a console REPL with the same interface, plus output routing. |
| `util.attributeEditor` | A Tk dialog for viewing and editing an object's attributes. |
| `util.actionDialog`, `util.urlDialog`, `util.tooltip`, `util.rtValuesDialog` | Smaller Tk dialogs and widgets. |

Modules whose names start with `x_` are older versions kept for reference, and
aren't part of the library.

## Requirements

- Python 3.14 or later (the code uses the newer generic syntax, eg:
  `class PRDb[T:PRObject]`).
- Tk (`tkinter`), for the widgets.
- `requests`, `urllib3` and `docstring_parser`.
- `matplotlib`, for `util.rtValuesDialog` only.

## Installing

Either put `src` on your Python path:

```sh
git clone https://github.com/robkremer/pythonUtils.git
export PYTHONPATH="$PWD/pythonUtils/src:$PYTHONPATH"
pip install requests urllib3 docstring_parser
```

or install it with pip:

```sh
pip install git+https://github.com/robkremer/pythonUtils.git
pip install "pythonUtils[rtvalues] @ git+https://github.com/robkremer/pythonUtils.git"  # with matplotlib
```

Semantic Nets expects pythonUtils checked out next to it (as `../pythonUtils`)
and puts its `src` on the path; its packaging script bundles the `util`
package into the Semantic Nets `.pyz` from there.

## Using it

Import from `util`:

```python
from util.persistence.pRef import PRDb, PRObject
from util.attribute import AttributedObject, Attribute
from util.observer import Subject
from util.utils import removeDuplicates
```

Every module gets its logger with `util.getLogger(__name__)`. An application
can supply its own `getLogger()` in its top-level package, which is then used
instead, and should call `util.setupLogger()` before importing anything else
from `util`.

## Tests

The unit tests are in `test/`. Run them from that directory with `src` on the
path:

```sh
cd test
PYTHONPATH=../src python3.14 -m unittest discover -s . -p 'test*.py'
```

(`ant test` does the same, using the Python named in `build.xml`.)

## Documentation

The documentation -- a developer guide and an API reference -- is at
[robkremer.github.io/pythonUtils](https://robkremer.github.io/pythonUtils/).

It's built with Sphinx from `sphinx/source`; it needs Graphviz for the
diagrams. `ant doc` regenerates the API pages from the code and builds the
HTML, and `make html` in `sphinx/` builds it without regenerating them.
`ant publishDocs` builds it and publishes it on GitHub Pages:
`tools/publishDocs.sh` commits the HTML to the `gh-pages` branch, which holds
nothing else, and pushes that (`--no-push` just commits it). The paths to
Python, `sphinx-build` and `dot` in `build.xml`, `sphinx/Makefile` and
`sphinx/source/conf.py` are set for the author's machine and may need
changing.

## License

MIT. See [LICENSE](LICENSE). Copyright (c) 2023-2026 Rob Kremer.
