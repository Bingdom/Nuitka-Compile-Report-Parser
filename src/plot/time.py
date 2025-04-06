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


def get_plotter(filename: str):
    return Plotter(filename, module_parser, time_fmt,
                   "Build Times by Root Module with Submodules",
                   "Build Time (seconds)",
                   "Root Module Name")
