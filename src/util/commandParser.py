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
'''
  .. inheritance-diagram:: 
                RedoCommand
                IntermediateCommandWord
                TopCommandParser
                MutatingCommandGenerator
                GenFromCommand
                GenFromFunction
                CommandContext
                NoValue
      :parts: 1
      :private-bases: 
      :top-classes: util.commandParser.Parsable

This module defines the following command hierarchy:

  :py:class:`Parsable` *abstract* (requires *commandName, defineParse()*)
  
  - :attr:`~util.commandParser.Parsable.commandName` defines the commandName of the command
  - :attr:`Parsable.topParser` the root parser
  - :attr:`Parsable.immediateSuper` the parent *SubParsable*
  - :attr:`Parsable.parser` the actual *argParse.ArgumentParser*.
  - :py:meth:`~util.commandParser.Parsable._makeParser` responsible for defining the argparse definition.  In this case, calls *addCommand()* on the topParser to make any intermediate subcommands as defined by spliting the *commandName*.

    :py:class:`SubParsable` Non-terminal parser holding subparsers.
    
    - :attr:`SubParsable.immediateSuper` 
    - :py:meth:`SubParsable._makeParser` (override) calls *addCommaand()* on *immediateSuper*
    - :py:meth:`SubParsable.addCommand` 
    
      :py:class:`TopCommandParser`
      
      - :attr:`TopCommandparser.doList`
      - :attr:`TopCommandparser.defaults`
      - :attr:`TopCommandparser.decoders`
      - :attr:`TopCommandparser.debug`
      - :attr:`TopCommandparser.args`
      - :py:meth:`TopCommandparser._makeParser`
      - :py:meth:`TopCommandparser._strToComList` (class method)
      - :py:meth:`TopCommandparser._comListToStr` (class method)
      - :py:meth:`TopCommandparser.parseLine`
      - :py:meth:`TopCommandparser.lastArgs`
      - :py:meth:`TopCommandparser.parse`
      - :py:meth:`TopCommandparser.loadCommands`
      
      :py:class:`IntermediateCommandWord`
      
    :py:class:`CommandGenerator` terminal node if the command tree.  NOT a command, but generators :py:class:`utils.command.Command` objects.
    
    - :py:meth:`CommandGenerator.defineParse` (abstract) sets the actual *argparse* definition for the command.
    - :py:meth:`CommandGenerator.do` (abstract) executes the command
     
      :py:class:`MutatingCommandGenerator` *abstract* (requires *_makeCommand()*)
      
      - :py:meth:`MutatingCommandGenerator._makeCommand`
      - :py:meth:`MutatingCommandGenerator.do`
        
        :py:class:`GenFromCommand`
        
        - :py:meth:`GenFromCommand._execute`
        - :py:meth:`GenFromCommand.defineParse`
  
      :py:class:`NonMutatingCommandGenerator` *abstract* (requires *_execute()*)
      
      - :py:meth:`NonMutatingCommandGenerator._execute`
      - :py:meth:`NonMutatingCommandGenerator.do`
  
        :py:class:`GenFromFunction`

        - :py:meth:`GenFromCommand._makeCommand`
        - :py:meth:`GenFromCommand.defineParse`

        :py:class:`~util.commandParser.UndoCommand`
        
        :py:class:`~util.commandParser.RedoCommand`
        
        :py:class:`~util.commandParser.HelpCommand`
        
        :py:class:`~util.commandParser.DebugCommand`
        
  :py:class:`CommandContext` a class that acts as a container for methods, 
  signatures, and *Command* classes that define commands that are both 
  callable and *argparse* (command-line style) parsable.
  
Created on Nov 1, 2024

.. codeauthor:: Rob Kremer <robkremer@me.com>

------------------------
'''

from __future__ import annotations
from util.command import Command, DoList
from abc import abstractmethod, ABC
from argparse import Namespace
import argparse
from typing import override, Optional, Any, cast, Callable, Iterable, Type
import shlex # for split with quotes
import sys
import logging
from util.utils import makeParserFromFunc, strToBool
import inspect
import ast
import util

logger:util.Logger = util.getLogger(__name__)

DecodersType = dict[str, Callable[[str], Any]]


################################################################################
############### Classes to modify argparse for extended behaviour ##############
################################################################################    

class AbbrevSubParsersAction(argparse._SubParsersAction):
  '''
  Replacement for *argparse._SubParsersAction* to allow for abbreviations.
  '''
  def __call__(self, parser, namespace, values, option_string=None):
    '''
    If we don't have an exact match for the command commandName, search for a unique
    prefix match, and go with that one. Error out if there is not match or 
    the match is not unique.

    :param parser:
    :type parser:
    :param namespace:
    :type namespace:
    :param values:
    :type values:
    :param option_string:
    :type option_string:
    :returns:
    :rtype:
    '''
    given = values[0]
    choices = list(self._name_parser_map.keys())

    # Exact match — proceed normally
    if given in choices:
      return super().__call__(parser, namespace, values, option_string)

    # Prefix match
    matches = [c for c in choices if c.startswith(given)]
    if len(matches) == 1:
      values = [matches[0]] + values[1:]
      return super().__call__(parser, namespace, values, option_string)
    elif len(matches) > 1:
      parser.error(f"ambiguous subcommand {given!r}: matches {matches}")
    else:
      parser.error(f"unknown subcommand {given!r}")


class _AbbrevChoices(dict[str,Any]):
  """
  A replacement for the choices dictionary.  Pretends every value is a valid 
  choice, but displays the real choices.  Thus, we must rely on 
  :py:class:`AbbrevSubParsersAction` to catch the error of a non existant choice. 
  """
  def __contains__(self, item: object) -> bool:
    '''
    :param item:
    :type item: object
    :returns:
    :rtype: bool
    '''
    return True  # bypass pre-validation; AbbrevSubParsersAction handles it


class ArgumentParser(argparse.ArgumentParser):
  "Trivial override of *argparse.ArgumentParser* to prevent it from exiting on error."
  def error(self, message):
    '''
    :param message:
    :type message:
    '''
    self.print_usage(sys.stderr)
    raise SyntaxError(f'{self.prog}: error: {message}\n')
  

################################################################################
############################# U #########################
################################################################################    

def funNameToCommandName(funName:str) -> str:
  '''
  In :py:class:`CommandContext` classes, this defines the translation from a 
  "signature" method commandName to it's corresponding :py:class:`util.command.Command`
  class commandName.

  :param funName:
  :type funName: str
  :returns:
  :rtype: str
  '''
  return f'_{funName[0].upper()}{funName[1:]}'

def commandNameToFunName(commandName:str) -> str:
  '''
  In :py:class:`CommandContext` classes, this defines the translation from a 
  :py:class:`util.command.Command` class commandName to it's corresponding "signature" method commandName .

  :param commandName:
  :type commandName: str
  :returns:
  :rtype: str
  '''
  return f'{commandName[1].lower()}{commandName[2:]}'

################################################################################
############################# MutatingCommandGenerator #########################
################################################################################    

