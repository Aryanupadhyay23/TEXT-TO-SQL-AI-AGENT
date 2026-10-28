"""
Frontend Configuration & Constants
Centralized table domains, sample queries, and technical specifications.
"""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
SCHEMA_FILES_DIR = BACKEND_DIR / "chatbot" / "schema_files"

# 27 Core Tables in ecommerce_db categorized into 7 domains
TABLE_DOMAINS = {
    "Users & Profiles": ["users", "customer_profiles", "user_addresses"],
    "Catalog & Merchandise": ["products", "product_variants", "product_images", "categories", "brands"],
    "Inventory & Logistics": ["inventory_items", "stock_movements", "warehouses", "shipments"],
    "Orders & Sales": ["orders", "order_items", "order_status_history", "payments", "refunds"],
    "Promotions & Marketing": ["coupons", "coupon_redemptions"],
    "Carts & Wishlists": ["shopping_carts", "cart_items", "wishlists", "wishlist_items"],
    "Feedback & RMA": ["product_reviews", "review_helpful_votes", "return_requests", "return_items"],
}

# Curated suggestions for the chat agent
SAMPLE_QUERIES = [
    "What are the top 3 highest revenue product categories?",
    "How many registered customers have gold tier membership?",
    "How many return items were restocked versus rejected?",
    "List top 5 products by price.",
    "Show all delivered orders in 2025.",
    "Which products are currently below their safety inventory threshold?",
]

# System specs for architecture viewer
SYSTEM_SPECIFICATIONS = [
    {"Component": "Foundation LLM", "Technology": "ChatOllama (gemma4:31b-cloud)", "Role": "Query Understanding, Autonomous Tool Reasoning, & SQL Synthesis"},
    {"Component": "Vector Embeddings", "Technology": "Nomic Embed (nomicapi.duckdns.org)", "Role": "Semantic Search across Schema, Business Rules, & Few-Shots"},
    {"Component": "Vector Database", "Technology": "ChromaDB (3 Collections)", "Role": "Stores 56+ Golden SQL Pairs, Business Rules, & Schema Cards"},
    {"Component": "Primary Database", "Technology": "Aiven Cloud MySQL 8.0+", "Role": "27 Relational Tables (ecommerce_db)"},
    {"Component": "Agent Orchestration", "Technology": "LangGraph (StateGraph)", "Role": "Multi-Step Graph with Dynamic Routing & Checkpointing"},
    {"Component": "Bound Tools", "Technology": "run_sql & search_knowledge_and_examples", "Role": "Autonomous Introspection & Schema Exploration"},
    {"Component": "Frontend", "Technology": "Streamlit 1.62+ Multipage", "Role": "Zero-Authentication Guest Access & Real-Time Pipeline Viewer"},
]
