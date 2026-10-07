#!/usr/bin/env python3
"""Collect BlueOS release entries, validating public access before publishing."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ACCEPT = ", ".join((
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json",
))


def download(url, headers=None):
    with urlopen(Request(url, headers=headers or {}), timeout=60) as response:
        return response.read()


def validate_entry(entry, source, release_tag):
    expected_docker = f"ghcr.io/{source['repository'].lower()}"
    if entry["identifier"] != source["identifier"] or entry["docker"] != expected_docker:
        raise ValueError("Release identity does not match configured source")
    if not re.fullmatch(r"v?\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", release_tag):
        raise ValueError(f"Invalid release version: {release_tag}")
    if set(entry["versions"]) != {release_tag}:
        raise ValueError("Release metadata must describe exactly its own version")
    for key in ("name", "website", "description"):
        if not isinstance(entry[key], str) or not entry[key]:
            raise ValueError(f"Missing extension field: {key}")
    version = entry["versions"][release_tag]
    if version["tag"] != release_tag or not isinstance(version["permissions"], dict):
        raise ValueError("Invalid version tag or permissions")
    if not version["images"]:
        raise ValueError("No images in release")
    for image in version["images"]:
        if image["platform"] != {"architecture": "arm64", "os": "linux"}:
            raise ValueError("Unsupported image platform")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image["digest"]):
            raise ValueError("Invalid image digest")
        if not isinstance(image["expanded_size"], int) or image["expanded_size"] <= 0:
            raise ValueError("Invalid image size")


def check_public_image(docker, image):
    package = docker.removeprefix("ghcr.io/")
    query = urlencode({"service": "ghcr.io", "scope": f"repository:{package}:pull"})
    token = json.loads(download(f"https://ghcr.io/token?{query}"))["token"]
    headers = {"Authorization": f"Bearer {token}", "Accept": ACCEPT}
    raw = download(f"https://ghcr.io/v2/{package}/manifests/{image['digest']}", headers)
    if f"sha256:{hashlib.sha256(raw).hexdigest()}" != image["digest"]:
        raise ValueError("Registry returned a different image digest")
    manifest = json.loads(raw)
    config = json.loads(download(
        f"https://ghcr.io/v2/{package}/blobs/{manifest['config']['digest']}", headers
    ))
    if config["architecture"] != image["platform"]["architecture"] or config["os"] != "linux":
        raise ValueError("Registry image platform does not match release metadata")


def merge_entries(entries):
    """Keep all versions, using the first (newest release) for card metadata."""
    merged = {}
    for entry in entries:
        identifier = entry["identifier"]
        if identifier not in merged:
            merged[identifier] = {**entry, "versions": dict(entry["versions"])}
            continue
        existing = merged[identifier]
        if existing["docker"] != entry["docker"]:
            raise ValueError("An extension identifier cannot refer to multiple image repositories")
        if set(existing["versions"]) & set(entry["versions"]):
            raise ValueError("Duplicate release version")
        existing["versions"].update(entry["versions"])
    return sorted(merged.values(), key=lambda entry: entry["identifier"])


def collect(sources):
    entries = []
    for source in sources:
        pages = json.loads(subprocess.check_output([
            "gh", "api", "--paginate", "--slurp",
            f"repos/{source['repository']}/releases?per_page=100",
        ], text=True))
        releases = sorted((release for page in pages for release in page),
                          key=lambda release: release.get("published_at") or "", reverse=True)
        count = 0
        for release in releases:
            if release["draft"]:
                continue
            asset = next((asset for asset in release["assets"]
                          if asset["name"] == "blueos-manifest.json"), None)
            if asset is None:
                continue
            entry = json.loads(download(asset["browser_download_url"]))
            validate_entry(entry, source, release["tag_name"])
            for version in entry["versions"].values():
                for image in version["images"]:
                    check_public_image(entry["docker"], image)
            entries.append(entry)
            count += 1
        if not count:
            raise ValueError(f"No published catalog releases for {source['repository']}")
    return merge_entries(entries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", default="sources.json")
    parser.add_argument("--output", default="manifest.json")
    args = parser.parse_args()
    entries = collect(json.loads(Path(args.sources).read_text()))
    Path(args.output).write_text(json.dumps(entries, indent=2) + "\n")
    print(f"Validated {len(entries)} extensions and published {args.output}")


if __name__ == "__main__":
    main()
