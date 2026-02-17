"""Module for handling equivalence checks with Yosys EQY."""

import os
import shutil
import subprocess
import tempfile
from contextlib import nullcontext
from pathlib import Path
from typing import List, Optional


class EquivalenceChecking:
    """
    Wrapper class for executing equivalence checks via Yosys EQY to prove the logical equivalence of two Verilog designs.
    It handles all setup and execution of the equivalence checks and provides methods for running them.
    """

    def __init__(
        self,
        gold_vfile_paths: List[str],
        gold_top_module: Optional[str],
        gate_vfile_paths: List[str],
        gate_top_module: Optional[str],
        script_path: str,
    ):
        """
        Initializes the EQY Wrapper class with the desired file path for the Yosys EQY script.

        Args:
            script_path (str): The path (including the desired file name) to the directory where the .eqy script will be saved.
            gold_vfile_paths (List[str]): A list of paths to the gold Verilog files.
            gold_top_module (Optional[str]): The top module name for the gold design. If None, module is auto-selected.
            gate_vfile_paths (List[str]): A list of paths to the gate Verilog files.
            gate_top_module (Optional[str]): The top module name for the gate design. If None, module is auto-selected.
        """
        self.gold_vfile_paths = gold_vfile_paths
        """A list of paths to the gold Verilog files."""
        self.gold_top_module = gold_top_module
        """The top module name for the gold design. If None, module is auto-selected."""
        self.gate_vfile_paths = gate_vfile_paths
        """A list of paths to the gate Verilog files."""
        self.gate_top_module = gate_top_module
        """The top module name for the gate design. If None, module is auto-selected."""
        self.script_path = Path(script_path)
        """The path to the directory where the .eqy script will be saved."""

    @property
    def formatted_template(self) -> str:
        """
        Formats the EQY template string with the provided input parameters.

        The gold Verilog files are the golden reference design files, while the gate Verilog files are the synthesized (gate-level) designs.
        In the scope of this framework, the gate designs refer to the modified or optimized versions of the original designs.

        Args:
            gold_vfile_paths (List[str]): A list of paths to the gold Verilog files.
            gold_top_module (Optional[str]): The top module name for the gold design. If None, module is auto-selected.
            gate_vfile_paths (List[str]): A list of paths to the gate Verilog files.
            gate_top_module (Optional[str]): The top module name for the gate design. If None, module is auto-selected.

        Returns:
            str: The formatted EQY template string.
        """
        template = """[gold]\n{gold_vsources}\n{gold_top_module}\nmemory_map\n\n[gate]\n{gate_vsources}\n{gate_top_module}\nmemory_map\n\n[strategy sat]\nuse sat\ndepth 10"""
        gold_vfiles = '\n'.join(f'read_verilog {p}' for p in self.gold_vfile_paths)
        gold_top_module = 'prep -top ' + self.gold_top_module + ' -flatten' if self.gold_top_module is not None else 'prep -auto-top -flatten'
        gate_vfiles = '\n'.join(f'read_verilog {p}' for p in self.gate_vfile_paths)
        gate_top_module = 'prep -top ' + self.gate_top_module + ' -flatten' if self.gate_top_module is not None else 'prep -auto-top -flatten'
        return template.format(gold_vsources=gold_vfiles, gold_top_module=gold_top_module, gate_vsources=gate_vfiles, gate_top_module=gate_top_module)

    def _create_eqy_file(self, overwrite: bool = False) -> None:
        """
        Creates the EQY script file at the path `self.path`.

        The gold Verilog files are the golden reference design files, while the gate Verilog files are the synthesized (gate-level) designs.
        In the scope of this framework, the gate designs refer to the modified or optimized versions of the original designs.
        """
        if self.script_path.exists() and not overwrite:
            raise FileExistsError(f'The file {self.script_path} already exists. Set `overwrite` to True if you want to overwrite it.')
        self.script_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.script_path, 'w') as f:
            f.write(self.formatted_template)
        self.script_path.chmod(self.script_path.stat().st_mode | 0o111)  # chmod for user/group/other

    def run_eqy(
        self,
        output_path: Optional[str] = None,
        overwrite: bool = False,
        quiet: bool = False,
    ) -> subprocess.CompletedProcess[bytes]:
        """
        Runs the Yosys EQY tool to prove the logical equivalence of the Verilog designs for the given Verilog designs.

        The gold Verilog files are the golden reference design files, while the gate Verilog files are the synthesized (gate-level) designs.
        In the scope of this framework, the gate designs refer to the modified or optimized versions of the original designs.

        The script for the equivalence check is the one specified in the `path` attribute of this class.

        If the parameter overwrite is set to True and the output directory exists already, it will be overwritten.
        If the directory exists, and the parameter is False or omitted, the equivalence checking script will fail with a corresponding error message.

        Args:
            output_path (Optional[str], optional): The path to the directory where the EQY tool will be executed.
                If None, executes the equivalence check in a temporary directory. Defaults to None.
            overwrite (bool, optional): Whether to overwrite the output directory if it already exists.
                Only has an effect, if an output_path is provided. Defaults to False.
            quiet (bool, optional): If True, pipes all Yosys output into the subprocess.CompletedProcess object.
                If False, prints all Yosys output to the console. Defaults to False.

        Returns:
            subprocess.CompletedProcess: The result of the execution plus some metadata.
        """
        self._create_eqy_file(overwrite)
        # Use the path if the given path is not None, otherwise use a temporary directory
        context = tempfile.TemporaryDirectory() if output_path is None else nullcontext(output_path)
        if output_path is not None:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with context as workdir:
            if overwrite and os.path.exists(workdir):
                shutil.rmtree(workdir, ignore_errors=True)
            dir_path = os.path.dirname(os.path.abspath(__file__))
            stdout = subprocess.PIPE if quiet else None
            stderr = subprocess.PIPE if quiet else None
            process = subprocess.run(
                [f'{dir_path}/eqy.sh', str(self.script_path.resolve()), str(Path(workdir).resolve())], stdout=stdout, stderr=stderr
            )
        return process


