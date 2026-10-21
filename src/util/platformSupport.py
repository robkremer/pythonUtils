'''
What's done differently on macOS, Windows and Linux: the key shortcuts are made
with (Command on the Mac, Control elsewhere), showing a file in the Finder (or
Explorer, or the file manager), moving a file to the Trash (or Recycle Bin),
putting a picture on the clipboard, where logs go, and the like. A program asks
this module, rather than testing *sys.platform* itself.

Nothing here imports the rest of *util*, so anything in it can use this.

.. codeauthor:: Rob Kremer <robkremer@me.com>
'''
from __future__ import annotations
import os
import sys
import shutil
import subprocess
from typing import Any, Optional

MAC = sys.platform == "darwin"
"Whether this is macOS."
WINDOWS = sys.platform == "win32"
"Whether this is Windows."
LINUX = not (MAC or WINDOWS)
"Whether this is Linux (or another Unix with X11 or Wayland)."

################################################################################
# ---- Key shortcuts -----------------------------------------------------------
################################################################################

SHORTCUT = "Command" if MAC else "Control"
'''The Tk modifier key shortcuts are made with: eg, ``f"<{SHORTCUT}-KeyPress-z>"``.
(Tk accepts "Command" off the Mac too, but no key there makes it.)'''
SHORTCUT_LABEL = "Command" if MAC else "Ctrl"
"*SHORTCUT*'s name in a menu item's accelerator (Tk on the Mac shows \"Command\" as ⌘)."
ALT = "Option" if MAC else "Alt"
"The Tk modifier for the Option key (on the Mac) or Alt (elsewhere)."
ALT_LABEL = "Option" if MAC else "Alt"
"*ALT*'s name in a menu item's accelerator."

_KEY_LABELS = {"equal": "+", "plus": "+", "minus": "-", "comma": ",", "period": ".", "slash": "/",
               "BackSpace": "Backspace", "Delete": "Delete", "Escape": "Esc", "Return": "Return"}

def shortcut(key:str, shift:bool=False, alt:bool=False, label:Optional[str]=None) -> tuple[str, str]:
  '''
  A key shortcut: *key* with Command (on the Mac) or Control (elsewhere).

  :param key: The key's Tk keysym, eg: "z", "equal", "0". With *shift*, give
    the shifted keysym (eg: "Z").
  :param shift: Whether it's with Shift too.
  :param alt: Whether it's with Option (Alt) too.
  :param label: How the key's shown in the accelerator (by default: *key*,
    upper-cased, or eg "+" for "equal").
  :returns: (the Tk event sequence to bind, the menu accelerator): eg, for "z",
    ("<Command-KeyPress-z>", "Command-Z") on the Mac and ("<Control-KeyPress-z>",
    "Ctrl+Z") elsewhere.
  '''
  mods = (["Shift"] if shift else []) + ([ALT] if alt else []) + [SHORTCUT]
  labels = (["Shift"] if shift else []) + ([ALT_LABEL] if alt else []) + [SHORTCUT_LABEL]
  shown = label if label is not None else _KEY_LABELS.get(key, key.upper() if len(key) == 1 else key)
  return f"<{'-'.join(mods)}-KeyPress-{key}>", ("-" if MAC else "+").join(labels + [shown])

def altKey(key:str, label:Optional[str]=None) -> tuple[str, str]:
  '''
  :returns: (the Tk event sequence, the menu accelerator) for *key* with Option
    (on the Mac) or Alt (elsewhere): eg, ("<Alt-KeyPress-v>", "Alt+V").
  '''
  shown = label if label is not None else _KEY_LABELS.get(key, key.upper() if len(key) == 1 else key)
  return f"<{ALT}-KeyPress-{key}>", ("-" if MAC else "+").join([ALT_LABEL, shown])

################################################################################
# ---- Files -------------------------------------------------------------------
################################################################################

def _launch(cmd:list[str]) -> None:
  subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def openFile(path:str) -> None:
  '''
  Open *path* (a file or folder) as if it were double-clicked: a folder in the
  Finder (Explorer, the file manager), a file in its application.

  :raises OSError: If it can't be.
  '''
  if WINDOWS:
    os.startfile(path) # type: ignore[attr-defined] # @UndefinedVariable
  elif MAC:
    _launch(["open", path])
  else:
    opener = shutil.which("xdg-open") or shutil.which("gio")
    if opener is None:
      raise OSError(f'Can\'t open "{path}": there\'s no xdg-open (or gio) to open it with.')
    _launch([opener, path] if not opener.endswith("gio") else [opener, "open", path])

