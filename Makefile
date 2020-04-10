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

inst: wheel
	pip install --force dist/jyserver-0.0.1-py3-none-any.whl

.PHONY: init test