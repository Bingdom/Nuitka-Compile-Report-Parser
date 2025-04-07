Can be used with command line arguments

```sh
python3 -m nuitka_reporter "compile-report.xml"
```

Or as a module

```py
import nuitka_reporter

output = nuitka_reporter.to_html("compile-report.xml")
print(output)
```