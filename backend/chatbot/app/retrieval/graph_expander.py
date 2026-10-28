"""Relational Schema Graph Expander for Foreign Key / Bridge Table Traversal."""

import networkx as nx
from typing import List, Dict, Any
from pathlib import Path
import json

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
JOIN_INFO_DIR = BACKEND_DIR / "schema_files" / "join_information"

# Default schema relationships for all 27 tables in ecommerce_db
KNOWN_RELATIONSHIPS = [
    # Users & Profiles
    {
        "from_table": "customer_profiles",
        "from_column": "user_id",
        "to_table": "users",
        "to_column": "id",
        "join_condition": "customer_profiles.user_id = users.id",
    },
    {
        "from_table": "user_addresses",
        "from_column": "user_id",
        "to_table": "users",
        "to_column": "id",
        "join_condition": "user_addresses.user_id = users.id",
    },
    # Catalog & Taxonomy
    {
        "from_table": "products",
        "from_column": "brand_id",
        "to_table": "brands",
        "to_column": "id",
        "join_condition": "products.brand_id = brands.id",
    },
    {
        "from_table": "products",
        "from_column": "category_id",
        "to_table": "categories",
        "to_column": "id",
        "join_condition": "products.category_id = categories.id",
    },
    {
        "from_table": "categories",
        "from_column": "parent_id",
        "to_table": "categories",
        "to_column": "id",
        "join_condition": "categories.parent_id = categories.id",
    },
    {
        "from_table": "product_variants",
        "from_column": "product_id",
        "to_table": "products",
        "to_column": "id",
        "join_condition": "product_variants.product_id = products.id",
    },
    {
        "from_table": "product_images",
        "from_column": "product_id",
        "to_table": "products",
        "to_column": "id",
        "join_condition": "product_images.product_id = products.id",
    },
    {
        "from_table": "product_images",
        "from_column": "variant_id",
        "to_table": "product_variants",
        "to_column": "id",
        "join_condition": "product_images.variant_id = product_variants.id",
    },
    # Inventory & Warehousing
    {
        "from_table": "inventory_items",
        "from_column": "warehouse_id",
        "to_table": "warehouses",
        "to_column": "id",
        "join_condition": "inventory_items.warehouse_id = warehouses.id",
    },
    {
        "from_table": "inventory_items",
        "from_column": "variant_id",
        "to_table": "product_variants",
        "to_column": "id",
        "join_condition": "inventory_items.variant_id = product_variants.id",
    },
    {
        "from_table": "stock_movements",
        "from_column": "inventory_item_id",
        "to_table": "inventory_items",
        "to_column": "id",
        "join_condition": "stock_movements.inventory_item_id = inventory_items.id",
    },
    # Carts & Wishlists
    {
        "from_table": "shopping_carts",
        "from_column": "user_id",
        "to_table": "users",
        "to_column": "id",
        "join_condition": "shopping_carts.user_id = users.id",
    },
    {
        "from_table": "cart_items",
        "from_column": "cart_id",
        "to_table": "shopping_carts",
        "to_column": "id",
        "join_condition": "cart_items.cart_id = shopping_carts.id",
    },
    {
        "from_table": "cart_items",
        "from_column": "variant_id",
        "to_table": "product_variants",
        "to_column": "id",
        "join_condition": "cart_items.variant_id = product_variants.id",
    },
    {
        "from_table": "wishlists",
        "from_column": "user_id",
        "to_table": "users",
        "to_column": "id",
        "join_condition": "wishlists.user_id = users.id",
    },
    {
        "from_table": "wishlist_items",
        "from_column": "wishlist_id",
        "to_table": "wishlists",
        "to_column": "id",
        "join_condition": "wishlist_items.wishlist_id = wishlists.id",
    },
    {
        "from_table": "wishlist_items",
        "from_column": "product_id",
        "to_table": "products",
        "to_column": "id",
        "join_condition": "wishlist_items.product_id = products.id",
    },
    {
        "from_table": "wishlist_items",
        "from_column": "variant_id",
        "to_table": "product_variants",
        "to_column": "id",
        "join_condition": "wishlist_items.variant_id = product_variants.id",
    },
    # Orders & Order Items
    {
        "from_table": "orders",
        "from_column": "user_id",
        "to_table": "users",
        "to_column": "id",
        "join_condition": "orders.user_id = users.id",
    },
    {
        "from_table": "orders",
        "from_column": "shipping_address_id",
        "to_table": "user_addresses",
        "to_column": "id",
        "join_condition": "orders.shipping_address_id = user_addresses.id",
    },
    {
        "from_table": "order_items",
        "from_column": "order_id",
        "to_table": "orders",
        "to_column": "id",
        "join_condition": "order_items.order_id = orders.id",
    },
    {
        "from_table": "order_items",
        "from_column": "variant_id",
        "to_table": "product_variants",
        "to_column": "id",
        "join_condition": "order_items.variant_id = product_variants.id",
    },
    {
        "from_table": "order_items",
        "from_column": "product_id",
        "to_table": "products",
        "to_column": "id",
        "join_condition": "order_items.product_id = products.id",
    },
    {
        "from_table": "order_items",
        "from_column": "category_id",
        "to_table": "categories",
        "to_column": "id",
        "join_condition": "order_items.category_id = categories.id",
    },
    {
        "from_table": "order_status_history",
        "from_column": "order_id",
        "to_table": "orders",
        "to_column": "id",
        "join_condition": "order_status_history.order_id = orders.id",
    },
    # Payments, Shipments & Refunds
    {
        "from_table": "payments",
        "from_column": "order_id",
        "to_table": "orders",
        "to_column": "id",
        "join_condition": "payments.order_id = orders.id",
    },
    {
        "from_table": "shipments",
        "from_column": "order_id",
        "to_table": "orders",
        "to_column": "id",
        "join_condition": "shipments.order_id = orders.id",
    },
    {
        "from_table": "shipments",
        "from_column": "warehouse_id",
        "to_table": "warehouses",
        "to_column": "id",
        "join_condition": "shipments.warehouse_id = warehouses.id",
    },
    {
        "from_table": "refunds",
        "from_column": "order_id",
        "to_table": "orders",
        "to_column": "id",
        "join_condition": "refunds.order_id = orders.id",
    },
    {
        "from_table": "refunds",
        "from_column": "payment_id",
        "to_table": "payments",
        "to_column": "id",
        "join_condition": "refunds.payment_id = payments.id",
    },
    # Coupons & Redemptions
    {
        "from_table": "coupon_redemptions",
        "from_column": "coupon_id",
        "to_table": "coupons",
        "to_column": "id",
        "join_condition": "coupon_redemptions.coupon_id = coupons.id",
    },
    {
        "from_table": "coupon_redemptions",
        "from_column": "order_id",
        "to_table": "orders",
        "to_column": "id",
        "join_condition": "coupon_redemptions.order_id = orders.id",
    },
    {
        "from_table": "coupon_redemptions",
        "from_column": "user_id",
        "to_table": "users",
        "to_column": "id",
        "join_condition": "coupon_redemptions.user_id = users.id",
    },
    # Reviews & Feedback
    {
        "from_table": "product_reviews",
        "from_column": "product_id",
        "to_table": "products",
        "to_column": "id",
        "join_condition": "product_reviews.product_id = products.id",
    },
    {
        "from_table": "product_reviews",
        "from_column": "user_id",
        "to_table": "users",
        "to_column": "id",
        "join_condition": "product_reviews.user_id = users.id",
    },
    {
        "from_table": "product_reviews",
        "from_column": "order_id",
        "to_table": "orders",
        "to_column": "id",
        "join_condition": "product_reviews.order_id = orders.id",
    },
    {
        "from_table": "product_reviews",
        "from_column": "order_item_id",
        "to_table": "order_items",
        "to_column": "id",
        "join_condition": "product_reviews.order_item_id = order_items.id",
    },
    {
        "from_table": "review_helpful_votes",
        "from_column": "review_id",
        "to_table": "product_reviews",
        "to_column": "id",
        "join_condition": "review_helpful_votes.review_id = product_reviews.id",
    },
    {
        "from_table": "review_helpful_votes",
        "from_column": "user_id",
        "to_table": "users",
        "to_column": "id",
        "join_condition": "review_helpful_votes.user_id = users.id",
    },
    # RMAs & Returns
    {
        "from_table": "return_requests",
        "from_column": "order_id",
        "to_table": "orders",
        "to_column": "id",
        "join_condition": "return_requests.order_id = orders.id",
    },
    {
        "from_table": "return_requests",
        "from_column": "user_id",
        "to_table": "users",
        "to_column": "id",
        "join_condition": "return_requests.user_id = users.id",
    },
    {
        "from_table": "return_items",
        "from_column": "return_request_id",
        "to_table": "return_requests",
        "to_column": "id",
        "join_condition": "return_items.return_request_id = return_requests.id",
    },
    {
        "from_table": "return_items",
        "from_column": "order_item_id",
        "to_table": "order_items",
        "to_column": "id",
        "join_condition": "return_items.order_item_id = order_items.id",
    },
]


