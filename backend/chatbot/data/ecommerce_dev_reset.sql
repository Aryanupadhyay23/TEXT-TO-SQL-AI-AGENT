-- ==============================================================================
-- DEVELOPMENT-ONLY HARD RESET SCRIPT
-- [WARNING]: ONLY RUN THIS SCRIPT IN A LOCAL OR STAGING DEVELOPMENT ENVIRONMENT.
-- 
-- Scope of Removal:
-- 1. Drops the 27 specific e-commerce tables in reverse dependency order.
-- 2. Drops the schema-specific procedure: `sp_validate_order_totals`.
-- 3. Drops the schema-specific triggers: `trg_coupon_redemptions_after_insert`,
--    `trg_coupon_redemptions_after_delete`, `trg_coupon_redemptions_after_update`.
-- NOTE: If you introduce additional custom routines, views, or triggers later,
--       they must be explicitly added to this reset script.
--
-- Session Safety & FOREIGN_KEY_CHECKS Warning:
-- - `SET FOREIGN_KEY_CHECKS = 0;` modifies only the current database session.
-- - If an unexpected error halts execution before reaching `SET FOREIGN_KEY_CHECKS = 1;`,
--   foreign-key checks will remain disabled for this active connection.
-- - BEST PRACTICE: Always run this reset via a dedicated, single-use CLI session
--   (e.g., `mysql ... < ecommerce_dev_reset.sql`) which automatically closes upon exit.
-- - If running inside an interactive IDE or pooled connection, verify afterward:
--   `SELECT @@SESSION.foreign_key_checks;` (should return 1).
-- ==============================================================================

-- 1. Temporarily disable FK checks for current session to permit reverse-order drops
SET FOREIGN_KEY_CHECKS = 0;

-- 2. Drop Explicitly Managed Stored Procedures
DROP PROCEDURE IF EXISTS sp_validate_order_totals;

-- 3. Drop Explicitly Managed Triggers
DROP TRIGGER IF EXISTS trg_coupon_redemptions_after_insert;
DROP TRIGGER IF EXISTS trg_coupon_redemptions_after_delete;
DROP TRIGGER IF EXISTS trg_coupon_redemptions_after_update;

-- 4. Drop the 27 E-Commerce Tables in Reverse Dependency Order
DROP TABLE IF EXISTS review_helpful_votes;
DROP TABLE IF EXISTS product_reviews;
DROP TABLE IF EXISTS return_items;
DROP TABLE IF EXISTS return_requests;
DROP TABLE IF EXISTS refunds;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS shipments;
DROP TABLE IF EXISTS order_status_history;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS coupon_redemptions;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS cart_items;
DROP TABLE IF EXISTS shopping_carts;
DROP TABLE IF EXISTS wishlist_items;
DROP TABLE IF EXISTS wishlists;
DROP TABLE IF EXISTS stock_movements;
DROP TABLE IF EXISTS inventory_items;
DROP TABLE IF EXISTS warehouses;
DROP TABLE IF EXISTS product_images;
DROP TABLE IF EXISTS product_variants;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS brands;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS coupons;
DROP TABLE IF EXISTS customer_profiles;
DROP TABLE IF EXISTS user_addresses;
DROP TABLE IF EXISTS users;

-- 5. Restore Foreign Key Checks for this session
SET FOREIGN_KEY_CHECKS = 1;

-- ==============================================================================
-- Recommended Two-Step Deployment Workflow:
-- 1. Reset development database:
--    mysql -h <HOST> -u <USER> -p <DB_NAME> < backend/chatbot/data/ecommerce_dev_reset.sql
-- 2. Build tables, constraints, triggers, procedures, and seed data:
--    mysql -h <HOST> -u <USER> -p <DB_NAME> < backend/chatbot/data/ecommerce_schema.sql
-- ==============================================================================
