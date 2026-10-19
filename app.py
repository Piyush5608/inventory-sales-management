
from decimal import Decimal, InvalidOperation

from flask import (
    Flask, render_template, request,
    redirect, url_for, flash
)
from db import get_db_connection

app = Flask(__name__)

# Local development only. Move this to an environment variable
# before publishing the project.
app.secret_key = "change-this-to-a-random-secret"


@app.route("/api/products", methods=["GET"])
def api_products():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                p.product_id,
                p.product_name,
                p.sku,
                p.price,
                p.stock_quantity,
                p.reorder_level,
                c.category_name
            FROM products p
            LEFT JOIN categories c
                ON p.category_id = c.category_id
            ORDER BY p.product_id
        """)

        products = cursor.fetchall()

        # Convert database Decimal values into JSON-compatible numbers
        for product in products:
            if product["price"] is not None:
                product["price"] = float(product["price"])

        return {
            "success": True,
            "count": len(products),
            "products": products
        }

    except Exception:
        app.logger.exception("Product API failed")
        return {"success": False, "message": "Unable to retrieve products"}, 500

    finally:
        cursor.close()
        conn.close()



@app.route("/restock", methods=["GET", "POST"])
def restock():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        if request.method == "POST":
            product_id = request.form.get("product_id", type=int)
            quantity = request.form.get("quantity", type=int)
            notes = request.form.get("notes", "").strip()

            if not product_id or not quantity or quantity < 1:
                flash("Please select a product and enter a positive quantity.")
                return redirect(url_for("restock"))

            # Lock the product row while updating stock
            cursor.execute("""
                SELECT product_id, stock_quantity
                FROM products
                WHERE product_id = %s
                FOR UPDATE
            """, (product_id,))

            product = cursor.fetchone()

            if product is None:
                conn.rollback()
                flash("Product not found.")
                return redirect(url_for("restock"))

            # Increase stock
            cursor.execute("""
                UPDATE products
                SET stock_quantity = stock_quantity + %s
                WHERE product_id = %s
            """, (quantity, product_id))

            # Record the incoming stock
            cursor.execute("""
                INSERT INTO stock_movements
                    (product_id, quantity, movement_type, notes)
                VALUES (%s, %s, 'RESTOCK', %s)
            """, (product_id, quantity, notes or None))

            conn.commit()
            flash(
                f"Stock increased successfully by {quantity} units."
            )
            return redirect(url_for("restock"))

        cursor.execute("""
            SELECT product_id, product_name, stock_quantity
            FROM products
            ORDER BY product_name
        """)
        products = cursor.fetchall()

        return render_template("restock.html", products=products)

    except Exception:
        conn.rollback()
        app.logger.exception("Restock operation failed")
        flash("Could not update stock. Check the VS Code terminal for details.")
        return redirect(url_for("restock"))

    finally:
        cursor.close()
        conn.close()


@app.route("/stock-history")
def stock_history():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                sm.movement_id,
                sm.quantity,
                sm.movement_type,
                sm.movement_date,
                sm.notes,
                p.product_name,
                p.sku
            FROM stock_movements sm
            JOIN products p
                ON sm.product_id = p.product_id
            ORDER BY sm.movement_id DESC
        """)

        movements = cursor.fetchall()

        return render_template(
            "stock_history.html",
            movements=movements
        )

    finally:
        cursor.close()
        conn.close()


