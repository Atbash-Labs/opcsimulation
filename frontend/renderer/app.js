// OPC Simulation Frontend Application

// State
let currentSection = 'dashboard';
let settings = {};
let runningTasks = new Map();
let activities = [];
let loadedExportData = null;
let selectedNode = null;

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    initTitleBar();
    initNavigation();
    initForms();
    initEventListeners();
    await loadSettings();
    await refreshFileList();
    await loadAppInfo();
});

// Title Bar Controls
function initTitleBar() {
    const platform = navigator.platform.toLowerCase();
    if (platform.includes('mac')) {
        document.getElementById('titlebar').style.display = 'none';
        document.querySelector('.app-container').style.height = '100vh';
    }

    document.getElementById('btn-minimize')?.addEventListener('click', () => api.minimize());
    document.getElementById('btn-maximize')?.addEventListener('click', () => api.maximize());
    document.getElementById('btn-close')?.addEventListener('click', () => api.close());
}

// Navigation
function initNavigation() {
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const section = btn.dataset.section;
            if (section) showSection(section);
        });
    });
}

function showSection(sectionId) {
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));

    document.getElementById(`section-${sectionId}`)?.classList.add('active');
    document.querySelector(`[data-section="${sectionId}"]`)?.classList.add('active');

    currentSection = sectionId;

    // Refresh data when switching sections
    if (sectionId === 'files') refreshFileList();
}

// Forms
function initForms() {
    document.getElementById('export-form')?.addEventListener('submit', handleExport);
    document.getElementById('import-form')?.addEventListener('submit', handleImport);
    document.getElementById('settings-form')?.addEventListener('submit', handleSaveSettings);
}

// Event Listeners from Main Process
function initEventListeners() {
    api.onTaskStart((data) => {
        runningTasks.set(data.taskId, data);
        addActivity(data.operation, 'pending', `Started ${data.operation}`);
    });

    api.onTaskLog((data) => {
        appendLog(data.taskId, data.text, data.stream);
    });

    api.onTaskComplete((data) => {
        const task = runningTasks.get(data.taskId);
        runningTasks.delete(data.taskId);

        if (task) {
            const status = data.success ? 'success' : 'error';
            const message = data.success ? `${task.operation} completed successfully` : `${task.operation} failed`;
            addActivity(task.operation, status, message);
            showToast(status, task.operation, message);
        }

        // Refresh file list after export
        if (data.taskId?.startsWith('export-') && data.success) {
            refreshFileList();
        }
    });
}

