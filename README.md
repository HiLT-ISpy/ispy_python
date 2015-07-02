# iSpy_python

Setup:

1. Make sure the database settings in config.py match your local database
2. If running for the first time, make sure that 'setup = True' is set in config.py. This will clean the database and build the initial models
3. If not the first time, you can change setup to False, but that won't clean out the old answers/start fresh

Run: 
- Execute 'python main.py' from within the ispy_python directory

Dependencies:
- MySQL server
- mysql-python or pymysql
- opencv
- sklearn
- matplotlib
- numpy

Configuration ('config.py')
- db: Database credentials
- setup: Should the pre-simulation tasks be executed?
