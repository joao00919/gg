"""
WebSocket connections module
"""

from .ws_manager import WSManager

# Global instance
ws_manager = None

def setup(bot):
    """Setup WebSocket connections"""
    global ws_manager
    
    # Create WebSocket manager
    ws_manager = WSManager(bot)
    
    # Store reference in bot
    bot.ws_manager = ws_manager
    
    return ws_manager

async def initialize(bot):
    """Initialize and connect WebSocket"""
    global ws_manager
    
    if ws_manager is None:
        ws_manager = setup(bot)
    
    await ws_manager.initialize()
    return ws_manager

def get_manager():
    """Get WebSocket manager instance"""
    return ws_manager

# Backwards compatibility
websocket_manager = None
WebSocketManager = WSManager
