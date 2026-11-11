.PHONY: run test smoke install icons clean

run:
	python3 main.py

test:
	QT_QPA_PLATFORM=offscreen python3 -m pytest test_app.py -v

smoke:
	python3 test_pipeline.py

install:
	pip3 install -r requirements.txt pytest pytest-qt

icons:
	pip3 install qtawesome

clean:
	rm -rf __pycache__ ui/__pycache__ .pytest_cache
