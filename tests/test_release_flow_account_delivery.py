from __future__ import annotations

from pathlib import Path, PureWindowsPath
import contextlib
import copy
import io
import json
import os
import queue
import runpy
import subprocess
import tarfile
import unittest
import zipfile

import yaml
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


RELEASE_FLOW_SCRIPT = (Path(__file__).resolve().parents[1] / "plugins/plugin-sync/skills/plugin-sync/scripts/plugin_sync.py")


class SnapshotSaveValidationTests(unittest.TestCase):
    def validate(self, *, corrupt=False, dirty=False, mode="RELEASE", link=False, expected=None,
                 release_ref="refs/tags/v1.0.0", package_name="example",
                 recorded_path="/snapshots/example", archive_link=False, directory_link=False, mode_mismatch=False):
        entry = runpy.run_path(str(RELEASE_FLOW_SCRIPT))["verified_snapshot"]
        metadata = json.dumps({"name": package_name, "version": "0.0.2"})
        contents = {".codex-plugin/plugin.json": metadata.encode(), "skills/entry/SKILL.md": b"entry", "skills/entry/scripts/tool.py": b"print(1)"}
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            for name, content in contents.items():
                entry_name = zipfile.ZipInfo(name)
                entry_name.create_system = 3
                entry_name.external_attr = (0o100755 if name.endswith("tool.py") else 0o100644) << 16
                archive.writestr(entry_name, content)
        archive_bytes = buffer.getvalue()
        digest = __import__("hashlib").sha256(archive_bytes).hexdigest()
        snapshot = {"sha256": digest, "inputVersion": "b" * 64, "sourceCommit": "c" * 40,
                    "sourceDirty": dirty, "metadataSource": {"repository": "owner/repo"}, "version": "0.0.2",
                    "artifact": "example.zip", "sizeBytes": len(archive_bytes), "pluginPath": recorded_path, "packageName": package_name, "accountMode": mode, "releaseRef": release_ref}
        manifest = json.dumps({"version": 1, "plugins": {"example": snapshot}})
        directory = Path("/snapshots/example")
        files = [directory / name for name in contents]
        def read(path):
            if path.name == "example.zip":
                return archive_bytes
            return b"changed" if corrupt else contents[path.relative_to(directory).as_posix()]
        def stat(path):
            return SimpleNamespace(st_mode=0o755 if path.name == "tool.py" and not mode_mismatch else 0o644,
                                   st_size=len(archive_bytes) if path.name == "example.zip" else len(contents[path.relative_to(directory).as_posix()]))
        original_zip = zipfile.ZipFile
        with patch.object(Path, "resolve", lambda path: path), \
                patch.object(Path, "read_text", lambda path, **kwargs: metadata if path.name == "plugin.json" else manifest), \
                patch.object(Path, "read_bytes", read), patch.object(Path, "is_file", return_value=True), \
                patch.object(Path, "is_dir", return_value=True), \
                patch.object(Path, "is_symlink", lambda path: (link and path.name == "tool.py")
                             or (archive_link and path.name == "example.zip") or (directory_link and path == directory)), \
                patch.object(Path, "rglob", return_value=files), patch.object(Path, "stat", stat), \
                patch("zipfile.ZipFile", side_effect=lambda path: original_zip(io.BytesIO(archive_bytes))):
            return entry("/snapshots/snapshots.json", "example", expected or digest, mode, __import__("time").monotonic() + 30)

    def test_rejects_traversal_or_an_unrelated_recorded_directory(self):
        for recorded_path in ("/builder/../example", r"C:\builder\..\example", "/builder/unrelated", None):
            with self.subTest(recorded_path=recorded_path), self.assertRaisesRegex(Exception, "recorded archive directory"):
                self.validate(recorded_path=recorded_path)

    def test_rejects_archive_or_sibling_directory_symlinks(self):
        for options in ({"archive_link": True}, {"directory_link": True}):
            with self.subTest(options=options), self.assertRaisesRegex(Exception, "verified sibling artifact"):
                self.validate(**options)

    def test_rejects_changed_directory_content(self):
        with self.assertRaisesRegex(Exception, "content or executable mode mismatch"):
            self.validate(corrupt=True)

    @unittest.skipIf(os.name == "nt", "Windows does not expose POSIX executable bits")
    def test_rejects_lost_executable_modes_without_repairing_them(self):
        with patch.object(Path, "chmod") as chmod:
            with self.assertRaisesRegex(Exception, "content or executable mode mismatch"):
                self.validate(mode_mismatch=True)
        chmod.assert_not_called()

    def test_rejects_symlink_inside_snapshot(self):
        with self.assertRaisesRegex(Exception, "complete archive"):
            self.validate(link=True)

    def test_rejects_unreviewed_digest(self):
        with self.assertRaisesRegex(Exception, "provenance"):
            self.validate(expected="0" * 64)

    def test_dirty_snapshot_cannot_update_release(self):
        with self.assertRaisesRegex(Exception, "development snapshot"):
            self.validate(dirty=True)
        self.assertFalse(self.validate()["sourceDirty"])

    def test_rejects_dev_snapshot_or_projected_development_name(self):
        for options in ({"mode": "DEV"}, {"package_name": "example-dev"}):
            with self.subTest(options=options), self.assertRaises(Exception):
                self.validate(**options)

    def test_rejects_missing_or_non_tag_release_reference(self):
        for release_ref in (None, "", "v1.0.0", "refs/heads/main"):
            with self.subTest(release_ref=release_ref), self.assertRaises(Exception):
                self.validate(release_ref=release_ref)


