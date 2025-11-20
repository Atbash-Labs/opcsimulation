"""
Shared utilities for OPC UA operations
"""
import asyncio
from asyncua import Client, Server, ua
from typing import Dict, List, Any, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_client(
    url: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    security_policy: Optional[str] = None,
    security_mode: Optional[str] = None
) -> Client:
    """
    Create and connect an OPC UA client
    
    Args:
        url: OPC UA server endpoint URL
        username: Optional username
        password: Optional password
        security_policy: Security policy (Basic128Rsa15, Basic256, Basic256Sha256)
        security_mode: Security mode (Sign, SignAndEncrypt)
    
    Returns:
        Connected OPC UA client
    """
    client = Client(url=url)
    
    # Set security if provided
    if security_policy or security_mode:
        security_policy_enum = None
        security_mode_enum = None
        
        if security_policy:
            policy_map = {
                "Basic128Rsa15": ua.SecurityPolicyType.Basic128Rsa15,
                "Basic256": ua.SecurityPolicyType.Basic256,
                "Basic256Sha256": ua.SecurityPolicyType.Basic256Sha256,
            }
            security_policy_enum = policy_map.get(security_policy)
        
        if security_mode:
            mode_map = {
                "Sign": ua.MessageSecurityMode.Sign,
                "SignAndEncrypt": ua.MessageSecurityMode.SignAndEncrypt,
            }
            security_mode_enum = mode_map.get(security_mode)
        
        client.set_security(
            security_policy_enum or ua.SecurityPolicyType.Basic256Sha256,
            security_mode_enum or ua.MessageSecurityMode.SignAndEncrypt
        )
    
    # Set user credentials if provided
    if username and password:
        client.set_user(username)
        client.set_password(password)
    
    await client.connect()
    logger.info(f"Connected to OPC UA server at {url}")
    return client


async def browse_node_recursive(client: Client, node, max_depth: int = 100, current_depth: int = 0) -> List[Dict[str, Any]]:
    """
    Recursively browse all nodes starting from a given node
    
    Args:
        client: OPC UA client
        node: Starting node
        max_depth: Maximum depth to browse
        current_depth: Current depth (for recursion)
    
    Returns:
        List of node dictionaries
    """
    if current_depth >= max_depth:
        return []
    
    nodes = []
    node_id = str(node.nodeid)
    
    try:
        # Get node attributes
        node_class = await node.read_node_class()
        browse_name = await node.read_browse_name()
        display_name = await node.read_display_name()
        
        node_info = {
            "node_id": node_id,
            "node_class": node_class.name,
            "browse_name": str(browse_name.Name),
            "display_name": str(display_name.Text),
            "namespace": browse_name.NamespaceIndex,
            "children": []
        }
        
        # If it's a variable node, try to read its value and data type
        if node_class == ua.NodeClass.Variable:
            try:
                data_value = await node.read_data_value()
                node_info["data_type"] = str(data_value.Value.VariantType.name)
                node_info["value"] = data_value.Value.Value
                node_info["status_code"] = str(data_value.StatusCode.name)
                
                # Try to get access level
                try:
                    access_level = await node.read_attribute(ua.AttributeIds.AccessLevel)
                    node_info["access_level"] = int(access_level.Value.Value)
                    node_info["user_access_level"] = int((await node.read_attribute(ua.AttributeIds.UserAccessLevel)).Value.Value)
                except Exception as e:
                    logger.debug(f"Could not read access level for {node_id}: {e}")
                    node_info["access_level"] = None
                    node_info["user_access_level"] = None
            except Exception as e:
                logger.debug(f"Could not read value for variable {node_id}: {e}")
                node_info["data_type"] = None
                node_info["value"] = None
                node_info["status_code"] = None
        
        # Browse children
        try:
            children = await node.get_children()
            for child in children:
                child_nodes = await browse_node_recursive(client, child, max_depth, current_depth + 1)
                node_info["children"].extend(child_nodes)
        except Exception as e:
            logger.debug(f"Could not browse children of {node_id}: {e}")
        
        nodes.append(node_info)
        
    except Exception as e:
        logger.warning(f"Error processing node {node_id}: {e}")
    
    return nodes


async def get_all_nodes(client: Client) -> List[Dict[str, Any]]:
    """
    Get all nodes from the OPC UA server starting from the root
    
    Args:
        client: OPC UA client
    
    Returns:
        List of all nodes in hierarchical structure
    """
    root = client.get_objects_node()
    nodes = await browse_node_recursive(client, root)
    return nodes


