"""
Test OPC UA server for testing the export/import functionality
"""

import asyncio
import argparse
from asyncua import Server, ua
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Suppress INFO messages from asyncua about namespace 0 nodes (standard OPC UA nodes)
# These are normal during server initialization
asyncua_logger = logging.getLogger("asyncua")
asyncua_logger.setLevel(logging.WARNING)  # Only show WARNING and above from asyncua


async def create_test_server(port: int = 4840):
    """
    Create a test OPC UA server with sample nodes

    Args:
        port: Port to run the server on
    """
    server = Server()
    await server.init()

    server.set_endpoint(f"opc.tcp://0.0.0.0:{port}/freeopcua/server/")
    server.set_server_name("Test OPC UA Server")

    # Setup namespace
    uri = "http://examples.freeopcua.github.io"
    idx = await server.register_namespace(uri)

    # Get Objects node
    objects = server.get_objects_node()

    # Create a test folder
    test_folder = await objects.add_folder(idx, "TestFolder")

    # Add some test variables
    var1 = await test_folder.add_variable(idx, "TestInt", 42)
    await var1.set_writable()

    var2 = await test_folder.add_variable(idx, "TestFloat", 3.14)
    await var2.set_writable()

    var3 = await test_folder.add_variable(idx, "TestString", "Hello OPC UA")
    await var3.set_writable()

    var4 = await test_folder.add_variable(idx, "TestBool", True)
    await var4.set_writable()

    # Create a nested folder
    nested_folder = await test_folder.add_folder(idx, "NestedFolder")

    var5 = await nested_folder.add_variable(idx, "NestedInt", 100)
    await var5.set_writable()

    var6 = await nested_folder.add_variable(idx, "NestedString", "Nested Value")
    await var6.set_writable()

    # Add some read-only variables
    read_only_var = await test_folder.add_variable(idx, "ReadOnlyVar", 999)
    # Don't set writable, so it's read-only

    logger.info(f"Test server created with nodes:")
    logger.info(f"  - TestFolder/TestInt = 42")
    logger.info(f"  - TestFolder/TestFloat = 3.14")
    logger.info(f"  - TestFolder/TestString = 'Hello OPC UA'")
    logger.info(f"  - TestFolder/TestBool = True")
    logger.info(f"  - TestFolder/NestedFolder/NestedInt = 100")
    logger.info(f"  - TestFolder/NestedFolder/NestedString = 'Nested Value'")
    logger.info(f"  - TestFolder/ReadOnlyVar = 999 (read-only)")

    async with server:
        logger.info(f"Test OPC UA server started on port {port}")
        logger.info(f"Server endpoint: opc.tcp://localhost:{port}/freeopcua/server/")
        logger.info("Press Ctrl+C to stop the server")

        try:
            # Keep server running
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down server...")


def main():
    parser = argparse.ArgumentParser(description="Run a test OPC UA server")
    parser.add_argument(
        "--port",
        type=int,
        default=4840,
        help="Port to run the server on (default: 4840)",
    )

    args = parser.parse_args()

    try:
        asyncio.run(create_test_server(args.port))
    except KeyboardInterrupt:
        logger.info("Server stopped")


if __name__ == "__main__":
    main()
