import argparse
from .main import to_html


parser = argparse.ArgumentParser(
    description="Parses a compilation report from nuitka and outputs a html file")
parser.add_argument(
    "filename", metavar="FILENAME", type=str, help="Path to the compilation report file"
)
args = parser.parse_args()
html_file = to_html(args.filename)
print(f"HTML report generated at: {html_file}")
