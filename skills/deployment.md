# Deployment — Version Bump + CI Release

## Prerequisite

User MUST explicitly approve the version number — CLAUDE.md hard rule. **Never** bump on your own.

## Release flow

1. **Bump version** in both files (must stay in sync):
   - `package.json` → `"version": "X.Y.Z"`
   - `frontend/package.json` → `"version": "X.Y.Z"`

2. **Update README.md**:
   - Version badge: `<img src="https://img.shields.io/badge/RELEASE-VX.Y.Z-blue" />`
   - Add row to releases table:
     ```
     | [VX.Y.Z](https://github.com/miao4ai/open_recruiter/releases/tag/vX.Y.Z) | YYYY-MM-DD | <one-line highlights> |
     ```

3. **Update `document/release.md`** — add a full section above the previous version.

4. **Commit and push the bump**:
   ```bash
   git add package.json frontend/package.json README.md document/release.md
   git commit -m "Bump version to X.Y.Z + release notes"
   git push
   ```

5. **Tag and push to trigger CI**:
   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

6. **Verify CI started**:
   ```bash
   gh run list --repo miao4ai/open_recruiter --limit 1
   ```

## If the tag already exists on the remote

```bash
gh release delete vX.Y.Z --yes --repo miao4ai/open_recruiter
git push origin --delete vX.Y.Z
git tag -d vX.Y.Z
git tag vX.Y.Z
git push origin vX.Y.Z
```

## CI output

GitHub Actions builds **exactly 3 artifacts** (~10 min total) and attaches them to the release:

| Platform | Filename |
|----------|----------|
| macOS (Apple Silicon) | `Open.Recruiter-X.Y.Z-arm64.dmg` |
| Windows | `Open.Recruiter.Setup.X.Y.Z.exe` |
| Linux | `Open.Recruiter-X.Y.Z.AppImage` |

Configured in `electron/electron-builder.json`. Triggered by tag push matching `v*.*.*` (see `.github/workflows/release.yml`).

## macOS Gatekeeper note

App is NOT notarized — users get "damaged" warnings on first launch. README documents the workaround:
```bash
xattr -cr /Applications/Open\ Recruiter.app
```

To enable notarization later: add 3 GitHub secrets (`APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID`), flip `notarize: true` in `electron-builder.json`.
