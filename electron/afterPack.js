// afterPack hook — ad-hoc sign ALL Mach-O binaries in the macOS .app bundle.
// macOS Tahoe+ enforces strict code-signature checks on nested executables.
// `codesign --deep` is deprecated and unreliable, so we sign each binary
// individually (innermost first) before signing the top-level .app.
const { execSync } = require("child_process");
const path = require("path");
const fs = require("fs");

/**
 * Recursively collect all files under `dir` that match one of the given
 * extensions, or are executable Mach-O binaries (no extension).
 */
function collectSignableFiles(dir) {
  const results = [];
  if (!fs.existsSync(dir)) return results;

  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      // Recurse, but skip symlinks to avoid loops
      if (!entry.isSymbolicLink()) {
        results.push(...collectSignableFiles(fullPath));
      }
    } else if (entry.isFile()) {
      const ext = path.extname(entry.name).toLowerCase();
      if ([".dylib", ".so", ".node"].includes(ext)) {
        results.push(fullPath);
      } else if (!ext || ext === "") {
        // Check if it's a Mach-O binary (no extension)
        try {
          const fd = fs.openSync(fullPath, "r");
          const buf = Buffer.alloc(4);
          fs.readSync(fd, buf, 0, 4, 0);
          fs.closeSync(fd);
          const magic = buf.readUInt32LE(0);
          // Mach-O magic numbers: MH_MAGIC_64, MH_CIGAM_64, FAT_MAGIC, FAT_CIGAM
          if ([0xfeedfacf, 0xcffaedfe, 0xbebafeca, 0xcafebabe].includes(magic)) {
            results.push(fullPath);
          }
        } catch {
          // Not readable or too small — skip
        }
      }
    }
  }
  return results;
}

exports.default = async function (context) {
  if (context.electronPlatformName !== "darwin") return;

  const appName = context.packager.appInfo.productFilename;
  const appPath = path.join(context.appOutDir, `${appName}.app`);
  const resourcesDir = path.join(appPath, "Contents", "Resources");

  // 1. Sign all nested Mach-O binaries inside Resources (backend + frameworks)
  const binaries = collectSignableFiles(resourcesDir);
  console.log(`[afterPack] Found ${binaries.length} signable binaries in Resources`);

  let signed = 0;
  for (const bin of binaries) {
    try {
      execSync(
        `codesign --force --sign - --timestamp=none "${bin}"`,
        { stdio: "pipe" }
      );
      signed++;
    } catch (err) {
      // Some files may not be Mach-O despite matching heuristics — skip
      console.log(`[afterPack] Skipped (not signable): ${path.relative(appPath, bin)}`);
    }
  }
  console.log(`[afterPack] Signed ${signed}/${binaries.length} binaries`);

  // 2. Sign the Electron framework and helpers
  const frameworksDir = path.join(appPath, "Contents", "Frameworks");
  const frameworkBinaries = collectSignableFiles(frameworksDir);
  console.log(`[afterPack] Found ${frameworkBinaries.length} signable binaries in Frameworks`);

  for (const bin of frameworkBinaries) {
    try {
      execSync(
        `codesign --force --sign - --timestamp=none "${bin}"`,
        { stdio: "pipe" }
      );
    } catch {
      // skip
    }
  }

  // 3. Sign the top-level .app bundle
  console.log(`[afterPack] Signing app bundle: ${appPath}`);
  execSync(`codesign --force --sign - --timestamp=none "${appPath}"`, {
    stdio: "inherit",
  });
  console.log("[afterPack] Ad-hoc signing complete.");
};
