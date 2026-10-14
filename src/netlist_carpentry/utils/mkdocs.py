import os

from mkdocs.plugins import BasePlugin


class TqdmDocsFlagPlugin(BasePlugin):
    """Sets the env variable (`'NC_MKDOCS_BUILD'`) used to determine whether MkDocs is currently running."""

    def on_pre_build(self, config: object) -> None:
        os.environ['NC_MKDOCS_BUILD'] = '1'
