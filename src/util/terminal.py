#################################################################################
# (c) Copyright 2024-2026, Rob Kremer, MIT open source license.                 #
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
from typing import override, Any, TextIO
from abc import abstractmethod
import threading
import queue
from typing import Callable, Optional
import tkinter as tk
import tkinter.font  # noqa: F401 — makes tk.font.* reliably available (see registerStyle, below)
import builtins
import sys
import io
import itertools
import traceback
import util
import logging

logger:util.Logger = util.getLogger(__name__)

# ---- Common types -------------------------------------------------
PromptType = str|Callable[[], str]
'''A prompt passed to a terminal can be either a string constant or 
a function with no parameters returning a string.  Useful when you
want to vary the prompt as unix shells often do.'''

OnLineType = Callable[[str], Any|None]
'''A function that a terminal will call to parse and execute a command
whenever the user enters the command in the terminal's REPL.'''

ResultToStringFunType = Callable[[Any], str]
'''Since terminals are purely text based, and command can return ANY type,
terminals will call a function of this type to translate the return value
to a printable string. This is usually defaulted the builtin str() function,
but more exotic functions can be passed in in the terminal's constructor.'''

class AbstractTerminal:
  def __init__(
      self,
      onLine:OnLineType,
      prompt:PromptType = "> ",
      resultToStringFun:ResultToStringFunType=str,
      **_kwargs,
    ) -> None:
    '''
    :param onLine: Callback invoked (on a background thread) for each submitted line.
    :type onLine: Callable[[str], None]
    :type onLine: Callable[[str], None]
    :param prompt: The prompt string shown before each new command line.
    :type prompt: str|Callable[[],str]
    '''
    self.onLine:OnLineType = onLine
    self._prompt:PromptType = prompt
    self.resultToStringFun:ResultToStringFunType = resultToStringFun
    self.oldOut:TextIO|None = None
    self.oldErr:TextIO|None = None
    self.oldInput:Callable[[object], str]|None = None
    self.lastExecutionResult:Any = None
    
  @property
  def prompt(self) -> str:
    if callable(self._prompt):
      return self._prompt()
    assert type(self._prompt) is str
    return self._prompt

  @abstractmethod
  def input(self, prompt: str = "") -> str:
    '''
    Method to imitate *buildins.input()*. 
    '''
    pass
  
  @abstractmethod
  def printLine(
    self,
    text: str,
    style: Optional[str] = None,
    fg: Optional[str] = None,
    bg: Optional[str] = None,
    font: Optional[tuple[str, int, str]] = None,
  ) -> None:
    """Write a line of output above the current prompt, with optional styling.
    Safe to call from any thread — calls from off the main thread are
    marshalled onto it via after().
    
    Concrete terminal implementations may ignore the optional parameters.

    :param text: The text to print.
    :type text: str
    :param style: Registered style name (e.g. "stdout", "stderr", "result").
      Takes precedence over fg/bg/font.
    :type style: Optional[str]
    :param fg: Foreground color, used only if style is not given.
    :type fg: Optional[str]
    :param bg: Background color, used only if style is not given.
    :type bg: Optional[str]
    :param font: Font spec, used only if style is not given.
    :type font: Optional[tuple[str, int, str]]
    :rtype: None
    """
    pass


