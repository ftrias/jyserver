all: jyserver/jyserver-min.js html wheel

init:
	pip install -r requirements.txt

test:
	py.test tests

wheel:
	rm -rf dist
	python setup.py sdist bdist_wheel

clean:
	rm -rf dist
	rm -r *.egg-info

install: wheel
	pip install --force dist/jyserver-*-py3-none-any.whl

upload: wheel
	twine upload dist/*

html: docs
	# pdoc --html --html-dir docs --all-submodules jyserver
	pdoc3 --html -o docs --force jyserver

# use https://developers.google.com/closure/compiler/docs/gettingstarted_app
jyserver/jyserver-min.js: jyserver/jyserver.js
	java -jar scratch/closure-compiler-v20200406.jar --js $< --js_output_file $@