class DeliveryBundleValidationTests(unittest.TestCase):
    def unpack(self, members):
        entry = runpy.run_path(str(RELEASE_FLOW_SCRIPT))["unpack_delivery_bundle"]
        archive = MagicMock()
        archive.__enter__.return_value = archive
        archive.getmembers.return_value = members
        with patch.object(Path, "is_symlink", return_value=False), \
                patch.object(Path, "is_file", return_value=True), \
                patch.object(Path, "stat", return_value=SimpleNamespace(st_size=10240)), \
                patch("tarfile.open", return_value=archive):
            try:
                return entry(Path("/dot-release-packages.tar"), Path("/delivery/.stage"),
                             __import__("time").monotonic() + 30)
            finally:
                archive.extractall.assert_not_called()

    def test_rejects_absolute_traversal_windows_or_duplicate_normalized_paths(self):
        cases = [[tarfile.TarInfo(name)] for name in ("/escape", "../escape", "ok/../../escape", r"..\escape", r"C:\escape", "a:b")]
        cases.extend([[tarfile.TarInfo("same"), tarfile.TarInfo("./same")],
                      [tarfile.TarInfo("a//b"), tarfile.TarInfo("a/b")]])
        for members in cases:
            with self.subTest(names=[item.name for item in members]), self.assertRaisesRegex(Exception, "unsafe path or file type"):
                self.unpack(members)

    def test_rejects_links_and_all_special_file_types_before_extraction(self):
        for member_type in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE, tarfile.BLKTYPE):
            member = tarfile.TarInfo("unsafe")
            member.type = member_type
            member.linkname = "../outside"
            with self.subTest(member_type=member_type), self.assertRaisesRegex(Exception, "unsafe path or file type"):
                self.unpack([member])


