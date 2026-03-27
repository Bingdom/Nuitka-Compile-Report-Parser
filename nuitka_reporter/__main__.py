import argparse
from .main import to_html


def main():
    parser = argparse.ArgumentParser(
        prog="nuitka-reporter",
        description="Parses a compilation report from nuitka and outputs a html file"
    )

    parser.add_argument(
        "report", type=str, help="Input a file path to the compilation report file (ex. './compilation-report.xml') that you want to parse and visualize.",
    )

    parser.add_argument(
        "output", type=str, nargs='?', default='report.html', help="Optional export filename as a .html file. Defaults to './report.html' if not provided."
    )

    args = parser.parse_args()
    html_file = to_html(args.report, args.output)
    return html_file


if __name__ == "__main__":
    main()
