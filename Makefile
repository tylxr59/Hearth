PYTHON ?= .venv/bin/python
CONTAINER_ENGINE ?= docker

.PHONY: test integration container-test check audit demo addon release image wheel

test:
	$(PYTHON) -m pytest -q
integration:
	HEARTH_CONTAINER_ENGINE=$(CONTAINER_ENGINE) HEARTH_BROKER_TEST=1 $(PYTHON) -m pytest -q
container-test: image
	HEARTH_CONTAINER_ENGINE=$(CONTAINER_ENGINE) HEARTH_CONTAINER_TEST=1 $(PYTHON) -m pytest -q tests/test_container.py

check:
	$(PYTHON) -m ruff check backend firmware provisioning tools tests
	$(PYTHON) -m ruff format --check backend firmware provisioning tools tests
	$(PYTHON) -m bandit -q -r backend firmware provisioning tools

audit:
	$(PYTHON) -m pip_audit --disable-pip --require-hashes -r requirements.lock
	$(PYTHON) -m pip_audit --disable-pip --require-hashes -r requirements-build.lock

demo:
	$(PYTHON) -m tools.demo_artifacts build/demo
addon:
	$(PYTHON) -m tools.package_addon build/addon
release:
	$(PYTHON) -m tools.release build/release
wheel:
	.venv/bin/pip install --require-hashes -r requirements-build.lock
	.venv/bin/pip wheel --no-deps --no-build-isolation --wheel-dir build/wheels .

image:
	$(CONTAINER_ENGINE) build -t hearth:dev .
