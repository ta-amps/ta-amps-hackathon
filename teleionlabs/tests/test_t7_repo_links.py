"""The account-name gate allows an exact public repository href and nothing else. Run: python3 tests/test_t7_repo_links.py"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_words import PUBLIC_REPOS, is_public_repo_url, raw_html_t7_hits  # noqa: E402

ACCOUNT = "https://github.com/ta-amps"


def page(body: str) -> str:
    return f"<!doctype html><body>{body}</body>"


class AllowedHrefs(unittest.TestCase):
    def test_each_public_repo_href_passes(self):
        self.assertEqual(len(PUBLIC_REPOS), 6)
        for repo in PUBLIC_REPOS:
            self.assertEqual(raw_html_t7_hits(page(f'<a href="{ACCOUNT}/{repo}">Source</a>')), [], repo)

    def test_each_public_repo_is_an_allowed_content_value(self):
        for repo in PUBLIC_REPOS:
            self.assertTrue(is_public_repo_url(f"{ACCOUNT}/{repo}"), repo)


class StillFails(unittest.TestCase):
    MAIN = f"{ACCOUNT}/{PUBLIC_REPOS[0]}"

    def assert_hit(self, html):
        self.assertTrue(raw_html_t7_hits(page(html)), html)

    def test_visible_account_name(self):
        self.assert_hit("<p>Made by ta-amps</p>")

    def test_repo_url_as_visible_text(self):
        self.assert_hit(f'<a href="{self.MAIN}">{self.MAIN}</a>')
        self.assert_hit(f"<p>{self.MAIN}</p>")

    def test_account_home(self):
        self.assert_hit(f'<a href="{ACCOUNT}">Source</a>')
        self.assert_hit(f'<a href="{ACCOUNT}/">Source</a>')

    def test_unlisted_repo_and_lookalikes(self):
        for bad in ("ta-amps-hackathon", "tessera-infrastructure-work-and-storage-engine", f"{PUBLIC_REPOS[0]}-copy"):
            self.assert_hit(f'<a href="{ACCOUNT}/{bad}">Source</a>')

    def test_paths_inside_a_repo(self):
        for tail in ("/", "/issues", "/blob/main/README.md", "?tab=readme", "#readme"):
            self.assert_hit(f'<a href="{self.MAIN}{tail}">Source</a>')

    def test_other_hosts_and_attributes(self):
        self.assert_hit(f'<a href="https://github.com.example.org/ta-amps/{PUBLIC_REPOS[0]}">Source</a>')
        self.assert_hit(f'<a title="{self.MAIN}" href="/">Source</a>')
        self.assert_hit(f'<meta content="{self.MAIN}">')

    def test_other_t7_words_beside_an_allowed_href(self):
        self.assert_hit(f'<a href="{self.MAIN}">Source</a><p>Made by ta-amps</p>')
        self.assert_hit(f'<a href="{self.MAIN}">Source</a><p>See our pricing</p>')

    def test_content_values(self):
        for bad in (f"See {self.MAIN}", f"[code]({self.MAIN})", f"{self.MAIN}/issues", ACCOUNT, "ta-amps"):
            self.assertFalse(is_public_repo_url(bad), bad)


if __name__ == "__main__":
    unittest.main(verbosity=0)
