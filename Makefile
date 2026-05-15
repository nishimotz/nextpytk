.PHONY: sync run run-multiscreen run-task-panel run-gallery run-du-flat run-du-flat-async

PYTHON ?= 3.14

sync:
	uv sync --python $(PYTHON)

run: sync
	uv run --python $(PYTHON) python examples/tkouter_grid_temp.py

run-multiscreen: sync
	uv run --python $(PYTHON) python examples/tkouter_multiscreen.py

run-task-panel: sync
	uv run --python $(PYTHON) python examples/tkouter_task_panel.py

run-gallery: sync
	uv run --python $(PYTHON) python examples/tkouter_widget_gallery.py

run-du-flat: sync
	uv run --python $(PYTHON) python examples/disk_usage_flat_viewer.py

run-du-flat-async: sync
	uv run --python $(PYTHON) python examples/disk_usage_flat_async.py