class Parsable(ABC):
  '''
  This is NOT a command, but a command definition used by a *TopCommandParser* to
  generate *Command* instances suitable for an *UndoList*. Thus, *MutatingCommandGenerator*
  objects act like a *class* whereas *Command* objects act like an object.
  '''     
  
  def __init__(self, commandName:str, topParser:TopCommandParser, **kwargs):
    '''
    :param commandName: The commandName of the command.
    :type commandName: str
    :param topParser: The top parser in the tree of parsers. Used by commands 
      to access defaults, etc.
    :type topParser: TopCommandParser
    :param kwarg: Keyword arguments to be passed along the *ArgumentParser* constructor
      for this command.
    :param kwargs:
    :type kwargs:
    '''
    super().__init__()
    assert isinstance(topParser, TopCommandParser), f'MutatingCommandGenerator.__init__(): Second parameter should be a TopCommandParser, got {topParser.__class__.__name__}'
    
    self.commandName = commandName
    'The name of the command. The name can be separated by spaces and will be split into subcommands on the spaces.'
    
    self.topParser:TopCommandParser = topParser # used by various commands to access defaults, etc
    'The top *SubParsable* in the hierarchy.'
    
    self.immediateSuper:SubParsable
    'The immediate super-*SubParsable*.'
    
    self.parser:ArgumentParser
    'The associated *argparse.ArgumentParser*.'
    
    self.parser, self.immediateSuper = self._makeParser(**kwargs)

  def _makeParser(self, **kwargs) -> tuple[ArgumentParser, SubParsable]:
    '''
    :param kwarg: Keyword arguments to be passed along the *ArgumentParser* constructor
      for this command.
    :returns: The result of *self.topParser.addCommand(self.commandName, self, **kwargs)*.
    :rtype: tuple[ArgumentParser, SubParsable]

    Used to instantiates self.parser in the constructor.

    :param kwargs:
    :type kwargs:
    '''
    parser:argparse.ArgumentParser
    immediateSuper:SubParsable
    parser, immediateSuper = self.topParser.addCommand(self.commandName, self, **kwargs)
    return parser, immediateSuper
    
  def __str__(self) -> str:
    '''
    :return: Name of the command or the path to the command (space separated)
      if this is a multi-word command. 
    :rtype: str
    '''
    return f'{str(self.immediateSuper)} {self.commandName}'
    

class SubParsable(Parsable):
  '''
  A trivial command used as a subparser for multi word commands like *pip*'s 
  *"pip install ..."* or *"pip uninstall ..."*.  These objects act as internal
  nodes in the tree of command words.
  '''
  
  def __init__(self, commandName:str, topParser:TopCommandParser, immediateSuper:SubParsable, help:str, description:str, **kwargs):
    '''
    :param commandName: The commandName of the command.
    :type commandName: str
    :param topParser: The top parser in the tree of parsers. Used by commands 
      to access defaults, etc.
    :type topParser: TopCommandParser
    :param immediateSuper: Another *SubParsable* under which this one will insert
      itself.
    :type immediateSuper: SubParsable
    :param help: The help string for this particular word in the command tree.
    :type help: str
    :param description: The description string for this particular word in the
      command tree.
    :type description: str
    :param kwarg: Keyword arguments to be passed along the *ArgumentParser* constructor
      for this command.
      
    Adds to the *super* version by creating subparsers (calling 
    *ArgParser.add_subparsers()*) and setting itself up as in internal command
    tree node.

    :param kwargs:
    :type kwargs:
    '''
    self.immediateSuper = immediateSuper # needed for str() before the Parsable constructor
    Parsable.__init__(self, commandName, topParser, help=help, **kwargs)
    self.subparsers:argparse._SubParsersAction = self.parser.add_subparsers(
          title=self.commandName, 
          prog=self.commandName, 
          dest=self.commandName,
          help=help,
          required=True,
          description=description) #,dest='_subparserName')
    self.commands:list[Parsable] = []

  def _makeShortDescription(self):
    '''
    Assuming *self.parser* contains a help description, make a short, summary
    description for it. The short description will be displayed in the super-
    parsers help description listing of subcomands, the long one will be in this
    parser's specific help.
    '''
    description = self.parser.description
    if description is not None:
      for action in self.immediateSuper.subparsers._choices_actions:
        if action.dest == self.commandName:
          shortDescription = description[:description.find(".")]+"."
          action.help = shortDescription
          break
        
class CommandGenerator(SubParsable):
  '''
  This is the top level class for all actual commands that have a *ArgParse*
  definition (and thus can be called from a command line).
  '''
  def __init__(self, commandName:str, topParser:TopCommandParser, **kwargs):
    '''
    :param topParser: A *TopCommandParser* object that this object will add
      itself using *topParser.addCommand(self)*
    :type topParser: :py:class:`TopCommandParser`
    :param kwarg: Keyword arguments to be passed along the *ArgumentParser* constructor
      for this command.
    :param commandName:
    :type commandName: str
    :param kwargs:
    :type kwargs:
    '''
    Parsable.__init__(self, commandName, topParser=topParser, **kwargs)
    self._makeShortDescription()
    # self.defineParse()
    
    # # Make sure the parent parser has it's help defined by adding this parser's 
    # # description to the parent parser so that it shows up in the parent help 
    # # summary
    # # TODO: This might be too lengthy for the summary. Maybe just first sentence?
    # assert self.immediateSuper.parser._subparsers is not None
    # # Get the subparsers action object from the parent parser
    # sp_action = self.immediateSuper.parser._subparsers._group_actions[0]  # the _SubParsersAction
    # # Each entry in _choices_actions is a pseudo-action with .help
    # for action in getattr(sp_action, "_choices_actions", []):
    #   if action.dest == self.commandName and (action.help is None or action.help == "PLACEHOLDER"):
    #     action.help = self.parser.description
    #     break
    #

  @override
  def _makeParser(self, **kwargs) -> tuple[ArgumentParser, SubParsable]:
    '''
    :param kwarg: Keyword arguments to be passed along the *ArgumentParser* constructor
      for this command.
    :returns: The result of *self.topParser.addCommand(self.commandName, self, **kwargs)*.
    :rtype: tuple[ArgumentParser, SubParsable]

    Used to instantiates self.parser in the constructor.

    :param kwargs:
    :type kwargs:
    '''
    self.parser, self.immediateSuper = super()._makeParser(**kwargs)
    self.defineParse()
    
    # Make sure the parent parser has it's help defined by adding this parser's 
    # description to the parent parser so that it shows up in the parent help 
    # summary
    # TODO: This might be too lengthy for the summary. Maybe just first sentence?
    assert self.immediateSuper.parser._subparsers is not None
    # Get the subparsers action object from the parent parser
    sp_action = self.immediateSuper.parser._subparsers._group_actions[0]  # the _SubParsersAction
    # Each entry in _choices_actions is a pseudo-action with .help
    for action in getattr(sp_action, "_choices_actions", []):
      if action.dest == self.commandName and (action.help is None or action.help == "PLACEHOLDER"):
        action.help = self.parser.description
        break
    return self.parser, self.immediateSuper
    
  @abstractmethod
  def defineParse(self):
    '''
    The actual *argparse* definition of the command consisting of 
    *self.parser.add_argument()* calls, etc.
    '''
    pass
      
  @abstractmethod
  def do(self, args:Namespace) -> Any:
    '''
    Execute this command using *args*.

    :param args:
    :type args: Namespace
    :returns:
    :rtype: Any
    '''
    pass
    
  
class NonMutatingCommandGenerator(CommandGenerator):  
  '''
  This is the top level class for all actual commands that do not modify the
  program's data (such as informational commands), and thus are not entered
  into the undo list.  As a result they may have a simple implementation without
  the need of a :py:class:`util.command.Command` subclass. Instead, you may simply
  override the :py:meth:`_execute() <NonMutatingCommandGenerator._execute>` method
  with the command's implementation.
  '''
  def __init__(self, commandName:str, topParser:TopCommandParser, **kwargs):
    '''
    See :py:class:`CommandGenerator` for parameter doc.
      
    This is technically not a generator, but a simple implmenetion of a command
    that DOES NOT CHANGE the state of the data, such as a query.  It will **not**
    be entered on the undo list. There is no associated :py:class:`util.commmand.Command`
    object associated with it.

    :param commandName:
    :type commandName: str
    :param topParser:
    :type topParser: TopCommandParser
    :param kwargs:
    :type kwargs:
    '''
    # if "help" not in kwargs:
    #   kwargs["help"] = f'help for {commandName}'
    super().__init__(commandName, topParser=topParser, **kwargs)
    
  
  @override
  def do(self, args:Namespace) -> Any:
    '''
    Execute this command using *args*.

    :param args:
    :type args: Namespace
    :returns:
    :rtype: Any
    '''
    return self._execute(args)
  
  @abstractmethod
  def _execute(self, args:Namespace) -> Any:
    '''
    Subclasses should override this method to provide the implementation of the
    command.

    :param args:
    :type args: Namespace
    :returns:
    :rtype: Any
    '''
    pass

