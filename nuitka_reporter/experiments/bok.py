import xml.etree.ElementTree as ET
from collections import defaultdict
from bokeh.plotting import figure, show
from bokeh.models import HoverTool, ColumnDataSource
from bokeh.io import output_file

# Load and parse the XML file
file_path = "compilation-report.xml"
tree = ET.parse(file_path)
root = tree.getroot()

# Dictionary to store optimization time per root module and its submodules
module_times = defaultdict(lambda: defaultdict(float))

# Iterate over modules and sum optimization times
for module in root.findall("module"):
    module_name = module.get("name", "Unknown")
    # Assume self if no parent
    parent_module = module.get("parent", module_name)
    total_time = 0.0

    for opt_time in module.findall("optimization-time"):
        total_time += float(opt_time.get("time", 0.0))

    module_times[parent_module][module_name] += total_time

# Sort root modules by total time taken and limit to top 20
sorted_modules = sorted(module_times.items(), key=lambda x: sum(
    x[1].values()), reverse=True)[:20]

# Prepare Bokeh stacked bar chart data
output_file("build_times.html")
p = figure(y_range=[m[0] for m in sorted_modules], x_axis_label="Build Time (seconds)",
           title="Top 20 Build Times by Root Module with Submodules", tools="pan,wheel_zoom,box_zoom,reset,save")
p.xgrid.grid_line_color = None

# Colors for submodules
colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
          "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]

# Prepare data for stacking
stacked_data = defaultdict(lambda: {"y": [], "x": [], "bottom": []})

for idx, (root_module, submodules) in enumerate(sorted_modules):
    bottom_offset = 0
    for sub_idx, (submodule, time) in enumerate(sorted(submodules.items(), key=lambda x: x[1], reverse=True)):
        stacked_data[submodule]["y"].append(root_module)
        stacked_data[submodule]["x"].append(bottom_offset + time)
        stacked_data[submodule]["bottom"].append(bottom_offset)
        bottom_offset += time

# Add stacked bars
for sub_idx, (submodule, data) in enumerate(stacked_data.items()):
    source = ColumnDataSource(data)
    p.hbar(y="y", left="bottom", right="x", height=0.5, source=source,
           color=colors[sub_idx % len(colors)], legend_label=submodule)

# Add hover tool
tooltips = [("Module", "@y"), ("Build Time", "@x s")]
p.add_tools(HoverTool(tooltips=tooltips))

# Configure legend for interactivity
p.legend.title = "Submodules"
p.legend.click_policy = "hide"
p.legend

# Show interactive plot
show(p)
