import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
import squarify
from collections import defaultdict

# Load and parse the XML file
file_path = "compilation-report.xml"
tree = ET.parse(file_path)
root = tree.getroot()

# Dictionary to store total optimization time per module
module_times = defaultdict(float)

# Iterate over modules and sum optimization times
for module in root.findall("module"):
    module_name = module.get("name", "Unknown")
    total_time = 0.0
    
    for opt_time in module.findall("optimization-time"):
        total_time += float(opt_time.get("time", 0.0))
    
    module_times[module_name] += total_time

# Sort modules by total time taken
sorted_modules = sorted(module_times.items(), key=lambda x: x[1], reverse=True)

# Extract names and times for plotting
module_names, build_times = zip(*sorted_modules) if sorted_modules else ([], [])

# Plot the build times as a treemap
plt.figure(figsize=(12, 8))
squarify.plot(sizes=build_times, label=module_names, alpha=0.7)
plt.axis("off")
plt.title("Treemap of Module Compilation Times")
plt.show()
