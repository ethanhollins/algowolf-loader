import os
import json
import time
import subprocess
import socketio
import boto3
import logging
import platform
from db import Database


'''
Initialization
'''

def load_config():
	with open('config.json', 'r') as f:
		return json.loads(f.read())


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


# Retrieve config
config = load_config()
# Create socket object
sio = socketio.Client()
# Create Database Handler
db = Database(config.get('DATABASE'))
# Create Logger
logger = create_logger()
logger.setLevel(logging.DEBUG)
# Create processes container
processes = {}

# Initialize Paths
if platform.system() == 'Windows':
	PATH = os.path.dirname(os.path.abspath(__file__))
	SCRIPTS_PATH = os.path.join(PATH, 'scripts')
	PACKAGES_PATH = os.path.join(PATH, 'packages')
	VENV_PATH = 'venv'
	PYTHON_PATH = 'venv\\scripts\\python.exe'
	PYTHON_SDK_PATH = 'venv\\scripts\\pythonsdk.exe'

else:
	PATH = os.path.dirname(os.path.abspath(__file__))
	SCRIPTS_PATH = os.path.join(PATH, 'scripts')
	PACKAGES_PATH = os.path.join(PATH, 'packages')
	VENV_PATH = 'venv'
	PYTHON_PATH = 'venv/bin/python3'
	PYTHON_SDK_PATH = 'venv/bin/pythonsdk'

config['SCRIPTS_PATH'] = SCRIPTS_PATH

'''
Main Functions
'''

def load_script_properties(script_id):
	package_path = os.path.join(SCRIPTS_PATH, script_id, 'package.json')
	if os.path.exists(package_path):
		with open(package_path, 'r') as f:
			return json.loads(f.read())

	return {}

def save_script_properties(script_id, obj):
	package_path = os.path.join(SCRIPTS_PATH, script_id, 'package.json')
	with open(package_path, 'w') as f:
		f.write(json.dumps(obj, indent=2))


def compile_script(script_id, version, strategy_id, auth_key):
	processes[user_id][account_code] = subprocess.Popen(
		[
			os.path.join(SCRIPTS_PATH, script_id, PYTHON_SDK_PATH), 'compile', '.'.join((script_id, version)), 
			'-sid', strategy_id, '-key', auth_key, '-c', json.dumps(config)
		]
	)


def initialize_script(script_id):
	# TODO: Send progress messages

	# Check script exists in storage

	# Initialize virtual environment
	logger.info(f'Initialize virtual envionment. {os.path.join(SCRIPTS_PATH, script_id, VENV_PATH)}')
	subprocess.run(['python', '-m', 'venv', os.path.join(SCRIPTS_PATH, script_id, VENV_PATH)], stdout=subprocess.DEVNULL)

	# Install Python SDK
	python_path = os.path.join(SCRIPTS_PATH, script_id, PYTHON_PATH)
	whl_files = [os.path.join(PACKAGES_PATH, i) for i in os.listdir(PACKAGES_PATH) if i.endswith('.whl')]
	logger.info(f'Whl files {whl_files}')
	logger.info('Install environment packages.')
	subprocess.run([python_path, '-m', 'pip', 'install', '--upgrade', 'pip'], stdout=subprocess.DEVNULL)
	subprocess.run([python_path, '-m', 'pip', 'install'] + whl_files, stdout=subprocess.DEVNULL)

	# Download script files
	db.downloadScript(script_id, SCRIPTS_PATH)
	save_script_properties(
		script_id,
		{
			'last_update': time.time()
		}
	)


