import os

import pytest

from netlist_carpentry.routines.check import CheckReport


@pytest.fixture()
def basic_check_report_good() -> CheckReport:
    return CheckReport(comb_loops={'m1': []}, fanouts={1: ['a.b.c']})


@pytest.fixture()
def basic_check_report_bad() -> CheckReport:
    return CheckReport(comb_loops={'m2': ['a.b.c', 'd.e.f']}, fanouts={0: ['d.e.f']})


def test_basics(basic_check_report_good: CheckReport, basic_check_report_bad: CheckReport) -> None:
    assert not basic_check_report_good
    assert not basic_check_report_good.any_without_load
    assert not basic_check_report_good.has_comb_loops
    assert 'm1' in basic_check_report_good.comb_loops
    assert 'm2' not in basic_check_report_good.comb_loops
    assert 0 not in basic_check_report_good.fanouts
    assert 1 in basic_check_report_good.fanouts

    assert basic_check_report_bad
    assert basic_check_report_bad.any_without_load
    assert basic_check_report_bad.has_comb_loops
    assert 'm1' not in basic_check_report_bad.comb_loops
    assert 'm2' in basic_check_report_bad.comb_loops
    assert 0 in basic_check_report_bad.fanouts
    assert 1 not in basic_check_report_bad.fanouts


def test_update_good2bad(basic_check_report_good: CheckReport, basic_check_report_bad: CheckReport) -> None:
    basic_check_report_good.update(basic_check_report_bad)

    assert basic_check_report_good
    assert basic_check_report_good.any_without_load
    assert basic_check_report_good.has_comb_loops
    assert 'm1' in basic_check_report_good.comb_loops
    assert 'm2' in basic_check_report_good.comb_loops
    assert 0 in basic_check_report_good.fanouts
    assert 1 in basic_check_report_good.fanouts


def test_update_bad2good(basic_check_report_good: CheckReport, basic_check_report_bad: CheckReport) -> None:
    basic_check_report_bad.update(basic_check_report_good)

    assert basic_check_report_bad
    assert basic_check_report_bad.any_without_load
    assert basic_check_report_bad.has_comb_loops
    assert 'm1' in basic_check_report_bad.comb_loops
    assert 'm2' in basic_check_report_bad.comb_loops
    assert 0 in basic_check_report_bad.fanouts
    assert 1 in basic_check_report_bad.fanouts


if __name__ == '__main__':
    file_name = os.path.basename(__file__)
    pytest.main(args=['-k', file_name])
