env/bin/activate:
	virtualenv env
	. env/bin/activate && pip install -r requirements.txt #&& pip install -e .

develop: env/bin/activate

start: develop
	. env/bin/activate && python ./src/webserver.py &