@app.route("/")
def dashboard():

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 1. Total number of products
        cursor.execute("""
            SELECT COUNT(*) AS total_products
            FROM products
        """)
        product_count = cursor.fetchone()["total_products"]

        # 2. Total revenue from completed sales
        cursor.execute("""
            SELECT COALESCE(SUM(total_amount), 0) AS revenue
            FROM sales
        """)
        revenue = cursor.fetchone()["revenue"]

        # 3. Number of products at or below reorder level
        cursor.execute("""
            SELECT COUNT(*) AS low_stock
            FROM products
            WHERE stock_quantity <= reorder_level
        """)
        low_stock = cursor.fetchone()["low_stock"]

        # 4. Total value of stock currently available
        cursor.execute("""
            SELECT COALESCE(
                SUM(price * stock_quantity), 0
            ) AS inventory_value
            FROM products
        """)
        inventory_value = cursor.fetchone()["inventory_value"]

        # 5. Products that need restocking
        cursor.execute("""
            SELECT product_name, sku, stock_quantity, reorder_level
            FROM products
            WHERE stock_quantity <= reorder_level
            ORDER BY stock_quantity ASC
            LIMIT 5
        """)
        low_stock_products = cursor.fetchall()

        # 6. Latest five sales
        cursor.execute("""
            SELECT
                s.sale_id,
                s.sale_date,
                s.total_amount,
                COALESCE(SUM(si.quantity), 0) AS items_sold
            FROM sales s
            LEFT JOIN sale_items si
                ON s.sale_id = si.sale_id
            GROUP BY
                s.sale_id, s.sale_date, s.total_amount
            ORDER BY s.sale_id DESC
            LIMIT 5
        """)
        recent_sales = cursor.fetchall()
        # Order statistics
        cursor.execute("""
            SELECT
                COUNT(*) AS total_orders,
                COALESCE(SUM(CASE
                    WHEN order_status = 'PENDING'
                    THEN 1 ELSE 0
                END), 0) AS pending_orders,
                COALESCE(SUM(CASE
                    WHEN order_status = 'CANCELLED'
                    THEN 1 ELSE 0
                END), 0) AS cancelled_orders,
                COALESCE(SUM(total_amount), 0) AS total_order_value,
                COALESCE(SUM(CASE
                    WHEN order_status = 'PAID'
                    THEN total_amount ELSE 0
                END), 0) AS paid_order_value
            FROM orders
        """)

        order_summary = cursor.fetchone()

        return render_template(
            "dashboard.html",
            product_count=product_count,
            revenue=revenue,
            low_stock=low_stock,
            inventory_value=inventory_value,
            low_stock_products=low_stock_products,
            recent_sales=recent_sales,
            order_summary=order_summary

        )

    finally:
        cursor.close()
        conn.close()


@app.route("/orders")
def orders_page():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                order_id,
                customer_name,
                customer_email,
                total_amount,
                order_status,
                created_at
            FROM orders
            ORDER BY created_at DESC
        """)

        orders = cursor.fetchall()

        return render_template("orders.html", orders=orders)

    finally:
        cursor.close()
        conn.close()


# @app.route("/orders/<int:order_id>")
# def order_details(order_id):
#     conn = get_db_connection()
#     cursor = conn.cursor(dictionary=True)

#     try:
#         cursor.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
#         order = cursor.fetchone()

#         if order is None:
#             return "Order not found", 404

#         return render_template("order_details.html", order=order)

#     finally:
#         cursor.close()
#         conn.close()

@app.route("/orders/<int:order_id>")
def order_details(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
        order = cursor.fetchone()

        if order is None:
            return "Order not found", 404

        cursor.execute("""
            SELECT p.product_name,
                   oi.quantity,
                   oi.unit_price,
                   (oi.quantity * oi.unit_price) AS subtotal
            FROM order_items oi
            JOIN products p ON p.product_id = oi.product_id
            WHERE oi.order_id = %s
        """, (order_id,))
        items = cursor.fetchall()

        return render_template("order_details.html", order=order, items=items)

    finally:
        cursor.close()
        conn.close()




@app.route("/products")
def products():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT p.*, c.category_name
            FROM products p
            LEFT JOIN categories c
                ON p.category_id = c.category_id
            ORDER BY p.product_id DESC
        """)
        product_list = cursor.fetchall()

        return render_template(
            "product.html",
            products=product_list
        )
    finally:
        cursor.close()
        conn.close()