// Settings
async function loadSettings() {
    try {
        settings = await api.getSettings();

        document.getElementById('export-url').value = settings.defaultSourceUrl || 'opc.tcp://localhost:4840';
        document.getElementById('import-url').value = settings.defaultDestUrl || 'opc.tcp://localhost:4840';
        document.getElementById('settings-python-path').value = settings.pythonPath || 'python3';
        document.getElementById('settings-default-source').value = settings.defaultSourceUrl || '';
        document.getElementById('settings-default-dest').value = settings.defaultDestUrl || '';
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

async function handleSaveSettings(e) {
    e.preventDefault();

    const newSettings = {
        pythonPath: document.getElementById('settings-python-path').value,
        defaultSourceUrl: document.getElementById('settings-default-source').value,
        defaultDestUrl: document.getElementById('settings-default-dest').value
    };

    try {
        await api.saveSettings(newSettings);
        settings = { ...settings, ...newSettings };
        showToast('success', 'Settings', 'Settings saved successfully');
    } catch (error) {
        showToast('error', 'Settings', 'Failed to save settings');
    }
}

// Check Server
async function checkServer(type) {
    const urlInput = document.getElementById(`${type}-url`);
    const url = urlInput.value;

    if (!url) {
        showToast('warning', 'Connection', 'Please enter a server URL');
        return;
    }

    showLoading('Testing connection...');

    try {
        const params = {
            url,
            username: document.getElementById(`${type}-username`)?.value,
            password: document.getElementById(`${type}-password`)?.value,
            securityPolicy: document.getElementById(`${type}-security-policy`)?.value,
            securityMode: document.getElementById(`${type}-security-mode`)?.value
        };

        const result = await api.checkServer(params);

        if (result.success) {
            showToast('success', 'Connection', 'Successfully connected to server');
        } else {
            showToast('error', 'Connection', result.error || 'Failed to connect');
        }
    } catch (error) {
        showToast('error', 'Connection', error.message || 'Connection failed');
    } finally {
        hideLoading();
    }
}

// Export
async function handleExport(e) {
    e.preventDefault();

    const sourceUrl = document.getElementById('export-url').value;
    const outputFile = document.getElementById('export-filename').value || `export-${Date.now()}.json`;

    showLoading('Exporting nodes...');
    showLogCard('export');

    try {
        const params = {
            sourceUrl,
            outputFile,
            username: document.getElementById('export-username').value,
            password: document.getElementById('export-password').value,
            securityPolicy: document.getElementById('export-security-policy').value,
            securityMode: document.getElementById('export-security-mode').value
        };

        const result = await api.exportNodes(params);

        if (result.success) {
            showToast('success', 'Export', `Exported to ${result.filename}`);
            refreshFileList();
        } else {
            showToast('error', 'Export', result.error || 'Export failed');
        }
    } catch (error) {
        showToast('error', 'Export', error.message || 'Export failed');
    } finally {
        hideLoading();
    }
}

// Import
async function handleImport(e) {
    e.preventDefault();

    const destinationUrl = document.getElementById('import-url').value;
    const inputFile = document.getElementById('import-file').value;
    const dryRun = document.getElementById('import-dry-run').checked;

    if (!inputFile) {
        showToast('warning', 'Import', 'Please select an input file');
        return;
    }

    showLoading(dryRun ? 'Validating import...' : 'Importing nodes...');
    showLogCard('import');

    try {
        const params = {
            destinationUrl,
            inputFile,
            dryRun,
            username: document.getElementById('import-username').value,
            password: document.getElementById('import-password').value,
            securityPolicy: document.getElementById('import-security-policy').value,
            securityMode: document.getElementById('import-security-mode').value
        };

        const result = await api.importNodes(params);

        if (result.success) {
            const msg = dryRun ? 'Validation completed' : 'Import completed successfully';
            showToast('success', 'Import', msg);
        } else {
            showToast('error', 'Import', result.error || 'Import failed');
        }
    } catch (error) {
        showToast('error', 'Import', error.message || 'Import failed');
    } finally {
        hideLoading();
    }
}

// File Selection
async function selectImportFile() {
    const result = await api.openFileDialog();
    if (result.success && result.filePath) {
        document.getElementById('import-file').value = result.filePath;
    }
}

async function selectCreateServerFile() {
    const result = await api.openFileDialog();
    if (result.success && result.filePath) {
        document.getElementById('create-server-file').value = result.filePath;
    }
}

async function selectBrowserFile() {
    const result = await api.openFileDialog();
    if (result.success && result.filePath) {
        document.getElementById('browser-file').value = result.filePath;
    }
}

// Servers
let testServerTaskId = null;
let createServerTaskId = null;

async function toggleTestServer() {
    const btn = document.getElementById('btn-test-server');
    const status = document.getElementById('test-server-status');

    if (testServerTaskId) {
        await api.stopProcess(testServerTaskId);
        testServerTaskId = null;
        btn.textContent = 'Start Server';
        btn.classList.remove('danger');
        btn.classList.add('primary');
        status.classList.remove('running');
        status.querySelector('.status-text').textContent = 'Stopped';
    } else {
        const port = document.getElementById('test-server-port').value || 4840;
        showLogCard('server');

        const result = await api.startTestServer({ port: parseInt(port) });

        if (result.success) {
            testServerTaskId = result.taskId;
            btn.textContent = 'Stop Server';
            btn.classList.remove('primary');
            btn.classList.add('danger');
            status.classList.add('running');
            status.querySelector('.status-text').textContent = `Running on port ${port}`;
            showToast('success', 'Test Server', result.message);
        } else {
            showToast('error', 'Test Server', result.error);
        }
    }
}

async function toggleCreateServer() {
    const btn = document.getElementById('btn-create-server');
    const status = document.getElementById('create-server-status');

    if (createServerTaskId) {
        await api.stopProcess(createServerTaskId);
        createServerTaskId = null;
        btn.textContent = 'Start Server';
        btn.classList.remove('danger');
        btn.classList.add('primary');
        status.classList.remove('running');
        status.querySelector('.status-text').textContent = 'Stopped';
    } else {
        const inputFile = document.getElementById('create-server-file').value;
        const port = document.getElementById('create-server-port').value || 4841;

        if (!inputFile) {
            showToast('warning', 'Create Server', 'Please select an export file');
            return;
        }

        showLogCard('server');

        const result = await api.createServer({
            inputFile,
            port: parseInt(port)
        });

        if (result.success) {
            createServerTaskId = result.taskId;
            btn.textContent = 'Stop Server';
            btn.classList.remove('primary');
            btn.classList.add('danger');
            status.classList.add('running');
            status.querySelector('.status-text').textContent = `Running on port ${port}`;
            showToast('success', 'Create Server', result.message);
        } else {
            showToast('error', 'Create Server', result.error);
        }
    }
}

// Node Browser
async function loadBrowserFile() {
    const filePath = document.getElementById('browser-file').value;

    if (!filePath) {
        showToast('warning', 'Browser', 'Please select a file');
        return;
    }

    showLoading('Loading export file...');

    try {
        const result = await api.readExport(filePath);

        if (result.success) {
            loadedExportData = result.content;
            renderBrowserInfo(result.content);
            renderNodeTree(result.content.nodes);
            document.querySelector('.browser-info').style.display = 'none';
            document.querySelector('.browser-content').style.display = 'grid';
            showToast('success', 'Browser', 'File loaded successfully');
        } else {
            showToast('error', 'Browser', result.error);
        }
    } catch (error) {
        showToast('error', 'Browser', error.message);
    } finally {
        hideLoading();
    }
}

function renderBrowserInfo(data) {
    const info = document.getElementById('browser-info');
    info.innerHTML = `
        <div class="info-grid">
            <span class="info-label">Source URL:</span>
            <span class="info-value">${data.source_url || 'N/A'}</span>
            <span class="info-label">Export Date:</span>
            <span class="info-value">${data.export_timestamp || 'N/A'}</span>
            <span class="info-label">Total Nodes:</span>
            <span class="info-value">${data.total_nodes || 0}</span>
        </div>
    `;
}

function renderNodeTree(nodes, container = null) {
    const treeContainer = container || document.getElementById('browser-tree');

    if (!container) {
        treeContainer.innerHTML = '';
    }

    nodes.forEach(node => {
        const nodeEl = document.createElement('div');
        nodeEl.className = 'tree-node';

        const hasChildren = node.children && node.children.length > 0;

        nodeEl.innerHTML = `
            <div class="tree-node-header" data-node-id="${node.node_id}">
                <span class="tree-toggle">${hasChildren ? '&#9658;' : ''}</span>
                <span class="tree-icon">${getNodeIcon(node.node_class)}</span>
                <span class="tree-name">${node.display_name || node.browse_name || node.node_id}</span>
            </div>
            ${hasChildren ? '<div class="tree-children"></div>' : ''}
        `;

        const header = nodeEl.querySelector('.tree-node-header');
        header.addEventListener('click', () => {
            selectNodeInTree(header, node);

            if (hasChildren) {
                const children = nodeEl.querySelector('.tree-children');
                const toggle = nodeEl.querySelector('.tree-toggle');

                if (children.classList.contains('expanded')) {
                    children.classList.remove('expanded');
                    toggle.innerHTML = '&#9658;';
                } else {
                    if (children.children.length === 0) {
                        renderNodeTree(node.children, children);
                    }
                    children.classList.add('expanded');
                    toggle.innerHTML = '&#9660;';
                }
            }
        });

        treeContainer.appendChild(nodeEl);
    });
}

function getNodeIcon(nodeClass) {
    switch (nodeClass) {
        case 'Object': return '&#128230;';
        case 'Variable': return '&#128200;';
        case 'Method': return '&#9881;';
        case 'ObjectType': return '&#128736;';
        case 'VariableType': return '&#128202;';
        case 'ReferenceType': return '&#128279;';
        case 'DataType': return '&#128203;';
        case 'View': return '&#128065;';
        default: return '&#128196;';
    }
}

function selectNodeInTree(header, node) {
    document.querySelectorAll('.tree-node-header.selected').forEach(el => {
        el.classList.remove('selected');
    });
    header.classList.add('selected');
    selectedNode = node;
    renderNodeDetails(node);
}

function renderNodeDetails(node) {
    const details = document.getElementById('browser-details');
    details.innerHTML = `
        <h3>Node Details</h3>
        <div class="detail-row">
            <span class="detail-label">Node ID</span>
            <span class="detail-value">${node.node_id}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Browse Name</span>
            <span class="detail-value">${node.browse_name || 'N/A'}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Display Name</span>
            <span class="detail-value">${node.display_name || 'N/A'}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Node Class</span>
            <span class="detail-value">${node.node_class || 'N/A'}</span>
        </div>
        <div class="detail-row">
            <span class="detail-label">Namespace</span>
            <span class="detail-value">${node.namespace ?? 'N/A'}</span>
        </div>
        ${node.data_type ? `
        <div class="detail-row">
            <span class="detail-label">Data Type</span>
            <span class="detail-value">${node.data_type}</span>
        </div>
        ` : ''}
        ${node.value !== undefined ? `
        <div class="detail-row">
            <span class="detail-label">Value</span>
            <span class="detail-value">${JSON.stringify(node.value)}</span>
        </div>
        ` : ''}
        ${node.access_level !== undefined ? `
        <div class="detail-row">
            <span class="detail-label">Access Level</span>
            <span class="detail-value">${node.access_level}</span>
        </div>
        ` : ''}
        <div class="detail-row">
            <span class="detail-label">Children</span>
            <span class="detail-value">${node.children?.length || 0}</span>
        </div>
    `;
}

function filterNodes() {
    const search = document.getElementById('browser-search').value.toLowerCase();
    const nodes = document.querySelectorAll('.tree-node-header');

    nodes.forEach(node => {
        const name = node.querySelector('.tree-name').textContent.toLowerCase();
        const parent = node.closest('.tree-node');

        if (name.includes(search)) {
            parent.style.display = '';

            // Expand parents
            let parentContainer = parent.parentElement;
            while (parentContainer && parentContainer.classList.contains('tree-children')) {
                parentContainer.classList.add('expanded');
                const toggle = parentContainer.previousElementSibling?.querySelector('.tree-toggle');
                if (toggle) toggle.innerHTML = '&#9660;';
                parentContainer = parentContainer.parentElement?.parentElement;
            }
        } else if (search) {
            parent.style.display = 'none';
        } else {
            parent.style.display = '';
        }
    });
}

// Files Management
async function refreshFileList() {
    try {
        const result = await api.listExports();

        if (result.success) {
            const tbody = document.getElementById('files-list');

            if (result.files.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No export files found</td></tr>';
                return;
            }

            tbody.innerHTML = result.files.map(file => `
                <tr>
                    <td>${file.filename}</td>
                    <td>${formatFileSize(file.size)}</td>
                    <td>${formatDate(file.modified)}</td>
                    <td class="actions">
                        <button class="btn small" onclick="viewFile('${file.filename}')">View</button>
                        <button class="btn small" onclick="useForImport('${file.filename}')">Import</button>
                        <button class="btn small danger" onclick="deleteFile('${file.filename}')">Delete</button>
                    </td>
                </tr>
            `).join('');
        }
    } catch (error) {
        console.error('Failed to refresh file list:', error);
    }
}

async function viewFile(filename) {
    document.getElementById('browser-file').value = filename;
    showSection('browser');
    await loadBrowserFile();
}

function useForImport(filename) {
    document.getElementById('import-file').value = filename;
    showSection('import');
}

async function deleteFile(filename) {
    if (!confirm(`Delete ${filename}?`)) return;

    try {
        const result = await api.deleteExport(filename);
        if (result.success) {
            showToast('success', 'Files', 'File deleted');
            refreshFileList();
        } else {
            showToast('error', 'Files', result.error);
        }
    } catch (error) {
        showToast('error', 'Files', error.message);
    }
}

async function copySampleExport() {
    try {
        const result = await api.copySampleExport();
        if (result.success) {
            showToast('success', 'Files', 'Sample export loaded');
            refreshFileList();
        } else {
            showToast('error', 'Files', result.error);
        }
    } catch (error) {
        showToast('error', 'Files', error.message);
    }
}

// App Info
async function loadAppInfo() {
    try {
        const info = await api.getAppInfo();
        const container = document.getElementById('app-info');

        container.innerHTML = `
            <span class="info-label">Version:</span>
            <span class="info-value">${info.version}</span>
            <span class="info-label">Platform:</span>
            <span class="info-value">${info.platform}</span>
            <span class="info-label">Architecture:</span>
            <span class="info-value">${info.arch}</span>
            <span class="info-label">Electron:</span>
            <span class="info-value">${info.electron}</span>
            <span class="info-label">Node.js:</span>
            <span class="info-value">${info.node}</span>
            <span class="info-label">Exports Dir:</span>
            <span class="info-value">${info.exportsDir}</span>
            <span class="info-label">Scripts Dir:</span>
            <span class="info-value">${info.scriptsDir}</span>
        `;
    } catch (error) {
        console.error('Failed to load app info:', error);
    }
}

// Logging
function showLogCard(type) {
    const card = document.getElementById(`${type}-log-card`);
    if (card) {
        card.style.display = 'block';
        clearLog(type);
    }
}

function clearLog(type) {
    const log = document.getElementById(`${type}-log`);
    if (log) log.innerHTML = '';
}

function appendLog(taskId, text, stream) {
    // Determine which log to use based on task type
    let logId = 'server-log';
    if (taskId?.startsWith('export')) logId = 'export-log';
    else if (taskId?.startsWith('import')) logId = 'import-log';

    const log = document.getElementById(logId);
    if (log) {
        const span = document.createElement('span');
        span.className = stream === 'stderr' ? 'log-stderr' : 'log-stdout';
        span.textContent = text;
        log.appendChild(span);
        log.scrollTop = log.scrollHeight;
    }
}

// Activity
function addActivity(operation, status, message) {
    activities.unshift({
        operation,
        status,
        message,
        time: new Date()
    });

    // Keep only last 20 activities
    if (activities.length > 20) {
        activities = activities.slice(0, 20);
    }

    renderActivities();
}

function renderActivities() {
    const container = document.getElementById('recent-activity');

    if (activities.length === 0) {
        container.innerHTML = '<p class="empty-state">No recent activity</p>';
        return;
    }

    container.innerHTML = activities.slice(0, 10).map(a => `
        <div class="activity-item">
            <span class="activity-dot ${a.status}"></span>
            <span class="activity-text">${a.message}</span>
            <span class="activity-time">${formatTime(a.time)}</span>
        </div>
    `).join('');
}

// Toast Notifications
function showToast(type, title, message) {
    const container = document.getElementById('toast-container');

    const icons = {
        success: '&#10003;',
        error: '&#10007;',
        warning: '&#9888;',
        info: '&#8505;'
    };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${icons[type]}</span>
        <div class="toast-content">
            <div class="toast-title">${title}</div>
            <div class="toast-message">${message}</div>
        </div>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

// Loading
function showLoading(text = 'Loading...') {
    document.getElementById('loading-text').textContent = text;
    document.getElementById('loading-overlay').classList.remove('hidden');
}

function hideLoading() {
    document.getElementById('loading-overlay').classList.add('hidden');
}

// Utilities
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(date) {
    return new Date(date).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatTime(date) {
    return new Date(date).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Make functions available globally for onclick handlers
window.showSection = showSection;
window.checkServer = checkServer;
window.selectImportFile = selectImportFile;
window.selectCreateServerFile = selectCreateServerFile;
window.selectBrowserFile = selectBrowserFile;
window.loadBrowserFile = loadBrowserFile;
window.filterNodes = filterNodes;
window.toggleTestServer = toggleTestServer;
window.toggleCreateServer = toggleCreateServer;
window.refreshFileList = refreshFileList;
window.viewFile = viewFile;
window.useForImport = useForImport;
window.deleteFile = deleteFile;
window.copySampleExport = copySampleExport;
window.clearLog = clearLog;