class GenFromFunction(NonMutatingCommandGenerator):
  # TODO: get rid of *containingClassObject*
  '''
  A command generator for a context's method that has no *Command* class: calling it just runs the method (it isn't undoable).
  '''
  def __init__(self, fun:Callable, commandParser:TopCommandParser, containingClassObject:Optional[Any]=None, commandName:Optional[str]=None, **kwargs):
    '''
    :param fun:
    :type fun: Callable
    :param commandParser:
    :type commandParser: TopCommandParser
    :param containingClassObject:
    :type containingClassObject: Optional[Any]
    :param commandName:
    :type commandName: Optional[str]
    :param kwargs:
    :type kwargs:
    '''
    assert callable(fun)
    if commandName is None: # create a commandName from the function's commandName.
      commandName = fun.__name__
      commandName = " ".join(commandName.split('_')) # make it a multi-word commandName by splitting on underscores
    self.fun:Callable = fun
    self.containingClassObject:Any = containingClassObject
    # if "help" not in kwargs:
    #   kwargs["help"] = f'help for {commandName}'
    NonMutatingCommandGenerator.__init__(self, commandName, commandParser, **kwargs) # will call the defineParse() method

  @override
  def defineParse(self):
    '''
    Build up the existing *self.parser* from the params and doc of the defining 
    *self.fun* function.
    '''
    # This will add the attributes to the current parser.
    makeParserFromFunc(self.fun,
                       ignoreParam=lambda name: name=="commandName" or name=="self" or name.startswith("_"), 
                       parser=self.parser,
                       typeHandlers=self.topParser.decoders)
    
  @override
  def _execute(self, args:Namespace) -> Any:
    # sig = inspect.signature(self.fun)
    # kwargs = vars(args)
    # kwargs2:dict[str, Any] = dict()
    # for paramName in kwargs: # remove anything in kwargs that isn't in the signature
    #   if paramName in sig.parameters:
    #     kwargs2[paramName] = kwargs[paramName]
    '''
    :param args:
    :type args: Namespace
    :returns:
    :rtype: Any
    '''
    pargs, kwargs = fixKwargs(fun=self.fun,
                       args=[], 
                       kwargs=vars(args),
                       defaults=self.topParser.defaults, 
                       decoders=self.topParser.decoders)

    return self.fun(*pargs, **kwargs) if self.containingClassObject is None else self.fun(self.containingClassObject, *pargs, **kwargs)


class MutatingCommandGenerator(CommandGenerator):
  '''
  And abstract class used by *TopCommandParser* requiring the *_makeCommand()* method
  to create a *Command* object suitable for undo lists.
  '''
  def __init__(self, commandName, commandParser:TopCommandParser, **kwargs):
    '''
    See :py:class:`CommandGenerator` for parameter doc.
      
    This is NOT a command, but a command definition used by a *TopCommandParser* to
    generate *Command* instances suitable for an *UndoList*. Thus, *MutatingCommandGenerator*
    objects act like a *class* whereas *Command* objects act like an object.

    :param commandName:
    :type commandName:
    :param commandParser:
    :type commandParser: TopCommandParser
    :param kwargs:
    :type kwargs:
    '''
    super().__init__(commandName, topParser=commandParser, **kwargs)
    
  @override
  def do(self, args:Namespace) -> Any:
    '''
    :param args: A namespace as generated by *ArgParse*.
    :type args: Namespace
    
    Builds the :py:class:`util.command.Command` object (by calling the 
    *_makeCommand()* method), enters it into the undo
    list, and executes it. This method method is usually called by the the command
    parser.

    :returns:
    :rtype: Any
    '''
    cmdObject:Command = self._makeCommand(args)
    if self.topParser.doList is not None:
      return self.topParser.doList.do(cmdObject)
    else:
      return cmdObject.do(self.args)
  
  @abstractmethod
  def _makeCommand(self, args:Namespace) -> Command:
    '''
    :param args:
    :type args: Namespace
    :returns:
    :rtype: Command
    '''
    pass
  
class GenFromCommand(MutatingCommandGenerator):
  '''
  A command generator for a context's method that has a *Command* class (eg: *move()* and *_Move*): running it makes the *Command* and does it on the undo list.
  '''
  def __init__(self, commandClass:type[Command], commandParser:TopCommandParser, commandName:Optional[str]=None, **kwargs):
    '''
    :param commandClass:
    :type commandClass: type[Command]
    :param commandParser:
    :type commandParser: TopCommandParser
    :param commandName:
    :type commandName: Optional[str]
    :param kwargs:
    :type kwargs:
    '''
    assert issubclass(commandClass, Command)
    if commandName is None:
      commandName = commandClass.__name__
      commandName = commandNameToFunName(commandName) #commandName[1].lower()+commandName[2:]
      commandName = " ".join(commandName.split('_'))
    self.commandClass:type[Command] = commandClass
    # if "help" not in kwargs:
    #   kwargs["help"] = f'help for {commandName}'
    MutatingCommandGenerator.__init__(self, commandName, commandParser, **kwargs)
    
  @override
  def _makeCommand(self, args:Namespace) -> Command:
    '''
    :param args:
    :type args: Namespace
    :returns:
    :rtype: Command
    '''
    pargs, kwargs = fixKwargs(fun=self.commandClass.__init__,
                       args=[], 
                       kwargs=vars(args),
                       defaults=self.topParser.defaults, 
                       decoders=self.topParser.decoders)
    return self.commandClass(*pargs, **kwargs)
  
  @override
  def defineParse(self):
    '''
    Build up the existing *self.parser* from the __init__ params and doc of 
    the defining *Command* class given in *self.commandClass*.
    '''
    init = getattr(self.commandClass, "__init__", None)
    assert callable(init)
    makeParserFromFunc(init, 
                       ignoreParam=lambda name: name=="commandName" or name=="self" or name.startswith("_"), 
                       parser=self.parser,
                       typeHandlers=self.topParser.decoders)
    
    

