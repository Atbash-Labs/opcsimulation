"""
Stage 1: Export nodes/values from an OPC UA server to a JSON file
"""
import asyncio
import json
import argparse
import sys
from typing import Optional
from datetime import datetime
from opc_utils import create_client, get_all_nodes
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def export_nodes(
    source_url: str,
    output_file: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    security_policy: Optional[str] = None,
    security_mode: Optional[str] = None
):
    """
    Export all nodes from source OPC UA server to a JSON file
    
    Args:
        source_url: Source OPC UA server URL
        output_file: Output JSON file path
        username: Optional username
        password: Optional password
        security_policy: Optional security policy
        security_mode: Optional security mode
    """
    client = None
    try:
        # Connect to source server
        client = await create_client(
            source_url,
            username=username,
            password=password,
            security_policy=security_policy,
            security_mode=security_mode
        )
        
        logger.info("Starting node export...")
        
        # Get all nodes
        nodes = await get_all_nodes(client)
        
        logger.info(f"Found {len(nodes)} top-level nodes")
        
        # Count total nodes recursively
        def count_nodes(node_list):
            count = len(node_list)
            for node in node_list:
                if "children" in node:
                    count += count_nodes(node["children"])
            return count
        
        total_nodes = count_nodes(nodes)
        logger.info(f"Total nodes (including children): {total_nodes}")
        
        # Prepare export data
        export_data = {
            "source_url": source_url,
            "export_timestamp": datetime.now().isoformat(),
            "total_nodes": total_nodes,
            "nodes": nodes
        }
        
        # Write to file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        logger.info(f"Successfully exported {total_nodes} nodes to {output_file}")
        
        # Print summary
        def count_variables(node_list):
            count = 0
            for node in node_list:
                if node.get("node_class") == "Variable":
                    count += 1
                if "children" in node:
                    count += count_variables(node["children"])
            return count
        
        variable_count = count_variables(nodes)
        logger.info(f"Total variable nodes: {variable_count}")
        
    except Exception as e:
        logger.error(f"Error during export: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if client:
            await client.disconnect()
            logger.info("Disconnected from source server")


def main():
    parser = argparse.ArgumentParser(description="Export nodes/values from OPC UA server to JSON file")
    parser.add_argument("--source-url", default="opc.tcp://localhost:4840",
                       help="Source OPC UA server URL (default: opc.tcp://localhost:4840)")
    parser.add_argument("--output-file", default="opc_nodes_export.json",
                       help="Output JSON file path (default: opc_nodes_export.json)")
    parser.add_argument("--username", help="Username for authentication")
    parser.add_argument("--password", help="Password for authentication")
    parser.add_argument("--security-policy", choices=["Basic128Rsa15", "Basic256", "Basic256Sha256"],
                       help="Security policy")
    parser.add_argument("--security-mode", choices=["Sign", "SignAndEncrypt"],
                       help="Security mode")
    
    args = parser.parse_args()
    
    asyncio.run(export_nodes(
        source_url=args.source_url,
        output_file=args.output_file,
        username=args.username,
        password=args.password,
        security_policy=args.security_policy,
        security_mode=args.security_mode
    ))


if __name__ == "__main__":
    main()

