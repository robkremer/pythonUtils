'''
The XML3 strategy: XML2's compact objects, in a document with a head (see
*SerializationStrategy.tostring()*)::

  <?xml version='1.0' encoding='utf-8'?>
  <document>
    <head>
      <property key="format" value="XML3" />
      <property key="formatVersion" value="1.0" />
      ...
      <property key="type" value="sn.model.model.Model" />
      <property key="url" value="file:///Users/me/family.snm" />
      <property key="objects" type="int" value="137" />
      <property key="superDBs" type="list">
        <item value="sn:/sn" />
        <item value="sn:/baseRules" />
      </property>
      ...
    </head>
    <object type="sn.model.model.Model" id="1"> ... </object>
  </document>

The head is plain: each property's value is a string (*type* "str", left
out), an int, a float, a bool, a list of those (*item* tags), or a table of
them (*property* tags). It can be read without reading the rest of the file
(see *readHead()*). Documents written by the XML and XML2 strategies (an
*object* at the top) are read too.

Created on Oct 12, 2026

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''
#################################################################################
# (c) Copyright 2026, Rob Kremer, MIT open source license.                      #
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
from typing import Any, IO, override
from urllib.parse import unquote
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element
from util.utils import fixURL, urlPath, openFile
from util.persistence.serialize import HEAD, BODY, HeadValue, TAG_KVPAIR, ATTR_TYPE
from util.persistence.serializeXML import ATTR_VALUE, TAG_KEY
from util.persistence.serializeXML2 import XML2SerializationStrategy

TAG_DOCUMENT = "document"
"The top tag of a document."
TAG_HEAD = HEAD
"Its head's tag."
TAG_ITEM = "item"
"An item of a list in the head."

class XML3SerializationStrategy(XML2SerializationStrategy):
  '''
  XML2's compact objects in a document with a head (see the module doc): the
  default strategy.
  '''

  preferred = True
  "Chosen for the \".xml\" extension (it reads what XML and XML2 write, too)."

  @override
  @classmethod
  def protocolName(cls) -> str:
    return "XML3"

  @override
  @classmethod
  def protocolVersion(cls) -> str:
    return "1.0"

  @override
  @classmethod
  def sniff(cls, start:bytes) -> int:
    '''
    :returns: 2 for a document of this format (it starts with a *document*
      tag), 1 for another XML file.
    '''
    if f"<{TAG_DOCUMENT}".encode() in start[:200]:
      return 2
    return 1 if start.lstrip().startswith(b"<") else 0

  # ── The head ──────────────────────────────────────────────────────────────

  @classmethod
  def _headValue(cls, key:str|None, value:HeadValue, tag:str=TAG_KVPAIR) -> Element:
    ''':returns: *value* (see *HeadValue*) as a tag: a property of the head (or an item of a list, or a table, in it).'''
    attrs = {TAG_KEY: key} if key is not None else {}
    if isinstance(value, bool):
      return Element(tag, {**attrs, ATTR_TYPE: "bool", ATTR_VALUE: str(value)})
    if isinstance(value, (int, float)):
      return Element(tag, {**attrs, ATTR_TYPE: type(value).__name__, ATTR_VALUE: repr(value)})
    if isinstance(value, str):
      return Element(tag, {**attrs, ATTR_VALUE: value}) # (a string: its type left out)
    if isinstance(value, (list, tuple)):
      elem = Element(tag, {**attrs, ATTR_TYPE: "list"})
      for v in value:
        elem.append(cls._headValue(None, v, TAG_ITEM))
      return elem
    assert isinstance(value, dict)
    elem = Element(tag, {**attrs, ATTR_TYPE: "dict"})
    for k, v in value.items():
      elem.append(cls._headValue(k, v))
    return elem

  @classmethod
  def _fromHeadValue(cls, elem:Element) -> HeadValue:
    ''':returns: The value of a tag made by *_headValue()*.'''
    typ = elem.attrib.get(ATTR_TYPE, "str")
    text = elem.attrib.get(ATTR_VALUE, "")
    if typ == "str":
      return text
    if typ == "int":
      return int(text)
    if typ == "float":
      return float(text)
    if typ == "bool":
      return text == "True"
    if typ == "list":
      return [cls._fromHeadValue(e) for e in elem.findall(TAG_ITEM)]
    if typ == "dict":
      return {e.attrib.get(TAG_KEY, ""): cls._fromHeadValue(e) for e in elem.findall(TAG_KVPAIR)}
    raise ValueError(f'A head\'s value of type "{typ}"?')

  @classmethod
  def _head(cls, elem:Element) -> dict[str, HeadValue]:
    ''':returns: The values in a *head* tag.'''
    return {e.attrib.get(TAG_KEY, ""): cls._fromHeadValue(e) for e in elem.findall(TAG_KVPAIR)}

  # ── Documents ─────────────────────────────────────────────────────────────

  @override
  def _tostringDocument(self, head:dict[str, HeadValue], body:Element, kwargs:dict[str, Any]) -> str:
    doc = Element(TAG_DOCUMENT) # (its format is in its head)
    headElem = ET.SubElement(doc, TAG_HEAD)
    for key, value in head.items():
      headElem.append(self._headValue(key, value))
    doc.append(body)
    return self._tostring(doc, kwargs)

  @override
  def _documentParts(self, top:Element) -> tuple[dict[str, HeadValue], Element]:
    if top.tag != TAG_DOCUMENT:
      return super()._documentParts(top) # (written by XML or XML2)
    headElem, body = top.find(TAG_HEAD), top.find(BODY)
    if body is None:
      raise ValueError(f'A document with no "{BODY}" in it.')
    return (self._head(headElem) if headElem is not None else {}), body

  @override
  def readHead(self, url:str, mode:str="", **kwargs) -> dict[str, HeadValue]:
    '''
    Only the start of the document is read: up to the end of its head. (A
    document written by XML or XML2 is read as they would be.)
    '''
    url, parsedUrl = fixURL(url, replaceExt=None, mode=mode, extension=self.defaultExtension())
    stream:IO[bytes]
    if parsedUrl.scheme == "file":
      stream = openFile(urlPath(url) or "", "rb")
    else:
      from urllib.request import urlopen
      from urllib.error import HTTPError, URLError
      from util.utils import cachedCopy, REMOTE_TIMEOUT
      try:
        stream = urlopen(url, timeout=REMOTE_TIMEOUT) # (just its head: not kept -- see fetchURL())
      except HTTPError as e:
        e.close()
        if e.code in (404, 410):
          raise FileNotFoundError(f'There\'s nothing at "{url}" (HTTP {e.code}).') from e
        raise
      except (URLError, TimeoutError, ConnectionError):
        copy = cachedCopy(url) # (the server can't be reached: the copy kept when it was last read)
        if copy is None:
          raise
        stream = open(copy, "rb")
    with stream:
      events = ET.iterparse(stream, events=("start", "end"))
      try:
        _, top = next(events)
      except StopIteration:
        raise ValueError(f'"{url}": it\'s empty.')
      if top.tag != TAG_DOCUMENT:
        stream.close()
        return super().readHead(url, mode=mode, **kwargs) # (written by XML or XML2: read as they would be)
      for event, elem in events:
        if event == "end" and elem.tag == TAG_HEAD:
          return self._head(elem)
        if event == "start" and elem.tag == BODY: # (no head)
          return {}
    return {}