# ################################################################################
# ##################### SelfContainedParsableCommandDef ##########################
# ################################################################################    
#
# class SelfContainedParsableCommandDef(MutatingCommandGenerator, ABC):
#   '''
#   Objects inheriting from this class are intended for use in the interactive
#   command-line interface only, and so do not have a corresponding *Command* 
#   class (which should be use by programmatic interfaces).
#   '''
#
#   def __init__(self, commandParser, immediateSuper:Optional[SubParsable]=None, changesState:bool=True, help:str=None, **kwargs):
#     '''
#     :param commandParser: A *TopCommandParser* object that this object will add
#       itself using *commandParser.addCommand(self)*
#     :param changesState: If true, declares that the generated commands are 
#       state-changing commands and will be added to the undo command list. otherwise
#       the generated commands will NOT be added to the undo command list.
#     :param help: The help string to be passed on to *argpares* . Defaults to 
#       "<self.commandName> command help".
#     :param kwarg: Keyword arguments to be passed along the *ArgumentParser* constructor
#       for this command.
#
#     '''
#     MutatingCommandGenerator.__init__(self, commandParser, immediateSuper=immediateSuper, changesState=changesState, help=help, **kwargs)
#
#   @abstractmethod
#   def do(self, **kwargs) -> Any:
#     'Execute the command according the arguments in the *args* namespace.'
#     return None
#
#   @abstractmethod
#   def undo(self, cache:Any, **kwargs:Unpack) -> Any:
#     '''
#     Undo the command according the arguments in the *args* namespace.
#
#     :Note: in the case of a command marked as *changesState == False* this
#       method will never be called.
#     '''
#     assert self.changesState, 'Expected changesState to be True' # see note above
#     return None
#
#   def _makeCommand(self, args:Namespace) -> Command:
#     return _ArgParseCommand(self, args, self.changesState)
#
#
# ################################################################################
# ################################ _ArgParseCommand ##############################
# ################################################################################    
#
# class _ArgParseCommand(Command):
#   '''
#   A convenience class for *SelfContainedParsableCommandDef* subclasses that
#   essentially performs callbacks for the *do()* and *undo()* methods.
#   '''
#
#   def __init__(self, definition:SelfContainedParsableCommandDef, namespace:Namespace, changesState=True):
#     super().__init__(definition.commandName, changesState)
#     self.definition = definition
#     self.namespace = namespace
#     self.cache = None
#
#   def do(self) -> Tuple[Any, Any]: # returns (result, undoData)
#     '''
#     Execute to do() method of of the parent *SelfContainedParsableCommandDef*, which will
#     pass back the result and some appropriate undo information (for example,
#     some previous state info).
#
#     :return: A tuple of (result, undoData) where "result" is the result of the 
#       execution (may be None) and some appropriate data to be passed to the 
#       undo() method later.
#     '''
#     result, self.cache = self.definition.do(**vars(self.namespace) if self.namespace is not None else dict())
#     return result
#
#   def undo(self) -> Any:
#     return self.definition.undo(self.cache, **vars(self.namespace))
#
#   @override
#   def __str__(self):
#     return f'{self.definition.commandName}'

################################################################################
##################################### Undo #####################################
################################################################################
    
# class UndoCommand(NonMutatingCommandGenerator): 
#
#   def __init__(self, commandParser:TopCommandParser):
#     help="Undo the last command executed."
#     super().__init__("undo", commandParser, help=help, description=help)
#
#   @override
#   def _execute(self, args:Namespace) -> list[str]|str|Any:
#     if args.queue: return self.topParser.doList.undoQueue()
#     if args.next : return self.topParser.doList.nextUndo()
#     return self.topParser.doList.undo()
#
#   @override
#   def defineParse(self):
#     self.parser.add_argument('--queue', '-q', action='store_true', help="List the actions in the undo queue.")
#     self.parser.add_argument('--next', '-n', action='store_true', help="List the action next in the undo queue.")
  

################################################################################
##################################### redo #####################################
################################################################################
    
class RedoCommand(NonMutatingCommandGenerator): # TODO: change this to the non-SelfContained version
  
  '''
  The *redo* command (see *UndoCommand*).
  '''
  def __init__(self, topParser:TopCommandParser):
    '''
    :param topParser:
    :type topParser: TopCommandParser
    '''
    help="Redo the last command that was undone by the undo command."
    super().__init__("redo", topParser=topParser, help=help, description=help)
    
  @override
  def _execute(self, args:Namespace) -> list[str]|str|Any:
    '''
    :param args:
    :type args: Namespace
    :returns:
    :rtype: list[str] | str | Any
    '''
    if args.queue: return self.topParser.doList.redoQueue()
    if args.next : return self.topParser.doList.nextRedo()
    return self.topParser.doList.redo()
 
  @override
  def defineParse(self):
    self.parser.add_argument('--queue', '-q', action='store_true', help="List the actions in the redo queue.")
    self.parser.add_argument('--next', '-n', action='store_true', help="List the actions in the redo queue.")
    
# ################################################################################
# ##################################### help #####################################
# ################################################################################
#
# class HelpCommand(NonMutatingCommandGenerator):
#
#   def __init__(self, topParser:TopCommandParser):
#     help="show a list of all commands"
#     super().__init__("help", topParser, help=help, description=help)
#
#   @override
#   def _execute(self, args:Namespace) -> Optional[tuple[Any, Any]]:
#     if args.topic is not None and len(args.topic) > 0:
#       line = ""
#       for t in args.topic:
#         line += ' '+t
#       self.topParser.parseLine(f'{line} -h')
#     else:
#       self.topParser.parser.print_help(sys.stdout)
#     return None
#
#   @override
#   def defineParse(self):
#     self.parser.add_argument('topic', nargs="*", default=None, help='[repeatable] any legal command, as defined by "help".')
#

################################################################################
##################################### debug ####################################
################################################################################
    
# class DebugCommand(NonMutatingCommandGenerator):
#   '''
#   "debug [-on=<bool>]
#   '''
#   def __init__(self, topParser:TopCommandParser):
#     super().__init__("debug", topParser, 
#                      help="set or clear the debug flag, which controls if tracebacks are shown",
#                      description="set or clear the debug flag, which controls if tracebacks are shown")
#
#   @override
#   def defineParse(self):
#     self.parser.add_argument('state', nargs='?', choices=["on", "off"])
#
#   @override
#   def _execute(self, args:Namespace) -> bool:
#     debug = args.state
#     if debug == "on":
#       self.topParser.debug = True
#       logger.print("Debug is now on")
#     elif debug == "off":
#       self.topParser.debug = False
#       logger.print("Debug is now off")
#     else:
#       logger.print(f'Debug is {"on" if self.topParser.debug else "off"}')
#     return self.topParser.debug
  
class NoValue:
  '''
  Used to represent no value for an object when *None* is otherwise a possible
  value. 
  '''
  pass
  
 
################################################################################
############################# IntermediateCommandWord ##########################
################################################################################
    
class IntermediateCommandWord(SubParsable):
  '''
  Used for multi-word commands like "model node update". Obviously, these must
  have subcommands, so the subparsers list *self.subparsers* is instantiated in the
  constructor.
  '''
  
  def __init__(self, commandName:str, commandParser:TopCommandParser, 
               immediateSuper:SubParsable, 
               help:Optional[str]=None, description:Optional[str]=None, **kwargs):
    '''
    :param commandName:
    :type commandName: str
    :param commandParser:
    :type commandParser: TopCommandParser
    :param immediateSuper:
    :type immediateSuper: SubParsable
    :param help:
    :type help: Optional[str]
    :param description:
    :type description: Optional[str]
    :param kwargs:
    :type kwargs:
    '''
    if help is None:
      help = f'For more detail, type "help {commandName} <choice>".'
    if description is None:
      description = f'"{commandName}" is an intermediate command word that needs to be followed with an additional choice. For more detail, type "help {commandName} <choice>".'
    SubParsable.__init__(self, commandName, commandParser, immediateSuper, help=help, description=description, **kwargs)
    
  
################################################################################
################################# TopCommandParser #############################
################################################################################
    
