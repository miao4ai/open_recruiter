import { app, BrowserWindow, Menu, dialog, nativeImage } from "electron";
import { spawn, ChildProcess, execSync } from "child_process";
import * as path from "path";
import * as http from "http";
import * as net from "net";
import * as fs from "fs";

let backendProcess: ChildProcess | null = null;
let mainWindow: BrowserWindow | null = null;
let backendPort = 8000;
let backendLogPath = "";

// ---------------------------------------------------------------------------
// Single-instance lock — prevent multiple app windows
// ---------------------------------------------------------------------------
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  // -----------------------------------------------------------------------
  // Helpers
  // -----------------------------------------------------------------------

  function findFreePort(): Promise<number> {
    return new Promise((resolve, reject) => {
      const server = net.createServer();
      server.listen(0, "127.0.0.1", () => {
        const port = (server.address() as net.AddressInfo).port;
        server.close(() => resolve(port));
      });
      server.on("error", reject);
    });
  }

  function getDataDir(): string {
    const dataDir = path.join(app.getPath("appData"), "OpenRecruiter");
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }
    return dataDir;
  }

  function getBackendCommand(): {
    command: string;
    args: string[];
    cwd: string;
  } {
    if (app.isPackaged) {
      // Production: PyInstaller-bundled executable in extraResources
      const exeName =
        process.platform === "win32" ? "backend.exe" : "backend";
      const exePath = path.join(process.resourcesPath, "backend", exeName);
      // Ensure execute permission on macOS/Linux (extraResources may strip it)
      if (process.platform !== "win32") {
        try { fs.chmodSync(exePath, 0o755); } catch {}
      }
      return {
        command: exePath,
        args: [String(backendPort)],
        cwd: path.dirname(exePath),
      };
    } else {
      // Dev mode: run via Python
      const backendDir = path.join(__dirname, "..", "backend");
      const pythonCmd = process.platform === "win32" ? "python" : "python3";
      return {
        command: pythonCmd,
        args: [
          "-m",
          "uvicorn",
          "app.main:app",
          "--host",
          "127.0.0.1",
          "--port",
          String(backendPort),
        ],
        cwd: backendDir,
      };
    }
  }

  function startBackend(): ChildProcess {
    const { command, args, cwd } = getBackendCommand();
    const dataDir = getDataDir();
    const env = {
      ...process.env,
      OPEN_RECRUITER_DATA_DIR: dataDir,
    };

    // Write backend logs to a file for diagnostics
    backendLogPath = path.join(dataDir, "backend.log");
    const logStream = fs.createWriteStream(backendLogPath, { flags: "w" });
    logStream.write(`[${new Date().toISOString()}] Starting: ${command} ${args.join(" ")}\n`);
    logStream.write(`[${new Date().toISOString()}] CWD: ${cwd}\n\n`);

    console.log(`[electron] Starting backend: ${command} ${args.join(" ")}`);
    console.log(`[electron] Log file: ${backendLogPath}`);

    const proc = spawn(command, args, {
      cwd,
      stdio: ["pipe", "pipe", "pipe"],
      env,
    });

    proc.stdout?.on("data", (data: Buffer) => {
      const text = data.toString();
      console.log(`[backend] ${text.trim()}`);
      logStream.write(text);
    });

    proc.stderr?.on("data", (data: Buffer) => {
      const text = data.toString();
      console.log(`[backend] ${text.trim()}`);
      logStream.write(text);
    });

    proc.on("close", (code: number | null) => {
      console.log(`[backend] exited with code ${code}`);
      logStream.write(`\n[Process exited with code ${code}]\n`);
      logStream.end();
    });

    return proc;
  }

  function waitForBackend(timeout = 120000): Promise<void> {
    const start = Date.now();
    return new Promise((resolve, reject) => {
      const check = () => {
        http
          .get(`http://127.0.0.1:${backendPort}/health`, (res) => {
            if (res.statusCode === 200) resolve();
            else retry();
          })
          .on("error", retry);
      };

      const retry = () => {
        if (Date.now() - start > timeout) {
          reject(new Error("Backend did not start in time"));
        } else {
          setTimeout(check, 500);
        }
      };

      check();
    });
  }

  function killBackend() {
    if (!backendProcess || backendProcess.pid == null) return;
    try {
      if (process.platform === "win32") {
        // Windows: kill entire process tree
        execSync(`taskkill /T /F /PID ${backendProcess.pid}`, {
          stdio: "ignore",
        });
      } else {
        backendProcess.kill("SIGTERM");
      }
    } catch {
      // Process may already be dead
    }
    backendProcess = null;
  }

  function buildAppMenu() {
    const template: Electron.MenuItemConstructorOptions[] = [
      {
        label: "Account",
        submenu: [
          {
            label: "Log Out",
            click: () => {
              mainWindow?.webContents.send("logout");
            },
          },
          {
            label: "Delete Account",
            click: async () => {
              const result = await dialog.showMessageBox(mainWindow!, {
                type: "warning",
                buttons: ["Cancel", "Delete"],
                defaultId: 0,
                cancelId: 0,
                title: "Delete Account",
                message:
                  "Are you sure you want to delete your account? This action cannot be undone. All your data will be permanently removed.",
              });
              if (result.response === 1) {
                mainWindow?.webContents.send("delete-account");
              }
            },
          },
          { type: "separator" },
          {
            label: "Exit",
            accelerator: process.platform === "darwin" ? "Cmd+Q" : "Alt+F4",
            click: () => {
              app.quit();
            },
          },
        ],
      },
      {
        label: "Edit",
        submenu: [
          { role: "undo" },
          { role: "redo" },
          { type: "separator" },
          { role: "cut" },
          { role: "copy" },
          { role: "paste" },
          { role: "selectAll" },
        ],
      },
      {
        label: "View",
        submenu: [
          { role: "reload" },
          { role: "forceReload" },
          { role: "toggleDevTools" },
          { type: "separator" },
          { role: "resetZoom" },
          { role: "zoomIn" },
          { role: "zoomOut" },
          { type: "separator" },
          { role: "togglefullscreen" },
        ],
      },
    ];

    const menu = Menu.buildFromTemplate(template);
    Menu.setApplicationMenu(menu);
  }

  function createWindow() {
    // Use .ico on Windows for proper taskbar/title bar icon, .png elsewhere
    const iconExt = process.platform === "win32" ? "avartar.ico" : "avartar.png";
    const iconPath = app.isPackaged
      ? path.join(process.resourcesPath, "images", iconExt)
      : path.join(__dirname, "..", "images", iconExt);
    const appIcon = nativeImage.createFromPath(iconPath);

    mainWindow = new BrowserWindow({
      width: 1400,
      height: 900,
      minWidth: 900,
      minHeight: 600,
      title: "Open Recruiter",
      icon: appIcon,
      webPreferences: {
        preload: path.join(__dirname, "preload.js"),
        contextIsolation: true,
        nodeIntegration: false,
      },
    });

    if (!app.isPackaged) {
      // Dev: try Vite dev server, fall back to FastAPI
      mainWindow.loadURL("http://localhost:5173").catch(() => {
        mainWindow?.loadURL(`http://127.0.0.1:${backendPort}`);
      });
    } else {
      // Production: load through FastAPI (serves static files + API)
      mainWindow.loadURL(`http://127.0.0.1:${backendPort}`);
    }

    mainWindow.on("closed", () => {
      mainWindow = null;
    });
  }

  // -----------------------------------------------------------------------
  // App lifecycle
  // -----------------------------------------------------------------------

  app.on("ready", async () => {
    // Dev mode: fixed port 8000 (matches Vite proxy config)
    // Prod mode: pick a free port to avoid conflicts
    if (app.isPackaged) {
      backendPort = await findFreePort();
    }
    console.log(`[electron] Using port ${backendPort}`);

    backendProcess = startBackend();

    let backendReady = false;
    try {
      await waitForBackend();
      console.log("[electron] Backend is ready.");
      backendReady = true;
    } catch (err) {
      console.error("[electron] Failed to start backend:", err);
    }

    createWindow();
    buildAppMenu();

    if (!backendReady && mainWindow) {
      mainWindow.loadURL(
        `data:text/html;charset=utf-8,${encodeURIComponent(`
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Open Recruiter - Error</title></head>
<body style="font-family:system-ui;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#1a1a2e;color:#e0e0e0">
<div style="text-align:center;max-width:500px">
  <h1 style="color:#e74c3c">Backend failed to start</h1>
  <p>The backend process did not respond within 120 seconds.</p>
  <p style="color:#aaa;font-size:13px;word-break:break-all">Log file: ${backendLogPath.replace(/\\/g, "/")}</p>
  <p style="color:#888;font-size:13px">Open the log file above to see the error details.</p>
</div>
</body></html>`)}`
      );
    }
  });

  app.on("window-all-closed", () => {
    if (process.platform !== "darwin") {
      app.quit();
    }
  });

  app.on("activate", () => {
    if (mainWindow === null) {
      createWindow();
    }
  });

  app.on("before-quit", () => {
    killBackend();
  });
}
