import os
import re
from collections import defaultdict
from typing import Callable
from html import escape as html_escape

import minify_html_onepass
from dash import dcc, html
from dash.development.base_component import Component
import dash_bootstrap_components as dbc

from ._types import NumberLike
from .plot import size, time
from .plot.plotter import Plotter
from .experiments import dependency_from_report
from .helpers import get_command_line, get_data_files, get_distributions, get_included, get_plugin_options
from typing import NamedTuple

BOOTSTRAP_CSS = '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" crossorigin="anonymous">'

CUSTOM_CSS = """<style>
.card { box-shadow: 0 .125rem .25rem rgba(0,0,0,.075); }
.stat-card .card-body { padding: 1rem; }
.stat-card h6 { font-size: .85rem; margin-bottom: .25rem; }
.stat-card h4 { margin-bottom: 0; }
</style>"""

SWITCH_GRAPH_JS = """<script>
function switchGraph(id, type) {
    ['bar', 'treemap', 'sunburst'].forEach(function(t) {
        document.getElementById(id + '_' + t).style.display = t === type ? '' : 'none';
        var btn = document.getElementById(id + '_' + t + '_btn');
        if (t === type) { btn.classList.add('active'); } else { btn.classList.remove('active'); }
    });
    var plotDiv = document.getElementById(id + '_' + type).querySelector('.plotly-graph-div');
    if (plotDiv) Plotly.Plots.resize(plotDiv);
}
</script>"""

# DBC component type -> (html_tag, default_bootstrap_class)
_DBC_TAG_MAP = {
    'Container': ('div', 'container'),
    'Row':       ('div', 'row'),
    'Col':       ('div', 'col'),
    'Card':      ('div', 'card'),
    'CardBody':  ('div', 'card-body'),
    'CardHeader': ('div', 'card-header'),
    'CardFooter': ('div', 'card-footer'),
    'Table':     ('table', 'table'),
    'Badge':     ('span', 'badge'),
    'Alert':     ('div', 'alert'),
    'ListGroup':     ('div', 'list-group'),
    'ListGroupItem': ('div', 'list-group-item'),
}

_VOID_ELEMENTS = frozenset({
    'br', 'hr', 'img', 'input', 'meta', 'link', 'area',
    'base', 'col', 'embed', 'source', 'track', 'wbr',
})


def _camel_to_kebab(name: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '-', name).lower()


def _style_to_str(style: dict | str | None) -> str:
    if not style:
        return ''
    if isinstance(style, str):
        return style
    return '; '.join(f'{_camel_to_kebab(k)}: {v}' for k, v in style.items())


def _build_attrs(props: dict, extra_classes: str = '') -> str:
    attrs: dict[str, str] = {}

    cls = props.get('className', '') or ''
    if extra_classes:
        cls = f"{extra_classes} {cls}".strip() if cls else extra_classes
    if cls:
        attrs['class'] = cls

    style = props.get('style')
    if style:
        attrs['style'] = _style_to_str(style)

    id_val = props.get('id')
    if id_val and isinstance(id_val, str):
        attrs['id'] = id_val

    href = props.get('href')
    if href:
        attrs['href'] = href

    colSpan = props.get('colSpan')
    if colSpan:
        attrs['colspan'] = str(colSpan)

    if not attrs:
        return ''
    return ' ' + ' '.join(
        f'{k}="{html_escape(str(v), quote=True)}"' for k, v in attrs.items()
    )


def _dbc_extra_classes(comp_type: str, props: dict) -> str:
    classes: list[str] = []
    tag_info = _DBC_TAG_MAP.get(comp_type)
    if tag_info:
        classes.append(tag_info[1])

    if comp_type == 'Col':
        for sz in ('xs', 'sm', 'md', 'lg', 'xl', 'xxl'):
            val = props.get(sz)
            if val is not None:
                if val is True:
                    classes.append(f'col-{sz}')
                else:
                    classes.append(f'col-{sz}-{val}')

    if comp_type == 'Table':
        for prop in ('striped', 'bordered', 'hover', 'dark'):
            if props.get(prop):
                classes.append(f'table-{prop}')

    if comp_type == 'Badge':
        color = props.get('color', 'primary')
        classes.append(f'text-bg-{color}')

    if comp_type == 'Alert':
        color = props.get('color', 'primary')
        classes.append(f'alert-{color}')

    return ' '.join(classes)


