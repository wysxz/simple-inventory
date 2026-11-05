import os

# Application Properties
ORG_NAME = '商品库存销售管理系统'
APP_TITLE = '商品库存销售管理系统'
APP_DESC = '用于管理商品库存、供应商、销售记录和销售统计。'

# Set INVENTORY_SECRET_KEY to a persistent random value for deployments.
SECRET_KEY = os.environ.get('INVENTORY_SECRET_KEY') or os.urandom(32)

# Generate a hash with:
# python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your-password'))"
LOGIN_USERNAME = os.environ.get('INVENTORY_LOGIN_USERNAME', '')
LOGIN_PASSWORD_HASH = os.environ.get('INVENTORY_LOGIN_PASSWORD_HASH', '')

# Flask-Admin config
DEBUG = False
HOST = '127.0.0.1'
PORT = 5000
FLASK_ADMIN_SWATCH = "readable"
BABEL_DEFAULT_LOCALE = 'zh_Hans_CN'

# database
DATABASE_FILE = 'inventory_0.1.0.sqlite'
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + DATABASE_FILE
SQLALCHEMY_ECHO = True
SQLALCHEMY_TRACK_MODIFICATIONS = True
SQLALCHEMY_LOGGING = False