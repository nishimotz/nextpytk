.PHONY: sync test run run-multiscreen run-task-panel run-gallery run-treeview run-paned run-progress run-tab-focus run-du-flat-async

PYTHON ?= 3.14

sync:
	uv sync --python $(PYTHON)

run: sync
	uv run --python $(PYTHON) python examples/grid_temp.py

run-multiscreen: sync
	uv run --python $(PYTHON) python examples/multiscreen.py

run-task-panel: sync
	uv run --python $(PYTHON) python examples/task_panel.py

run-gallery: sync
	uv run --python $(PYTHON) python examples/widget_gallery.py

run-treeview: sync
	uv run --python $(PYTHON) python examples/treeview_table.py

run-paned: sync
	uv run --python $(PYTHON) python examples/paned_split.py

run-progress: sync
	uv run --python $(PYTHON) python examples/progress_demo.py

run-tab-focus: sync
	uv run --python $(PYTHON) python examples/tab_focus_demo.py

run-du-flat-async: sync
	uv run --python $(PYTHON) python examples/disk_usage_flat_async.py

test: sync
	uv run --python $(PYTHON) pytest -q
