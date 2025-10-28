import datetime
import inspect
import logging
import os
import shutil
from typing import Callable, List, Mapping, Tuple

from rich.console import Console, ConsoleRenderable
from rich.highlighter import NullHighlighter
from rich.logging import RichHandler as _RichHandler
from rich.theme import Theme

from netlist_carpentry import CFG

RICH_THEME: Mapping[str, str] = {
    'DEBUG': 'bright_cyan',
    'INFO': 'gray50',
    'WARNING': 'bold orange1',
    'ERROR': 'bold bright_red',
    'CRITICAL': 'bold bright_red',
}


class Log:
    """
    Not very useful class. This is only to store some staticial information and
    variables, which are needed for formatting purposes by the logger, so all
    messages start at the same column after the `DEBUG`/`INFO`/`ERROR`/... and
    module name entries.
    """

    _init_finished: bool = False
    """
    Flag to display whether the logging initialization process is finished. If
    this value is False, the log has not been fully initialized and any message
    sent to the logger will be ignored. Is set to `True` automatically at the
    end of the initialization phase
    """

    file_path = ''
    """
    The path to the log file, where all log messages will be saved.
    """

    longest_caller_name = 48
    """
    This variable holds the length of the module name (plus package path) with
    the most characters. This is needed for formatting purposes by the logger,
    so all messages start at the same column after the `DEBUG`/`INFO`/`ERROR`/
    ... and module name entries.
    """

    fatals_quantity = 0
    """
    How many fatal errors have been encountered during the run. Incremented
    with every fatal error encountered.
    """

    errors_quantity = 0
    """
    How many catched errors have been encountered during the run. Incremented
    with every catched error encountered.
    """

    warns_quantity = 0
    """
    How many warnings have been encountered during the run. Incremented with
    every warning encountered.
    """

    def _highlight(self, message: str, fcn_to_highlight: Callable[..., None]) -> None:
        """
        Highlights a given message by printing it surrounded by borders.

        Args:
            message (str): The message to be highlighted.
            fcn_to_highlight (Callable): A function that will print the formatted
                message. This could be any callable object that accepts a string,
                such as `print`, but preferably is a logging function (e.g. self.info,
                self.debug, ...)

        Returns:
            None
        """
        fcn_to_highlight('#' + (len(message) + 4) * '=' + '#')
        fcn_to_highlight('|  ' + message + '  |')
        fcn_to_highlight('#' + (len(message) + 4) * '=' + '#')

    def debug_highlighted(self, message: str) -> None:
        """Adds a highlighted DEBUG message to the logger."""
        self._highlight(message, self.debug)

    def debug(self, message: str) -> None:
        """Adds a DEBUG message to the logger."""
        if self._init_finished and CFG.log_level <= 1:
            logging.debug(self.format_string(message))

    def info(self, message: str) -> None:
        """Adds an INFO message to the logger."""
        if self._init_finished and CFG.log_level <= 2:
            logging.info(self.format_string(message))

    def info_highlighted(self, message: str) -> None:
        """Adds a highlighted INFO message to the logger."""
        self._highlight(message, self.info)

    def warn(self, message: str) -> None:
        """Adds a WARNING message to the logger."""
        if self._init_finished and CFG.log_level <= 3:
            logging.warning(self.format_string(message))
            self.warns_quantity += 1

    def error(self, message: str) -> None:
        """Adds an ERROR message to the logger."""
        if self._init_finished and CFG.log_level <= 4:
            logging.error(self.format_string(message))
            self.errors_quantity += 1

    def fatal(self, message: str) -> None:
        """Adds a FATAL message to the logger."""
        if self._init_finished and CFG.log_level <= 5:
            logging.fatal(self.format_string(message))
            self.fatals_quantity += 1

    def fatal_and_exit(self, message: str, exception: type) -> None:
        """
        Adds a FATAL message to the logger and ends the program by raising the
        given exception.

        Args:
            message (str): The message to log.
            exception (type): The exception class to raise, e.g. `ValueError`.
        """
        self.fatal(message)
        self.finish()
        raise exception(message)

    def mute(self) -> None:
        """
        Disable all following logging messages. Script outputs are still printed to
        the console.
        """
        logging.getLogger().setLevel(logging.getLevelName(50))

    def unmute(self) -> None:
        """Undoes the muting."""
        logging.getLogger().setLevel(logging.getLevelName(int(CFG.log_level) * 10))

    def format_string(self, message: str) -> str:
        """
        Formats the given string to be a fancy console message with the name of the module
        causing the message (if `CFG.print_source_module` is `True`), as well as the message itself.
        The modified message is then returned.
        If `CFG.print_source_module` is set to `False`, the original message is returned instead.
        """
        if not CFG.print_source_module:
            return message

        # Update the longest caller name if necessary
        caller_name = self.get_caller_name()
        self.longest_caller_name = max(len(caller_name), self.longest_caller_name)

        # Calculate the padding, ensuring it's non-negative
        padding = max(0, self.longest_caller_name - len(caller_name))
        return f'[{caller_name}]:{" " * padding}{message}'

    def get_caller_name(self, skip_frames: List[str] = ['log']) -> str:
        """
        Returns the name of the caller module together with the calling function.

        This is needed for printing log messages and determining the module sending
        the logging entry. `skip_frames` is a list of strings with the names of
        modules that should be excluded. For example:

            Top Frame:  package1.module1.func1
            2nd Frame:  package1.module1.func2
            3rd Frame:  package1.module2.func3
            skip_frames:["module1"]

        In this case, the return value will be `module2.func3`, because the two top
        frames contain the excluded module. The main usage is the `log` module, for
        example:

            Top Frame:  log.format_string
            2nd Frame:  log.info
            3rd Frame:  util.connect_two_instances
            skip_frames:["log"]

        In this case, the return value will be `util.connect_two_instances`, which is
        then used for the logger to print the source of the logging call.
        """
        for f in inspect.stack():
            skip = False
            for s in skip_frames:
                if str(s) in f.filename:
                    skip = True
            if not skip:
                return f'{f.filename[f.filename.rfind("/") + 1 : f.filename.rfind(".")]}.{f.function}'
        return 'invalid_caller_name'

    def finish(self, start_time: float = -1, end_time: float = -1) -> None:
        """
        Outputs error and warning summary, and disables the logger afterwards.

        Args:
            start_time (float): The start time of the program execution.
            end_time (float): The end time of the program execution.
        """
        self.report()
        spent_time = round(end_time - start_time, 2)
        self.info('Completed all tasks' + f' in {spent_time} seconds!' if spent_time > 0 else '!')
        logging.basicConfig(handlers=[], force=True)

    def report(self) -> None:
        """
        Prints a summary of warnings and errors encountered up to this point during
        runtime. Can be called anytime to get information over the already
        encountered errors and warnings.
        """
        fatal_str = str(self.fatals_quantity) + ' Critical Error(s), ' if self.fatals_quantity > 0 else ''
        self.info('Found ' + fatal_str + str(self.errors_quantity) + ' Error(s) and ' + str(self.warns_quantity) + ' Warning(s)!')


