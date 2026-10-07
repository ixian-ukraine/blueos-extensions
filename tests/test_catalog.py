import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from catalog import check_public_image, merge_entries, validate_entry
from release_manifest import make_entry


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.repository = "ixian-ukraine/blueos-extension-netbird"
        self.source = {"repository": self.repository, "identifier": "ixian-ukraine.netbird"}
        self.image = {
            "Architecture": "arm64", "Os": "linux", "Size": 1000000,
            "RepoDigests": [f"ghcr.io/{self.repository}@sha256:" + "a" * 64],
            "Config": {"Labels": {
                "company": '{"name":"Ixian Ukraine"}',
                "permissions": '{"HostConfig":{"NetworkMode":"host","Binds":["/state:/state"]}}',
            }},
        }

    def entry(self, tag="0.74.7"):
        return make_entry(self.image, self.repository, tag, self.source["identifier"],
                          "NetBird VPN", "VPN connectivity")

    def test_image_inspection_preserves_permissions_and_digest(self):
        entry = self.entry()
        validate_entry(entry, self.source, "0.74.7")
        version = entry["versions"]["0.74.7"]
        self.assertEqual(version["permissions"]["HostConfig"]["Binds"], ["/state:/state"])
        self.assertEqual(version["images"][0]["digest"], "sha256:" + "a" * 64)
        self.assertEqual(version["images"][0]["expanded_size"], 1000000)

    def test_unpublished_image_is_rejected(self):
        self.image["RepoDigests"] = []
        with self.assertRaisesRegex(ValueError, "published registry digest"):
            self.entry()

    def test_release_cannot_substitute_another_image_or_identifier(self):
        for field, value in (("docker", "ghcr.io/other/image"), ("identifier", "other.id")):
            entry = self.entry()
            entry[field] = value
            with self.assertRaisesRegex(ValueError, "identity"):
                validate_entry(entry, self.source, "0.74.7")

    def test_metadata_tag_must_match_release(self):
        with self.assertRaisesRegex(ValueError, "own version"):
            validate_entry(self.entry(), self.source, "0.74.8")

    def test_merge_keeps_old_versions_and_latest_card_metadata(self):
        latest, old = self.entry("0.74.8"), self.entry()
        old["name"] = "Old name"
        snapshot = copy.deepcopy(latest)
        result = merge_entries([latest, old])
        self.assertEqual(set(result[0]["versions"]), {"0.74.7", "0.74.8"})
        self.assertEqual(result[0]["name"], "NetBird VPN")
        self.assertEqual(latest, snapshot)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            merge_entries([latest, latest])

    def test_registry_digest_and_platform_are_verified(self):
        raw = json.dumps({"config": {"digest": "sha256:" + "b" * 64}}).encode()
        image = {"digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
                 "platform": {"architecture": "arm64", "os": "linux"}}
        with patch("catalog.download", side_effect=[
            b'{"token":"anonymous-token"}', raw, b'{"architecture":"amd64","os":"linux"}'
        ]):
            with self.assertRaisesRegex(ValueError, "platform"):
                check_public_image(f"ghcr.io/{self.repository}", image)
        with patch("catalog.download", side_effect=[b'{"token":"anonymous-token"}', b"wrong"]):
            with self.assertRaisesRegex(ValueError, "digest"):
                check_public_image(f"ghcr.io/{self.repository}", image)


if __name__ == "__main__":
    unittest.main()
