"""Module for handling equivalence checks with Yosys EQY."""

import os
import shutil
import subprocess
import tempfile
from contextlib import nullcontext
from pathlib import Path
from typing import List, Optional


class EqyWrapper:
    """
    Wrapper class for running Yosys EQY to prove the logical equivalence of two Verilog designs.
    It generates a .eqy script from a template and executes it using the Yosys EQY tool.
    """

    def __init__(self, path: str, overwrite: bool = False):
        """
        Initializes the EqyWrapper with the desired file path for the Yosys EQY script.

        Args:
            path (str): The path (including the desired file name) to the directory where the .eqy script will be saved.
                The path must not point to a directory or a file that already exists.
                To overwrite an existing file at this path, set overwrite to True.
            overwrite (bool, optional): If True, overwrites an existing file at the specified path.
                If False, raises a FileExistsError if an existing file at this path. Defaults to False.
        """
        self.path = Path(path)
        """The path to the directory where the .eqy script will be saved."""
        if self.path.exists() and not overwrite:
            raise FileExistsError(f'Path {self.path} already exists!')

    def format_template(self, gold_vfile_paths: List[str], gold_top_module: str, gate_vfile_paths: List[str], gate_top_module: str) -> str:
        """
        Formats the EQY template string with the provided input parameters.

        The gold Verilog files are the golden reference design files, while the gate Verilog files are the synthesized (gate-level) designs.
        In the scope of this framework, the gate designs refer to the modified or optimized versions of the original designs.

        Args:
            gold_vfile_paths (List[str]): A list of paths to the gold Verilog files.
            gold_top_module (str): The top module name for the gold design.
            gate_vfile_paths (List[str]): A list of paths to the gate Verilog files.
            gate_top_module (str): The top module name for the gate design.

        Returns:
            str: The formatted EQY template string.
        """
        template = """[gold]\n{gold_vsources}\n{gold_top_module}\nmemory_map\n\n[gate]\n{gate_vsources}\n{gate_top_module}\nmemory_map\n\n[strategy sat]\nuse sat\ndepth 10"""
        gold_vfiles = '\n'.join(f'read_verilog {p}' for p in gold_vfile_paths)
        gold_top_module = 'prep -top ' + gold_top_module if gold_top_module else ''
        gate_vfiles = '\n'.join(f'read_verilog {p}' for p in gate_vfile_paths)
        gate_top_module = 'prep -top ' + gate_top_module if gate_top_module else ''
        return template.format(gold_vsources=gold_vfiles, gold_top_module=gold_top_module, gate_vsources=gate_vfiles, gate_top_module=gate_top_module)

    def proc(self, gold_path: str, gold_top_module: str, gate_path: str, gate_top_module: str) -> None:
        dir_path = os.path.dirname(os.path.abspath(__file__))
        script_path = f'{dir_path}/eqy_proc.sh'
        subprocess.call(['chmod', 'u+x', script_path])
        subprocess.call([script_path, gold_path, gold_top_module], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.call([script_path, gate_path, gate_top_module], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def create_eqy_file(self, gold_vfile_paths: List[str], gold_top_module: str, gate_vfile_paths: List[str], gate_top_module: str) -> None:
        """
        Creates the EQY script file at the path `self.path`.

        The gold Verilog files are the golden reference design files, while the gate Verilog files are the synthesized (gate-level) designs.
        In the scope of this framework, the gate designs refer to the modified or optimized versions of the original designs.


        Args:
            gold_vfile_paths (List[str]): A list of paths to the gold Verilog files.
            gold_top_module (str): The top module name for the gold design.
            gate_vfile_paths (List[str]): A list of paths to the gate Verilog files.
            gate_top_module (str): The top module name for the gate design.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'w') as f:
            f.write(self.format_template(gold_vfile_paths, gold_top_module, gate_vfile_paths, gate_top_module))
        self.path.chmod(self.path.stat().st_mode | 0o111)  # chmod for user/group/other

    def run_eqy(self, output_path: Optional[str] = None, overwrite: bool = False, quiet: bool = False) -> int:
        """
        Runs the Yosys EQY tool to prove the logical equivalence of the Verilog designs.

        The script for the equivalence check is the one specified in the `path` attribute of this class.

        If the parameter overwrite is set to True and the output directory exists already, it will be overwritten.
        If the directory exists, and the parameter is False or omitted, the equivalence checking script will fail with a corresponding error message.

        Args:
            output_path (Optional[str], optional): The path to the directory where the EQY tool will be executed.
                If None, executes the equivalence check in a temporary directory. Defaults to None.
            overwrite (bool, optional): Whether to overwrite the output directory if it already exists.
                Only has an effect, if an output_path is provided. Defaults to False.
            quiet (bool, optional): If True, suppresses all Yosys output. If False, prints all Yosys output to the console. Defaults to False.

        Returns:
            int: The return code of the EQY tool. 0 if the equivalence proof was successful, otherwise a non-zero value along with an error message.
        """
        if overwrite and output_path is not None and os.path.exists(output_path):
            shutil.rmtree(output_path, ignore_errors=True)
        # Use the path if the given path is not None, otherwise use a temporary directory
        context = tempfile.TemporaryDirectory() if output_path is None else nullcontext(output_path)
        if output_path is not None:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with context as workdir:
            dir_path = os.path.dirname(os.path.abspath(__file__))
            stdout = subprocess.PIPE if quiet else None
            stderr = subprocess.STDOUT if quiet else None
            return_code = subprocess.call(
                [f'{dir_path}/eqy.sh', str(self.path.resolve()), str(Path(workdir).resolve())], stdout=stdout, stderr=stderr
            )
        return return_code
