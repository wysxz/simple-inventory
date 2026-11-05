
# ----------------------------------------------------------------------------
# Imports
# ----------------------------------------------------------------------------

import os
import time
import sqlite3
import logging
import json
import datetime
import hmac
from urllib.parse import urlsplit
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_babelex import Babel
from sqlalchemy.schema import FetchedValue
from jinja2 import Markup
from wtforms import validators
import petl as etl
from dateutil.parser import parse
from werkzeug.security import check_password_hash

import flask_admin as admin
from flask_admin.contrib import sqla
from flask_admin.contrib.sqla import filters
from flask_admin.contrib.sqla import ModelView
from flask_admin.form import rules
from flask_admin import BaseView, expose
from .sale_price import ensure_sold_price_triggers

# ----------------------------------------------------------------------------
# Application Setup
# ----------------------------------------------------------------------------

# Create application
app = Flask(__name__)
app.config.from_pyfile('config.py')
if app.config.get('SECRET_KEY') == '123456790':
    app.config['SECRET_KEY'] = (
        os.environ.get('INVENTORY_SECRET_KEY') or os.urandom(32)
    )
app.config.setdefault(
    'LOGIN_USERNAME', os.environ.get('INVENTORY_LOGIN_USERNAME', '')
)
app.config.setdefault(
    'LOGIN_PASSWORD_HASH',
    os.environ.get('INVENTORY_LOGIN_PASSWORD_HASH', '')
)
babel = Babel(app)
db = SQLAlchemy(app)

# setup logging for SQLAlchemy
if app.config['SQLALCHEMY_LOGGING']:
    logging.basicConfig()
    logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def format_currency(view, context, model, name):
    # print("{0} - {1}".format(name, model.__dict__[name]))
    v = model.__dict__[name]
    # print(v)
    if v is not None:
        return Markup("¥{:,.2f}".format(v))
    else:
        return Markup("¥---")


def format_date(date_string, strf_string='%Y-%m-%d', replace_nonetype_with="00-00-0000"):
    # if date_string is None:
    #     print(date_string, type(date_string))
    #     return replace_nonetype_with
    # else:
    dt = date_string if isinstance(date_string, datetime.datetime) else parse(date_string)
    return dt.strftime(strf_string)


def parse_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value
    return parse(value)


def calculate_profit(rec, assume_quantity=1):
    """give a record created from a join of Sales and Product data, return profit.
    If no price information is available, returns zero. If no quantity information is available,
    uses the assume_quantity parameter (default = 1)

    Arguments:
        rec {dict} -- a record created from a join of Sales and Product data
        assume_quantity {int} -- number to use if quantity (from sale) is empty. defaults to 1

    Returns:
        gross profit from the sale, as a float
    """

    # print(rec['id'], rec['quantity'], rec['special_price'],
    #       rec['list_price'], rec['sold_price'])

    # determine quantity
    if not rec['quantity']:
        q = assume_quantity
    else:
        q = rec['quantity']
    # calculate profit
    if rec['special_price']:
        return round(((rec['special_price'] - rec['list_price']) * q), 2)
    elif rec['sold_price']:
        return round(((rec['sold_price'] - rec['list_price']) * q), 2)
    elif 'list_price' in rec:
        return 0
    else:
        return 0

    return 0


def calculate_gross_sales(rec, assume_quantity=1):
    """give a record created from a join of Sales and Product data, return gross sales.
    If no price information is available, returns zero. If no quantity information is available,
    uses the assume_quantity parameter (default = 1)

    Arguments:
        rec {dict} -- a record created from a join of Sales and Product data
        assume_quantity {int} -- number to use if quantity (from sale) is empty. defaults to 1

    Returns:
        gross profit from the sale, as a float
    """

    # print(rec['id'], rec['quantity'], rec['special_price'],
    #       rec['list_price'], rec['sold_price'])
    # determine quantity
    if not rec['quantity']:
        q = assume_quantity
    else:
        q = rec['quantity']
    # calculate profit
    if rec['special_price']:
        return round((rec['special_price'] * q), 2)
    elif rec['sold_price']:
        return round((rec['sold_price'] * q), 2)
    elif 'list_price' in rec:
        return round((rec['list_price'] * q), 2)
    else:
        return 0