class PlainTextTerminal(AbstractTerminal):
  '''
  Not really a terminal at all. This is a pure text interface (REPL -
  Real, Evaluate, Print, Loop) that expects to operate called from
  a command line on a regular terminal. It does VT terminal or emulator.
  Colors are supported to the limited extent of the VT terminals.
  
  Instantiating this object runs the REPL, and the *__init__()* method
  does not return until the user presses ctrl-D. 
  '''
  TERMINAL_SEQUENCES:dict[str,str] = {
    "default": "0",
    "underline": "4",
    "black": "30",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "white": "37",
    "boldblack": "40",
    "boldred": "41",
    "boldgreen": "42",
    "boldyellow": "43",
    "boldblue": "44",
    "boldmagenta": "45",
    "boldcyan": "46",
    "boldwhite": "47",
    }
  
  @staticmethod
  def _getStyleSeq(name:str, default:str="") -> str:
    seq = PlainTextTerminal.TERMINAL_SEQUENCES.get(name, None)
    if seq is not None:
      return f'\033[{seq}m'
    return default
  
  def __init__(
      self,
      onLine:OnLineType,
      prompt:PromptType = "> ",
      resultToStringFun:ResultToStringFunType=str,
      stderrfg:str="red",
      stdoutfg:str="",
      promptfg:str="yellow",
      queryfg:str="green",
      resultfg:str="blue",
      **_kwargs,
    ) -> None:
    '''
    Run a plain text REPL interface. 
    
    Possible values for the various colour parameters are: default, underline, black, 
    red, green, yellow, blue, magenta, cyan, white, boldblack, boldred, boldgreen, 
    boldyellow, boldblue, boldmagenta, boldcyan, boldwhite.
    
    :param onLine: Callback invoked (on a background thread) for each submitted line.
    :type onLine: Callable[[str], None]
    :param prompt: The prompt string shown before each new command line.
    :type prompt: str|Callable[[],str]
    :param stderrfg: The colour of text from stderr. Default "red".
    :param stdoutfg: The colour of text from stdout. Default "" (terminal default).
    :param promptfg: The colour of text for the prompt. Default "yellow".
    :param queryfg: The colour of text prompts from self.input(). Default "green".
    :param resultfg: The colour of text for command returned results. Default "blue".
    '''
    super().__init__(onLine, prompt, resultToStringFun)
    self.styleTags: dict[str, str] = {
      "prompt": self._getStyleSeq(promptfg, "green"),
      "query": self._getStyleSeq(queryfg, "green"),
      "result": self._getStyleSeq(resultfg, "black"),
      "stderr": self._getStyleSeq(stderrfg, "red"),
      "stdout": self._getStyleSeq(stdoutfg, "black"),
      }
    
    try: # REPL
      oldSysErr = sys.stderr
      sys.stderr = LineFilteringStream(sys.stderr, lambda line: f'{self.styleTags.get("stderr", "")}{line}\033[0m')
      oldSysOut = sys.stdout
      sys.stdout = LineFilteringStream(sys.stdout, lambda line: f'{self.styleTags.get("stdout", "")}{line}\033[0m')

      line:str = ""
      while True:
        try:
          line = self.input(f'{self.styleTags.get("prompt","")}{self.prompt.strip()}\033[0m ')
          if line != "":
            self.lastExecutionResult = self.onLine(line)
        except EOFError: # ^D
          sys.exit(0)
          break
        except Exception:
          traceback.print_exc()
        else:
          if self.lastExecutionResult:
            self.printLine(self.resultToStringFun(self.lastExecutionResult), style="result")
            self.lastExecutionResult = None
    finally:
      sys.stderr = oldSysErr
      sys.stdout = oldSysOut
      

  @override
  def input(self, prompt:str="")->str:
    return input(f'{self.styleTags.get("prompt","")}{prompt}\033[0m')

  @override
  def printLine(
    self,
    text: str,
    style: Optional[str] = None,
    fg: Optional[str] = None,
    bg: Optional[str] = None,
    font: Optional[tuple[str, int, str]] = None,
  ) -> None:
    """Write a line of output above the current prompt, with optional styling.
    Safe to call from any thread — calls from off the main thread are
    marshalled onto it via after().

    :param text: The text to print.
    :type text: str
    :param style: Registered style name (e.g. "stdout", "stderr", "result").
      Takes precedence over fg/bg/font.
    :type style: Optional[str]
    :param fg: Foreground color, used only if style is not given.
    :type fg: Optional[str]
    :param bg: Background color, used only if style is not given.
    :type bg: Optional[str]
    :param font: Font spec, used only if style is not given.
    :type font: Optional[tuple[str, int, str]]
    :rtype: None
    """
    if style is None:
      style = ""
    if text is None:
      return
    if text.startswith("\033["): #if this has been escaped already, use that.
      m = text.find("m")
      prefix = text[0:m+1]
      text = text[m:]
    elif style == "":
      prefix = ""
    else:
      prefix = self.styleTags.get(style,"")
    for line in text.split("\n"):
      print(f'{prefix}{line}\033[0m')


class LineBufferedStream(io.TextIOBase):
  """Base class for file-like stream wrappers that buffer writes by line and
  hand each complete line to a subclass for emission.

  Subclasses implement _emitLine() to decide how a line actually gets displayed
  (e.g. ANSI escape codes for a text console, or styled inserts into a Tk widget).

  :rtype: None
  """

  def __init__(self) -> None:
    self._buffer = ""

  def write(self, text: str) -> int:
    """Buffer incoming text and flush complete lines via _emitLine().

    :param text: Text written by print() or similar.
    :type text: str
    :returns: Number of characters accepted.
    :rtype: int
    """
    self._buffer += text
    while "\n" in self._buffer:
      line, self._buffer = self._buffer.split("\n", 1)
      self._emitLine(line)
    return len(text)

  def flush(self) -> None:
    """Flush any partial (no trailing newline) buffered text as a final line.

    :rtype: None
    """
    if self._buffer:
      self._emitLine(self._buffer, end="")
      self._buffer = ""

  def _emitLine(self, line: str, end:str="\n") -> None:
    """Emit one complete line (no trailing newline). Subclasses must override.

    :param line: The line to emit.
    :type line: str
    :rtype: None
    """
    raise NotImplementedError


# for pure text-based terminal back end
class LineFilteringStream(LineBufferedStream):
  """Applies a transform to each complete line, then forwards it to an
  underlying stream (e.g. real stdout/stderr in a text console, using ANSI
  escape codes for color).

  :param target: The underlying stream to write transformed lines to.
  :type target: TextIO
  :param transform: Function applied to each line. Return None to suppress
    (drop) a line entirely. Defaults to passing lines through unchanged.
  :type transform: Optional[Callable[[str], Optional[str]]]
  """

  def __init__(
    self,
    target: "TextIO",
    transform: Optional[Callable[[str], Optional[str]]] = None,
  ) -> None:
    super().__init__()
    self.target = target
    self.transform = transform

  def _emitLine(self, line: str, end:str="\n") -> None:
    """Apply the transform and write the result to the target stream, unless
    the transform suppressed the line.

    :param line: The line to emit.
    :type line: str
    :rtype: None
    """
    result = line if self.transform is None else self.transform(line)
    if result is not None:
      self.target.write(result + end)

  def flush(self) -> None:
    """Flush buffered content, then the underlying target stream.

    :rtype: None
    """
    super().flush()
    self.target.flush()
    
    
