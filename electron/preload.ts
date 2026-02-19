import { contextBridge, ipcRenderer } from "electron";

// Expose a safe API to the renderer process
contextBridge.exposeInMainWorld("electronAPI", {
  platform: process.platform,
  onLogout: (callback: () => void) => {
    ipcRenderer.on("logout", callback);
  },
  onDeleteAccount: (callback: () => void) => {
    ipcRenderer.on("delete-account", callback);
  },
});