def handle_none(v, replace_with=1):
    if v is None:
        return replace_with
    else:
        return v


def export_data(table):
    dir_path = os.path.dirname(os.path.realpath(__file__))
    print(dir_path)
    data_dir = os.path.join(dir_path, 'static', 'data')
    os.makedirs(data_dir, exist_ok=True)
    outpath = os.path.join(data_dir, "sales.csv")

    etl.tocsv(table, outpath)


def sales_summary(start_dt=None, end_dt=None, staff_id=None, for_export=False):
    # retrieve existing tables
    products_records = etl.fromdb(db.engine, 'SELECT * FROM product')
    sales_records = etl.fromdb(db.engine, 'SELECT * FROM sale')
    staff_records = etl.fromdb(db.engine, 'SELECT * FROM staff')

    # join product info to sales data
    sales_data = etl\
        .join(
            sales_records,
            products_records,
            lkey='product_id', 
            rkey='id'
        )\
        .leftjoin(
            staff_records,
            lkey='staff_id',
            rkey='id'
        )
            

    # prep joined sales data for tabulation
    sales_data = etl\
        .convert(
            sales_data,
            'date',
            lambda dt: format_date(dt, '%Y-%m-%d %H:%M:%S.%f') if dt else None
        )\
        .sort('date')\
        .convert('quantity', lambda q: handle_none(q, replace_with=1))\
        .addfield('profit', lambda rec: calculate_profit(rec))\
        .addfield('gross_sales', lambda rec: calculate_gross_sales(rec))

    if not for_export:
        export_data(sales_data)

    if start_dt is not None:
        sales_data = etl.select(
            sales_data,
            'date',
            lambda value: value is not None and parse_datetime(value) >= start_dt
        )
    if end_dt is not None:
        sales_data = etl.select(
            sales_data,
            'date',
            lambda value: value is not None and parse_datetime(value) <= end_dt
        )
    if staff_id:
        sales_data = etl.select(sales_data, 'staff_id', lambda value: value == staff_id)

    chart_end = end_dt or datetime.datetime.now()
    if start_dt is not None:
        chart_start = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        bucket_count = 24
    else:
        chart_start = chart_end - datetime.timedelta(hours=24)
        bucket_count = 24
    chart_hours = [
        chart_start + datetime.timedelta(hours=index)
        for index in range(bucket_count)
    ]
    hourly_summary = {
        hour.strftime('%Y-%m-%dT%H:%M:%S'): {
            'gross_sales': 0, 'profits': 0, 'count': 0
        }
        for hour in chart_hours
    }

    gross_sales = 0
    profits = 0
    for sale in etl.dicts(sales_data):
        sale_profit = calculate_profit(sale)
        sale_gross = calculate_gross_sales(sale)
        profits += sale_profit
        gross_sales += sale_gross
        if sale['date'] is not None:
            sale_dt = parse_datetime(sale['date'])
            bucket_index = int((sale_dt - chart_start).total_seconds() // 3600)
            if bucket_index == bucket_count and sale_dt == chart_end:
                bucket_index = bucket_count - 1
            if not 0 <= bucket_index < bucket_count:
                continue
            label = chart_hours[bucket_index].strftime('%Y-%m-%dT%H:%M:%S')
            bucket = hourly_summary[label]
            bucket['gross_sales'] += sale_gross
            bucket['profits'] += sale_profit
            bucket['count'] += 1

    if for_export:
        return {
            'gross_sales': gross_sales,
            'profits': profits,
            'table': sales_data
        }

    return {
        'gross_sales': gross_sales,
        'profits': profits,
        'chart_gross': [
            {'x': label, 'y': bucket['gross_sales']}
            for label, bucket in hourly_summary.items()
        ],
        'chart_profit': [
            {'x': label, 'y': bucket['profits']}
            for label, bucket in hourly_summary.items()
        ],
        'chart_count': [
            {'x': label, 'y': bucket['count']}
            for label, bucket in hourly_summary.items()
        ],
        'chart_gross_missing_date': [],
        'chart_profit_missing_date': [],
        'chart_count_missing_date': []
    }


# ----------------------------------------------------------------------------
# Models and corresponding custom Flask-Admin view classes
# ----------------------------------------------------------------------------

class Supplier(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), unique=True)
    contact = db.Column(db.String(255))
    email = db.Column(db.String(255))
    phone = db.Column(db.String)
    notes = db.Column(db.Text)

    def __str__(self):
        return self.name