def reveal(path:str) -> None:
  '''
  Show *path* in the Finder (Explorer, the file manager): a file selected in its
  folder (on Linux, its folder is opened), a folder opened.

  :raises OSError: If it can't be.
  '''
  if os.path.isdir(path):
    openFile(path)
  elif MAC:
    _launch(["open", "-R", path])
  elif WINDOWS:
    _launch(["explorer", "/select," + os.path.normpath(path)])
  else:
    openFile(os.path.dirname(path) or ".")

TRASH_NAME = "Recycle Bin" if WINDOWS else "Trash"
"What the place deleted files go is called here."

def moveToTrash(path:str) -> None:
  '''
  Move a file (or folder) to the Trash -- the Recycle Bin, on Windows -- where it
  can be put back from.

  :raises OSError: If it can't be moved there (nothing's deleted then).
  '''
  path = os.path.abspath(path)
  if not os.path.lexists(path):
    raise FileNotFoundError(f'There\'s no "{path}" to move to the {TRASH_NAME}.')
  if MAC:
    _trashMac(path)
  elif WINDOWS:
    _trashWindows(path)
  else:
    _trashFreedesktop(path)

def _trashMac(path:str) -> None:
  # (NSFileManager's trashItemAtURL, so the Finder's "Put Back" can restore it)
  import ctypes, ctypes.util
  objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc") or "/usr/lib/libobjc.dylib")
  ctypes.cdll.LoadLibrary("/System/Library/Frameworks/Foundation.framework/Foundation")
  objc.objc_getClass.restype = ctypes.c_void_p
  objc.objc_getClass.argtypes = [ctypes.c_char_p]
  objc.sel_registerName.restype = ctypes.c_void_p
  objc.sel_registerName.argtypes = [ctypes.c_char_p]
  send = objc.objc_msgSend
  def call(receiver, selector:bytes, *args, argtypes:tuple=(), restype=ctypes.c_void_p):
    send.restype = restype
    send.argtypes = [ctypes.c_void_p, ctypes.c_void_p, *argtypes]
    return send(receiver, objc.sel_registerName(selector), *args)
  manager = call(objc.objc_getClass(b"NSFileManager"), b"defaultManager")
  string = call(objc.objc_getClass(b"NSString"), b"stringWithUTF8String:", os.fsencode(path),
                argtypes=(ctypes.c_char_p,))
  url = call(objc.objc_getClass(b"NSURL"), b"fileURLWithPath:", string, argtypes=(ctypes.c_void_p,))
  error = ctypes.c_void_p()
  ok = call(manager, b"trashItemAtURL:resultingItemURL:error:", url, None, ctypes.byref(error),
            argtypes=(ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)), restype=ctypes.c_bool)
  if not ok:
    reason = "unknown error"
    if error.value:
      text = call(error.value, b"localizedDescription")
      if text:
        reason = (call(text, b"UTF8String", restype=ctypes.c_char_p) or b"").decode("utf-8", "replace") or reason
    raise OSError(f'Couldn\'t move "{path}" to the Trash: {reason}')

def _trashWindows(path:str) -> None:
  # (the shell's SHFileOperation, with "allow undo": to the Recycle Bin)
  import ctypes
  from ctypes import wintypes
  class SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
                ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]
  FO_DELETE, FOF_SILENT, FOF_NOCONFIRMATION, FOF_ALLOWUNDO, FOF_NOERRORUI = 3, 0x4, 0x10, 0x40, 0x400
  op = SHFILEOPSTRUCTW(None, FO_DELETE, path + "\0", None, # (a list of paths, ending in an empty one)
                       FOF_SILENT | FOF_NOCONFIRMATION | FOF_ALLOWUNDO | FOF_NOERRORUI, False, None, None)
  result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) # type: ignore[attr-defined]
  if result != 0 or op.fAnyOperationsAborted:
    raise OSError(f'Couldn\'t move "{path}" to the Recycle Bin (error {result:#x}).')

