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

.PHONY: init test