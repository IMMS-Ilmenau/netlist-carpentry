from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Literal, Optional, Tuple, Union

from pydantic import NonNegativeInt
from pywellen import Var, Waveform

from netlist_carpentry.io.vcd.types import SCOPE_TYPES, VAR_TYPES

if TYPE_CHECKING:
    from pywellen import Scope


@dataclass(frozen=True)
class VCDVar:
    var: Var
    wf: Waveform

    @property
    def name(self) -> str:
        """Return the variable's name."""
        return self.var.name(self.wf.hierarchy)

    @property
    def full_name(self) -> str:
        """Return the variable's full name."""
        return self.var.full_name(self.wf.hierarchy)

    @property
    def bitwidth(self) -> Optional[int]:
        """Return the variable's bitwidth."""
        return self.var.bitwidth()

    @property
    def var_type(self) -> VAR_TYPES:
        """Return the variable's type."""
        return self.var.var_type()

    @property
    def enum_type(self) -> Optional[Tuple[str, List[Tuple[str, str]]]]:
        """Return the variable's enum type."""
        return self.var.enum_type(self.wf.hierarchy)

    @property
    def direction(self) -> Literal['Unknown', 'Implicit', 'Input', 'Output', 'InOut', 'Buffer', 'Linkage']:
        """Return the variable's direction."""
        return self.var.direction()

    @property
    def length(self) -> Optional[int]:
        """Return the variable's length."""
        return self.var.length()

    @property
    def is_real(self) -> bool:
        """Return True if the variable is real."""
        return self.var.is_real()

    @property
    def is_string(self) -> bool:
        """Return True if the variable is a string."""
        return self.var.is_string()

    @property
    def is_bit_vector(self) -> bool:
        """Return True if the variable is a bit vector."""
        return self.var.is_bit_vector()

    @property
    def is_1bit(self) -> bool:
        """Return True if the variable is 1-bit."""
        return self.var.is_1bit()

    @property
    def all_changes(self) -> List[Tuple[NonNegativeInt, Union[NonNegativeInt, str]]]:
        """Return a list of all signal changes."""
        return [sig for sig in self.wf.get_signal(self.var).all_changes()]

    @property
    def change_times(self) -> List[NonNegativeInt]:
        """Return a list of times when the variable changed."""
        return [t for t, _ in self.all_changes]

    def value_at_time(self, time: NonNegativeInt) -> Union[NonNegativeInt, str]:
        """
        Return the signal's value at a given timestamp.

        Args:
            time (NonNegativeInt): The timestamp to retrieve the value for.

        Returns:
            Union[int, str]: The signal's value at the specified timestamp.
        """
        return self.wf.get_signal(self.var).value_at_time(time)

    def value_at_idx(self, idx: int) -> Union[NonNegativeInt, str]:
        """
        Return the signal's value at a given index in the waveform list.

        Args:
            idx (int): The index to retrieve the value for.

        Returns:
            Union[int, str]: The signal's value at the specified index.
        """
        return self.wf.get_signal(self.var).value_at_idx(idx)

    def __str__(self) -> str:
        return f'{self.var_type}({self.full_name})'

    def __repr__(self) -> str:
        return str(self)


@dataclass(frozen=True)
class VCDScope:
    scope: 'Scope'
    wf: Waveform

    @property
    def name(self) -> str:
        """Return the scope's name."""
        return self.scope.name(self.wf.hierarchy)

    @property
    def full_name(self) -> str:
        """Return the scope's full name."""
        return self.scope.full_name(self.wf.hierarchy)

    @property
    def scope_type(self) -> SCOPE_TYPES:
        """Return the scope's type."""
        return self.scope.scope_type()

    @property
    def scopes(self) -> List['VCDScope']:
        """Return a list of sub-scopes."""
        return [VCDScope(scope=s, wf=self.wf) for s in self.scope.scopes(self.wf.hierarchy)]

    @property
    def vars(self) -> List['VCDVar']:
        """Return a list of variables in the scope."""
        return [VCDVar(var=v, wf=self.wf) for v in self.scope.vars(self.wf.hierarchy)]

    def __str__(self) -> str:
        return f'{self.scope_type}({self.full_name})'

    def __repr__(self) -> str:
        return str(self)


class VCDWaveform:
    def __init__(self, wf: Union[Waveform, str, Path]):
        if isinstance(wf, Path):
            wf = str(wf)
        if isinstance(wf, str):
            wf = Waveform(wf)
        self.wf = wf

    @property
    def top_scopes(self) -> List[VCDScope]:
        """Return a list of top-level scopes."""
        return [VCDScope(s, self.wf) for s in self.wf.hierarchy.top_scopes()]

    @property
    def all_vars(self) -> Dict[str, VCDVar]:
        """Return a dictionary of all variables."""
        var_dict: Dict[str, VCDVar] = {}
        for s in self.top_scopes:
            self._add_all_vars(var_dict, s)
        return var_dict

    def _add_all_vars(self, var_dict: Dict[str, VCDVar], scope: VCDScope) -> None:
        for v in scope.vars:
            var_dict[v.full_name] = v
        for s in scope.scopes:
            self._add_all_vars(var_dict, s)

    def __str__(self) -> str:
        scope = '1 Top Scope' if len(self.top_scopes) == 1 else f' {len(self.top_scopes)} Top Scopes'
        var = '1 Variable' if len(self.all_vars) == 1 else f'{len(self.all_vars)} Variables'
        return f'Waveform({scope}, {var})'

    def __repr__(self) -> str:
        return str(self)
