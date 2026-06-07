import os
import sys

# Add agent-game to sys path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from agents.mcp_client import SyncMCPClient

print("Initializing SyncMCPClient...")
try:
    script_path = os.path.join("dnd-mcp", "dnd_mcp_server.py")
    print(f"Using server script path: {script_path}")
    client = SyncMCPClient(script_path, cwd=os.getcwd())
    print("Initialization successful!")
    client.close()
except Exception as e:
    import traceback
    traceback.print_exc()
