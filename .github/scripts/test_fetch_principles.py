"""Exercise release preference and fail-closed preview resolution without network."""
import base64
import json
import unittest
from urllib.error import HTTPError

from fetch_principles import resolve

SHA = "a" * 40
PIN = {"version": "0.3.0", "pr": 23, "sha": SHA}


def file(version="0.3.0"):
    return {
        "type": "file", "encoding": "base64",
        "content": base64.b64encode(json.dumps({"version": version}).encode()).decode(),
    }


class ResolutionTests(unittest.TestCase):
    def fetcher(self, routes):
        def get(path):
            value = routes[path]
            if isinstance(value, Exception):
                raise value
            return value
        return get

    def missing(self, status=404):
        return HTTPError("test", status, "test", {}, None)

    def preview_routes(self):
        return {
            "git/ref/tags/v0.3.0": self.missing(),
            "pulls/23/commits?per_page=100&page=1": [{"sha": SHA}],
            f"contents/stamped-principles.json?ref={SHA}": file(),
        }

    def test_release_wins_over_preview(self):
        routes = self.preview_routes()
        routes["git/ref/tags/v0.3.0"] = {"object": {"type": "commit", "sha": SHA}}
        del routes["pulls/23/commits?per_page=100&page=1"]
        data, source = resolve("0.3.0", PIN, self.fetcher(routes))
        self.assertEqual(data["version"], "0.3.0")
        self.assertTrue(source.startswith("Released"))

    def test_annotated_release(self):
        routes = self.preview_routes()
        routes["git/ref/tags/v0.3.0"] = {"object": {"type": "tag", "sha": "b" * 40}}
        routes[f"git/tags/{'b' * 40}"] = {"object": {"type": "commit", "sha": SHA}}
        self.assertTrue(resolve("0.3.0", None, self.fetcher(routes))[1].startswith("Released"))

    def test_verified_preview(self):
        self.assertIn("not released", resolve("0.3.0", PIN, self.fetcher(self.preview_routes()))[1])

    def test_release_mode_rejects_missing_tag(self):
        with self.assertRaises(HTTPError):
            resolve("0.3.0", None, self.fetcher(self.preview_routes()))

    def test_non_404_failures_do_not_use_preview(self):
        for status in (403, 429, 500):
            with self.subTest(status=status), self.assertRaises(HTTPError):
                resolve("0.3.0", PIN, self.fetcher({"git/ref/tags/v0.3.0": self.missing(status)}))

    def test_unrelated_sha_rejected(self):
        routes = self.preview_routes()
        routes["pulls/23/commits?per_page=100&page=1"] = [{"sha": "b" * 40}]
        with self.assertRaisesRegex(ValueError, "not a commit"):
            resolve("0.3.0", PIN, self.fetcher(routes))

    def test_wrong_version_rejected(self):
        routes = self.preview_routes()
        routes[f"contents/stamped-principles.json?ref={SHA}"] = file("0.2.0")
        with self.assertRaisesRegex(ValueError, "wrong version"):
            resolve("0.3.0", PIN, self.fetcher(routes))

    def test_invalid_pin_rejected(self):
        for pin in ({**PIN, "version": "0.2.0"}, {**PIN, "sha": "main"}, {**PIN, "pr": True}):
            with self.subTest(pin=pin), self.assertRaisesRegex(ValueError, "Invalid"):
                resolve("0.3.0", pin, self.fetcher(self.preview_routes()))

    def test_release_file_failure_does_not_use_preview(self):
        routes = self.preview_routes()
        routes["git/ref/tags/v0.3.0"] = {"object": {"type": "commit", "sha": SHA}}
        routes[f"contents/stamped-principles.json?ref={SHA}"] = self.missing()
        with self.assertRaises(HTTPError):
            resolve("0.3.0", PIN, self.fetcher(routes))


if __name__ == "__main__":
    unittest.main()
