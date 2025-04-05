import xml.etree.ElementTree as ET
from collections import defaultdict
from _types import NumberLike


def sizeof_fmt(num: NumberLike, suffix="B"):
    for unit in ("", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"):
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


def get_plugins(file_path: str):
    tree = ET.parse(file_path)
    root = tree.getroot()

    to_return: list[tuple[str, str]] = []

    # Iterate over modules and sum optimization times
    for plugins in root.findall("plugins"):
        for plugin in plugins.findall("plugin"):
            to_return.append((plugin.get("name"), plugin.get("user_enabled")))

    return to_return

def get_command_line(file_path: str):
    tree = ET.parse(file_path)
    root = tree.getroot()

    to_return: list[tuple[str, str]] = []

    # Iterate over modules and sum optimization times
    for plugins in root.findall("command_line"):
        for plugin in plugins.findall("option"):
            to_return.append(plugin.get("value"))
    
    return to_return