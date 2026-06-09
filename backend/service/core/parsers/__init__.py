import importlib
import pkgutil

from service.core.parsers.base import ContentParser, ParseResult

_registry: dict[str, ContentParser] = {}


def register_parser(parser: ContentParser) -> ContentParser:
    for source_type in parser.supported_types:
        _registry[source_type] = parser
    return parser


def get_parser(source_type: str) -> ContentParser:
    try:
        return _registry[source_type]
    except KeyError:
        raise ValueError(f"No parser registered for source type: {source_type}")


def _auto_import() -> None:
    package = importlib.import_module("service.core.parsers")
    for _, modname, ispkg in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
        if ispkg:
            continue
        importlib.import_module(modname)


_auto_import()

__all__ = ["ParseResult", "ContentParser", "register_parser", "get_parser"]
