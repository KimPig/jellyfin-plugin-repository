# KimPig Jellyfin Plugin Repository

Plugin catalog for Jellyfin plugins maintained by [KimPig](https://github.com/KimPig).

## Add this repository to Jellyfin

1. Open **Dashboard > Plugins > Repositories**.
2. Select **Add Repository**.
3. Enter `KimPig Jellyfin Plugins` as the repository name.
4. Enter the following URL:

```text
https://raw.githubusercontent.com/KimPig/jellyfin-plugin-repository/main/manifest.json
```

5. Save the repository, open the plugin catalog, and install the desired plugin.

## Available plugins

| Plugin | Description | Requirements |
| --- | --- | --- |
| [Attachment Optimizer](https://github.com/KimPig/jellyfin-plugin-attachment-optimizer) | Batches attachment extraction, deduplicates identical files, and manages plugin-owned cache data. | Jellyfin Server 12 |
| [Subtitle Font Bridge](https://github.com/KimPig/jellyfin-plugin-subtitle-font-bridge) | Supplies compatible Jellyfin Web builds with server-installed fonts referenced by ASS/SSA subtitles. | Jellyfin Server 12 and [KimPig's customized Jellyfin Web](https://github.com/KimPig/jellyfin-web) |

## Manifest updates

The repository manifest is generated from the plugins' published GitHub Releases. The updater downloads each release ZIP, reads its packaged `meta.json`, calculates the MD5 checksum required by Jellyfin, and writes the catalog entry.

The `Update plugin manifest` workflow runs every six hours and can also be started manually from GitHub Actions.
