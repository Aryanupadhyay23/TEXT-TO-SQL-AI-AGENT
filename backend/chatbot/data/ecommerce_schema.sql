-- ==============================================================================
-- Full-Fledged Modern E-Commerce Relational Database Schema (MySQL 8.0+)
-- Production-Ready: Non-Destructive DDL, Triggers, Financial Procedures,
-- RESTRICT Delete Rules, Idempotent Seeds, and Validated Integrity
-- ==============================================================================

-- ==============================================================================
-- 1. USERS, ADDRESSES & PROFILES
-- ==============================================================================

CREATE TABLE IF NOT EXISTS users (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(191) NOT NULL UNIQUE COMMENT 'Unique login and communication email',
    password_hash VARCHAR(255) NOT NULL COMMENT 'Bcrypt encrypted password hash',
    first_name VARCHAR(100) NOT NULL COMMENT 'Customer or staff first name',
    last_name VARCHAR(100) NOT NULL COMMENT 'Customer or staff last name',
    phone VARCHAR(32) NULL COMMENT 'E.164 formatted contact number',
    role ENUM('customer', 'admin', 'vendor', 'support') NOT NULL DEFAULT 'customer' COMMENT 'System access role',
    status ENUM('active', 'suspended', 'pending_verification') NOT NULL DEFAULT 'active' COMMENT 'Account status',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_users_role_status (role, status),
    INDEX idx_users_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Master identity table for shoppers, sellers, and administrators';

CREATE TABLE IF NOT EXISTS user_addresses (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL COMMENT 'Foreign key to users table',
    address_type ENUM('shipping', 'billing', 'both') NOT NULL DEFAULT 'shipping' COMMENT 'Type of address',
    recipient_name VARCHAR(150) NOT NULL COMMENT 'Full name of recipient for parcel delivery',
    phone VARCHAR(32) NULL COMMENT 'Local contact phone number for courier',
    street_address VARCHAR(255) NOT NULL COMMENT 'Primary street address line',
    apartment_suite VARCHAR(100) NULL COMMENT 'Apartment, suite, unit, or floor number',
    city VARCHAR(100) NOT NULL COMMENT 'City, town, or municipality',
    state_province VARCHAR(100) NOT NULL COMMENT 'State, province, or administrative region',
    postal_code VARCHAR(20) NOT NULL COMMENT 'Postal or ZIP code',
    country VARCHAR(2) NOT NULL DEFAULT 'US' COMMENT 'ISO 3166-1 alpha-2 country code',
    is_default BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Whether this is user default address',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_address_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY uq_address_id_user (id, user_id),
    INDEX idx_address_user (user_id, is_default),
    INDEX idx_address_country_state (country, state_province)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Shipping and billing delivery addresses saved by users';

CREATE TABLE IF NOT EXISTS customer_profiles (
    user_id BIGINT UNSIGNED PRIMARY KEY COMMENT '1:1 reference to users table',
    loyalty_points INT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Available rewards points for redemption',
    membership_tier ENUM('standard', 'silver', 'gold', 'platinum') NOT NULL DEFAULT 'standard' COMMENT 'VIP status',
    lifetime_spend DECIMAL(12,2) NOT NULL DEFAULT 0.00 COMMENT 'Cumulative monetary spending in store currency',
    lifetime_orders_count INT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Total count of completed orders',
    birth_date DATE NULL COMMENT 'Customer birthday for promotional rewards',
    gender ENUM('male', 'female', 'non_binary', 'prefer_not_to_say') NULL,
    notes TEXT NULL COMMENT 'Internal customer service notes or preferences',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_profile_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT chk_profile_spend_nonneg CHECK (lifetime_spend >= 0.00),
    INDEX idx_profile_tier (membership_tier),
    INDEX idx_profile_spend (lifetime_spend)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Enriched marketing, loyalty tier, and lifetime analytics metrics';

-- ==============================================================================
-- 2. CATALOG: CATEGORIES, BRANDS & PRODUCTS
-- ==============================================================================

CREATE TABLE IF NOT EXISTS categories (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    parent_id INT UNSIGNED NULL COMMENT 'Self-reference for nested sub-categories',
    name VARCHAR(120) NOT NULL COMMENT 'Category title (e.g. Footwear, Smartphones)',
    slug VARCHAR(150) NOT NULL UNIQUE COMMENT 'URL-safe identifier',
    description TEXT NULL COMMENT 'Category overview and SEO copy',
    display_order SMALLINT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Sorting order on storefront nav',
    is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Visibility flag',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_cat_parent FOREIGN KEY (parent_id) REFERENCES categories(id) ON DELETE SET NULL,
    INDEX idx_cat_parent (parent_id, is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Hierarchical merchandise taxonomy tree';

CREATE TABLE IF NOT EXISTS brands (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL UNIQUE COMMENT 'Brand manufacturer or vendor name',
    slug VARCHAR(150) NOT NULL UNIQUE COMMENT 'URL-friendly slug',
    logo_url VARCHAR(500) NULL COMMENT 'Asset URL for brand badge',
    website_url VARCHAR(255) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Product brands and manufacturers';

CREATE TABLE IF NOT EXISTS products (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    brand_id INT UNSIGNED NULL COMMENT 'Associated manufacturer brand',
    category_id INT UNSIGNED NOT NULL COMMENT 'Primary catalog classification',
    name VARCHAR(255) NOT NULL COMMENT 'Product title',
    slug VARCHAR(280) NOT NULL UNIQUE COMMENT 'SEO slug',
    sku_prefix VARCHAR(32) NOT NULL UNIQUE COMMENT 'Unique vendor catalog code prefix',
    short_description VARCHAR(500) NULL COMMENT 'Elevator summary for search snippet cards',
    description LONGTEXT NULL COMMENT 'Rich HTML or Markdown product specification',
    base_price DECIMAL(10,2) NOT NULL COMMENT 'Standard retail reference price',
    cost_price DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT 'Wholesale unit acquisition cost for margin metrics',
    status ENUM('draft', 'active', 'archived') NOT NULL DEFAULT 'active' COMMENT 'Merchandise lifecycle state',
    is_featured BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Storefront spotlight showcase toggle',
    rating_average DECIMAL(3,2) NOT NULL DEFAULT 0.00 COMMENT 'Precomputed rolling average rating (1.00 - 5.00)',
    rating_count INT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Total verified review volume',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_prod_brand FOREIGN KEY (brand_id) REFERENCES brands(id) ON DELETE SET NULL,
    CONSTRAINT fk_prod_category FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT,
    CONSTRAINT chk_prod_base_price_nonneg CHECK (base_price >= 0.00),
    CONSTRAINT chk_prod_cost_price_nonneg CHECK (cost_price >= 0.00),
    CONSTRAINT chk_prod_rating_range CHECK (rating_average >= 0.00 AND rating_average <= 5.00),
    INDEX idx_prod_category (category_id, status),
    INDEX idx_prod_brand (brand_id),
    INDEX idx_prod_price (base_price),
    INDEX idx_prod_featured_rating (is_featured, rating_average)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Primary catalog merchandise entity';

CREATE TABLE IF NOT EXISTS product_variants (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    product_id BIGINT UNSIGNED NOT NULL COMMENT 'Parent product reference',
    sku VARCHAR(64) NOT NULL UNIQUE COMMENT 'Unique stock keeping unit barcode/identifier',
    title VARCHAR(150) NOT NULL COMMENT 'Variant descriptor (e.g. Midnight Blue / XL / 128GB)',
    option_color VARCHAR(60) NULL COMMENT 'Color attribute value',
    option_size VARCHAR(40) NULL COMMENT 'Size attribute value',
    option_material VARCHAR(60) NULL COMMENT 'Material attribute value',
    price DECIMAL(10,2) NOT NULL COMMENT 'Actual retail sell price for this exact variant',
    compare_at_price DECIMAL(10,2) NULL COMMENT 'Original MSRP or strike-through sale price',
    weight_grams INT UNSIGNED NULL COMMENT 'Product mass in grams for shipping cost calculation',
    barcode_upc VARCHAR(32) NULL COMMENT 'Standard UPC/EAN retail barcode',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_variant_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    CONSTRAINT chk_variant_price_nonneg CHECK (price >= 0.00),
    CONSTRAINT chk_variant_compare_price_nonneg CHECK (compare_at_price IS NULL OR compare_at_price >= 0.00),
    UNIQUE KEY uq_variant_id_product (id, product_id) COMMENT 'Composite key enabling strict cross-table validation',
    INDEX idx_variant_product (product_id, is_active),
    INDEX idx_variant_price (price)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Stock variants by color, size, and material combinations';

CREATE TABLE IF NOT EXISTS product_images (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    product_id BIGINT UNSIGNED NOT NULL,
    variant_id BIGINT UNSIGNED NULL,
    image_url VARCHAR(500) NOT NULL COMMENT 'High-resolution CDN URL',
    alt_text VARCHAR(255) NULL COMMENT 'Accessibility and search keyword text',
    display_order SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    is_thumbnail BOOLEAN NOT NULL DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_img_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    CONSTRAINT fk_img_variant_composite FOREIGN KEY (variant_id, product_id) REFERENCES product_variants(id, product_id) ON DELETE CASCADE,
    INDEX idx_img_product (product_id, display_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Gallery and gallery thumbnails for products and variants';

-- ==============================================================================
-- 3. INVENTORY & WAREHOUSES
-- ==============================================================================

CREATE TABLE IF NOT EXISTS warehouses (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(32) NOT NULL UNIQUE COMMENT 'Facility identifier (e.g. WH-EAST-01)',
    name VARCHAR(120) NOT NULL COMMENT 'Warehouse name',
    street_address VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state_province VARCHAR(100) NOT NULL,
    postal_code VARCHAR(20) NOT NULL,
    country VARCHAR(2) NOT NULL DEFAULT 'US',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Fulfillment distribution centers and storage depots';

CREATE TABLE IF NOT EXISTS inventory_items (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    warehouse_id INT UNSIGNED NOT NULL,
    variant_id BIGINT UNSIGNED NOT NULL,
    quantity_on_hand INT NOT NULL DEFAULT 0 COMMENT 'Physical count in storage bins',
    quantity_reserved INT NOT NULL DEFAULT 0 COMMENT 'Allocated to open orders awaiting pick/pack',
    safety_threshold INT NOT NULL DEFAULT 10 COMMENT 'Minimum count triggering replenishment alert',
    available_quantity INT GENERATED ALWAYS AS (quantity_on_hand - quantity_reserved) STORED COMMENT 'Effective stock sellable right now',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_inv_warehouse FOREIGN KEY (warehouse_id) REFERENCES warehouses(id) ON DELETE RESTRICT,
    CONSTRAINT fk_inv_variant FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE CASCADE,
    CONSTRAINT chk_inv_qty_on_hand CHECK (quantity_on_hand >= 0),
    CONSTRAINT chk_inv_qty_reserved CHECK (quantity_reserved >= 0),
    CONSTRAINT chk_inv_reserved_le_onhand CHECK (quantity_reserved <= quantity_on_hand),
    CONSTRAINT chk_inv_safety_nonneg CHECK (safety_threshold >= 0),
    UNIQUE KEY uq_warehouse_variant (warehouse_id, variant_id),
    INDEX idx_inv_avail_safety (available_quantity, safety_threshold)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Real-time stock ledger per warehouse and SKU';

CREATE TABLE IF NOT EXISTS stock_movements (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    inventory_item_id BIGINT UNSIGNED NOT NULL,
    movement_type ENUM('inbound_purchase', 'outbound_order', 'return_restock', 'cycle_adjustment', 'scrap_damaged') NOT NULL,
    quantity_changed INT NOT NULL COMMENT 'Signed change (+X received, -Y fulfilled)',
    reference_id VARCHAR(100) NULL COMMENT 'Order number, PO number, or RMA ticket reference',
    notes VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sm_item FOREIGN KEY (inventory_item_id) REFERENCES inventory_items(id) ON DELETE RESTRICT,
    CONSTRAINT chk_sm_qty_nonzero CHECK (quantity_changed <> 0),
    INDEX idx_sm_item (inventory_item_id, created_at),
    INDEX idx_sm_ref (reference_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Immutable audit trail of inventory adjustments';

-- ==============================================================================
-- 4. MARKETING, COUPONS & DISCOUNTS
-- ==============================================================================

CREATE TABLE IF NOT EXISTS coupons (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE COMMENT 'Discount promo code (e.g. WELCOME20, WINTER50)',
    discount_type ENUM('percentage', 'fixed_amount', 'free_shipping') NOT NULL,
    discount_value DECIMAL(10,2) NOT NULL COMMENT 'E.g. 20.00 for 20% or $20.00 off',
    minimum_order_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    max_discount_amount DECIMAL(10,2) NULL COMMENT 'Cap for percentage coupons (e.g. max $50 off)',
    usage_limit_total INT UNSIGNED NULL COMMENT 'Max redemptions overall (null = unlimited)',
    usage_limit_per_user INT UNSIGNED NOT NULL DEFAULT 1 COMMENT 'Max redemptions per customer',
    times_used INT UNSIGNED NOT NULL DEFAULT 0 COMMENT 'Maintained automatically in sync via database triggers',
    starts_at DATETIME NOT NULL,
    expires_at DATETIME NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_coupon_value_positive CHECK (discount_value > 0.00),
    CONSTRAINT chk_coupon_min_amount_nonneg CHECK (minimum_order_amount >= 0.00),
    CONSTRAINT chk_coupon_max_discount_nonneg CHECK (max_discount_amount IS NULL OR max_discount_amount > 0.00),
    INDEX idx_coupon_active (code, is_active, starts_at, expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Voucher and coupon promotion rules';

-- ==============================================================================
-- 5. SHOPPING CARTS & WISHLISTS
-- ==============================================================================

CREATE TABLE IF NOT EXISTS shopping_carts (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NULL COMMENT 'Registered customer id, null for guest session',
    session_token VARCHAR(128) NOT NULL UNIQUE COMMENT 'Browser anonymous cookie session UUID',
    status ENUM('active', 'converted', 'abandoned') NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_cart_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_cart_user (user_id),
    INDEX idx_cart_status_updated (status, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Pre-checkout persistent shopping carts';

CREATE TABLE IF NOT EXISTS cart_items (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    cart_id BIGINT UNSIGNED NOT NULL,
    variant_id BIGINT UNSIGNED NOT NULL,
    quantity INT UNSIGNED NOT NULL DEFAULT 1,
    unit_price DECIMAL(10,2) NOT NULL COMMENT 'Snapshot of variant unit price when item was added',
    added_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ci_cart FOREIGN KEY (cart_id) REFERENCES shopping_carts(id) ON DELETE CASCADE,
    CONSTRAINT fk_ci_variant FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE CASCADE,
    CONSTRAINT chk_ci_qty_positive CHECK (quantity > 0),
    CONSTRAINT chk_ci_price_nonneg CHECK (unit_price >= 0.00),
    UNIQUE KEY uq_cart_variant (cart_id, variant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Cart line items';

CREATE TABLE IF NOT EXISTS wishlists (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    title VARCHAR(120) NOT NULL DEFAULT 'My Wishlist' COMMENT 'Custom name (e.g. Holiday Tech, Saved for Later)',
    is_public BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Shareable wishlist toggle',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_wish_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_wish_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Customer wishlists parent containers';

CREATE TABLE IF NOT EXISTS wishlist_items (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    wishlist_id BIGINT UNSIGNED NOT NULL,
    product_id BIGINT UNSIGNED NOT NULL,
    variant_id BIGINT UNSIGNED NULL COMMENT 'Optional specific SKU variant',
    effective_variant_id BIGINT UNSIGNED GENERATED ALWAYS AS (COALESCE(variant_id, 0)) VIRTUAL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_wi_wishlist FOREIGN KEY (wishlist_id) REFERENCES wishlists(id) ON DELETE CASCADE,
    CONSTRAINT fk_wi_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    CONSTRAINT fk_wi_variant_composite FOREIGN KEY (variant_id, product_id) REFERENCES product_variants(id, product_id) ON DELETE CASCADE,
    UNIQUE KEY uq_wishlist_product_effective_variant (wishlist_id, product_id, effective_variant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Individual merchandise items saved within a wishlist';

-- ==============================================================================
-- 6. ORDERS, LINE ITEMS & TRACKING
-- ==============================================================================

CREATE TABLE IF NOT EXISTS orders (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    order_number VARCHAR(64) NOT NULL UNIQUE COMMENT 'Public reference (e.g. ORD-2025-00101)',
    user_id BIGINT UNSIGNED NOT NULL COMMENT 'Customer placing order',
    status ENUM('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded') NOT NULL DEFAULT 'pending',
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    subtotal_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT 'Sum of item prices before discount/tax/ship',
    discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT 'Total promotional discount applied',
    shipping_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT 'Delivery freight charged to buyer',
    tax_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT 'Sales tax / VAT collected',
    total_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT 'Final grand total charged',
    shipping_address_id BIGINT UNSIGNED NULL,
    billing_address_id BIGINT UNSIGNED NULL,
    shipping_method VARCHAR(60) NOT NULL DEFAULT 'Standard Ground' COMMENT 'Carrier tier selected',
    customer_notes TEXT NULL,
    placed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_ord_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT,
    -- [CRITICAL FIX A]: ON DELETE RESTRICT prevents illegal SET NULL on NOT NULL user_id, preserving address historical records
    CONSTRAINT fk_ord_ship_addr_user FOREIGN KEY (shipping_address_id, user_id) REFERENCES user_addresses(id, user_id) ON DELETE RESTRICT,
    CONSTRAINT fk_ord_bill_addr_user FOREIGN KEY (billing_address_id, user_id) REFERENCES user_addresses(id, user_id) ON DELETE RESTRICT,
    CONSTRAINT chk_ord_subtotal_nonneg CHECK (subtotal_amount >= 0.00),
    CONSTRAINT chk_ord_discount_nonneg CHECK (discount_amount >= 0.00),
    CONSTRAINT chk_ord_shipping_nonneg CHECK (shipping_amount >= 0.00),
    CONSTRAINT chk_ord_tax_nonneg CHECK (tax_amount >= 0.00),
    CONSTRAINT chk_ord_total_nonneg CHECK (total_amount >= 0.00),
    CONSTRAINT chk_ord_total_math CHECK (total_amount = (subtotal_amount - discount_amount + shipping_amount + tax_amount)),
    UNIQUE KEY uq_order_id_user (id, user_id),
    INDEX idx_ord_user (user_id, placed_at),
    INDEX idx_ord_status (status),
    INDEX idx_ord_placed_at (placed_at),
    INDEX idx_ord_total (total_amount)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Master commercial order records';

CREATE TABLE IF NOT EXISTS order_items (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    order_id BIGINT UNSIGNED NOT NULL,
    variant_id BIGINT UNSIGNED NULL COMMENT 'Null allowed if catalog variant was deleted later',
    product_id BIGINT UNSIGNED NOT NULL COMMENT 'Direct parent product reference for review verification',
    category_id INT UNSIGNED NOT NULL COMMENT 'Historical category snapshot at checkout',
    product_name VARCHAR(255) NOT NULL COMMENT 'Denormalized product name snapshot',
    variant_title VARCHAR(150) NOT NULL COMMENT 'Denormalized variant attributes snapshot',
    sku VARCHAR(64) NOT NULL COMMENT 'SKU code at order time',
    quantity INT UNSIGNED NOT NULL DEFAULT 1,
    unit_price DECIMAL(10,2) NOT NULL COMMENT 'Unit price charged',
    unit_cost DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT 'Unit cost at purchase for gross margin computation',
    discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    total_price DECIMAL(10,2) NOT NULL COMMENT '(unit_price * quantity) - discount_amount',
    CONSTRAINT fk_oi_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    CONSTRAINT fk_oi_variant FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE SET NULL,
    CONSTRAINT fk_oi_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT,
    CONSTRAINT fk_oi_category FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT,
    CONSTRAINT chk_oi_qty_positive CHECK (quantity > 0),
    CONSTRAINT chk_oi_unit_price_nonneg CHECK (unit_price >= 0.00),
    CONSTRAINT chk_oi_unit_cost_nonneg CHECK (unit_cost >= 0.00),
    CONSTRAINT chk_oi_discount_nonneg CHECK (discount_amount >= 0.00),
    CONSTRAINT chk_oi_total_price_nonneg CHECK (total_price >= 0.00),
    UNIQUE KEY uq_order_item_id_order (id, order_id),
    UNIQUE KEY uq_oi_id_order_product (id, order_id, product_id),
    INDEX idx_oi_order (order_id),
    INDEX idx_oi_variant (variant_id),
    INDEX idx_oi_product (product_id),
    INDEX idx_oi_category (category_id),
    INDEX idx_oi_sku (sku)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Individual line items contained within an order';

CREATE TABLE IF NOT EXISTS coupon_redemptions (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    coupon_id INT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    order_id BIGINT UNSIGNED NOT NULL,
    amount_discounted DECIMAL(10,2) NOT NULL,
    redeemed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_cr_coupon FOREIGN KEY (coupon_id) REFERENCES coupons(id) ON DELETE RESTRICT,
    CONSTRAINT fk_cr_order_user FOREIGN KEY (order_id, user_id) REFERENCES orders(id, user_id) ON DELETE CASCADE,
    CONSTRAINT chk_cr_discount_positive CHECK (amount_discounted > 0.00),
    UNIQUE KEY uq_coupon_order (coupon_id, order_id),
    INDEX idx_cr_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Redemption records tracking coupon utilization';

CREATE TABLE IF NOT EXISTS order_status_history (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    order_id BIGINT UNSIGNED NOT NULL,
    old_status ENUM('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded') NULL,
    new_status ENUM('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded') NOT NULL,
    changed_by_user_id BIGINT UNSIGNED NULL COMMENT 'Staff member or automated workflow agent',
    comment VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_osh_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    CONSTRAINT fk_osh_user FOREIGN KEY (changed_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_osh_order (order_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Status transition log for SLA and shipment tracking';

CREATE TABLE IF NOT EXISTS shipments (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    order_id BIGINT UNSIGNED NOT NULL,
    warehouse_id INT UNSIGNED NULL,
    carrier VARCHAR(60) NOT NULL COMMENT 'E.g. FedEx, UPS, DHL, USPS',
    tracking_number VARCHAR(120) NOT NULL UNIQUE,
    status ENUM('label_created', 'in_transit', 'out_for_delivery', 'delivered', 'failed', 'returned') NOT NULL DEFAULT 'label_created',
    estimated_delivery DATE NULL,
    actual_delivery DATETIME NULL,
    shipped_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ship_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    CONSTRAINT fk_ship_wh FOREIGN KEY (warehouse_id) REFERENCES warehouses(id) ON DELETE SET NULL,
    INDEX idx_ship_order (order_id),
    INDEX idx_ship_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Fulfillment dispatches and courier tracking numbers';

-- ==============================================================================
-- 7. PAYMENTS & REFUNDS
-- ==============================================================================

CREATE TABLE IF NOT EXISTS payments (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    order_id BIGINT UNSIGNED NOT NULL,
    payment_method ENUM('credit_card', 'paypal', 'stripe', 'apple_pay', 'google_pay', 'bank_transfer', 'cod') NOT NULL,
    transaction_reference VARCHAR(128) NOT NULL UNIQUE COMMENT 'Payment gateway charge token or transaction ID',
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    status ENUM('pending', 'authorized', 'captured', 'failed', 'refunded') NOT NULL DEFAULT 'pending',
    gateway_response JSON NULL COMMENT 'Raw metadata from payment gateway provider',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_pay_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    CONSTRAINT chk_pay_amount_positive CHECK (amount > 0.00),
    UNIQUE KEY uq_payment_id_order (id, order_id),
    INDEX idx_pay_order (order_id),
    INDEX idx_pay_status (status),
    INDEX idx_pay_method (payment_method)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Financial transactions charged for orders';

CREATE TABLE IF NOT EXISTS refunds (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    order_id BIGINT UNSIGNED NOT NULL,
    payment_id BIGINT UNSIGNED NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    reason VARCHAR(255) NOT NULL COMMENT 'Customer return, out of stock, or dispute compensation',
    status ENUM('requested', 'approved', 'processed', 'declined') NOT NULL DEFAULT 'requested',
    processed_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ref_order FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    CONSTRAINT fk_ref_payment_order FOREIGN KEY (payment_id, order_id) REFERENCES payments(id, order_id) ON DELETE RESTRICT,
    CONSTRAINT chk_ref_amount_positive CHECK (amount > 0.00),
    INDEX idx_ref_order (order_id),
    INDEX idx_ref_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Monetary refund settlements processed back to shoppers';

-- ==============================================================================
-- 8. REVIEWS, RATINGS & ENGAGEMENT
-- ==============================================================================

CREATE TABLE IF NOT EXISTS product_reviews (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    product_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    order_id BIGINT UNSIGNED NULL COMMENT 'Order verifying customer purchase',
    order_item_id BIGINT UNSIGNED NULL COMMENT 'Associated order line item verifying purchase',
    rating TINYINT UNSIGNED NOT NULL COMMENT 'Score between 1 and 5 stars',
    title VARCHAR(150) NOT NULL COMMENT 'Review headline',
    review_text TEXT NOT NULL COMMENT 'Customer feedback text',
    is_verified_purchase BOOLEAN NOT NULL DEFAULT FALSE,
    status ENUM('pending', 'approved', 'rejected') NOT NULL DEFAULT 'approved' COMMENT 'Moderation status',
    helpful_votes INT UNSIGNED NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_rev_product FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
    CONSTRAINT fk_rev_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    -- [CRITICAL FIX B]: ON DELETE RESTRICT prevents illegal SET NULL on NOT NULL user_id
    CONSTRAINT fk_rev_order_user FOREIGN KEY (order_id, user_id) REFERENCES orders(id, user_id) ON DELETE RESTRICT,
    -- [CRITICAL FIX C]: ON DELETE RESTRICT prevents illegal SET NULL on NOT NULL product_id
    CONSTRAINT fk_rev_order_item_product FOREIGN KEY (order_item_id, order_id, product_id) REFERENCES order_items(id, order_id, product_id) ON DELETE RESTRICT,
    CONSTRAINT chk_review_rating_1_to_5 CHECK (rating >= 1 AND rating <= 5),
    INDEX idx_rev_product_status (product_id, status, rating),
    INDEX idx_rev_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Shopper reviews, ratings, and customer sentiment';

CREATE TABLE IF NOT EXISTS review_helpful_votes (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    review_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    is_helpful BOOLEAN NOT NULL DEFAULT TRUE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_rhv_review FOREIGN KEY (review_id) REFERENCES product_reviews(id) ON DELETE CASCADE,
    CONSTRAINT fk_rhv_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY uq_review_user_vote (review_id, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Upvotes/downvotes on customer reviews';

-- ==============================================================================
-- 9. RETURNS & MERCHANDISE AUTHORIZATIONS (RMA)
-- ==============================================================================

CREATE TABLE IF NOT EXISTS return_requests (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    order_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NOT NULL,
    status ENUM('requested', 'authorized', 'received', 'inspected', 'completed', 'rejected') NOT NULL DEFAULT 'requested',
    return_reason VARCHAR(255) NOT NULL COMMENT 'E.g. Defective, Wrong Size, Did not match description',
    requested_action ENUM('refund', 'exchange', 'store_credit') NOT NULL DEFAULT 'refund',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_rma_order_user FOREIGN KEY (order_id, user_id) REFERENCES orders(id, user_id) ON DELETE CASCADE,
    UNIQUE KEY uq_rma_id_order (id, order_id),
    INDEX idx_rma_order (order_id),
    INDEX idx_rma_user (user_id),
    INDEX idx_rma_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Customer return and warranty claim cases';

CREATE TABLE IF NOT EXISTS return_items (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    return_request_id BIGINT UNSIGNED NOT NULL,
    order_id BIGINT UNSIGNED NOT NULL COMMENT 'Enforces matching order',
    order_item_id BIGINT UNSIGNED NOT NULL,
    quantity INT UNSIGNED NOT NULL DEFAULT 1,
    item_condition ENUM('unopened', 'like_new', 'damaged', 'defective') NOT NULL DEFAULT 'like_new',
    restock_approved BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT fk_ri_request_composite FOREIGN KEY (return_request_id, order_id) REFERENCES return_requests(id, order_id) ON DELETE CASCADE,
    CONSTRAINT fk_ri_item_composite FOREIGN KEY (order_item_id, order_id) REFERENCES order_items(id, order_id) ON DELETE RESTRICT,
    CONSTRAINT chk_ri_qty_positive CHECK (quantity > 0),
    INDEX idx_ri_request (return_request_id),
    INDEX idx_ri_order_item (order_item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Specific line items returned within an RMA request';

-- ==============================================================================
-- 10. DATABASE TRIGGERS & RECONCILIATION PROCEDURES
-- ==============================================================================

DELIMITER $$

-- [TRIGGER 1]: Auto-increment on new redemption
DROP TRIGGER IF EXISTS trg_coupon_redemptions_after_insert$$
CREATE TRIGGER trg_coupon_redemptions_after_insert
AFTER INSERT ON coupon_redemptions
FOR EACH ROW
BEGIN
    UPDATE coupons 
    SET times_used = times_used + 1 
    WHERE id = NEW.coupon_id;
END$$

-- [TRIGGER 2]: Auto-decrement on redemption deletion
DROP TRIGGER IF EXISTS trg_coupon_redemptions_after_delete$$
CREATE TRIGGER trg_coupon_redemptions_after_delete
AFTER DELETE ON coupon_redemptions
FOR EACH ROW
BEGIN
    UPDATE coupons 
    SET times_used = GREATEST(0, times_used - 1) 
    WHERE id = OLD.coupon_id;
END$$

-- [TRIGGER 3]: Handle coupon reassignment on updates without drift
DROP TRIGGER IF EXISTS trg_coupon_redemptions_after_update$$
CREATE TRIGGER trg_coupon_redemptions_after_update
AFTER UPDATE ON coupon_redemptions
FOR EACH ROW
BEGIN
    IF OLD.coupon_id <> NEW.coupon_id THEN
        UPDATE coupons SET times_used = GREATEST(0, times_used - 1) WHERE id = OLD.coupon_id;
        UPDATE coupons SET times_used = times_used + 1 WHERE id = NEW.coupon_id;
    END IF;
END$$

-- [PROCEDURE]: Comprehensive line-item and discount consistency verification
DROP PROCEDURE IF EXISTS sp_validate_order_totals$$
CREATE PROCEDURE sp_validate_order_totals(IN p_order_id BIGINT UNSIGNED)
BEGIN
    DECLARE v_items_subtotal DECIMAL(10,2);
    DECLARE v_items_discount DECIMAL(10,2);
    DECLARE v_items_total DECIMAL(10,2);
    DECLARE v_ord_subtotal DECIMAL(10,2);
    DECLARE v_ord_discount DECIMAL(10,2);
    DECLARE v_ord_shipping DECIMAL(10,2);
    DECLARE v_ord_tax DECIMAL(10,2);
    DECLARE v_ord_total DECIMAL(10,2);

    SELECT 
        COALESCE(SUM(unit_price * quantity), 0.00),
        COALESCE(SUM(discount_amount), 0.00),
        COALESCE(SUM(total_price), 0.00)
    INTO v_items_subtotal, v_items_discount, v_items_total
    FROM order_items
    WHERE order_id = p_order_id;

    SELECT subtotal_amount, discount_amount, shipping_amount, tax_amount, total_amount
    INTO v_ord_subtotal, v_ord_discount, v_ord_shipping, v_ord_tax, v_ord_total
    FROM orders
    WHERE id = p_order_id;

    -- 1. Validate subtotal
    IF v_items_subtotal <> v_ord_subtotal THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Order validation error: Subtotal amount does not match sum of line item gross prices';
    END IF;

    -- 2. Validate discount consistency
    IF v_items_discount <> v_ord_discount THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Order validation error: Order discount amount does not match sum of line item discounts';
    END IF;

    -- 3. Validate grand total
    IF (v_items_total + v_ord_shipping + v_ord_tax) <> v_ord_total THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Order validation error: Total amount does not match line items total plus shipping and tax';
    END IF;
END$$

DELIMITER ;

-- ==============================================================================
-- 11. IDEMPOTENT BENCHMARK SEED DATA (Repeatable Execution Safe)
-- ==============================================================================

-- 1. Users
INSERT INTO users (id, email, password_hash, first_name, last_name, phone, role, status, created_at) VALUES
(1, 'sarah.connor@example.com', '$2b$12$KIXl1u61K/3w6U1yD.Uq8O3zZ02P.Rz2JkY77O1G9E6y2B.Lq.0aG', 'Sarah', 'Connor', '+15551234001', 'customer', 'active', '2025-01-10 10:20:00'),
(2, 'alex.mercer@example.com', '$2b$12$KIXl1u61K/3w6U1yD.Uq8O3zZ02P.Rz2JkY77O1G9E6y2B.Lq.0aG', 'Alex', 'Mercer', '+15551234002', 'customer', 'active', '2025-01-15 14:15:00'),
(3, 'elena.rostova@example.com', '$2b$12$KIXl1u61K/3w6U1yD.Uq8O3zZ02P.Rz2JkY77O1G9E6y2B.Lq.0aG', 'Elena', 'Rostova', '+15551234003', 'customer', 'active', '2025-01-20 09:30:00'),
(4, 'marcus.vance@example.com', '$2b$12$KIXl1u61K/3w6U1yD.Uq8O3zZ02P.Rz2JkY77O1G9E6y2B.Lq.0aG', 'Marcus', 'Vance', '+15551234004', 'customer', 'active', '2025-02-01 16:45:00'),
(5, 'david.kim@example.com', '$2b$12$KIXl1u61K/3w6U1yD.Uq8O3zZ02P.Rz2JkY77O1G9E6y2B.Lq.0aG', 'David', 'Kim', '+15551234005', 'customer', 'active', '2025-02-05 11:10:00'),
(6, 'chloe.bennett@example.com', '$2b$12$KIXl1u61K/3w6U1yD.Uq8O3zZ02P.Rz2JkY77O1G9E6y2B.Lq.0aG', 'Chloe', 'Bennett', '+15551234006', 'customer', 'active', '2025-02-12 13:20:00'),
(7, 'admin@ecom-store.com', '$2b$12$KIXl1u61K/3w6U1yD.Uq8O3zZ02P.Rz2JkY77O1G9E6y2B.Lq.0aG', 'System', 'Admin', '+15551234099', 'admin', 'active', '2024-12-01 08:00:00')
ON DUPLICATE KEY UPDATE 
    email=VALUES(email),
    password_hash=VALUES(password_hash),
    first_name=VALUES(first_name),
    last_name=VALUES(last_name),
    phone=VALUES(phone),
    role=VALUES(role),
    status=VALUES(status);

-- 2. Customer Profiles
INSERT INTO customer_profiles (user_id, loyalty_points, membership_tier, lifetime_spend, lifetime_orders_count, birth_date, gender) VALUES
(1, 1450, 'gold', 3240.50, 8, '1990-05-12', 'female'),
(2, 620, 'silver', 1199.00, 3, '1988-11-23', 'male'),
(3, 2800, 'platinum', 6890.00, 15, '1995-07-08', 'female'),
(4, 150, 'standard', 289.00, 1, '2001-03-30', 'male'),
(5, 450, 'standard', 539.98, 2, '1992-09-14', 'male'),
(6, 920, 'silver', 1450.00, 4, '1997-12-03', 'female')
ON DUPLICATE KEY UPDATE 
    loyalty_points=VALUES(loyalty_points),
    membership_tier=VALUES(membership_tier),
    lifetime_spend=VALUES(lifetime_spend),
    lifetime_orders_count=VALUES(lifetime_orders_count);

-- 3. Addresses
INSERT INTO user_addresses (id, user_id, address_type, recipient_name, phone, street_address, apartment_suite, city, state_province, postal_code, country, is_default) VALUES
(1, 1, 'both', 'Sarah Connor', '+15551234001', '742 Evergreen Terrace', 'Apt 4B', 'Springfield', 'OR', '97477', 'US', 1),
(2, 2, 'both', 'Alex Mercer', '+15551234002', '120 Broadway St', 'Suite 1800', 'New York', 'NY', '10005', 'US', 1),
(3, 3, 'both', 'Elena Rostova', '+15551234003', '850 Market Street', NULL, 'San Francisco', 'CA', '94102', 'US', 1),
(4, 4, 'both', 'Marcus Vance', '+15551234004', '450 North Michigan Ave', '#12', 'Chicago', 'IL', '60611', 'US', 1),
(5, 5, 'both', 'David Kim', '+15551234005', '2101 4th Ave', 'Ste 500', 'Seattle', 'WA', '98121', 'US', 1),
(6, 6, 'both', 'Chloe Bennett', '+15551234006', '500 Boylston St', NULL, 'Boston', 'MA', '02116', 'US', 1)
ON DUPLICATE KEY UPDATE 
    recipient_name=VALUES(recipient_name),
    street_address=VALUES(street_address),
    city=VALUES(city),
    state_province=VALUES(state_province),
    postal_code=VALUES(postal_code);

-- 4. Brands
INSERT INTO brands (id, name, slug, logo_url, website_url, is_active) VALUES
(1, 'Apex Acoustics', 'apex-acoustics', 'https://assets.store.com/brands/apex.png', 'https://apexacoustics.example.com', 1),
(2, 'VoltWear', 'volt-wear', 'https://assets.store.com/brands/volt.png', 'https://voltwear.example.com', 1),
(3, 'NexusTech', 'nexus-tech', 'https://assets.store.com/brands/nexus.png', 'https://nexustech.example.com', 1),
(4, 'TerraOutdoor', 'terra-outdoor', 'https://assets.store.com/brands/terra.png', 'https://terraoutdoor.example.com', 1)
ON DUPLICATE KEY UPDATE name=VALUES(name), slug=VALUES(slug), is_active=VALUES(is_active);

-- 5. Categories
INSERT INTO categories (id, parent_id, name, slug, description, display_order, is_active) VALUES
(1, NULL, 'Electronics', 'electronics', 'Smart audio, computing, and smart gadgets', 1, 1),
(2, 1, 'Headphones & Audio', 'headphones-audio', 'Noise cancelling headphones and earbuds', 1, 1),
(3, 1, 'Wearables & Smartwatches', 'wearables', 'Fitness trackers and smart watches', 2, 1),
(4, NULL, 'Apparel & Fashion', 'apparel', 'Performance clothing and everyday wear', 2, 1),
(5, 4, 'Jackets & Outerwear', 'outerwear', 'Weather-resistant and thermal jackets', 1, 1),
(6, NULL, 'Home & Living', 'home-living', 'Smart home automation and appliances', 3, 1)
ON DUPLICATE KEY UPDATE name=VALUES(name), slug=VALUES(slug), is_active=VALUES(is_active);

-- 6. Products
INSERT INTO products (id, brand_id, category_id, name, slug, sku_prefix, short_description, description, base_price, cost_price, status, is_featured, rating_average, rating_count) VALUES
(1, 1, 2, 'Apex Pro Wireless ANC Headphones', 'apex-pro-wireless-anc-headphones', 'APX-ANC', 'Flagship 40-hour battery active noise cancelling over-ear headphones.', 'Experience studio-grade clarity with custom 45mm neodymium drivers, active hybrid noise cancellation, and ultra-plush memory foam earcups.', 349.99, 140.00, 'active', 1, 4.80, 128),
(2, 3, 3, 'Nexus UltraFit Smartwatch 2', 'nexus-ultrafit-smartwatch-2', 'NEX-WTCH', 'Rugged GPS smartwatch with ECG, sleep tracking, and titanium bezel.', 'Advanced health tracking smartwatch featuring sapphire glass, 100m water resistance, continuous SpO2 monitoring, and 14-day battery life.', 279.99, 110.00, 'active', 1, 4.65, 94),
(3, 2, 5, 'VoltWear StormShield All-Weather Parka', 'voltwear-stormshield-parka', 'VLT-PRK', 'Waterproof breathable winter parka with recycled down insulation.', 'Engineered with 3-layer Gore-Tex fabric, thermal taped seams, magnetic storm flap, and temperature rating down to -25C.', 399.00, 165.00, 'active', 1, 4.90, 42),
(4, 4, 5, 'TerraVent Light Windbreaker', 'terravent-light-windbreaker', 'TRA-WND', 'Ultralight packable trail running and hiking windbreaker.', 'Weighs only 140g, packs down into its own chest pocket, with DWR water-resistant finish and reflective safety accents.', 119.50, 45.00, 'active', 0, 4.40, 31)
ON DUPLICATE KEY UPDATE 
    name=VALUES(name),
    base_price=VALUES(base_price),
    cost_price=VALUES(cost_price),
    status=VALUES(status),
    rating_average=VALUES(rating_average),
    rating_count=VALUES(rating_count);

-- 7. Product Variants
INSERT INTO product_variants (id, product_id, sku, title, option_color, option_size, option_material, price, compare_at_price, weight_grams, barcode_upc, is_active) VALUES
(1, 1, 'APX-ANC-BLK', 'Matte Black', 'Matte Black', 'One Size', 'Aluminum & Leather', 349.99, 399.99, 290, '850012340011', 1),
(2, 1, 'APX-ANC-SLV', 'Silver Chrome', 'Silver Chrome', 'One Size', 'Aluminum & Leather', 349.99, 399.99, 290, '850012340028', 1),
(3, 2, 'NEX-WTCH-44-TI', 'Titanium Gray / 44mm', 'Titanium Gray', '44mm', 'Grade 5 Titanium', 279.99, NULL, 58, '850012340035', 1),
(4, 2, 'NEX-WTCH-40-GLD', 'Rose Gold / 40mm', 'Rose Gold', '40mm', 'Aluminum', 249.99, 299.99, 48, '850012340042', 1),
(5, 3, 'VLT-PRK-BLK-M', 'Black / Medium', 'Black', 'M', 'Recycled Down & Gore-Tex', 399.00, 450.00, 1150, '850012340059', 1),
(6, 3, 'VLT-PRK-BLK-L', 'Black / Large', 'Black', 'L', 'Recycled Down & Gore-Tex', 399.00, 450.00, 1220, '850012340066', 1),
(7, 3, 'VLT-PRK-OLV-L', 'Olive Green / Large', 'Olive Green', 'L', 'Recycled Down & Gore-Tex', 399.00, 450.00, 1220, '850012340073', 1),
(8, 4, 'TRA-WND-BLU-M', 'Cobalt Blue / Medium', 'Cobalt Blue', 'M', 'Ripstop Nylon', 119.50, NULL, 140, '850012340080', 1)
ON DUPLICATE KEY UPDATE 
    title=VALUES(title),
    price=VALUES(price),
    compare_at_price=VALUES(compare_at_price),
    is_active=VALUES(is_active);

-- 8. Product Images
INSERT INTO product_images (id, product_id, variant_id, image_url, alt_text, display_order, is_thumbnail) VALUES
(1, 1, 1, 'https://assets.store.com/prod/apex-black-front.jpg', 'Apex Wireless Black Front View', 1, 1),
(2, 1, 2, 'https://assets.store.com/prod/apex-silver-front.jpg', 'Apex Wireless Silver Front View', 2, 0),
(3, 2, 3, 'https://assets.store.com/prod/nexus-ti-dial.jpg', 'Nexus Smartwatch Titanium Display', 1, 1),
(4, 3, 5, 'https://assets.store.com/prod/voltwear-parka-m.jpg', 'VoltWear Winter Parka Front', 1, 1)
ON DUPLICATE KEY UPDATE 
    image_url=VALUES(image_url),
    alt_text=VALUES(alt_text);

-- 9. Warehouses
INSERT INTO warehouses (id, code, name, street_address, city, state_province, postal_code, country, is_active) VALUES
(1, 'WH-US-WEST', 'Pacific Northwest Hub', '1400 Airport Way S', 'Seattle', 'WA', '98134', 'US', 1),
(2, 'WH-US-EAST', 'East Coast Distribution Center', '200 Logistics Blvd', 'Allentown', 'PA', '18109', 'US', 1),
(3, 'WH-US-CENTRAL', 'Midwest Regional Depot', '500 Interchange Parkway', 'Dallas', 'TX', '75261', 'US', 1)
ON DUPLICATE KEY UPDATE name=VALUES(name), city=VALUES(city), is_active=VALUES(is_active);

-- 10. Inventory Items
INSERT INTO inventory_items (id, warehouse_id, variant_id, quantity_on_hand, quantity_reserved, safety_threshold) VALUES
(1, 1, 1, 85, 5, 15),
(2, 2, 1, 60, 2, 15),
(3, 1, 2, 45, 0, 10),
(4, 2, 3, 110, 8, 20),
(5, 3, 3, 90, 4, 20),
(6, 1, 4, 35, 1, 10),
(7, 1, 5, 25, 3, 5),
(8, 2, 6, 40, 2, 10),
(9, 3, 7, 18, 0, 5),
(10, 1, 8, 150, 12, 25)
ON DUPLICATE KEY UPDATE 
    quantity_on_hand=VALUES(quantity_on_hand),
    quantity_reserved=VALUES(quantity_reserved),
    safety_threshold=VALUES(safety_threshold);

-- 11. Coupons
INSERT INTO coupons (id, code, discount_type, discount_value, minimum_order_amount, max_discount_amount, usage_limit_total, usage_limit_per_user, times_used, starts_at, expires_at, is_active) VALUES
(1, 'WELCOME20', 'percentage', 20.00, 100.00, 50.00, 1000, 1, 0, '2025-01-01 00:00:00', '2026-12-31 23:59:59', 1),
(2, 'WINTERSALE50', 'fixed_amount', 50.00, 300.00, NULL, 500, 1, 0, '2025-01-01 00:00:00', '2025-03-31 23:59:59', 1),
(3, 'FREESHIP', 'free_shipping', 15.00, 75.00, 15.00, NULL, 5, 0, '2025-01-01 00:00:00', NULL, 1)
ON DUPLICATE KEY UPDATE 
    discount_value=VALUES(discount_value),
    minimum_order_amount=VALUES(minimum_order_amount),
    max_discount_amount=VALUES(max_discount_amount),
    is_active=VALUES(is_active);

-- 12. Orders
INSERT INTO orders (id, order_number, user_id, status, currency, subtotal_amount, discount_amount, shipping_amount, tax_amount, total_amount, shipping_address_id, billing_address_id, shipping_method, customer_notes, placed_at) VALUES
(101, 'ORD-2025-00101', 1, 'delivered', 'USD', 699.98, 50.00, 0.00, 52.00, 701.98, 1, 1, 'FedEx 2-Day', 'Please leave at front door behind plant.', '2025-02-10 11:30:00'),
(102, 'ORD-2025-00102', 2, 'delivered', 'USD', 279.99, 50.00, 12.00, 19.99, 261.98, 2, 2, 'UPS Ground', NULL, '2025-02-14 15:40:00'),
(103, 'ORD-2025-00103', 3, 'shipped', 'USD', 748.99, 50.00, 0.00, 59.92, 758.91, 3, 3, 'FedEx Overnight', 'Express gate code #4490', '2025-03-01 09:12:00'),
(104, 'ORD-2025-00104', 4, 'processing', 'USD', 119.50, 0.00, 9.99, 9.56, 139.05, 4, 4, 'Standard Ground', NULL, '2025-03-04 18:22:00'),
(105, 'ORD-2025-00105', 5, 'delivered', 'USD', 529.98, 50.00, 0.00, 38.40, 518.38, 5, 5, 'FedEx Ground', NULL, '2025-02-18 10:15:00')
ON DUPLICATE KEY UPDATE 
    subtotal_amount=VALUES(subtotal_amount),
    discount_amount=VALUES(discount_amount),
    shipping_amount=VALUES(shipping_amount),
    tax_amount=VALUES(tax_amount),
    total_amount=VALUES(total_amount),
    status=VALUES(status);

-- 13. Order Items
INSERT INTO order_items (id, order_id, variant_id, product_id, category_id, product_name, variant_title, sku, quantity, unit_price, unit_cost, discount_amount, total_price) VALUES
(1, 101, 1, 1, 2, 'Apex Pro Wireless ANC Headphones', 'Matte Black', 'APX-ANC-BLK', 1, 349.99, 140.00, 25.00, 324.99),
(2, 101, 2, 1, 2, 'Apex Pro Wireless ANC Headphones', 'Silver Chrome', 'APX-ANC-SLV', 1, 349.99, 140.00, 25.00, 324.99),
(3, 102, 3, 2, 3, 'Nexus UltraFit Smartwatch 2', 'Titanium Gray / 44mm', 'NEX-WTCH-44-TI', 1, 279.99, 110.00, 50.00, 229.99),
(4, 103, 1, 1, 2, 'Apex Pro Wireless ANC Headphones', 'Matte Black', 'APX-ANC-BLK', 1, 349.99, 140.00, 20.00, 329.99),
(5, 103, 5, 3, 5, 'VoltWear StormShield All-Weather Parka', 'Black / Medium', 'VLT-PRK-BLK-M', 1, 399.00, 165.00, 30.00, 369.00),
(6, 104, 8, 4, 5, 'TerraVent Light Windbreaker', 'Cobalt Blue / Medium', 'TRA-WND-BLU-M', 1, 119.50, 45.00, 0.00, 119.50),
(7, 105, 3, 2, 3, 'Nexus UltraFit Smartwatch 2', 'Titanium Gray / 44mm', 'NEX-WTCH-44-TI', 1, 279.99, 110.00, 25.00, 254.99),
(8, 105, 4, 2, 3, 'Nexus UltraFit Smartwatch 2', 'Rose Gold / 40mm', 'NEX-WTCH-40-GLD', 1, 249.99, 100.00, 25.00, 224.99)
ON DUPLICATE KEY UPDATE 
    quantity=VALUES(quantity),
    unit_price=VALUES(unit_price),
    discount_amount=VALUES(discount_amount),
    total_price=VALUES(total_price);

-- 14. Coupon Redemptions
INSERT INTO coupon_redemptions (id, coupon_id, user_id, order_id, amount_discounted, redeemed_at) VALUES
(1, 2, 1, 101, 50.00, '2025-02-10 11:30:00'),
(2, 1, 2, 102, 50.00, '2025-02-14 15:40:00'),
(3, 2, 3, 103, 50.00, '2025-03-01 09:12:00'),
(4, 2, 5, 105, 50.00, '2025-02-18 10:15:00')
ON DUPLICATE KEY UPDATE 
    coupon_id=VALUES(coupon_id),
    amount_discounted=VALUES(amount_discounted);

-- 15. Reconcile Coupon Usage Counter
UPDATE coupons c
SET c.times_used = (
    SELECT COUNT(*) 
    FROM coupon_redemptions cr 
    WHERE cr.coupon_id = c.id
);

-- 16. Payments
INSERT INTO payments (id, order_id, payment_method, transaction_reference, amount, currency, status, created_at) VALUES
(1, 101, 'credit_card', 'ch_3M4kxL9102830001', 500.00, 'USD', 'captured', '2025-02-10 11:31:12'),
(2, 101, 'paypal', 'PAYID-MTK48291001B', 201.98, 'USD', 'captured', '2025-02-10 11:32:00'),
(3, 102, 'apple_pay', 'ch_3M4kxL9102830002', 261.98, 'USD', 'captured', '2025-02-14 15:41:05'),
(4, 103, 'stripe', 'ch_3M4kxL9102830003', 758.91, 'USD', 'captured', '2025-03-01 09:13:00'),
(5, 104, 'paypal', 'PAYID-MTK48291004', 139.05, 'USD', 'captured', '2025-03-04 18:23:45'),
(6, 105, 'credit_card', 'ch_3M4kxL9102830005', 518.38, 'USD', 'captured', '2025-02-18 10:16:00')
ON DUPLICATE KEY UPDATE amount=VALUES(amount), status=VALUES(status);

-- 17. Refunds
INSERT INTO refunds (id, order_id, payment_id, amount, reason, status, processed_at, created_at) VALUES
(1, 101, 1, 50.00, 'Customer goodwill courtesy adjustment', 'processed', '2025-02-14 10:00:00', '2025-02-14 09:30:00')
ON DUPLICATE KEY UPDATE amount=VALUES(amount), status=VALUES(status);

-- 18. Shipments
INSERT INTO shipments (id, order_id, warehouse_id, carrier, tracking_number, status, estimated_delivery, actual_delivery, shipped_at) VALUES
(1, 101, 1, 'FedEx', 'FDX-994827104928', 'delivered', '2025-02-12', '2025-02-12 14:10:00', '2025-02-10 16:00:00'),
(2, 102, 2, 'UPS', '1Z9999999999999999', 'delivered', '2025-02-17', '2025-02-17 11:25:00', '2025-02-15 09:00:00'),
(3, 103, 1, 'FedEx', 'FDX-883719402847', 'in_transit', '2025-03-03', NULL, '2025-03-01 17:30:00'),
(4, 105, 1, 'FedEx', 'FDX-774928190281', 'delivered', '2025-02-21', '2025-02-21 15:30:00', '2025-02-18 16:45:00')
ON DUPLICATE KEY UPDATE status=VALUES(status);

-- 19. Reviews
INSERT INTO product_reviews (id, product_id, user_id, order_id, order_item_id, rating, title, review_text, is_verified_purchase, status, helpful_votes, created_at) VALUES
(1, 1, 1, 101, 1, 5, 'Phenomenal audio fidelity and battery life', 'Noise cancellation easily rivals Sony and Bose. Traveled 14 hours international flight on a single charge and ears did not fatigue.', 1, 'approved', 24, '2025-02-15 19:20:00'),
(2, 2, 2, 102, 3, 5, 'Best smartwatch for outdoor workouts', 'GPS locks in under 3 seconds and the battery lasts a solid 10 days with always-on display off.', 1, 'approved', 18, '2025-02-20 10:14:00'),
(3, 3, 3, 103, 5, 5, 'Bulletproof winter parka', 'Survived severe blizzard in Tahoe with zero wind penetration. Warmest jacket I have ever owned.', 1, 'approved', 12, '2025-03-05 12:00:00')
ON DUPLICATE KEY UPDATE rating=VALUES(rating), status=VALUES(status);

-- 20. Shopping Carts
INSERT INTO shopping_carts (id, user_id, session_token, status, created_at) VALUES
(1, 1, 'sess_c7f8a9e0-2025-4b11-92fa-018291029381', 'active', '2025-03-05 08:10:00'),
(2, NULL, 'sess_guest_9938210-9128-44fa-ba01-883719204918', 'active', '2025-03-05 10:45:00')
ON DUPLICATE KEY UPDATE status=VALUES(status);

INSERT INTO cart_items (id, cart_id, variant_id, quantity, unit_price) VALUES
(1, 1, 4, 1, 249.99),
(2, 2, 1, 1, 349.99)
ON DUPLICATE KEY UPDATE quantity=VALUES(quantity), unit_price=VALUES(unit_price);

-- 21. Wishlists
INSERT INTO wishlists (id, user_id, title, is_public) VALUES
(1, 1, 'Holiday Tech Wishlist', 0),
(2, 2, 'Outdoor Gear 2026', 1)
ON DUPLICATE KEY UPDATE title=VALUES(title);

INSERT INTO wishlist_items (id, wishlist_id, product_id, variant_id) VALUES
(1, 1, 3, 5),
(2, 1, 2, 3),
(3, 2, 4, 8),
(4, 2, 1, NULL)
ON DUPLICATE KEY UPDATE product_id=VALUES(product_id), variant_id=VALUES(variant_id);

-- 22. Returns & RMA
INSERT INTO return_requests (id, order_id, user_id, status, return_reason, requested_action, created_at) VALUES
(1, 101, 1, 'authorized', 'Ear cushion leather stitching was loose', 'refund', '2025-02-13 14:00:00')
ON DUPLICATE KEY UPDATE status=VALUES(status);

INSERT INTO return_items (id, return_request_id, order_id, order_item_id, quantity, item_condition, restock_approved) VALUES
(1, 1, 101, 2, 1, 'like_new', 1)
ON DUPLICATE KEY UPDATE quantity=VALUES(quantity);

-- ==============================================================================
-- 12. VALIDATION EXECUTION
-- ==============================================================================

-- Explicitly validate every seeded order against line-item totals and discounts
CALL sp_validate_order_totals(101);
CALL sp_validate_order_totals(102);
CALL sp_validate_order_totals(103);
CALL sp_validate_order_totals(104);
CALL sp_validate_order_totals(105);
