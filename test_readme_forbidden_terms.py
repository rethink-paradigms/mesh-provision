"""Verify README.md contains no forbidden terms from the old marketing era."""

import re
import sys

with open("README.md") as f:
    content = f.read()

errors = []
for term in ["kubernetes", "heroku", "13+", "gpu", "spot", "pricing", "$8", "$25"]:
    if re.search(term, content, re.IGNORECASE):
        errors.append(f"Found forbidden term: {term}")

if errors:
    for e in errors:
        print(e)
    sys.exit(1)
else:
    print("All checks passed")
    sys.exit(0)
