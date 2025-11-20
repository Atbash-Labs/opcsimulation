"""
Create OPC UA nodes on a server from an export file.
This script creates the node structure (in correct order) and then writes values.
"""
import asyncio
import json
import argparse
import sys
from typing import Optional, Dict, List, Any
from asyncua import Server, ua
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def flatten_nodes_hierarchical(nodes: List[Dict[str, Any]], parent_path: str = "") -> List[Dict[str, Any]]:
    """
    Flatten node tree into a list, preserving depth information.
    This ensures parents come before children.
    
    Args:
        nodes: List of node dictionaries
        parent_path: Path to parent node
    
    Returns:
        List of nodes with depth information, sorted so parents come first
    """
    result = []
    
    for node in nodes:
        node_path = f"{parent_path}/{node.get('browse_name', '')}" if parent_path else node.get('browse_name', '')
        node_copy = node.copy()
        node_copy['_path'] = node_path
        node_copy['_parent_path'] = parent_path
        
        # Add this node
        result.append(node_copy)
        
        # Then add children recursively
        if "children" in node and node["children"]:
            children = flatten_nodes_hierarchical(node["children"], node_path)
            result.extend(children)
    
    return result


def parse_node_id(node_id_str: str) -> Optional[ua.NodeId]:
    """
    Parse a node ID string into a ua.NodeId object
    
    Args:
        node_id_str: Node ID as string (e.g., "ns=2;i=123" or "ns=0;i=85")
    
    Returns:
        ua.NodeId object or None if parsing fails
    """
    try:
        # Handle different formats: "ns=2;i=123", "i=85", etc.
        if "ns=" in node_id_str:
            parts = node_id_str.split(";")
            ns = 0
            identifier = None
            
            for part in parts:
                if part.startswith("ns="):
                    ns = int(part.split("=")[1])
                elif part.startswith("i="):
                    identifier = int(part.split("=")[1])
                elif part.startswith("s="):
                    identifier = part.split("=", 1)[1]
                elif part.startswith("g="):
                    identifier = part.split("=", 1)[1]  # GUID as string
            
            if identifier is not None:
                if isinstance(identifier, int):
                    return ua.NodeId(identifier, ns)
                elif isinstance(identifier, str):
                    if len(identifier) == 36 and identifier.count('-') == 4:  # GUID format
                        return ua.NodeId(ua.Guid.from_string(identifier), ns)
                    else:
                        return ua.NodeId(identifier, ns)
        else:
            # Try to parse as simple numeric ID (assumes namespace 0)
            if node_id_str.startswith("i="):
                identifier = int(node_id_str.split("=")[1])
                return ua.NodeId(identifier, 0)
            elif node_id_str.startswith("s="):
                identifier = node_id_str.split("=", 1)[1]
                return ua.NodeId(identifier, 0)
        
        # Fallback: try to parse as integer
        try:
            identifier = int(node_id_str)
            return ua.NodeId(identifier, 0)
        except ValueError:
            pass
            
    except Exception as e:
        logger.debug(f"Failed to parse node ID '{node_id_str}': {e}")
    
    return None


def should_skip_node(node_info: Dict[str, Any]) -> bool:
    """
    Determine if a node should be skipped (e.g., standard OPC UA nodes in namespace 0)
    
    Args:
        node_info: Node information dictionary
    
    Returns:
        True if node should be skipped
    """
    node_id_str = str(node_info.get("node_id", ""))
    namespace = node_info.get("namespace", 0)
    
    # Skip ALL nodes in namespace 0 (OPC UA standard namespace)
    # These are standard nodes that already exist and shouldn't be recreated
    if namespace == 0:
        return True
    
    # Also check the node_id string format
    if "ns=0" in node_id_str:
        return True
    
    # If node_id starts with "i=" or "s=" without "ns=", it's likely namespace 0
    if (node_id_str.startswith("i=") or node_id_str.startswith("s=")) and "ns=" not in node_id_str:
        # Parse to check namespace
        parsed_id = parse_node_id(node_id_str)
        if parsed_id is not None and parsed_id.NamespaceIndex == 0:
            return True
    
    # Skip if it's a numeric node ID without namespace info (assumed namespace 0)
    try:
        # If it's just a number, it's likely namespace 0
        int(node_id_str)
        if "ns=" not in node_id_str:
            return True
    except ValueError:
        pass
    
    return False


async def create_node_on_server(
    server: Server,
    node_info: Dict[str, Any],
    parent_node,
    namespace_idx: int
) -> Optional[Any]:
    """
    Create a node on the server
    
    Args:
        server: OPC UA Server instance
        node_info: Node information dictionary
        parent_node: Parent node object
        namespace_idx: Namespace index
    
    Returns:
        Created node object or None if failed
    """
    try:
        node_class = node_info.get("node_class")
        browse_name = node_info.get("browse_name", "")
        display_name = node_info.get("display_name", browse_name)
        
        # Parse node ID but check if it's namespace 0
        node_id = parse_node_id(node_info.get("node_id", ""))
        
        # NEVER create nodes with namespace 0 node IDs
        if node_id is not None and node_id.NamespaceIndex == 0:
            node_id_str = node_info.get("node_id", "")
            logger.warning(f"Attempted to create node with namespace 0 ID - skipping: {browse_name} (node_id={node_id_str})")
            return None
        
        if node_class == "Variable":
            # Create variable node - always use our namespace, not the original node ID
            # This ensures we don't try to recreate standard namespace nodes
            var_node = await parent_node.add_variable(
                namespace_idx,
                browse_name,
                node_info.get("value")
            )
            
            # Set writable if access level indicates it
            access_level = node_info.get("access_level")
            if access_level is not None and (access_level & 0x02):  # CurrentWrite bit
                await var_node.set_writable()
            
            logger.debug(f"Created variable: {browse_name}")
            return var_node
            
        elif node_class == "Object":
            # Create object node - always use our namespace
            obj_node = await parent_node.add_folder(
                namespace_idx,
                browse_name
            )
            
            logger.debug(f"Created object/folder: {browse_name}")
            return obj_node
            
        else:
            logger.debug(f"Skipping node class: {node_class}")
            return None
            
    except Exception as e:
        logger.warning(f"Failed to create node {node_info.get('browse_name')}: {e}")
        return None