@app.route("/products/add", methods=["GET", "POST"])
def add_product():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        if request.method == "POST":
            name = request.form.get("product_name", "").strip()
            sku = request.form.get("sku", "").strip()
            category_id = request.form.get("category_id") or None

            try:
                price = Decimal(request.form.get("price", ""))
                stock = int(request.form.get("stock_quantity", ""))
                reorder = int(request.form.get("reorder_level", ""))
            except (InvalidOperation, ValueError):
                flash("Enter valid price and stock values.")
                return redirect(url_for("add_product"))

            if not name or not sku:
                flash("Product name and SKU are required.")
                return redirect(url_for("add_product"))

            if not price.is_finite() or price < 0:
                flash("Price must be a valid non-negative amount.")
                return redirect(url_for("add_product"))

            if stock < 0 or reorder < 0:
                flash("Stock and reorder level cannot be negative.")
                return redirect(url_for("add_product"))

            try:
                cursor.execute("""
                    INSERT INTO products
                        (category_id, product_name, sku, price,
                         stock_quantity, reorder_level)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    category_id, name, sku, price,
                    stock, reorder
                ))
                conn.commit()
                flash("Product added successfully!")
                return redirect(url_for("products"))

            except Exception:
                conn.rollback()
                flash(
                    "Could not add product. Check that the SKU "
                    "is unique and the category is valid."
                )
                return redirect(url_for("add_product"))

        cursor.execute(
            "SELECT category_id, category_name "
            "FROM categories ORDER BY category_name"
        )
        categories = cursor.fetchall()

        return render_template(
            "add_product.html",
            categories=categories
        )
    finally:
        cursor.close()
        conn.close()


@app.route("/sales")
def sales():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT s.sale_id, s.sale_date, s.total_amount,
                   COALESCE(SUM(si.quantity), 0) AS items_sold
            FROM sales s
            LEFT JOIN sale_items si ON s.sale_id = si.sale_id
            GROUP BY s.sale_id, s.sale_date, s.total_amount
            ORDER BY s.sale_id DESC
        """)
        sale_list = cursor.fetchall()

        return render_template("sales.html", sales=sale_list)
    finally:
        cursor.close()
        conn.close()


@app.route("/sales/new", methods=["GET", "POST"])
def new_sale():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        if request.method == "POST":
            try:
                product_id = int(request.form.get("product_id", ""))
                quantity = int(request.form.get("quantity", ""))
            except ValueError:
                flash("Select a product and enter a valid quantity.")
                return redirect(url_for("new_sale"))

            if quantity < 1:
                flash("Quantity must be at least 1.")
                return redirect(url_for("new_sale"))

            try:
                conn.start_transaction()

                cursor.execute("""
                    SELECT product_id, price, stock_quantity
                    FROM products
                    WHERE product_id = %s
                    FOR UPDATE
                """, (product_id,))
                product = cursor.fetchone()

                if product is None:
                    conn.rollback()
                    flash("Product not found.")
                    return redirect(url_for("new_sale"))

                if product["stock_quantity"] < quantity:
                    conn.rollback()
                    flash("Not enough stock available.")
                    return redirect(url_for("new_sale"))

                total = product["price"] * quantity

                cursor.execute(
                    "INSERT INTO sales (total_amount) VALUES (%s)",
                    (total,)
                )
                sale_id = cursor.lastrowid

                cursor.execute("""
                    INSERT INTO sale_items
                        (sale_id, product_id, quantity, unit_price)
                    VALUES (%s, %s, %s, %s)
                """, (
                    sale_id, product_id,
                    quantity, product["price"]
                ))

                cursor.execute("""
                    UPDATE products
                    SET stock_quantity = stock_quantity - %s
                    WHERE product_id = %s
                """, (quantity, product_id))

                conn.commit()
                flash("Sale recorded and stock updated!")
                return redirect(url_for("sales"))

            except Exception:
                conn.rollback()
                app.logger.exception("Failed to record sale")
                flash("The sale could not be completed.")
                return redirect(url_for("new_sale"))

        cursor.execute("""
            SELECT product_id, product_name, price, stock_quantity
            FROM products
            WHERE stock_quantity > 0
            ORDER BY product_name
        """)
        product_list = cursor.fetchall()

        return render_template(
            "new_sale.html",
            products=product_list
        )
    finally:
        cursor.close()
        conn.close()


