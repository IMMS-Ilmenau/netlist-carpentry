"""Module for handling equivalence checks with Yosys EQY."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from contextlib import nullcontext
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Union, overload

from pydantic import PositiveInt

if TYPE_CHECKING:
    from netlist_carpentry import Circuit

Process = subprocess.CompletedProcess[bytes]

EQY_TEMPLATE = """[gold]
{gold_vsources}
{gold_top_module}
memory_map

[gate]
{gate_vsources}
{gate_top_module}
memory_map

[strategy sat]
use sat
depth 10"""


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
        gold = '\n'.join(f'read_verilog {p}' for p in self.gold_vfile_paths)
        gold_top_module = 'prep -top ' + self.gold_top_module + ' -flatten' if self.gold_top_module is not None else 'prep -auto-top -flatten'
        gate = '\n'.join(f'read_verilog {p}' for p in self.gate_vfile_paths)
        gate_top_module = 'prep -top ' + self.gate_top_module + ' -flatten' if self.gate_top_module is not None else 'prep -auto-top -flatten'
        return EQY_TEMPLATE.format(gold_vsources=gold, gold_top_module=gold_top_module, gate_vsources=gate, gate_top_module=gate_top_module)

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
    ) -> Process:
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
        if not self.script_path.exists() or overwrite:
            self._create_eqy_file(overwrite)
        # Use the path if the given path is not None, otherwise use a temporary directory
        context = tempfile.TemporaryDirectory() if output_path is None else nullcontext(output_path)
        if output_path is not None:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with context as workdir:
            eqy_dir = workdir if output_path is not None else workdir + '/eqy'
            if overwrite and os.path.exists(eqy_dir):
                shutil.rmtree(eqy_dir, ignore_errors=True)
            dir_path = os.path.dirname(os.path.abspath(__file__))
            stdout = subprocess.PIPE if quiet else None
            stderr = subprocess.PIPE if quiet else None
            process = subprocess.run(
                [f'{dir_path}/eqy.sh', str(self.script_path.resolve()), str(Path(eqy_dir).resolve())], stdout=stdout, stderr=stderr
            )
        return process


@overload
def run_eqy(
    gold_design: Circuit,
    gate_design: Circuit,
    *,
    script_path: Optional[str] = None,
    output_path: Optional[str] = None,
    overwrite: bool = False,
    quiet: bool = False,
) -> Process: ...


@overload
def run_eqy(
    gold_design: List[str],
    gate_design: List[str],
    gold_top: Optional[str] = None,
    gate_top: Optional[str] = None,
    *,
    script_path: Optional[str] = None,
    output_path: Optional[str] = None,
    overwrite: bool = False,
    quiet: bool = False,
) -> Process: ...


def run_eqy(
    gold_design: Union[Circuit, List[str]],
    gate_design: Union[Circuit, List[str]],
    gold_top: Optional[str] = None,
    gate_top: Optional[str] = None,
    *,
    script_path: Optional[str] = None,
    output_path: Optional[str] = None,
    overwrite: bool = False,
    quiet: bool = False,
) -> Process:
    """
    Runs the Yosys EQY tool to prove the logical equivalence of the Verilog designs for the given Verilog designs.

    The gold Verilog files are the golden reference design files, while the gate Verilog files are the synthesized (gate-level) designs.
    In the scope of this framework, the gate designs refer to the modified or optimized versions of the original designs.

    The script for the equivalence check is the one specified in the `path` attribute of this class.

    If the parameter overwrite is set to True and the output directory exists already, it will be overwritten.
    If the directory exists, and the parameter is False or omitted, the equivalence checking script will fail with a corresponding error message.

    Args:
        gold_design (Union[Circuit, List[str]]): A Circuit object or a list of paths to the gold Verilog files.
        gate_design (Union[Circuit, List[str]]): A Circuit object or a list of paths to the gate Verilog files.
        gold_top (Optional[str]): The top module name for the gold design. If None, module is auto-selected.
        gate_top (Optional[str]): The top module name for the gate design. If None, module is auto-selected.
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
    from netlist_carpentry import Circuit

    with tempfile.TemporaryDirectory() as vtmp_dir:
        if isinstance(gold_design, Circuit):
            gold_path = os.path.join(vtmp_dir, 'gold.v')
            gold_design.write(gold_path)
            gold_top = gold_design.top_name
            gold_design = [gold_path]
        if isinstance(gate_design, Circuit):
            gate_path = os.path.join(vtmp_dir, 'gate.v')
            gate_design.write(gate_path)
            gate_top = gate_design.top_name
            gate_design = [gate_path]
        context = tempfile.TemporaryDirectory() if script_path is None else nullcontext(str(Path(script_path).parent))
        if script_path is not None:
            Path(script_path).parent.mkdir(parents=True, exist_ok=True)
        with context as script_dir:
            script_path = script_dir + '/eqy.eqy' if script_path is None else script_path
            eqy = EquivalenceChecking(gold_design, gold_top, gate_design, gate_top, script_path)
            return eqy.run_eqy(output_path, overwrite, quiet)