class SupplierView(ModelView):
    column_labels = {
        'id': '编号',
        'name': '供应商名称',
        'contact': '联系人',
        'email': '电子邮箱',
        'phone': '联系电话',
        'notes': '备注',
    }
    column_searchable_list = ('name', 'contact', 'email', 'phone', 'notes')
    form_args = {
        'phone': {
            'validators': [
                validators.InputRequired(
                    message='联系电话必须为11位数字。'
                ),
                validators.Regexp(
                    r'^[0-9]{11}$',
                    message='联系电话必须为11位数字。'
                )
            ]
        }
    }
    form_widget_args = {
        'phone': {
            'maxlength': 11,
            'inputmode': 'numeric'
        }
    }
    action_disallowed_list = ['delete']
    column_exclude_list = ['notes']
    form_excluded_columns = ['suppliers']
    can_export = True
    can_delete = False


product_tags_table = db.Table(
    'product_tags',
    db.Model.metadata,
    db.Column('product_id', db.Integer, db.ForeignKey('product.id')),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'))
)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # descriptive fields
    code = db.Column(db.String(255), unique=True)
    name = db.Column(db.String(255), unique=True)
    quantity_per_unit = db.Column(db.Integer)
    list_price = db.Column(db.Float)
    selling_price = db.Column(db.Float)
    description = db.Column(db.Text)
    discontinued = db.Column(db.Boolean())

    # REF: Supplier (brand) table
    supplier_id = db.Column(db.Integer(), db.ForeignKey(Supplier.id))
    supplier = db.relationship(Supplier, backref='suppliers')

    # auto-completed from database trigger (concatentates several fields)
    fullname = db.Column(
        db.String(1000),
        server_default=FetchedValue(),
        server_onupdate=FetchedValue()
    )

    # intial amount; managed in a separate form
    initial_volume = db.Column(db.Integer)

    # REF: tags table
    tags = db.relationship('Tag', secondary=product_tags_table)

    def __str__(self):
        return (self.fullname or self.name or "商品 {}".format(self.id)).replace("$", "¥")


class ProductView(ModelView):
    column_labels = {
        'id': '编号',
        'code': '商品编码',
        'name': '商品名称',
        'quantity_per_unit': '每单位数量',
        'list_price': '进价',
        'selling_price': '销售价',
        'description': '商品描述',
        'discontinued': '已停用',
        'supplier': '供应商',
        'supplier_id': '供应商',
        'fullname': '商品信息',
        'initial_volume': '初始库存',
        'tags': '分类',
    }
    column_formatters = {
        'list_price': format_currency,
        'selling_price': format_currency
    }
    column_searchable_list = ('name', Supplier.name,
                              'tags.name', 'fullname', 'code')
    column_exclude_list = ['description', 'initial_volume', 'fullname']
    column_editable_list = ['tags']
    action_disallowed_list = ['delete']
    page_size = 100
    form_excluded_columns = ['products', 'fullname']
    can_export = True
    can_delete = False


'''
class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer(), db.ForeignKey(Product.id))
    units_purchased = db.Column(db.Integer, default=1)
    use_list_price = db.Column(db.Boolean(), default=False)
    special_price = db.Column(db.Float)
    date = db.Column(db.DateTime, default=datetime.datetime.now)
    notes = db.Column(db.Text)

    def __str__(self):
        return self.units_purchased


class Inventory(db.Model):
    """Inventory is a table populated by triggers fired in the Order and Sales tables.
    While directly editable, it should only need to be set-up once--for the initial
    inventory--and the triggers will handle the rest. Its primary purpose is to show
    how many items are left in stock
    """
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer(), db.ForeignKey(Product.id))
    notes = db.Column(db.Text)

    # in stock = initial volume - volume sold + volume replaced
    # in_stock is used to set an initial volume during table setup
    in_stock = db.Column(
        db.Integer,
        default=0,
        server_default=FetchedValue(),
        server_onupdate=FetchedValue()
    )

    # total replaced = *deincremented* from Order table entries
    volume_replaced = db.Column(
        db.Integer,
        default=0,
        server_default=FetchedValue(),
        server_onupdate=FetchedValue()
    )

    # total sold = *incremented* from Sale table entries
    volume_sold = db.Column(
        db.Integer,
        default=0,
        server_default=FetchedValue(),
        server_onupdate=FetchedValue()
    )

    def __str__(self):
        return self.in_stock
'''


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Unicode(64))

    def __str__(self):
        return self.name


