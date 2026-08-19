from __future__ import annotations
from typing import override, Any, TextIO
from abc import abstractmethod
import threading
import queue
from typing import Callable, Optional
import tkinter as tk
import builtins
import sys
import itertools
import util

logger:util.Logger = util.getLogger(__name__)


class AbstractTerminal:
  def __init__(
      self,
      onLine: Callable[[str], None],
      prompt: str|Callable[[],str] = "> ",
      resultToStringFun: Callable[[Any], str]=str,
      **_kwargs,
    ) -> None:
    '''
    :param onLine: Callback invoked (on a background thread) for each submitted line.
    :type onLine: Callable[[str], None]
    :param prompt: The prompt string shown before each new command line.
    :type prompt: str|Callable[[],str]
    '''
    self.onLine = onLine
    self._prompt:str|Callable[[],str] = prompt
    self._resultToStringFun: Callable[[Any], str] = resultToStringFun
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
  def printLine(self, text:str, **kwargs):
    '''
    Method to imitate *buildins.print()*. 
    '''
    pass


class PlainTextTerminal(AbstractTerminal):
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
  def getStyleSeq(name:str) -> str:
    seq = PlainTextTerminal.TERMINAL_SEQUENCES.get(name, None)
    if seq is not None:
      return f'\033[{seq}m'
    return ""
  
  def __init__(
      self,
      onLine: Callable[[str], None],
      prompt: str|Callable[[],str] = "> ",
      resultToStringFun: Callable[[Any], str]=str,
      stderrfg:str="red",
      stdoutfg:str="",
      promptfg:str="yellow",
      queryfg:str="green",
      resultfg:str="blue",
      **_kwargs,
    ) -> None:
    '''
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
      "prompt": self.getStyleSeq(promptfg),
      "query": self.getStyleSeq(queryfg),
      "result": self.getStyleSeq(resultfg),
      "stderr": self.getStyleSeq(stderrfg),
      "stdout": self.getStyleSeq(stdoutfg),
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
          import traceback
          traceback.print_exc()
        else:
          if self.lastExecutionResult:
            self.printLine(resultToStringFun(self.lastExecutionResult), style="result")
            self.lastExecutionResult = None
    finally:
      sys.stderr = oldSysErr
      sys.stdout = oldSysOut
      

  @override
  def input(self, prompt:str="")->str:
    return input(f'{self.styleTags.get("prompt","")}{prompt}\033[0m')

  @override
  def printLine(self, text:str, style="", **_kwargs):
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



class TerminalWidget(AbstractTerminal, tk.Text):
  """
  A Text widget that behaves like a simple terminal input.
  
  The terminal automatically defaults to the following styles for the
  different categories of output, which may be modified using the 
  *registerStyle()* method:
  
    - stdout: text coming from sys.out
    - stderr: text coming from sys.err
    - prompt: the style of the command line prompt
    - query: the style of text coming from the builtin.input() prompt.
  
  :param master: The parent Tk widget.
  :type master: tk.Widget
  :param onLine: Callback invoked (on a background thread) for each submitted line.
  :type onLine: Callable[[str], None]
  :param prompt: The prompt string shown before each new command line.
  :type prompt: str
  """
  def __init__(
      self,
      master: tk.Widget,
      onLine: Callable[[str], None],
      prompt: str|Callable[[],str] = "> ",
      resultToStringFun: Callable[[Any], str]=str,
      stderrfg:str="red",
      stdoutfg:str="black",
      promptfg:str="yellow",
      queryfg:str="green",
      resultfg:str="lightblue",
      **kwargs
    ) -> None:
    '''
    kwargs keys can be: background, borderwidth, cursor,
    exportselection, font, foreground,
    highlightbackground, highlightcolor,
    highlightthickness, insertbackground,
    insertborderwidth, insertofftime,
    insertontime, insertwidth, padx, pady,
    relief, selectbackground,
    selectborderwidth, selectforeground,
    setgrid, takefocus,
    xscrollcommand, yscrollcommand,
    autoseparators, height, maxundo,
    spacing1, spacing2, spacing3,
    state, tabs, undo, width, wrap.
    
    :param master: The parent Tk widget.
    :type master: tk.Widget
    :param onLine: Callback invoked (on a background thread) for each submitted line.
    :type onLine: Callable[[str], None]
    :param prompt: The prompt string shown before each new command line.
    :type prompt: str|Callable[[],str]
    :param stderrfg: The colour of text from stderr. Default "red".
    :param stdoutfg: The colour of text from stdout. Default "" (terminal default).
    :param promptfg: The colour of text for the prompt. Default "yellow".
    :param queryfg: The colour of text prompts from self.input(). Default "green".
    :param resultfg: The colour of text for command returned results. Default "lightblue".
    '''
    tk.Text.__init__(self, master, **kwargs)
    AbstractTerminal.__init__(self, onLine, prompt=prompt, resultToStringFun=resultToStringFun)
    self.history: list[str] = []
    self.historyIndex: Optional[int] = None
    self.inputStart: str = "1.0"
    self.styleTags: dict[str, str] = {}
    self.adHocTagCache: dict[tuple, str] = {}
    self._tagCounter = itertools.count()

    self._workerThread: Optional[threading.Thread] = None
    self._replyQueue: "queue.Queue[str]" = queue.Queue()
    self._awaitingReply: bool = False
    self._capturingIO:int=0 # depth-flag for self._captureSysIO() and self._releaseSysIO()

    # Create the mark before the first _writePrompt() call needs it.
    self.mark_set("inputStart", "1.0")
    self.mark_gravity("inputStart", "left")

    self.bind("<Return>", self._handleReturn)
    self.bind("<Up>", self._handleUp)
    self.bind("<Down>", self._handleDown)
    self.bind("<BackSpace>", self._handleBackspace)
    self.bind("<Key>", self._guardEditableRegion)
    self.bind("<Control-d>", self._handleCtrlD)

    self.registerStyle("stderr", fg=stderrfg)#, bg, font)
    self.registerStyle("stdout", fg=stdoutfg)#, bg, font)
    self.registerStyle("prompt", fg=promptfg)#, bg, font)
    self.registerStyle("query",  fg=queryfg)#, bg, font)
    self.registerStyle("result", fg=resultfg)#, bg, font)
    
    self._writePrompt()
    
  # ---- prompt / line plumbing (main thread only) -------------------------
  
  def _writePrompt(self, text: Optional[str] = None) -> None:
    """Write a prompt and mark the start of the editable input region.
  
    :param text: Prompt text to use. Defaults to self.prompt.
    :type text: Optional[str]
    :rtype: None
    """
    tagName:str|None = None
    if text is None and "prompt" in self.styleTags:
      tagName = self.styleTags["prompt"]
    if text is not None and "query" in self.styleTags:
      tagName = self.styleTags["query"]

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

  # ---- command dispatch (spawns/feeds worker thread) ----------------------

  def _handleReturn(self, _event: tk.Event) -> str:
    """Handle Enter: feed a pending input() request, or start a new command.
  
    :rtype: str
    """
    line = self._currentLine()
    self.insert("end", "\n")
    self.mark_set("inputStart", "end")  # nothing is "pending" until the next prompt
  
    if self._awaitingReply:
      self._awaitingReply = False
      self._replyQueue.put(line)
      return "break"
  
    if self._workerThread is not None and self._workerThread.is_alive():
      return "break"
  
    if line.strip():
      self.history.append(line)
    self.historyIndex = None
  
    if line.strip():
      self._workerThread = threading.Thread(target=self._runCommand, args=(line,), daemon=True)
      self._workerThread.start()
    else:
      self._writePrompt()
    return "break"

  def _runCommand(self, line: str) -> None:
    """Run onLine on a background thread, with stdout/stderr and input() redirected
    to the terminal, then restore the prompt.
  
    :param line: The submitted command line.
    :type line: str
    :rtype: None
    """
    self._captureSysIO()
    try:
      self.lastExecutionResult = self.onLine(line)
    except Exception:
      import traceback
      traceback.print_exc()
    finally:
      sys.stdout.flush()
      sys.stderr.flush()
      self._releaseSysIO()
      self.after(0, self._finishCommand)
      
  def _captureSysIO(self):
    self._capturingIO += 1
    if self._capturingIO > 1:
      return
    assert self.oldOut is None
    self.oldOut, self.oldErr = sys.stdout, sys.stderr
    self.oldInput = builtins.input
    sys.stdout = _StreamToTerminal(self, style="stdout" if "stdout" in self.styleTags else None)
    sys.stderr = _StreamToTerminal(self, style="stderr" if "stderr" in self.styleTags else None)
    builtins.input = self._inputBuiltinReplacement
    
  def _releaseSysIO(self):
    self._capturingIO -= 1
    if self._capturingIO > 0:
      return
    assert self.oldOut is not None
    sys.stdout, sys.stderr = self.oldOut, self.oldErr
    self.oldOut, self.oldErr = None, None 
    if self.oldInput is not None:
        builtins.input = self.oldInput #type: ignore[assignment]
    self.oldInput = None
    
  def _finishCommand(self) -> None:
    """Clear the current (empty) line and write a fresh command prompt.
  
    Runs on the main thread via after().
  
    :rtype: None
    """
    self.delete("inputStart linestart", "end")
    if self.lastExecutionResult is not None:
      self.printLine(self._resultToStringFun(self.lastExecutionResult), style="result")
      self.lastExecutionResult = None
    self._writePrompt()
  
  def _inputBuiltinReplacement(self, prompt: object = "") -> str:
    """Drop-in replacement for builtins.input(), routed through the terminal.

    Matches input()'s signature: the prompt argument is optional and, per the
    standard library, is str()-converted rather than type-checked.

    :param prompt: The prompt to display, as with builtins.input().
    :type prompt: object
    :returns: The line the user typed.
    :rtype: str
    """
    return self.input(str(prompt))  
      
  @override
  def input(self, prompt: str = "") -> str:
    """Block and return a line of input, input()-style. Call only from onLine
    (or a function it calls) — i.e. from the command worker thread, never from
    the main/GUI thread.

    :param prompt: The prompt text to display.
    :type prompt: str
    :returns: The line the user typed.
    :rtype: str
    """
    if threading.current_thread() is threading.main_thread():
      raise RuntimeError("TerminalWidget.input() must be called from onLine's worker thread")
    self.after(0, self._showInputPrompt, prompt)
    return self._replyQueue.get()  # blocks this worker thread only, GUI stays live

  def _showInputPrompt(self, prompt: str) -> None:
    """Display an input() prompt and mark that the next Enter is a reply, not a command.
  
    Runs on the main thread via after().
  
    :param prompt: The prompt text.
    :type prompt: str
    :rtype: None
    """
    self.delete("inputStart linestart", "end")
    self._writePrompt(prompt)
    self._awaitingReply = True
  
  # ---- history navigation --------------------------------------------------

  def _handleUp(self, _event: tk.Event) -> str:
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

  def _handleDown(self, _event: tk.Event) -> str:
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

  def _handleBackspace(self, _event: tk.Event) -> Optional[str]:
    """Prevent backspacing past the start of the input region.

    :rtype: Optional[str]
    """
    if self.compare("insert", "<=", "inputStart"):
      return "break"
    return None
  
  def _handleCtrlD(self, _event: tk.Event) -> str:
    '''
    Close the window.
    '''
    self.winfo_toplevel().destroy()
    return "break"
    
  def _guardEditableRegion(self, event: tk.Event) -> Optional[str]:
    """Block edits (other than at/after inputStart) to protect prior output.

    :rtype: Optional[str]
    """
    if self.compare("insert", "<", "inputStart") and event.keysym not in (
      "Left", "Right", "Up", "Down", "Home", "End",
    ):
      self.mark_set("insert", "end")
    return None

  # ---- styled output ("print()"-like), thread-safe -------------------------

  def registerStyle(
    self, name: str, fg: Optional[str] = None, bg: Optional[str] = None,
    font: Optional[tuple[str, int, str]] = None,
  ) -> None:
    """Pre-register a named style for reuse across multiple printLine calls.

    :param name: Style name, e.g. "error".
    :type name: str
    :param fg: Foreground color.
    :type fg: Optional[str]
    :param bg: Background color.
    :type bg: Optional[str]
    :param font: Font spec as (family, size, style).
    :type font: Optional[tuple[str, int, str]]
    :rtype: None
    """
    tagName = f"style_{name}"
    tagOptions: dict[str, Any] = {}
    if fg is not None:
      tagOptions["foreground"] = fg
    if bg is not None:
      tagOptions["background"] = bg
    if font is not None:
      tagOptions["font"] = font
    self.tag_configure(tagName, **tagOptions)
    self.styleTags[name] = tagName

  def _getAdHocTag(
    self, fg: Optional[str], bg: Optional[str], font: Optional[tuple[str, int, str]],
  ) -> str:
    """Get (creating/caching) a tag for an unnamed style combo.

    :rtype: str
    """
    key = (fg, bg, font)
    if key in self.adHocTagCache:
      return self.adHocTagCache[key]
    tagName = f"adhoc_{next(self._tagCounter)}"
    tagOptions: dict[str, Any] = {}
    if fg is not None:
      tagOptions["foreground"] = fg
    if bg is not None:
      tagOptions["background"] = bg
    if font is not None:
      tagOptions["font"] = font
    self.tag_configure(tagName, **tagOptions)
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
    **_kwargs
  ) -> None:
    """Write a line of output above the current prompt. Safe to call from onLine's
    worker thread or the main thread.
  
    :param text: The text to print.
    :type text: str
    :param style: Registered style name; takes precedence over fg/bg/font.
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
    self.mark_set("inputStart", "end")  # no prompt written here — see() below only
    self.see("end")    

# class _StreamToTerminal(io.TextIOBase):
#   """A file-like object that redirects writes to a TerminalWidget as printed lines.
#
#   :param terminal: The terminal widget to write to.
#   :type terminal: TerminalWidget
#   :param style: Registered style name to apply to each line (e.g. "stderr").
#   :type style: Optional[str]
#   """
#
#   def __init__(self, terminal: "TerminalWidget", **kwargs) -> None: #style: Optional[str] = None) -> None:
#     self.terminal = terminal
#     #self.style = style
#     self.kwargs = kwargs
#     self._buffer = ""
#
#   @override
#   def write(self, text: str) -> int:
#     """Buffer written text and flush complete lines to the terminal.
#
#     :param text: Text written by print() or similar.
#     :type text: str
#     :returns: Number of characters written.
#     :rtype: int
#     """
#     self._buffer += text
#     while "\n" in self._buffer:
#       line, self._buffer = self._buffer.split("\n", 1)
#       self.terminal.printLine(line, **self.kwargs) #style=self.style)
#     return len(text)
#
#   @override
#   def flush(self) -> None:
#     """Flush any partial (no trailing newline) buffered text as a final line.
#
#     :rtype: None
#     """
#     if self._buffer:
#       self.terminal.printLine(self._buffer, **self.kwargs) #style=self.style)
#       self._buffer = ""
    

import io
from typing import Callable, Optional


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


# for GUI back end
class _StreamToTerminal(LineBufferedStream):
  """Redirects writes to a TerminalWidget as styled printed lines.

  :param terminal: The terminal widget to write to.
  :type terminal: TerminalWidget
  :param style: Registered style name to apply to each line (e.g. "stderr").
  :type style: Optional[str]
  """

  def __init__(self, terminal: "TerminalWidget", style: Optional[str] = None) -> None:
    super().__init__()
    self.terminal = terminal
    self.style = style

  def _emitLine(self, line: str, end:str="\n") -> None:
    """Write the line to the terminal widget with this stream's style.

    :param line: The line to emit.
    :type line: str
    :rtype: None
    """
    self.terminal.printLine(line, style=self.style)


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
    
    
def onLine(line: str) -> Any:
  """Runs on the worker thread — argparse dispatch as usual.

  :param line: The submitted command line.
  :type line: str
  :rtype: None
  """
  # try:
  #   args = parser.parse_args(shlex.split(line))
  # except SystemExit:
  #   return
  # if hasattr(args, "func"):
  #   args.func(args, terminal) 
        
  # print(f'got line: "{line}"')
  # print('A second line', file=sys.stderr)
  # x = input("What? ")
  # print(f'got reply: "{x}"')
  return eval(line)

####################################################################################
'''
TerminalWidget: a Text-based terminal emulator for Tkinter, designed to be
used as a mixin alongside a plain-object command-context class (see
SNTerminalWidget(SNAbstractTerminal, TerminalWidget) for the real usage
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
# from __future__ import annotations
#
# import sys
# import queue
# import threading
# import itertools
# import tkinter as tk
# from typing import Any, Callable, Optional, Union


PromptType = str|Callable[[], str]


class TerminalWidget2(tk.Text):
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
    own worker thread against that registry.
  :type registry: TerminalRegistry
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
  :param kwargs: Forwarded to tk.Text (e.g. bg, fg, font, width, height).
  :type kwargs: object
  """

  def __init__(
    self,
    master: tk.Widget,
    onLine: Callable[[str], Any],
    prompt: PromptType,
    registry: "TerminalRegistry",
    resultToStringFun: Optional[Callable[[Any], str]] = None,
    stdoutfg: str = "black",
    stderrfg: str = "red",
    promptfg: str = "darkgreen",
    queryfg: str = "green",
    resultfg: str = "purple4",
    **kwargs: object,
  ) -> None:
    super().__init__(master, **kwargs)  # remaining kwargs (bg, fg, font, ...) go to tk.Text
    self.onLine = onLine
    self.prompt = prompt
    self.registry = registry
    self.resultToStringFun = resultToStringFun if resultToStringFun is not None else str

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
    self.registerStyle("query", fg=queryfg)
    self.registerStyle("result", fg=resultfg)

    self._writePrompt()

  # ---- prompt resolution / line plumbing -----------------------------------

  def _resolvePrompt(self) -> str:
    """Resolve self.prompt to a concrete string, calling it if it's callable.

    :returns: The current prompt text.
    :rtype: str
    """
    return self.prompt() if callable(self.prompt) else self.prompt

  def _writePrompt(self, text: Optional[str] = None, style: str = "prompt") -> None:
    """Write a prompt (styled) and mark the start of the editable input region.
    Only ever appends — callers that need to replace the current line
    (printLine, _showInputPrompt, _finishCommand) must delete it first.

    :param text: Prompt text to use. Defaults to the resolved self.prompt.
    :type text: Optional[str]
    :param style: Registered style to apply to the prompt text.
    :type style: str
    :rtype: None
    """
    promptText = self._resolvePrompt() if text is None else text
    tagName = self.styleTags.get(style)
    self.insert("end", promptText, tagName if tagName else ())
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
      import traceback
      traceback.print_exc()  # goes through sys.stderr -> registry -> this terminal
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
    return result

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

  def _handleCtrlD(self, event: tk.Event) -> str:
    """Signal EOF to a pending input() call, mimicking terminal Ctrl+D semantics.

    :rtype: str
    """
    if self._awaitingReply:
      self._awaitingReply = False
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
    tagName = f"style_{name}"
    tagOptions: dict[str, object] = {}
    if fg is not None:
      tagOptions["foreground"] = fg
    if bg is not None:
      tagOptions["background"] = bg
    if font is not None:
      tagOptions["font"] = font
    self.tag_configure(tagName, **tagOptions)
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
    self.tag_configure(tagName, **tagOptions)
    self.adHocTagCache[key] = tagName
    return tagName

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
  
  n = 0
  def nprompt():
    global n
    n += 1
    return f'{n}> '
    
  if __name__ == "__main__":
    gui = False
    terminal:AbstractTerminal
    if gui:
      root = tk.Tk()
      terminal = TerminalWidget(root, onLine=onLine, prompt=nprompt, bg="black", fg="lime", insertbackground="lime") #type: ignore[arg-type]
      terminal.pack(fill="both", expand=True)
      root.mainloop()
    else:
      terminal = PlainTextTerminal(onLine, prompt=nprompt)
    