class TopCommandParser(SubParsable):
  '''
  A *Command* container meant to be the central hub for interpreting and executing
  command language commands through iterative calls to *parse()* or *parseLine()*.
  '''
  
  def __init__(self, 
               commandName:str, 
               doList:Optional[DoList]=None, 
               loadCommandsFrom:list[CommandContext]=[],
               ignore:Callable[[str], bool]=lambda name: name.startswith("_"), 
               defaults:Optional[dict[str,Any]]=None,
               decoders:Optional[DecodersType]=None,
               description:str="",
                **args):
    '''
    :param commandName: The commandName of the command.
    :type commandName: str
    :param description: What *help* (with no arguments) says before the list
      of commands: eg: the syntax of the language's arguments.
    :type description: str
    :param doList: An undo list to use. By default, a new one will be created.
    :type doList: DoList
    :param kwarg: Keyword arguments to be passed along the *ArgumentParser* constructor.
      
    Adds to the *super* version by setting itself as an empty root command,
    insuring there is a dolist, and instantiating
    *undo, redo, help*, and *debug* commands. The *debug* command merely sets or
    clear a self.debug boolean for other commands to use as appropriate.

    :param loadCommandsFrom:
    :type loadCommandsFrom: list[CommandContext]
    :param ignore:
    :type ignore: Callable[[str], bool]
    :param defaults:
    :type defaults: Optional[dict[str, Any]]
    :param decoders:
    :type decoders: Optional[DecodersType]
    :param args:
    :type args:
    '''
    self.description:str = description
    'What *help* says before the list of commands.'
    
    # The *immediageSuper* is self...
    SubParsable.__init__(self, commandName, self, self, help='List of commands', description="Top level commands")
    
    self.doList:DoList = doList if doList is not None else DoList()
    'All mutating commands will be added to the the dolist.'
    
    self.defaults:dict[str,Any] = defaults if defaults is not None else dict()
    'Defaults are automatically filled in whenever a parameter name matches a default name and has a NoValue value. Name->Any.'
    
    self.decoders:DecodersType = decoders if decoders is not None else dict()
    'Used to translate str parameters to actual objects. Type->function.'
    
    self.debug:bool = False
    'Debug flag'
    
    self.args:Optional[Namespace] = None
    'The last *argparse* arguments used.'
    
    self.currentContextClass:Optional[Type[CommandContext]] = None
    
    # UndoCommand(self)
    # RedoCommand(self)
    # HelpCommand(self)
    # DebugCommand(self)
    for moduleOrClass in loadCommandsFrom:
      self.loadCommands(moduleOrClass, ignore)


  def addCommand(self, commandName:str, command:Parsable, context:Optional[CommandContext]=None, **kwargs) -> tuple[ArgumentParser, SubParsable]:
    '''
    :param commandName: The commandName if the command. May be a simple commandName like "delete", in
      which case the command will be added to this node in the command tree; or
      it may be a multi-word command path like "modify node commandName", in which case the
      any intermediate nodes in the command tree will be created (if they don't
      already exist) and the command will be added at the last commandName in the the path.
    :type commandName: str
    :param command: A *Parsable* object to add to the command tree in the position
      as described above.
    :type command: Parsable
    :param kwargs: keyword arguments to be passed to the new command's parser's 
      constructor (an *ArgumentParser*)
    :returns: the *ArgumentParser* created and this *SubParsable*'s immediate
      parent in the command tree (another *SubParsable*).
    :rtype: tuple[ArgumentParser, SubParsable]
    
    Add a command to this container and create and return a sub parser for that
    command. The idea being that commands that change state are *Command* commands
    and interact with the *DoList* while commands that are strictly informational
    are *MutatingCommandGenerator* (:> *Command* ) don't interact with the *DoList* .
    
    .. Note:: The commandName parameter may contain spaces indicating a chain of commands, thus
      you might have command names "modify node" which will create a subparser
      "modify" with command "node" to execute the command's code. If later you
      add command "modify relation", the "relation" command will be added to 
      "modify"'s list of commands. Thus you have commands:
        
        > modify node ...

        > modify relation ...
        
        > modify      <<Raises a SyntaxError>>

    :param context:
    :type context: Optional[CommandContext]
    '''
    commandPath:list[str] = commandName.split(maxsplit=1)
    #help = kwargs["help"] if "help" in kwargs else (command.help if hasattr(command, "help") and command.help is not None else f'help for {commandName}')
    
    parent:SubParsable = self
    while len(commandPath) > 1:
      found:bool = False
      for c in [spc for spc in self.commands if isinstance(spc, SubParsable)]: #type: ignore[assignment]
        if c.commandName == commandPath[0]:
          found = True
          break
      commandLevel:list[Parsable]
      if found: # keep searching at the next depth
        #return c.addCommand(commandPath[1], command, **kwargs)
        parent = c
      else: # create a new subparser
        help_ = None if self.currentContextClass is None else self.currentContextClass.commandHelp.get(commandPath[0], None)
        new = IntermediateCommandWord(commandPath[0], self.topParser, immediateSuper=self, help=help_) # move down the tree of owners
        parent.commands.append(new)
        #return new.addCommand(commandPath[1], command, **kwargs)
        parent = new
      commandPath = commandPath[1:]
      
    assert len(commandPath) == 1
    if "help" not in kwargs: # "help" is required in add_parser(), otherwise the command doesn't show up in the choices.
      kwargs["help"] = "PLACEHOLDER" # this will be replaced in CommandGenerator.__init__()
    if "formatter_class" not in kwargs:
      kwargs["formatter_class"] = argparse.RawDescriptionHelpFormatter
    command.parser = parent.subparsers.add_parser(commandPath[0], **kwargs)
    command.parser.set_defaults(_command=command)
    
    command.immediateSuper = parent
    parent.commands.append(command)
    command.commandName = commandPath[0]
    return command.parser, parent
    
  def _makeParser(self, **kwargs) -> tuple[ArgumentParser, SubParsable]:
    '''
    :param kwargs:
    :type kwargs:
    :returns:
    :rtype: tuple[ArgumentParser, SubParsable]
    '''
    if "help" in kwargs:
      del kwargs["help"]
    descr = self.description
    epilog = """
Type "<cmd...> -h" or "help <cmd...>" for more detail on each command."""
    parser =  ArgumentParser(prog=self.commandName, add_help=True,
              allow_abbrev=True, description=descr, epilog=epilog,
              formatter_class=argparse.RawDescriptionHelpFormatter, **kwargs)
    # parser.register('action', 'parsers', AbbrevSubParsersAction)
    return parser, self
    
  # @override
  # @property
  # def commandName(self):
  #   return self._name
    
    
  # def findCommandGenerator(self, commandName:str) -> Optional[CommandGenerator]:
  #   commandPath:list[str] = commandName.split()
  #   commands:list[Parsable] = self.commands
  #   c:SubParsable
  #   for pathElem in commandPath[:-1]:
  #     found = False
  #     for c in [cmd for cmd in commands if isinstance(cmd, SubParsable)]:
  #       if c.commandName == pathElem:
  #         found = True
  #         break
  #     commandLevel:list[Parsable]
  #     if found: # keep searching at the next depth
  #       owner = c
  #     else: # create a new subparser
  #       return None
  #   assert isinstance(c, CommandGenerator)
  #   return c
    
  @staticmethod
  def _strToComList(line:str) -> list[str]:
    '''
    :param line:
    :type line: str
    :returns:
    :rtype: list[str]
    '''
    return shlex.split(line)#, posix=False)
    
  @staticmethod
  def _comListToStr(com:list[str]) -> str:
    '''
    :param com:
    :type com: list[str]
    :returns:
    :rtype: str
    '''
    result = ""
    for c in com:
      result += ("<" + str(c) + "> ")
    return result[:-1] if len(result)>0 else ""
    
  def parseLine(self, line:str) -> Any:
    '''
    :param line: A command line to interpret and execute.
    :type line: str
    :returns: The result of executing the command.
    :rtype: Any
    
    Interpret the *line* string by spliting it respecting quotes, then call *parse()*.
    '''
    return self.parse(self._strToComList(line))
  
  def lastArgs(self):
    '''
    Return the set of args parsed from the last parse.

    :returns:
    :rtype:
    '''
    if self.args is None:
      return dict()
    logger.info(f'lastArgs = {self.args}:{self.args.__class__.__name__}')
    return vars(self.args)
    
  def parse(self, argsList:list[str]) -> Any:
    '''
    - Parse the command line using parser
    - if it creates a command, execute it either on the doList if we have one or otherwise
    - return the result of the execution

    :param argsList:
    :type argsList: list[str]
    :returns:
    :rtype: Any
    '''
    assert self.parser._subparsers is not None
    if len(argsList) == 0:
      return None
    
    result = None
    
    # allow abbreviateions
    for action in self.parser._subparsers._actions: # desperately try to make it do abbreviations...
      if isinstance(action, argparse._SubParsersAction):
        action.__class__ = AbbrevSubParsersAction
        break
    for group in self.parser._action_groups:
      for action in group._actions:
        if isinstance(action, argparse._SubParsersAction):
          action.__class__ = AbbrevSubParsersAction
          action.choices = _AbbrevChoices(action._name_parser_map)
                      
    try:
      # pop off *prog* if it's the first on the args list
      if len(argsList)>1 and argsList[0] == self.parser.prog:
        argsList = argsList[1:]
      self.args = self.parser.parse_args(argsList)
    except Exception as ex: # handle errors generated by interpreting the command line
      msg = f'{self.__class__.__name__}.parse("{shlex.join(argsList)}"):\n  Exception while parsing: {ex.__class__.__name__}: {ex}'
      ex.__class__(msg)
      print(f'Oops!: {ex}')
      raise ex
    except SystemExit as ex:
      if ex.code == 0: # 0 means argparse probably printed some help info
        #print(f'System exit called: {ex}')
        return ex.code
      else:
        raise SyntaxError(f"ArgumentParser.parse_args() called sys.exit({ex.code})")
      
    try:
      # strip out the "_command" arg.
      if not hasattr(self.args, "_command"):
        return None
      commandGen:CommandGenerator = self.args._command
      del self.args._command
      
      # result = self._runCommand(commandGen)
      result = commandGen.do(self.args)
    except Exception as ex: # handle errors generated by executing the command line
      msg = f'{self.__class__.__name__}.parse("{shlex.join(argsList)}"):\n Exception while executing {commandGen.commandName}: {ex.__class__.__name__}: {ex}'
      ex.add_note(msg)
      raise ex
      
    return result
  
  def loadCommands(self, context:CommandContext, ignore:Callable[[str], bool]=lambda name: name.startswith("_")):
    
    '''
    :param context:
    :type context: CommandContext
    :param ignore:
    :type ignore: Callable[[str], bool]
    '''
    def addSynonyms(cls, c):
      # for any declared synonyms, associate the parser according to the synonym dict
      for syn in cls.commandSynonyms.get(c.commandName, []):
        c.immediateSuper.subparsers._name_parser_map[syn] = c.parser
        #print(f'added synonym {syn} to {c.immediateSuper.commandName}: {c.immediateSuper.subparsers._name_parser_map}')
        
        # The subparsers _ChoicesPseudoAction entries are what show in help
        for pseudoAction in c.immediateSuper.subparsers._choices_actions:
          if pseudoAction.dest == c.commandName:
            suffix = f'(also: {syn}) '
            if pseudoAction.help is None: pseudoAction.help = ""
            if not pseudoAction.help.startswith(suffix):
              pseudoAction.help = suffix + (pseudoAction.help)
            break
                  
    def load(cls, log):
      classes = dict(inspect.getmembers(cls, inspect.isclass))
      for funName, fun in inspect.getmembers(cls, inspect.isfunction):
        if not ignore(funName):# and not commandName in classes:
          commandName = funNameToCommandName(funName)
          if commandName in classes: # make a GenFromCommand
            if not issubclass(classes[commandName], Command):
              logger.warning(f'Class {commandName} corresponds to function {funName}(), but expected it to be a subclass of Command, but it was of type {cls.__name__}. Ignoring it.')
            else: 
              try:
                c = GenFromCommand(classes[commandName], self) # the constructor will add the object to our self.commands list
                addSynonyms(cls, c)
                            
                if logger.getEffectiveLevel() <= logging.DEBUG:
                  logger.print(f'  {commandName:30} "{c.commandName}"') #type: ignore[attr-defined]
              except ValueError as ex: # we might be reloading a superclass, so ignore the 'conflicing subparser' error
                if log:
                  logger.exception('Failed to load command class "%s": %s: %s', commandName, ex.__class__.__name__, str(ex))
              except Exception as ex:
                  logger.exception('Failed to load command class "%s": %s: %s', commandName, ex.__class__.__name__, str(ex))
          else: # make a GenFromFunction
            try:
              c1 = GenFromFunction(fun, self, containingClassObject=context) # the constructor will add the object to our self.commands list
              addSynonyms(cls, c1)
              if logger.getEffectiveLevel() <= logging.DEBUG:
                logger.print(f'  {funName:30} "{c1.commandName}"') #type: ignore[attr-defined]
            except Exception as ex:
              if log:
                logger.exception('Failed to load function "%s": %s: %s', funName, ex.__class__.__name__, str(ex))
      
    if logger.getEffectiveLevel() <= logging.DEBUG:
      logger.print(f'Loading the following commands from context "{context.__class__.__name__}":') #type: ignore[attr-defined]

    self.currentContextClass = context.__class__
    load(context.__class__, True)
    for c in context.__class__.__mro__[1:-1]: # load from superclasses
      if issubclass(c, CommandContext):
        self.currentContextClass = c
        load(c, False) # not logging errors as the superclass may have already been loaded.
    self.currentContextClass = None
        