class Staff(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text)

    def __str__(self):
        return self.name


class TagView(ModelView):
    column_labels = {
        'id': '编号',
        'name': '分类名称',
    }


class StaffView(ModelView):
    column_labels = {
        'id': '编号',
        'name': '员工姓名',
    }
    form_excluded_columns = ('staff',)


class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quantity = db.Column(db.Integer, default=1)
    date = db.Column(db.DateTime, default=datetime.datetime.now)
    special_price = db.Column(db.Float)
    use_list_price = db.Column(db.Boolean(), default=False)
    notes = db.Column(db.Text)
    product_id = db.Column(db.Integer(), db.ForeignKey(Product.id))
    product = db.relationship(Product, backref='products')
    staff_id = db.Column(db.Integer(), db.ForeignKey(Staff.id))
    staff = db.relationship(Staff, backref='staff')
    sold_price = db.Column(db.Float)

    def __str__(self):
        return self.product


class SaleView(ModelView):
    column_labels = {
        'id': '编号',
        'quantity': '数量',
        'date': '销售日期',
        'special_price': '特价',
        'use_list_price': '按进价销售',
        'notes': '备注',
        'product': '商品',
        'product_id': '商品',
        'staff': '经手员工',
        'staff_id': '经手员工',
        'sold_price': '成交单价',
    }
    column_formatters = {
        'special_price': format_currency,
        'sold_price': format_currency
    }
    column_searchable_list = (Product.fullname, Product.code, 'date')
    column_exclude_list = ['notes', 'special_price',
                           'fullname', 'use_list_price']
    form_excluded_columns = ['sold_price']
    can_export = True


class StockReceipt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey(Product.id), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    received_at = db.Column(db.DateTime, nullable=False, default=datetime.datetime.now)
    notes = db.Column(db.Text)


# ----------------------------------------------------------------------------
# Custom view classes (uses Flask-Admin template but not derived from table)
# ----------------------------------------------------------------------------

class InventoryView(BaseView):
    @expose('/')
    def index(self):
        db.create_all()

        sales_totals = dict(
            db.session.query(
                Sale.product_id,
                db.func.sum(db.func.coalesce(Sale.quantity, 1))
            ).group_by(Sale.product_id).all()
        )
        receipt_totals = dict(
            db.session.query(
                StockReceipt.product_id,
                db.func.sum(StockReceipt.quantity)
            ).group_by(StockReceipt.product_id).all()
        )

        products = Product.query.order_by(Product.name.asc()).all()
        inventory = []
        for product in products:
            opening = product.initial_volume or 0
            sold = sales_totals.get(product.id, 0) or 0
            received = receipt_totals.get(product.id, 0) or 0
            on_hand = opening + received - sold
            status = (
                '已停用' if product.discontinued else
                '需要补货' if on_hand <= 5 else
                '库存不足' if on_hand <= 10 else
                '库存充足'
            )
            inventory.append({
                'product': product,
                'opening': opening,
                'sold': sold,
                'received': received,
                'on_hand': on_hand,
                'status': status
            })

        low_stock = [
            item for item in inventory
            if not item['product'].discontinued and item['on_hand'] <= 10
        ]
        restock_needed = [
            item for item in inventory
            if not item['product'].discontinued and item['on_hand'] <= 5
        ]
        return self.render(
            'pages/inventory.html',
            inventory=inventory,
            low_stock=low_stock,
            restock_needed=restock_needed,
            active_products=[
                item['product'] for item in inventory
                if not item['product'].discontinued
            ],
            total_products=len(products),
            total_units=sum(max(item['on_hand'], 0) for item in inventory),
            low_stock_count=len(low_stock),
            restock_count=len(restock_needed)
        )

    @expose('/receive/', methods=('POST',))
    def receive(self):
        db.create_all()
        product_id = request.form.get('product_id', type=int)
        try:
            quantity = int(request.form.get('quantity', ''))
        except (TypeError, ValueError):
            quantity = 0

        product = Product.query.filter_by(id=product_id).first()
        if product is None or product.discontinued:
            flash('请选择有效且未停用的商品。', 'error')
        elif quantity <= 0:
            flash('补货数量必须是大于 0 的整数。', 'error')
        else:
            receipt = StockReceipt(
                product_id=product.id,
                quantity=quantity,
                notes=(request.form.get('notes') or '').strip() or None
            )
            db.session.add(receipt)
            db.session.commit()
            flash('已登记 {} 件商品“{}”入库。'.format(quantity, product.name), 'success')

        return redirect(self.get_url('.index'))


