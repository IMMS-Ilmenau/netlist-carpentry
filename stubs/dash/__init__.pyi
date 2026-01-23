# stubs/dash/__init__.pyi
from typing import Any, Callable, Dict, List, Literal, Optional, Union

import dash
from dash.dependencies import ComponentIdType, DashDependency
from flask import Flask

# Define a generic type for the layout (Component, list, or function)
LayoutType = Union[Any, Callable[[], Any]]
no_update = dash.no_update  # type: ignore[attr-defined, misc]

class Dash:
    server: Flask
    layout: LayoutType
    JupyterDisplayMode = Literal['inline', 'external', 'jupyterlab', 'tab', '_none']

    def __init__(
        self,
        name: Optional[str] = ...,
        server: Union[bool, Flask] = ...,
        static_folder: Optional[str] = ...,
        assets_folder: Optional[str] = ...,
        use_pages: bool = ...,
        external_stylesheets: Optional[List[Union[str, Dict[str, Any]]]] = ...,
        external_scripts: Optional[List[Union[str, Dict[str, Any]]]] = ...,
        url_base_pathname: Optional[str] = ...,
        suppress_callback_exceptions: bool = ...,
        prevent_initial_callbacks: bool = ...,
        # Add other common init args here as needed
        **kwargs: Any,
    ) -> None: ...
    def run_server(
        self,
        host: Optional[str] = ...,
        port: Optional[str | int] = ...,
        proxy: Optional[str] = ...,
        debug: bool = ...,
        dev_tools_ui: bool = ...,
        dev_tools_props_check: bool = ...,
        dev_tools_serve_dev_bundles: bool = ...,
        dev_tools_hot_reload: bool = ...,
        dev_tools_hot_reload_interval: int = ...,
        dev_tools_hot_reload_watch_interval: int = ...,
        dev_tools_hot_reload_max_retry: int = ...,
        dev_tools_silence_routes_logging: bool = ...,
        dev_tools_prune_errors: bool = ...,
        **kwargs: Any,
    ) -> None: ...
    def run(
        self,
        host: str | None = None,
        port: str | int | None = None,
        proxy: str | None = None,
        debug: bool | None = None,
        jupyter_mode: JupyterDisplayMode | None = None,
        jupyter_width: str = '100%',
        jupyter_height: int = 650,
        jupyter_server_url: str | None = None,
        dev_tools_ui: bool | None = None,
        dev_tools_props_check: bool | None = None,
        dev_tools_serve_dev_bundles: bool | None = None,
        dev_tools_hot_reload: bool | None = None,
        dev_tools_hot_reload_interval: int | None = None,
        dev_tools_hot_reload_watch_interval: int | None = None,
        dev_tools_hot_reload_max_retry: int | None = None,
        dev_tools_silence_routes_logging: bool | None = None,
        dev_tools_disable_version_check: bool | None = None,
        dev_tools_prune_errors: bool | None = None,
        **flask_run_options: Any,
    ) -> None: ...

    # The callback decorator
    def callback(
        self, output: Any, inputs: Any, state: Any = ..., prevent_initial_call: Optional[bool] = ...
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...

# Re-export html so 'from dash import html' works in your code
from . import html as html  # noqa: E402

class Output(DashDependency):  # pylint: disable=too-few-public-methods
    """Output of a callback."""

    def __init__(
        self,
        component_id: ComponentIdType,
        component_property: str,
        allow_duplicate: bool = False,
    ): ...

class Input(DashDependency):  # pylint: disable=too-few-public-methods
    """Input of callback: trigger an update when it is updated."""

    def __init__(
        self,
        component_id: ComponentIdType,
        component_property: str,
        allow_optional: bool = False,
    ): ...

class State(DashDependency):  # pylint: disable=too-few-public-methods
    """Use the value of a State in a callback but don't trigger updates."""

    def __init__(
        self,
        component_id: ComponentIdType,
        component_property: str,
        allow_optional: bool = False,
    ): ...
