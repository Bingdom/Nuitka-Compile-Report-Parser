import xml.etree.ElementTree as ET
import networkx as nx
import plotly.graph_objects as go
from ..helpers import get_parsed_file, get_module_metadata


def parse_name(name: str):
    return name


def allowed_module(module: ET.Element):
    return (module.get("kind") == "CompiledPythonModule" and module.get("source_path", '').startswith("${cwd}") and not module.get("name", "").endswith("-preLoad"))


def get_fig(filename: str):
    root = get_parsed_file(filename)

    # Create a directed graph
    G = nx.DiGraph()

    # Parse module dependencies
    for module in root.findall("module"):
        if allowed_module(module):
            # print("Adding module:", module.get("name"), module.get("usage"),
            #       module.get("kind"), module.get("source_path"))
            module_name = parse_name(module.get("name"))

            G.add_node(module_name)

    for module in root.findall("module"):
        if allowed_module(module):
            module_name = parse_name(module.get("name"))
            for module_usages in module.findall("module_usages"):
                for module_usage in module_usages.findall("module_usage"):
                    dep_name = parse_name(module_usage.get("name", ''))
                    if dep_name in G.nodes():
                        # print(dep_name, '=>', module_name)
                        G.add_edge(dep_name, module_name)

    # Generate node positions using NetworkX layout
    pos = nx.spring_layout(G, seed=42)

    # Extract edges for plotting
    edge_x = []
    edge_y = []
    annotations = []
    for src, dst in G.edges():
        x0, y0 = pos[src]
        x1, y1 = pos[dst]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

        # Add directional arrow annotation
        annotations.append(
            dict(
                ax=x0, ay=y0,
                x=x1, y=y1,
                xref="x", yref="y",
                axref="x", ayref="y",
                showarrow=True,
                arrowhead=2,
                arrowsize=2,
                arrowwidth=1,
                arrowcolor="grey"
            )
        )

    # Create edge traces
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=1, color='gray'),
        hoverinfo='none',
        mode='lines'
    )

    # Create node traces
    node_x = []
    node_y = []
    node_text = []
    node_hover = []
    metadata = get_module_metadata(filename)
    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_text.append(node)
        hover = node
        meta = metadata.get(node, {})
        if "kind" in meta:
            hover += f"<br>Kind: {meta['kind']}"
        if "usage" in meta:
            hover += f"<br>Usage: {meta['usage']}"
        if "reason" in meta:
            hover += f"<br>Reason: {meta['reason']}"
        if "source_path" in meta:
            hover += f"<br>Source: {meta['source_path']}"
        node_hover.append(hover)

    node_adjacencies = []
    for node, adjacencies in enumerate(G.adjacency()):
        node_adjacencies.append(len(adjacencies[1]))
        node_text[node] += ': '+str(len(adjacencies[1]))
        node_hover[
            node] += f"<br><br>Used by {len(adjacencies[1])} other module(s)"

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        text=node_text,
        textposition='top center',
        marker=dict(
            size=15,
            colorscale='YlGnBu',
            showscale=True,
            color=node_adjacencies,
            line=dict(width=2, color='black')
        ),
        hoverinfo='text',
        hovertext=node_hover,
    )

    # Create figure
    fig = go.Figure(data=[node_trace  # ,edge_trace # using annotations now
                          ])
    fig.update_layout(
        title="Dependency Graph from Nuitka Compilation Report",
        showlegend=False,
        hovermode='closest',
        margin=dict(b=0, l=0, r=0, t=40),
        annotations=annotations
    )

    return fig, G
