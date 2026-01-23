# stubs/dash_cytoscape.pyi
from typing import Any, Dict, List, Optional

from dash.development.base_component import Component

from netlist_carpentry.core.graph.visualization.formatting_types import (
    CytoscapeGraphDict,
    CytoscapeLayoutDict,
    StylesheetDict,
)

class Cytoscape(Component):
    def __init__(
        self,
        id: Optional[str] = ...,
        elements: Optional[List[CytoscapeGraphDict]] = ...,
        stylesheet: Optional[List[StylesheetDict]] = ...,
        layout: Optional[CytoscapeLayoutDict] = ...,
        style: Optional[Dict[str, str]] = ...,
        **kwargs: Any,
    ) -> None: ...

def load_extra_layouts() -> None: ...
