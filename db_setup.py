#!/usr/bin/env python3

import os
import csv
import sqlite3
import petl as etl

from project.app import app, db
from project.app import Product, Supplier, Tag, Staff
from project.sale_price import ensure_sold_price_triggers

#db_path = r"C:\GitHub\fc-inventory\project\db.sqlite"
app_dir = os.path.realpath(os.path.dirname(__file__))
db_path = os.path.join(app_dir, 'project', app.config['DATABASE_FILE'])

#----------------------------------------------------------------------------#
# ETL
#----------------------------------------------------------------------------#

src_suppliers = etl.fromcsv("sources/Suppliers.csv")
src_products = etl.fromcsv("sources/Products.csv")
src_tags = etl.fromcsv("sources/Categories.csv")
src_staff = etl.fromcsv("sources/Staff.csv")


def create_suppliers():
    for row in etl.dicts(src_suppliers):
        new_supplier = Supplier(
            id=row["ID"],
            name=row["Company"]
        )
        db.session.add(new_supplier)
    db.session.commit()


def create_products():
    for row in etl.dicts(src_products):
        new_product = Product(
            code=row["ProductCode"],
            name=row["ProductName"],
            list_price=row["StandardCost"],
            selling_price=row["ListPrice"],
            quantity_per_unit=row["QuantityPerUnit"],
            description=row["Description"],
            supplier_id=row["SupplierID"],
            discontinued=row["Discontinued"],
        )
        db.session.add(new_product)
    db.session.commit()


def create_tags():
    for row in etl.dicts(src_tags):
        new_row = Tag(
            id=row["ID"],
            name=row["Category"]
        )
        db.session.add(new_row)
    db.session.commit()


def create_staff():
    for row in etl.dicts(src_staff):
        new_row = Staff(
            id=row["ID"],
            name=row["FullName"]
        )
        db.session.add(new_row)
    db.session.commit()

#----------------------------------------------------------------------------#
# DB CONFIG
#----------------------------------------------------------------------------#


def set_trigger_fullname(db_path):
    q1 = """
    CREATE TRIGGER product_update_fullname
    AFTER UPDATE ON product
    FOR EACH ROW
    BEGIN
        UPDATE product
        SET fullname = (SELECT supplier.name FROM supplier WHERE supplier.id = product.supplier_id) || ' | ' || name || ' | ¥' || list_price || ' list / ¥' || selling_price || ' selling price'
        WHERE id = new.id;
    END;
    """
    q2 = """
    CREATE TRIGGER product_insert_fullname
    AFTER INSERT ON product
    FOR EACH ROW
    BEGIN
        UPDATE product
        SET fullname = (SELECT supplier.name FROM supplier WHERE supplier.id = product.supplier_id) || ' | ' || name || ' | ¥' || list_price || ' list / ¥' || selling_price || ' selling price'
        WHERE id = new.id;
    END;
    """
    q3 = """
    CREATE TRIGGER update_supplier_update_product_fullname
    AFTER UPDATE ON supplier
    FOR EACH ROW
    BEGIN
        UPDATE product
        SET fullname = (SELECT supplier.name FROM supplier WHERE supplier.id = product.supplier_id) || ' | ' || product.name || ' | ¥' || product.list_price || ' list / ¥' || product.selling_price || ' selling price';
    END;
    """
    q4 = """UPDATE product SET fullname = (SELECT supplier.name FROM supplier WHERE supplier.id = product.supplier_id) || ' | ' || name || ' | ¥' || list_price || ' list / ¥' || selling_price || ' selling price';"""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    for each in [q1, q2, q3, q4]:
        c.execute(each)
    conn.commit()
    conn.close()


def set_trigger_selling_price(db_path):
    ensure_sold_price_triggers(db_path)

#----------------------------------------------------------------------------#
# CREATE SOME DATA
#----------------------------------------------------------------------------#


def build_db():
    # build tables from source data
    print(app.config)
    create_suppliers()
    create_tags()
    create_products()
    create_staff()
    # set triggers
    set_trigger_fullname(db_path)
    set_trigger_selling_price(db_path)


if __name__ == '__main__':
    db.drop_all()
    db.create_all()
    build_db()
