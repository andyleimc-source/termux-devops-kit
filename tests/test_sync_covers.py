import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync-covers.py"
spec = importlib.util.spec_from_file_location("sync_covers", SCRIPT)
covers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(covers)
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000b49444154789c636000020000050001a5f645400000000049454e44ae426082"
)


class CoverSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "output"
        self.manifest = self.root / "manifest.json"
        self.item = {
            "rom_id": "dino", "label": "恐龙快打", "library": "经典街机",
            "art_kind": "boxart", "source_url": "https://example.test/dino.png",
            "sha256": hashlib.sha256(PNG).hexdigest(),
        }
        self.save()

    def save(self):
        self.manifest.write_text(json.dumps({"items": [self.item]}, ensure_ascii=False))

    def run_cli(self, *extra):
        args = [str(SCRIPT), "--manifest", str(self.manifest), "--output", str(self.output), *extra]
        with mock.patch.object(sys, "argv", args), contextlib.redirect_stdout(io.StringIO()):
            covers.main()

    def test_fullwidth_chinese_title_preserved(self):
        self.assertEqual(covers.sanitize("Pang：打气球"), "Pang：打气球")
        self.assertEqual(covers.sanitize('A/B: C & D?'), 'A_B_ C _ D_')

    def test_unknown_game_is_error_and_manifest_unchanged(self):
        before = self.manifest.read_bytes()
        with self.assertRaises((ValueError, SystemExit)):
            self.run_cli("--only", "does-not-exist")
        self.assertEqual(self.manifest.read_bytes(), before)

    def test_manifest_cannot_escape_output(self):
        self.item["library"] = "../outside"
        self.save()
        with mock.patch.object(covers.urllib.request, "urlopen", return_value=io.BytesIO(PNG)):
            with self.assertRaises(ValueError):
                self.run_cli()
        self.assertFalse((self.root / "outside").exists())

    def test_download_hash_failure_leaves_no_cached_image(self):
        with mock.patch.object(covers.urllib.request, "urlopen", return_value=io.BytesIO(PNG + b"wrong")):
            with self.assertRaises(ValueError):
                self.run_cli()
        self.assertFalse(list(self.output.rglob("*.png")))

    def test_invalid_cached_png_is_rejected_even_with_matching_hash(self):
        dest = self.output / "经典街机" / "Named_Boxarts" / "恐龙快打.png"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"not-an-image")
        self.item["sha256"] = hashlib.sha256(b"not-an-image").hexdigest()
        self.save()
        with self.assertRaises(ValueError):
            self.run_cli()

    def test_remote_shell_preserves_spaces_and_metacharacters(self):
        relative = "经典 街机/Named_Boxarts/打击者1945 II.png"
        remote_root = "/sdcard/My Covers"
        digest = "a" * 64
        with mock.patch.object(covers.subprocess, "run") as run, mock.patch.object(
            covers.subprocess, "check_output", return_value=digest + "  image.png\n"
        ) as output:
            covers.install_image("test-device", remote_root, relative, Path("local.png"), digest)
        import shlex
        mkdir = run.call_args_list[0].args[0][-1]
        self.assertEqual(shlex.split(mkdir), ["mkdir", "-p", "/sdcard/My Covers/经典 街机/Named_Boxarts"])
        checksum = output.call_args.args[0][-1]
        self.assertEqual(shlex.split(checksum), ["sha256sum", remote_root + "/" + relative])

    def test_verified_cache_reuse_never_calls_network(self):
        dest = self.output / "经典街机" / "Named_Boxarts" / "恐龙快打.png"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(PNG)
        with mock.patch.object(covers.urllib.request, "urlopen", side_effect=AssertionError("network called")):
            self.run_cli()
            self.run_cli()
        result = json.loads(self.manifest.read_text())["items"][0]
        self.assertEqual(result["sha256"], hashlib.sha256(PNG).hexdigest())
        self.assertEqual(result["local_relative_path"], "经典街机/Named_Boxarts/恐龙快打.png")


if __name__ == "__main__":
    unittest.main()