# The fabricated repository must also own its trusted GitHub Actions identity.
@patch.dict(os.environ, {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "owner/repo"})
def test_release_workflow_uploads_complete_packages_after_publication_without_account_access():
    workflow_path = RELEASE_FLOW_SCRIPT.parents[5] / ".github/workflows/release.yml"
    text = workflow_path.read_text(encoding="utf-8")
    steps = yaml.safe_load(text)["jobs"]["publish"]["steps"]
    names = [step.get("name") for step in steps]
    publish = steps[names.index("Publish release channel")]
    build = steps[names.index("Build complete dot release packages")]
    upload = steps[names.index("Upload complete dot release packages")]
    assert names.index(publish["name"]) < names.index(build["name"]) < names.index(upload["name"])
    assert "ci-publish" in publish["run"]
    assert publish["if"] == build["if"] == upload["if"] == "env.FIRST_PUBLISH_REQUIRED != 'true'"
    script = build["run"]
    assert 'git -C source fetch --no-tags origin "refs/tags/$RELEASE_TAG:refs/tags/$RELEASE_TAG"' in script
    assert 'git -C source checkout --detach "refs/tags/$RELEASE_TAG"' in script
    assert 'python source/plugins/tool-lifecycle/pack.py snapshots "$RUNNER_TEMP/dot-release-packages"' in script
    assert '--project source --account-mode RELEASE --release-ref "$RELEASE_TAG"' in script
    assert script.index("fetch") < script.index("checkout --detach") < script.index("pack.py snapshots")
    assert upload["uses"].startswith("actions/upload-artifact@")
    assert upload["with"]["name"] == "dot-release-packages"
    tar_command = 'tar -cf "$RUNNER_TEMP/dot-release-packages.tar" -C "$RUNNER_TEMP/dot-release-packages" .'
    assert tar_command in script
    assert script.index("pack.py snapshots") < script.index(tar_command)
    assert upload["with"]["path"] == "${{ runner.temp }}/dot-release-packages.tar"
    assert upload["with"]["if-no-files-found"] == "error"
    for forbidden in ("deliver-account", "reconcile-account", "plugin/share/save", "codex app-server",
                      "CODEX_AUTH", "CHATGPT_TOKEN", "OPENAI_API_KEY"):
        assert forbidden not in text


def test_private_projection_keeps_original_files_and_rejects_changed_inputs(tmp_path):
    module = runpy.run_path(str(Path(__file__).resolve().parents[1] / "plugins/tool-lifecycle/private_sources.py"))
    import hashlib, zipfile
    raw = {"plugin.json": json.dumps({"version": "1.3.2", "author": {"name": "Upstream author"}, "description": "Original description", "skills": ["./skills/example"]}).encode(),
           "LICENSE": b"fixture license", "skills/example/SKILL.md": b"---\nname: example\ndisable-model-invocation: true\n---\nExact body\n",
           "skills/example/agents/openai.yaml": b"policy:\n  allow_implicit_invocation: false\n",
           "skills/example/scripts/tool.py": b"print('resource')\n"}
    archive = tmp_path / "upstream.zip"
    with zipfile.ZipFile(archive, "w") as z:
        for name, data in raw.items(): z.writestr("source/" + name, data)
    config = {"name": "example-private", "repository": "owner/source", "commit": "a" * 40,
        "version": "1.3.2", "archivePrefix": "source/", "archiveSha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "manifest": "plugin.json", "skills": ["./skills/example"],
        "license": {"path": "LICENSE", "sha256": hashlib.sha256(raw["LICENSE"]).hexdigest()},
        "adaptations": [{"path": "skills/example/SKILL.md", "field": ["disable-model-invocation"], "before": True, "after": False},
                        {"path": "skills/example/agents/openai.yaml", "field": ["policy", "allow_implicit_invocation"], "before": False, "after": True}]}
    files, provenance = module["project_archive"](archive.read_bytes(), config)
    assert files["skills/example/scripts/tool.py"] == raw["skills/example/scripts/tool.py"]
    assert files["skills/example/SKILL.md"] == raw["skills/example/SKILL.md"].replace(b": true", b": false")
    assert files["skills/example/agents/openai.yaml"] == raw["skills/example/agents/openai.yaml"].replace(b": false", b": true")
    assert files["LICENSE"] == raw["LICENSE"] and provenance["commit"] == "a" * 40
    assert "plugin.json" not in files
    for bad in ({**config, "archiveSha256": "0" * 64}, {**config, "skills": []},
                {**config, "license": {"path": "LICENSE", "sha256": "0" * 64}}):
        with __import__("pytest").raises(ValueError): module["project_archive"](archive.read_bytes(), bad)
