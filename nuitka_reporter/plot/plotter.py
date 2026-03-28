from typing import Callable, Literal
from dataclasses import dataclass, field
import plotly.graph_objects as go
from nuitka_reporter._types import NumberLike
from collections import defaultdict

GraphType = Literal["treemap", "bar", "sunburst"]

CHART_HEIGHT = 800


@dataclass
class HierarchyData:
    """Pre-computed hierarchical data for treemap/sunburst charts."""
    ids: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
    parents: list[str] = field(default_factory=list)
    values: list[NumberLike] = field(default_factory=list)
    hover_text: list[str] = field(default_factory=list)
    formatted_values: list[str] = field(default_factory=list)


def _breakdown_hover(
    name: str,
    total: NumberLike,
    value_formatter: Callable[[NumberLike], str],
    leaf_breakdowns: dict[str, tuple[NumberLike, ...]] | None,
    breakdown_labels: tuple[str, ...],
    match_prefix: str,
) -> str:
    """Build hover text, listing each breakdown component then Total at the bottom."""
    if leaf_breakdowns is None:
        return f"{name}<br>{value_formatter(total)}"
    n = len(breakdown_labels)
    component_totals = [0.0] * n
    for k, v in leaf_breakdowns.items():
        if k == name or k.startswith(match_prefix):
            for i in range(n):
                component_totals[i] += v[i] if i < len(v) else 0.0
    lines = "".join(
        f"<br>{label}: {value_formatter(val)}"
        for label, val in zip(breakdown_labels, component_totals)
    )
    return f"{name}{lines}<br>Total: {value_formatter(total)}"


def build_hierarchy_data(
    sorted_modules: list[tuple[str, defaultdict[str, NumberLike]]],
    value_formatter: Callable[[NumberLike], str],
    leaf_breakdowns: dict[str, tuple[NumberLike, ...]] | None = None,
    breakdown_labels: tuple[str, ...] = ("Part 1", "Part 2"),
) -> HierarchyData:
    data = HierarchyData()

    for root_module, submodules in sorted_modules:
        root_total = sum(submodules.values())

        root_hover = _breakdown_hover(
            root_module, root_total, value_formatter,
            leaf_breakdowns, breakdown_labels, root_module + ".")

        data.ids.append(root_module)
        data.labels.append(root_module)
        data.parents.append("")
        data.values.append(root_total)
        data.hover_text.append(root_hover)
        data.formatted_values.append(value_formatter(root_total))

        # Build full hierarchy from nested module paths
        path_values: dict[str, NumberLike] = dict(submodules)
        all_paths: set[str] = set()

        for submodule in submodules:
            parts = submodule.split(".")
            for i in range(1, len(parts) + 1):
                all_paths.add(".".join(parts[:i]))

        # Compute totals (each node = own value + all descendants)
        path_totals: dict[str, NumberLike] = {}
        for path in all_paths:
            total = path_values.get(path, 0)
            prefix = path + "."
            for other_path, val in path_values.items():
                if other_path.startswith(prefix):
                    total += val
            path_totals[path] = total

        # Add child nodes sorted by depth then name (skip root, already added)
        for path in sorted(all_paths - {root_module}, key=lambda x: (x.count("."), x)):
            parts = path.split(".")
            parent_path = ".".join(parts[:-1])
            parent_id = f"{root_module}/{parent_path}" if parent_path != root_module else root_module
            node_id = f"{root_module}/{path}"

            total = path_totals[path]

            hover = _breakdown_hover(
                path, total, value_formatter,
                leaf_breakdowns, breakdown_labels, path + ".")

            data.ids.append(node_id)
            data.labels.append(parts[-1])
            data.parents.append(parent_id)
            data.values.append(total)
            data.hover_text.append(hover)
            data.formatted_values.append(value_formatter(total))

    return data