def switchable_graph_html(plotter: Plotter, graph_id: str, include_plotlyjs: bool = False) -> str:
    """Generate raw HTML with Bootstrap-styled toggle buttons to switch between bar chart, treemap, and sunburst."""
    bar_html = plotter.get_figure("bar").to_html(
        include_plotlyjs='cdn' if include_plotlyjs else False, full_html=False)
    treemap_html = plotter.get_figure("treemap").to_html(
        include_plotlyjs=False, full_html=False)
    sunburst_html = plotter.get_figure("sunburst").to_html(
        include_plotlyjs=False, full_html=False)

    return (
        f'<div class="mb-3">'
        f'<div class="btn-group mb-2" role="group">'
        f'<button class="btn btn-outline-primary active" onclick="switchGraph(\'{graph_id}\',\'bar\')" '
        f'id="{graph_id}_bar_btn">Bar Chart</button>'
        f'<button class="btn btn-outline-primary" onclick="switchGraph(\'{graph_id}\',\'treemap\')" '
        f'id="{graph_id}_treemap_btn">Treemap</button>'
        f'<button class="btn btn-outline-primary" onclick="switchGraph(\'{graph_id}\',\'sunburst\')" '
        f'id="{graph_id}_sunburst_btn">Sunburst</button>'
        f'</div>'
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


def component_to_html(component: Component | list[Component]) -> str:
    """
    Recursively converts Dash component(s) into an HTML string.
    Supports standard html.*, dcc.Graph, and dash_bootstrap_components.*.
    Handles className, style, id, and href attributes.
    """
    has_included_plotlyjs = False

    def html_child(component: Component | list[Component]) -> str:
        nonlocal has_included_plotlyjs
        if isinstance(component, list | tuple):
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

        try:
            plotly_json = component.to_plotly_json()
        except Exception:
            return str(component)

        comp_type = plotly_json.get('type', 'div')
        namespace = plotly_json.get('namespace', '')
        props = plotly_json.get('props', {})
        children = props.get('children', '')

        # DBC components
        if namespace == 'dash_bootstrap_components':
            tag_info = _DBC_TAG_MAP.get(comp_type)
            if tag_info:
                tag = tag_info[0]
                extra_classes = _dbc_extra_classes(comp_type, props)
            else:
                tag = 'div'
                extra_classes = ''
            attrs = _build_attrs(props, extra_classes)
            if tag in _VOID_ELEMENTS:
                return f'<{tag}{attrs}/>'
            content = html_child(children) if children else ''
            return f'<{tag}{attrs}>{content}</{tag}>'

        # Standard html.* components
        element = comp_type.lower()
        attrs = _build_attrs(props)
        if element in _VOID_ELEMENTS:
            return f'<{element}{attrs}/>'
        content = html_child(children) if children else ''
        return f'<{element}{attrs}>{content}</{element}>'

    return html_child(component)


def get_included_table(filename: str, element_name: str):
    return dbc.Table([
        html.Thead(html.Tr([
            html.Th('Name'),
            html.Th('Dest Path'),
            html.Th('Package'),
            html.Th('Ignored'),
            html.Th('Reason'),
        ])),
        html.Tbody([
            html.Tr([
                html.Td(name),
                html.Td(html.Code(dest)),
                html.Td(pkg or html.Span(
                    '—', className='text-muted')),
                html.Td(html.Code(ignored)) if ignored else html.Td(html.Span(
                    '—', className='text-muted')),
                html.Td(reason),
            ]) for name, dest, pkg, ignored, reason in get_included(filename, element_name)
        ]) if get_included(filename, element_name) else html.Tbody(html.Tr(html.Td('None', colSpan=5, className='text-muted text-center'))),
    ], striped=True, hover=True, bordered=True)


def to_html(filename: str, export_filename: str = os.path.join(".", "index.html")):
    """Input a compile report to output a html report file with visualizations and summaries of the build time, build size, and dependency graph. The HTML file is saved to the specified export filename (or default, index.html next to the specified compile report)."""
    size_graph = size.get_plotter(filename)
    time_graph = time.get_plotter(filename)
    dep_fig, dep_graph = dependency_from_report.get_fig(filename)

    longest_times = get_largest_submodule(
        time_graph.sorted_modules, time.time_fmt)
    largest_sizes = get_largest_submodule(
        size_graph.sorted_modules, size.sizeof_fmt)

    component = dbc.Container([
        html.H2('Nuitka Compilation Report', className='my-4'),

        # Command line
        dbc.Card([
            dbc.CardHeader(html.H5('Command line', className='mb-0')),
            dbc.CardBody(
                dbc.ListGroup([
                    dbc.ListGroupItem(html.Code(command))
                    for command in get_command_line(filename)
                ])
            ),
        ], className='mb-4'),

        # Plugin options & Distributions
        dbc.Row([
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader(
                        html.H5('Plugin options', className='mb-0')),
                    dbc.CardBody(
                        dbc.Table([
                            html.Thead(html.Tr([
                                html.Th('Name'),
                                html.Th('User Enabled'),
                            ])),
                            html.Tbody([
                                html.Tr([
                                    html.Td(name),
                                    html.Td(
                                        dbc.Badge(
                                            'Yes' if enabled == 'True' else enabled,
                                            color='success' if enabled == 'True' else 'secondary',
                                        )
                                    ),
                                ]) for name, enabled in get_plugin_options(filename)
                            ]),
                        ], striped=True, hover=True, bordered=True)
                    ),
                ], className='h-100'),
                md=6,
            ),
            dbc.Col(
                dbc.Card([
                    dbc.CardHeader(html.H5('Distributions', className='mb-0')),
                    dbc.CardBody(
                        dbc.Table([
                            html.Thead(html.Tr([
                                html.Th('Name'),
                                html.Th('Version'),
                                html.Th('Installer'),
                            ])),
                            html.Tbody([
                                html.Tr([
                                    html.Td(name),
                                    html.Td(version),
                                    html.Td(installer),
                                ]) for name, version, installer in get_distributions(filename)
                            ]),
                        ], striped=True, hover=True, bordered=True)
                    ),
                ], className='h-100'),
                md=6,
            ),
        ], className='mb-4'),

        # Included Extensions, Included DLLs, Excluded DLLs
        dbc.Card([
            dbc.CardHeader(
                html.H5('Included Extensions & DLLs', className='mb-0')),
            dbc.CardBody([
                html.H6('Included Extensions', className='mt-0 mb-2'),
                get_included_table(filename, "included_extension"),

                html.H6('Included DLLs', className='mt-4 mb-2'),
                get_included_table(filename, "included_dll"),

                html.H6('Excluded DLLs', className='mt-4 mb-2'),
                get_included_table(filename, "excluded_dll"),
            ]),
        ], className='mb-4'),

        # Data Files
        dbc.Card([
            dbc.CardHeader(html.H5('Data Files', className='mb-0')),
            dbc.CardBody(
                dbc.Table([
                    html.Thead(html.Tr([
                        html.Th('Name'),
                        html.Th('Source'),
                        html.Th('Size'),
                        html.Th('Reason'),
                        html.Th('Tags'),
                    ])),
                    html.Tbody([
                        html.Tr([
                            html.Td(name),
                            html.Td(html.Code(source)),
                            html.Td(size.sizeof_fmt(sz)),
                            html.Td(reason),
                            html.Td([
                                dbc.Badge(tag.strip(), color='info',
                                          className='me-1')
                                for tag in tags.split(',') if tag.strip()
                            ] if tags else html.Span('\u2014', className='text-muted')),
                        ]) for name, source, sz, reason, tags in get_data_files(filename)
                    ]) if get_data_files(filename) else html.Tbody(
                        html.Tr(html.Td('None', colSpan=5,
                                className='text-muted text-center'))
                    ),
                ], striped=True, hover=True, bordered=True)
            ),
        ], className='mb-4'),

        # Transpilation Time
        dbc.Card([
            dbc.CardHeader(html.H5('Transpilation time', className='mb-0')),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col(
                        dbc.Card([
                            dbc.CardBody([
                                html.H6('Total time', className='text-muted'),
                                html.H4(time.time_fmt(time_graph.total)),
                            ])
                        ], className='text-center stat-card'),
                        md=6,
                    ),
                    dbc.Col(
                        dbc.Card([
                            dbc.CardBody([
                                html.H6('Root modules',
                                        className='text-muted'),
                                html.H4(str(len(time_graph.module_parsed))),
                                html.Small(
                                    f"({sum(len(s) for s in time_graph.module_parsed.values())} submodules)",
                                    className='text-muted',
                                ),
                            ])
                        ], className='text-center stat-card'),
                        md=6,
                    ),
                ], className='mb-3'),
                html.H6('Largest submodule transpilation times',
                        className='mt-3'),
                dbc.ListGroup([
                    dbc.ListGroupItem([
                        html.Span(f"{module}{submodule}"),
                        dbc.Badge(t, color='info', className='float-end'),
                    ])
                    for module, submodule, t in longest_times
                ], className='mb-3'),
                switchable_graph_html(
                    time_graph, 'time_graph', include_plotlyjs=True),
            ]),
        ], className='mb-4'),

        SWITCH_GRAPH_JS,

        # Build Size
        dbc.Card([
            dbc.CardHeader(html.H5('Build size', className='mb-0')),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col(
                        dbc.Card([
                            dbc.CardBody([
                                html.H6(
                                    f'Total {size.get_size_type(filename)} size',
                                    className='text-muted',
                                ),
                                html.H4(size.sizeof_fmt(size_graph.total)),
                            ])
                        ], className='text-center stat-card'),
                        md=6,
                    ),
                    dbc.Col(
                        dbc.Card([
                            dbc.CardBody([
                                html.H6('Root Modules',
                                        className='text-muted'),
                                html.H4(str(len(size_graph.module_parsed))),
                                html.Small(
                                    f"({sum(len(s) for s in size_graph.module_parsed.values())} submodules)",
                                    className='text-muted',
                                ),
                            ])
                        ], className='text-center stat-card'),
                        md=6,
                    ),
                ], className='mb-3'),
                html.H6('Largest submodule sizes', className='mt-3'),
                dbc.ListGroup([
                    dbc.ListGroupItem([
                        html.Span(f"{module}{submodule}"),
                        dbc.Badge(s, color='info', className='float-end'),
                    ])
                    for module, submodule, s in largest_sizes
                ], className='mb-3'),
                switchable_graph_html(size_graph, 'size_graph'),
            ]),
        ], className='mb-4'),

        # Dependency Graph
        dbc.Card([
            dbc.CardHeader(html.H5('Dependency Graph', className='mb-0')),
            dbc.CardBody([
                html.P([
                    'Node count: ',
                    dbc.Badge(str(len(dep_graph.nodes())), color='secondary'),
                ]),
                dep_fig.to_html(include_plotlyjs=False, full_html=False),
            ]),
        ], className='mb-4'),
    ], className='py-4')

    body_html = component_to_html(component)
    full_html = (
        '<!DOCTYPE html>'
        '<html lang="en">'
        '<head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>Nuitka Compilation Report</title>'
        f'{BOOTSTRAP_CSS}'
        f'{CUSTOM_CSS}'
        '</head>'
        f'<body class="bg-light">{body_html}</body>'
        '</html>'
    )

    with open(export_filename, "w", encoding="utf-8") as f:
        f.write(minify_html_onepass.minify(
            full_html, minify_js=True, minify_css=True))
    return export_filename
