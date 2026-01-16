# OPC Simulation - Electron Frontend

A native desktop application for the OPC UA Simulation Tool.

## Features

- **Export Nodes**: Export OPC UA nodes from a server to JSON
- **Import Nodes**: Import OPC UA nodes from JSON to a server
- **Server Management**: Start test servers or create servers from export files
- **Node Browser**: Browse and inspect exported node hierarchies
- **File Management**: Manage your export files

## Installation

```bash
cd frontend
npm install
```

## Running

```bash
npm start
```

## Building for Distribution

```bash
# Build for current platform
npm run build

# Build for specific platforms
npm run build:win    # Windows
npm run build:mac    # macOS
npm run build:linux  # Linux
```

## Requirements

- Node.js 18+
- Python 3.12+ (for running OPC scripts)
- The Python `asyncua` package installed

## Configuration

On first run, go to **Settings** to configure:

- **Python Path**: Path to your Python executable (default: `python3`)
- **Default Source URL**: Default OPC server URL for exports
- **Default Destination URL**: Default OPC server URL for imports

## Architecture

```
frontend/
├── main.js          # Electron main process
├── preload.js       # Secure IPC bridge
├── renderer/
│   ├── index.html   # Main UI
│   ├── styles.css   # Dark theme styling
│   └── app.js       # Frontend logic
└── package.json     # Dependencies & build config
```

The app uses Electron's IPC (Inter-Process Communication) to securely communicate between the renderer and main processes. Python scripts are executed as child processes with real-time output streaming.

## Screenshots

The app features a modern dark theme with:
- Sidebar navigation
- Dashboard with quick actions
- Forms for export/import operations
- Real-time log output
- Tree-view node browser
- File management table
