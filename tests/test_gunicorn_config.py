import os
import sys
import unittest
import importlib.util
from pathlib import Path


def load_gunicorn_conf():
    project_root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        f"gunicorn_conf_test_{os.urandom(8).hex()}",
        str(project_root / "gunicorn.conf.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GunicornConfigTests(unittest.TestCase):
    def setUp(self):
        self.old_port = os.environ.get("PORT")

    def tearDown(self):
        if self.old_port is None:
            os.environ.pop("PORT", None)
        else:
            os.environ["PORT"] = self.old_port

    def test_bind_defaults_to_10000_when_port_invalid(self):
        for value in [None, "", "abc", "65536"]:
            if value is None:
                os.environ.pop("PORT", None)
            else:
                os.environ["PORT"] = value
            module = load_gunicorn_conf()
            self.assertEqual(module.bind, "0.0.0.0:10000")

    def test_bind_uses_valid_port(self):
        os.environ["PORT"] = "8080"
        module = load_gunicorn_conf()
        self.assertEqual(module.bind, "0.0.0.0:8080")


if __name__ == "__main__":
    unittest.main()
