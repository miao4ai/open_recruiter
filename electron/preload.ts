import { contextBridge } from "electron";

// Expose a safe API to the renderer process
contextBridge.exposeInMainWorld("electronAPI", {
  platform: process.platform,
});
