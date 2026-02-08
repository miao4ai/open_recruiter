import { app, BrowserWindow } from "electron";
import { spawn, ChildProcess } from "child_process";
import * as path from "path";
import * as http from "http";

const BACKEND_PORT = 8000;
const DEV_FRONTEND_URL = `http://localhost:5173`;
const BACKEND_URL = `http://localhost:${BACKEND_PORT}`;

let backendProcess: ChildProcess | null = null;
let mainWindow: BrowserWindow | null = null;

function startBackend(): ChildProcess {
  const backendDir = path.join(__dirname, "..", "backend");
  const proc = spawn(
    "python3",
    ["-m", "uvicorn", "app.main:app", "--port", String(BACKEND_PORT)],
    {
      cwd: backendDir,
      stdio: ["pipe", "pipe", "pipe"],
    }
  );

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

function waitForBackend(timeout = 15000): Promise<void> {
  const start = Date.now();
  return new Promise((resolve, reject) => {
    const check = () => {
      http
        .get(`${BACKEND_URL}/health`, (res) => {
          if (res.statusCode === 200) {
            resolve();
          } else {
            retry();
          }
        })
        .on("error", retry);
    };

    const retry = () => {
      if (Date.now() - start > timeout) {
        reject(new Error("Backend did not start in time"));
      } else {
        setTimeout(check, 300);
      }
    };

    check();
  });
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

  // In dev mode, load from Vite dev server; in production, load built files
  const isDev = !app.isPackaged;
  if (isDev) {
    mainWindow.loadURL(DEV_FRONTEND_URL);
  } else {
    mainWindow.loadFile(path.join(__dirname, "..", "frontend", "dist", "index.html"));
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

app.on("ready", async () => {
  console.log("Starting backend...");
  backendProcess = startBackend();

  try {
    await waitForBackend();
    console.log("Backend is ready.");
  } catch (err) {
    console.error("Failed to start backend:", err);
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
  if (backendProcess) {
    backendProcess.kill("SIGTERM");
    backendProcess = null;
  }
});
