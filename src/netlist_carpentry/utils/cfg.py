"""Module for handling global configuration of Netlist Carpentry."""


class Config:
    """
    Configuration class containing application settings and constants.

    This class provides a centralized location for storing configuration data,
    making it easier to manage and modify application settings.
    """

    def __init__(self) -> None:
        """Initializes the configuration class."""

        self.log_level = 3
        """
        The level of logging, with higher values indicating more verbose logging.

        - Log level 5 does only print fatal errors leading to a program crash.
        - Log level 4 does also print errors that could be catched and the program does not necessarily crash.
        - Log level 3 does also print warnings.
        - Log level 2 prints all of the above as well as standard info messages about the program's state or progress.
        - Log level 1 print every message, including debug messages.

        Defaults to 3.
        """
        self.print_source_module = False
        """
        Whether to print the source module (i.e. the module issuing a message) for each log message,
        which is useful for debugging. Defaults to False.
        """
        self.id_external = '__'
        """The identifier used for external naming conventions, e. g. for write-out into a Verilog file. Defaults to '__' (two underscores)."""
        self.id_internal = '§'
        """The identifier used for internal naming conventions, e. g. for instance handling. Defaults to '§'."""

        self.allow_detached_segments = False
        """Whether to allow port or wire segments to exist without a parent object. Defaults to False, raising a DetachedSegementError whenever a segment exists without a parent"""


CFG = Config()
"""Global config object for storing all program configuration data."""