def _load_relationships_from_files() -> List[Dict[str, Any]]:
    """Loads relationships from schema_files/join_information/*.json if available."""
    loaded = []
    if JOIN_INFO_DIR.exists():
        for json_file in sorted(JOIN_INFO_DIR.glob("*.json")):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    rels = data.get("relationships", []) if isinstance(data, dict) else data
                    if isinstance(rels, list):
                        loaded.extend(rels)
            except Exception:
                continue

    if loaded:
        return loaded
    return KNOWN_RELATIONSHIPS


class RelationalGraphExpander:
    """Graph traversal engine that ensures all retrieved tables form a connected join graph."""

    def __init__(self, relationships: List[Dict[str, Any]] = None):
        self.relationships = relationships or _load_relationships_from_files()
        self._graph = self._build_graph()

    def _build_graph(self) -> nx.Graph:
        """Constructs an undirected graph where nodes are tables and edges are join relationships."""
        G = nx.Graph()
        for rel in self.relationships:
            t1 = rel.get("from_table")
            t2 = rel.get("to_table")
            if t1 and t2:
                G.add_edge(t1, t2, rel=rel)
        return G

    def expand_tables(self, candidate_tables: List[str], max_tables: int = 6) -> List[str]:
        """
        Takes candidate tables from vector retrieval and includes any intermediate bridge tables
        needed to form valid JOIN paths between disconnected pairs.
        """
        if not candidate_tables:
            return []

        expanded = list(dict.fromkeys(candidate_tables))
        current_set = set(expanded)

        for i in range(len(candidate_tables)):
            for j in range(i + 1, len(candidate_tables)):
                src, dst = candidate_tables[i], candidate_tables[j]
                if src in self._graph and dst in self._graph:
                    try:
                        path = nx.shortest_path(self._graph, source=src, target=dst)
                        for node in path:
                            if node not in current_set and len(expanded) < max_tables:
                                expanded.append(node)
                                current_set.add(node)
                    except nx.NetworkXNoPath:
                        continue

        return expanded[:max_tables]

    def get_join_paths(self, tables: List[str]) -> List[str]:
        """Returns the specific JOIN conditions connecting the selected tables."""
        table_set = set(tables)
        join_paths = []
        seen = set()

        for rel in self.relationships:
            t1 = rel.get("from_table")
            t2 = rel.get("to_table")
            cond = rel.get("join_condition")
            if t1 in table_set and t2 in table_set and cond:
                if cond not in seen:
                    seen.add(cond)
                    join_paths.append(cond)

        return join_paths


# Singleton instance
graph_expander = RelationalGraphExpander()
