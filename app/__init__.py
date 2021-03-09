import os
import logging
from flask import Flask
from app.db import Database

def create_logger():
	logger = logging.getLogger(__name__)
	handler = logging.StreamHandler()
	formatter = logging.Formatter(
		fmt='%(asctime)s %(levelname)s: %(message)s', 
		datefmt='%d/%m/%Y %H:%M:%S'
	)
	handler.setFormatter(formatter)
	logger.addHandler(handler)
	return logger


def create_app(test_config=None):
	
	instance_path = os.path.join(os.path.abspath(os.getcwd()), 'instance')
	app = Flask(__name__, instance_relative_config=True, instance_path=instance_path)

	app.config.from_mapping(
		SECRET_KEY='dev',
		BROKERS=os.path.join(app.instance_path, 'brokers.json')
	)

	if test_config is None:
		# load the instance config, if it exists, when not testing
		app.config.from_pyfile(os.path.join(app.instance_path, 'config.py'), silent=True)
	else:
		# load the test config if passed in
		app.config.from_mapping(test_config)

	# Ensure the instance folder exists
	try:
		os.makedirs(app.instance_path)
	except OSError:
		pass

	if 'DEBUG' in app.config:
		app.debug = app.config['DEBUG']

	return app

app = create_app()

# Create Database Handler
db = Database(app.config.get('DATABASE'))
# Create Logger
logger = create_logger()
logger.setLevel(logging.DEBUG)
# Create processes container
processes = {}
event_queue = {}
# Create Path constant
PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


from app import views