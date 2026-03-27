import os
import ast
import networkx as nx
import plotly.graph_objects as go
from collections import defaultdict

# Function to extract imports from a Python file


def extract_imports(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=file_path)
        except SyntaxError:
            return []

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return imports

# Function to build an import dependency graph


def build_import_graph(directory):
    graph = nx.DiGraph()

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                module_name = os.path.relpath(
                    file_path, directory).replace(os.sep, ".").rstrip(".py")

                imports = extract_imports(file_path)
                for imp in imports:
                    graph.add_edge(module_name, imp)

    return graph

# Function to visualize the graph using Plotly


def plot_import_graph(graph):
    # Group modules by their root package
    grouped_nodes = defaultdict(list)
    for node in graph.nodes():
        root_module = node.split(".")[0]
        if root_module != node or root_module not in grouped_nodes:
            grouped_nodes[root_module].append(node)

    # Assign positions for better layout
    pos = {}
    x_offset = 0
    y_offset_step = -1

    for root, nodes in grouped_nodes.items():
        for i, node in enumerate(nodes):
            pos[node] = (x_offset, i * y_offset_step)
        x_offset += 3  # Space out root modules

    edge_x, edge_y = [], []
    for edge in graph.edges():
        if edge[0] in pos and edge[1] in pos:
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=1, color='#888'),
        hoverinfo='none',
        mode='lines'
    )

    node_x, node_y, text = [], [], []
    for node, (x, y) in pos.items():
        node_x.append(x)
        node_y.append(y)
        text.append(node)

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        marker=dict(size=10, color='blue'),
        text=text,
        textposition='top center',
        legend="legend",
    )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        showlegend=False, title="Python Import Dependency Graph (Grouped by Root Module)")

    return fig


# Define the project directory (modify as needed)
project_directory = "../GitHub/MyProject"
graph = build_import_graph(project_directory)
fig = plot_import_graph(graph)