@app.route("/api/orders", methods=["POST"])
def create_order():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        data = request.get_json(silent=True) or {}

        customer_name = str(data.get("customer_name", "")).strip()
        customer_email = str(data.get("customer_email", "")).strip()

        try:
            product_id = int(data.get("product_id", 0))
            quantity = int(data.get("quantity", 0))
        except (TypeError, ValueError):
            return {
                "success": False,
                "message": "Product ID and quantity must be integers."
            }, 400

        if not customer_name or not customer_email:
            return {
                "success": False,
                "message": "Customer name and email are required."
            }, 400

        if product_id < 1 or quantity < 1:
            return {
                "success": False,
                "message": "Valid product ID and quantity are required."
            }, 400

        conn.start_transaction()

        # Get the product and lock its row during this transaction.
        cursor.execute("""
            SELECT product_id, product_name, price, stock_quantity
            FROM products
            WHERE product_id = %s
            FOR UPDATE
        """, (product_id,))

        product = cursor.fetchone()

        if product is None:
            conn.rollback()
            return {
                "success": False,
                "message": "Product not found."
            }, 404

        if product["stock_quantity"] < quantity:
            conn.rollback()
            return {
                "success": False,
                "message": "Insufficient stock."
            }, 400

        # Always calculate the price on the server.
        total = product["price"] * quantity

        cursor.execute("""
            INSERT INTO orders (
                customer_name,
                customer_email,
                total_amount,
                order_status
            )
            VALUES (%s, %s, %s, 'PENDING')
        """, (customer_name, customer_email, total))

        order_id = cursor.lastrowid

        cursor.execute("""
            INSERT INTO order_items (
                order_id,
                product_id,
                quantity,
                unit_price
            )
            VALUES (%s, %s, %s, %s)
        """, (order_id, product_id, quantity, product["price"]))

        # Stock is NOT deducted yet.
        # It will be deducted after verified payment.

        conn.commit()

        return {
            "success": True,
            "message": "Order created successfully. Payment is pending.",
            "order_id": order_id,
            "product_name": product["product_name"],
            "quantity": quantity,
            "total_amount": float(total),
            "order_status": "PENDING"
        }, 201

    except Exception:
        conn.rollback()
        app.logger.exception("Order creation failed")
        return {
            "success": False,
            "message": "Could not create order."
        }, 500

    finally:
        cursor.close()
        conn.close()


@app.route("/api/orders", methods=["GET"])
def get_orders():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                o.order_id,
                o.customer_name,
                o.customer_email,
                o.total_amount,
                o.order_status,
                o.created_at,
                oi.product_id,
                p.product_name,
                oi.quantity,
                oi.unit_price
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            JOIN products p ON oi.product_id = p.product_id
            ORDER BY o.order_id DESC
        """)

        orders = cursor.fetchall()

        return {
            "success": True,
            "total_orders": len(orders),
            "orders": orders
        }, 200

    except Exception:
        app.logger.exception("Fetching orders failed")
        return {
            "success": False,
            "message": "Could not fetch orders."
        }, 500

    finally:
        cursor.close()
        conn.close()
@app.route("/api/orders/<int:order_id>", methods=["GET"])
def get_order(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                o.order_id,
                o.customer_name,
                o.customer_email,
                o.total_amount,
                o.order_status,
                o.created_at,
                oi.product_id,
                p.product_name,
                oi.quantity,
                oi.unit_price
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            JOIN products p ON oi.product_id = p.product_id
            WHERE o.order_id = %s
        """, (order_id,))

        order = cursor.fetchone()

        if order is None:
            return {
                "success": False,
                "message": "Order not found."
            }, 404

        return {
            "success": True,
            "order": order
        }, 200

    except Exception:
        app.logger.exception("Fetching order failed")
        return {
            "success": False,
            "message": "Could not fetch order."
        }, 500

    finally:
        cursor.close()
        conn.close()

