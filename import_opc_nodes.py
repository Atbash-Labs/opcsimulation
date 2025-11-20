"""
Stage 2: Import nodes/values from a JSON file to an OPC UA server
"""

import asyncio
import json
import argparse
import sys
from typing import Optional, Dict, List, Any
from opc_utils import create_client, write_node_value, build_browse_path
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def find_node_by_id(
    nodes: List[Dict[str, Any]], target_node_id: str
) -> Optional[Dict[str, Any]]:
    """
    Recursively find a node by its node ID

    Args:
        nodes: List of node dictionaries
        target_node_id: Target node ID to find

    Returns:
        Node dictionary if found, None otherwise
    """
    for node in nodes:
        if node.get("node_id") == target_node_id:
            return node
        if "children" in node:
            result = find_node_by_id(node["children"], target_node_id)
            if result:
                return result
    return None


def collect_variable_nodes(
    nodes: List[Dict[str, Any]], parent_path: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Collect all variable nodes with values from the node tree, including their browse paths

    Args:
        nodes: List of node dictionaries
        parent_path: Current parent path (for building browse paths)

    Returns:
        List of variable nodes with their values and browse paths
    """
    if parent_path is None:
        parent_path = []

    variables = []

    def traverse(node_list, current_path):
        for node in node_list:
            browse_name = node.get("browse_name", "")
            node_path = current_path + [browse_name] if browse_name else current_path

            if node.get("node_class") == "Variable":
                # Only include if it has a value
                if "value" in node and node["value"] is not None:
                    node_copy = node.copy()
                    node_copy["_browse_path"] = node_path
                    variables.append(node_copy)
            if "children" in node:
                traverse(node["children"], node_path)

    traverse(nodes, parent_path)
    return variables


async def import_nodes(
    destination_url: str,
    input_file: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    security_policy: Optional[str] = None,
    security_mode: Optional[str] = None,
    dry_run: bool = False,
):
    """
    Import nodes/values from a JSON file to destination OPC UA server

    Args:
        destination_url: Destination OPC UA server URL
        input_file: Input JSON file path
        username: Optional username
        password: Optional password
        security_policy: Optional security policy
        security_mode: Optional security mode
        dry_run: If True, only validate without writing
    """
    client = None
    try:
        # Load export data
        logger.info(f"Loading export data from {input_file}...")
        with open(input_file, "r", encoding="utf-8") as f:
            export_data = json.load(f)

        nodes = export_data.get("nodes", [])
        logger.info(
            f"Loaded {export_data.get('total_nodes', 0)} nodes from export file"
        )

        # Collect all variable nodes with values (including browse paths)
        variable_nodes = collect_variable_nodes(nodes)
        logger.info(f"Found {len(variable_nodes)} variable nodes with values to import")

        if dry_run:
            logger.info("DRY RUN MODE - No values will be written")
            for var_node in variable_nodes:
                logger.info(
                    f"Would write: {var_node['node_id']} = {var_node.get('value')}"
                )
            return

        # Connect to destination server
        client = await create_client(
            destination_url,
            username=username,
            password=password,
            security_policy=security_policy,
            security_mode=security_mode,
        )

        logger.info("Starting node import...")

        # Write values to nodes
        success_count = 0
        fail_count = 0

        for var_node in variable_nodes:
            node_id = var_node["node_id"]
            value = var_node.get("value")
            data_type = var_node.get("data_type")
            browse_path = var_node.get("_browse_path", [])

            if value is None:
                logger.debug(f"Skipping {node_id} - no value")
                continue

            # Use browse path for display
            path_str = "/".join(browse_path) if browse_path else node_id
            logger.info(f"Writing to {path_str}: {value} (type: {data_type})")

            # Try writing using browse path first, then fallback to node ID
            success = await write_node_value(
                client, node_id, value, data_type, browse_path
            )
            if success:
                success_count += 1
            else:
                fail_count += 1
                logger.warning(f"Failed to write to {path_str} (node_id: {node_id})")

        logger.info(f"Import complete: {success_count} successful, {fail_count} failed")

    except FileNotFoundError:
        logger.error(f"Export file not found: {input_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON file: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error during import: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if client:
            await client.disconnect()
            logger.info("Disconnected from destination server")


def main():
    parser = argparse.ArgumentParser(
        description="Import nodes/values from JSON file to OPC UA server"
    )
    parser.add_argument(
        "--destination-url",
        default="opc.tcp://localhost:4840",
        help="Destination OPC UA server URL (default: opc.tcp://localhost:4840)",
    )
    parser.add_argument(
        "--input-file",
        default="opc_nodes_export.json",
        help="Input JSON file path (default: opc_nodes_export.json)",
    )
    parser.add_argument("--username", help="Username for authentication")
    parser.add_argument("--password", help="Password for authentication")
    parser.add_argument(
        "--security-policy",
        choices=["Basic128Rsa15", "Basic256", "Basic256Sha256"],
        help="Security policy",
    )
    parser.add_argument(
        "--security-mode", choices=["Sign", "SignAndEncrypt"], help="Security mode"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Dry run mode - validate without writing"
    )

    args = parser.parse_args()

    asyncio.run(
        import_nodes(
            destination_url=args.destination_url,
            input_file=args.input_file,
            username=args.username,
            password=args.password,
            security_policy=args.security_policy,
            security_mode=args.security_mode,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