async def create_nodes_from_export(
    server: Server,
    input_file: str,
    namespace_uri: str = "http://examples.freeopcua.github.io"
):
    """
    Create nodes on server from export file
    
    Args:
        server: OPC UA Server instance (already initialized)
        input_file: Path to export JSON file
        namespace_uri: Namespace URI to use
    """
    # Load export data
    logger.info(f"Loading export data from {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        export_data = json.load(f)
    
    nodes = export_data.get("nodes", [])
    logger.info(f"Loaded {export_data.get('total_nodes', 0)} nodes from export file")
    
    # Register namespace
    namespace_idx = await server.register_namespace(namespace_uri)
    logger.info(f"Registered namespace '{namespace_uri}' with index {namespace_idx}")
    
    # Get Objects node as root
    objects_node = server.get_objects_node()
    
    # Flatten nodes maintaining hierarchy order
    flat_nodes = flatten_nodes_hierarchical(nodes)
    logger.info(f"Flattened to {len(flat_nodes)} nodes")
    
    # Create a mapping of path to created node
    created_nodes = {
        "": objects_node  # Root
    }
    
    # Track variable nodes for value writing
    variable_nodes_to_write = []
    
    # Create nodes in order (parents before children)
    created_count = 0
    failed_count = 0
    skipped_count = 0
    
    for node_info in flat_nodes:
        # Skip standard namespace nodes
        if should_skip_node(node_info):
            skipped_count += 1
            node_id_str = node_info.get("node_id", "")
            namespace = node_info.get("namespace", 0)
            logger.debug(f"Skipping namespace 0 node: {node_info.get('browse_name')} (node_id={node_id_str}, namespace={namespace})")
            continue
        
        parent_path = node_info.get("_parent_path", "")
        node_path = node_info.get("_path", "")
        
        if parent_path not in created_nodes:
            logger.warning(f"Parent node not found for {node_path}, skipping")
            failed_count += 1
            continue
        
        parent_node = created_nodes[parent_path]
        
        # Create the node
        created_node = await create_node_on_server(
            server,
            node_info,
            parent_node,
            namespace_idx
        )
        
        if created_node:
            created_nodes[node_path] = created_node
            created_count += 1
            
            # If it's a variable with a value, track it for writing
            if node_info.get("node_class") == "Variable" and "value" in node_info:
                variable_nodes_to_write.append({
                    "node": created_node,
                    "value": node_info.get("value"),
                    "browse_name": node_info.get("browse_name")
                })
        else:
            failed_count += 1
    
    logger.info(f"Node creation complete: {created_count} created, {failed_count} failed, {skipped_count} skipped (standard namespace)")
    
    # Write values to variable nodes
    if variable_nodes_to_write:
        logger.info(f"Writing values to {len(variable_nodes_to_write)} variable nodes...")
        write_success = 0
        write_fail = 0
        
        for var_info in variable_nodes_to_write:
            try:
                await var_info["node"].write_value(var_info["value"])
                write_success += 1
                logger.debug(f"Wrote value to {var_info['browse_name']}")
            except Exception as e:
                write_fail += 1
                logger.warning(f"Failed to write value to {var_info['browse_name']}: {e}")
        
        logger.info(f"Value writing complete: {write_success} successful, {write_fail} failed")


async def main_async():
    parser = argparse.ArgumentParser(
        description="Create OPC UA nodes on a server from an export file"
    )
    parser.add_argument("--input-file", default="opc_nodes_export.json",
                       help="Input JSON file path (default: opc_nodes_export.json)")
    parser.add_argument("--port", type=int, default=4841,
                       help="Port to run server on (default: 4841)")
    parser.add_argument("--namespace-uri", default="http://examples.freeopcua.github.io",
                       help="Namespace URI (default: http://examples.freeopcua.github.io)")
    
    args = parser.parse_args()
    
    # Create and initialize server
    server = Server()
    await server.init()
    
    server.set_endpoint(f"opc.tcp://0.0.0.0:{args.port}/freeopcua/server/")
    server.set_server_name("OPC UA Server from Export")
    
    try:
        # Create nodes from export
        await create_nodes_from_export(server, args.input_file, args.namespace_uri)
        
        # Start server
        async with server:
            logger.info(f"Server started on port {args.port}")
            logger.info(f"Endpoint: opc.tcp://localhost:{args.port}/freeopcua/server/")
            logger.info("Press Ctrl+C to stop the server")
            
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("Shutting down server...")
                
    except FileNotFoundError:
        logger.error(f"Export file not found: {args.input_file}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        sys.exit(1)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()

