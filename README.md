# Ixian Ukraine BlueOS extensions

Public extension catalog for BlueOS. Images are built on native ARM64 GitHub
Actions runners and published to GitHub Container Registry (GHCR).

## Install

In BlueOS, open **Extensions → Settings (gear) → Extensions Manifest → +**.
Add this enabled source:

- **Name:** Ixian Ukraine
- **URL:** `https://raw.githubusercontent.com/ixian-ukraine/blueos-extensions/main/manifest.json`

Apply the settings, then select an extension in the store:

| Extension | Identifier | Source | Image |
| --- | --- | --- | --- |
| MediaMTX (Ixian) | `ixian-ukraine.mediamtx` | [Source](https://github.com/ixian-ukraine/blueos-extension-mediamtx) | `ghcr.io/ixian-ukraine/blueos-extension-mediamtx` |
| NetBird VPN | `ixian-ukraine.netbird` | [Source](https://github.com/ixian-ukraine/blueos-extension-netbird) | `ghcr.io/ixian-ukraine/blueos-extension-netbird` |
| ZeroTier (Ixian) | `ixian-ukraine.zerotier` | [Source](https://github.com/ixian-ukraine/blueos-extension-zerotier) | `ghcr.io/ixian-ukraine/blueos-extension-zerotier` |

Supported platform: **Linux ARM64** (64-bit BlueOS). The catalog does not advertise
ARMv7 or AMD64 images. BlueOS may cache manifest downloads for one hour.

Existing manually installed extensions must use the same identifier to receive
catalog updates. MediaMTX shares its ports and persistent directory with the
upstream extension; stop the existing instance before switching to this build.

ZeroTier also reuses the upstream extension's ports and persistent directory
(`/usr/blueos/extensions/zerotier`) to retain its node identity and network
memberships. Disable the upstream instance before installing **ZeroTier (Ixian)**.
Use a local connection or another VPN for the switch, since stopping ZeroTier
interrupts its connection.

## Release process

1. Update the extension's version metadata and commit the changes.
2. Push a SemVer tag (for example `2.1.1`) in the extension repository.
3. Its workflow calls `publish-extension.yml` here to build and smoke-test the
   image, push a versioned GHCR tag, and attach `blueos-manifest.json` to a GitHub
   release. The metadata records the pushed image digest, actual image size,
   Docker labels, platform, and runtime permissions.
4. The **Refresh catalog** workflow collects published release metadata hourly.
   It can also be run manually from this repository's Actions tab.
5. The workflow validates that every listed image is anonymously accessible in
   GHCR before committing an updated `manifest.json`. If validation fails, the
   existing catalog is retained.

### First publication of a package

GHCR initially creates packages as private. An organization/package administrator
must open each package's **Package settings → Change visibility → Public** once.
This is separate from the source repository's visibility. Then run **Refresh
catalog**. No Docker Hub credentials or cross-repository personal access tokens
are required by these workflows.

### Catalog implementation

- `scripts/release_manifest.py`: generates a release entry from the built image.
- `scripts/catalog.py`: collects releases and checks public registry digests.
- `sources.json`: explicitly lists the repositories and extension IDs to publish.
- `tests/`: validation and version-merging tests; run
  `python3 -m unittest discover -s tests -v`.

The catalog uses BlueOS's manifest schema, including per-platform image digests.
Application configuration and VPN credentials belong on the vehicle's persistent
mounts, not in release metadata.
