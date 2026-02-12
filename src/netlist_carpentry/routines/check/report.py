from dataclasses import dataclass
from typing import Dict

from netlist_carpentry.routines.check.comb_loops import COMB_LOOPS
from netlist_carpentry.routines.check.fanout_analysis import FANOUT_BY_NUMBER


@dataclass
class CheckReport:
    comb_loops: Dict[str, COMB_LOOPS]
    fanouts: FANOUT_BY_NUMBER

    @property
    def has_comb_loops(self) -> bool:
        return any(loops for loops in self.comb_loops.values())

    @property
    def any_without_load(self) -> bool:
        return 0 in self.fanouts and len(self.fanouts[0]) > 0

    def __bool__(self) -> bool:
        return self.has_comb_loops or self.any_without_load