class RichHandler(_RichHandler):
    """
    Custom logging handler that renders output with Rich.

    Overrides formatting and adds custom levels.
    """

    def render_message(self, record: logging.LogRecord, message: str) -> ConsoleRenderable:
        """Render message text in to Text.

        Applies style to message text for special levels.
        """
        level_name = record.levelname
        if level_name in RICH_THEME:
            style = RICH_THEME[level_name]
            pad_len = 10 - len(level_name)
            message = f'[{style}]{level_name}:{" " * pad_len}{message}[/{style}]'
            record.markup = True

        return super().render_message(record, message)


def initialize_logging(output_dir: str = CFG.output_dir + 'logs/', no_file: bool = False, custom_file_name: str = '') -> bool:
    """
    Sets up the initial configuration for the logging module.

    Args:
        output_dir (str): The directory where log files will be saved. Defaults to `CFG.output_dir + 'logs/'`.
        no_file (bool): If True, logging to a file will be disabled. Defaults to False.
        custom_file_name (str): A custom file name to use for logging. Defaults to an empty string, in which case the log file name will be generated based on on the current timestamp and log level.

    Returns:
        bool: Whether an error occurred during initialization.
    """
    timestamp = datetime.datetime.now()
    timestamp_str = timestamp.strftime('%Y%m%d_%H_%M_%S')
    log_level_name = logging.getLevelName(int(CFG.log_level) * 10)

    # Set the file path to None if no_file is True, otherwise create a log file name
    fname = custom_file_name if custom_file_name != '' else f'{timestamp_str}_{log_level_name}.log'
    Log.file_path = '' if no_file else f'{output_dir}{fname}'

    # Create handlers for the logger
    handlers, error_occurred = _create_handlers(output_dir, no_file)

    # Set up basic logging configuration with the created handlers
    logging.basicConfig(level=log_level_name, handlers=handlers, force=True)

    # Mark the initialization as finished
    Log._init_finished = True
    return error_occurred


def _create_handlers(output_dir: str, skip_file_creation: bool) -> Tuple[List[logging.Handler], bool]:
    """
    Creates handlers for the logger.

    Args:
        output_dir (str): The directory where log files will be saved.
        skip_file_creation (bool): If True, logging to a file will be disabled.

    Returns:
        tuple: A tuple containing the list of created handlers and an error flag.
    """
    # if detection yields small (e.g. 80, which is often default width), bump it up
    cols = max(shutil.get_terminal_size((200, 20)).columns, 120)
    shell_handler = RichHandler(
        console=Console(theme=Theme(RICH_THEME), force_terminal=True, force_jupyter=False, width=cols),
        markup=True,
        show_time=False,
        show_level=False,
        show_path=False,
        rich_tracebacks=True,
        highlighter=NullHighlighter(),
    )
    shell_handler.setFormatter(logging.Formatter('%(message)s'))
    handlers: List[logging.Handler] = [shell_handler]
    error_occurred = False

    if not skip_file_creation:
        try:
            # Create the output directory if it does not exist
            os.makedirs(output_dir, exist_ok=True)

            # If a file path is specified, create a FileHandler for logging to a file
            if Log.file_path != '':
                fhandler = logging.FileHandler(Log.file_path, 'w')
                fhandler.setFormatter(logging.Formatter('[ %(asctime)s ] %(levelname)s\t%(message)s'))
                handlers.append(fhandler)
        except Exception:
            # Mark an error as occurred if permission is denied
            error_occurred = True
    return handlers, error_occurred


LOG = Log()
