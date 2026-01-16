const { contextBridge, ipcRenderer } = require('electron');

// Expose protected APIs to renderer
contextBridge.exposeInMainWorld('api', {
    // Window controls
    minimize: () => ipcRenderer.send('window-minimize'),
    maximize: () => ipcRenderer.send('window-maximize'),
    close: () => ipcRenderer.send('window-close'),

    // Settings
    getSettings: () => ipcRenderer.invoke('get-settings'),
    saveSettings: (settings) => ipcRenderer.invoke('save-settings', settings),

    // OPC Operations
    checkServer: (params) => ipcRenderer.invoke('check-server', params),
    exportNodes: (params) => ipcRenderer.invoke('export-nodes', params),
    importNodes: (params) => ipcRenderer.invoke('import-nodes', params),
    createServer: (params) => ipcRenderer.invoke('create-server', params),
    startTestServer: (params) => ipcRenderer.invoke('start-test-server', params),
    stopProcess: (taskId) => ipcRenderer.invoke('stop-process', taskId),

    // File operations
    listExports: () => ipcRenderer.invoke('list-exports'),
    readExport: (filename) => ipcRenderer.invoke('read-export', filename),
    deleteExport: (filename) => ipcRenderer.invoke('delete-export', filename),
    openFileDialog: () => ipcRenderer.invoke('open-file-dialog'),
    saveFileDialog: (defaultName) => ipcRenderer.invoke('save-file-dialog', defaultName),
    copySampleExport: () => ipcRenderer.invoke('copy-sample-export'),

    // App info
    getAppInfo: () => ipcRenderer.invoke('get-app-info'),
    openExternal: (url) => ipcRenderer.send('open-external', url),

    // Event listeners
    onTaskStart: (callback) => {
        ipcRenderer.on('task-start', (event, data) => callback(data));
    },
    onTaskLog: (callback) => {
        ipcRenderer.on('task-log', (event, data) => callback(data));
    },
    onTaskComplete: (callback) => {
        ipcRenderer.on('task-complete', (event, data) => callback(data));
    },

    // Remove listeners
    removeAllListeners: () => {
        ipcRenderer.removeAllListeners('task-start');
        ipcRenderer.removeAllListeners('task-log');
        ipcRenderer.removeAllListeners('task-complete');
    }
});
