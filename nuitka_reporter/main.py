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
from .helpers import get_command_line, get_data_files, get_distributions, get_included, get_nuitka_version, get_plugin_options, get_module_stats, has_nuitka_version_upgraded_report
from typing import NamedTuple

BOOTSTRAP_CSS = '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" crossorigin="anonymous">'

CUSTOM_CSS = """<style>
.card { box-shadow: 0 .125rem .25rem rgba(0,0,0,.075); }
.stat-card .card-body { padding: 1rem; }
.stat-card h6 { font-size: .85rem; margin-bottom: .25rem; }
.stat-card h4 { margin-bottom: 0; }
.accordion-button:not(.collapsed) { background-color: #e7f1ff; color: #0c63e4; }
.accordion-button:focus { box-shadow: 0 0 0 0.15rem rgba(13,110,253,.25); }
.accordion-body > .table:last-child { margin-bottom: 0; }
.expand-controls .btn { font-size: .85rem; }
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
function expandAll() {
    document.querySelectorAll('#reportAccordion .accordion-collapse').forEach(function(el) {
        el.classList.add('show');
    });
    document.querySelectorAll('#reportAccordion .accordion-button').forEach(function(el) {
        el.classList.remove('collapsed');
        el.setAttribute('aria-expanded', 'true');
    });
    resizeAllPlots();
}
function collapseAll() {
    document.querySelectorAll('#reportAccordion .accordion-collapse').forEach(function(el) {
        el.classList.remove('show');
    });
    document.querySelectorAll('#reportAccordion .accordion-button').forEach(function(el) {
        el.classList.add('collapsed');
        el.setAttribute('aria-expanded', 'false');
    });
}
function resizeAllPlots() {
    document.querySelectorAll('.plotly-graph-div').forEach(function(el) {
        Plotly.Plots.resize(el);
    });
}
document.addEventListener('shown.bs.collapse', function() { resizeAllPlots(); });
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
    value: NumberLike


def get_largest_submodule(sorted_modules: list[tuple[str, defaultdict[str, NumberLike]]]):
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
            root_module, biggest_module, biggest_value))

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


_accordion_counter = 0


def _accordion_item(title: str, body_html: str, expanded: bool = False) -> str:
    """Build a single Bootstrap 5 accordion item as raw HTML."""
    global _accordion_counter
    _accordion_counter += 1
    item_id = f"acc-item-{_accordion_counter}"
    show = " show" if expanded else ""
    collapsed = "" if expanded else " collapsed"
    aria = "true" if expanded else "false"
    return (
        f'<div class="accordion-item">'
        f'<h2 class="accordion-header">'
        f'<button class="accordion-button{collapsed}" type="button" '
        f'data-bs-toggle="collapse" data-bs-target="#{item_id}" '
        f'aria-expanded="{aria}" aria-controls="{item_id}">'
        f'{html_escape(title)}</button></h2>'
        f'<div id="{item_id}" class="accordion-collapse collapse{show}" '
        f'data-bs-parent="#reportAccordion">'
        f'<div class="accordion-body">{body_html}</div>'
        f'</div></div>'
    )


def get_included_table(filename: str, element_name: str):
    return html.Div(dbc.Table([
        html.Thead(html.Tr([
            html.Th('Name'),
            html.Th('Src Path'),
            html.Th('Dest Path'),
            html.Th('Package'),
            html.Th('Ignored'),
            html.Th('Reason'),
        ])),
        html.Tbody([
            html.Tr([
                html.Td(name),
                html.Td(html.Code(src)),
                html.Td(html.Code(dest)),
                html.Td(pkg or html.Span(
                    '—', className='text-muted')),
                html.Td(get_colour_badge(ignored, ignored == 'yes')),
                html.Td(reason, className='text-nowrap'),
            ]) for name, src, dest, pkg, ignored, reason in get_included(filename, element_name)
        ]) if get_included(filename, element_name) else html.Tbody(html.Tr(html.Td('None', colSpan=6, className='text-muted text-center'))),
    ], striped=True, hover=True, bordered=True), className='table-responsive')


def get_colour_badge(text: str, truth: bool):
    return dbc.Badge(
        text,
        color='success' if truth else 'secondary'
    )


def to_html(filename: str, export_filename: str = os.path.join(".", "index.html")):
    """Input a compile report to output a html report file with visualizations and summaries of the build time, build size, and dependency graph. The HTML file is saved to the specified export filename (or default, index.html next to the specified compile report)."""
    global _accordion_counter
    _accordion_counter = 0

    size_graph = size.get_plotter(filename)
    time_graph = time.get_plotter(filename)
    dep_fig, dep_graph = dependency_from_report.get_fig(filename)

    longest_times = get_largest_submodule(
        time_graph.sorted_modules)
    largest_sizes = get_largest_submodule(
        size_graph.sorted_modules)

    c_gen_time = sum(conv for module, (opt1, opt2, conv) in time_graph._leaf_breakdowns.items(
    )) if time_graph._leaf_breakdowns else 0

    # --- Build each section's inner HTML via Dash components ---

    # Command line
    cmd_html = component_to_html(
        dbc.ListGroup([
            dbc.ListGroupItem(html.Code(command))
            for command in get_command_line(filename)
        ])
    )

    # Plugin options & Distributions (side by side)
    plugins_distros_html = component_to_html(
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
                                        get_colour_badge(
                                            enabled, enabled == 'yes')
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
        ])
    )

    # Included Extensions & DLLs
    ext_dll_html = component_to_html(html.Div([
        html.H6('Included Extensions', className='mt-0 mb-2'),
        get_included_table(filename, "included_extension"),
        html.H6('Included DLLs', className='mt-4 mb-2'),
        get_included_table(filename, "included_dll"),
        html.H6('Excluded DLLs', className='mt-4 mb-2'),
        get_included_table(filename, "excluded_dll"),
    ]))

    # Data Files
    data_files = get_data_files(filename)
    data_files_html = component_to_html(
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
                ]) for name, source, sz, reason, tags in data_files
            ]) if data_files else html.Tbody(
                html.Tr(html.Td('None', colSpan=5,
                        className='text-muted text-center'))
            ),
        ], striped=True, hover=True, bordered=True)
    )

    # Transpilation Time
    time_html = component_to_html(html.Div([
        dbc.Row([
            dbc.Col(
                dbc.Card([
                    dbc.CardBody([
                        html.H6('Optimization time ', className='text-muted'),
                        html.H4(str(
                            time.time_fmt(sum(opt1 + opt2 for module, (opt1, opt2, conv) in time_graph._leaf_breakdowns.items()))) if time_graph._leaf_breakdowns else 'N/A'),
                    ])
                ], className='text-center stat-card'),
                md=4,
            ),
            dbc.Col(
                dbc.Card([
                    dbc.CardBody([
                        html.H6('C generation time ', className='text-muted'),
                        html.H4(str(
                            time.time_fmt(c_gen_time) if time_graph._leaf_breakdowns else 'N/A'),
                            className='text-warning' if c_gen_time == 0 else None
                        ),
                    ])
                ], className='text-center stat-card'),
                md=4,
            ),
            dbc.Col(
                dbc.Card([
                    dbc.CardBody([
                        html.H6('Total time', className='text-muted'),
                        html.H4(time.time_fmt(time_graph.total)),
                    ])
                ], className='text-center stat-card'),
                md=4,
            ),
        ], className='mb-3'),
        dbc.Alert(
            'Upgrade Nuitka to see c code generation times', color='warning') if c_gen_time == 0 else None,
        html.H6('Largest submodule transpilation times',
                className='mt-3'),
        dbc.ListGroup([
            dbc.ListGroupItem([
                html.Span(f"{module}{submodule}"),
                time.get_badge(t),
            ])
            for module, submodule, t in longest_times
        ], className='mb-3'),
    ])) + switchable_graph_html(time_graph, 'time_graph', include_plotlyjs=True)

    total_modules, total_files = get_module_stats(filename)

    # Build Size
    size_html = component_to_html(html.Div([
        dbc.Row([
            dbc.Col(
                dbc.Card([
                    dbc.CardBody([
                         html.H6('Modules',
                                 className='text-muted'),
                         html.H4(str(total_modules)),
                         ])
                ], className='text-center stat-card'),
                md=4,
            ),
            dbc.Col(
                dbc.Card([
                    dbc.CardBody([
                         html.H6('Files',
                                 className='text-muted'),
                         html.H4(str(total_files)),
                         ])
                ], className='text-center stat-card'),
                md=4,
            ),
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
                md=4,
            ),
        ], className='mb-3'),
        html.H6('Largest submodule sizes', className='mt-3'),
        dbc.ListGroup([
            dbc.ListGroupItem([
                html.Span(f"{module}{submodule}"),
                size.get_badge(s),
            ])
            for module, submodule, s in largest_sizes
        ], className='mb-3'),
    ])) + switchable_graph_html(size_graph, 'size_graph')

    # Dependency Graph
    dep_html = component_to_html(html.P([
        'Node count: ',
        dbc.Badge(str(len(dep_graph.nodes())), color='secondary'),
    ])) + dep_fig.to_html(include_plotlyjs=False, full_html=False)

    # --- Assemble accordion ---
    accordion_items = ''.join([
        _accordion_item('Command Line', cmd_html, expanded=True),
        _accordion_item('Plugin Options & Distributions',
                        plugins_distros_html),
        _accordion_item('Included Extensions & DLLs', ext_dll_html),
        _accordion_item('Data Files', data_files_html),
        _accordion_item('Transpilation Time', time_html, expanded=True),
        _accordion_item(
            f'Build Size ({size.get_size_type(filename)})', size_html, expanded=True),
        _accordion_item('Dependency Graph', dep_html),
    ])

    body_html = (
        '<div class="container py-4">'
        '<div class="d-flex justify-content-between align-items-center mb-4">'
        '<h2 class="mb-0">Nuitka Compilation Report</h2>'
        '<div class="expand-controls btn-group">'
        '<button class="btn btn-outline-secondary" onclick="expandAll()">'
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-arrows-expand me-1" viewBox="0 0 16 16">'
        '<path fill-rule="evenodd" d="M1 8a.5.5 0 0 1 .5-.5h13a.5.5 0 0 1 0 1h-13A.5.5 0 0 1 1 8m7-8a.5.5 0 0 1 .5.5v3.793l1.146-1.147a.5.5 0 0 1 .708.708l-2 2a.5.5 0 0 1-.708 0l-2-2a.5.5 0 1 1 .708-.708L7.5 4.293V.5A.5.5 0 0 1 8 0m-.5 11.707-1.146 1.147a.5.5 0 0 1-.708-.708l2-2a.5.5 0 0 1 .708 0l2 2a.5.5 0 0 1-.708.708L8.5 11.707V15.5a.5.5 0 0 1-1 0z"/>'
        '</svg>Expand All</button>'
        '<button class="btn btn-outline-secondary" onclick="collapseAll()">'
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-arrows-collapse me-1" viewBox="0 0 16 16">'
        '<path fill-rule="evenodd" d="M1 8a.5.5 0 0 1 .5-.5h13a.5.5 0 0 1 0 1h-13A.5.5 0 0 1 1 8m7-8a.5.5 0 0 1 .5.5v3.793l1.146-1.147a.5.5 0 0 1 .708.708l-2 2a.5.5 0 0 1-.708 0l-2-2a.5.5 0 1 1 .708-.708L7.5 4.293V.5A.5.5 0 0 1 8 0m-.5 11.707-1.146 1.147a.5.5 0 0 1-.708-.708l2-2a.5.5 0 0 1 .708 0l2 2a.5.5 0 0 1-.708.708L8.5 11.707V15.5a.5.5 0 0 1-1 0z"/>'
        '</svg>Collapse All</button>'
        '</div></div>'
        f'<div class="accordion" id="reportAccordion">{accordion_items}</div>'
        '</div>'
    )

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
        '<body class="bg-light">'
        f'{body_html}'
        '<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js" crossorigin="anonymous"></script>'
        f'{SWITCH_GRAPH_JS}'
        '</body>'
        '</html>'
    )

    with open(export_filename, "w", encoding="utf-8") as f:
        f.write(minify_html_onepass.minify(
            full_html, minify_js=True, minify_css=True))
        return export_filename
