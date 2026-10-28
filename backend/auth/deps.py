"""Authentication dependencies for standalone chatbot."""
from typing import Dict, Any


async def get_current_user() -> Dict[str, Any]:
    """
    Default authenticated user dependency in standalone mode.
    Returns admin user credentials without requiring external auth tokens.
    """
    return {
        "id": "admin-standalone",
        "username": "admin",
        "role": "admin",
        "is_admin": True,
    }
