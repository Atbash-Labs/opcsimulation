const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const Store = require('electron-store');

const store = new Store();

// Get the scripts directory
function getScriptsDir() {
    if (app.isPackaged) {
        return path.join(process.resourcesPath, 'scripts');
    }
    return path.join(__dirname, '..');
}

// Get exports directory
function getExportsDir() {
    const dir = path.join(app.getPath('userData'), 'exports');
    if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
    }
    return dir;
}

let mainWindow;
let runningProcesses = new Map();

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 1000,
        minHeight: 700,
        backgroundColor: '#1a1a2e',
        titleBarStyle: 'hiddenInset',
        frame: process.platform === 'darwin' ? true : false,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false
        }
    });

    mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));

    // Open DevTools in development
    if (!app.isPackaged) {
        mainWindow.webContents.openDevTools();
    }
}

app.whenReady().then(() => {
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    // Kill all running processes
    runningProcesses.forEach((proc, id) => {
        try { proc.kill(); } catch (e) {}
    });

    if (process.platform !== 'darwin') {
        app.quit();
    }
});

// Helper to run Python scripts
function runPythonScript(scriptName, args, taskId) {
    return new Promise((resolve, reject) => {
        const pythonPath = store.get('pythonPath', 'python3');
        const scriptPath = path.join(getScriptsDir(), scriptName);

        const proc = spawn(pythonPath, [scriptPath, ...args]);
        runningProcesses.set(taskId, proc);

        let stdout = '';
        let stderr = '';

        proc.stdout.on('data', (data) => {
            const text = data.toString();
            stdout += text;
            mainWindow?.webContents.send('task-log', { taskId, stream: 'stdout', text });
        });

        proc.stderr.on('data', (data) => {
            const text = data.toString();
            stderr += text;
            mainWindow?.webContents.send('task-log', { taskId, stream: 'stderr', text });
        });

        proc.on('close', (code) => {
            runningProcesses.delete(taskId);
            if (code === 0) {
                resolve({ success: true, stdout, stderr, code });
            } else {
                reject({ success: false, stdout, stderr, code });
            }
        });

        proc.on('error', (err) => {
            runningProcesses.delete(taskId);
            reject({ success: false, error: err.message });
        });
    });
}

// IPC Handlers

// Window controls
ipcMain.on('window-minimize', () => mainWindow?.minimize());
ipcMain.on('window-maximize', () => {
    if (mainWindow?.isMaximized()) {
        mainWindow.unmaximize();
    } else {
        mainWindow?.maximize();
    }
});
ipcMain.on('window-close', () => mainWindow?.close());

// Settings
ipcMain.handle('get-settings', () => {
    return {
        pythonPath: store.get('pythonPath', 'python3'),
        defaultSourceUrl: store.get('defaultSourceUrl', 'opc.tcp://localhost:4840'),
        defaultDestUrl: store.get('defaultDestUrl', 'opc.tcp://localhost:4840'),
        theme: store.get('theme', 'dark')
    };
});

ipcMain.handle('save-settings', (event, settings) => {
    Object.entries(settings).forEach(([key, value]) => {
        store.set(key, value);
    });
    return { success: true };
});

// Check server connectivity
ipcMain.handle('check-server', async (event, { url, username, password, securityPolicy, securityMode }) => {
    const taskId = `check-${Date.now()}`;
    mainWindow?.webContents.send('task-start', { taskId, operation: 'check-server', url });

    try {
        const args = ['--url', url];
        if (username) args.push('--username', username);
        if (password) args.push('--password', password);
        if (securityPolicy) args.push('--security-policy', securityPolicy);
        if (securityMode) args.push('--security-mode', securityMode);

        const result = await runPythonScript('check_server.py', args, taskId);
        mainWindow?.webContents.send('task-complete', { taskId, success: true });
        return { success: true, ...result };
    } catch (error) {
        mainWindow?.webContents.send('task-complete', { taskId, success: false });
        return { success: false, error: error.stderr || error.error || 'Unknown error' };
    }
});

