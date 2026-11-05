import sqlite3


_SALE_PRICE = """
CASE
    WHEN special_price IS NOT NULL AND special_price > 0
        THEN special_price
    WHEN use_list_price = 1
        THEN (SELECT list_price FROM product WHERE product.id = sale.product_id)
    ELSE
        (SELECT selling_price FROM product WHERE product.id = sale.product_id)
END
"""


def ensure_sold_price_triggers(database_path):
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("""
            CREATE TRIGGER IF NOT EXISTS record_selling_price_at_time_of_sale
            AFTER INSERT ON sale
            FOR EACH ROW
            BEGIN
                UPDATE sale
                SET sold_price = {}
                WHERE id = new.id;
            END;
        """.format(_SALE_PRICE))
        connection.execute("""
            CREATE TRIGGER IF NOT EXISTS update_selling_price_if_sale_price_changes
            AFTER UPDATE OF special_price, use_list_price, product_id ON sale
            FOR EACH ROW
            BEGIN
                UPDATE sale
                SET sold_price = {}
                WHERE id = new.id;
            END;
        """.format(_SALE_PRICE))
        connection.execute("""
            UPDATE sale
            SET sold_price = {}
            WHERE sold_price IS NULL;
        """.format(_SALE_PRICE))
        connection.commit()
    finally:
        connection.close()
