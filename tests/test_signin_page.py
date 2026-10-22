"""The sign-in page may only talk to Apple, and its CSP must allow its own script."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from update_csp import PAGE, script_hash  # noqa: E402


def test_csp_hash_matches_inline_script():
    html = PAGE.read_text()
    assert f"'{script_hash(html)}'" in html, "run python3 scripts/update_csp.py"


def test_only_apple_is_contacted():
    html = PAGE.read_text()
    csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', html).group(1)
    assert "connect-src https://api.apple-cloudkit.com;" in csp
    assert "default-src 'none'" in csp
    assert '<meta name="referrer" content="no-referrer">' in html
    # No external scripts, styles or fonts.
    assert not re.search(r'<(script|link)[^>]+(src|href)="https?://', html)


def test_all_app_languages():
    html = PAGE.read_text()
    for lang in ("DE", "ES", "IT", "TR"):
        assert f"const {lang} = {{" in html
