import xml.etree.ElementTree as ET
from collections import defaultdict
from .plotter import Plotter
from ..helpers import get_parsed_file
import dash_bootstrap_components as dbc


def time_fmt(seconds: float):
    """
    Formats time in a human readable format. If time is less than 1 second, it is formatted in milliseconds. If time is less than 60 seconds, it is formatted in seconds. Otherwise, it is formatted in minutes and seconds.
    """
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    elif seconds < 60:
        return f"{seconds:.2f}s"
    else:
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds:.1f}s"
    
def get_badge(seconds: float):
    if seconds < 1:
        color = 'success'
    elif seconds < 5:
        color = 'warning'
    else:
        color = 'danger'

    return dbc.Badge(
        time_fmt(seconds),
        color=color,
        className='float-end'
    )


def module_parser(file_path: str):
    """
    Parses the XML file at the given file path and returns a tuple containing:
    - A dictionary mapping root modules to their submodules and optimization times.
      Each submodule key is the full module path (e.g. "sqlalchemy.orm.session").
    - The total optimization time of all modules.
    - A dict mapping each module name to a
      (opt_pass1, opt_pass2, code_gen_time) breakdown tuple.
    """
    # Dictionary to store optimization time per root module and its submodules
    module_times = defaultdict[str, defaultdict[str, float]](
        lambda: defaultdict(float))
    opt_pass1_times: dict[str, float] = {}
    opt_pass2_times: dict[str, float] = {}
    code_gen_times: dict[str, float] = {}
    total_time = 0.0

    root = get_parsed_file(file_path)

    # Iterate over modules and sum optimization times
    for module in root.findall("module"):
        module_name = module.get("name", "Unknown")
        # Assume self if no parent
        modules = module_name.split(".")
        parent_module = modules[0]
        opt_pass1 = 0.0
        opt_pass2 = 0.0
        code_gen_time = 0.0

        for o in module.findall("optimization-time"):
            if o.get("pass") == "2":
                opt_pass2 += float(o.get("time", 0.0))
            else:
                opt_pass1 += float(o.get("time", 0.0))

        for c in module.findall("code-generation-time"):
            code_gen_time += float(c.get("time", 0.0))

        module_time = opt_pass1 + opt_pass2 + code_gen_time
        module_times[parent_module][module_name] += module_time
        total_time += module_time
        opt_pass1_times[module_name] = opt_pass1_times.get(
            module_name, 0.0) + opt_pass1
        opt_pass2_times[module_name] = opt_pass2_times.get(
            module_name, 0.0) + opt_pass2
        code_gen_times[module_name] = code_gen_times.get(
            module_name, 0.0) + code_gen_time

    all_names = set(opt_pass1_times) | set(
        opt_pass2_times) | set(code_gen_times)
    leaf_breakdowns = {
        name: (
            opt_pass1_times.get(name, 0.0),
            opt_pass2_times.get(name, 0.0),
            code_gen_times.get(name, 0.0),
        )
        for name in all_names
    }

    return module_times, total_time, leaf_breakdowns


def get_plotter(filename: str):
    return Plotter(filename, module_parser, time_fmt,
                   "Transpilation Times by Root Module with Submodules",
                   "Transpilation Time (seconds)",
                   "Root Module Name",
                   breakdown_labels=("Opt Pass 1", "Opt Pass 2", "Code Gen"))