def _trashFreedesktop(path:str) -> None:
  # (gio, if it's there: it knows every disk's trash; else the home trash, by the freedesktop.org spec)
  gio = shutil.which("gio")
  if gio is not None:
    done = subprocess.run([gio, "trash", path], capture_output=True, text=True)
    if done.returncode == 0:
      return
  import datetime
  from urllib.parse import quote
  trash = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser(os.path.join("~", ".local", "share")), "Trash")
  files, info = os.path.join(trash, "files"), os.path.join(trash, "info")
  os.makedirs(files, exist_ok=True)
  os.makedirs(info, exist_ok=True)
  base, ext = os.path.splitext(os.path.basename(path))
  name, n = base + ext, 1
  while True: # (a name not already in the trash: its info file is made first, so it's claimed)
    try:
      fd = os.open(os.path.join(info, name + ".trashinfo"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
      break
    except FileExistsError:
      n += 1
      name = f"{base} {n}{ext}"
  with os.fdopen(fd, "w", encoding="utf-8") as f:
    f.write(f"[Trash Info]\nPath={quote(path)}\nDeletionDate={datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}\n")
  try:
    os.rename(path, os.path.join(files, name))
  except OSError as ex:
    os.remove(os.path.join(info, name + ".trashinfo"))
    raise OSError(f'Couldn\'t move "{path}" to the Trash: {ex.strerror or ex}') from ex

def logFolder(program:str) -> str:
  '''
  :param program: The program's name, eg: "Semantic Nets".
  :returns: The folder the program's logs belong in (not made): eg,
    "~/Library/Logs/<program>" on the Mac, "%LOCALAPPDATA%\\<program>\\Logs" on
    Windows, "~/.local/state/<program>" on Linux.
  '''
  if MAC:
    return os.path.join(os.path.expanduser("~"), "Library", "Logs", program)
  if WINDOWS:
    return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), program, "Logs")
  return os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser(os.path.join("~", ".local", "state")), program)

def documentsFolder() -> str:
  '''
  :returns: The user's Documents folder: on Windows, wherever it really is (eg:
    in OneDrive); on Linux, XDG's (eg: from ``xdg-user-dir DOCUMENTS``), if it's
    set up; else ~/Documents.
  '''
  if WINDOWS:
    try:
      import ctypes
      from ctypes import wintypes
      buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
      CSIDL_PERSONAL = 5 # (My Documents)
      if ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_PERSONAL, None, 0, buf) == 0 and buf.value: # type: ignore[attr-defined]
        return buf.value
    except Exception:
      pass
  elif LINUX and shutil.which("xdg-user-dir"):
    try:
      folder = subprocess.run(["xdg-user-dir", "DOCUMENTS"], capture_output=True, text=True, timeout=5).stdout.strip()
      if folder and folder != os.path.expanduser("~"): # (it's the home folder when there's no Documents)
        return folder
    except (OSError, subprocess.SubprocessError):
      pass
  return os.path.join(os.path.expanduser("~"), "Documents")

################################################################################
# ---- Pictures and the clipboard ----------------------------------------------
################################################################################

def pdfToPNG(pdfPath:str, pngPath:str, dpi:int) -> None:
  '''
  Make a PNG of a PDF's first page, at *dpi* dots per inch: with *sips* on the
  Mac; elsewhere with the *pypdfium2* and *Pillow* packages.

  :raises RuntimeError: If it can't be made (eg: they aren't installed).
  '''
  if MAC:
    subprocess.run(["sips", "-s", "format", "png", pdfPath, "--out", pngPath], check=True, capture_output=True)
    subprocess.run(["sips", "-s", "dpiWidth", str(dpi), "-s", "dpiHeight", str(dpi), pngPath], check=True, capture_output=True)
    return
  try:
    import pypdfium2 # @UnresolvedImport
  except ImportError as ex:
    raise RuntimeError("making a picture needs the pypdfium2 and pillow packages (pip install pypdfium2 pillow).") from ex
  pdf = pypdfium2.PdfDocument(pdfPath)
  try:
    image = pdf[0].render(scale=dpi / 72).to_pil()
    image.save(pngPath, dpi=(dpi, dpi))
  finally:
    pdf.close()

