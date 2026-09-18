"""Print every route in the app as a Markdown table row.

Used to keep docs/API.md honest: the reference is generated from the live OpenAPI
schema rather than hand-copied, so a route cannot be documented that does not exist
or be added without appearing here.

    uv run python -m scripts.list_routes
"""

from app.main import app


def main() -> int:
    spec = app.openapi()

    rows: list[tuple[str, str, str, str]] = []

    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            tags = ", ".join(operation.get("tags") or [])
            summary = (operation.get("summary") or "").strip().replace("|", "\\|")
            rows.append((path, method.upper(), tags, summary))

    rows.sort(key=lambda row: (row[2], row[0], row[1]))

    width_path = max(len("Path"), *(len(row[0]) for row in rows))
    width_method = max(len("Method"), *(len(row[1]) for row in rows))
    width_tags = max(len("Tag"), *(len(row[2]) for row in rows))

    print(f"| {'Path':<{width_path}} | {'Method':<{width_method}} | {'Tag':<{width_tags}} | Summary |")
    print(f"| {'-' * width_path} | {'-' * width_method} | {'-' * width_tags} | --- |")

    for path, method, tags, summary in rows:
        print(f"| `{path}` | {method} | {tags} | {summary} |")

    print()
    print(f"{len(rows)} routes across {len(spec['paths'])} paths")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
