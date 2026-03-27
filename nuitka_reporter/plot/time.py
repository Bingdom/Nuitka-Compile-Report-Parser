import xml.etree.ElementTree as ET
from collections import defaultdict
from .plotter import Plotter


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


def module_parser(file_path: str):
    """
    Parses the XML file at the given file path and returns a tuple containing:
    - A dictionary mapping root modules to their submodules and optimization times.
    - The total optimization time of all modules.
    """
    # Dictionary to store optimization time per root module and its submodules
    module_times = defaultdict[str, defaultdict[str, float]](lambda: defaultdict(float))
    total_time = 0.0

    tree = ET.parse(file_path)
    root = tree.getroot()

    # Iterate over modules and sum optimization times
    for module in root.findall("module"):
        module_name = module.get("name", "Unknown")
        # Assume self if no parent
        modules = module_name.split(".")
        parent_module = modules[0]
        module_time = 0.0

        for opt_time in module.findall("optimization-time"):
            module_time += float(opt_time.get("time", 0.0))

        module_times[parent_module][module_name if len(
            modules) <= 1 else ".".join(modules[:-1])] += module_time
        total_time += module_time

    return module_times, total_time


def get_plotter(filename: str):
    return Plotter(filename, module_parser, time_fmt,
                   "Build Times by Root Module with Submodules",
                   "Build Time (seconds)",
                   "Root Module Name")
