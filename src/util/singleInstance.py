'''
One copy of a program at a time (per user): a second copy, started to open some
files (eg: a document double-clicked in Explorer or the file manager), hands them
to the copy that's running and quits. On the Mac this isn't needed -- the Finder
sends a running app the documents to open itself (Tk's *::tk::mac::OpenDocument*)
-- but on Windows and Linux each double-click starts a new copy.

The running copy listens on a socket on this computer only (127.0.0.1), whose
port, and a secret the other copies must send with their files, are in a file in
a folder of the user's own (eg: ~/.sn). Use::

  instance = SingleInstance("sn", folder)
  if instance.handOff(sys.argv[1:]):
    sys.exit(0)             # the running copy has them
  root = tk.Tk()
  instance.listen(root, openFiles) # openFiles(paths) is called in Tk's thread

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''
from __future__ import annotations
import json
import logging
import os
import secrets
import socket
import threading
from queue import Queue, Empty
from typing import Any, Callable

logger = logging.getLogger(__name__)

class SingleInstance:
  '''Hands a second copy's files to the running copy (see the module doc).'''

  TIMEOUT = 2.0
  "How long (seconds) a second copy waits for the running one to answer."
  POLL_MS = 200
  "How often (milliseconds) the running copy looks for files handed to it."

  def __init__(self, name:str, folder:str):
    '''
    :param name: The program's (short) name: the port file is *folder/<name>.port*.
    :param folder: A folder of the user's own, for the port file (made if it isn't there).
    '''
    self.portFile = os.path.join(folder, f"{name}.port")
    self.folder = folder
    self._server:socket.socket|None = None
    self._received:Queue[list[str]] = Queue()

  def handOff(self, args:list[str]) -> bool:
    '''
    If a copy of the program is running, give it *args* (the files to open:
    made absolute, as this copy's current folder may not be its).

    :returns: Whether a running copy took them: if so, this one should quit.
    '''
    try:
      with open(self.portFile, encoding="utf-8") as f:
        port, secret = f.read().split()
      with socket.create_connection(("127.0.0.1", int(port)), timeout=self.TIMEOUT) as conn:
        paths = [a if "://" in a else os.path.abspath(a) for a in args]
        conn.sendall(json.dumps({"secret": secret, "args": paths}).encode("utf-8") + b"\n")
        return conn.makefile("rb").readline().strip() == b"ok"
    except (OSError, ValueError):
      return False

  def listen(self, root:Any, onArgs:Callable[[list[str]], None]) -> None:
    '''
    Be the running copy: take the files later copies hand over, and call
    *onArgs* with them -- in Tk's thread, from *root*'s event loop.

    :param root: The Tk root (or any widget that lasts as long as the program).
    :param onArgs: Called with each later copy's files (perhaps none: then it
      was just started again -- eg, show a window).
    '''
    secret = secrets.token_hex(16)
    try:
      server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      server.bind(("127.0.0.1", 0))
      server.listen(5)
      os.makedirs(self.folder, exist_ok=True)
      fd = os.open(self.portFile + ".part", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
      with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(f"{server.getsockname()[1]} {secret}\n")
      os.replace(self.portFile + ".part", self.portFile)
    except OSError:
      logger.warning("Can't listen for other copies of the program: each will run on its own.", exc_info=True)
      return
    self._server = server
    threading.Thread(target=self._serve, args=(server, secret), name="SingleInstance", daemon=True).start()
    def poll() -> None:
      try:
        while True:
          onArgs(self._received.get_nowait())
      except Empty:
        pass
      root.after(self.POLL_MS, poll)
    root.after(self.POLL_MS, poll)

  def _serve(self, server:socket.socket, secret:str) -> None:
    while True:
      try:
        conn, _ = server.accept()
      except OSError: # (closed)
        return
      with conn:
        try:
          conn.settimeout(self.TIMEOUT)
          message = json.loads(conn.makefile("rb").readline() or b"{}")
          if not secrets.compare_digest(str(message.get("secret", "")), secret):
            continue
          self._received.put([str(a) for a in message.get("args", [])])
          conn.sendall(b"ok\n")
        except (OSError, ValueError):
          continue

  def close(self) -> None:
    '''Stop listening (eg: when the program quits), and remove the port file if it's this copy's.'''
    if self._server is None:
      return
    port = self._server.getsockname()[1]
    self._server.close()
    self._server = None
    try:
      with open(self.portFile, encoding="utf-8") as f:
        if f.read().split()[0] == str(port):
          os.remove(self.portFile)
    except (OSError, IndexError):
      pass
