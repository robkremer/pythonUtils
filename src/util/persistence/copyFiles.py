'''
Copying a set of files written by the persistence strategies -- eg: a model,
its views, and the models it builds on -- to another folder, as a unit (see
*Copier*): each copy refers to the other copies, not to the originals; says
where it now is, so it isn't taken to have been copied when it's read (see
*PRDb.readFile()*); and records where it came from (its *previousURL*). The
copies can be put on a web site, too: say where it'll serve them from, and
they say they're there.

What a file refers to is found in its text (see *references()*), without
reading it as objects: so a big model is copied quickly, nothing is loaded,
and a copy is the same as its original, but for its references. A reference is
a string value that's a URL of another file (or of an object in it: "x.snm#12")
-- relative to the file's own (eg: "pets.snm", "../shared/animals.snm") or
absolute ("file:///...", "https://...") -- whose extension is that of one of
the files, or that names an object. (Other strings that merely look like URLs
are left alone.) Only the XML formats are understood (XML, XML2, XML3): files
in other formats are copied as they are.

Created on Nov 18, 2026

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
from __future__ import annotations
import html
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable, Iterator
from urllib.parse import urljoin, urlparse, quote
from util.utils import urlPath, isWindowsPath

FILE_SCHEMES = ("file", "http", "https")
"The schemes of the URLs that are references to files (others -- eg: \"sn:\" -- are names of things in memory)."

_VALUE = re.compile(r'\b(value)="([^"]*)"')
_KEY_OR_VALUE = re.compile(r'\b(key|value)="([^"]*)"')
_OBJECT_PART = re.compile(r"#-?\d+(?:\?name=[^\s\"<>]*)?|\?id=-?\d+(?:&name=[^\s\"<>]*)?|\?name=[^\s\"<>]*")
"What may follow a file's URL in a reference to an object in it (see *PReference.formatForURL()*)."
_REPLACED = re.compile(r'<property key="replacedModels"[^<>]*?(?<!/)>')
'''A table, in a model's head, of the models it replaced and those that
replaced them (eg: sn's *Model.replacedModels*): their URLs, absolute.'''
_HEAD_URL = re.compile(r'^([ \t]*)<property key="url" value="[^"]*" />\r?\n', re.M)
_FIRST_URL = re.compile(r'key="url"(?: type="str")? value="([^"]*)"|key="url">\s*<object type="str" value="([^"]*)"')

def fileURL(path:str) -> str:
  '''
  :param path: A file's path (it needn't be there yet).
  :returns: Its URL, as *fixURL()* makes it -- and so as a file read from
    there is taken to be (see *PRDb.readFile()*): eg, with "%20" for a space,
    and symbolic links followed.
  '''
  return Path(path).resolve().as_uri()

@lru_cache(maxsize=4096)
def _key(url:str) -> str:
  '''
  :returns: What *url* is compared by: for a file on this computer, its path
    (symbolic links followed); else the URL itself.
  '''
  path = urlPath(url)
  return os.path.realpath(path) if path is not None else url

def _escape(value:str) -> str:
  return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

@dataclass
class References:
  '''What a file refers to (see *references()*): files' URLs (without the part
  naming an object), each with how many references there are to it.'''
  local:dict[str, int] = field(default_factory=dict)
  "Files on this computer that are there."
  missing:dict[str, int] = field(default_factory=dict)
  "Files on this computer that aren't there."
  web:dict[str, int] = field(default_factory=dict)
  "Files elsewhere (eg: \"https:...\"): not looked for."
  adjustable:bool = True
  "Whether the file's in a format whose references can be adjusted (an XML one); if not, nothing's found in it."

class _File:
  '''A file being looked through (see *references()*) or copied (see *Copier*).'''

  def __init__(self, path:str, text:str|None, extensions:set[str]):
    self.path = path
    self.url = fileURL(path)
    "Where it is."
    self.text = text
    "What's in it; None if it isn't in an XML format."
    self.extensions = extensions
    self.stored:str|None = None
    "The URL written in it: where it was when it was saved."
    if text is not None:
      m = _FIRST_URL.search(text)
      if m:
        self.stored = html.unescape(m.group(1) if m.group(1) is not None else m.group(2))
    self._exists:dict[str, bool] = {}
    self._resolved:dict[str, tuple[str, str]|None] = {} # (see resolve())

  @classmethod
  def read(cls, path:str, extensions:set[str]) -> _File:
    with open(path, "rb") as f:
      data = f.read()
    try:
      text:str|None = data.decode("utf-8")
    except UnicodeDecodeError:
      text = None
    if text is not None and not text.lstrip("\ufeff \t\r\n").startswith("<"):
      text = None # (not XML: eg, JSON)
    return cls(path, text, extensions)

  def exists(self, url:str) -> bool:
    if url not in self._exists:
      path = urlPath(url)
      self._exists[url] = path is not None and os.path.isfile(path)
    return self._exists[url]

  def resolve(self, value:str, isMember:Callable[[str], bool]=lambda u: False) -> tuple[str, str, str]|None:
    '''
    :param value: A string value in the file.
    :param isMember: Whether a file's URL is of one of the files being copied.
    :returns: If *value* is a reference to a file (see the module's notes):
      the file's URL (absolute), what follows it in *value* (eg: "#12"), and
      the part of *value* before that, if it's relative (else ""). Else None.
      A relative reference is taken relative to where the file is; but if
      there's nothing there, and it was copied from somewhere else, relative
      to where it was (as *PRDb.absoluteURL()* takes it).
    '''
    if not value or value[0] in "#?$~/\\" or isWindowsPath(value):
      return None
    cut = min((i for i in (value.find("#"), value.find("?")) if i >= 0), default=len(value))
    where, rest = value[:cut], value[cut:]
    if rest and not _OBJECT_PART.fullmatch(rest):
      return None
    if where[0] == ":" or any(c in where for c in '"<>\n\r\t'):
      return None # (eg: text that has a "#" in it)
    ext = os.path.splitext(urlparse(where).path)[1]
    if not ext or (not rest and ext not in self.extensions):
      return None
    if " " in where and not urlparse(where).scheme:
      return None # (a relative URL is written quoted: "%20" for a space)
    if where not in self._resolved:
      self._resolved[where] = self._resolveFile(where, isMember)
    found = self._resolved[where]
    return None if found is None else (found[0], rest, found[1])

  def _resolveFile(self, where:str, isMember:Callable[[str], bool]) -> tuple[str, str]|None:
    ''':returns: For *resolve()*: the URL of the file *where* is of, and *where* if it's relative (else ""); or None.'''
    scheme = urlparse(where).scheme.lower()
    if scheme and scheme not in FILE_SCHEMES:
      return None
    moved = bool(self.stored) and self.stored != self.url
    if scheme:
      url, relative = where, ""
      if moved and _key(url) != _key(self.stored or ""): # (as PRDb._relocate() takes it: a file that was next to it is the one next to it now, if it's there)
        old, new = (self.stored or "").rsplit("/", 1)[0], self.url.rsplit("/", 1)[0]
        if url.startswith(old + "/") and "/" not in url[len(old) + 1:]:
          candidate = new + url[len(old):]
          if isMember(candidate) or self.exists(candidate):
            url = candidate
    else:
      url, relative = urljoin(self.url, where), where
      if moved and not isMember(url) and not self.exists(url):
        alt = urljoin(self.stored or "", where)
        if isMember(alt) or self.exists(alt):
          url = alt
    if moved and _key(url) == _key(self.stored or ""):
      url = self.url # (itself: where it is now)
    return url, relative

  def values(self) -> Iterator[tuple[re.Match, str, str]]:
    '''
    :returns: The string values in it that may be references (see the
      module's notes): each with its match (*_VALUE*'s, or *_KEY_OR_VALUE*'s,
      group 2 the value: as it's written), its value, and what it is:
      "replaced" (in a table of replaced models -- see *_REPLACED* -- a key or
      a value: an absolute URL), "previous" (where it was copied from), or
      "value" (anything else).
    '''
    text = self.text
    if text is None:
      return
    blocks:list[tuple[int, int]] = []
    for m in _REPLACED.finditer(text):
      end = text.find("</property>", m.end())
      end = len(text) if end < 0 else end
      blocks.append((m.start(), end))
      for a in _KEY_OR_VALUE.finditer(text, m.end(), end):
        yield a, html.unescape(a.group(2)), "replaced"
    for m in _VALUE.finditer(text):
      raw = m.group(2)
      if "." not in raw and ":" not in raw:
        continue # (quickly: not a reference)
      if blocks and any(s <= m.start() < e for s, e in blocks):
        continue
      yield m, html.unescape(raw), "previous" if self._isPreviousURL(m.start()) else "value"

  def _isPreviousURL(self, at:int) -> bool:
    '''
    :returns: Whether the value at *at* is where the file was copied from: in
      a tag with key="previousURL", or in the object in one (as the XML
      format writes it).
    '''
    assert self.text is not None
    start = self.text.rfind("<", 0, at)
    if 'key="previousURL"' in self.text[start:at]:
      return True
    return self.text[max(0, start - 100):start].rstrip().endswith('<property key="previousURL">')

  def references(self) -> References:
    ''':returns: What it refers to (see *references()*).'''
    ret = References(adjustable=self.text is not None)
    own = {_key(self.url)} | ({_key(self.stored)} if self.stored else set())
    for _m, value, kind in self.values():
      if kind != "value":
        continue
      found = self.resolve(value)
      if found is None or _key(found[0]) in own:
        continue
      url = found[0]
      table = ret.web if urlPath(url) is None else ret.local if self.exists(url) else ret.missing
      table[url] = table.get(url, 0) + 1
    return ret

def references(path:str, extensions:Iterable[str]) -> References:
  '''
  :param path: A file written by one of the persistence strategies (eg: a
    model or a view).
  :param extensions: The extensions of the files that may be referred to
    without naming an object in them (eg: ".snm"): only strings ending in one
    of those -- or naming an object -- are taken to be references.
  :returns: The files it refers to (not itself), each with how many references
    there are to it. Nothing's found in a file that isn't in an XML format.
  '''
  return _File.read(path, set(extensions)).references()

def layout(sources:Iterable[str], folder:str, base:str|None=None) -> dict[str, str]:
  '''
  Where to put copies of *sources* in *folder*: those in *base* (or in a
  folder below it) keep their places relative to it -- eg, "views/a.snv" --
  and the others go in *folder* itself. Two that would be in the same place
  are told apart by " 2", " 3", ... after their names.

  :param sources: The files' paths.
  :param folder: The folder to put the copies in.
  :param base: A folder: by default, that of the first of *sources*.
  :returns: Each of *sources*: where its copy goes.
  '''
  sources = list(sources)
  if base is None:
    base = os.path.dirname(sources[0]) if sources else folder
  base = os.path.realpath(base)
  ret:dict[str, str] = {}
  taken:set[str] = set()
  for src in sources:
    real = os.path.realpath(src)
    rel = os.path.relpath(real, base)
    if rel.startswith(os.pardir + os.sep) or rel == os.pardir or os.path.isabs(rel):
      rel = os.path.basename(src)
    dst = os.path.join(folder, rel)
    stem, ext = os.path.splitext(dst)
    n = 1
    while os.path.normcase(dst) in taken:
      n += 1
      dst = f"{stem} {n}{ext}"
    taken.add(os.path.normcase(dst))
    ret[src] = dst
  return ret

@dataclass
class Copied:
  '''What *Copier.run()* did with one file.'''
  source:str
  "The original's path."
  copy:str
  "The copy's path."
  references:int = 0
  "How many of its references were changed."
  adjusted:bool = True
  "Whether it's in a format whose references could be adjusted; if not, it was copied as it is."

class Copier:
  '''
  Copies of a set of files (see the module's notes): eg,

  >>> copier = Copier(layout(files, "/Users/me/web"), servedFrom="https://example.org/models/")
  >>> copier.outside() # (what they refer to that isn't being copied)
  >>> copier.run()
  '''

  def __init__(self, plan:dict[str, str], extensions:Iterable[str]|None=None, servedFrom:str|None=None,
               folder:str|None=None):
    '''
    :param plan: The files to copy (paths), each with where its copy goes.
    :param extensions: As for *references()*: by default, those of the files
      in *plan*.
    :param servedFrom: If the copies are to be put on a web site: the URL
      *folder* will be there (eg: "https://example.org/models/"). Each copy
      says it's at its place under it, rather than where it's copied to.
    :param folder: The folder the copies go in (by default: the folder of
      the first of them): needed with *servedFrom*.
    :raises ValueError: If two files would be copied to the same place, or a
      file onto itself; or a copy isn't in *folder*, with *servedFrom*.
    '''
    self.plan = dict(plan)
    self.extensions = set(extensions) if extensions is not None else {os.path.splitext(p)[1] for p in self.plan}
    self.servedFrom = servedFrom.rstrip("/") + "/" if servedFrom else None
    self.folder = folder if folder is not None else os.path.dirname(next(iter(self.plan.values()), "") or ".")
    copies:dict[str, str] = {}
    for src, dst in self.plan.items():
      k = os.path.normcase(os.path.realpath(dst))
      if k == os.path.normcase(os.path.realpath(src)):
        raise ValueError(f'"{src}" would be copied onto itself.')
      if k in copies:
        raise ValueError(f'"{copies[k]}" and "{src}" would both be copied to "{dst}".')
      copies[k] = src
    self._members:dict[str, str] = {_key(fileURL(src)): src for src in self.plan}
    self._references:dict[str, References] = {}
    for src in self.plan:
      self.ownURL(src) # (with servedFrom: each copy's in folder)

  def isMember(self, url:str) -> bool:
    ''':returns: Whether *url* is of one of the files being copied.'''
    return _key(url) in self._members

  def copyURL(self, source:str) -> str:
    ''':returns: Where the copy of *source* (one of the files being copied) will be.'''
    return fileURL(self.plan[source])

  def ownURL(self, source:str) -> str:
    '''
    :returns: Where the copy of *source* is to say it is: where it will be;
      or, if it's to be put on a web site, where it'll be there (see
      *servedFrom*).
    '''
    if not self.servedFrom:
      return self.copyURL(source)
    rel = os.path.relpath(os.path.realpath(self.plan[source]), os.path.realpath(self.folder))
    if rel.startswith(os.pardir) or os.path.isabs(rel):
      raise ValueError(f'"{self.plan[source]}" isn\'t in "{self.folder}", which is served from "{self.servedFrom}".')
    return urljoin(self.servedFrom, quote(rel.replace(os.sep, "/")))

  def references(self, source:str) -> References:
    ''':returns: What *source* (one of the files being copied) refers to (see *references()*).'''
    if source not in self._references:
      file = _File.read(source, self.extensions)
      self._references[source] = file.references()
    return self._references[source]

  def outside(self) -> dict[str, dict[str, int]]:
    '''
    :returns: For each file being copied that refers to files on this computer
      that aren't being copied: those files' URLs, each with how many
      references there are to it. The copies refer to them where they are --
      so they're found on this computer, but not elsewhere (eg: on a web site).
    '''
    ret:dict[str, dict[str, int]] = {}
    for src in self.plan:
      refs = {u: n for u, n in self.references(src).local.items() if not self.isMember(u)}
      if refs:
        ret[src] = refs
    return ret

  def run(self, progress:Callable[[str, int, int], None]|None=None) -> list[Copied]:
    '''
    Copy the files (see *Copier*). Each copy is written whole, then put in
    place: if one can't be written, it's not left half written (those
    already copied are kept).

    :param progress: Called before each file is copied: with its path, how
      many have been copied, and how many there are.
    :returns: What was done with each file.
    :raises OSError: If a file can't be read, or its copy written.
    '''
    ret:list[Copied] = []
    total = len(self.plan)
    for i, (src, dst) in enumerate(self.plan.items()):
      if progress is not None:
        progress(src, i, total)
      os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
      file = _File.read(src, self.extensions)
      if file.text is None:
        shutil.copyfile(src, dst)
        ret.append(Copied(src, dst, adjusted=False))
        continue
      text, changed = self._rewrite(file)
      fd, tmp = tempfile.mkstemp(dir=os.path.dirname(dst) or ".", prefix=".copying-", suffix=os.path.splitext(dst)[1])
      try:
        with os.fdopen(fd, "wb") as f:
          f.write(text.encode("utf-8"))
        os.replace(tmp, dst)
      except BaseException:
        try:
          os.unlink(tmp)
        except OSError:
          pass
        raise
      ret.append(Copied(src, dst, references=changed))
    return ret

  # ── Adjusting a copy's references ─────────────────────────────────────────

  def _rewrite(self, file:_File) -> tuple[str, int]:
    '''
    :returns: The text of the copy of *file*, and how many of its references
      were changed (not counting its own URL, nor where it came from).
    '''
    assert file.text is not None
    text = file.text
    src = file.path
    copyURL, ownURL = self.copyURL(src), self.ownURL(src)
    edits:list[tuple[int, int, str]] = [] # (start, end, the new text)
    changed = 0
    previous = False
    for m, value, kind in file.values():
      if kind == "replaced": # (absolute URLs of models: of the copies' places, if they're being copied)
        new = self.ownURL(self._members[_key(value)]) if self.isMember(value) else value
      elif kind == "previous":
        previous = True
        new = file.url
      elif value == file.stored:
        new = ownURL
      else:
        new = self._newReference(file, value, copyURL) or value
        changed += new != value
      if new != value:
        edits.append((m.start(2), m.end(2), _escape(new)))
    if not previous: # (where it came from: in the head, after its URL)
      head = text.find("</head>")
      if head >= 0:
        m = _HEAD_URL.search(text, 0, head)
        if m:
          edits.append((m.end(), m.end(), f'{m.group(1)}<property key="previousURL" value="{_escape(file.url)}" />\n'))
    out:list[str] = []
    at = 0
    for start, end, new in sorted(edits):
      out.append(text[at:start])
      out.append(new)
      at = end
    out.append(text[at:])
    return "".join(out), changed

  def _newReference(self, file:_File, value:str, copyURL:str) -> str|None:
    '''
    :param value: A string value in *file*.
    :returns: What it's to be in the copy, if it's a reference: to the copy of
      a file being copied, relative to the copy; to a file that isn't, as it
      is, or absolute if it was relative to the original (so it's still
      found). None if it isn't a reference, or it's as it was.
    '''
    found = file.resolve(value, self.isMember)
    if found is None:
      return None
    url, rest, relative = found
    cache = file.__dict__.setdefault("_newWhere", {})
    key = (url, relative)
    if key not in cache:
      cache[key] = self._newWhere(file, url, relative, copyURL)
    new = cache[key]
    return None if new is None else new + rest

  def _newWhere(self, file:_File, url:str, relative:str, copyURL:str) -> str|None:
    '''
    :returns: For *_newReference()*: what the part of a reference naming the
      file *url* (as *relative*, if it's relative) is to be in the copy; or
      None if it's as it was.
    '''
    from util.persistence.pRef import PRDb
    member = self._members.get(_key(url))
    if member is not None:
      target = self.copyURL(member)
      if relative and _key(urljoin(copyURL, relative)) == _key(target):
        return None # (it's still right)
      return PRDb.relativeURL(target, base=copyURL, keep={target})
    if relative and urlPath(url) is not None and file.exists(url) and _key(urljoin(copyURL, relative)) != _key(url):
      return url # (a file that isn't copied, near the original: absolute)
    return None
