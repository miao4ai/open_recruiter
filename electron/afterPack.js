// afterPack hook — ad-hoc sign ALL Mach-O binaries in the macOS .app bundle.
// macOS Tahoe+ enforces strict code-signature checks on nested executables.
// `codesign --deep` is deprecated and unreliable, so we sign each binary
// individually (innermost first) before signing the top-level .app with
// entitlements.
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

function signFile(filePath, entitlements) {
  const entFlag = entitlements ? `--entitlements "${entitlements}"` : "";
  execSync(
    `codesign --force --sign - --timestamp=none ${entFlag} "${filePath}"`,
    { stdio: "pipe" }
  );
}

exports.default = async function (context) {
  if (context.electronPlatformName !== "darwin") return;

  const appName = context.packager.appInfo.productFilename;
  const appPath = path.join(context.appOutDir, `${appName}.app`);
  const entitlements = path.join(__dirname, "entitlements.mac.plist");

  // 1. Sign all nested Mach-O binaries inside Resources (backend + data)
  const resourcesDir = path.join(appPath, "Contents", "Resources");
  const resBinaries = collectSignableFiles(resourcesDir);
  console.log(`[afterPack] Found ${resBinaries.length} signable binaries in Resources`);

  let signed = 0;
  for (const bin of resBinaries) {
    try {
      signFile(bin);
      signed++;
    } catch {
      console.log(`[afterPack] Skipped: ${path.relative(appPath, bin)}`);
    }
  }
  console.log(`[afterPack] Signed ${signed}/${resBinaries.length} resource binaries`);

  // 2. Sign Electron framework binaries
  const frameworksDir = path.join(appPath, "Contents", "Frameworks");
  const fwBinaries = collectSignableFiles(frameworksDir);
  console.log(`[afterPack] Found ${fwBinaries.length} signable binaries in Frameworks`);

  for (const bin of fwBinaries) {
    try {
      signFile(bin);
    } catch {
      // skip
    }
  }

  // 3. Sign .framework bundles themselves (required on Tahoe+)
  if (fs.existsSync(frameworksDir)) {
    const fwEntries = fs.readdirSync(frameworksDir);
    for (const name of fwEntries) {
      const fwPath = path.join(frameworksDir, name);
      if (name.endsWith(".framework") && fs.statSync(fwPath).isDirectory()) {
        try {
          signFile(fwPath);
          console.log(`[afterPack] Signed framework: ${name}`);
        } catch {
          // skip
        }
      }
    }
  }

  // 4. Sign helper apps (e.g. crashpad, renderer)
  const helpersDir = path.join(frameworksDir);
  if (fs.existsSync(helpersDir)) {
    const helperApps = fs.readdirSync(helpersDir).filter((n) => n.endsWith(".app"));
    for (const helper of helperApps) {
      const helperPath = path.join(helpersDir, helper);
      try {
        signFile(helperPath, entitlements);
        console.log(`[afterPack] Signed helper: ${helper}`);
      } catch {
        // skip
      }
    }
  }

  // 5. Sign the top-level .app with entitlements
  console.log(`[afterPack] Signing app bundle with entitlements: ${appPath}`);
  execSync(
    `codesign --force --sign - --timestamp=none --entitlements "${entitlements}" "${appPath}"`,
    { stdio: "inherit" }
  );
  console.log("[afterPack] Ad-hoc signing complete.");

  // 6. Verify the signature
  try {
    execSync(`codesign --verify --deep --strict "${appPath}"`, { stdio: "inherit" });
    console.log("[afterPack] Signature verification passed.");
  } catch {
    console.warn("[afterPack] WARNING: Signature verification failed — app may be blocked by Gatekeeper.");
  }
};