def run_eqy(
    gold_vfile_paths: List[str],
    gate_vfile_paths: List[str],
    gold_top_module: Optional[str] = None,
    gate_top_module: Optional[str] = None,
    script_path: Optional[str] = None,
    output_path: Optional[str] = None,
    overwrite: bool = False,
    quiet: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    """
    Runs the Yosys EQY tool to prove the logical equivalence of the Verilog designs for the given Verilog designs.

    The gold Verilog files are the golden reference design files, while the gate Verilog files are the synthesized (gate-level) designs.
    In the scope of this framework, the gate designs refer to the modified or optimized versions of the original designs.

    The script for the equivalence check is the one specified in the `path` attribute of this class.

    If the parameter overwrite is set to True and the output directory exists already, it will be overwritten.
    If the directory exists, and the parameter is False or omitted, the equivalence checking script will fail with a corresponding error message.

    Args:
        gold_vfile_paths (List[str]): A list of paths to the gold Verilog files.
        gate_vfile_paths (List[str]): A list of paths to the gate Verilog files.
        gold_top_module (Optional[str]): The top module name for the gold design. If None, module is auto-selected.
        gate_top_module (Optional[str]): The top module name for the gate design. If None, module is auto-selected.
        script_path (Optional[str]): The path (including the desired file name) to the directory where the .eqy script will be saved.
        output_path (Optional[str], optional): The path to the directory where the EQY tool will be executed.
            If None, executes the equivalence check in a temporary directory. Defaults to None.
        overwrite (bool, optional): Whether to overwrite the output directory if it already exists.
            Only has an effect, if an output_path is provided. Defaults to False.
        quiet (bool, optional): If True, pipes all Yosys output into the subprocess.CompletedProcess object.
            If False, prints all Yosys output to the console. Defaults to False.

    Returns:
        subprocess.CompletedProcess: The result of the execution plus some metadata.
    """
    context = tempfile.TemporaryDirectory() if script_path is None else nullcontext(str(Path(script_path).parent))
    if script_path is not None:
        Path(script_path).parent.mkdir(parents=True, exist_ok=True)
    with context as script_dir:
        script_path = script_dir + '/eqy.eqy' if script_path is None else script_path
        eqy = EquivalenceChecking(gold_vfile_paths, gold_top_module, gate_vfile_paths, gate_top_module, script_path)
        return eqy.run_eqy(output_path, overwrite, quiet)


def run_equiv(
    gold_vfile_path: str,
    gate_vfile_path: str,
    gold_top_module: str,
    gate_top_module: str,
    quiet: bool = False,
) -> subprocess.CompletedProcess[bytes]:
    """
    Runs a predefined script using the equiv_* passes from Yosys to prove the logical equivalence of the Verilog designs for the given Verilog designs.

    The gold Verilog file is the golden reference design, while the gate Verilog file is the synthesized (gate-level) design.
    In the scope of this framework, the gate design refers to the modified or optimized version of the original design.

    Args:
        gold_vfile_path (str): The file path to the gold Verilog file.
        gate_vfile_path (str): The file path to the gate Verilog file.
        gold_top_module (str): The top module name for the gold design.
        gate_top_module (str): The top module name for the gate design.
        quiet (bool, optional): If True, pipes all Yosys output into the subprocess.CompletedProcess object.
            If False, prints all Yosys output to the console. Defaults to False.

    Returns:
        subprocess.CompletedProcess: The result of the execution plus some metadata.
    """
    dir_path = os.path.dirname(os.path.abspath(__file__))
    script_path = f'{dir_path}/equiv.sh'
    stdout = subprocess.PIPE if quiet else None
    stderr = subprocess.PIPE if quiet else None
    return subprocess.run([script_path, gold_vfile_path, gold_top_module, gate_vfile_path, gate_top_module], stdout=stdout, stderr=stderr)
