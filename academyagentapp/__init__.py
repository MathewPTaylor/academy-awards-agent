from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///site.db"
app.config['SECRET_KEY'] = "suckyourmumontuesdays"

CORS(app)
db = SQLAlchemy(app)

from academyagentapp import routes