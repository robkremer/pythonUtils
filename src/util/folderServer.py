'''
Showing a folder of web pages (eg: Sphinx documentation) in the user's web
browser through a small web server on this computer (*serveFolder()*,
*openInBrowser()*), rather than as file: URLs: browsers restrict what a
file: page may load (Safari won't load a page's stylesheets, scripts or
images from its parent folder, eg: "../_static/"), so such pages show
unstyled.

The server only listens on 127.0.0.1, serves only the folder's files, runs
in a daemon thread, and stops when the program ends.

Created on Oct 29, 2026

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
import os
import threading
import functools
import webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import quote

class _QuietHandler(SimpleHTTPRequestHandler):
  'Serves the files, without logging each request to stderr.'
  def log_message(self, format, *args) -> None:
    pass

_servers:dict[str, ThreadingHTTPServer] = {}
"The servers started by *serveFolder()*, by folder (its real path)."
_lock = threading.Lock()

def serveFolder(folder:str) -> str:
  '''
  Serve *folder* on this computer (once: later calls for the same folder
  reuse the server).

  :param folder: The folder whose files are served.
  :return: The server's URL for the folder, ending in "/": eg: "http://127.0.0.1:52345/".
  '''
  folder = os.path.realpath(folder)
  if not os.path.isdir(folder):
    raise FileNotFoundError(f'Not a folder: "{folder}"')
  with _lock:
    server = _servers.get(folder)
    if server is None:
      server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_QuietHandler, directory=folder))
      server.daemon_threads = True
      threading.Thread(target=server.serve_forever, name=f"serveFolder {folder}", daemon=True).start()
      _servers[folder] = server
  return f"http://127.0.0.1:{server.server_address[1]}/"

def folderURL(folder:str, page:str="") -> str:
  '''
  :param folder: A folder, served by *serveFolder()*.
  :param page: A file in it, relative to the folder, with "/" separators (eg: "user/index.html").
  :return: The URL that shows *page* from the server for *folder* (starting it if need be).
  '''
  return serveFolder(folder) + quote(page.lstrip("/"))

def openInBrowser(folder:str, page:str="index.html") -> str:
  '''
  Show *page* from *folder* in the user's web browser, through the server for
  *folder* (see *serveFolder()*).

  :param folder: The folder (eg: the top of a Sphinx build's html).
  :param page: The page, relative to the folder, with "/" separators (eg: "user/index.html").
  :return: The URL opened.
  '''
  url = folderURL(folder, page)
  webbrowser.open(url)
  return url

def stopServing(folder:str|None=None) -> None:
  '''
  Stop the server for *folder*, or every server if it's None (for tests: the
  servers stop by themselves when the program ends).
  '''
  with _lock:
    folders = list(_servers) if folder is None else [os.path.realpath(folder)]
    for f in folders:
      server = _servers.pop(f, None)
      if server is not None:
        server.shutdown()
        server.server_close()
