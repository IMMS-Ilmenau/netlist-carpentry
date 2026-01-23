# stubs/dash/html.pyi
from typing import Any, Dict, List, Literal, Optional, Union

from dash.development.base_component import Component
from dash.html.P import ComponentType, NumberType

from netlist_carpentry.core.graph.visualization.formatting_types import StyleDict

# Type alias for children (can be a string, a number, a component, or a list of these)
ChildrenType = Union[str, int, float, Component, List[Any], None]

class Div(Component):
    def __init__(
        self,
        children: Optional[ChildrenType] = ...,
        *,
        id: Optional[str] = ...,
        className: Optional[str] = ...,
        style: Optional[StyleDict] = ...,
        hidden: Optional[bool] = ...,
        n_clicks: Optional[int] = ...,
        n_clicks_timestamp: Optional[int] = ...,
        key: Optional[str] = ...,
        role: Optional[str] = ...,
        accessKey: Optional[str] = ...,
        contentEditable: Optional[str] = ...,
        contextMenu: Optional[str] = ...,
        dir: Optional[str] = ...,
        draggable: Optional[str] = ...,
        lang: Optional[str] = ...,
        spellCheck: Optional[str] = ...,
        tabIndex: Optional[str] = ...,
        title: Optional[str] = ...,
        loading_state: Optional[Dict[str, Any]] = ...,
        **kwargs: Any,
    ) -> None: ...

class P(Component):
    def __init__(
        self,
        children: Optional[ComponentType] = None,
        id: Optional[Union[str, Dict[object, object]]] = None,
        n_clicks: Optional[NumberType] = None,
        n_clicks_timestamp: Optional[NumberType] = None,
        disable_n_clicks: Optional[bool] = None,
        key: Optional[str] = None,
        accessKey: Optional[str] = None,
        className: Optional[str] = None,
        contentEditable: Optional[str] = None,
        dir: Optional[str] = None,
        draggable: Optional[str] = None,
        hidden: Optional[Union[Literal['hidden', 'HIDDEN'], bool]] = None,
        lang: Optional[str] = None,
        role: Optional[str] = None,
        spellCheck: Optional[str] = None,
        style: Optional[Any] = None,
        tabIndex: Optional[Union[str, NumberType]] = None,
        title: Optional[str] = None,
        **kwargs: object,
    ) -> None: ...
