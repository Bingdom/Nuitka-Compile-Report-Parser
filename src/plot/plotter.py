from typing import Callable
import plotly.graph_objects as go
from _types import NumberLike


class Plotter():
    def __init__(self, file_path: str, module_parser: Callable[..., tuple[dict[str, dict[str, NumberLike]], NumberLike]], value_parser: Callable[[NumberLike], str], title: str, xaxis_title: str, yaxis_title: str):
        self.file_path = file_path

        self.module_parsed, self.total = module_parser(file_path)

        self.sorted_modules = sorted(self.module_parsed.items(),
                                     key=lambda x: sum(x[1].values()), reverse=True)[:20]

        # Prepare stacked bar chart data
        self.fig = go.Figure()
        for group_idx, (root_module, submodules) in enumerate(self.sorted_modules):
            group_name = root_module + \
                f" - Total: {value_parser(sum(submodules.values()))}"

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
                    name=f"{new_name} - {value_parser(time)}",
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