####################################################################################
'''
TerminalWidget: a Text-based terminal emulator for Tkinter, designed to be
used as a mixin alongside a plain-object command-context class (see
TerminalWidget(SNAbstractTerminal, TerminalWidget) for the real usage
pattern this is built to support).

Responsibilities:
  - prompt/history/editing (prompt may be a str OR a zero-arg callable,
    re-evaluated on every write — e.g. SNAbstractTerminal.getPrompt)
  - styled output via named roles: "stdout", "stderr", "prompt", "query",
    "result" (colors supplied via stdoutfg/stderrfg/promptfg/queryfg/resultfg)
  - running onLine() per submitted command on a worker thread, converting its
    RETURN VALUE via resultToStringFun and printing it with the "result" style
  - blocking input() for onLine (and anything it calls) via a thread-safe queue
  - binding/unbinding its worker thread against a shared TerminalRegistry, so
    sys.stdout/sys.stderr/logging/input() route here for the duration of a
    command regardless of which window has keyboard focus by the time output
    actually happens
'''


# =============================================================================
# Terminal routing: resolves, for any stdout/stderr write, log record, or
# input() call, which TerminalWidget it should go to. A thread that has been
# explicitly bound (e.g. a window's command worker, or a background task
# launched by the graphics editor) always routes to its bound terminal,
# regardless of what has focus later. An unbound main-thread call (interactive
# typing, or a stray print()) routes to whichever window currently has focus.
# =============================================================================


class TerminalRegistry:
  """Routes stdio/logging/input() output to the correct TerminalWidget.

  :rtype: None
  """

  def __init__(self) -> None:
    self._byThread: dict[int, TerminalWidget] = {}
    self._focusedMainThreadTarget: Optional[TerminalWidget] = None
    self._lock = threading.Lock()

  def bindThreadToTerminal(self, terminal: TerminalWidget, thread: Optional[threading.Thread]=None) -> None:
    """Associate a thread with a specific terminal for the lifetime of its work.
    Call this from the code that STARTS the thread (e.g. a window's command
    dispatch, or the graphics editor launching a background computation).

    :param terminal: The terminal that output from this thread should route to.
    :type terminal: TerminalWidget
    :param thread: The thread to bind. Defaults to the current thread.
    :type thread: Optional[threading.Thread]
    :rtype: None
    """
    targetThread = thread or threading.current_thread()
    with self._lock:
      self._byThread[id(targetThread)] = terminal

  def unbindThread(self, thread: Optional[threading.Thread]=None) -> None:
    """Remove a thread's routing entry once its work is done.

    :param thread: The thread to unbind. Defaults to the current thread.
    :type thread: Optional[threading.Thread]
    :rtype: None
    """
    targetThread = thread or threading.current_thread()
    with self._lock:
      self._byThread.pop(id(targetThread), None)

  def resolveTerminal(self) -> Optional[TerminalWidget]:
    """Determine which terminal the current call should route to.

    :returns: The bound terminal for this thread, or the focused terminal for
      the main thread if unbound, or None if nothing resolves.
    :rtype: Optional[TerminalWidget]
    """
    threadId = id(threading.current_thread())
    with self._lock:
      bound = self._byThread.get(threadId)
    if bound is not None:
      return bound
    if threading.current_thread() is threading.main_thread():
      return self._focusedMainThreadTarget
    return None

  def onFocusIn(self, terminal: TerminalWidget) -> None:
    """Set the default routing target for interactive (main-thread) actions.

    :param terminal: The terminal belonging to the window that gained focus.
    :type terminal: TerminalWidget
    :rtype: None
    """
    self._focusedMainThreadTarget = terminal

  def onFocusOut(self, terminal: TerminalWidget) -> None:
    """Clear the default target if this terminal's window is the one losing focus.

    :param terminal: The terminal belonging to the window that lost focus.
    :type terminal: TerminalWidget
    :rtype: None
    """
    if self._focusedMainThreadTarget is terminal:
      self._focusedMainThreadTarget = None


class LineBufferedRoutingStream(io.TextIOBase):
  """A file-like object that buffers writes by line and routes each complete
  line to whichever terminal the TerminalRegistry resolves to at write time.

  :param registry: The shared registry used to resolve the target terminal.
  :type registry: TerminalRegistry
  :param style: Style name to use when printing (e.g. "stdout", "stderr").
  :type style: Optional[str]
  """

  def __init__(self, registry: TerminalRegistry, style: Optional[str]=None) -> None:
    self.registry = registry
    self.style = style
    self._buffer = ""

  def write(self, text: str) -> int:
    """Buffer incoming text and route complete lines to the resolved terminal.

    :param text: Text written by print() or similar.
    :type text: str
    :returns: Number of characters accepted.
    :rtype: int
    """
    self._buffer += text
    while "\n" in self._buffer:
      line, self._buffer = self._buffer.split("\n", 1)
      self._emit(line)
    return len(text)

  def flush(self) -> None:
    """Emit any partial (no trailing newline) buffered text as a final line.

    :rtype: None
    """
    if self._buffer:
      self._emit(self._buffer)
      self._buffer = ""

  def _emit(self, line: str) -> None:
    """Resolve the current target terminal and print the line to it.
    Silently dropped if no terminal resolves (e.g. unbound background thread
    with no window focused at all).

    :param line: The line to emit.
    :type line: str
    :rtype: None
    """
    terminal = self.registry.resolveTerminal()
    if terminal is not None:
      terminal.printLine(line, style=self.style)


