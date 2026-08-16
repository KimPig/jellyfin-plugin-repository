#!/usr/bin/env python3
"""Generate Jellyfin's plugin repository manifest from GitHub Releases."""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "manifest.json"
GITHUB_API = "https://api.github.com"
VERSION_PATTERN = re.compile(r"^\d+(?:\.\d+){1,3}$")

PLUGINS = (
    {
        "repository": "KimPig/jellyfin-plugin-attachment-optimizer",
        "asset_prefix": "AttachmentOptimizer_",
        "guid": "41341b7d-9374-4c82-824a-21d360036771",
        "name": "Attachment Optimizer",
    },
    {
        "repository": "KimPig/jellyfin-plugin-subtitle-font-bridge",
        "asset_prefix": "SubtitleFontBridge_",
        "guid": "81ea0bd3-d8e0-4f4a-b680-bf8b83a673f7",
        "name": "Subtitle Font Bridge",
    },
)


def request(url: str, *, accept: str) -> bytes:
    headers = {
        "Accept": accept,
        "User-Agent": "KimPig-Jellyfin-Plugin-Repository",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith(GITHUB_API):
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub request failed ({error.code}) for {url}: {detail}") from error


def request_json(url: str) -> object:
    return json.loads(request(url, accept="application/vnd.github+json"))


def published_releases(repository: str) -> list[dict[str, object]]:
    releases: list[dict[str, object]] = []
    page = 1
    while True:
        payload = request_json(
            f"{GITHUB_API}/repos/{repository}/releases?per_page=100&page={page}"
        )
        if not isinstance(payload, list):
            raise RuntimeError(f"Unexpected releases response for {repository}")

        batch = [
            release
            for release in payload
            if isinstance(release, dict)
            and not release.get("draft")
            and not release.get("prerelease")
        ]
        releases.extend(batch)
        if len(payload) < 100:
            break
        page += 1

    return releases


def version_key(value: str) -> tuple[int, ...]:
    if not VERSION_PATTERN.fullmatch(value):
        raise RuntimeError(f"Unsupported plugin version: {value}")
    return tuple(int(part) for part in value.split("."))


def matching_asset(release: dict[str, object], prefix: str) -> dict[str, object] | None:
    assets = release.get("assets", [])
    if not isinstance(assets, list):
        return None

    matches = [
        asset
        for asset in assets
        if isinstance(asset, dict)
        and str(asset.get("name", "")).startswith(prefix)
        and str(asset.get("name", "")).lower().endswith(".zip")
    ]
    if len(matches) > 1:
        tag = release.get("tag_name", "unknown")
        raise RuntimeError(f"Multiple matching ZIP assets found for {tag}")
    return matches[0] if matches else None


def read_package_metadata(package: bytes) -> dict[str, object]:
    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        names = {Path(name).name: name for name in archive.namelist()}
        meta_path = names.get("meta.json")
        if not meta_path:
            raise RuntimeError("Plugin package does not contain meta.json")
        return json.loads(archive.read(meta_path).decode("utf-8-sig"))


def build_package(plugin: dict[str, str]) -> dict[str, object]:
    versions: list[dict[str, str]] = []
    package_info_by_version: dict[str, dict[str, object]] = {}
    seen_versions: set[str] = set()

    for release in published_releases(plugin["repository"]):
        asset = matching_asset(release, plugin["asset_prefix"])
        if asset is None:
            continue

        source_url = str(asset.get("browser_download_url", ""))
        if not source_url:
            raise RuntimeError(f"Release asset has no download URL: {asset.get('name')}")

        package = request(source_url, accept="application/octet-stream")
        metadata = read_package_metadata(package)
        version = str(metadata.get("version", ""))

        if metadata.get("guid") != plugin["guid"]:
            raise RuntimeError(f"GUID mismatch in {source_url}")
        if metadata.get("name") != plugin["name"]:
            raise RuntimeError(f"Plugin name mismatch in {source_url}")
        expected_asset_name = f"{plugin['asset_prefix']}{version}.zip"
        if asset.get("name") != expected_asset_name:
            raise RuntimeError(
                f"Expected asset {expected_asset_name}, found {asset.get('name')}"
            )
        release_version = str(release.get("tag_name") or "").removeprefix("v")
        if release_version != version:
            raise RuntimeError(
                f"Release tag {release.get('tag_name')} does not match package version {version}"
            )
        if version in seen_versions:
            raise RuntimeError(f"Duplicate plugin version {version} in {plugin['repository']}")
        version_key(version)
        seen_versions.add(version)

        release_notes = str(release.get("body") or "").strip()
        versions.append(
            {
                "version": version,
                "changelog": release_notes or str(metadata.get("changelog") or ""),
                "targetAbi": str(metadata.get("targetAbi") or ""),
                "sourceUrl": source_url,
                # Jellyfin's plugin installer currently validates repository packages with MD5.
                "checksum": hashlib.md5(package).hexdigest(),  # noqa: S324
                "timestamp": str(
                    release.get("published_at")
                    or asset.get("updated_at")
                    or metadata.get("timestamp")
                    or ""
                ),
            }
        )

        package_info_by_version[version] = {
            "guid": str(metadata.get("guid") or ""),
            "name": str(metadata.get("name") or ""),
            "description": str(metadata.get("description") or ""),
            "overview": str(metadata.get("overview") or ""),
            "owner": str(metadata.get("owner") or ""),
            "category": str(metadata.get("category") or "General"),
        }

    if not versions:
        raise RuntimeError(f"No published plugin packages found for {plugin['repository']}")

    versions.sort(key=lambda item: version_key(item["version"]), reverse=True)
    package_info = package_info_by_version[versions[0]["version"]]
    package_info["versions"] = versions
    return package_info


def main() -> int:
    manifest = [build_package(plugin) for plugin in PLUGINS]
    output = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    MANIFEST_PATH.write_text(output, encoding="utf-8", newline="\n")
    print(f"Updated {MANIFEST_PATH} with {sum(len(item['versions']) for item in manifest)} versions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