class CommandContext:
  
  '''
  A container of commands: each public method is a command, callable from code
  and parsable from a command line (its name's words, eg: *new_node* is "new
  node"; its parameters, the arguments and options). A method with a matching
  nested *Command* class (*move()* and *_Move*) is done through the undo list, so
  it can be undone. Arguments are converted by the context's *decoders*, and
  missing ones filled in from its *defaults*.
  '''
  commandSynonyms:dict[str, Iterable[str]] = dict()
  'The methodname -> list[synonym] defining synonyms for commands'
  
  optionSynonyms:dict[str, dict[str, list[str]]] = {
    "undo": {"queue": ["-q"], "next": ["-n"]},
    "redo": {"queue": ["-q"], "next": ["-n"]}
    }
  'The methodname -> (option -> list[synonym]) dict for command definitions in this context.'
  
  commandHelp:dict[str,str] = dict()
  'The command-name -> help-string dict for intermediate commands in this context.'

  def __init__(self, parser:Optional[TopCommandParser]=None):
    
    '''
    :param parser:
    :type parser: Optional[TopCommandParser]
    '''
    self.parser:TopCommandParser = parser if parser is not None else TopCommandParser("")
    'The associatated parser.'
    
    self.doList:DoList = self.parser.doList
    'The *DoList* for all mutating commands.'
    
    self.defaults:dict[str, Any] = self.parser.defaults
    'The defaults (name->value) dict for command definitions in this context.'
    self.defaults["_commandContext"] = self
    
    self.decoders:DecodersType = self.parser.decoders
    self._defineDecoders()
    '''
    The command-name -> decoder-function dict for method parameter types in
    this context.
    '''
  
    self._capture:CompositeCommandMgr|None = None
    'Used to capture commands to combine in a CompositeCommand.'
  
    self.parser.loadCommands(self)
    #print(f'CommandContext.__init__(): defaults@{id(self.defaults)}')

  def _defineDecoders(self):
    pass
    
  def __getattribute__(self, name: str) -> Any:
    '''
    :param name:
    :type name: str
    :returns:
    :rtype: Any
    '''
    attr = super().__getattribute__(name)
    try:
      # if this is a public method or function (private "_" ones -- helpers, which
      # loadCommands() doesn't make commands of either -- are left alone: no
      # defaults are filled in for them)
      if not name.startswith('_') and callable(attr):
        className = funNameToCommandName(name)#commandName[0].upper()+commandName[1:]

        #can't use hasattr() to determine if there is a corresponding command...
        shouldUseCommand = False
        try:
          object.__getattribute__(self, className) # raises if className is not an attribute
          shouldUseCommand = True
        except:
          pass

        sig = inspect.signature(attr)

        def commandWrapper(*args: Any, **kwargs: Any) -> Any:
          pargs, kwargs = fixKwargs(fun=object.__getattribute__(self, className if shouldUseCommand else name), 
                             args=list(args),
                             kwargs=kwargs, 
                             defaults=object.__getattribute__(self, "defaults"), 
                             decoders=object.__getattribute__(self, "decoders"))
          #print(f'CommandContext.__getattribute__(): defaults@{id(self.defaults)}')
          command:Command = object.__getattribute__(self, className)(*pargs, **kwargs) # construct the command
          if self._capture is None:
            ret = object.__getattribute__(self, "doList").do(command)
            #print(f"{commandName} command wrapped, pargs={pargs}, kwargs={kwargs}")
            return ret
          else:
            self._capture._addCommand(command)
            return lambda *args, **kwargs: None 
        
        def funWrapper(*args: Any, **kwargs: Any) -> Any:
          pargs, kwargs = fixKwargs(fun=object.__getattribute__(self, className if shouldUseCommand else name), 
                             args=list(args),
                             kwargs=kwargs, 
                             defaults=object.__getattribute__(self, "defaults"), 
                             decoders=object.__getattribute__(self, "decoders"))
          ret = object.__getattribute__(self, name)(*pargs, **kwargs)
          #print(f"{commandName} function wrapped. pargs={pargs}, kwargs={kwargs}")
          return ret

        return commandWrapper if shouldUseCommand else funWrapper
    except Exception as ex:
      print(f'************ {ex.__class__.__name__} in __getattribute__(): {ex}')
    return attr
  
  def _setCapture(self, capture:CompositeCommandMgr|None):
    '''
    :param capture:
    :type capture: CompositeCommandMgr | None
    '''
    if capture is None:
      self._capture = None
    else:
      assert self._capture is None
      self._capture = capture
      
  def help(self, topic:list[str]|None) -> None:
    '''
    Show a list of all commands pr help on a specific topic"
    
    :param topic: The topic print help for.
    :type topic: list[str]|None
    '''
    if topic is not None and len(topic) > 0:
      line = ""
      for t in topic:
        line += ' '+t
      self.parser.parseLine(f'{line} -h')
    else:
      self.parser.parser.print_help(sys.stdout)
    return None
    
  def debug(self, state:str|None=None, /) -> bool:
    '''
    Get or turn on or off the debug state. When debug is on, tracebacks are 
    printed for errors; when it's off, simple exception messages are printed.
    If no argument is present, the current debug state is printed.
    
    :param state: can be missing, "on", "off", "true", or "false", or unique
      abbreviations of those.
    :type state: str|None
    :returns: The new (or current) debug state.
    :rtype: bool
    '''
    debug = state
    if debug is not None:
      debug = debug.lower()
      self.parser.debug = strToBool(debug)
    logger.print(f'Debug is {"on" if self.parser.debug else "off"}')
    return self.parser.debug
  
  def undo(self, /, queue:bool=False, next:bool=False):
    '''
    Undo the last command executed.
    
    :param queue: Return a list of strings describing the actions in the undo
       queue.
    :type queue: bool
    :param next: Return a string describing the action next in the undo queue.
    :type next: bool
    :returns: If neither of the options is present, returns whatever the result
      of undoing the last action.
    :rtype: Any  
    '''
    if queue: return self.parser.doList.undoQueue()
    if next : return self.parser.doList.nextUndo()
    return self.parser.doList.undo()
    
  # class UndoCommand(NonMutatingCommandGenerator): 
  #
  # def __init__(self, commandParser:TopCommandParser):
  #   help="Undo the last command executed."
  #   super().__init__("undo", commandParser, help=help, description=help)
  #
  # @override
  # def _execute(self, args:Namespace) -> list[str]|str|Any:
  #   if args.queue: return self.topParser.doList.undoQueue()
  #   if args.next : return self.topParser.doList.nextUndo()
  #   return self.topParser.doList.undo()
  #
  # @override
  # def defineParse(self):
  #   self.parser.add_argument('--queue', '-q', action='store_true', help="List the actions in the undo queue.")
  #   self.parser.add_argument('--next', '-n', action='store_true', help="List the action next in the undo queue.")

  def redo(self, /, queue:bool=False, next:bool=False): 
    '''
    Redo the last command that was undone by the undo command.
    
    :param queue: Return a list of strings describing the actions in the redo
       queue.
    :type queue: bool
    :param next: Return a string describing the action next in the redo queue.
    :type next: bool
    :returns: If neither of the options is present, returns whatever the result
      of redoing the action.
    :rtype: Any  
    '''
    if queue: return self.parser.doList.redoQueue()
    if next : return self.parser.doList.nextRedo()
    return self.parser.doList.redo()
  
