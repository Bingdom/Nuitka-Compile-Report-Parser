from nuitka_reporter import to_html
import os


def generate(filename: str, export_filename: str):
    output_filename = to_html(filename, export_filename)

    assert os.path.isfile(output_filename), "Output file must exist"

    assert os.path.getsize(output_filename) > 0, "Output file is 0 kb"


def test_generate_4_0():
    current_dir = os.path.dirname(__file__)
    filename = os.path.join(current_dir, "data/compilation-report_4.0.xml")
    output_filename = os.path.join(
        current_dir, "data/compilation-report_4.0.html")
    generate(filename, output_filename)


def test_generate_4_1():
    current_dir = os.path.dirname(__file__)
    filename = os.path.join(current_dir, "data/compilation-report_4.1.xml")
    output_filename = os.path.join(
        current_dir, "data/compilation-report_4.1.html")
    generate(filename, output_filename)
