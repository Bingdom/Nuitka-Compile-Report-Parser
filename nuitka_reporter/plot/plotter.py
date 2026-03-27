from typing import Callable, Any
import plotly.graph_objects as go
from nuitka_reporter._types import NumberLike
from collections import defaultdict


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

    def __init__(self, file_path: str, module_parser: Callable[[str], tuple[defaultdict[str, defaultdict[str, NumberLike]], NumberLike]], value_formatter: Callable[[NumberLike], str], title: str, xaxis_title: str, yaxis_title: str):
        self.file_path = file_path

        self.module_parsed, self.total = module_parser(file_path)

        self.sorted_modules = sorted(self.module_parsed.items(),
                                     key=lambda x: sum(x[1].values()), reverse=True)[:20]

        # Prepare stacked bar chart data
        self.fig = go.Figure()
        for group_idx, (root_module, submodules) in enumerate(self.sorted_modules):
            group_name = root_module + \
                f" - Total: {value_formatter(sum(submodules.values()))}"

            # Sort submodules and get their count for ranking
            sorted_submodules = sorted(
                submodules.items(), key=lambda x: x[1], reverse=True)
            submodule_count = len(sorted_submodules)

            for sub_idx, (submodule, time) in enumerate(sorted_submodules):
                # Calculate rank: group_idx * 1000 ensures groups stay together
                # submodule_count - sub_idx reverses the order within the group
                legendrank = group_idx * 1000 + (submodule_count - sub_idx)

                modules = submodule.split(".")
                new_name = ".".join(modules[1:]) if len(
                    modules) > 1 else modules[0]

                self.fig.add_trace(go.Bar(
                    y=[root_module],
                    x=[time],
                    name=f"{new_name} - {value_formatter(time)}",
                    orientation='h',
                    hoverinfo="name",
                    legendgroup=group_name,
                    legendgrouptitle_text=group_name,
                    marker=dict(line=dict(width=1)),
                    legendrank=legendrank
                ))

        # Formatting
        self.fig.update_layout(
            barmode='stack',
            title=title,
            xaxis_title=xaxis_title,
            yaxis_title=yaxis_title,
            yaxis=dict(categoryorder='total ascending'),
            legend_title="Modules",
            # hovermode="y unified",
        )
