import xml.etree.ElementTree as ET
from collections import defaultdict
from .plotter import Plotter
from _types import NumberLike


def sizeof_fmt(num: NumberLike, suffix="B"):
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


def module_parser(file_path: str):
    tree = ET.parse(file_path)
    root = tree.getroot()
    # Dictionary to store optimization time per root module and its submodules
    module_sizes: defaultdict[str, defaultdict[str, int]
                              ] = defaultdict(lambda: defaultdict(int))
    total_size = 0

    # Iterate over modules and sum optimization times
    for data_composer in root.findall("data_composer"):
        for module in data_composer.findall("module_data"):
            module_name = module.get("blob_name", "Unknown")
            if module_name.split(".")[0] == "":
                module_name = module.get("filename", "Unknown")

            modules = module_name.split(".")

            # Assume self if no parent
            parent_module = modules[0]
            module_size = int(module.get("blob_size", 0))

            module_sizes[parent_module][module_name if len(
                modules) <= 1 else ".".join(modules[:-1])] += module_size
            total_size += module_size

    for data_file in root.findall("data_file"):
        module_sizes["Included files"][data_file.get("name", "Unknown")] = int(
            data_file.get("size", 0))

    return module_sizes, total_size


def get_plotter(filename: str):
    return Plotter(filename, module_parser, sizeof_fmt,
                   "Bytecode build size by Root Module with Submodules", "Bytecode Build Size (bytes)", "Root Module Name")

# # Sort root modules by total time taken
# sorted_modules = sorted(module_sizes.items(),
#                         key=lambda x: sum(x[1].values()), reverse=True)[:20]

# # Prepare stacked bar chart data
# fig = go.Figure()
# for group_idx, (root_module, submodules) in enumerate(sorted_modules):
#     group_name = root_module + \
#         f" - Total: {sizeof_fmt(sum(submodules.values()))}"

#     # Sort submodules and get their count for ranking
#     sorted_submodules = sorted(
#         submodules.items(), key=lambda x: x[1], reverse=True)
#     submodule_count = len(sorted_submodules)

#     for sub_idx, (submodule, size) in enumerate(sorted_submodules):
#         module_path = submodule.split(".")

#         # Calculate rank: group_idx * 1000 ensures groups stay together
#         # submodule_count - sub_idx reverses the order within the group
#         legendrank = group_idx * 1000 + (submodule_count - sub_idx)

#         new_name = ".".join(submodule.split(".")[1:])

#         fig.add_trace(go.Bar(
#             y=[root_module],
#             x=[size],
#             name=f"{new_name} - {sizeof_fmt(size)}",
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
#     title="Bytecode build size by Root Module with Submodules",
#     xaxis_title="Bytecode Build Size (bytes)",
#     yaxis_title="Root Module Name",
#     yaxis=dict(categoryorder='total ascending'),
#     legend_title="Modules",
#     # hovermode="y unified",
# )
