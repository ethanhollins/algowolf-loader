import sys
import os
import json
from db import Database

def load_config():
	with open('config.json', 'r') as f:
		return json.loads(f.read())

def deploy_script():
	if len(sys.argv) == 3:
		script_id = sys.argv[1]
		path = sys.argv[2]
		if not os.path.exists(path):
			print('[ERROR] Path does not exist.')
			return

		print('Uploading...')
		db.uploadScript(script_id, path)
	else:
		print('[ERROR] Invalid arguments.')


config = load_config()
db = Database(config.get('DATABASE'))

if __name__ == '__main__':
	deploy_script()
