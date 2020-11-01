import os
import json
import time
import subprocess
import socketio
import boto3


'''
Initialization
'''

def load_config():
	with open('config.json', 'r') as f:
		return json.loads(f.read())

config = load_config()
sio = socketio.Client()
processes = {}

PATH = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_PATH = os.path.join(PATH, 'scripts')
PYTHON_PATH = 'venv\\scripts\\python.exe'

'''
Main Functions
'''

def initialize_script(script_id):
	# TODO: Send progress messages

	# Check script exists in storage

	# Initialize virtual environment
	subprocess.run(['python', '-m', 'venv', os.path.join(SCRIPTS_PATH, script_id, PYTHON_PATH)], stdout=subprocess.DEVNULL)

	# Install Python SDK
	python_path = os.path.join(SCRIPTS_PATH, script_id, PYTHON_PATH)
	whl_files = [i for i in os.listdir(os.path.join(PATH, 'packages')) if i.endswith('.whl')]
	subprocess.run([python_path, '-m', 'pip', 'install'] + whl_files, stdout=subprocess.DEVNULL)

	# Download script files

	return


def check_script_updates(script_id):
	# Compare last modified dates

	# Download new script
	return


def generate_user_dict(user_id):
	if user_id not in processes:
		processes[user_id] = {}


def run_script(user_id, account_code, script_id, input_variables):
	# Check if scripts exists
	python_path = os.path.join(SCRIPTS_PATH, script_id, PYTHON_PATH)
	script_path = os.path.join(SCRIPTS_PATH, script_id)
	
	generate_user_dict(user_id)
	if account_code not in processes[user_id] and os.path.exists(script_path):
		# Run script
		# TODO: Sandbox process
		processes[user_id][account_code] = subprocess.Popen(
			[], stdout=subprocess.DEVNULL
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
	run_script(script_id)


	return

@sio.on('stop', namespace='/admin')
def stop_script(data):
	# Send stop message
	return


@sio.on('onuserupdate', namespace='admin'):
def on_user_update(data):
	# Send update message
	return


if __name__ == '__main__':
	while True:
		try:
			sio.connect(config.get('STREAM_URL'), namespaces=['/admin'])
			break
		except socketio.exceptions.ConnectionError:
			time.sleep(1)