class TerminalLogHandler(logging.Handler):
  """A logging.Handler that routes formatted records to whichever terminal the
  TerminalRegistry resolves to at emit time.

  :param registry: The shared registry used to resolve the target terminal.
  :type registry: TerminalRegistry
  """

  def __init__(self, registry: TerminalRegistry) -> None:
    super().__init__()
    self.registry = registry

  def emit(self, record: logging.LogRecord) -> None:
    """Format and route a log record to the resolved terminal, styled by level.

    :param record: The log record to emit.
    :type record: logging.LogRecord
    :rtype: None
    """
    terminal = self.registry.resolveTerminal()
    if terminal is None:
      return
    message = self.format(record)
    style = "stderr" if record.levelno >= logging.WARNING else "stdout"
    terminal.printLine(message, style=style)


# Captured before installGlobalIORouting() ever redirects sys.stderr, so an
# uncaught exception with nowhere else to go (see logUncaughtException below)
# can still reach the real console as a last resort.
_originalStderr:TextIO = sys.stderr

# Tracks which registry (if any) installGlobalIORouting() has already wired
# global stdout/stderr/input()/logging routing for. Makes the function
# idempotent against repeat calls with the same registry, which is what lets
# TerminalWidget call it itself (below) — so a simple, single-TerminalWidget
# app never has to call it explicitly — while a multi-window app like
# guiApp2.Application can still call it once, up front, before creating any
# widgets, with no double-installation.
_installedIORoutingRegistry: Optional[TerminalRegistry] = None


def installGlobalIORouting(registry: Optional[TerminalRegistry] = None) -> None:
  """Install stdout/stderr/input() redirection and logging routing ONCE, for
  the lifetime of the application. Safe to call more than once with the same
  registry — later calls are a no-op. TerminalWidget calls this itself, so a
  simple, single-terminal app never has to call it explicitly.

  :param registry: The shared registry that resolves which terminal each call routes
    to. Defaults to the module-level singleton (terminalRegistry) — a simple,
    single-terminal app doesn't need to know TerminalRegistry exists at all.
  :type registry: Optional[TerminalRegistry]
  :rtype: None
  """
  global _installedIORoutingRegistry
  if registry is None:
    registry = terminalRegistry

  if _installedIORoutingRegistry is registry:
    return  # already installed for this registry — nothing to do
  _installedIORoutingRegistry = registry

  sys.stdout = LineBufferedRoutingStream(registry, style="stdout")
  sys.stderr = LineBufferedRoutingStream(registry, style="stderr")

  def routedInput(prompt: object="") -> str:
    """Global input() replacement, routed through the resolved terminal.

    :param prompt: The prompt to display.
    :type prompt: object
    :returns: The line typed by the user.
    :rtype: str
    :raises RuntimeError: If no terminal can be resolved for this call.
    """
    terminal = registry.resolveTerminal()
    if terminal is None:
      raise RuntimeError("input() called with no bound thread and no focused terminal")
    return terminal.input(str(prompt))

  builtins.input = routedInput

  root = logging.getLogger()

  # util.setupLogger() (called at "sn" package import time) attaches a
  # DynamicStderrHandler that always writes to whatever sys.stderr currently
  # is. Now that sys.stderr has just been redirected above, that handler
  # would ALSO deliver every log record to this terminal — on top of the
  # TerminalLogHandler we're about to add below — producing a duplicate line
  # per record. Evict any such plain StreamHandler (but not FileHandler,
  # which IS a StreamHandler subclass and must keep writing to the log file)
  # so TerminalLogHandler becomes the single route from logging into the
  # terminal.
  for h in list(root.handlers):
    if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
      root.removeHandler(h)

  handler = TerminalLogHandler(registry)
  handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
  root.addHandler(handler)

  def logUncaughtException(excType: type[BaseException], excValue: BaseException,
                            excTraceback: object) -> None:
    """Guarantee an uncaught exception reaches the log file, even if it
    happens before any window/terminal exists.

    Python's default excepthook writes the traceback straight to sys.stderr —
    but by the time this can fire, sys.stderr is a LineBufferedRoutingStream,
    which silently drops output when no terminal is registered yet (e.g. a
    crash while constructing the first window). That path never touches the
    logging module at all, so nothing reaches fileHandler either. Routing
    through the root logger here fixes that: FileHandler doesn't depend on
    any GUI state, so it reliably captures the traceback regardless of
    whether a terminal exists. If a terminal does happen to exist,
    TerminalLogHandler will additionally display it there like any other log
    record; if not, fall back to the real console so it isn't invisible.

    :param excType: The exception's type.
    :type excType: type[BaseException]
    :param excValue: The exception instance.
    :type excValue: BaseException
    :param excTraceback: The exception's traceback.
    :type excTraceback: object
    :rtype: None
    """
    if issubclass(excType, KeyboardInterrupt):
      sys.__excepthook__(excType, excValue, excTraceback)  # type: ignore[arg-type]
      return
    logging.getLogger().critical("Uncaught exception", exc_info=(excType, excValue, excTraceback))  # type: ignore[arg-type]
    if registry.resolveTerminal() is None:
      traceback.print_exception(excType, excValue, excTraceback, file=_originalStderr)  # type: ignore[call-overload]

  sys.excepthook = logUncaughtException


