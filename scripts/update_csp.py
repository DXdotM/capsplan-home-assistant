#!/usr/bin/env python3
"""Updates the script hash in the sign-in page's Content-Security-Policy.

Run after changing the inline script in docs/index.html.
"""

import base64
import hashlib
import re
from pathlib import Path

PAGE = Path(__file__).parents[1] / "docs" / "index.html"


def script_hash(html: str) -> str:
    script = re.search(r"<script>(.*?)</script>", html, re.S).group(1)
    return "sha256-" + base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()


if __name__ == "__main__":
    html = PAGE.read_text()
    PAGE.write_text(re.sub(r"'sha256-[A-Za-z0-9+/=]+'", f"'{script_hash(html)}'", html, count=1))
    print("updated", script_hash(html))
