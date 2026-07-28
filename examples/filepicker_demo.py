"""Demo for @app.filepicker declarative file dialogs."""

from __future__ import annotations

from typing import Any

from nextpytk import TkApp, Layout


def main() -> None:
    app = TkApp(title="filepicker demo")

    @app.filepicker("open_file", mode="open", label="Open file",
                     title="Open file", filetypes=[("Text files", "*.txt")])
    def open_file(path: str | None) -> dict[str, Any]:
        return {"message": f"opened: {path}", "open_file": path}

    @app.filepicker("save_file", mode="save", label="Save as",
                     title="Save file", defaultextension=".txt")
    def save_file(path: str | None) -> dict[str, Any]:
        return {"message": f"save to: {path}", "save_file": path}

    @app.filepicker("folder", mode="directory", label="Choose folder",
                     title="Select directory")
    def folder(path: str | None) -> dict[str, Any]:
        return {"message": f"folder: {path}", "folder": path}

    @app.label("message")
    def message() -> str:
        return "pick a file"

    @app.label("open_file_path")
    def open_file_path_label() -> str:
        return ""

    app.run(
        layout=Layout()
            .section("open_file", "save_file", "folder")
            .section("message")
            .section("open_file_path"),
    )


if __name__ == "__main__":
    main()
