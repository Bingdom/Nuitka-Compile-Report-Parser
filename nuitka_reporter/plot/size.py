import xml.etree.ElementTree as ET
from collections import defaultdict
from .plotter import Plotter
from .._types import NumberLike
from ..helpers import has_nuitka_version_upgraded_report, get_parsed_file, get_nuitka_version, resolve_module_name, build_module_name_map
import dash_bootstrap_components as dbc


def sizeof_fmt(bytes_count: int | float):
    """
    Returns a human readable string representation of bytes.
    Uses binary prefixes (base-1024) by default.
    """
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB"):
        if abs(bytes_count) < 1024.0:
            return f"{bytes_count:3.1f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.1f}YiB"


def get_badge(size_bytes: NumberLike):
    if size_bytes < 1024 ** 2:  # < 1 MiB
        color = 'success'
    elif size_bytes < 10 * 1024 ** 2:  # < 10 MiB
        color = 'warning'
    else:
        color = 'danger'

    return dbc.Badge(
        sizeof_fmt(size_bytes),
        color=color,
        className='float-end'
    )


def module_blob_size(root: ET.Element):
    """
    Returns the size of the blob for a given module element. (Nuitka <v4.1)
    If the blob size is not available, it falls back to 0.
    """
    module_sizes = defaultdict[str, defaultdict[str, NumberLike]](
        lambda: defaultdict(int))
    total_size = 0

    # Iterate over modules and sum sizes
    for data_composer in root.findall("data_composer"):
        name_map = build_module_name_map(root)
        for module in data_composer.findall("module_data"):
            module_name = module.get("blob_name", "Unknown")
            if module_name.split(".")[0] == "":
                module_name = module.get("filename", "Unknown")
            module_name = name_map.get(module_name, module_name)

            modules = module_name.split(".")

            # Assume self if no parent
            parent_module = modules[0]
            module_size = int(module.get("blob_size", 0))

            module_sizes[parent_module][module_name] += module_size
            total_size += module_size

    for data_file in root.findall("data_file"):
        module_sizes["Included files"][data_file.get("name", "Unknown")] = int(
            data_file.get("size", 0))

    return module_sizes, total_size


def module_object_file_size(root: ET.Element):
    """
    Returns the size of the object file for a given module element. (Nuitka >=v4.1)
    If the object file size is not available, it falls back to 0.
    """
    module_sizes = defaultdict[str, defaultdict[str, NumberLike]](
        lambda: defaultdict(int))
    total_size = 0

    # Iterate over modules and sum sizes
    for module in root.findall("module"):
        for c_comp_res in module.findall("c-compilation-resources"):
            for object_size in c_comp_res.findall("object-file"):
                original = module.get("name", "Unknown")
                source_path = module.get("source_path", "")
                module_name = resolve_module_name(original, source_path)
                if module_name.split(".")[0] == "":
                    module_name = module.get("filename", "Unknown")

                modules = module_name.split(".")

                # Assume self if no parent
                parent_module = modules[0]
                module_size = int(object_size.get("size", 0))

                module_sizes[parent_module][module_name] += module_size
                total_size += module_size

    for data_file in root.findall("data_file"):
        module_sizes["Included files"][data_file.get("name", "Unknown")] = int(
            data_file.get("size", 0))

    return module_sizes, total_size


def get_size_type(file_path: str):
    """
    Returns the type of size information available in the report. It checks for the presence of object file size information (Nuitka >=v4.1) and returns "object file" if available. Otherwise, it returns "constants" (Nuitka <v4.1).
    """
    if has_nuitka_version_upgraded_report(get_nuitka_version(file_path)):
        return "object file"

    return "constants"


def module_parser(file_path: str):
    """
    Parses the XML file at the given file path and returns a tuple containing:
    - A dictionary mapping root modules to their submodules and sizes.
      Each submodule key is the full module path (e.g. "sqlalchemy.orm.session").
    - The total size of all modules.
    """
    root = get_parsed_file(file_path)

    if has_nuitka_version_upgraded_report(get_nuitka_version(file_path)):
        return module_object_file_size(root)

    return module_blob_size(root)


def get_plotter(filename: str):
    """
    Returns a Plotter instance that analyzes the bytecode build size by root module and its submodules. The values in the plot are formatted using the `sizeof_fmt` function.
    """
    return Plotter(filename, module_parser, sizeof_fmt,
                   f"{get_size_type(filename).capitalize()} build size + included files", f"{get_size_type(filename).capitalize()} Build Size (bytes)", "Root Module Name")

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
