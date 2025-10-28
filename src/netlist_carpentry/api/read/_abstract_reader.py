from pathlib import Path
from typing import Union


class _AbstractReader:
    def __init__(self, path: Union[str, Path]):
        if isinstance(path, str):
            path = Path(path)
        self.path = path

    def read(self) -> object:
        raise NotImplementedError('Not implemented in abstract class!')
