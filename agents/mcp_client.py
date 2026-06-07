import asyncio
import threading
import sys
import os
from typing import Any
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

class SyncMCPClient:
    def __init__(self, server_script: str, cwd: str):
        self.server_script = server_script
        self.cwd = cwd
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.ready_event = threading.Event()
        self.session = None
        self._exit_stack = None
        self.thread.start()
        self.ready_event.wait(timeout=15)
        if not self.session:
            raise RuntimeError("Failed to initialize MCP session within timeout.")

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._connect())
        self.ready_event.set()
        self.loop.run_forever()

    async def _connect(self):
        from contextlib import AsyncExitStack
        self._exit_stack = AsyncExitStack()
        
        env = os.environ.copy()
        
        server_params = StdioServerParameters(
            command="python",
            args=[self.server_script],
            env=env
        )
        
        # NOTE: stdio_client changes cwd? No, it doesn't take cwd.
        # But we can just use absolute path for the script.
        stdio_transport = await self._exit_stack.enter_async_context(stdio_client(server_params))
        read, write = stdio_transport
        
        self.session = await self._exit_stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()

    def call_tool(self, tool_name: str, arguments: dict) -> Any:
        future = asyncio.run_coroutine_threadsafe(
            self.session.call_tool(tool_name, arguments=arguments),
            self.loop
        )
        return future.result(timeout=30)
        
    def close(self):
        async def _close():
            if self._exit_stack:
                await self._exit_stack.aclose()
            self.loop.stop()
        if self.loop.is_running():
            asyncio.run_coroutine_threadsafe(_close(), self.loop)


