from nuitka_reporter import to_html
import os


def test_generate():
    current_dir = os.path.dirname(__file__)
    filename = os.path.join(current_dir, "data/compilation-report.xml")
    output_filename = to_html(filename)

    # assert filename == output_filename, "Input filename must match with output filename"

    assert os.path.isfile(output_filename), "Output file must exist"

    assert os.path.getsize(output_filename) > 0, "Output file is 0 kb"
