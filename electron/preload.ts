/** @format */

import { contextBridge, ipcRenderer } from "electron"

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld("electronAPI", {
  platform: process.platform,
  openFileDialog: () => ipcRenderer.invoke("dialog:openFile"),
  readFile: (filePath: string) => ipcRenderer.invoke("fs:readFile", filePath),
})