# class RedoCommand(NonMutatingCommandGenerator): # TODO: change this to the non-SelfContained version
#
#   def __init__(self, topParser:TopCommandParser):
#     help="Redo the last command that was undone by the undo command."
#     super().__init__("redo", topParser=topParser, help=help, description=help)
#
#   @override
#   def _execute(self, args:Namespace) -> list[str]|str|Any:
#     if args.queue: return self.topParser.doList.redoQueue()
#     if args.next : return self.topParser.doList.nextRedo()
#     return self.topParser.doList.redo()
#
#   @override
#   def defineParse(self):
#     self.parser.add_argument('--queue', '-q', action='store_true', help="List the actions in the redo queue.")
#     self.parser.add_argument('--next', '-n', action='store_true', help="List the actions in the redo queue.")
 
  # This is a signature only, the class Default will be used when this is called.  
  def default(self, defName:str, value:Any=NoValue, /, _defaults:Optional[dict[str,Any]]=None) -> Any:
    '''
    Set or get a parser-global command default. If *value* is omitted the current
    default is simply returned.
    
    :param commandName: The commandName of the param to have the default filled in.
    :type commandName: str
    :param value: The default value.
    :type value: Any|None
    :param defName:
    :type defName: str
    :param _defaults:
    :type _defaults: Optional[dict[str, Any]]
    :returns:
    :rtype: Any
    '''
    pass

  class _Default(Command):
    '''
    The command that sets one of a context's defaults (see *CommandContext.default()*).
    '''
    def __init__(self, defName:str, value:Any=NoValue, /, _commandContext:Optional[CommandContext]=None):
      '''
      Set or get a parser-global command default. If *value* is omitted the current
      default is simply returned.
      
      :param commandName: The commandName of the param to have the default filled in.
      :type commandName: str
      :param value: The default value.
      :type value: Any|None
      :param defName:
      :type defName: str
      :param _commandContext:
      :type _commandContext: Optional[CommandContext]
      '''
      assert _commandContext is not None
      super().__init__("default")
      self.defaults = _commandContext.defaults
      self.defName = defName
      self.value = value
      self.oldValue = _commandContext.defaults[defName]
      
    @override
    def do(self):
      '''
      :returns:
      :rtype:
      '''
      super().do()
      if self.value is NoValue:
        #print(f'CommandContext.Default.do(): defaults@{id(self.defaults)}')
        return self.defaults[self.defName]
      else:
        #print(f'CommandContext.Default.do(): defaults@{id(self.defaults)}')
        self.defaults[self.defName] = self.value
        return self.defaults[self.defName]
      
    @override
    def undo(self):
      '''
      :returns:
      :rtype:
      '''
      super().undo()
      self.defaults[self.defName] = self.oldValue
      return self.oldValue
    
    @override
    def delete(self):
      super().delete()
      self.defaults = None #type: ignore[assignment]
      self.value = None
      self.defName = None #type: ignore[assignment]
      
    @override
    def __str__(self) -> str:
      '''
      :returns:
      :rtype: str
      '''
      return f'{super().__str__()} {self.defName} {self.value}'
    
class CompositeCommand(Command):
  '''
  Several commands as one: done in order, and undone in reverse order.
  '''
  def __init__(self, commands:list[Command]):
    '''
    :param commands:
    :type commands: list[Command]
    '''
    super().__init__("<composite command>")
    self.commands:list[Command] = commands

  @override
  def do(self)->Any:
    '''
    :returns:
    :rtype: Any
    '''
    ret = super().do()
    for c in self.commands:
      c.do()
    return ret

  @override
  def undo(self)->Any:
    '''
    :returns:
    :rtype: Any
    '''
    ret = super().undo()
    for c in reversed(self.commands): # (later commands may depend on earlier ones)
      c.undo()
    return ret

  @override
  def delete(self):
    super().delete()
    self.commands = None #type: ignore[assignment]


