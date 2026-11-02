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
	$(PYTHON) -m tools.sync_integration --check
	$(PYTHON) -m ruff check backend firmware provisioning installer tools tests custom_components
	$(PYTHON) -m ruff format --check backend firmware provisioning installer tools tests custom_components
	$(PYTHON) -m bandit -q -x custom_components/hearth/_backend -r backend firmware provisioning installer tools custom_components

audit:
	$(PYTHON) -m pip_audit --disable-pip --require-hashes -r requirements.lock
	$(PYTHON) -m pip_audit --disable-pip --require-hashes -r requirements-build.lock

demo:
	$(PYTHON) -m tools.demo_artifacts build/demo
addon:
	$(PYTHON) -m tools.package_addon build/addon
release:
	$(PYTHON) -m tools.public_release build/release
wheel:
	.venv/bin/pip install --require-hashes -r requirements-build.lock
	.venv/bin/pip wheel --no-deps --no-build-isolation --wheel-dir build/wheels .

image:
	$(CONTAINER_ENGINE) build -t hearth:dev .
