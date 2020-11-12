from app import app, processes, logger

if __name__ == '__main__':
	app.run(port=3003)

	logger.info('[Loader] Stopping.')

	for i in processes:
		for j in processes[i]:
			processes[i][j].kill()

