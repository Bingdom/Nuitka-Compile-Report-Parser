import argparse
from typing import Optional
from .main import to_html


def main():
    parser = argparse.ArgumentParser(
        description="Parses a compilation report from nuitka and outputs a html file")
    parser.add_argument(
        "compile-filename", type=str, help="Path to the compilation report file",
    )
    parser.add_argument(
        "export-filename", type=str, nargs='?', default='report.html', help="Optional export filename as a .html file. Defaults to 'report.html' if not provided."
    )
    args = parser.parse_args()
    html_file = to_html(getattr(args, "compile-filename"),
                        getattr(args, "export-filename"))
    print(f"HTML report generated at: {html_file}")


if __name__ == "__main__":
    main()
