import os
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel

from netlist_carpentry import CFG, ON_WINDOWS
from netlist_carpentry.core.exceptions import YosysError

ShareStrategy = Literal['off', 'aggressive', 'fast']


class ReadConfig(BaseModel):
    files: List[Path]
    """A list of paths for readable design files, which Yosys should read.

    May contain Verilog, SystemVerilog, JSON and VHDL (if GHDL is installed and loaded).
    May also contain paths to directories.
    In this case, each file within the directory must be in one of the mentioned formats."""
    output: Optional[Path] = None
    """The path to the output location, where the resulting generic netlist will be stored.

    If None, no output file is generated. Does not affect the `json_path` property however.
    If `json_path` is specified, a JSON netlist will be printed regardless of the value of this property. Defaults to None.

    The path suffix (i.e. the file ending) determines whether the netlist is written in JSON, Verilog or SystemVerilog format."""
    top: Optional[str] = None
    """The top module to set. If None, the top module is auto-selected. Defaults to None."""
    json_path: Optional[Path] = None
    """The path where to save the intermediate JSON netlist. If None, it is only temporarily created and removed afterwards. Defaults to None."""
    techmaps: Optional[List[Path]] = None
    """Any techmaps to apply. Defaults to None, in which case no techmaps are applied."""
    share: ShareStrategy = 'off'
    """Whether Yosys should apply resource-sharing algorithms to simplify circuit size at the (possible) cost of timing."""
    environments: Optional[List[Path]] = None
    """Any additional environments to load. On Linux, this conforms to `source path/to/env`
    and is executed before Yosys is called. Defaults to None, in which case, no environments are activated."""
    yosys_plugins: Optional[List[str]] = None
    """Any additional Yosys modules to load when starting Yosys.

    Common plugins are GHDL and SLang. Loading both can be achieved with `yosys_plugins=["ghdl", "slang"]`."""
    no_hierarchy: bool = False
    """This property only has an effect if `top` is None, in which case a top module would be auto-selected.

    Whether to ignore the hierarchy completely. If True, the `hierarchy` pass is omitted completely. Defaults to False."""

    keep_memory_cells: bool = False
    """Whether to keep memory cells (with dedicated address and data ports) or split them down into FFs and MUX trees.

    If True, Yosys will introduce `mem_v2` cells whenever it infers a memory unit.
    If False, Yosys will map all memory cells to FFs and Mux trees."""

    insbuf: bool = True
    """Whether to insert buffer cells for directly connected wires. Defaults to True."""

    @property
    def yosys_executable(self) -> str:
        """The shell command to start Yosys. Defaults to `CFG.yosys_executable`, which provides the initially selected Yosys executable.

        Defaults of `CFG.yosys_executable` is `yosys`, which is normally used to run Yosys.
        If Netlist Carpentry is unable to start Yosys via `yosys`, it falls back to using `yowasp-yosys`.
        """
        return CFG.yosys_executable

    @property
    def script_template(self) -> str:
        return """\
{read}
{hierarchy}
proc; opt
{memory}
pmuxtree
{techmaps}
{share}
opt; clean
{insbuf}
{write}
"""

    @property
    def read_pass(self) -> str:
        """The formatted Yosys read passes for each file in `ReadConfig.files`."""
        read_cmds = []
        for f in self.files:
            if os.path.exists(f):
                read_cmds.extend(self._read_files(f))
            else:
                raise YosysError(f'Cannot collect read commands: No file {f!r} exists!')
        if not read_cmds:
            raise YosysError(f'No files to read! Input file list was {"[" + ", ".join(str(f) for f in self.files) + "]" if self.files else "empty!"}')
        return '\n'.join(read_cmds)

    def _read_files(self, f: Path) -> List[str]:
        ext_dict = {'.v': 'read_verilog', '.sv': 'read_verilog -sv', '.json': 'read_json', '.vhd': 'ghdl -read', '.vhdl': 'ghdl -read'}
        if self.yosys_plugins is not None and 'slang' in self.yosys_plugins:
            ext_dict['.sv'] = 'read_slang'
            ext_dict['.v'] = 'read_slang'
        if os.path.isdir(f):
            fs = []
            for file in sorted(os.listdir(f)):
                fs.extend(self._read_files(f / file))
            return fs
        elif f.suffix.lower() in ext_dict:
            return [f'{ext_dict[f.suffix.lower()]} {f.expanduser().resolve().as_posix()}']
        else:
            raise YosysError(f'Cannot find a Yosys read pass for {f.name!r}: Unknown format {f.suffix!r}!')

    @property
    def write_pass(self) -> str:
        ext_dict = {'.v': 'write_verilog', '.sv': 'write_verilog -sv', '.json': 'write_json'}
        if self.json_path is not None:
            json_write_pass = f'write_json {self.json_path.expanduser().resolve().as_posix()}\n'
        else:
            json_write_pass = ''
        if self.output is not None:
            out_path = self.output / 'out.v' if self.output.is_dir() else self.output
            if out_path.suffix.lower() in ext_dict:
                return f'{json_write_pass}{ext_dict[out_path.suffix.lower()]} {out_path.expanduser().resolve().as_posix()}'
            raise YosysError(f'Cannot find a Yosys write pass for {out_path.name!r}: Unknown format {out_path.suffix!r}!')
        return json_write_pass

    @property
    def hierarchy_pass(self) -> str:
        """The formatted Yosys hierarchy pass, depending on `ReadConfig.top` and `ReadConfig.no_hierarchy`."""
        if self.top is not None:
            return f'hierarchy -top {self.top}'
        return '' if self.no_hierarchy else 'hierarchy -auto-top'

    @property
    def memory_pass(self) -> str:
        """The formatted Yosys memory pass, with or without `-nomap`, depending on `ReadConfig.keep_memory_cells`."""
        return 'memory -nomap' if self.keep_memory_cells else 'memory'

    @property
    def techmap_pass(self) -> str:
        """The formatted Yosys techmap pass, where each techmap is applied in the order given in `ReadConfig.techmaps`."""
        if self.techmaps is not None:
            return '\n'.join(f'techmap -map {tm.expanduser().resolve().as_posix()}' for tm in self.techmaps)
        return ''

    @property
    def share_pass(self) -> str:
        """The formatted Yosys share pass for resource sharing as specified in `ReadConfig.share`.

        Sharing is disabled if `ReadConfig.share` is "off".
        """
        if self.share not in ['off', 'fast', 'aggressive']:
            raise YosysError(f'Unknown share option: {self.share!r}')
        return '' if self.share == 'off' else f'share -{self.share}'

    @property
    def insbuf_pass(self) -> str:
        """The formatted Yosys insbuf pass which inserts buffers between directly connected wires."""
        return 'insbuf; proc' if self.insbuf else ''

    @property
    def environment_activation(self) -> str:
        """The shell commands to activate the given environments."""
        source_cmd = '.' if ON_WINDOWS else 'source'
        return '\n'.join(f'{source_cmd} {p.expanduser().resolve()}' for p in self.environments or [])

    @property
    def yosys_plugin_str(self) -> str:
        """The formatted string that loads additional Yosys plugins."""
        return ' '.join(f'-m {m}' for m in self.yosys_plugins or [])

    def yosys_commands(self) -> str:
        """Formats the predefined Yosys script template with the current properties.

        Returns:
            str: The formatted Yosys script template, so that these commands form a synthesis flow
                that produces a generic netlist for the current properties of this ReadConfig.
        """
        return self.script_template.format(
            read=self.read_pass,
            hierarchy=self.hierarchy_pass,
            memory=self.memory_pass,
            techmaps=self.techmap_pass,
            share=self.share_pass,
            insbuf=self.insbuf_pass,
            write=self.write_pass,
        )

    def shell_script(self, path: Optional[Path] = None) -> List[str]:
        """Creates the content for the shell script (setup and yosys commands).

        This method collects the Yosys command and sets up environments (if given) and loads
        Yosys plugins (if specified), before the Yosys commands are written.
        The content is only written into a file if a `path` is given.

        Args:
            path (Optional[Path], optional): The path where to save the script content.
                If None, it will not be written to a file. Defaults to None.

        Returns:
            str: The content of the shell script (setup and yosys commands)
        """
        init = '#!/bin/env bash\n\n' if not ON_WINDOWS and path is not None else ''
        fail_on_error = "$ErrorActionPreference = 'Stop'" if ON_WINDOWS else 'set -e'
        script = f'{fail_on_error}\n{self.environment_activation}\n{self.yosys_executable} {self.yosys_plugin_str} -p "\n{self.yosys_commands()}"\n'
        if ON_WINDOWS:
            # Windows → PowerShell
            shell_cmd = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script]
        else:
            # Linux/macOS → bash
            shell_cmd = ['bash', '-c', script]
        if path is not None:
            with open(path, 'w') as f:
                f.write(init + script)
        return shell_cmd
