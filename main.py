import os
from collections import defaultdict
from typing import Callable, Literal
import minify_html_onepass
from dash import Dash, dcc, html
from dash.development.base_component import Component
from _types import NumberLike
from plot import size, time
from threading import Thread
from experiments import dependency_from_report
import helpers

app = Dash(__name__)
OUTPUT_DIR = "export"
FILE = "compilation-report.xml"


def calc_largest(sorted_modules: list[dict[dict[str, NumberLike]]], parser: Callable[[NumberLike], str]):
    largest = defaultdict(str)
    for root_module, submodules in sorted_modules:
        biggest_module = ""
        biggest_time = 0
        for submodule, time in submodules.items():
            if time > biggest_time:
                biggest_time = time
                biggest_module = submodule

        largest[biggest_module] = parser(biggest_time)

    return largest


longest_times = calc_largest(time.plot.sorted_modules, time.time_fmt)
largest_sizes = calc_largest(size.plot.sorted_modules, size.sizeof_fmt)

app.layout = html.Div([
    html.H4('Command line'),
    html.Ul([html.Li(command) for command in helpers.get_command_line(FILE)]),
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
            ]) for name, enabled in helpers.get_plugins(FILE)
        ])
    ]),

    html.H4('Build time Summary'),
    html.P(f"Total compile time: {time.time_fmt(time.plot.total)}"),
    html.P(
        f"Total root modules: {len(time.plot.module_parsed)} (incl. submodules: {sum(len(submodules) for submodules in time.plot.module_parsed.values())})"),
    html.H4("Largest submodule build time"),
    html.Ul([
        html.Li(f"{module}: {time}") for module, time in longest_times.items()]),
    dcc.Graph(figure=time.plot.fig, id='graph', style={'height': '70vh'}),
    html.H4('Build size Summary'),
    html.P(
        f"Total bytecode size: {size.sizeof_fmt(size.plot.total)}"),
    html.P(
        f"Total root modules: {len(size.plot.module_parsed)} (incl. submodules: {sum(len(submodules) for submodules in size.plot.module_parsed.values())})"),
    html.Ul([
        html.Li(f"{module}: {s}") for module, s in largest_sizes.items()]),
    dcc.Graph(figure=size.plot.fig, id='graph2', style={'height': '70vh'}),
    html.H4('Dependency Summary'),
    html.P(
        f"High-level node count: {len(dependency_from_report.G.nodes())}"),
    dcc.Graph(figure=dependency_from_report.fig,
              id='graph3', style={'height': '70vh'}),
])

_include_plotlyjs = True


def layout_to_html(component: Component | list[Component], include_plotlyjs: bool | Literal['cdn'] = True):
    global _include_plotlyjs
    _include_plotlyjs = include_plotlyjs

    def html_child(component: Component | list[Component]):
        global _include_plotlyjs
        if isinstance(component, list):
            return ''.join(html_child(child) for child in component)

        if isinstance(component, dcc.Graph):
            comp = component.figure.to_html(
                include_plotlyjs=_include_plotlyjs, full_html=False)
            _include_plotlyjs = False
            return comp

        if isinstance(component, str | int | float):
            return component

        if component is None:
            return ''

        element = component._type.lower()
        return f"<{element}>{html_child(component.children)}</{element}>"

    # return html_child(component)
    return minify_html_onepass.minify(f"<body>{html_child(component)}</body>", minify_js=True, minify_css=True)


def to_html():
    """Convert the Dash app to HTML."""
    # Save the Dash app as HTML
    html_file = os.path.join(OUTPUT_DIR, "index.html")
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(layout_to_html(app.layout, 'cdn'))
    return html_file


thread = Thread(target=to_html, daemon=True).start()

app.run(debug=True)
