import { app, BrowserWindow } from "electron";
import { spawn, ChildProcess, execSync } from "child_process";
import * as path from "path";
import * as http from "http";
import * as net from "net";
import * as fs from "fs";

let backendProcess: ChildProcess | null = null;
let mainWindow: BrowserWindow | null = null;
let backendPort = 8000;

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
    const env = {
      ...process.env,
      OPEN_RECRUITER_DATA_DIR: getDataDir(),
    };

    console.log(`[electron] Starting backend: ${command} ${args.join(" ")}`);
    console.log(`[electron] Data dir: ${env.OPEN_RECRUITER_DATA_DIR}`);

    const proc = spawn(command, args, {
      cwd,
      stdio: ["pipe", "pipe", "pipe"],
      env,
    });

    proc.stdout?.on("data", (data: Buffer) => {
      console.log(`[backend] ${data.toString().trim()}`);
    });

    proc.stderr?.on("data", (data: Buffer) => {
      console.log(`[backend] ${data.toString().trim()}`);
    });

    proc.on("close", (code: number | null) => {
      console.log(`[backend] exited with code ${code}`);
    });

    return proc;
  }

  function waitForBackend(timeout = 30000): Promise<void> {
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

  function createWindow() {
    mainWindow = new BrowserWindow({
      width: 1400,
      height: 900,
      minWidth: 900,
      minHeight: 600,
      title: "Open Recruiter",
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

    try {
      await waitForBackend();
      console.log("[electron] Backend is ready.");
    } catch (err) {
      console.error("[electron] Failed to start backend:", err);
    }

    createWindow();
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
