import os
from collections import defaultdict
from typing import Callable
import minify_html_onepass
from dash import Dash, dcc, html
from dash.development.base_component import Component
from ._types import NumberLike
from .plot import size, time
from .experiments import dependency_from_report
from .helpers import get_command_line, get_plugin_options


def get_largest_submodule(sorted_modules: list[dict[dict[str, NumberLike], NumberLike]], formatter: Callable[[NumberLike], str]):
    """
    From within a module, find the largest submodule and format its value using the provided formatter. Returns a dict of submodule name to formatted value.
    """
    largest = defaultdict[str, str](str)
    for root_module, submodules in sorted_modules:
        biggest_module = ""
        biggest_time = 0
        for submodule, time in submodules.items():
            if time > biggest_time:
                biggest_time = time
                biggest_module = submodule

        largest[biggest_module] = formatter(biggest_time)

    return largest


def layout_to_html(component: Component | list[Component]):
    """
    Converts a Dash layout into a HTML string.
    """
    # Include the plotly.js library only for the first graph to avoid duplicate script tags
    has_included_plotlyjs = False

    def html_child(component: Component | list[Component]):
        """
        Recursively converts a Dash component or a list of components into an HTML string.
        Ensuring that the plotly.js library is included only once for all graphs.
        """
        nonlocal has_included_plotlyjs
        if isinstance(component, list):
            return ''.join(html_child(child) for child in component)

        if isinstance(component, dcc.Graph):
            comp = component.figure.to_html(
                include_plotlyjs='cdn' if not has_included_plotlyjs else False, full_html=False)
            has_included_plotlyjs = True
            return comp

        if isinstance(component, str | int | float):
            return str(component)

        if component is None:
            return ''

        element = component._type.lower()
        return f"<{element}>{html_child(component.children)}</{element}>"

    # return html_child(component)
    return minify_html_onepass.minify(f"<body>{html_child(component)}</body>", minify_js=True, minify_css=True)


def to_html(filename: str, export_filename: str = os.path.join(".", "index.html")):
    """Input a compile report to output a html report file with visualizations and summaries of the build time, build size, and dependency graph. The HTML file is saved to the specified export filename (or default, index.html next to the specified compile report)."""
    size_graph = size.get_plotter(filename)
    time_graph = time.get_plotter(filename)
    dep_fig, dep_graph = dependency_from_report.get_fig(filename)

    longest_times = get_largest_submodule(
        time_graph.sorted_modules, time.time_fmt)
    largest_sizes = get_largest_submodule(
        size_graph.sorted_modules, size.sizeof_fmt)

    layout = html.Div([
        html.H4('Command line'),
        html.Ul([html.Li(command)
                for command in get_command_line(filename)]),
        html.H4('Plugin options'),
        html.Table([
            html.Thead([
                html.Tr([
                    html.Th('Name'),
                    html.Th('User Enabled')
                ])
            ]),
            html.Tbody([
                html.Tr([
                    html.Td(name),
                    html.Td(enabled)
                ]) for name, enabled in get_plugin_options(filename)
            ])
        ]),
        html.H4('Build time Summary'),
        html.P(f"Total compile time: {time.time_fmt(time_graph.total)}"),
        html.P(
            f"Total root modules: {len(time_graph.module_parsed)} (incl. aggregated submodules: {sum(len(submodules) for submodules in time_graph.module_parsed.values())})"),
        html.H4("Largest submodule build time"),
        html.Ul([
            html.Li(f"{module}: {time}") for module, time in longest_times.items()]),
        dcc.Graph(figure=time_graph.fig, id='graph', style={'height': '70vh'}),
        html.H4('Build size Summary'),
        html.P(
            f"Total bytecode size: {size.sizeof_fmt(size_graph.total)}"),
        html.P(
            f"Total root modules: {len(size_graph.module_parsed)} (incl. aggregated submodules: {sum(len(submodules) for submodules in size_graph.module_parsed.values())})"),
        html.Ul([
            html.Li(f"{module}: {s}") for module, s in largest_sizes.items()]),
        dcc.Graph(figure=size_graph.fig, id='graph2',
                  style={'height': '70vh'}),
        html.H4('Dependency Summary'),
        html.P(
            f"Node count: {len(dep_graph.nodes())}"),
        dcc.Graph(figure=dep_fig,
                  id='graph3', style={'height': '70vh'}),
    ])
    with open(export_filename, "w", encoding="utf-8") as f:
        f.write(layout_to_html(layout))
    return export_filename
