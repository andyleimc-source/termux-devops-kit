import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "install.sh"


class InstallerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "usr/bin"
        self.bin.mkdir(parents=True)
        self.home = self.root / "home"
        self.home.mkdir()
        self.log = self.root / "calls"
        self.env = dict(os.environ, HOME=str(self.home), PREFIX=str(self.bin.parent),
                        PATH=str(self.bin) + ":" + os.environ["PATH"], CALL_LOG=str(self.log))
        self.tool("pkg", 'echo "$*" >> "$CALL_LOG"; exit "${PKG_EXIT:-0}"')
        self.tool("apt-get", 'exit 0')
        self.tool("termux-reload-settings", 'exit "${RELOAD_EXIT:-0}"')
        # Test substitute: dispatch arguments; production uses coreutils timeout.
        self.tool("timeout", 'shift 2; exec "$@"')
        (self.bin / "python").symlink_to(sys.executable)

    def tool(self, name, body):
        path = self.bin / name
        path.write_text("#!/usr/bin/env bash\n" + body + "\n")
        path.chmod(0o755)

    def run_install(self):
        return subprocess.run(["bash"], input=SCRIPT.read_text(), text=True,
                              env=self.env, capture_output=True, timeout=10)

    def test_idempotent_and_preserves_settings(self):
        config = self.home / ".termux/termux.properties"
        config.parent.mkdir()
        config.write_text("# keep\nuse-black-ui = true\nextra-keys = \\\nold-layout\nbell-character=beep\n")
        first = self.run_install()
        self.assertEqual(first.returncode, 0, first.stderr)
        content = config.read_text()
        self.assertIn("use-black-ui = true", content)
        self.assertNotIn("old-layout", content)
        self.assertEqual(content.count("extra-keys ="), 1)
        backups = list(config.parent.glob("*.bak.*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(self.run_install().returncode, 0)
        self.assertEqual(config.read_text(), content)
        self.assertEqual(list(config.parent.glob("*.bak.*")), backups)
        calls = self.log.read_text()
        for package in "openssh mosh tmux termux-tools termux-api nodejs-lts android-tools git python build-essential curl tar proot ca-certificates".split():
            self.assertIn(package, calls)
        self.assertIn("Dpkg::Options::=--force-confold", calls)

    def test_install_failure_does_not_write_config(self):
        self.env["PKG_EXIT"] = "42"
        result = self.run_install()
        self.assertEqual(result.returncode, 42)
        self.assertFalse((self.home / ".termux").exists())

    def test_reload_failure_is_reported(self):
        self.env["RELOAD_EXIT"] = "1"
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("重载失败", result.stderr)

    def test_rejects_non_termux(self):
        self.env.pop("PREFIX")
        self.assertNotEqual(self.run_install().returncode, 0)
        self.assertFalse(self.log.exists())

    def test_rejects_invalid_timeout(self):
        self.env["TERMUX_KIT_TIMEOUT"] = "forever"
        self.assertNotEqual(self.run_install().returncode, 0)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
