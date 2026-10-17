
CREATE DATABASE inventory_sales_management;

USE inventory_sales_management;



USE inventory_sales;

CREATE TABLE categories (
    category_id INT AUTO_INCREMENT PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE products (
    product_id INT AUTO_INCREMENT PRIMARY KEY,
    category_id INT,
    product_name VARCHAR(150) NOT NULL,
    sku VARCHAR(50) NOT NULL UNIQUE,
    price DECIMAL(10,2) NOT NULL,
    stock_quantity INT NOT NULL DEFAULT 0,
    reorder_level INT NOT NULL DEFAULT 5,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id)
        REFERENCES categories(category_id)
);

CREATE TABLE sales (
    sale_id INT AUTO_INCREMENT PRIMARY KEY,
    sale_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_amount DECIMAL(10,2) NOT NULL DEFAULT 0
);

CREATE TABLE sale_items (
    sale_item_id INT AUTO_INCREMENT PRIMARY KEY,
    sale_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (sale_id) REFERENCES sales(sale_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
