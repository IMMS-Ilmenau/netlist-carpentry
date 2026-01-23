"""A bunch of TypedDicts and Type Aliases (related to graph formatting and visualization) for convenience and structure."""

from typing import Dict, TypedDict

from pydantic import PositiveInt
from typing_extensions import NotRequired

NodeName = str
FormatName = str
NodeLabel = str


class NodeFormat(TypedDict):
    color: NotRequired[str]
    size: NotRequired[PositiveInt]


class FormatDict(TypedDict):
    node_formats: NotRequired[Dict[NodeName, FormatName]]
    """A dict of node names and associated format names."""
    formats: NotRequired[Dict[FormatName, NodeFormat]]
    """A dict of format names and associated attributes (e.g. node color, node size)."""
    labels: NotRequired[Dict[NodeName, NodeLabel]]
    """A dict of node names and associated labels."""


StyleDict = TypedDict(
    'StyleDict',
    {
        'background-color': NotRequired[str],
        'color': NotRequired[str],
        'content': NotRequired[str],
        'curve-style': NotRequired[str],
        'font-size': NotRequired[str],
        'font-style': NotRequired[str],
        'height': NotRequired[str],
        'label': NotRequired[str],
        'line-color': NotRequired[str],
        'shape': NotRequired[str],
        'target-arrow-color': NotRequired[str],
        'target-arrow-shape': NotRequired[str],
        'text-background-color': NotRequired[str],
        'text-background-opacity': NotRequired[int],
        'text-background-padding': NotRequired[str],
        'text-halign': NotRequired[str],
        'text-valign': NotRequired[str],
        'width': NotRequired[str],
    },
)


class StylesheetDict(TypedDict):
    selector: str
    style: StyleDict


class CytoscapeGraphDataDict(TypedDict):
    id: NotRequired[str]
    label: NotRequired[str]
    source: NotRequired[str]
    target: NotRequired[str]
    object_type: NotRequired[str]
    object_subtype: NotRequired[str]


class CytoscapeGraphDict(TypedDict):
    data: NotRequired[CytoscapeGraphDataDict]
    classes: NotRequired[str]


class CytoscapeLayoutDict(TypedDict):
    name: NotRequired[str]
    directed: NotRequired[bool]
    animate: NotRequired[bool]