class Plotter():
    """
    A class that takes in a file path to a compile report, parses it using the provided `module_parser`, and generates a plotly figure with the values formatted with the provided `value_formatter`. \n

    In addition, provide titles for the plot and axes. \n

    Attributes:
        `file_path` is the path to the compile report file.
        `value_formatter`  is used to format the values for display in the plot.
        `total` is the total value for all modules.
        `sorted_modules`   is a list of modules sorted by their total values.
        `fig`  is the plotly figure generated based on the parsed data.
    """
    file_path: str
    module_parsed: defaultdict[str, defaultdict[str, NumberLike]]
    total: NumberLike
    sorted_modules: list[tuple[str, defaultdict[str, NumberLike]]]
    fig: go.Figure

    def __init__(self, file_path: str, module_parser: Callable[..., tuple], value_formatter: Callable[[NumberLike], str], title: str, xaxis_title: str, yaxis_title: str, breakdown_labels: tuple[str, str] | None = None):
        self.file_path = file_path
        self.value_formatter = value_formatter
        self.title = title
        self.xaxis_title = xaxis_title
        self.yaxis_title = yaxis_title

        result = module_parser(file_path)
        self.module_parsed, self.total = result[0], result[1]
        self._leaf_breakdowns = result[2] if len(result) > 2 else None
        self._breakdown_labels = breakdown_labels or ("Part 1", "Part 2")

        self.sorted_modules = sorted(self.module_parsed.items(),
                                     key=lambda x: sum(x[1].values()), reverse=True)[:20]

        self._hierarchy = build_hierarchy_data(
            self.sorted_modules, self.value_formatter,
            self._leaf_breakdowns, self._breakdown_labels)

        self.fig = self._build_treemap()

    def get_figure(self, graph_type: GraphType = "treemap") -> go.Figure:
        if graph_type == "bar":
            return self._build_bar()
        if graph_type == "sunburst":
            return self._build_sunburst()
        return self._build_treemap()

    def _build_treemap(self) -> go.Figure:
        h = self._hierarchy
        fig = go.Figure(go.Treemap(
            ids=h.ids,
            labels=h.labels,
            parents=h.parents,
            values=h.values,
            text=h.formatted_values,
            hovertext=h.hover_text,
            hoverinfo="text",
            branchvalues="total",
            textinfo="label+text",
        ))

        fig.update_layout(
            title=self.title,
            margin=dict(t=50, l=10, r=10, b=10),
            height=CHART_HEIGHT,
        )
        return fig

    def _build_sunburst(self) -> go.Figure:
        h = self._hierarchy
        fig = go.Figure(go.Sunburst(
            ids=h.ids,
            labels=h.labels,
            parents=h.parents,
            values=h.values,
            text=h.formatted_values,
            hovertext=h.hover_text,
            hoverinfo="text",
            branchvalues="total",
            textinfo="label+text",
        ))

        fig.update_layout(
            title=self.title,
            margin=dict(t=50, l=10, r=10, b=10),
            height=CHART_HEIGHT,
        )
        return fig

    def _build_bar(self) -> go.Figure:
        fig = go.Figure()

        for group_idx, (root_module, submodules) in enumerate(self.sorted_modules):
            group_name = root_module + \
                f" - Total: {self.value_formatter(sum(submodules.values()))}"

            # Aggregate submodules to depth 2 (one level below root)
            # e.g. sqlalchemy.orm.session + sqlalchemy.orm.mapper -> sqlalchemy.orm
            aggregated: defaultdict[str, NumberLike] = defaultdict(int)
            for submodule, value in submodules.items():
                modules = submodule.split(".")
                key = ".".join(modules[:2]) if len(modules) > 1 else modules[0]
                aggregated[key] += value

            sorted_submodules = sorted(
                aggregated.items(), key=lambda x: x[1], reverse=True)
            submodule_count = len(sorted_submodules)

            for sub_idx, (submodule, value) in enumerate(sorted_submodules):
                legendrank = group_idx * 1000 + (submodule_count - sub_idx)

                modules = submodule.split(".")
                display_name = ".".join(modules[1:]) if len(
                    modules) > 1 else modules[0]

                fig.add_trace(go.Bar(
                    y=[root_module],
                    x=[value],
                    name=f"{display_name} - {self.value_formatter(value)}",
                    orientation='h',
                    hoverinfo="name",
                    legendgroup=group_name,
                    legendgrouptitle_text=group_name,
                    marker=dict(line=dict(width=1)),
                    legendrank=legendrank,
                ))

        fig.update_layout(
            barmode='stack',
            title=self.title,
            xaxis_title=self.xaxis_title,
            yaxis_title=self.yaxis_title,
            yaxis=dict(categoryorder='total ascending'),
            legend_title="Modules",
            height=CHART_HEIGHT,
        )
        return fig
