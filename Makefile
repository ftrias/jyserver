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
	pip install --force dist/jyserver-0.0.1-py3-none-any.whl

upload: wheel
	twine upload dist/*

docs:
	mkdir docs

html: docs
	rm -rf docs/*
	pdoc --html -o docs jyserver/
	mv docs/jyserver/index.html docs
	rmdir docs/jyserver
	
.PHONY: init test