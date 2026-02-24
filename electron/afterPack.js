// afterPack hook — sign nested Mach-O binaries in the macOS .app bundle.
//
// When CSC_LINK is set (CI with Apple Developer cert), electron-builder handles
// top-level signing + notarization. This hook pre-signs nested binaries in
// Resources (PyInstaller backend) that electron-builder doesn't know about.
//
// When CSC_LINK is NOT set (local dev), falls back to ad-hoc signing everything.
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

function getSignIdentity() {
  // When CSC_LINK is set, electron-builder imports the cert into a temp keychain.
  // We use the Developer ID identity for nested binaries; electron-builder
  // handles the top-level .app and Electron frameworks.
  if (process.env.CSC_LINK) {
    return "Developer ID Application";
  }
  return "-"; // ad-hoc fallback
}

function signFile(filePath, identity, entitlements) {
  const entFlag = entitlements ? `--entitlements "${entitlements}"` : "";
  const tsFlag = identity === "-" ? "--timestamp=none" : "";
  execSync(
    `codesign --force --sign "${identity}" ${tsFlag} ${entFlag} "${filePath}"`,
    { stdio: "pipe" }
  );
}

exports.default = async function (context) {
  if (context.electronPlatformName !== "darwin") return;

  const appName = context.packager.appInfo.productFilename;
  const appPath = path.join(context.appOutDir, `${appName}.app`);
  const entitlements = path.join(__dirname, "entitlements.mac.plist");
  const identity = getSignIdentity();
  const hasRealCert = identity !== "-";

  console.log(`[afterPack] Signing mode: ${hasRealCert ? "Developer ID" : "ad-hoc"}`);

  // Sign all nested Mach-O binaries inside Resources (PyInstaller backend).
  // electron-builder only signs Electron's own frameworks — it does NOT sign
  // extraResources, so we must sign the backend binaries ourselves.
  const resourcesDir = path.join(appPath, "Contents", "Resources");
  const resBinaries = collectSignableFiles(resourcesDir);
  console.log(`[afterPack] Found ${resBinaries.length} signable binaries in Resources`);

  let signed = 0;
  for (const bin of resBinaries) {
    try {
      signFile(bin, identity);
      signed++;
    } catch {
      console.log(`[afterPack] Skipped: ${path.relative(appPath, bin)}`);
    }
  }
  console.log(`[afterPack] Signed ${signed}/${resBinaries.length} resource binaries`);

  // When using a real cert, electron-builder handles Frameworks, helpers,
  // and the top-level .app — we only needed to sign extraResources above.
  if (hasRealCert) {
    console.log("[afterPack] Real cert detected — electron-builder will sign the rest.");
    return;
  }

  // --- Ad-hoc fallback (no cert): sign everything ourselves ---

  const frameworksDir = path.join(appPath, "Contents", "Frameworks");
  const fwBinaries = collectSignableFiles(frameworksDir);
  for (const bin of fwBinaries) {
    try { signFile(bin, identity); } catch {}
  }

  if (fs.existsSync(frameworksDir)) {
    for (const name of fs.readdirSync(frameworksDir)) {
      const fwPath = path.join(frameworksDir, name);
      if (name.endsWith(".framework") && fs.statSync(fwPath).isDirectory()) {
        try { signFile(fwPath, identity); } catch {}
      }
    }
    for (const name of fs.readdirSync(frameworksDir)) {
      if (name.endsWith(".app")) {
        try { signFile(path.join(frameworksDir, name), identity, entitlements); } catch {}
      }
    }
  }

  execSync(
    `codesign --force --sign - --timestamp=none --entitlements "${entitlements}" "${appPath}"`,
    { stdio: "inherit" }
  );
  console.log("[afterPack] Ad-hoc signing complete.");
};
