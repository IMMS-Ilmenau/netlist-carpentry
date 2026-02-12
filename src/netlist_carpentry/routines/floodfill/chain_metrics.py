"""
Gate-Chain Optimizer Metrics & Reporting.

Contains all dataclasses and reporting functionality.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from netlist_carpentry.core.netlist_elements.element_path import WireSegmentPath


class ChainStatus(Enum):
    """Status of a chain replacement attempt."""

    REPLACED = auto()
    SKIPPED_RESOLUTION_FAILED = auto()
    SKIPPED_BOUNDARY_FAILED = auto()
    SKIPPED_DISCONNECT_FAILED = auto()
    SKIPPED_DEGENERATE = auto()
    FAILED_TREE_BUILD = auto()


@dataclass
class GateAnalysis:
    """Analysis of gates in a module by input count."""

    total_gates: int = 0
    by_input_count: Dict[int, int] = field(default_factory=dict)
    constant_input_gates: int = 0

    def add_gate(self, real_inputs: int, has_constant: bool) -> None:
        self.total_gates += 1
        self.by_input_count[real_inputs] = self.by_input_count.get(real_inputs, 0) + 1
        if has_constant:
            self.constant_input_gates += 1

    def summary(self) -> str:
        parts = [f"{k}-input: {v}" for k, v in sorted(self.by_input_count.items())]
        return f"Total: {self.total_gates} ({', '.join(parts)})"


@dataclass
class ChainBoundary:
    """Defines the input/output boundary of a gate-chain."""

    inputs: List["WireSegmentPath"]
    output: "WireSegmentPath"
    internal_wires: List["WireSegmentPath"]


@dataclass
class ChainInfo:
    """Detailed information about a single chain."""

    chain_keys: List[str]
    status: ChainStatus
    error_message: Optional[str] = None
    num_gates: int = 0
    num_inputs: int = 0
    num_internal_wires: int = 0
    num_constant_inputs: int = 0
    output_wire: Optional[str] = None
    input_wires: List[str] = field(default_factory=list)

    @property
    def length(self) -> int:
        return len(self.chain_keys)

    @property
    def was_replaced(self) -> bool:
        return self.status == ChainStatus.REPLACED

    @property
    def was_skipped(self) -> bool:
        return self.status in (
            ChainStatus.SKIPPED_RESOLUTION_FAILED,
            ChainStatus.SKIPPED_BOUNDARY_FAILED,
            ChainStatus.SKIPPED_DISCONNECT_FAILED,
            ChainStatus.SKIPPED_DEGENERATE,
        )

    @property
    def is_degenerate(self) -> bool:
        """Chain is degenerate (only constant inputs) - expected skip, not an error."""
        return self.status == ChainStatus.SKIPPED_DEGENERATE

    @property
    def is_problematic_skip(self) -> bool:
        """Chain was skipped due to an unexpected problem."""
        return self.was_skipped and not self.is_degenerate

    @property
    def failed(self) -> bool:
        return self.status == ChainStatus.FAILED_TREE_BUILD

    @property
    def has_constants(self) -> bool:
        return self.num_constant_inputs > 0

    def __repr__(self) -> str:
        if self.was_replaced:
            const_info = f", {self.num_constant_inputs} constants" if self.num_constant_inputs else ""
            return f"ChainInfo({self.length} gates -> {self.num_inputs} inputs{const_info}, {self.status.name})"
        return f"ChainInfo({self.length} gates, {self.status.name}: {self.error_message})"


@dataclass
class ModuleReport:
    """Detailed report for a single module."""

    module_name: str
    gate_analysis: GateAnalysis = field(default_factory=GateAnalysis)
    chains_detected: int = 0
    chains_replaced: int = 0
    chains_skipped: int = 0
    chains_failed: int = 0
    skipped_details: List[Dict] = field(default_factory=list)
    failed_details: List[Dict] = field(default_factory=list)


@dataclass
class ReplacementResult:
    """Statistics for chain replacement operations in one module."""

    chains_detected: List[List[str]]
    chains_replaced: int = 0
    chains_skipped: int = 0
    chains_failed: int = 0
    chain_details: List[ChainInfo] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Detected: {len(self.chains_detected)}, "
            f"Replaced: {self.chains_replaced}, "
            f"Skipped: {self.chains_skipped}, "
            f"Failed: {self.chains_failed}"
        )

    def skipped_chains(self) -> List[ChainInfo]:
        return [c for c in self.chain_details if c.was_skipped]

    def failed_chains(self) -> List[ChainInfo]:
        return [c for c in self.chain_details if c.failed]

    def replaced_chains(self) -> List[ChainInfo]:
        return [c for c in self.chain_details if c.was_replaced]


@dataclass
class CircuitOptimizationResult:
    """Complete statistics for circuit-wide optimization."""

    modules_processed: int = 0
    modules_with_chains: int = 0
    total_chains_detected: int = 0
    total_chains_replaced: int = 0
    total_chains_skipped: int = 0
    total_chains_failed: int = 0
    module_results: Dict[str, ReplacementResult] = field(default_factory=dict)
    module_reports: Dict[str, ModuleReport] = field(default_factory=dict)

    def summary(self) -> str:
        return (
            f"Modules: {self.modules_processed} ({self.modules_with_chains} with chains)\n"
            f"Chains: {self.total_chains_detected} detected, "
            f"{self.total_chains_replaced} replaced, "
            f"{self.total_chains_skipped} skipped, "
            f"{self.total_chains_failed} failed"
        )

    def all_chain_details(self) -> List[Tuple[str, ChainInfo]]:
        result: List[Tuple[str, ChainInfo]] = []
        for module_name, mod_result in self.module_results.items():
            result.extend((module_name, chain_info) for chain_info in mod_result.chain_details)
        return result

    def all_skipped(self) -> List[Tuple[str, ChainInfo]]:
        return [(m, c) for m, c in self.all_chain_details() if c.was_skipped]

    def all_degenerate(self) -> List[Tuple[str, ChainInfo]]:
        """Return all degenerate chains (expected skips - only constant inputs)."""
        return [(m, c) for m, c in self.all_chain_details() if c.is_degenerate]

    def all_problematic(self) -> List[Tuple[str, ChainInfo]]:
        """Return problematic skips (unexpected issues requiring attention)."""
        return [(m, c) for m, c in self.all_chain_details() if c.is_problematic_skip]

    def all_failed(self) -> List[Tuple[str, ChainInfo]]:
        return [(m, c) for m, c in self.all_chain_details() if c.failed]

    def all_with_constants(self) -> List[Tuple[str, ChainInfo]]:
        return [(m, c) for m, c in self.all_chain_details() if c.has_constants]

    @staticmethod
    def _keys_preview(keys: List[str], limit: int = 3) -> str:
        """Return a compact preview string for a list of keys."""
        if not keys:
            return ""
        keys_str = ", ".join(keys[:limit])
        if len(keys) > limit:
            keys_str += f"... (+{len(keys) - limit} more)"
        return keys_str

    @staticmethod
    def _log_header(log: Callable[[str], None]) -> None:
        """Log report header."""
        log("")
        log("=" * 70)
        log("GATE CHAIN OPTIMIZATION - FINAL REPORT")
        log("=" * 70)

    def _log_overall_summary(self, log: Callable[[str], None]) -> Tuple[int, int]:
        """Log overall summary and return (degenerate_count, problematic_count)."""
        degenerate_count = len(self.all_degenerate())
        problematic_count = len(self.all_problematic())

        log("")
        log("### OVERALL SUMMARY ###")
        log(f"  Modules processed:     {self.modules_processed}")
        log(f"  Modules with chains:   {self.modules_with_chains}")
        log(f"  Total chains found:    {self.total_chains_detected}")
        log(f"  Successfully replaced: {self.total_chains_replaced}")
        log(f"  Skipped (degenerate):  {degenerate_count} (expected - only constant inputs)")
        log(f"  Skipped (problematic): {problematic_count}")
        log(f"  Failed:                {self.total_chains_failed}")

        return degenerate_count, problematic_count

    @staticmethod
    def _log_success_footer(log: Callable[[str], None], degenerate_count: int) -> None:
        """Log success footer when no problems remain."""
        if degenerate_count > 0:
            log(f"\n✓ All viable chains replaced! ({degenerate_count} degenerate chains skipped as expected)")
        else:
            log("\n✓ All chains were successfully replaced!")
        log("=" * 70)

    def _iter_modules_with_results(self):
        """Yield (module_name, report, mod_result) for modules that have results."""
        for module_name, report in self.module_reports.items():
            mod_result = self.module_results.get(module_name)
            if mod_result is None:
                continue
            yield module_name, report, mod_result

    def _log_problematic_skips(self, log: Callable[[str], None], chain_infos: List[ChainInfo]) -> None:
        """Log problematic skips section for a module."""
        log(f"\n  PROBLEMATIC SKIPS ({len(chain_infos)}):")
        for chain_info in chain_infos:
            log(f"    • Chain with {chain_info.num_gates} gates:")
            log(f"      Status: {chain_info.status.name}")
            log(f"      Inputs: {chain_info.num_inputs}, Constants: {chain_info.num_constant_inputs}")
            log(f"      Error: {chain_info.error_message}")
            keys_str = self._keys_preview(chain_info.chain_keys or [])
            if keys_str:
                log(f"      Keys: {keys_str}")

    def _log_failed_chains(self, log: Callable[[str], None], failed_details: List[Dict]) -> None:
        """Log failed chains section for a module."""
        log(f"\n  FAILED CHAINS ({len(failed_details)}):")
        for detail in failed_details:
            log(f"    • Chain with {detail['num_gates']} gates:")
            log(f"      Error: {detail['error']}")
            keys = detail.get("keys") or []
            keys_str = self._keys_preview(keys)
            if keys_str:
                log(f"      Keys: {keys_str}")

    def _log_modules_with_problems(self, log: Callable[[str], None]) -> None:
        """Log module sections that contain problematic skips or failures."""
        log("")
        log("-" * 70)
        log("### MODULES WITH PROBLEMS ###")
        log("-" * 70)

        for module_name, report, mod_result in self._iter_modules_with_results():
            problematic_in_module = [c for c in mod_result.chain_details if c.is_problematic_skip]
            degenerate_in_module = [c for c in mod_result.chain_details if c.is_degenerate]

            if len(problematic_in_module) == 0 and report.chains_failed == 0:
                continue

            log(f"\n[MODULE: {module_name}]")
            log(f"  Gate analysis: {report.gate_analysis.summary()}")
            if report.gate_analysis.constant_input_gates > 0:
                log(f"  Gates with constant inputs: {report.gate_analysis.constant_input_gates}")

            log(
                f"  Chains: {report.chains_detected} detected, {report.chains_replaced} replaced, "
                f"{len(degenerate_in_module)} degenerate, {len(problematic_in_module)} problematic, "
                f"{report.chains_failed} failed"
            )

            if problematic_in_module:
                self._log_problematic_skips(log, problematic_in_module)

            if report.failed_details:
                self._log_failed_chains(log, report.failed_details)

    def _log_skip_reason_summary(self, log: Callable[[str], None]) -> None:
        """Log skip reason summary section."""
        log("")
        log("-" * 70)
        log("### SKIP REASON SUMMARY ###")
        log("-" * 70)

        reason_counts: Dict[str, int] = {}
        input_count_distribution: Dict[int, int] = {}

        for _, chain_info in self.all_skipped():
            reason = chain_info.status.name
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

            inputs = chain_info.num_inputs
            input_count_distribution[inputs] = input_count_distribution.get(inputs, 0) + 1

        log("\nBy reason:")
        for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
            marker = " (expected)" if reason == "SKIPPED_DEGENERATE" else ""
            log(f"  {reason}: {count}{marker}")

        log("\nSkipped chains by external input count:")
        for input_count in sorted(input_count_distribution):
            count = input_count_distribution[input_count]
            log(f"  {input_count} inputs: {count} chains")

        log("")
        log("=" * 70)

    def _log_report(self, log: Callable[[str], None]) -> None:
        """Log the final optimization report. Internal use only."""
        self._log_header(log)
        degenerate_count, problematic_count = self._log_overall_summary(log)

        if problematic_count == 0 and self.total_chains_failed == 0:
            self._log_success_footer(log, degenerate_count)
            return

        self._log_modules_with_problems(log)
        self._log_skip_reason_summary(log)