class CompositeCommandMgr:
  '''
  A context manager that groups the commands called on a *CommandContext*
  inside its ``with`` block into one *CompositeCommand* -- one entry on the undo
  list. The commands are queued, not run, until the block ends.
  '''
  def __init__(self, context:CommandContext):
    '''
    :param context:
    :type context: CommandContext
    '''
    self.commands:list[Command] = []
    self.context:CommandContext = context
  
  def __enter__(self):
    '''
    :returns:
    :rtype:
    '''
    self.context._setCapture(self)
    return self
        
  def __exit__(self, exc_type, exc_val, exc_tb):
    '''
    :param exc_type:
    :type exc_type:
    :param exc_val:
    :type exc_val:
    :param exc_tb:
    :type exc_tb:
    :returns:
    :rtype:
    '''
    self.context._setCapture(None)
    composite = CompositeCommand(self.commands)
    self.context.doList.do(composite)
    # Returning True would suppress exceptions if they occur
    return False 
      
  def _addCommand(self, command:Command):
    '''
    :param command:
    :type command: Command
    '''
    self.commands.append(command)

def fixKwargs(fun:Callable, args:list[Any], kwargs:dict[str,Any], 
              defaults:dict[str,Any], 
              decoders:DecodersType) -> tuple[list[Any],dict[str,Any]]:
  '''
  Given a function and a kwargs dict where the kwargs may be from a argParse
  *Namespace* (containing extra elements), return a kwargs dict that's legal
  for the given function. But also:
  
    - fill in any defaults for param names that match *defaults* keys have None
      values.
    - decode any str param values for types in the *fun* signature that have
      str values in *kwargs*.
    - decode each element of a list-of-str param value (eg: from an argparse
      ``nargs``) with the decoder for the element type of a ``list[...]`` in the
      annotation (or failing that, for the annotation itself) -- unless that
      allows str (eg: ``list[str|GraphObject]``: the function looks them up).
    - decoders that don't take ``**kwargs`` run first; those that do are then
      called with the (already decoded) other params as *kwargs*.
    - a value that won't decode stays a str if the annotation (or the list's
      element type) allows str; otherwise a ValueError naming the param is
      raised, chained from the decoder's exception.

  :param fun:
  :type fun: Callable
  :param args:
  :type args: list[Any]
  :param kwargs:
  :type kwargs: dict[str, Any]
  :param defaults:
  :type defaults: dict[str, Any]
  :param decoders:
  :type decoders: DecodersType
  :returns:
  :rtype: tuple[list[Any], dict[str, Any]]
  '''
  sig = inspect.signature(fun)
  retKwargs = kwargs.copy() # fixed kwargs
  retArgs = list(args)      # fixed args
  
  # remove anything in kwargs that isn't in the signature
  for paramName in kwargs: 
    if paramName not in sig.parameters:
      del retKwargs[paramName]
  
  # fill in defaults
  for paramName, param in sig.parameters.items():
    val = kwargs.get(paramName, None)
    if val is None and paramName in defaults:
      retKwargs[paramName] = defaults[paramName] # fill in a default

  def splitTopLevelUnion(annotation: str) -> list[str]:
    """Split a type-annotation string into its top-level ``|`` union
    members, leaving any ``|`` nested inside subscripted generics
    (``list[...]``, ``dict[...]``, etc.) untouched.
  
    :param annotation: The annotation as a string, e.g. from
        ``str(param.annotation)`` or a ``from __future__ import
        annotations`` deferred-evaluation annotation.
    :type annotation: str
    :returns: Ordered list of the top-level union members as strings. If
        the annotation is not a top-level union, this is a single-element
        list containing the (re-serialized) original annotation.
    :rtype: list[str]
    :raises SyntaxError: If ``annotation`` is not a valid Python expression.
    """
    tree = ast.parse(annotation, mode="eval")
    parts: list[str] = []
  
    def flatten(node: ast.expr) -> None:
      """Recursively unpack a left-associated chain of ``|`` BinOps.
  
      :param node: Current AST node being visited.
      :type node: ast.expr
      :rtype: None
      """
      if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        flatten(node.left)
        flatten(node.right)
      else:
        parts.append(ast.unparse(node))
  
    flatten(tree.body)
    return parts

  def elementTypes(annotation:str) -> list[str]:
    """Return the union members of the element type of any ``list[...]``
    member of *annotation* (eg: ``GraphObject|list[GraphObject]`` gives
    ``["GraphObject"]``)."""
    ret:list[str] = []
    for t in splitTopLevelUnion(annotation):
      node = ast.parse(t, mode="eval").body
      if isinstance(node, ast.Subscript) and ast.unparse(node.value) in ("list", "List"):
        ret.extend(splitTopLevelUnion(ast.unparse(node.slice)))
    return ret

  def decode(typ:str, val:str) -> Any:
    """Decode *val* with the decoder for *typ*, passing the other params if the decoder wants them."""
    dsig = inspect.signature(decoders[typ])
    dparams = dsig.parameters
    dkwargs:dict[str,Any] = dict()
    if "kwargs" in dparams:
      #dkwargs["params"] = retKwargs
      dkwargs = retKwargs
    return decoders[typ](val, **dkwargs)

  def wantsKwargs(typ:str) -> bool:
    """True if the decoder for *typ* takes the other (decoded) params as **kwargs."""
    return "kwargs" in inspect.signature(decoders[typ]).parameters

  def message(ex:Exception) -> str:
    """The message of *ex* (a KeyError's str() would show it quoted)."""
    return str(ex.args[0]) if isinstance(ex, KeyError) and len(ex.args) == 1 else str(ex)

  # work out which decoder (if any) applies to each str (or list-of-str) param
  todo:list[tuple[str,str,Any,bool,bool]] = [] # (paramName, typ, val, isStrList, allowsStr)
  for paramName, param in sig.parameters.items():
    val = kwargs.get(paramName, None)
    isStrList = isinstance(val, list) and len(val) > 0 and all(type(v) is str for v in val)
    if type(val) is not str and not isStrList: # if the type has already been dealt with by argparse ignore it
      continue
    if param.annotation is inspect._empty: # nothing we can do without type info
      continue
    # a list from argparse (nargs) is decoded element-wise, preferably by a list[...] member's element type
    if isStrList:
      types:list[str] = elementTypes(param.annotation) or splitTopLevelUnion(param.annotation)
      if "str" in types: # (the function takes names, and looks them up itself)
        continue
    else:
      types = splitTopLevelUnion(param.annotation)
    typ = next((t for t in types if t in decoders), None)
    if typ is not None:
      todo.append((paramName, typ, val, isStrList, "str" in types))

  # decode in dependency order: decoders that don't need the other params (eg:
  # Model) first, then those that do (eg: GraphObject), so they see decoded values.
  todo.sort(key=lambda item: wantsKwargs(item[1]))
  for paramName, typ, val, isStrList, allowsStr in todo:
    try:
      if isStrList:
        retKwargs[paramName] = [decode(typ, v) for v in val]
      else:
        retKwargs[paramName] = decode(typ, val) # replace a str value with the decoded version
    except Exception as ex:
      if allowsStr: # leave the str for the function to deal with
        continue
      raise ValueError(f"--{paramName}: {message(ex)}") from ex
   
  for paramName, param in sig.parameters.items(): # look to fill in defaults
    # move any positional only elements to args
    if param.kind == param.POSITIONAL_ONLY and paramName in retKwargs and paramName != "self":
      retArgs.append(retKwargs[paramName])
      del retKwargs[paramName]
  return retArgs, retKwargs

