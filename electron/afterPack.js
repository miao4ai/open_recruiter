// afterPack hook — ad-hoc sign the macOS .app bundle before DMG creation.
// This avoids the "damaged and can't be opened" Gatekeeper error for unsigned apps.
const { execSync } = require("child_process");
const path = require("path");

exports.default = async function (context) {
  if (context.electronPlatformName !== "darwin") return;

  const appName = context.packager.appInfo.productFilename;
  const appPath = path.join(context.appOutDir, `${appName}.app`);

  console.log(`[afterPack] Ad-hoc signing: ${appPath}`);
  execSync(`codesign --force --deep --sign - "${appPath}"`, {
    stdio: "inherit",
  });
  console.log("[afterPack] Ad-hoc signing complete.");
};