class AnalyticsView(BaseView):
    @expose('/')
    def index(self):
        now = datetime.datetime.now()
        selected_date = now.date()
        requested_date = request.args.get('date')
        date_error = None
        if requested_date:
            try:
                selected_date = datetime.datetime.strptime(
                    requested_date, '%Y-%m-%d'
                ).date()
            except ValueError:
                date_error = '日期无效，请选择有效日期。'

        start_dt = datetime.datetime.combine(
            selected_date, datetime.time.min
        )
        end_dt = datetime.datetime.combine(
            selected_date, datetime.time.max
        )
        summary = sales_summary(
            start_dt=start_dt,
            end_dt=end_dt
        )
        return self.render(
            'pages/analytics.html',
            summaryChartData=json.dumps(summary),
            gross_sales="¥{:,.2f}".format(summary['gross_sales']),
            profits="¥{:,.2f}".format(summary['profits']),
            selected_date=selected_date.isoformat(),
            date_error=date_error
        )

# ----------------------------------------------------------------------------
# Flask Views
# ----------------------------------------------------------------------------

# root route


def safe_next_url(target):
    if not target:
        return url_for('index')

    parsed = urlsplit(target)
    if (parsed.scheme or parsed.netloc or not parsed.path.startswith('/') or
            parsed.path.startswith('//') or '\\' in parsed.path):
        return url_for('index')
    return target


@app.before_request
def require_login():
    if request.endpoint in ('login', 'static'):
        return None
    if not session.get('authenticated'):
        return redirect(url_for('login', next=request.full_path))
    return None


@app.before_first_request
def initialize_sold_prices():
    database_path = db.engine.url.database
    if not database_path:
        raise RuntimeError('The SQLite database path is not configured.')
    ensure_sold_price_triggers(database_path)


@app.route('/login', methods=('GET', 'POST'))
def login():
    next_url = safe_next_url(request.values.get('next'))
    username = app.config.get('LOGIN_USERNAME', '')
    password_hash = app.config.get('LOGIN_PASSWORD_HASH', '')
    login_configured = bool(username and password_hash)
    error = None

    if session.get('authenticated'):
        return redirect(next_url)

    if request.method == 'POST':
        submitted_username = request.form.get('username', '')
        submitted_password = request.form.get('password', '')
        if not login_configured:
            error = '请先在配置文件中设置登录账号和密码哈希。'
        elif (hmac.compare_digest(
                submitted_username.encode('utf-8'),
                username.encode('utf-8')
        ) and check_password_hash(password_hash, submitted_password)):
            session.clear()
            session['authenticated'] = True
            return redirect(next_url)
        else:
            error = '账号或密码错误。'

    return render_template(
        'pages/login.html',
        error=error,
        next_url=next_url,
        login_configured=login_configured
    )


@app.route('/logout', methods=('POST',))
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
def index():
    # return redirect("/admin/", code=302)
    # return "<h1><a href='/admin/'>View Inventory</a></h1>"
    return render_template('/pages/index.html')


# Create admin
admin = admin.Admin(
    app,
    name=app.config['APP_TITLE'],
    index_view=admin.AdminIndexView(name='首页'),
    template_mode='bootstrap3'
)

# Add model views
admin.add_view(SaleView(Sale, db.session, name='销售记录'))
admin.add_view(SupplierView(Supplier, db.session, name='供应商'))
admin.add_view(ProductView(Product, db.session, name='商品'))
admin.add_view(TagView(Tag, db.session, name='商品分类'))
admin.add_view(StaffView(Staff, db.session, name='员工'))
# add custom views
admin.add_view(InventoryView(name='库存', endpoint='inventory'))
admin.add_view(AnalyticsView(name='销售统计', endpoint='analytics'))
