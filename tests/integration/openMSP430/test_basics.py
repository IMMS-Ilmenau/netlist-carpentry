import os
import time
from pathlib import Path
from typing import List

import pytest
from utils import profile

from integration import gen_omsp, omsp_modules
from netlist_carpentry import Circuit, read, run_equiv

top_cnt = [
    ('omsp_alu', 1),
    ('omsp_clock_module', 3),
    ('omsp_dbg', 3),
    ('omsp_dbg_uart', 2),
    ('omsp_execution_unit', 3),
    ('omsp_frontend', 1),
    ('omsp_mem_backbone', 1),
    ('omsp_multiplier', 1),
    ('omsp_register_file', 1),
    ('omsp_sfr', 2),
    ('omsp_sync_cell', 1),
    ('omsp_sync_reset', 1),
    ('omsp_watchdog', 1),
    ('openMSP430', 14),
]


@pytest.fixture()
def omsp_files() -> List[Path]:
    return [Path('openmsp430/core/rtl/verilog') / f for f in os.listdir('openmsp430/core/rtl/verilog') if f.endswith('v')]


def test_read(omsp_files: List[Path]) -> None:
    start = time.time()
    c = read(omsp_files)
    print(f'Runtime: {time.time() - start}s')
    assert len(c.modules) == 14
    assert 'omsp_alu' in c.modules
    assert 'omsp_clock_module' in c.modules
    assert 'omsp_dbg' in c.modules
    assert 'omsp_dbg_uart' in c.modules
    assert 'omsp_execution_unit' in c.modules
    assert 'omsp_frontend' in c.modules
    assert 'omsp_mem_backbone' in c.modules
    assert 'omsp_multiplier' in c.modules
    assert 'omsp_register_file' in c.modules
    assert 'omsp_sfr' in c.modules
    assert 'omsp_sync_cell' in c.modules
    assert 'omsp_sync_reset' in c.modules
    assert 'omsp_watchdog' in c.modules
    assert 'openMSP430' in c.modules
    assert c.top_name == 'openMSP430'


@pytest.mark.parametrize('top,cnt', top_cnt)
def test_read_different_tops(omsp_files: List[Path], top: str, cnt: int) -> None:
    start = time.time()
    c: Circuit = profile(read, f'tests/files/profiles/read/{top}', cfg_or_files=omsp_files, top=top)  # type: ignore
    print(f'Runtime: {time.time() - start}s')
    assert len(c.modules) == cnt
    assert c.top_name == top


@pytest.mark.parametrize('top', omsp_modules)
def test_equivalence(omsp_files: List[Path], top: str) -> None:
    c1path = Path('tests/files/gen/openMSP430_nc.v')
    c2path = Path('tests/files/gen/openMSP430.v')
    c1 = read(omsp_files, top=top)
    profile(c1.write, f'tests/files/profiles/write/{top}', output_file_path=c1path, overwrite=True)
    gen_omsp(top)
    proc = run_equiv(c1path, c2path, top, top, quiet=True)
    assert proc.returncode == 0


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
