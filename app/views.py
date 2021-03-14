import os
import json
import time
import subprocess
import shortuuid
import platform
from app import (
	app, db, logger, processes, PATH, event_queue
)
from flask import Response, request

'''
Initialization
'''

# Initialize Paths
SCRIPTS_PATH = os.path.join(PATH, 'scripts')
PACKAGES_PATH = os.path.join(PATH, 'packages')
VENV_PATH = 'venv'

# WINDOWS
if platform.system() == 'Windows':
	PYTHON_PATH = 'venv\\scripts\\python.exe'
	PYTHON_SDK_PATH = 'venv\\scripts\\pythonsdk.exe'

# LINUX
else:
	PYTHON_PATH = 'venv/bin/python3'
	PYTHON_SDK_PATH = 'venv/bin/pythonsdk'

'''
Main Functions
'''

def getScriptConfig():
	return {
		'API_URL': app.config.get('API_URL'),
		'STREAM_URL': app.config.get('STREAM_URL'),
		'SCRIPTS_PATH': SCRIPTS_PATH
	}


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
	processes[user_id][account_code] = {
		'script_id': script_id,
		'input_variables': {},
		'process': subprocess.Popen(
			[
				os.path.join(SCRIPTS_PATH, script_id, PYTHON_SDK_PATH), 'compile', '.'.join((script_id, version)), 
				'-sid', strategy_id, '-key', auth_key, '-c', json.dumps(getScriptConfig())
			]
		)
	}

	


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
	subprocess.run([python_path, '-m', 'pip', 'install', '--upgrade', 'pip==20.3.1'], stdout=subprocess.DEVNULL)
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


def addEventToQueue(group_id):
	if group_id not in event_queue:
		event_queue[group_id] = []

	event_id = shortuuid.uuid()
	event_queue[group_id].append(event_id)
	return event_id


def popEventQueue(group_id):
	del event_queue[group_id][0]


def waitForEvent(group_id, event_id):
	while event_queue[group_id][0] != event_id:
		time.sleep(1)


def run_script(user_id, strategy_id, broker_id, accounts, auth_key, input_variables, script_id, version):
	# Check if scripts exists
	python_path = os.path.join(SCRIPTS_PATH, script_id, PYTHON_PATH)
	script_path = os.path.join(SCRIPTS_PATH, script_id)

	generate_user_dict(user_id)
	for account_id in accounts:
		account_code = get_account_code(broker_id, account_id)

		group_id = get_account_code(user_id, account_code)
		event_id = addEventToQueue(group_id)
		waitForEvent(group_id, event_id)

		if not check_running(user_id, broker_id, account_id) and os.path.exists(script_path):
			print(f'STARTING {user_id}, {account_code}')
			# Run script
			# TODO: Sandbox process
			logger.info(f'RUN {user_id}, {account_code}')
			processes[user_id][account_code] = {
				'script_id': script_id,
				'input_variables': input_variables,
				'process': subprocess.Popen(
					[
						os.path.join(SCRIPTS_PATH, script_id, PYTHON_SDK_PATH), 'run', '.'.join((script_id, version)), 
						'-sid', strategy_id, '-acc', account_code,  '-key', auth_key, 
						'-vars', json.dumps(input_variables), '-c', json.dumps(getScriptConfig())
					]
				)
			}

			
		else:
			print(f'ALREADY RUNNING {user_id}, {account_code}')

		popEventQueue(group_id)


def backtest_script(user_id, strategy_id, auth_key, input_variables, script_id, version, broker, start, end, spread):
	# Check if scripts exists
	python_path = os.path.join(SCRIPTS_PATH, script_id, PYTHON_PATH)
	script_path = os.path.join(SCRIPTS_PATH, script_id)

	# Run Backtest
	# TODO: Sandbox process
	logger.info(f'BACKTEST {user_id}, {script_id}')

	cmd = [
		os.path.join(SCRIPTS_PATH, script_id, PYTHON_SDK_PATH), 'backtest', '.'.join((script_id, version)), 
		'-sid', strategy_id, '-key', auth_key, '-vars', json.dumps(input_variables), '-b', broker, 
		'-f', str(start), '-t', str(end), '-c', json.dumps(getScriptConfig())
	]

	if spread is not None:
		cmd += ['-s', str(spread)]

	subprocess.Popen(cmd)


def getJson():
	try:
		body = request.get_json(force=True)
	except BadRequest:
		error = {
			'error': 'BadRequest',
			'message': 'Unrecognizable JSON body provided.'
		}
		abort(Response(
			json.dumps(error, indent=2),
			status=400, content_type='application/json'
		))

	return body


def check_running(user_id, broker_id, account_id):
	running = False
	if user_id in processes:
		account_code = get_account_code(broker_id, account_id)
		if account_code in processes[user_id]:
			running = processes[user_id][account_code]['process'].poll() is None
			if not running:
				del processes[user_id][account_code]
	if running:
		return processes[user_id][account_code]
	else:
		return None


'''
Endpoints
'''

@app.route("/")
def index():
	res = { 'message': 'Hello World!' }
	return Response(
		json.dumps(res, indent=2),
		status=200, content_type='application/json'
	)

@app.route('/start', methods=('POST',))
def start_script_ept():
	data = getJson()

	script_id = data.get('script_id')

	event_id = addEventToQueue(script_id)
	waitForEvent(script_id, event_id)

	if script_id is not None:
		# Check if script exists
		if os.path.exists(os.path.join(SCRIPTS_PATH, script_id)):
			# Check for script updates
			check_script_updates(script_id)
		else:
			# Initialize script folder
			initialize_script(script_id)

		popEventQueue(script_id)

		# Run script
		run_script(**data)
	else:
		popEventQueue(script_id)

	res = { 'started': script_id }
	return Response(
		json.dumps(res, indent=2),
		status=200, content_type='application/json'
	)


@app.route('/stop', methods=('POST',))
def stop_script_ept():
	data = getJson()

	# Send stop message
	user_id = data.get('user_id')
	broker_id = data.get('broker_id')
	accounts = data.get('accounts')

	if user_id in processes:
		for account_id in accounts:
			account_code = get_account_code(broker_id, account_id)

			group_id = get_account_code(user_id, account_code)
			event_id = addEventToQueue(group_id)
			waitForEvent(group_id, event_id)

			if account_code in processes[user_id]:
				logger.info(f'TERMINATING {user_id}, {account_code}')
				processes[user_id][account_code]['process'].terminate()

				try:
					processes[user_id][account_code]['process'].wait(timeout=10)
				except subprocess.TimeoutExpired as e:
					processes[user_id][account_code]['process'].kill()

				del processes[user_id][account_code]

			popEventQueue(group_id)

	res = { 'message': 'stopped' }
	return Response(
		json.dumps(res, indent=2),
		status=200, content_type='application/json'
	)


@app.route('/backtest', methods=('POST',))
def backtest_script_ept():
	data = getJson()
	print(data)

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
		backtest_script(**data)

	res = { 'message': 'started' }
	return Response(
		json.dumps(res, indent=2),
		status=200, content_type='application/json'
	)


@app.route('/running', methods=('GET',))
def is_script_running():
	data = getJson()

	# Send stop message
	user_id = data.get('user_id')
	broker_id = data.get('broker_id')
	account_id = data.get('account_id')

	running = check_running(user_id, broker_id, account_id)			

	if running is not None:
		res = { 
			'running': running['script_id'],
			'input_variables': running['input_variables']
		}
	else:
		res = { 
			'running': None,
			'input_variables': {}
		}
	return Response(
		json.dumps(res, indent=2),
		status=200, content_type='application/json'
	)

