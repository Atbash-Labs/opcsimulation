# OPC UA Sync Tool

A tool to export nodes/values from an OPC UA server to a file, and import them into another OPC UA server.

## Features

- **Stage 1 (Export)**: Browse and read all nodes/values from a source OPC UA server and save to a JSON file
- **Stage 2 (Import)**: Read nodes/values from a JSON file and write them to a destination OPC UA server

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Stage 1: Export from Source Server

```bash
python export_opc_nodes.py --source-url opc.tcp://localhost:4840 --output-file nodes_export.json
```

Options:
- `--source-url`: OPC UA server endpoint URL (default: `opc.tcp://localhost:4840`)
- `--output-file`: Output JSON file path (default: `opc_nodes_export.json`)
- `--username`: Optional username for authentication
- `--password`: Optional password for authentication
- `--security-policy`: Security policy (default: None, options: Basic128Rsa15, Basic256, Basic256Sha256)
- `--security-mode`: Security mode (default: None, options: Sign, SignAndEncrypt)

### Stage 2: Import to Destination Server

There are two ways to import:

#### Option A: Write values to existing nodes

```bash
python import_opc_nodes.py --destination-url opc.tcp://localhost:4841 --input-file nodes_export.json
```

This assumes the destination server already has the same node structure. It only writes values to existing nodes.

Options:
- `--destination-url`: Destination OPC UA server endpoint URL (default: `opc.tcp://localhost:4841`)
- `--input-file`: Input JSON file path (default: `opc_nodes_export.json`)
- `--username`: Optional username for authentication
- `--password`: Optional password for authentication
- `--security-policy`: Security policy (default: None)
- `--security-mode`: Security mode (default: None)
- `--dry-run`: Validate without writing

#### Option B: Create nodes and write values (for Python OPC UA servers)

```bash
python create_nodes_from_export.py --input-file nodes_export.json --port 4841
```

This creates a new Python OPC UA server with nodes created from the export file. Nodes are created in the correct order (parents before children), then values are written.

Options:
- `--input-file`: Input JSON file path (default: `opc_nodes_export.json`)
- `--port`: Port to run server on (default: 4841)
- `--namespace-uri`: Namespace URI (default: `http://examples.freeopcua.github.io`)

### Test Server

Run a test Python OPC UA server:

```bash
python test_server.py --port 4840
```

This creates a simple server with some test nodes for demonstration.

## File Format

The export file is a JSON file containing:
- Node ID
- Node Class (Variable, Object, etc.)
- Browse Name
- Display Name
- Data Type
- Value (if readable)
- Access Level (if applicable)
- Children nodes (recursive structure)

## Testing

Run the test suite:

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_opc_sync.py

# Run specific test
pytest tests/test_opc_sync.py::TestOPCExport::test_export_nodes
```

The test suite includes:
- **Export tests**: Verify nodes are exported correctly with values
- **Import tests**: Verify values are imported and modified on destination servers
- **Integration tests**: Full export/import cycle with value verification

Tests use separate test servers on ports 4850 and 4851 to avoid conflicts.

## Notes

- Only readable/writable nodes are exported/imported
- The tool handles hierarchical node structures
- Variable nodes with values are prioritized for import
- Object nodes are created but their values come from their child Variable nodes
- Tests automatically start/stop test servers for isolated testing

