import xml.etree.ElementTree as ET
from collections import defaultdict
from .plotter import Plotter


def time_fmt(time: float):
    if time < 1:
        return f"{int(time*1000)}ms"
    if time < 60:
        return f"{int(time)}s"
    return f"{int(time/60)}:{int(time % 60)}"


def module_parser(file_path: str):
    # Dictionary to store optimization time per root module and its submodules
    module_times = defaultdict(lambda: defaultdict(float))
    total_time = 0.0

    tree = ET.parse(file_path)
    root = tree.getroot()

    # Iterate over modules and sum optimization times
    for module in root.findall("module"):
        module_name = module.get("name", "Unknown")
        # Assume self if no
        modules = module_name.split(".")
        parent_module = modules[0]
        module_time = 0.0

        for opt_time in module.findall("optimization-time"):
            module_time += float(opt_time.get("time", 0.0))

        module_times[parent_module][module_name if len(
            modules) <= 1 else ".".join(modules[:-1])] += module_time
        total_time += module_time

    return module_times, total_time


plot = Plotter("compilation-report.xml", module_parser, time_fmt,
               "Build Times by Root Module with Submodules",
               "Build Time (seconds)",
               "Root Module Name")


# # Prepare stacked bar chart data
# fig = go.Figure()
# for group_idx, (root_module, submodules) in enumerate(sorted_modules):
#     group_name = root_module + \
#         f" - Total: {time_fmt(sum(submodules.values()))}"

#     # Sort submodules and get their count for ranking
#     sorted_submodules = sorted(
#         submodules.items(), key=lambda x: x[1], reverse=True)
#     submodule_count = len(sorted_submodules)

#     for sub_idx, (submodule, time) in enumerate(sorted_submodules):
#         module_path = submodule.split(".")

#         # Calculate rank: group_idx * 1000 ensures groups stay together
#         # submodule_count - sub_idx reverses the order within the group
#         legendrank = group_idx * 1000 + (submodule_count - sub_idx)

#         new_name = ".".join(submodule.split(".")[1:])

#         fig.add_trace(go.Bar(
#             y=[root_module],
#             x=[time],
#             name=f"{new_name} - {time_fmt(time)}",
#             orientation='h',
#             hoverinfo="name",
#             legendgroup=group_name,
#             legendgrouptitle_text=group_name,
#             marker=dict(line=dict(width=1)),
#             legendrank=legendrank
#         ))

# # Formatting
# fig.update_layout(
#     barmode='stack',
#     title="Build Times by Root Module with Submodules",
#     xaxis_title="Build Time (seconds)",
#     yaxis_title="Root Module Name",
#     yaxis=dict(categoryorder='total ascending'),
#     legend_title="Modules",
#     # hovermode="y unified",
# )