# Single, app-wide registry. Created here so both AppWindow/AppPanedWidget and
# TerminalWidget (once patched — see note below) can reach it via the
# Application instance (self._root().terminalRegistry) or, more simply, this
# module-level reference.
terminalRegistry = TerminalRegistry()

# =============================================================================

class TerminalWidget(AbstractTerminal, tk.Text):
  """A Text widget that behaves like a simple terminal.

  :param master: The parent Tk widget.
  :type master: tk.Widget
  :param onLine: Callback invoked (on a background thread) for each submitted
    line. May return a value — if non-None, it is converted via
    resultToStringFun and printed with the "result" style.
  :type onLine: Callable[[str], Any]
  :param prompt: The prompt shown before each new command line. Either a
    plain string, or a zero-argument callable re-evaluated on every prompt
    write (e.g. a bound method that reflects current state).
  :type prompt: PromptType
  :param registry: The shared TerminalRegistry used for stdio/input() routing.
    Global streams (sys.stdout, sys.stderr, builtins.input) and logging are
    expected to already be installed once at app startup via
    installGlobalIORouting(registry) — this widget only binds/unbinds its
    own worker thread against that registry. Defaults to the module-level
    singleton (terminalRegistry) — a simple, single-TerminalWidget app doesn't
    need to know TerminalRegistry exists at all.
  :type registry: Optional[TerminalRegistry]
  :param resultToStringFun: Converts a non-None onLine() return value to a
    string for display. Defaults to str().
  :type resultToStringFun: Optional[Callable[[Any], str]]
  :param stdoutfg: Foreground color for stdout-routed lines.
  :type stdoutfg: str
  :param stderrfg: Foreground color for stderr-routed lines.
  :type stderrfg: str
  :param promptfg: Foreground color for the command prompt.
  :type promptfg: str
  :param queryfg: Foreground color for input()-style query prompts.
  :type queryfg: str
  :param resultfg: Foreground color for onLine()'s returned result.
  :type resultfg: str
  :param queryFont: Font spec (family, size, style) for input()-style query
    prompts, e.g. ("Helvetica", 12, "bold"). Defaults to a bold variant of
    the widget's own font, so a pending input() request stands out from
    ordinary output even without any styling of your own.
  :type queryFont: Optional[tuple[str, int, str]]
  :param queryFlashColor: Background color the widget flashes to draw
    attention to a pending input() request. Set to None to disable flashing
    entirely.
  :type queryFlashColor: Optional[str]
  :param queryFlashCount: Number of on/off flashes to run when input() is
    called. The flash stops early, automatically, once the reply arrives.
  :type queryFlashCount: int
  :param queryFlashIntervalMs: Milliseconds between flash transitions.
  :type queryFlashIntervalMs: int
  :param kwargs: Forwarded to tk.Text (e.g. bg, fg, font, width, height).
  :type kwargs: object
  """

  def __init__(
    self,
    master: tk.Widget,
    onLine: OnLineType,
    prompt: PromptType = "> ",
    resultToStringFun: ResultToStringFunType = str,
    registry: Optional[TerminalRegistry] = None,
    stdoutfg: str = "black",
    stderrfg: str = "red",
    promptfg: str = "darkgreen",
    queryfg: str = "violet red",
    resultfg: str = "purple4",
    queryFont: Optional[tuple[str, int, str]] = None,
    queryFlashColor: Optional[str] = "yellow",
    queryFlashCount: int = 6,
    queryFlashIntervalMs: int = 150,
    **kwargs: object,
  ) -> None:
    tk.Text.__init__(self, master, kwargs)  # remaining kwargs (bg, fg, font, ...) go to tk.Text
    AbstractTerminal.__init__(self, onLine, prompt, resultToStringFun, **kwargs)

    # Defaulting here (rather than in the signature) keeps this a plain,
    # ordinary default — module-level terminalRegistry is defined further
    # down in this same file, so it can't be referenced directly as a
    # parameter default above (that's evaluated at def time, before this
    # module has finished loading).
    self.registry:TerminalRegistry = registry if registry is not None else terminalRegistry

    # Ensure stdout/stderr/input()/logging are routed globally. Idempotent —
    # a multi-widget app (e.g. guiApp2.Application) that already called this
    # explicitly before creating any widgets is unaffected; a simple,
    # single-TerminalWidget app gets routing installed automatically here,
    # with no registry boilerplate of its own.
    installGlobalIORouting(self.registry)

    self.history: list[str] = []
    self.historyIndex: Optional[int] = None
    self.styleTags: dict[str, str] = {}
    self.adHocTagCache: dict[tuple, str] = {}
    self._tagCounter = itertools.count()

    self._workerThread: Optional[threading.Thread] = None
    self._replyQueue: "queue.Queue[object]" = queue.Queue()
    self._awaitingReply: bool = False

    # Create the mark before the first _writePrompt() call needs it.
    self.mark_set("inputStart", "1.0")
    self.mark_gravity("inputStart", "left")

    self.bind("<Return>", self._handleReturn)
    self.bind("<Up>", self._handleUp)
    self.bind("<Down>", self._handleDown)
    self.bind("<BackSpace>", self._handleBackspace)
    self.bind("<Key>", self._guardEditableRegion)
    self.bind("<Control-d>", self._handleCtrlD)
    self.bind("<Control-D>", self._handleCtrlD)

    # Fixed roles, always available — no separate registerStyle() call needed
    # by subclasses for these five.
    self.registerStyle("stdout", fg=stdoutfg)
    self.registerStyle("stderr", fg=stderrfg)
    self.registerStyle("prompt", fg=promptfg)
    if queryFont is None:
      # Bold variant of whatever font this widget is already using, so a
      # pending input() request is visually distinct with zero configuration.
      baseFont = tk.font.Font(font=self.cget("font"))
      queryFont = (baseFont.actual("family"), baseFont.actual("size"), "bold")
    self.registerStyle("query", fg=queryfg, font=queryFont)
    self.registerStyle("result", fg=resultfg)

    # input()-attention-flash state — see _startQueryFlash/_flashTick/_stopQueryFlash.
    self.queryFlashColor = queryFlashColor
    self.queryFlashCount = queryFlashCount
    self.queryFlashIntervalMs = queryFlashIntervalMs
    self._flashJob: Optional[str] = None
    self._normalBg = self.cget("bg")

    self._writePrompt()

  # ---- prompt resolution / line plumbing -----------------------------------

  def _atLineStart(self) -> bool:
    """Whether the widget is positioned at the start of a fresh line — either
    because it's still empty, or because the last character written was a
    newline.

    :returns: True if a prompt can be written without first breaking onto a
      new line of its own.
    :rtype: bool
    """
    if self.index("end-1c") == "1.0":
      return True  # widget is still empty — nothing to break onto a new line from
    return self.get("end-2c", "end-1c") == "\n" # doesn't work for some reason

  def _writePrompt(self, text: Optional[str] = None, style: str = "prompt") -> None:
    """Write a prompt (styled) and mark the start of the editable input region.
    Only ever appends — callers that need to replace the current line
    (printLine, _showInputPrompt, _finishCommand) must delete it first.

    If the most recently written character isn't a newline (e.g. output
    printed from a background thread that didn't end its own line), a
    newline is inserted first so the prompt always starts on its own line
    rather than getting appended to whatever came before it.

    :param text: Prompt text to use. Defaults to the resolved self.prompt.
    :type text: Optional[str]
    :param style: Registered style to apply to the prompt text.
    :type style: str
    :rtype: None
    """
    if not self._atLineStart():
      self.insert("end", "\n")
    #promptText = self._resolvePrompt() if text is None else text
    tagName = self.styleTags.get(style)
    #self.insert("end", promptText, tagName if tagName else ())
    self.insert("end", self.prompt if text is None else text, tagName if tagName else ())
    self.inputStart = self.index("end-1c")
    self.mark_set("inputStart", self.inputStart)
    self.mark_gravity("inputStart", "left")
    self.see("end")

  def _currentLine(self) -> str:
    """Get the text the user has typed on the current input line.

    :returns: The current (uncommitted) input line.
    :rtype: str
    """
    return self.get("inputStart", "end-1c")

  def _replaceCurrentLine(self, text: str) -> None:
    """Replace the current input line with new text (used for history recall).

    :param text: The text to place on the input line.
    :type text: str
    :rtype: None
    """
    self.delete("inputStart", "end-1c")
    self.insert("inputStart", text)

  # ---- command dispatch (spawns/feeds worker thread) -----------------------

  def _handleReturn(self, event: tk.Event) -> str:
    """Handle Enter: feed a pending input() request, or start a new command.

    :rtype: str
    """
    line = self._currentLine()
    self.insert("end", "\n")
    self.mark_set("inputStart", "end")  # nothing "pending" until the next prompt

    if self._awaitingReply:
      self._awaitingReply = False
      self._stopQueryFlash()
      self._replyQueue.put(line)          # wakes the worker thread's input()
      return "break"

    if self._workerThread is not None and self._workerThread.is_alive():
      return "break"                      # a command is still running; ignore

    if line.strip():
      self.history.append(line)
    self.historyIndex = None

    self._workerThread = threading.Thread(
      target=self._runCommand, args=(line,), daemon=True
    )
    self._workerThread.start()
    return "break"

  def _runCommand(self, line: str) -> None:
    """Run onLine on a background thread, bound to THIS terminal via the
    registry for the duration. If onLine returns a non-None value, it is
    converted via resultToStringFun and printed with the "result" style.
    Restores the prompt when done.

    :param line: The submitted command line.
    :type line: str
    :rtype: None
    """
    self.registry.bindThreadToTerminal(self)
    try:
      result = self.onLine(line)
      if result is not None:
        self.printLine(self.resultToStringFun(result), style="result")
    except Exception:
      #import traceback
      #traceback.print_exc() # goes through sys.stderr -> registry -> this terminal
      logger.error(f'While running command "{line}"', exc_info=True)
    finally:
      sys.stdout.flush()
      sys.stderr.flush()
      self.registry.unbindThread()
      self.after(0, self._finishCommand)

  def _finishCommand(self) -> None:
    """Clear the current (empty) line and write a fresh command prompt.
    Runs on the main thread via after().

    :rtype: None
    """
    self.delete("inputStart linestart", "end")
    self._writePrompt()

  # ---- input() — blocks the CALLING (worker) thread only --------------------

  def input(self, prompt: str = "") -> str:
    """Block and return a line of input, input()-style. Safe to call from
    onLine's worker thread, or from any other thread that has bound itself
    to this terminal via the registry. Never call from the main/GUI thread.

    :param prompt: The prompt text to display (uses the "query" style).
    :type prompt: str
    :returns: The line the user typed.
    :rtype: str
    :raises EOFError: If the user sent EOF (Ctrl+D) instead of a line.
    """
    if threading.current_thread() is threading.main_thread():
      raise RuntimeError("TerminalWidget.input() must not be called from the main/GUI thread")
    self.after(0, self._showInputPrompt, prompt)
    result = self._replyQueue.get()  # blocks this thread only, GUI stays live
    if result is _EOF_SENTINEL:
      raise EOFError()
    return str(result)

  def _showInputPrompt(self, prompt: str) -> None:
    """Display an input() prompt (styled as a "query") and mark that the next
    Enter is a reply, not a command. Runs on the main thread via after().

    :param prompt: The prompt text.
    :type prompt: str
    :rtype: None
    """
    self.delete("inputStart linestart", "end")
    self._writePrompt(prompt, style="query")
    self._awaitingReply = True
    self._startQueryFlash()

  def _startQueryFlash(self) -> None:
    """Flash the widget's background a few times to draw attention to a
    newly-shown input() prompt. No-ops if queryFlashColor is None. Stops
    automatically as soon as the reply arrives — see _stopQueryFlash(),
    called from _handleReturn()/_handleCtrlD() — so a fast typist never
    sees it run past their answer.

    :rtype: None
    """
    if self.queryFlashColor is None or self.queryFlashCount <= 0:
      return
    if self._flashJob is not None:
      self.after_cancel(self._flashJob)  # a flash was already running — restart it
    self._flashTick(self.queryFlashCount * 2)

  def _flashTick(self, ticksRemaining: int) -> None:
    """One step of the input() attention-flash. Alternates the widget's
    background between queryFlashColor and its normal color; reschedules
    itself via after() until ticksRemaining reaches 0 or the reply arrives.

    :param ticksRemaining: Number of color alternations left.
    :type ticksRemaining: int
    :rtype: None
    """
    if not self._awaitingReply or ticksRemaining <= 0:
      self.configure(bg=self._normalBg)
      self._flashJob = None
      return
    self.configure(bg=self.queryFlashColor if ticksRemaining % 2 == 0 else self._normalBg)
    self._flashJob = self.after(self.queryFlashIntervalMs, self._flashTick, ticksRemaining - 1)

  def _stopQueryFlash(self) -> None:
    """Cancel any in-progress input() attention-flash and restore the normal
    background immediately. Safe to call even when no flash is running.

    :rtype: None
    """
    if self._flashJob is not None:
      self.after_cancel(self._flashJob)
      self._flashJob = None
    self.configure(bg=self._normalBg)

  def _handleCtrlD(self, event: tk.Event) -> str:
    """Signal EOF to a pending input() call, mimicking terminal Ctrl+D semantics.

    :rtype: str
    """
    if self._awaitingReply:
      self._awaitingReply = False
      self._stopQueryFlash()
      self._replyQueue.put(_EOF_SENTINEL)
    return "break"

  # ---- history navigation ---------------------------------------------------

  def _handleUp(self, event: tk.Event) -> str:
    """Recall the previous history entry.

    :rtype: str
    """
    if self._awaitingReply or not self.history:
      return "break"
    if self.historyIndex is None:
      self.historyIndex = len(self.history) - 1
    elif self.historyIndex > 0:
      self.historyIndex -= 1
    self._replaceCurrentLine(self.history[self.historyIndex])
    return "break"

  def _handleDown(self, event: tk.Event) -> str:
    """Recall the next history entry, or clear the line at the end of history.

    :rtype: str
    """
    if self._awaitingReply or self.historyIndex is None:
      return "break"
    if self.historyIndex < len(self.history) - 1:
      self.historyIndex += 1
      self._replaceCurrentLine(self.history[self.historyIndex])
    else:
      self.historyIndex = None
      self._replaceCurrentLine("")
    return "break"

  def _handleBackspace(self, event: tk.Event) -> Optional[str]:
    """Prevent backspacing past the start of the input region.

    :rtype: Optional[str]
    """
    if self.compare("insert", "<=", "inputStart"):
      return "break"
    return None

  def _guardEditableRegion(self, event: tk.Event) -> Optional[str]:
    """Block edits (other than at/after inputStart) to protect prior output.

    :rtype: Optional[str]
    """
    if self.compare("insert", "<", "inputStart") and event.keysym not in (
      "Left", "Right", "Up", "Down", "Home", "End",
    ):
      self.mark_set("insert", "end")
    return None

  # ---- styled output ("print()"-like), thread-safe --------------------------

  def registerStyle(
    self,
    name: str,
    fg: Optional[str] = None,
    bg: Optional[str] = None,
    font: Optional[tuple[str, int, str]] = None,
  ) -> None:
    """Register (or re-register) a named style for use by printLine/_writePrompt.

    :param name: Style name, e.g. "stdout", "stderr", "prompt", "query", "result".
    :type name: str
    :param fg: Foreground (text) color.
    :type fg: Optional[str]
    :param bg: Background highlight color.
    :type bg: Optional[str]
    :param font: Font spec as (family, size, style).
    :type font: Optional[tuple[str, int, str]]
    :rtype: None
    """
    def isValidColor(name: str) -> bool:
      try:
        self.winfo_rgb(name)
        return True
      except tk.TclError:
        return False
    tagName = f"style_{name}"
    tagOptions: dict[str, object] = {}
    if fg is not None:
      if fg == "white": fg = "snow"
      if isValidColor(fg):
        tagOptions["foreground"] = fg
      else:
        logger.warning(f'Invalid foreground color name for style "{name}": "{fg}"')
    if bg is not None:
      if bg == "white": bg = "snow"
      if isValidColor(bg):
        tagOptions["background"] = bg
      else:
        logger.warning(f'Invalid background color name for style "{name}": "{bg}"')
    if font is not None:
      # tk will silently use the default font if the font family name is wrong, so just warn...
      if font[0] not in tk.font.families():
        logger.warning(f'Invalid font family for style "{name}": "{font[0]}"')
      tagOptions["font"] = font
    self.tag_configure(tagName, **tagOptions) #type: ignore[call-overload]
    self.styleTags[name] = tagName

  def _getAdHocTag(
    self,
    fg: Optional[str],
    bg: Optional[str],
    font: Optional[tuple[str, int, str]],
  ) -> str:
    """Get (creating and caching if necessary) a tag for an unnamed style combo.

    :param fg: Foreground color.
    :type fg: Optional[str]
    :param bg: Background color.
    :type bg: Optional[str]
    :param font: Font spec.
    :type font: Optional[tuple[str, int, str]]
    :returns: The tag name to use for this style combination.
    :rtype: str
    """
    key = (fg, bg, font)
    if key in self.adHocTagCache:
      return self.adHocTagCache[key]
    tagName = f"adhoc_{next(self._tagCounter)}"
    tagOptions: dict[str, object] = {}
    if fg is not None:
      tagOptions["foreground"] = fg
    if bg is not None:
      tagOptions["background"] = bg
    if font is not None:
      tagOptions["font"] = font
    self.tag_configure(tagName, **tagOptions) # type: ignore[call-overload]
    self.adHocTagCache[key] = tagName
    return tagName

  @override
  def printLine(
    self,
    text: str,
    style: Optional[str] = None,
    fg: Optional[str] = None,
    bg: Optional[str] = None,
    font: Optional[tuple[str, int, str]] = None,
  ) -> None:
    """Write a line of output above the current prompt, with optional styling.
    Safe to call from any thread — calls from off the main thread are
    marshalled onto it via after().

    :param text: The text to print.
    :type text: str
    :param style: Registered style name (e.g. "stdout", "stderr", "result").
      Takes precedence over fg/bg/font.
    :type style: Optional[str]
    :param fg: Foreground color, used only if style is not given.
    :type fg: Optional[str]
    :param bg: Background color, used only if style is not given.
    :type bg: Optional[str]
    :param font: Font spec, used only if style is not given.
    :type font: Optional[tuple[str, int, str]]
    :rtype: None
    """
    if threading.current_thread() is not threading.main_thread():
      self.after(0, self.printLine, text, style, fg, bg, font)
      return

    self.delete("inputStart linestart", "end")

    tagName: Optional[str] = None
    if style is not None:
      if style not in self.styleTags:
        raise ValueError(f"Unregistered style: {style!r}")
      tagName = self.styleTags[style]
    elif fg is not None or bg is not None or font is not None:
      tagName = self._getAdHocTag(fg, bg, font)

    self.insert("end", text + "\n", tagName if tagName else ())
    self.mark_set("inputStart", "end")

    # If a command is running, leave the line blank — _finishCommand writes
    # the real prompt when it completes. If nothing is running and no input()
    # query is currently displayed, redraw the prompt so output never leaves
    # the terminal without a prompt visible.
    commandRunning = self._workerThread is not None and self._workerThread.is_alive()
    if not commandRunning and not self._awaitingReply:
      self._writePrompt()

    self.see("end")


class _EofSentinel:
  """Distinct sentinel object put on the reply queue to signal EOF (Ctrl+D),
  distinguishable from any real string a user could type.
  """
  __slots__ = ()


_EOF_SENTINEL = _EofSentinel()
              
####################################################################################
  
if __name__ == "__main__":
  
  def onLine(line: str) -> Any:
    """Runs on the worker thread — argparse dispatch as usual.
  
    :param line: The submitted command line.
    :type line: str
    :rtype: None
    """
    line = line.strip()
    if len(line) > 0:
      return eval(line)

  n = 0
  def nprompt():
    global n
    n += 1
    return f'{n}> '
    
  if __name__ == "__main__":
    gui = True
    #terminal:AbstractTerminal
    if gui:
      root = tk.Tk()
      terminal2 = TerminalWidget(root, onLine=onLine, prompt=nprompt) #type: ignore[arg-type]
      terminal2.pack(fill="both", expand=True)
      root.mainloop()
    else:
      terminal = PlainTextTerminal(onLine, prompt=nprompt)
    
