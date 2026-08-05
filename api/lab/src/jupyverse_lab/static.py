from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit


@dataclass(frozen=True)
class StaticScript:
    attributes: tuple[tuple[str, str | None], ...]
    source: str
    path: PurePosixPath
    query: str
    fragment: str


class _ScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[tuple[tuple[str, str | None], ...]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script" and any(name == "src" for name, _ in attrs):
            self.scripts.append(tuple(attrs))


def parse_static_scripts(html: str) -> list[StaticScript]:
    parser = _ScriptParser()
    parser.feed(html)
    scripts = []

    for attributes in parser.scripts:
        source = next(value for name, value in attributes if name == "src")
        if source is None:
            raise ValueError("Script source cannot be empty")

        parsed_source = urlsplit(source)
        decoded_path = unquote(parsed_source.path)
        path = PurePosixPath(decoded_path)
        if (
            parsed_source.scheme
            or parsed_source.netloc
            or "\\" in decoded_path
            or ".." in path.parts
        ):
            raise ValueError(f"Script source is not local: {source}")

        scripts.append(
            StaticScript(
                attributes,
                source,
                path,
                parsed_source.query,
                parsed_source.fragment,
            )
        )

    return scripts
