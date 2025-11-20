"""
Example usage of the OPC UA sync tool

This demonstrates a complete workflow:
1. Start a test server (source)
2. Export nodes from source server
3. Start another test server (destination) 
4. Import nodes to destination server

Note: In practice, you would run these steps separately.
"""
import asyncio
import subprocess
import time
import sys
import os

# This is just a demonstration script
# In practice, you would:
# 1. Run: python test_server.py --port 4840 (in one terminal)
# 2. Run: python export_opc_nodes.py --source-url opc.tcp://localhost:4840 --output-file export.json
# 3. Run: python test_server.py --port 4841 (in another terminal, or modify test_server.py to create same structure)
# 4. Run: python import_opc_nodes.py --destination-url opc.tcp://localhost:4841 --input-file export.json

print("""
Example Usage:

1. Export from source server:
   python export_opc_nodes.py --source-url opc.tcp://localhost:4840 --output-file nodes_export.json

2. Import to destination server:
   python import_opc_nodes.py --destination-url opc.tcp://localhost:4841 --input-file nodes_export.json

3. Test with dry-run first:
   python import_opc_nodes.py --destination-url opc.tcp://localhost:4841 --input-file nodes_export.json --dry-run

Note: Make sure the destination server has the same node structure as the source server,
or the writes will fail for nodes that don't exist.
""")


