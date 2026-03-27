Can be used with command line arguments

```sh
python3 -m nuitka_reporter "compile-report.xml"
```

Or as executable

```sh
uvx git+https://github.com/Bingdom/Nuitka-Compile-Report-Parser "compile-report.xml"
pipx run --spec git+https://github.com/Bingdom/Nuitka-Compile-Report-Parser nuitka-reporter "compile-report.xml"
```

Or as a module

```py
import nuitka_reporter

output = nuitka_reporter.to_html("compile-report.xml")
print(output)
```
It will output a .html report, with graphs showing which modules take the most time and storage, a dependency graph, and a short overview summary.

_Note: This report doesn't include the C compilation information, as the compile report currently doesn't include this information._