async def find_node_by_browse_path(client: Client, browse_path: List[str]) -> Optional[Any]:
    """
    Find a node by its browse path (list of browse names)
    
    Args:
        client: OPC UA client
        browse_path: List of browse names from root (e.g., ["Objects", "TestFolder", "TestInt"])
    
    Returns:
        Node object if found, None otherwise
    """
    try:
        # Start from Objects node
        current_node = client.get_objects_node()
        
        # Skip "Objects" if it's the first element since we're already starting from Objects node
        path_to_follow = browse_path[1:] if browse_path and browse_path[0] == "Objects" else browse_path
        
        # Filter out empty strings
        path_to_follow = [p for p in path_to_follow if p]
        
        if not path_to_follow:
            # If path is empty or only "Objects", return Objects node
            return current_node
        
        logger.debug(f"Looking for path: {path_to_follow} (original: {browse_path})")
        
        for i, browse_name in enumerate(path_to_follow):
            # Browse children to find the node with matching browse name
            try:
                children = await current_node.get_children()
            except Exception as e:
                logger.debug(f"Error getting children at step {i} ({browse_name}): {e}")
                return None
            
            found = False
            
            for child in children:
                try:
                    child_browse_name = await child.read_browse_name()
                    child_name = str(child_browse_name.Name)
                    if child_name == browse_name:
                        current_node = child
                        found = True
                        logger.debug(f"Found '{browse_name}' at step {i}")
                        break
                except Exception as e:
                    logger.debug(f"Error reading browse name from child: {e}")
                    continue
            
            if not found:
                logger.debug(f"Could not find node '{browse_name}' at step {i} in path {browse_path}")
                # Log available children for debugging (first few)
                try:
                    available_names = []
                    for child in children[:10]:  # Limit to first 10 for logging
                        try:
                            bn = await child.read_browse_name()
                            available_names.append(str(bn.Name))
                        except:
                            pass
                    if available_names:
                        logger.debug(f"Available children at '{path_to_follow[i-1] if i > 0 else 'Objects'}': {available_names[:10]}")
                except:
                    pass
                return None
        
        return current_node
        
    except Exception as e:
        logger.debug(f"Error finding node by browse path {browse_path}: {e}")
        return None


def build_browse_path(nodes: List[Dict[str, Any]], target_node_id: str, current_path: List[str] = None) -> Optional[List[str]]:
    """
    Build browse path to a node by recursively searching
    
    Args:
        nodes: List of node dictionaries
        target_node_id: Target node ID to find
        current_path: Current path being built
    
    Returns:
        List of browse names forming the path, or None if not found
    """
    if current_path is None:
        current_path = []
    
    for node in nodes:
        path = current_path + [node.get("browse_name", "")]
        
        if node.get("node_id") == target_node_id:
            return path
        
        if "children" in node and node["children"]:
            result = build_browse_path(node["children"], target_node_id, path)
            if result:
                return result
    
    return None


async def write_node_value(client: Client, node_id: str, value: Any, data_type: Optional[str] = None, browse_path: Optional[List[str]] = None) -> bool:
    """
    Write a value to a node
    
    Args:
        client: OPC UA client
        node_id: Node ID string (used as fallback)
        value: Value to write
        data_type: Optional data type hint
        browse_path: Optional browse path to find node (preferred over node_id)
    
    Returns:
        True if successful, False otherwise
    """
    node = None
    
    # Try browse path first if provided
    if browse_path:
        node = await find_node_by_browse_path(client, browse_path)
    
    # Fallback to node ID
    if node is None:
        try:
            node = client.get_node(node_id)
        except Exception as e:
            logger.debug(f"Could not get node by ID {node_id}: {e}")
    
    if node is None:
        logger.warning(f"Could not find node with ID {node_id} or path {browse_path}")
        return False
    
    try:
        node_class = await node.read_node_class()
        
        if node_class != ua.NodeClass.Variable:
            logger.warning(f"Node {node_id} is not a Variable node, skipping write")
            return False
        
        # Check access level
        try:
            access_level = await node.read_attribute(ua.AttributeIds.AccessLevel)
            if not (access_level.Value.Value & ua.AccessLevel.CurrentWrite):
                logger.warning(f"Node {node_id} is not writable (access_level: {access_level.Value.Value})")
                return False
        except Exception as e:
            logger.debug(f"Could not check access level for {node_id}: {e}")
        
        # Write the value
        await node.write_value(value)
        logger.info(f"Successfully wrote value {value} to node {node_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to write value to node {node_id}: {e}")
        return False


