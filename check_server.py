"""
Check if an OPC UA server is running and accessible
"""

import asyncio
import argparse
import sys
from asyncua import Client
from opc_utils import create_client
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def check_server(url: str, timeout: int = 5):
    """
    Check if an OPC UA server is running at the given URL

    Args:
        url: OPC UA server URL
        timeout: Connection timeout in seconds

    Returns:
        True if server is accessible, False otherwise
    """
    client = None
    try:
        logger.info(f"Attempting to connect to {url}...")
        client = Client(url=url)

        # Set a timeout for the connection attempt
        try:
            await asyncio.wait_for(client.connect(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(f"Connection to {url} timed out after {timeout} seconds")
            return False

        # Try to read server info
        try:
            server_name = await client.get_server_node().read_browse_name()
            logger.info(f"✓ Successfully connected to server!")
            logger.info(f"  Server browse name: {server_name.Name}")

            # Try to get objects node to verify we can browse
            objects_node = client.get_objects_node()
            children = await objects_node.get_children()
            logger.info(f"  Found {len(children)} top-level objects")

            return True
        except Exception as e:
            logger.warning(f"Connected but could not read server info: {e}")
            return True  # Still consider it running if we connected

    except Exception as e:
        logger.error(f"✗ Failed to connect to {url}")
        logger.error(f"  Error: {e}")
        return False
    finally:
        if client:
            try:
                await client.disconnect()
            except:
                pass


async def check_ignition_default():
    """
    Check common Ignition OPC UA server URLs
    """
    # Common Ignition OPC UA server URLs
    ignition_urls = [
        "opc.tcp://localhost:62541",  # Default Ignition OPC UA server port
        "opc.tcp://localhost:4840",  # Alternative/common OPC UA port
        "opc.tcp://127.0.0.1:62541",
        "opc.tcp://127.0.0.1:4840",
    ]

    logger.info("Checking common Ignition OPC UA server URLs...")
    logger.info("")

    found_running = False
    for url in ignition_urls:
        is_running = await check_server(url)
        if is_running:
            found_running = True
            logger.info("")
            logger.info(f"✓ Found running server at: {url}")
        logger.info("")

    if not found_running:
        logger.warning("No running OPC UA servers found at common Ignition ports")
        logger.info("")
        logger.info("Common Ignition OPC UA server URLs:")
        logger.info("  - opc.tcp://localhost:62541 (default Ignition port)")
        logger.info("  - opc.tcp://localhost:4840 (alternative port)")
        logger.info("")
        logger.info("To check a specific URL, use:")
        logger.info("  python check_server.py --url opc.tcp://localhost:62541")


def main():
    parser = argparse.ArgumentParser(description="Check if an OPC UA server is running")
    parser.add_argument(
        "--url",
        help="OPC UA server URL to check (if not provided, checks common Ignition ports)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="Connection timeout in seconds (default: 5)",
    )

    args = parser.parse_args()

    if args.url:
        # Check specific URL
        result = asyncio.run(check_server(args.url, args.timeout))
        sys.exit(0 if result else 1)
    else:
        # Check common Ignition URLs
        asyncio.run(check_ignition_default())


if __name__ == "__main__":
    main()
