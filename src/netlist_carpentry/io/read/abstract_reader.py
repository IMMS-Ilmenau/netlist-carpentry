"""Base module for reading circuit content from a text file."""

from pathlib import Path
from typing import Union

from netlist_carpentry.core.circuit import Circuit


class AbstractReader:
    def __init__(self, path: Union[str, Path]):
        if isinstance(path, str):
            path = Path(path)
        self.path = path

    def read(self) -> object:
        raise NotImplementedError('Not implemented in abstract class!')

    def transform_to_circuit(self, name: str = '') -> Circuit:
        raise NotImplementedError('Not implemented in abstract class!')
