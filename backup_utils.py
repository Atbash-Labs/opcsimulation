from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from pathlib import Path
import json
import os
import shutil
import sqlite3
import zipfile
import uuid
import argparse


class BackupModifier:
    def __init__(self, backup_path: str):
        self.backup_path = backup_path
        self.temp_dir = None
        self.zip_ref = None
        self.db_file_name = "db_backup_sqlite.idb"  # Assuming this is the standard name
        self.extracted_db_path = None

    def __enter__(self):
        # Create a temporary directory in the current workspace
        temp_dir_name = f"temp_backup_{str(uuid.uuid4())[:8]}"
        self.temp_dir = os.path.abspath(temp_dir_name)
        os.makedirs(self.temp_dir, exist_ok=True)
        print(f"Created temporary directory: {self.temp_dir}")

        try:
            # Open the backup file as a zip
            self.zip_ref = zipfile.ZipFile(self.backup_path, "r")

            # Find and extract only the database file
            db_extracted = False
            for file_info in self.zip_ref.filelist:
                # Check if the file is the database file (e.g., at the root or specific known path)
                # For simplicity, we'll assume it's named db_backup_sqlite.idb at the root.
                # A more robust solution might check for file_info.filename.endswith(self.db_file_name)
                # and potentially its path if it's nested.
                if file_info.filename == self.db_file_name:
                    self.extracted_db_path = os.path.join(
                        self.temp_dir, self.db_file_name
                    )
                    # Ensure parent directory for the db file exists if it's nested (not the case here)
                    # os.makedirs(os.path.dirname(self.extracted_db_path), exist_ok=True)
                    with open(self.extracted_db_path, "wb") as f_out:
                        f_out.write(self.zip_ref.read(file_info.filename))
                    db_extracted = True
                    print(
                        f"Extracted database file: {file_info.filename} to {self.extracted_db_path}"
                    )
                    break  # Found and extracted the DB file

            if not db_extracted:
                raise FileNotFoundError(
                    f"Database file '{self.db_file_name}' not found in the backup."
                )

            return self

        except Exception as e:
            print(f"Error during extraction: {str(e)}")
            if self.zip_ref:
                self.zip_ref.close()
            # Clean up temp_dir on error during __enter__
            if self.temp_dir and os.path.exists(self.temp_dir):
                try:
                    shutil.rmtree(self.temp_dir)
                except Exception as cleanup_e:
                    print(f"Warning: Failed to clean up temp_dir on error: {cleanup_e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.zip_ref:
            self.zip_ref.close()
        if self.temp_dir:
            self.cleanup()
        # Removed cleanup of temp_dir to allow inspection

    def get_temp_dir(self):
        return self.temp_dir

    def create_modified_backup(self, output_path: str):
        if not self.temp_dir:
            raise Exception("No temporary directory available")
        if not self.extracted_db_path or not os.path.exists(self.extracted_db_path):
            raise Exception(
                f"Extracted database file '{self.db_file_name}' not found or not accessible."
            )
        if not self.zip_ref:
            raise Exception("Original zip reference is not available.")

        # Create a new zip file
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # 1. Add the modified database file from the temporary directory
            zipf.write(self.extracted_db_path, self.db_file_name)
            print(f"Added modified database file '{self.db_file_name}' to new backup.")

            # 2. Copy all other files from the original zip
            for item in self.zip_ref.infolist():
                if item.filename != self.db_file_name:
                    # Read content from old zip and write to new zip
                    buffer = self.zip_ref.read(item.filename)
                    zipf.writestr(item, buffer)
            print(f"Copied all other files from original backup.")

    def cleanup(self):
        """Clean up the temporary directory if it exists"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                print(f"Cleaned up temporary directory: {self.temp_dir}")
            except Exception as e:
                print(f"Warning: Failed to clean up temporary directory: {str(e)}")


class TagUtil:
    """API for tag operations in an Ignition backup"""

    def __init__(self, backup: BackupModifier):
        self._backup = backup
        self._db_path = None
        self._conn = None
        self._cursor = None

    def __enter__(self):
        """Context manager entry - opens database connection"""
        # Find and open the database
        self._db_path = str(Path(self._backup.get_temp_dir()) / "db_backup_sqlite.idb")
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._cursor = self._conn.cursor()
        self._conn.execute("BEGIN TRANSACTION")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - commits changes and closes database"""
        if self._conn:
            if exc_type:

                self._conn.rollback()
            else:
                self._conn.commit()
            self._conn.close()

    def get_gateway_name(self) -> Optional[str]:
        """Get the gateway name from the SysProps table."""
        if not self._cursor:
            print("Error: Database cursor is not available.")
            return None
        try:
            self._cursor.execute("SELECT SystemName FROM SysProps LIMIT 1")
            result = self._cursor.fetchone()
            if result:
                return result["SystemName"]
            else:
                print("Error: SystemName not found in SysProps table.")
                return None
        except sqlite3.Error as e:
            print(f"Database error while fetching gateway name: {e}")
            return None

    def update_gateway_name(self, new_name: str) -> bool:
        """Update the gateway name in the SysProps table."""
        if not self._cursor:
            print("Error: Database cursor is not available.")
            return False
        if not self._conn:  # Ensure connection is available for commit
            print("Error: Database connection is not available.")
            return False
        try:
            # Check if a record exists, as SysProps might be empty or not have SystemName
            self._cursor.execute("SELECT SystemName FROM SysProps LIMIT 1")
            existing_record = self._cursor.fetchone()

            if existing_record:
                self._cursor.execute("UPDATE SysProps SET SystemName = ?", (new_name,))
            else:
                # If no record exists, insert a new one.
                # This assumes other properties might be missing or have defaults.
                # A more robust solution might require knowing all columns for SysProps.
                self._cursor.execute(
                    "INSERT INTO SysProps (SystemName) VALUES (?)", (new_name,)
                )

            self._conn.commit()  # Commit the change immediately after execution
            print(f"Gateway name updated to: {new_name}")
            return True
        except sqlite3.Error as e:
            print(f"Database error while updating gateway name: {e}")
            self._conn.rollback()  # Rollback on error
            return False

    def update_opc_server_connection(self, old_url: str, new_local_url: str) -> bool:
        """Update OPC server connection settings in the opcuaserverconnectionsettings table.

        Finds rows where DISCOVERYURL or ENDPOINTURL matches old_url and updates them to:
        - Set DISCOVERYURL and ENDPOINTURL to new_local_url
        - Set SECURITYPOLICY to 'None'
        - Set SECURITYMODE to 'None'
        - Clear USERNAME and PASSWORD (set to empty string)

        Args:
            old_url: The URL to match against (DISCOVERYURL or ENDPOINTURL)
            new_local_url: The new local OPC server URL to use

        Returns:
            True if update was successful, False otherwise
        """
        if not self._cursor:
            print("Error: Database cursor is not available.")
            return False
        if not self._conn:
            print("Error: Database connection is not available.")
            return False
        try:
            # First, find matching rows
            self._cursor.execute(
                """SELECT SERVERSETTINGSID, DISCOVERYURL, ENDPOINTURL 
                   FROM opcuaserverconnectionsettings 
                   WHERE DISCOVERYURL = ? OR ENDPOINTURL = ?""",
                (old_url, old_url),
            )
            matching_rows = self._cursor.fetchall()

            if not matching_rows:
                print(f"No rows found matching URL: {old_url}")
                return False

            print(f"Found {len(matching_rows)} row(s) matching URL: {old_url}")

            # Update each matching row
            for row in matching_rows:
                server_settings_id = row["SERVERSETTINGSID"]
                print(
                    f"Updating SERVERSETTINGSID {server_settings_id}: "
                    f"DISCOVERYURL={row['DISCOVERYURL']}, ENDPOINTURL={row['ENDPOINTURL']}"
                )

                self._cursor.execute(
                    """UPDATE opcuaserverconnectionsettings 
                       SET DISCOVERYURL = ?,
                           ENDPOINTURL = ?,
                           SECURITYPOLICY = ?,
                           SECURITYMODE = ?,
                           USERNAME = ?,
                           PASSWORD = ?
                       WHERE SERVERSETTINGSID = ?""",
                    (
                        new_local_url,
                        new_local_url,
                        "None",
                        "None",
                        "",  # Empty username
                        "",  # Empty password
                        server_settings_id,
                    ),
                )

            print(
                f"Successfully updated {len(matching_rows)} row(s) to use local URL: {new_local_url}"
            )
            return True
        except sqlite3.Error as e:
            print(f"Database error while updating OPC server connection: {e}")
            self._conn.rollback()  # Rollback on error
            return False


def main():
    """Update OPC server connection settings in an Ignition backup file."""
    # Setup argparse
    parser = argparse.ArgumentParser(
        description="Update OPC server connection settings in an Ignition backup file."
    )
    parser.add_argument("backup_path", help="Path to the input .gwbk backup file.")
    parser.add_argument(
        "output_backup_path", help="Path to save the modified .gwbk backup file."
    )
    parser.add_argument(
        "old_url",
        help="The URL to match against (DISCOVERYURL or ENDPOINTURL) in opcuaserverconnectionsettings table.",
    )
    parser.add_argument(
        "new_local_url",
        help="The new local OPC server URL to use (will be set for both DISCOVERYURL and ENDPOINTURL).",
    )

    args = parser.parse_args()

    backup_path = args.backup_path
    output_backup_path = args.output_backup_path
    old_url = args.old_url
    new_local_url = args.new_local_url

    print(f"Attempting to read backup file: {backup_path}")
    print(f"Output path for modified backup: {output_backup_path}")
    print(f"Old URL to match: {old_url}")
    print(f"New local OPC server URL: {new_local_url}")

    try:
        with BackupModifier(backup_path) as backup:
            print("BackupModifier entered successfully.")
            with TagUtil(backup) as tag_util:
                print("TagUtil entered successfully.")

                # Update the OPC server connection settings
                print(
                    f"Attempting to update OPC server connection settings from '{old_url}' to '{new_local_url}'"
                )
                update_success = tag_util.update_opc_server_connection(
                    old_url, new_local_url
                )

                if update_success:
                    print(
                        "OPC server connection settings update successful in database."
                    )
                else:
                    print("OPC server connection settings update failed in database.")

            # Save the modified backup
            # Ensure this is called outside the TagUtil context but inside BackupModifier context
            print(f"Attempting to save modified backup to: {output_backup_path}")
            backup.create_modified_backup(output_backup_path)
            print(f"Modified backup saved to {output_backup_path}")

    except FileNotFoundError:
        print(f"Error: Backup file not found at {backup_path}")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
