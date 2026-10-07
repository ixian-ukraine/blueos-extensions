#!/usr/bin/env python3
"""Create a BlueOS catalog entry from an image that has been pushed to GHCR."""

import argparse
import html
import json
import re
import subprocess
from pathlib import Path


def make_entry(image, repository, tag, identifier, name, description):
    if not re.fullmatch(r"v?\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", tag):
        raise ValueError(f"Release tag must be SemVer: {tag}")
    docker = f"ghcr.io/{repository.lower()}"
    digests = [value.split("@", 1)[1] for value in image.get("RepoDigests", [])
               if value.startswith(docker + "@")]
    if not digests or not re.fullmatch(r"sha256:[0-9a-f]{64}", digests[0]):
        raise ValueError("Image has no published registry digest")
    if image["Architecture"] != "arm64" or image["Os"] != "linux":
        raise ValueError("This release workflow supports Linux ARM64 only")
    labels = image["Config"]["Labels"]
    website = f"https://github.com/{repository}"
    links = json.loads(labels.get("links", "{}"))
    return {
        "identifier": identifier,
        "name": name,
        "website": website,
        "docker": docker,
        "description": description,
        "versions": {
            tag: {
                "tag": tag,
                "type": labels.get("type", "other"),
                "authors": json.loads(labels.get("authors", "[]")),
                "company": json.loads(labels["company"]),
                "filter_tags": json.loads(labels.get("tags", "[]")),
                "extra_links": links,
                "website": website,
                "support": f"{website}/issues",
                "readme": (
                    f"<p>{html.escape(description)}</p>"
                    f'<p><a href="{website}/blob/{tag}/README.md">'
                    "Installation and usage documentation</a></p>"
                ),
                "requirements": labels.get("requirements", "core >= 1.1"),
                "permissions": json.loads(labels["permissions"]),
                "images": [{
                    "platform": {"architecture": "arm64", "os": "linux"},
                    "digest": digests[0],
                    "expanded_size": image["Size"],
                }],
            }
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("repository", "tag", "identifier", "name", "description", "output"):
        parser.add_argument(f"--{argument}", required=True)
    args = parser.parse_args()
    image_name = f"ghcr.io/{args.repository.lower()}:{args.tag}"
    image = json.loads(subprocess.check_output(
        ["docker", "image", "inspect", image_name], text=True
    ))[0]
    entry = make_entry(image, args.repository, args.tag, args.identifier, args.name, args.description)
    Path(args.output).write_text(json.dumps(entry, indent=2) + "\n")


if __name__ == "__main__":
    main()
