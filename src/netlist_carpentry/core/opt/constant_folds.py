from typing import List, Set

from tqdm import tqdm

from netlist_carpentry.core.exceptions import EvaluationError
from netlist_carpentry.core.netlist_elements.instance import Instance
from netlist_carpentry.core.netlist_elements.module import Module
from netlist_carpentry.utils.log import LOG


def opt_constant(module: Module) -> bool:
    any_removed = False
    while True:
        any_removed_this_iteration = opt_constant_mux_inputs(module)
        any_removed |= any_removed_this_iteration
        if not any_removed_this_iteration:
            return any_removed


def opt_constant_mux_inputs(module: Module) -> bool:
    inst_to_remove: List[Instance] = []

    for inst in tqdm(module.instances.values()):
        if inst.instance_type == '§mux':
            D0 = inst.connection_str_paths['D_0'].values()
            D1 = inst.connection_str_paths['D_1'].values()

            if all(i == '0' for i in D0) and all(i == '1' for i in D1):
                for j in inst.connections['Y']:
                    output_signal = module.get_from_path(inst.connections['Y'][j])  # PortSegment

                    for load in output_signal.loads():
                        module.disconnect(load)
                        module.connect(inst.connections['S'][0], load)

                inst_to_remove.append(inst)

    for inst in inst_to_remove:
        module.remove_instance(inst)

    return inst_to_remove != []


def opt_constant_propagation(module: Module) -> bool:
    any_propagated = False
    while True:
        now_propagated = _opt_constant_propagation_single_iter(module)
        any_propagated |= now_propagated
        if not now_propagated:
            break
    return any_propagated


def _opt_constant_propagation_single_iter(module: Module) -> bool:
    mark_delete: Set[Instance] = set()
    for inst in tqdm(module.instances.values()):
        if all(p.is_tied_defined for p in inst.input_ports):
            try:
                inst.evaluate()
            except EvaluationError as e:
                LOG.warn(f'Unable to evaluate instance {inst.raw_path}: {e}!')
                continue
            mark_delete.add(inst)
            for p in inst.output_ports:
                for idx, ps in p:
                    out_signal = ps.signal
                    w = module.get_wire(ps.wire_name)
                    ws = w[idx]
                    for ld in ws.loads():
                        module.disconnect(ld)
                        ld.tie_signal(out_signal)
                    w.remove_wire_segment(ws.index)
                    if not w.segments:
                        module.remove_wire(w)
    for inst in mark_delete:
        module.remove_instance(inst)
    return bool(mark_delete)
