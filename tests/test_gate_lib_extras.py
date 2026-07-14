import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List, Union

import pytest

from netlist_carpentry import LOG, Circuit, Direction, Module, ReadConfig, Signal, read, run_equiv, run_eqy
from netlist_carpentry.core.exceptions import UnsupportedOperationError, VerilogSyntaxError
from netlist_carpentry.core.types import SignalArray
from netlist_carpentry.utils.gate_lib_dataclasses import BRAMParams
from netlist_carpentry.utils.gate_lib_extras import BRAM


class SimulationException(Exception):
    pass


def _print_results(result: subprocess.CompletedProcess[str], quiet: bool) -> None:
    if not quiet:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)


def _run_sim(tempdir: Path, vfiles: List[str], quiet: bool) -> subprocess.CompletedProcess[str]:
    """Run simulation with verilog."""
    # Execute icarus verilog
    command = ['iverilog', *vfiles, '../tb.sv']
    result = subprocess.run(command, cwd=tempdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    _print_results(result, quiet)

    if result.returncode != 0:
        raise VerilogSyntaxError(f'Icarus Verilog Compiler Error: \n {result.stdout} \n {result.stderr}')

    # run simulation
    result = subprocess.run(['vvp', 'a.out'], cwd=tempdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    _print_results(result, quiet)

    if result.returncode != 0:
        raise SimulationException(f'Icarus Verilog Runner Error: \n {result.stdout} \n {result.stderr}')
    return result


def _setup_run_circuit(sim_dir: str, circuit: Circuit, quiet: bool = True) -> subprocess.CompletedProcess[str]:
    with TemporaryDirectory(dir=f'tests/files/sim/{sim_dir}') as tempdir_str:
        tempdir = Path(tempdir_str)
        circuit.write(tempdir / 'dut.sv')
        return _run_sim(tempdir, ['dut.sv'], quiet)


def _setup_run_vfile(sim_dir: str, vfiles: Union[Path, List[Path]], quiet: bool = True) -> subprocess.CompletedProcess[str]:
    with TemporaryDirectory(dir=f'tests/files/sim/{sim_dir}') as tempdir_str:
        tempdir = Path(tempdir_str)
        if isinstance(vfiles, Path):
            vfiles = [vfiles]
        vfile_names = []
        for vfile in vfiles:
            shutil.copy(vfile, tempdir / vfile.name)
            vfile_names.append(vfile.name)
        return _run_sim(tempdir, vfile_names, quiet)


@pytest.fixture
def module() -> Module:
    c = Circuit(name='c')
    m = c.create_module('m')
    m.create_port('CLK', Direction.IN, create_associated_wire=True)
    m.create_port('EN', Direction.IN, create_associated_wire=True)
    m.create_port('D', Direction.IN, width=8, create_associated_wire=True)
    m.create_port('ADDR', Direction.IN, width=4, create_associated_wire=True)
    m.create_port('Q', Direction.OUT, width=8)
    return m


@pytest.fixture
def module_bram() -> Module:
    c = Circuit(name='c')
    m = c.create_module('m')
    m.create_port('RD_ADDR', Direction.IN, 8, create_associated_wire=True)
    m.create_port('RD_ARST', Direction.IN, create_associated_wire=True)
    m.create_port('RD_CLK', Direction.IN, create_associated_wire=True)
    m.create_port('RD_DATA', Direction.OUT, 16)
    m.create_port('RD_EN', Direction.IN, create_associated_wire=True)
    m.create_port('RD_SRST', Direction.IN, create_associated_wire=True)
    m.create_port('WR_ADDR', Direction.IN, 8, create_associated_wire=True)
    m.create_port('WR_CLK', Direction.IN, create_associated_wire=True)
    m.create_port('WR_DATA', Direction.IN, 16, create_associated_wire=True)
    m.create_port('WR_EN', Direction.IN, create_associated_wire=True)
    return m


@pytest.fixture
def read_config() -> ReadConfig:
    return ReadConfig(files=[Path('tests/files/mem_complex_small.v')], output=Path('tests/files/gen/mem_complex_small.json'), keep_memory_cells=True)


@pytest.mark.skip
def test_read_bram() -> None:
    c = read('tests/files/test_mem.v', process_memory=False)
    assert 'ram' in c.first.instances
    assert c.first.instances['ram'].instance_type == '§mem_v2'
    assert '§mem_v2' in c.first.instances_by_types

    assert isinstance(c.first.instances['ram'], BRAM)

    c.optimize()
    c.write('tests/files/gen/bram_out.v', overwrite=True)

    p = run_eqy(['tests/files/test_mem.v'], ['tests/files/gen/bram_out.v'], 'test_mem', 'test_mem')
    assert p.returncode == 0


def test_bram_basics(module: Module) -> None:
    bram = BRAM(name='bram', parameters=BRAMParams(WIDTH=8, ABITS=4), module=module)

    assert bram.is_primitive
    assert not bram.is_blackbox
    assert not bram.is_module_instance
    assert not bram.is_combinational
    assert bram.is_sequential
    assert bram.width == 8
    assert bram.abits == 4
    assert len(bram.ports) == 10
    port_names = {'RD_ADDR', 'RD_ARST', 'RD_CLK', 'RD_DATA', 'RD_EN', 'RD_SRST', 'WR_ADDR', 'WR_CLK', 'WR_DATA', 'WR_EN'}
    assert set(bram.ports.keys()) == port_names
    assert bram.ports['RD_CLK'].direction is Direction.IN
    assert bram.ports['RD_CLK'].width == 1
    assert bram.ports['WR_EN'].direction is Direction.IN
    assert bram.ports['WR_EN'].width == 1
    assert bram.ports['WR_DATA'].direction is Direction.IN
    assert bram.ports['WR_DATA'].width == 8
    assert bram.ports['WR_ADDR'].direction is Direction.IN
    assert bram.ports['WR_ADDR'].width == 4
    assert bram.ports['RD_DATA'].direction is Direction.OUT
    assert bram.ports['RD_DATA'].width == 8

    with pytest.raises(UnsupportedOperationError):
        bram.clk_port
    assert bram.rd_clk_port == bram.ports['RD_CLK']
    assert bram.wr_clk_port == bram.ports['WR_CLK']
    assert bram.rd_addr_port == bram.ports['RD_ADDR']
    assert bram.wr_addr_port == bram.ports['WR_ADDR']
    assert bram.rd_data_port == bram.ports['RD_DATA']
    assert bram.wr_data_port == bram.ports['WR_DATA']
    assert bram.rd_en_port == bram.ports['RD_EN']
    assert bram.wr_en_port == bram.ports['WR_EN']

    assert bram.verilog_template == 'reg [{WORD}:0] {MEM} [{OFFSET}:{DEPTH}];\n{INIT}{RD_WR}\n'

    module.connect(module.ports['CLK'], bram.ports['WR_CLK'], 'CLK')
    module.connect(module.ports['CLK'], bram.ports['RD_CLK'], 'CLK')
    module.connect(module.ports['EN'], bram.ports['WR_EN'], 'EN')
    module.connect(module.ports['D'], bram.ports['WR_DATA'], 'D')
    module.connect(module.ports['ADDR'], bram.ports['WR_ADDR'], 'ADDR')
    module.connect(module.ports['ADDR'], bram.ports['RD_ADDR'], 'ADDR')
    module.connect(bram.ports['RD_DATA'], module.ports['Q'], 'Q')
    bram.ports['RD_EN'].tie_signal(1)
    assert bram.verilog_net_map == {
        'RD_ADDR': 'ADDR',
        'RD_ARST': "1'bx",
        'RD_CLK': 'CLK',
        'RD_DATA': 'Q',
        'RD_EN': "1'b1",
        'RD_SRST': "1'bx",
        'WR_ADDR': 'ADDR',
        'WR_CLK': 'CLK',
        'WR_DATA': 'D',
        'WR_EN': 'EN',
    }
    assert (
        bram.verilog
        == 'reg [7:0] bram [0:15];\nalways @(posedge CLK) begin\n\tif (EN)\n\t\tbram[ADDR] <= D;\nend\nalways @(posedge CLK) begin\n\tQ <= bram[ADDR];\nend\n'
    )


def test_bram_different_ports(module_bram: Module) -> None:
    bram = BRAM(name='bram', parameters=BRAMParams(WIDTH=16, ABITS=8), module=module_bram)

    module_bram.connect(module_bram.ports['RD_ADDR'], bram.ports['RD_ADDR'], 'RD_ADDR')
    module_bram.connect(module_bram.ports['RD_ARST'], bram.ports['RD_ARST'], 'RD_ARST')
    module_bram.connect(module_bram.ports['RD_CLK'], bram.ports['RD_CLK'], 'RD_CLK')
    module_bram.connect(module_bram.ports['RD_EN'], bram.ports['RD_EN'], 'RD_EN')
    module_bram.connect(module_bram.ports['RD_SRST'], bram.ports['RD_SRST'], 'RD_SRST')
    module_bram.connect(module_bram.ports['WR_ADDR'], bram.ports['WR_ADDR'], 'WR_ADDR')
    module_bram.connect(module_bram.ports['WR_CLK'], bram.ports['WR_CLK'], 'WR_CLK')
    module_bram.connect(module_bram.ports['WR_DATA'], bram.ports['WR_DATA'], 'WR_DATA')
    module_bram.connect(module_bram.ports['WR_EN'], bram.ports['WR_EN'], 'WR_EN')
    module_bram.connect(bram.ports['RD_DATA'], module_bram.ports['RD_DATA'], 'RD_DATA')

    assert bram.verilog_net_map == {
        'RD_ADDR': 'RD_ADDR',
        'RD_ARST': 'RD_ARST',
        'RD_CLK': 'RD_CLK',
        'RD_DATA': 'RD_DATA',
        'RD_EN': 'RD_EN',
        'RD_SRST': 'RD_SRST',
        'WR_ADDR': 'WR_ADDR',
        'WR_CLK': 'WR_CLK',
        'WR_DATA': 'WR_DATA',
        'WR_EN': 'WR_EN',
    }
    assert (
        bram.verilog
        == 'reg [15:0] bram [0:255];\nalways @(posedge WR_CLK) begin\n\tif (WR_EN)\n\t\tbram[WR_ADDR] <= WR_DATA;\nend\nalways @(posedge RD_CLK) begin\n\tRD_DATA <= bram[RD_ADDR];\nend\n'
    )


def test_format_vpart(module_bram: Module) -> None:
    bram = BRAM(name='bram', parameters=BRAMParams(WIDTH=16, ABITS=8), module=module_bram)
    module_bram.connect(module_bram.ports['RD_ADDR'], bram.ports['RD_ADDR'], 'RD_ADDR')
    module_bram.connect(bram.ports['RD_DATA'], module_bram.ports['RD_DATA'], 'RD_DATA')
    with pytest.raises(ValueError):
        bram._format_vpart(0, 'rw', 'some_clk', Signal.HIGH, bram.rd_en_port[0], bram.rd_addr_port, bram.rd_data_port)

    bram.rd_en_port.tie_signal(1)
    temp = bram._format_vpart(0, 'r', 'some_clk', Signal.HIGH, bram.rd_en_port[0], bram.rd_addr_port, bram.rd_data_port)
    assert temp == 'always @(posedge some_clk) begin\n\tRD_DATA <= bram[RD_ADDR];\nend'

    bram.rd_en_port.tie_signal(0)
    temp = bram._format_vpart(0, 'r', 'some_clk', Signal.HIGH, bram.rd_en_port[0], bram.rd_addr_port, bram.rd_data_port)
    assert temp == ''

    bram.rd_en_port.tie_signal(Signal.FLOATING)
    with pytest.raises(VerilogSyntaxError):
        bram._format_vpart(0, 'r', 'some_clk', Signal.HIGH, bram.rd_en_port[0], bram.rd_addr_port, bram.rd_data_port)


def test_mem_complex() -> None:  # STRUCTURAL COMPARISON
    c = read('tests/files/mem_complex.v', 'mem_complex')
    ram = c.first.instances['ram']
    assert isinstance(ram, BRAM)
    assert ram.parameters.ABITS == 7
    assert (
        ram.parameters.INIT
        == 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
    )
    assert ram.parameters.MEMID == '\\ram'
    assert ram.parameters.OFFSET == 10
    assert ram.parameters.RD_ARST_VALUE == 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
    assert ram.parameters.RD_CE_OVER_SRST.signals == {idx: Signal.LOW if idx != 2 else Signal.HIGH for idx in range(5)}
    assert ram.parameters.RD_CLK_ENABLE.signals == {4: Signal.HIGH, 3: Signal.HIGH, 2: Signal.HIGH, 1: Signal.LOW, 0: Signal.HIGH}
    assert ram.parameters.RD_CLK_POLARITY.signals == {4: Signal.HIGH, 3: Signal.HIGH, 2: Signal.HIGH, 1: Signal.LOW, 0: Signal.LOW}
    assert ram.parameters.RD_COLLISION_X_MASK.signals == {idx: Signal.LOW for idx in range(10)}
    assert ram.parameters.RD_INIT_VALUE == SignalArray.from_bin('000000000000000000000000000000001100101011111110xxxxxxxxxxxxxxxx0000000000000000')
    assert ram.parameters.RD_PORTS == 5
    assert ram.parameters.RD_SRST_VALUE == 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx1101111010101101xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
    assert ram.parameters.RD_TRANSPARENCY_MASK.signals == {idx: Signal.LOW if idx != 0 else Signal.HIGH for idx in range(10)}
    assert ram.parameters.RD_WIDE_CONTINUATION.signals == {4: Signal.HIGH, 3: Signal.LOW, 2: Signal.LOW, 1: Signal.LOW, 0: Signal.LOW}
    assert ram.parameters.SIZE == 64
    assert ram.parameters.WIDTH == 16
    assert ram.parameters.WR_CLK_ENABLE.signals == {1: Signal.HIGH, 0: Signal.HIGH}
    assert ram.parameters.WR_CLK_POLARITY.signals == {1: Signal.HIGH, 0: Signal.LOW}
    assert ram.parameters.WR_PORTS == 2
    assert ram.parameters.WR_PRIORITY_MASK.signals == {idx: Signal.LOW for idx in range(4)}
    assert ram.parameters.WR_WIDE_CONTINUATION.signals == {1: Signal.LOW, 0: Signal.LOW}

    c.write('tests/files/gen/mem_complex_out.v', overwrite=True)

    p = run_eqy(['tests/files/mem_complex.v'], ['tests/files/gen/mem_complex_out.v'], 'mem_complex', 'mem_complex', overwrite=True)
    assert p.returncode == 0


@pytest.mark.skip
def test_mem_complex_small(read_config: ReadConfig) -> None:  # LOGICAL COMPARISON
    LOG.set_log_level(5)
    c = read(read_config)
    ram = c.first.instances['ram']
    assert isinstance(ram, BRAM)

    c.optimize()
    c.write('tests/files/gen/mem_complex_out_small.v', overwrite=True)

    p = run_equiv(
        ['tests/files/mem_complex_small.v'],
        ['tests/files/mem_complex_small_yosys.v'],
        'mem_complex_small',
        'mem_complex_small',
    )
    assert p.returncode == 0


def test_mem_complex_small_sim(read_config: ReadConfig) -> None:  # "PROOF" BY TESTBENCH
    c = read(read_config)
    c.optimize()
    c.write('tests/files/gen/mem_complex_out_small.v', overwrite=True)
    ram = c.first.instances['ram']
    ram.verilog
    proc = _setup_run_vfile('mem_complex_small', Path('tests/files/mem_complex_small.v'))
    assert proc.returncode == 0
    assert proc.stdout != ''
    assert proc.stderr == ''
    proc = _setup_run_vfile('mem_complex_small', Path('tests/files/mem_complex_small_yosys.v'))
    assert proc.returncode == 0
    assert proc.stdout != ''
    assert proc.stderr == ''
    _setup_run_vfile('mem_complex_small', Path('tests/files/gen/mem_complex_out_small.v'), quiet=False)
    assert proc.returncode == 0
    assert proc.stdout != ''
    assert proc.stderr == ''


def test_verilog_template(read_config: ReadConfig) -> None:
    c = read(read_config)
    ram: BRAM = c.first.instances['ram']
    found_w0 = ram._verilog_template(0, 'w')
    target_w0 = """always @(posedge clk) begin
    if ({we_w0_s[0], we_w0_s[0]})
        ram[addr_w0][1:0] <= __0__memwr____ram__tests__files__mem_complex_small__v__50__1_DATA__3__0____10[1:0];
    if ({we_w0_s[1], we_w0_s[1]})
        ram[addr_w0][3:2] <= __0__memwr____ram__tests__files__mem_complex_small__v__51__2_DATA__3__0____13[3:2];
end"""
    # TODO: assert found_w0 == target_w0

    found_w1 = ram._verilog_template(1, 'w')
    target_w1 = """always @(posedge clk) begin
    if (we_w1)
        ram[__0__memwr____ram__tests__files__mem_complex_small__v__58__3_ADDR__4__0____22] <= __0__memwr____ram__tests__files__mem_complex_small__v__58__3_DATA__3__0____23;
end"""
    # TODO: assert found_w1 == target_w1

    found_w0, found_w1, target_w0, target_w1


def test_data_slice(read_config: ReadConfig) -> None:
    c = read(read_config)
    ram: BRAM = c.first.instances['ram']
    with pytest.raises(ValueError):
        ram.data_slice(0, 'a')
    w0 = ram.data_slice(0, 'w')
    assert w0 == {i: ram.wr_data_port[i] for i in range(0, 4)}
    w1 = ram.data_slice(1, 'w')
    assert w1 == {i: ram.wr_data_port[i] for i in range(4, 8)}
    with pytest.raises(IndexError):
        ram.data_slice(2, 'w')
    r0 = ram.data_slice(0, 'r')
    assert r0 == {i: ram.rd_data_port[i] for i in range(0, 4)}
    r4 = ram.data_slice(4, 'r')
    assert r4 == {i: ram.rd_data_port[i] for i in range(16, 20)}
    with pytest.raises(IndexError):
        ram.data_slice(5, 'r')


def test_addr_slice(read_config: ReadConfig) -> None:
    c = read(read_config)
    ram: BRAM = c.first.instances['ram']
    with pytest.raises(ValueError):
        ram.addr_slice(0, 'a')
    w0 = ram.addr_slice(0, 'w')
    assert w0 == {i: ram.wr_addr_port[i] for i in range(0, 5)}
    w1 = ram.addr_slice(1, 'w')
    assert w1 == {i: ram.wr_addr_port[i] for i in range(5, 10)}
    with pytest.raises(IndexError):
        ram.addr_slice(2, 'w')
    r0 = ram.addr_slice(0, 'r')
    assert r0 == {i: ram.rd_addr_port[i] for i in range(0, 5)}
    r4 = ram.addr_slice(4, 'r')
    assert r4 == {i: ram.rd_addr_port[i] for i in range(20, 25)}
    with pytest.raises(IndexError):
        ram.addr_slice(5, 'r')


def test_en_array(read_config: ReadConfig) -> None:
    c = read(read_config)
    ram: BRAM = c.first.instances['ram']
    with pytest.raises(ValueError):
        ram.en_array(0, 'a')
    w0 = ram.en_array(0, 'w')
    assert w0 == {i: ram.wr_en_port[i] for i in range(0, 4)}
    w1 = ram.en_array(1, 'w')
    assert w1 == {i: ram.wr_en_port[i] for i in range(4, 8)}
    with pytest.raises(IndexError):
        ram.en_array(2, 'w')
    r0 = ram.en_array(0, 'r')
    assert r0 == {0: Signal.HIGH}
    r1 = ram.en_array(1, 'r')
    assert r1 == {1: Signal.HIGH}
    r2 = ram.en_array(2, 'r')
    assert r2 == {2: ram.rd_en_port[2]}
    r3 = ram.en_array(3, 'r')
    assert r3 == {3: Signal.HIGH}
    r4 = ram.en_array(4, 'r')
    assert r4 == {4: Signal.HIGH}
    with pytest.raises(IndexError):
        ram.en_array(5, 'r')


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