EQUIV_TEMPLATE = """#!/bin/bash

yosys -p "
read_verilog {gold} # Load the "Gold" (Reference) design
prep -top {gold_top} -flatten
{rename_wires}
design -stash gold

read_verilog {gate} # Load the "Gate" (Implementation) design
prep -top {gate_top} -flatten
{rename_wires}
design -stash gate

# Create the Equivalence Miter (new module 'equiv') by matching ports of 'gold' and 'gate'
design -copy-from gold -as gold {gold_top}
design -copy-from gate -as gate {gate_top}
equiv_make gold gate equiv
hierarchy -top equiv

flatten
chformal -early # Prepares formal cells for equivalence check
async2sync      # Resolves async FFs into synced FF (since it happens in both designs, equality is preserved)
equiv_simple    # Simple combinational equivalence
equiv_struct    # Structural matching (matches logic cones, e.g. wires with same names)
equiv_induct    # Temporal induction (for sequential logic/FFs)

# Check results
equiv_status -assert"
"""


def _equiv_template(gold: str, gate: str, gold_top: Optional[str], gate_top: Optional[str], *, no_name_matching: bool = False) -> str:
    no_matching = 'rename -hide w:* i:* %d     # Rename and hide all wires that are NOT ports to prevent false matching (gold.w1 may be structurally different from gate.w1, but logically equivalent)'
    rename_wires = no_matching if no_name_matching else ''
    return EQUIV_TEMPLATE.format(gold=gold, gate=gate, gold_top=gold_top, gate_top=gate_top, rename_wires=rename_wires)


@overload
def run_equiv(
    gold_design: Circuit, gate_design: Circuit, *, quiet: bool = False, out_dir: Optional[str] = None, no_name_matching: bool = False
) -> Process: ...


@overload
def run_equiv(
    gold_design: str,
    gate_design: str,
    gold_top: str,
    gate_top: str,
    *,
    quiet: bool = False,
    out_dir: Optional[str] = None,
    no_name_matching: bool = False,
) -> Process: ...


def run_equiv(
    gold_design: Union[Circuit, str],
    gate_design: Union[Circuit, str],
    gold_top: str = '',
    gate_top: str = '',
    *,
    quiet: bool = False,
    out_dir: Optional[str] = None,
    no_name_matching: bool = False,
) -> Process:
    """
    Runs a predefined script using the equiv_* passes from Yosys to prove the logical equivalence of the Verilog designs for the given Verilog designs.

    The gold design is the golden reference design, while the gate design is the synthesized (gate-level) design.
    In the scope of this framework, the gate design refers to the modified or optimized version of the original design.

    Args:
        gold_design (Union[Circuit, str]): The circuit object, or the file path to the gold design.
        gate_design (Union[Circuit, str]): The circuit object, or the file path to the gate design.
        gold_top (str): The top module name for the gold design.
        gate_top (str): The top module name for the gate design.
        quiet (bool, optional): If True, pipes all Yosys output into the subprocess.CompletedProcess object.
            If False, prints all Yosys output to the console. Defaults to False.
        out_dir (Optional[str], optional): The directory path, where the script (and other temporary files) will be stored.
            Defaults to None, in which case a temporary directory is created.
        no_name_matching (bool, optional): Whether to suppress the assumption that wires with the same name are identical.
            For example, gold.w1 may be structurally different from gate.w1, but logically equivalent. If `no_name_matching` is
            set to `True`, the equivalence check will still see the equivalence, but if it is `False` it will fail, since gold.w1
            and gate.w1 do not follow the same structure. Defaults to False.

    Returns:
        subprocess.CompletedProcess: The result of the execution plus some metadata.
    """
    from netlist_carpentry import Circuit

    context = tempfile.TemporaryDirectory() if out_dir is None else nullcontext(str(Path(out_dir).resolve()))
    with context as tmp_dir:
        if isinstance(gold_design, Circuit):
            gold_path = os.path.join(tmp_dir, 'gold.v')
            gold_design.write(gold_path)
            gold_top = gold_design.top_name
            gold_design = gold_path
        if isinstance(gate_design, Circuit):
            gate_path = os.path.join(tmp_dir, 'gate.v')
            gate_design.write(gate_path)
            gate_top = gate_design.top_name
            gate_design = gate_path
        script_path = Path(f'{tmp_dir}/equiv.sh')
        with open(script_path, 'w') as f:
            f.write(_equiv_template(gold_design, gate_design, gold_top, gate_top, no_name_matching=no_name_matching))
        stdout = subprocess.PIPE if quiet else None
        stderr = subprocess.PIPE if quiet else None
        script_path.chmod(script_path.stat().st_mode | 0o111)
        return subprocess.run([script_path], stdout=stdout, stderr=stderr)