@app.route("/api/orders/<int:order_id>/payment", methods=["GET"])
def get_payment_status(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                o.order_id,
                o.order_status,
                p.payment_status,
                p.provider
            FROM orders o
            LEFT JOIN payments p ON o.order_id = p.order_id
            WHERE o.order_id = %s
        """, (order_id,))

        result = cursor.fetchone()

        if result is None:
            return {
                "success": False,
                "message": "Order not found."
            }, 404

        return {
            "success": True,
            "payment": result
        }, 200

    except Exception:
        app.logger.exception("Payment status lookup failed")
        return {
            "success": False,
            "message": "Could not retrieve payment status."
        }, 500

    finally:
        cursor.close()
        conn.close()


@app.route("/api/orders/<int:order_id>/cancel", methods=["POST"])
def cancel_order(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        conn.start_transaction()

        cursor.execute("""
            SELECT order_status
            FROM orders
            WHERE order_id = %s
            FOR UPDATE
        """, (order_id,))

        order = cursor.fetchone()

        if order is None:
            conn.rollback()
            return {
                "success": False,
                "message": "Order not found."
            }, 404

        if order["order_status"] != "PENDING":
            conn.rollback()
            return {
                "success": False,
                "message": "Only pending orders can be cancelled."
            }, 400

        cursor.execute("""
            UPDATE orders
            SET order_status = 'CANCELLED'
            WHERE order_id = %s
        """, (order_id,))

        cursor.execute("""
            UPDATE payments
            SET payment_status = 'FAILED'
            WHERE order_id = %s
              AND payment_status = 'PENDING'
        """, (order_id,))

        conn.commit()

        return {
            "success": True,
            "message": "Order cancelled successfully.",
            "order_id": order_id,
            "order_status": "CANCELLED"
        }, 200

    except Exception:
        conn.rollback()
        app.logger.exception("Order cancellation failed")
        return {
            "success": False,
            "message": "Could not cancel order."
        }, 500

    finally:
        cursor.close()
        conn.close()


@app.route("/orders/<int:order_id>/cancel", methods=["POST"])
def cancel_order_from_page(order_id):
    response, status_code = cancel_order(order_id)

    if status_code == 200:
        return redirect(url_for("orders_page"))

    if status_code == 404:
        return "Order not found.", 404

    if status_code == 400:
        return response["message"], 400

    return response["message"], 500



@app.route("/api/order-summary", methods=["GET"])
def order_summary():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                COUNT(*) AS total_orders,
                COALESCE(SUM(
                    CASE WHEN order_status = 'PENDING'
                    THEN 1 ELSE 0 END
                ), 0) AS pending_orders,
                COALESCE(SUM(
                    CASE WHEN order_status = 'CANCELLED'
                    THEN 1 ELSE 0 END
                ), 0) AS cancelled_orders,
                COALESCE(SUM(total_amount), 0)
                    AS total_order_value,
                COALESCE(SUM(
                    CASE WHEN order_status = 'PAID'
                    THEN total_amount ELSE 0 END
                ), 0) AS paid_order_value
            FROM orders
        """)

        summary = cursor.fetchone()

        # Convert Decimal values to JSON-friendly numbers.
        summary["total_order_value"] = float(
            summary["total_order_value"]
        )
        summary["paid_order_value"] = float(
            summary["paid_order_value"]
        )

        # Convert order counts to integers.
        summary["total_orders"] = int(summary["total_orders"])
        summary["pending_orders"] = int(summary["pending_orders"])
        summary["cancelled_orders"] = int(summary["cancelled_orders"])

        return {
            "success": True,
            "summary": summary
        }, 200

    except Exception:
        app.logger.exception("Order summary failed")
        return {
            "success": False,
            "message": "Could not fetch order summary."
        }, 500

    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    app.run(debug=True)
