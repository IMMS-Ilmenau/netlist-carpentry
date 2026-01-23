import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List, Union

import pytest

import netlist_carpentry
from netlist_carpentry import Circuit
from netlist_carpentry.routines.dft.scan_chain_insertion import implement_scan_chain


def _run_sim(tempdir: Path, vfiles: List[str]) -> None:
    """Run simulation with verilog."""
    # Execute icarus verilog
    command = ['iverilog', *vfiles, '../tb.sv']
    result = subprocess.run(command, cwd=tempdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    if result.returncode != 0:
        raise Exception(f'Icarus Verilog Compiler Error: \n {result.stdout} \n {result.stderr}')

    # run simulation
    result = subprocess.run(['vvp', 'a.out'], cwd=tempdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    if result.returncode != 0:
        raise Exception(f'Icarus Verilog Runner Error: \n {result.stdout} \n {result.stderr}')


def _setup_run_circuit(sim_dir: str, circuit: Circuit) -> None:
    with TemporaryDirectory(dir=f'tests/files/sim/{sim_dir}') as tempdir_str:
        tempdir = Path(tempdir_str)
        circuit.write(tempdir / 'dut.sv')
        _run_sim(tempdir, ['dut.sv'])


def _setup_run_vfile(sim_dir: str, vfiles: Union[Path, List[Path]]) -> None:
    with TemporaryDirectory(dir=f'tests/files/sim/{sim_dir}') as tempdir_str:
        tempdir = Path(tempdir_str)
        if isinstance(vfiles, Path):
            vfiles = [vfiles]
        vfile_names = []
        for vfile in vfiles:
            shutil.copy(vfile, tempdir / vfile.name)
            vfile_names.append(vfile.name)
        _run_sim(tempdir, vfile_names)


def test_verilog_init_simple_adder() -> None:
    c = netlist_carpentry.read('tests/files/simpleAdder.v')
    _setup_run_circuit('adder_basics', c)


def test_verilog_init_dec() -> None:
    _setup_run_vfile('dec', Path('tests/files/dec.v'))


def test_verilog_init_adderWrapper() -> None:
    _setup_run_vfile('adderWrapper', [Path('tests/files/adderWrapper.v'), Path('tests/files/simpleAdder.v')])


def test_verilog_init_ctr_async() -> None:
    c = netlist_carpentry.read('tests/files/ctr_async.v')
    _setup_run_circuit('ctr_async', c)


def test_verilog_init_decentral_mux() -> None:
    c = netlist_carpentry.read('tests/files/decentral_mux.v')
    _setup_run_circuit('decentral_mux', c)


def test_verilog_init_edge_detector() -> None:
    c = netlist_carpentry.read('tests/files/edge_detector.v')
    _setup_run_circuit('edge_detector', c)


def test_verilog_init_hierarchicalAdder() -> None:
    c = netlist_carpentry.read(['tests/files/hierarchicalAdder.v', 'tests/files/simpleAdder.v'])
    _setup_run_circuit('hierarchicalAdder', c)


def test_verilog_init_signed_example() -> None:
    c = netlist_carpentry.read('tests/files/signed_example.v')
    _setup_run_circuit('signed_example', c)


def test_verilog_init_thermo_enc() -> None:
    c = netlist_carpentry.read('tests/files/thermo_enc.v')
    _setup_run_circuit('thermo_enc', c)


def test_scan_chains() -> None:
    c = netlist_carpentry.read('tests/files/dff_circuit.v', top='Top')
    implement_scan_chain(c.top)
    _setup_run_circuit('scan_chains', c)


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
