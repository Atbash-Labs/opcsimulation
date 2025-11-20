"""
Unit tests for OPC UA sync tool
"""
import pytest
import asyncio
import json
import tempfile
import os
import sys
import subprocess
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from asyncua import Client
from opc_utils import create_client, get_all_nodes, write_node_value
from export_opc_nodes import export_nodes
from import_opc_nodes import import_nodes


@pytest.fixture
def event_loop():
    """Create an event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_export_file():
    """Create a temporary export file"""
    fd, path = tempfile.mkstemp(suffix='.json', prefix='opc_test_')
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def test_server_process():
    """Start a test server process"""
    # Start server on a different port for testing
    port = 4850
    process = subprocess.Popen(
        ['python', 'test_server.py', '--port', str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for server to start
    time.sleep(3)
    
    yield port, process
    
    # Cleanup
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


@pytest.fixture
def destination_server_process():
    """Start a destination test server process"""
    # Start server on a different port for testing
    port = 4851
    process = subprocess.Popen(
        ['python', 'test_server.py', '--port', str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for server to start
    time.sleep(3)
    
    yield port, process
    
    # Cleanup
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


class TestOPCExport:
    """Test OPC UA export functionality"""
    
    @pytest.mark.asyncio
    async def test_export_nodes(self, test_server_process, temp_export_file):
        """Test exporting nodes from a server"""
        port, _ = test_server_process
        source_url = f"opc.tcp://localhost:{port}/freeopcua/server/"
        
        # Export nodes
        await export_nodes(
            source_url=source_url,
            output_file=temp_export_file
        )
        
        # Verify export file exists and has content
        assert os.path.exists(temp_export_file), "Export file should exist"
        
        with open(temp_export_file, 'r') as f:
            export_data = json.load(f)
        
        assert 'nodes' in export_data, "Export should contain nodes"
        assert 'source_url' in export_data, "Export should contain source URL"
        assert 'total_nodes' in export_data, "Export should contain total nodes count"
        assert len(export_data['nodes']) > 0, "Export should have at least one node"
        
        # Verify we exported some expected nodes
        def find_node_by_name(nodes, name):
            """Recursively find a node by browse name"""
            for node in nodes:
                if node.get('browse_name') == name:
                    return node
                if 'children' in node:
                    result = find_node_by_name(node['children'], name)
                    if result:
                        return result
            return None
        
        test_folder = find_node_by_name(export_data['nodes'], 'TestFolder')
        assert test_folder is not None, "Should find TestFolder"
        
        # Check for nested folder
        nested_folder = find_node_by_name(
            test_folder.get('children', []), 
            'NestedFolder'
        )
        assert nested_folder is not None, "Should find NestedFolder"
    
    @pytest.mark.asyncio
    async def test_export_contains_variable_values(self, test_server_process, temp_export_file):
        """Test that exported nodes contain variable values"""
        port, _ = test_server_process
        source_url = f"opc.tcp://localhost:{port}/freeopcua/server/"
        
        # Export nodes
        await export_nodes(
            source_url=source_url,
            output_file=temp_export_file
        )
        
        with open(temp_export_file, 'r') as f:
            export_data = json.load(f)
        
        # Find TestInt variable
        def find_variable(nodes, name):
            """Recursively find a variable by browse name"""
            for node in nodes:
                if node.get('node_class') == 'Variable' and node.get('browse_name') == name:
                    return node
                if 'children' in node:
                    result = find_variable(node['children'], name)
                    if result:
                        return result
            return None
        
        test_int = find_variable(export_data['nodes'], 'TestInt')
        assert test_int is not None, "Should find TestInt variable"
        assert 'value' in test_int, "Variable should have a value"
        assert test_int['value'] == 42, "TestInt should have value 42"
        
        test_string = find_variable(export_data['nodes'], 'TestString')
        assert test_string is not None, "Should find TestString variable"
        assert test_string['value'] == "Hello OPC UA", "TestString should have correct value"


class TestOPCImport:
    """Test OPC UA import functionality"""
    
    @pytest.mark.asyncio
    async def test_import_modifies_values(self, test_server_process, destination_server_process, temp_export_file):
        """Test that importing nodes modifies values on destination server"""
        source_port, _ = test_server_process
        dest_port, _ = destination_server_process
        
        source_url = f"opc.tcp://localhost:{source_port}/freeopcua/server/"
        dest_url = f"opc.tcp://localhost:{dest_port}/freeopcua/server/"
        
        # Step 1: Export from source server
        await export_nodes(
            source_url=source_url,
            output_file=temp_export_file
        )
        
        # Step 2: Modify values in export file
        with open(temp_export_file, 'r') as f:
            export_data = json.load(f)
        
        def modify_variable_value(nodes, browse_name, new_value):
            """Recursively modify a variable's value"""
            for node in nodes:
                if node.get('node_class') == 'Variable' and node.get('browse_name') == browse_name:
                    node['value'] = new_value
                    return True
                if 'children' in node:
                    if modify_variable_value(node['children'], browse_name, new_value):
                        return True
            return False
        
        # Modify some values
        modify_variable_value(export_data['nodes'], 'TestInt', 999)
        modify_variable_value(export_data['nodes'], 'TestString', 'Modified Value')
        modify_variable_value(export_data['nodes'], 'TestFloat', 99.99)
        modify_variable_value(export_data['nodes'], 'TestBool', False)
        
        # Save modified export
        with open(temp_export_file, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        # Step 3: Import to destination server
        await import_nodes(
            destination_url=dest_url,
            input_file=temp_export_file
        )
        
        # Step 4: Browse destination server and verify values changed
        client = await create_client(dest_url)
        try:
            nodes = await get_all_nodes(client)
            
            def find_variable_value(nodes, browse_name):
                """Recursively find a variable's value"""
                for node in nodes:
                    if node.get('node_class') == 'Variable' and node.get('browse_name') == browse_name:
                        return node.get('value')
                    if 'children' in node:
                        result = find_variable_value(node['children'], browse_name)
                        if result is not None:
                            return result
                return None
            
            # Verify values were updated
            test_int_value = find_variable_value(nodes, 'TestInt')
            assert test_int_value == 999, f"TestInt should be 999, got {test_int_value}"
            
            test_string_value = find_variable_value(nodes, 'TestString')
            assert test_string_value == 'Modified Value', f"TestString should be 'Modified Value', got {test_string_value}"
            
            test_float_value = find_variable_value(nodes, 'TestFloat')
            assert abs(test_float_value - 99.99) < 0.01, f"TestFloat should be ~99.99, got {test_float_value}"
            
            test_bool_value = find_variable_value(nodes, 'TestBool')
            assert test_bool_value == False, f"TestBool should be False, got {test_bool_value}"
            
        finally:
            await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_import_preserves_structure(self, test_server_process, destination_server_process, temp_export_file):
        """Test that import preserves node structure"""
        source_port, _ = test_server_process
        dest_port, _ = destination_server_process
        
        source_url = f"opc.tcp://localhost:{source_port}/freeopcua/server/"
        dest_url = f"opc.tcp://localhost:{dest_port}/freeopcua/server/"
        
        # Export from source
        await export_nodes(
            source_url=source_url,
            output_file=temp_export_file
        )
        
        # Import to destination
        await import_nodes(
            destination_url=dest_url,
            input_file=temp_export_file
        )
        
        # Browse destination and verify structure
        client = await create_client(dest_url)
        try:
            nodes = await get_all_nodes(client)
            
            def find_node_by_name(nodes, name):
                """Recursively find a node by browse name"""
                for node in nodes:
                    if node.get('browse_name') == name:
                        return node
                    if 'children' in node:
                        result = find_node_by_name(node['children'], name)
                        if result:
                            return result
                return None
            
            # Verify structure exists
            test_folder = find_node_by_name(nodes, 'TestFolder')
            assert test_folder is not None, "TestFolder should exist"
            
            nested_folder = find_node_by_name(
                test_folder.get('children', []),
                'NestedFolder'
            )
            assert nested_folder is not None, "NestedFolder should exist"
            
            production_folder = find_node_by_name(nodes, 'Production')
            assert production_folder is not None, "Production folder should exist"
            
            line1 = find_node_by_name(
                production_folder.get('children', []),
                'Line1'
            )
            assert line1 is not None, "Line1 should exist"
            
        finally:
            await client.disconnect()


class TestOPCIntegration:
    """Integration tests for full export/import cycle"""
    
    @pytest.mark.asyncio
    async def test_full_export_import_cycle(self, test_server_process, destination_server_process, temp_export_file):
        """Test complete export/import cycle"""
        source_port, _ = test_server_process
        dest_port, _ = destination_server_process
        
        source_url = f"opc.tcp://localhost:{source_port}/freeopcua/server/"
        dest_url = f"opc.tcp://localhost:{dest_port}/freeopcua/server/"
        
        # Export
        await export_nodes(
            source_url=source_url,
            output_file=temp_export_file
        )
        
        # Verify export
        with open(temp_export_file, 'r') as f:
            export_data = json.load(f)
        
        assert export_data.get('total_nodes', 0) > 0, "Should export nodes"
        
        # Modify values
        def modify_all_variables(nodes, multiplier=2):
            """Multiply all numeric values by multiplier"""
            for node in nodes:
                if node.get('node_class') == 'Variable':
                    value = node.get('value')
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        node['value'] = value * multiplier
                if 'children' in node:
                    modify_all_variables(node['children'], multiplier)
        
        modify_all_variables(export_data['nodes'])
        
        with open(temp_export_file, 'w') as f:
            json.dump(export_data, f, indent=2, default=str)
        
        # Import
        await import_nodes(
            destination_url=dest_url,
            input_file=temp_export_file
        )
        
        # Verify import
        client = await create_client(dest_url)
        try:
            nodes = await get_all_nodes(client)
            
            def find_variable_value(nodes, browse_name):
                """Find variable value"""
                for node in nodes:
                    if node.get('node_class') == 'Variable' and node.get('browse_name') == browse_name:
                        return node.get('value')
                    if 'children' in node:
                        result = find_variable_value(node['children'], browse_name)
                        if result is not None:
                            return result
                return None
            
            # Original TestInt was 42, should now be 84 (42 * 2)
            test_int = find_variable_value(nodes, 'TestInt')
            assert test_int == 84, f"TestInt should be 84 (42*2), got {test_int}"
            
        finally:
            await client.disconnect()

