
Persistence
===========

:py:mod:`util.persistence` saves objects to files and reads them back, with
their references to one another intact -- including references from one file
to another. It's in two layers:

:py:mod:`util.persistence.serialize`
  Writing and reading *objects*: any structure of ints, floats, strings,
  lists, tuples, sets, dicts and :py:class:`~util.persistence.serialize.Serializable`
  objects, in one of several formats.

:py:mod:`util.persistence.pRef`
  *Databases* of objects: a file is a :py:class:`~util.persistence.pRef.PRDb`
  of :py:class:`~util.persistence.pRef.PRObject`\ s, each with an id, which
  refer to each other -- and to objects in other files -- with
  :py:class:`~util.persistence.pRef.PReference`\ s.

Serialization
-------------

A :py:class:`~util.persistence.serialize.SerializationStrategy` writes and
reads one format. There are four, each in a module of its own:

=======  ============================================================  =========
name     module                                                        extension
=======  ============================================================  =========
XML2     :py:mod:`~util.persistence.serializeXML2` (the default)       .xml
XML      :py:mod:`~util.persistence.serializeXML` (the original)       .xml
JSON     :py:mod:`~util.persistence.serializeJSON`                     .json
plist    :py:mod:`~util.persistence.serializePlist`                    .plist
=======  ============================================================  =========

The class methods are the usual way in::

  SerializationStrategy.writex(url, obj)          # in DEFAULT_STRATEGY's format
  obj = SerializationStrategy.readx(url)          # whichever format it's in

Reading tries the strategies in turn -- the ones for the file's extension
first, then the preferred ones -- so files in any of the formats can be read;
:py:meth:`~util.persistence.serialize.SerializationStrategy.peekTypex` finds
out what's in a file without reading it all. *XML2* writes simple values and
references as XML attributes, rather than elements of their own, which makes
its files around 40% smaller than *XML*'s.

An object referred to more than once is written once; later references to it
are written by its id, so that after reading, ``a is b`` is still true if it
was before.

Making a class serializable
~~~~~~~~~~~~~~~~~~~~~~~~~~~

A class is serializable if it inherits from
:py:class:`~util.persistence.serialize.Serializable` and says how to rebuild
an instance, in
:py:meth:`~util.persistence.serialize.Serializable.getInstantiationInfo`.
That returns an :py:class:`~util.persistence.serialize.InstantiationInfo`
made of:

- **constructor arguments** -- ``conArgs`` and ``conKWArgs``: what to pass to
  the class to make the object;
- **post-construction setters** -- ``postconSetters``: properties set once
  it's made (other objects in the file may not exist yet);
- **final setters** -- ``finalSetters``: run once the whole file has been
  read, when every object it refers to exists.

Each item is a :py:class:`~util.persistence.serialize.ParamInfo` or
:py:class:`~util.persistence.serialize.PropertyInfo`: a name, a type, and
(optionally) a getter and setter, so a class can save its state in whatever
form suits it, not just as its attributes. A subclass usually starts from its
parent's *InstantiationInfo* and adds to it.

Databases of objects
--------------------

A :py:class:`~util.persistence.pRef.PRDb` is a dict-like container of
:py:class:`~util.persistence.pRef.PRObject`\ s, kept in a file (named by a
URL). Each object registers itself with its database when it's made, which
gives it an integer id; it may also have a name. Look objects up by either:
``db[12]`` or ``db["fred"]``.

- ``PRDb.getDB(url)`` returns the database at *url*: the one in memory if
  it's open already, or else read from the file. Open databases are kept in
  ``PRDb.AllDBs``, so every reference to a file finds the same database.
- ``db.save()`` writes it, in ``DEFAULT_STRATEGY``'s format unless told
  otherwise. A database is :py:class:`~util.dirtyable.Dirtyable`: it knows
  whether it's changed since it was last saved. A database can be
  *write-locked*.
- A database is a :py:class:`~util.observer.Subject`: it announces objects
  added (``"new"``) and removed (``"del"``), so views of it can keep up (see
  :doc:`observer`).

References
~~~~~~~~~~

A :py:class:`~util.persistence.pRef.PReference` refers to an object (or a
whole database) without needing it to be loaded: it's resolved -- the file
read if need be -- when it's called. Its text forms are:

=============================  ==============================================
``file:///a/b/pets.snm#12``    object 12 in that file
``file:///a/b/pets.snm#fred``  the object named *fred* in it
``#12``, ``#fred``, ``fred``   relative: in the current database
``file:///a/b/pets.snm``       the whole database
``$pets``                      an open database, by its name
=============================  ==============================================

Copied and moved files
~~~~~~~~~~~~~~~~~~~~~~

References between files are written *relative* to the file being written
when the target is close by -- in the same folder, below it, or at most
``PRDb.MAX_UP`` (2) folders up -- so a folder of files can be moved or copied
as a block. Further afield, they're absolute.

Each file's header records the URL it was saved to (and the one before
that). :py:meth:`PRDb.readFile() <util.persistence.pRef.PRDb.readFile>`
notices when a file is read from somewhere else (it's been copied or moved),
takes it to be where it now is -- never confusing it with the original, which
may be open too -- and reports it. A relative reference that isn't found next
to a copied file is looked for where the original was.
