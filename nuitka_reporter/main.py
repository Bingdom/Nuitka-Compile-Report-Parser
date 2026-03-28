import os
from collections import defaultdict
from typing import Callable
import minify_html_onepass
from dash import dcc, html
from dash.development.base_component import Component
from ._types import NumberLike
from .plot import size, time
from .plot.plotter import Plotter
from .experiments import dependency_from_report
from .helpers import get_command_line, get_plugin_options
from typing import NamedTuple


SWITCH_GRAPH_JS = """<script>
function switchGraph(id, type) {
    ['bar', 'treemap', 'sunburst'].forEach(function(t) {
        document.getElementById(id + '_' + t).style.display = t === type ? '' : 'none';
        document.getElementById(id + '_' + t + '_btn').style.fontWeight = t === type ? 'bold' : 'normal';
    });
    var plotDiv = document.getElementById(id + '_' + type).querySelector('.plotly-graph-div');
    if (plotDiv) Plotly.Plots.resize(plotDiv);
}
</script>"""


def switchable_graph_html(plotter: Plotter, graph_id: str, include_plotlyjs: bool = False) -> str:
    """Generate raw HTML with toggle buttons to switch between bar chart, treemap, and sunburst."""
    bar_html = plotter.get_figure("bar").to_html(
        include_plotlyjs='cdn' if include_plotlyjs else False, full_html=False)
    treemap_html = plotter.get_figure("treemap").to_html(
        include_plotlyjs=False, full_html=False)
    sunburst_html = plotter.get_figure("sunburst").to_html(
        include_plotlyjs=False, full_html=False)

    return (
        f'<div>'
        f'<button onclick="switchGraph(\'{graph_id}\',\'bar\')" '
        f'id="{graph_id}_bar_btn" style="font-weight:bold">Bar Chart</button> '
        f'<button onclick="switchGraph(\'{graph_id}\',\'treemap\')" '
        f'id="{graph_id}_treemap_btn">Treemap</button> '
        f'<button onclick="switchGraph(\'{graph_id}\',\'sunburst\')" '
        f'id="{graph_id}_sunburst_btn">Sunburst</button>'
        f'<div id="{graph_id}_bar">{bar_html}</div>'
        f'<div id="{graph_id}_treemap" style="display:none">{treemap_html}</div>'
        f'<div id="{graph_id}_sunburst" style="display:none">{sunburst_html}</div>'
        f'</div>'
    )


class LargestSubmodule(NamedTuple):
    """
    Includes the root module, the largest submodule, and the value of the largest submodule (e.g. build time or size).
    """
    module: str
    submodule: str
    value: str


def get_largest_submodule(sorted_modules: list[tuple[str, defaultdict[str, NumberLike]]], formatter: Callable[[NumberLike], str]):
    """
    From within a module, find the largest submodule and format its value using the provided formatter. Returns a list of LargestSubmodule named tuples.
    """
    largest_submodules: list[LargestSubmodule] = []
    for root_module, submodules in sorted_modules:
        biggest_module = ""
        biggest_value = 0
        for submodule, value in submodules.items():
            if value > biggest_value:
                biggest_value = value
                biggest_module = submodule

        # Try to get the submodule name without the root module for easier reading
        biggest_module = f".<b>{'.'.join(biggest_module.split('.')[1:])}</b>" if biggest_module.startswith(
            root_module + ".") else ' (root)'

        largest_submodules.append(LargestSubmodule(
            root_module, biggest_module, formatter(biggest_value)))

    return largest_submodules


def component_to_html(component: Component | list[Component]):
    """
    Recursively converts Dash component(s) into an HTML string.

    *Note: This function is not well tested and may not cover all edge cases of Dash components.*
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

    component = html.Div([
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
        html.H4('Transpilation time Summary'),
        html.P(f"Total compile time: {time.time_fmt(time_graph.total)}"),
        html.P(
            f"Total root modules: {len(time_graph.module_parsed)} (incl. aggregated submodules: {sum(len(submodules) for submodules in time_graph.module_parsed.values())})"),
        html.H4("Largest submodule transpilation times summary"),
        html.Ul([
            html.Li(f"{module}{submodule}: {time}") for module, submodule, time in longest_times]),
        switchable_graph_html(time_graph, 'time_graph', include_plotlyjs=True),
        SWITCH_GRAPH_JS,
        html.H4('Largest submodule sizes summary'),
        html.P(
            f"Total {size.get_size_type(filename)} size: {size.sizeof_fmt(size_graph.total)}"),
        html.P(
            f"Total root modules: {len(size_graph.module_parsed)} (incl. aggregated submodules: {sum(len(submodules) for submodules in size_graph.module_parsed.values())})"),
        html.Ul([
            html.Li(f"{module}{submodule}: {s}") for module, submodule, s in largest_sizes]),
        switchable_graph_html(size_graph, 'size_graph'),
        html.H4('Dependency Summary'),
        html.P(
            f"Node count: {len(dep_graph.nodes())}"),
        dep_fig.to_html(include_plotlyjs=False, full_html=False),
    ])
    with open(export_filename, "w", encoding="utf-8") as f:
        f.write(component_to_html(component))
    return export_filename