def check_script_updates(script_id):
	# Install Python SDK
	python_path = os.path.join(SCRIPTS_PATH, script_id, PYTHON_PATH)
	whl_files = [os.path.join(PACKAGES_PATH, i) for i in os.listdir(PACKAGES_PATH) if i.endswith('.whl')]
	subprocess.run([python_path, '-m', 'pip', 'install', '--upgrade', 'pip'], stdout=subprocess.DEVNULL)
	subprocess.run([python_path, '-m', 'pip', 'install', '--upgrade'] + whl_files, stdout=subprocess.DEVNULL)

	properties = load_script_properties(script_id)

	# Update Script
	db.downloadScript(script_id, SCRIPTS_PATH, last_update=properties.get('last_update'))

	save_script_properties(
		script_id,
		{
			'last_update': time.time()
		}
	)


def generate_user_dict(user_id):
	if user_id not in processes:
		processes[user_id] = {}


def get_account_code(broker_id, account_id):
	return '.'.join((broker_id, account_id))


def run_script(user_id, strategy_id, broker_id, accounts, auth_key, input_variables, script_id, version):
	# Check if scripts exists
	python_path = os.path.join(SCRIPTS_PATH, script_id, PYTHON_PATH)
	script_path = os.path.join(SCRIPTS_PATH, script_id)

	generate_user_dict(user_id)
	for account_id in accounts:
		account_code = get_account_code(broker_id, account_id)
		if account_code not in processes[user_id] and os.path.exists(script_path):
			# Run script
			# TODO: Sandbox process
			logger.info(f'RUN {user_id}, {account_code}')
			processes[user_id][account_code] = subprocess.Popen(
				[
					os.path.join(SCRIPTS_PATH, script_id, PYTHON_SDK_PATH), 'run', '.'.join((script_id, version)), 
					'-sid', strategy_id, '-acc', account_code,  '-key', auth_key, 
					'-vars', json.dumps(input_variables), '-c', json.dumps(config)
				]
			)

'''
Socket Endpoints
'''

@sio.on('start', namespace='/admin')
def start_script(data):
	script_id = data.get('script_id')

	if script_id is not None:
		# Check if script exists
		if os.path.exists(os.path.join(SCRIPTS_PATH, script_id)):
			# Check for script updates
			check_script_updates(script_id)
		else:
			# Initialize script folder
			initialize_script(script_id)

		# Run script
		run_script(**data)


	return

@sio.on('stop', namespace='/admin')
def stop_script(data):
	# Send stop message
	user_id = data.get('user_id')
	broker_id = data.get('broker_id')
	accounts = data.get('accounts')

	if user_id in processes:
		for account_id in accounts:
			account_code = get_account_code(broker_id, account_id)

			if account_code in processes[user_id]:
				logger.info(f'TERMINATING {user_id}, {account_code}')
				processes[user_id][account_code].terminate()

				try:
					processes[user_id][account_code].wait(timeout=10)
				except subprocess.TimeoutExpired as e:
					processes[user_id][account_code].kill()


@sio.on('onuserupdate', namespace='admin')
def on_user_update(data):
	# Send update message.
	return


if __name__ == '__main__':
	# data = {
	# 	'user_id': '9sXFsHDK7oAEFaaDaZy8XL',
	# 	'package': 'v0_0_1',
	# 	'strategy_id': '2QNEJ6',
	# 	'broker_id': '6Q6Y3U',
	#	'accounts': ['ZU769']
	# 	'auth_key': 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI5c1hGc0hESzdvQUVGYWFEYVp5OFhMIiwiaWF0IjoxNjAzMzU1MjIxfQ.o9WPnUi18AYaEzLRz5_gg0jtMXGDWOtmIRu6201n1-Q',
	# 	'input_variables': {},
	# 	'script_id': 'test'
	# }
	# start_script(data)
	while True:
		try:
			sio.connect(config.get('STREAM_URL'), namespaces=['/admin'])
			break
		except socketio.exceptions.ConnectionError:
			time.sleep(1)

	logger.info("[Loader] Started.")
	try:
		while True: time.sleep(3)
	except KeyboardInterrupt:
		logger.info('[Loader] Stopping.')
		sio.disconnect()

		for i in processes:
			for j in processes[i]:
				processes[i][j].kill()