def copyPNG(pngPath:str) -> None:
  '''
  Put a PNG on the clipboard: with *osascript* on the Mac; on Windows as a PNG
  and a bitmap (for programs that don't take PNGs: that needs *Pillow*); on
  Linux with *wl-copy* (Wayland) or *xclip* (X11).

  :raises RuntimeError: If it can't be done.
  '''
  if MAC:
    script = f'set the clipboard to (read (POSIX file "{pngPath}") as «class PNGf»)'
    subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
  elif WINDOWS:
    _copyPNGWindows(pngPath)
  else:
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    for tool, args in ((("wl-copy", ["--type", "image/png"]), ("xclip", ["-selection", "clipboard", "-t", "image/png", "-i"]))
                       if wayland else (("xclip", ["-selection", "clipboard", "-t", "image/png", "-i"]), ("wl-copy", ["--type", "image/png"]))):
      exe = shutil.which(tool)
      if exe is None:
        continue
      with open(pngPath, "rb") as f:
        if tool == "wl-copy":
          subprocess.run([exe, *args], stdin=f, check=True, capture_output=True, timeout=10)
        else: # (xclip stays, to give the picture to whoever asks for it: it's not waited for)
          subprocess.Popen([exe, *args, pngPath], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
      return
    raise RuntimeError("putting a picture on the clipboard needs xclip (X11) or wl-clipboard (Wayland): eg, sudo apt install xclip.")

def _copyPNGWindows(pngPath:str) -> None:
  import ctypes
  from ctypes import wintypes
  with open(pngPath, "rb") as f:
    png = f.read()
  formats:list[tuple[int, bytes]] = []
  user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32 # type: ignore[attr-defined]
  user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
  formats.append((user32.RegisterClipboardFormatW("PNG"), png))
  try:
    import io
    from PIL import Image # @UnresolvedImport
    bmp = io.BytesIO()
    Image.open(io.BytesIO(png)).convert("RGB").save(bmp, "BMP")
    CF_DIB = 8
    formats.append((CF_DIB, bmp.getvalue()[14:])) # (a DIB is a .bmp without its file header)
  except ImportError:
    pass
  kernel32.GlobalAlloc.restype = ctypes.c_void_p
  kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
  kernel32.GlobalLock.restype = ctypes.c_void_p
  kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
  kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
  user32.SetClipboardData.restype = ctypes.c_void_p
  user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
  if not user32.OpenClipboard(None):
    raise RuntimeError("the clipboard is in use.")
  try:
    user32.EmptyClipboard()
    GMEM_MOVEABLE = 0x2
    for fmt, data in formats:
      handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
      pointer = kernel32.GlobalLock(handle)
      ctypes.memmove(pointer, data, len(data))
      kernel32.GlobalUnlock(handle)
      if not user32.SetClipboardData(fmt, handle):
        raise RuntimeError("the picture couldn't be put on the clipboard.")
  finally:
    user32.CloseClipboard()

################################################################################
# ---- The look of things ------------------------------------------------------
################################################################################

WINDOW_BACKGROUND = "systemWindowBackgroundColor" if MAC else "SystemButtonFace" if WINDOWS else "#d9d9d9"
"The Tk color of a window's background (the Mac's and Windows' system colors only exist there)."

def setDPIAware() -> None:
  '''
  On Windows, say the program draws for the screen's resolution itself, so
  Windows doesn't scale its windows up (blurred) on a high-resolution screen.
  Call it before the first Tk window is made. Elsewhere it does nothing.
  '''
  if not WINDOWS:
    return
  import ctypes
  try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1) # type: ignore[attr-defined] # (system DPI aware)
  except (AttributeError, OSError):
    try:
      ctypes.windll.user32.SetProcessDPIAware() # type: ignore[attr-defined] # (before Windows 8.1)
    except (AttributeError, OSError):
      pass

def setUpLook(root:Any) -> None:
  '''
  Choose a ttk theme that fits in: on Linux, "clam" (Tk's "default" there looks
  dated); the Mac's and Windows' own native themes are left as they are.

  :param root: The Tk root (or any widget).
  '''
  if not LINUX:
    return
  from tkinter import ttk
  style = ttk.Style(root)
  if style.theme_use() == "default" and "clam" in style.theme_names():
    style.theme_use("clam")