EQUIV_MITER_TEMPLATE = """#!/bin/bash

yosys -p "
read_verilog {gold} # Load the "Gold" (Reference) design
prep -top {gold_top}
techmap; flatten; abc -fast; clk2fflogic; opt_clean
rename {gold_top} gold
design -stash gold

read_verilog {gate} # Load the "Gate" (Implementation) design
prep -top {gate_top}
techmap; flatten; abc -fast; clk2fflogic; opt_clean
rename {gate_top} gate
design -stash gate

# Create the equivalence checking miter
design -copy-from gold -as gold gold
design -copy-from gate -as gate gate
miter -equiv -flatten gold gate miter
hierarchy -top miter
flatten
techmap
opt -full

# Prove equivalence using SAT
sat -verify {sat_strat} -set-init-zero -prove trigger 0 -show-inputs -show-outputs -show-public -show-regs"
"""


def _equiv_miter_template(gold: str, gate: str, gold_top: Optional[str], gate_top: Optional[str], *, cycles: Optional[PositiveInt] = None) -> str:
    sat_strat = f'-seq {cycles}' if cycles is not None else '-tempinduct'
    return EQUIV_MITER_TEMPLATE.format(gold=gold, gate=gate, gold_top=gold_top, gate_top=gate_top, sat_strat=sat_strat)


def run_equiv_miter(
    gold_design: Union[Circuit, str],
    gate_design: Union[Circuit, str],
    gold_top: str = '',
    gate_top: str = '',
    *,
    quiet: bool = False,
    out_dir: Optional[str] = None,
    cycles: Optional[PositiveInt] = None,
) -> Process:
    """
    Runs a predefined script to prove the logical equivalence for the given Verilog designs using a miter/SAT approach in Yosys.

    The equivalence check is either executed for a given number of cycles for which the design must be equivalent (Bounded Model Check)
    or via temporal induction to prove that if the designs are equal after `K` cycles, they will be equal in cycle `K+1`.

    The gold design is the golden reference design, while the gate design is the synthesized (gate-level) design.
    In the scope of this framework, the gate design refers to the modified or optimized version of the original design.

    Args:
        gold_design (Union[Circuit, str]): The circuit object, or the file path to the gold design.
        gate_design (Union[Circuit, str]): The circuit object, or the file path to the gate design.
        gold_top (str): The top module name for the gold design.
        gate_top (str): The top module name for the gate design.
        quiet (bool, optional): If True, pipes all Yosys output into the subprocess.CompletedProcess object.
            If False, prints all Yosys output to the console. Defaults to False.
        out_dir (Optional[str], optional): The directory path, where the script (and other temporary files) will be stored.
            Defaults to None, in which case a temporary directory is created.
        cycles (Optional[PositiveInt], optional): The number of clock cycles for which the Bounded Model Checking should be executed.
            This approach checks if the designs behave equally for the given number of clock cycles. This however means, that if Yosys
            proves the equivalence for 5 cycles, it may diverge on the 6th cycle.
            However, larger numbers (e.g. more than 10 cycles) may lead to the algorithm running infinitely.
            If `cycles` is None (default case), an induction prove is executed that checks if they match at an arbitrary cycle `K`,
            they must match at cycle `K+1` as well. This however may be hard for large circuits and run seemingly infinitely.
            Defaults to None, in which case a temporal induction is executed.

    Returns:
        subprocess.CompletedProcess: The result of the execution plus some metadata.
    """
    from netlist_carpentry import Circuit

    context = tempfile.TemporaryDirectory() if out_dir is None else nullcontext(str(Path(out_dir).resolve()))
    with context as tmp_dir:
        if isinstance(gold_design, Circuit):
            gold_path = os.path.join(tmp_dir, 'gold.v')
            gold_design.write(gold_path)
            gold_top = gold_design.top_name
            gold_design = gold_path
        if isinstance(gate_design, Circuit):
            gate_path = os.path.join(tmp_dir, 'gate.v')
            gate_design.write(gate_path)
            gate_top = gate_design.top_name
            gate_design = gate_path
        script_path = Path(f'{tmp_dir}/equiv_miter.sh')
        with open(script_path, 'w') as f:
            f.write(_equiv_miter_template(gold_design, gate_design, gold_top, gate_top, cycles=cycles))
        stdout = subprocess.PIPE if quiet else None
        stderr = subprocess.PIPE if quiet else None
        script_path.chmod(script_path.stat().st_mode | 0o111)
        return subprocess.run([script_path], stdout=stdout, stderr=stderr)