// Export nodes
ipcMain.handle('export-nodes', async (event, { sourceUrl, outputFile, username, password, securityPolicy, securityMode }) => {
    const taskId = `export-${Date.now()}`;
    const filename = outputFile || `export-${Date.now()}.json`;
    const outputPath = path.join(getExportsDir(), filename);

    mainWindow?.webContents.send('task-start', { taskId, operation: 'export', sourceUrl });

    try {
        const args = ['--source-url', sourceUrl, '--output-file', outputPath];
        if (username) args.push('--username', username);
        if (password) args.push('--password', password);
        if (securityPolicy) args.push('--security-policy', securityPolicy);
        if (securityMode) args.push('--security-mode', securityMode);

        const result = await runPythonScript('export_opc_nodes.py', args, taskId);
        mainWindow?.webContents.send('task-complete', { taskId, success: true, filename });
        return { success: true, filename, outputPath, ...result };
    } catch (error) {
        mainWindow?.webContents.send('task-complete', { taskId, success: false });
        return { success: false, error: error.stderr || error.error || 'Unknown error' };
    }
});

// Import nodes
ipcMain.handle('import-nodes', async (event, { destinationUrl, inputFile, dryRun, username, password, securityPolicy, securityMode }) => {
    const taskId = `import-${Date.now()}`;

    mainWindow?.webContents.send('task-start', { taskId, operation: 'import', destinationUrl, dryRun });

    try {
        let inputPath = inputFile;
        if (!path.isAbsolute(inputFile)) {
            inputPath = path.join(getExportsDir(), inputFile);
        }

        if (!fs.existsSync(inputPath)) {
            throw { stderr: `File not found: ${inputFile}` };
        }

        const args = ['--destination-url', destinationUrl, '--input-file', inputPath];
        if (dryRun) args.push('--dry-run');
        if (username) args.push('--username', username);
        if (password) args.push('--password', password);
        if (securityPolicy) args.push('--security-policy', securityPolicy);
        if (securityMode) args.push('--security-mode', securityMode);

        const result = await runPythonScript('import_opc_nodes.py', args, taskId);
        mainWindow?.webContents.send('task-complete', { taskId, success: true });
        return { success: true, ...result };
    } catch (error) {
        mainWindow?.webContents.send('task-complete', { taskId, success: false });
        return { success: false, error: error.stderr || error.error || 'Unknown error' };
    }
});

// Create OPC server from export
ipcMain.handle('create-server', async (event, { inputFile, port, namespaceUri }) => {
    const taskId = `create-${Date.now()}`;

    mainWindow?.webContents.send('task-start', { taskId, operation: 'create-server', inputFile, port });

    try {
        let inputPath = inputFile;
        if (!path.isAbsolute(inputFile)) {
            inputPath = path.join(getExportsDir(), inputFile);
        }

        if (!fs.existsSync(inputPath)) {
            throw { stderr: `File not found: ${inputFile}` };
        }

        const pythonPath = store.get('pythonPath', 'python3');
        const scriptPath = path.join(getScriptsDir(), 'create_nodes_from_export.py');
        const args = ['--input-file', inputPath, '--port', String(port || 4841)];
        if (namespaceUri) args.push('--namespace-uri', namespaceUri);

        const proc = spawn(pythonPath, [scriptPath, ...args]);
        runningProcesses.set(taskId, proc);

        proc.stdout.on('data', (data) => {
            mainWindow?.webContents.send('task-log', { taskId, stream: 'stdout', text: data.toString() });
        });

        proc.stderr.on('data', (data) => {
            mainWindow?.webContents.send('task-log', { taskId, stream: 'stderr', text: data.toString() });
        });

        proc.on('close', (code) => {
            runningProcesses.delete(taskId);
            mainWindow?.webContents.send('task-complete', { taskId, success: code === 0 });
        });

        return { success: true, taskId, message: `Server starting on port ${port || 4841}` };
    } catch (error) {
        return { success: false, error: error.stderr || error.error || 'Unknown error' };
    }
});

