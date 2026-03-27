"""
This is an example project to test the nuitka_reporter. It includes some imports and a simple print statement. The imports are designed to create a small dependency graph.
"""

# nuitka-project: --mode=standalone
# nuitka-project: --report=compilation-report.xml

import import_1
import import_2

import bcrypt
import aiohttp
import asyncio


print("Hello world!")
