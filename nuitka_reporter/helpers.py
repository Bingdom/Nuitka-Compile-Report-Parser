import xml.etree.ElementTree as ET


def get_plugin_options(file_path: str):
    """
    Returns a list of tuples containing plugin names and their user-enabled status.
    """
    tree = ET.parse(file_path)
    root = tree.getroot()

    to_return: list[tuple[str, str]] = []

    # Iterate over modules and sum optimization times
    for plugins in root.findall("plugins"):
        for plugin in plugins.findall("plugin"):
            to_return.append((
                plugin.get("name", "unknown"),
                plugin.get("user_enabled", "unknown")
            ))

    return to_return


def get_command_line(file_path: str):
    """
    Returns a list of command line options used on Nuitka.
    """
    tree = ET.parse(file_path)
    root = tree.getroot()

    to_return: list[str] = []

    # Iterate over modules and sum optimization times
    for plugins in root.findall("command_line"):
        for plugin in plugins.findall("option"):
            to_return.append(plugin.get("value", "unknown"))

    return to_return
