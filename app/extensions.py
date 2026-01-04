"""
Flask extensions initialization.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Database
db = SQLAlchemy()

# Migrations
migrate = Migrate()
