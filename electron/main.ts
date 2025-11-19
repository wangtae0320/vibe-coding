/** @format */

import { app, BrowserWindow, dialog, ipcMain } from "electron"
import * as path from "path"
import * as fs from "fs"

let mainWindow: BrowserWindow | null = null

const isDev = process.env.NODE_ENV === "development" || !app.isPackaged

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
    },
  })

  if (isDev) {
    mainWindow.loadURL("http://localhost:3000")
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, "../dist/index.html"))
  }

  mainWindow.on("closed", () => {
    mainWindow = null
  })
}

app.whenReady().then(() => {
  createWindow()

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })

  // IPC handlers
  ipcMain.handle("dialog:openFile", async () => {
    const result = await dialog.showOpenDialog({
      properties: ["openFile"],
      filters: [
        { name: "텍스트 파일", extensions: ["txt", "md", "js", "ts", "jsx", "tsx", "json", "xml", "html", "css"] },
        { name: "모든 파일", extensions: ["*"] },
      ],
    })

    if (!result.canceled && result.filePaths.length > 0) {
      return result.filePaths[0]
    }
    return null
  })

  ipcMain.handle("fs:readFile", async (event, filePath: string) => {
    try {
      const content = fs.readFileSync(filePath, "utf-8")
      return content
    } catch (error) {
      throw error
    }
  })
})

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit()
  }
})
