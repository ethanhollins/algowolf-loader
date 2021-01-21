import sys
import os
import json
import subprocess
from app.db import Database
from app.views import initialize_script, check_script_updates

def load_config():
	with open('./instance/config.json', 'r') as f:
		return json.loads(f.read())

config = load_config()
db = Database(config.get('DATABASE'))

PATH = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_PATH = os.path.join(PATH, 'scripts')
PYTHON_SDK_PATH = 'venv\\scripts\\pythonsdk.exe'

config['SCRIPTS_PATH'] = SCRIPTS_PATH

def getScriptConfig():
	return {
		'API_URL': config.get('API_URL'),
		'STREAM_URL': config.get('STREAM_URL'),
		'SCRIPTS_PATH': SCRIPTS_PATH
	}


def compile_script(script_id, version):
	strategy_id = 'J330N2'
	account_code = 'CH566W.101-011-13163978-001'
	auth_key = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI5c1hGc0hESzdvQUVGYWFEYVp5OFhMIiwiaWF0IjoxNjAzMzU1MjIxfQ.o9WPnUi18AYaEzLRz5_gg0jtMXGDWOtmIRu6201n1-Q'

	subprocess.run(
		[
			os.path.join(SCRIPTS_PATH, script_id, PYTHON_SDK_PATH), 
			'compile', '.'.join((script_id, version)), '-sid', strategy_id,
			'-acc', account_code, '-key', auth_key,
			'-c', json.dumps(getScriptConfig())
		]
	)


def deploy_script():
	if len(sys.argv) == 4:
		script_id = sys.argv[1]
		version = sys.argv[2]
		path = sys.argv[3]
		if not os.path.exists(path):
			print('[ERROR] Path does not exist.')
			return

		print('Uploading...')
		db.uploadScript(script_id, path)

		# Check if script exists
		if os.path.exists(os.path.join(SCRIPTS_PATH, script_id)):
			# Check for script updates
			check_script_updates(script_id)
		else:
			# Initialize script folder
			initialize_script(script_id)

		print('Compiling...')
		compile_script(script_id, version)
	else:
		print('[ERROR] Invalid arguments.')


if __name__ == '__main__':
	deploy_script()
