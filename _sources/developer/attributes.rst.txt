
Attributes
==========

:py:mod:`util.attribute` gives objects named, typed values -- *attributes* --
that are inherited down a type hierarchy, the way a class's members are
inherited by its subclasses and instances, but at run time and under rules you
set per attribute.

Attributes and attributed objects
---------------------------------

An :py:class:`~util.attribute.Attribute` is a value with:

- a **type**: a Python type, or the name of one of the *known types* --
  ``int``, ``float``, ``bool``, ``str``, ``text`` and ``mtext`` (multi-line
  text), ``color``, ``list``, ``dict``, ``attrs``, or ``choices[...]`` (one of
  a list of values). The names tell an editor how to edit the value (see
  :doc:`widgets`);
- a **restriction** on how it's inherited (below);
- a **note**: a description, shown as a tooltip by the attribute editor.

An :py:class:`~util.attribute.AttributedObject` is a dict of attributes, by
name, that also inherits attributes from its *supertypes*. A subclass says what
those are, and whether the object is a type or an individual (an instance), by
overriding :py:meth:`~util.attribute.AttributedObject.getSupers` and
:py:meth:`~util.attribute.AttributedObject.isIndividual`. Then:

- ``obj.get(key)`` is the attribute's *effective* value: the object's own,
  or else the one it inherits (searching its supertypes in order);
- ``obj.getLocal(key)`` and ``obj.getInh(key)`` give just one or the other;
- ``obj[key] = value`` sets the object's own value.

``get()`` can also store a default -- ``obj.get(key, storeDefault=v,
storeType=t, note=...)`` -- which is how an application declares its
attributes (and preferences: see :doc:`utilities`) as it first uses them.

An *AttributedObject* is a :py:class:`~util.observer.Subject`: it announces
``"new attribute"``, ``"mod attribute"`` and ``"del attribute"``, so that,
eg: the drawing of an object can follow its attributes. It's
:py:class:`~util.persistence.serialize.Serializable` and
:py:class:`~util.dirtyable.Dirtyable` too.

Inheritance restrictions
------------------------

A :py:class:`~util.attribute.Restriction` holds two
:py:class:`~util.attribute.RestrictionTypes` flags: one for how *individuals*
inherit the attribute, and one for how *subtypes* do:

``NOINHERIT``
  The key is inherited, but not the value: it's a slot that must be filled
  locally.
``NOOVERRIDE``
  The inherited value can't be overridden.
``PRIVATE``
  The attribute isn't inherited at all.

The useful combinations have names:

======================  ==============  ==============  ===========================================
restriction             individuals     subtypes        eg
======================  ==============  ==============  ===========================================
``VAR_DEFAULTED``       inherit         inherit         a default that anything may change
``VAR``                 must fill in    inherit         an object's name
``CONST_TYPEOVERRIDE``  can't change    inherit         a constant that subtypes may change
``CONST``               can't change    can't change    a constant
``UNINHERITED``         must fill in    must fill in    a slot everything below must fill
``TYPENAME``            can't change    must fill in    the name of a type
``TYPEONLY``            don't see it    inherit         something only for types
``LOCAL``               don't see it    don't see it    only for the object itself
======================  ==============  ==============  ===========================================

(Some combinations make no sense, and are refused: see
:py:meth:`~util.attribute.Restriction.legalityError`.)

The attribute editor
--------------------

:py:mod:`util.attributeEditor` edits an *AttributedObject*'s attributes in a
dialog: their values, types and restrictions, with the values they inherit
shown above them -- see :doc:`widgets`.
