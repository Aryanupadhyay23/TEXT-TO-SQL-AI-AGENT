"""
Centralized Chatbot Database Connection

Uses the readymade chatbot_db_manager from backend/conf/database.py.
"""

from conf.database import chatbot_db_manager as db_manager

__all__ = ["db_manager"]
