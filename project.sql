-- Inventory & Sales Management System
-- Safe to run more than once: it never drops tables or deletes data.

CREATE DATABASE IF NOT EXISTS inventory_sales_management;
USE inventory_sales_management;

CREATE TABLE IF NOT EXISTS categories (
    category_id INT NOT NULL AUTO_INCREMENT,
    category_name VARCHAR(100) NOT NULL,
    PRIMARY KEY (category_id),
    UNIQUE KEY category_name (category_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS products (
    product_id INT NOT NULL AUTO_INCREMENT,
    category_id INT DEFAULT NULL,
    product_name VARCHAR(150) NOT NULL,
    sku VARCHAR(50) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    stock_quantity INT NOT NULL DEFAULT 0,
    reorder_level INT NOT NULL DEFAULT 5,
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (product_id),
    UNIQUE KEY sku (sku),
    KEY category_id (category_id),
    CONSTRAINT products_ibfk_1 FOREIGN KEY (category_id) REFERENCES categories (category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sales (
    sale_id INT NOT NULL AUTO_INCREMENT,
    sale_date TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    total_amount DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    PRIMARY KEY (sale_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS sale_items (
    sale_item_id INT NOT NULL AUTO_INCREMENT,
    sale_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (sale_item_id),
    KEY sale_id (sale_id),
    KEY product_id (product_id),
    CONSTRAINT sale_items_ibfk_1 FOREIGN KEY (sale_id) REFERENCES sales (sale_id),
    CONSTRAINT sale_items_ibfk_2 FOREIGN KEY (product_id) REFERENCES products (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS orders (
    order_id INT NOT NULL AUTO_INCREMENT,
    customer_name VARCHAR(150) NOT NULL,
    customer_email VARCHAR(255) NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    order_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    stock_deducted TINYINT(1) NOT NULL DEFAULT 0,
    customer_phone VARCHAR(15) DEFAULT NULL,
    PRIMARY KEY (order_id),
    CONSTRAINT orders_chk_1 CHECK (total_amount >= 0),
    CONSTRAINT orders_chk_2 CHECK (order_status IN ('PENDING','PAID','CANCELLED','FAILED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id INT NOT NULL AUTO_INCREMENT,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (order_item_id),
    KEY order_id (order_id),
    KEY product_id (product_id),
    CONSTRAINT order_items_ibfk_1 FOREIGN KEY (order_id) REFERENCES orders (order_id),
    CONSTRAINT order_items_ibfk_2 FOREIGN KEY (product_id) REFERENCES products (product_id),
    CONSTRAINT order_items_chk_1 CHECK (quantity > 0),
    CONSTRAINT order_items_chk_2 CHECK (unit_price >= 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS payments (
    payment_id INT NOT NULL AUTO_INCREMENT,
    order_id INT NOT NULL,
    provider VARCHAR(30) NOT NULL DEFAULT 'RAZORPAY',
    provider_order_id VARCHAR(100) DEFAULT NULL,
    provider_payment_id VARCHAR(100) DEFAULT NULL,
    payment_status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (payment_id),
    UNIQUE KEY uq_provider_payment (provider, provider_payment_id),
    KEY order_id (order_id),
    CONSTRAINT payments_ibfk_1 FOREIGN KEY (order_id) REFERENCES orders (order_id),
    CONSTRAINT payments_chk_1 CHECK (payment_status IN ('PENDING','SUCCESS','FAILED'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS stock_movements (
    movement_id INT NOT NULL AUTO_INCREMENT,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    movement_type VARCHAR(20) NOT NULL,
    movement_date TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP,
    notes VARCHAR(255) DEFAULT NULL,
    PRIMARY KEY (movement_id),
    KEY product_id (product_id),
    CONSTRAINT stock_movements_ibfk_1 FOREIGN KEY (product_id) REFERENCES products (product_id),
    CONSTRAINT stock_movements_chk_1 CHECK (quantity > 0),
    CONSTRAINT stock_movements_chk_2 CHECK (movement_type = 'RESTOCK')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Sample data (INSERT IGNORE skips rows that already exist)

INSERT IGNORE INTO categories (category_name)
VALUES ('Electronics'), ('Stationery'), ('Accessories');

INSERT IGNORE INTO products (category_id, product_name, sku, price, stock_quantity, reorder_level)
SELECT category_id, 'FAN', 'ELEC-003', 1299.00, 10, 5 FROM categories WHERE category_name = 'Electronics';

INSERT IGNORE INTO products (category_id, product_name, sku, price, stock_quantity, reorder_level)
SELECT category_id, 'Monitor', 'ELEC-002', 8999.00, 15, 5 FROM categories WHERE category_name = 'Electronics';

INSERT IGNORE INTO products (category_id, product_name, sku, price, stock_quantity, reorder_level)
SELECT category_id, 'Keyboard', 'ELEC-001', 799.00, 25, 5 FROM categories WHERE category_name = 'Electronics';

INSERT IGNORE INTO products (category_id, product_name, sku, price, stock_quantity, reorder_level)
SELECT category_id, 'Trimax Pen', 'STAT-002', 50.00, 100, 20 FROM categories WHERE category_name = 'Stationery';

INSERT IGNORE INTO products (category_id, product_name, sku, price, stock_quantity, reorder_level)
SELECT category_id, 'Notebook', 'STAT-001', 80.00, 60, 15 FROM categories WHERE category_name = 'Stationery';

INSERT IGNORE INTO products (category_id, product_name, sku, price, stock_quantity, reorder_level)
SELECT category_id, 'USB Cable', 'ACC-001', 199.00, 50, 10 FROM categories WHERE category_name = 'Accessories';