// Start test server
ipcMain.handle('start-test-server', async (event, { port }) => {
    const taskId = `test-server-${Date.now()}`;

    mainWindow?.webContents.send('task-start', { taskId, operation: 'test-server', port });

    try {
        const pythonPath = store.get('pythonPath', 'python3');
        const scriptPath = path.join(getScriptsDir(), 'test_server.py');
        const args = port ? ['--port', String(port)] : [];

        const proc = spawn(pythonPath, [scriptPath, ...args]);
        runningProcesses.set(taskId, proc);

        proc.stdout.on('data', (data) => {
            mainWindow?.webContents.send('task-log', { taskId, stream: 'stdout', text: data.toString() });
        });

        proc.stderr.on('data', (data) => {
            mainWindow?.webContents.send('task-log', { taskId, stream: 'stderr', text: data.toString() });
        });

        proc.on('close', (code) => {
            runningProcesses.delete(taskId);
            mainWindow?.webContents.send('task-complete', { taskId, success: code === 0 });
        });

        return { success: true, taskId, message: `Test server starting on port ${port || 4840}` };
    } catch (error) {
        return { success: false, error: error.message };
    }
});

// Stop process
ipcMain.handle('stop-process', (event, taskId) => {
    const proc = runningProcesses.get(taskId);
    if (proc) {
        proc.kill();
        runningProcesses.delete(taskId);
        return { success: true };
    }
    return { success: false, error: 'Process not found' };
});

// List export files
ipcMain.handle('list-exports', () => {
    try {
        const exportsDir = getExportsDir();
        const files = fs.readdirSync(exportsDir)
            .filter(f => f.endsWith('.json'))
            .map(filename => {
                const filePath = path.join(exportsDir, filename);
                const stats = fs.statSync(filePath);
                return {
                    filename,
                    path: filePath,
                    size: stats.size,
                    created: stats.birthtime,
                    modified: stats.mtime
                };
            })
            .sort((a, b) => new Date(b.modified) - new Date(a.modified));

        return { success: true, files };
    } catch (error) {
        return { success: false, error: error.message };
    }
});

// Read export file
ipcMain.handle('read-export', (event, filename) => {
    try {
        let filePath = filename;
        if (!path.isAbsolute(filename)) {
            filePath = path.join(getExportsDir(), filename);
        }

        if (!fs.existsSync(filePath)) {
            return { success: false, error: 'File not found' };
        }

        const content = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
        return { success: true, content };
    } catch (error) {
        return { success: false, error: error.message };
    }
});

// Delete export file
ipcMain.handle('delete-export', (event, filename) => {
    try {
        const filePath = path.join(getExportsDir(), filename);
        if (!fs.existsSync(filePath)) {
            return { success: false, error: 'File not found' };
        }

        fs.unlinkSync(filePath);
        return { success: true };
    } catch (error) {
        return { success: false, error: error.message };
    }
});

// Open file dialog
ipcMain.handle('open-file-dialog', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
        properties: ['openFile'],
        filters: [{ name: 'JSON Files', extensions: ['json'] }]
    });

    if (result.canceled) {
        return { success: false, canceled: true };
    }

    return { success: true, filePath: result.filePaths[0] };
});

// Save file dialog
ipcMain.handle('save-file-dialog', async (event, defaultName) => {
    const result = await dialog.showSaveDialog(mainWindow, {
        defaultPath: defaultName,
        filters: [{ name: 'JSON Files', extensions: ['json'] }]
    });

    if (result.canceled) {
        return { success: false, canceled: true };
    }

    return { success: true, filePath: result.filePath };
});

// Copy sample export
ipcMain.handle('copy-sample-export', () => {
    try {
        const sampleFile = path.join(getScriptsDir(), 'opc_nodes_export.json');
        if (fs.existsSync(sampleFile)) {
            const destFile = path.join(getExportsDir(), 'sample-opc_nodes_export.json');
            fs.copyFileSync(sampleFile, destFile);
            return { success: true, filename: 'sample-opc_nodes_export.json' };
        }
        return { success: false, error: 'Sample export file not found' };
    } catch (error) {
        return { success: false, error: error.message };
    }
});

// Open external link
ipcMain.on('open-external', (event, url) => {
    shell.openExternal(url);
});

// Get app info
ipcMain.handle('get-app-info', () => {
    return {
        version: app.getVersion(),
        platform: process.platform,
        arch: process.arch,
        electron: process.versions.electron,
        node: process.versions.node,
        exportsDir: getExportsDir(),
        scriptsDir: getScriptsDir()
    };
});
