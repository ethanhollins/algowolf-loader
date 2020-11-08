import shortuuid
import boto3
import os
import shutil
import time
import collections
from decimal import Decimal
from datetime import datetime

class Database(object):

	def __init__(self, db_name):
		self._generate_db()
		self._generate_s3()
		if 'dev' in db_name:
			self.scriptTable = self._generate_table('algowolf-scripts-dev')
			self.scriptBucketName = 'algowolf-scripts-dev'
		else:
			self.scriptTable = self._generate_table('algowolf-scripts')
			self.scriptBucketName = 'algowolf-scripts'

	# DB Functions
	def _generate_db(self):
		self._db_client = boto3.resource(
			'dynamodb',
			region_name='ap-southeast-2'
		)


	def _generate_table(self, table_name):
		return self._db_client.Table(table_name)


	def _convert_to_decimal(self, row):
		if isinstance(row, dict):
			for k in row:
				row[k] = self._convert_to_decimal(row[k])
		elif (not isinstance(row, str) and
			isinstance(row, collections.Iterable)):
			row = list(row)
			for i in range(len(row)):
				row[i] = self._convert_to_decimal(row[i])
		elif isinstance(row, float):
			return Decimal(row)
			
		return row

	def _convert_to_float(self, row):
		if isinstance(row, dict):
			for k in row:
				row[k] = self._convert_to_float(row[k])
		elif (not isinstance(row, str) and
			isinstance(row, collections.Iterable)):
			row = list(row)
			for i in range(len(row)):
				row[i] = self._convert_to_float(row[i])
		elif isinstance(row, Decimal):
			return float(row)

		return row


	# S3 Storage
	def _generate_s3(self):
		self._s3_client = boto3.client('s3')
		self._s3_res = boto3.resource('s3')


	# General Functions
	def getScriptData(self, script_id):
		res = self.scriptTable.get_item(
			Key={ 'script_id': script_id }
		)
		if res.get('Item') is not None:
			return self._convert_to_float(res['Item'])
		else:
			return None


	def updateScriptData(self, script_id, update):
		update_values = self._convert_to_decimal(
			dict([tuple([':{}'.format(i[0][0]), i[1]])
					for i in update.items()])
		)
		update_exp = ('set ' + ' '.join(
			['{} = :{},'.format(k, k[0]) for k in update.keys()]
		))[:-1]
		res = self.scriptTable.update_item(
			Key={
				'script_id': script_id
			},
			UpdateExpression=update_exp,
			ExpressionAttributeValues=update_values,
			ReturnValues="UPDATED_NEW"
		)
		return True


	def isUpdated(self, script_id, last_update):
		item = self.getScriptData(script_id)
		if (
			item is not None and
			item.get('last_update') is not None and 
			last_update > item.get('last_update')
		):
			return True

		return False


	def downloadScript(self, script_id, path, last_update=None):
		bucket = self._s3_res.Bucket(self.scriptBucketName)
		objects = bucket.objects.filter(Prefix=script_id+'/')

		if last_update is not None:
			script_path = os.path.join(path, script_id)
			if not isUpdated(script_id, last_update):
				# Delete all files
				for i in os.listdir(script_path):
					if os.path.isdir(os.path.join(script_path, i)):
						if i != 'venv':
							shutil.rmtree(os.path.join(script_path, i))
					elif os.path.isfile(os.path.join(script_path, i)):
						if i != 'package.json':
							os.remove(os.path.join(script_path, i))
			else:
				return

		for obj in objects:
			if not os.path.exists(os.path.join(path, os.path.dirname(obj.key))):
				os.makedirs(os.path.join(path, os.path.dirname(obj.key)))
			bucket.download_file(obj.key, os.path.join(path, obj.key))


	def recursiveUpload(self, bucket, key, script_path, path):
		IGNORE = ['__pycache__', 'venv', '.pyc']
		current_path = os.path.join(script_path, path)
		for i in os.listdir(current_path):
			# Check ignore
			for x in IGNORE:
				if x in i:
					continue

			if os.path.isdir(os.path.join(current_path, i)):
				self.recursiveUpload(bucket, key, script_path, os.path.join(path, i))
			elif os.path.isfile(os.path.join(current_path, i)):
				if path:
					upload_key = '/'.join((key, path.replace('\\', '/'), i))
				else:
					upload_key = '/'.join((key, i))

				with open(os.path.join(current_path, i), 'rb') as data:
					bucket.upload_fileobj(data, upload_key)


	def uploadScript(self, script_id, path):
		bucket = self._s3_res.Bucket(self.scriptBucketName)

		# Delete old files
		bucket.objects.filter(Prefix=script_id+'/').delete()
		# Upload new files
		self.recursiveUpload(bucket, script_id, os.path.join(path, script_id), '')
		# Update script metadata
		update = {
			'last_update': time.time()
		}
		self.updateScriptData(script_id, update)

