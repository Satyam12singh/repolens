from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FileNode:
    path: str           # repo-relative path
    size: int = 0
    language: str = ""
    content: Optional[str] = None


@dataclass
class FunctionNode:
    name: str
    file_path: str
    line_start: int
    line_end: int
    calls: list[str] = field(default_factory=list)   # raw call names found in body
    callers: list[str] = field(default_factory=list)  # populated by graph builder
    docstring: Optional[str] = None


@dataclass
class FileAnalysis:
    path: str
    language: str
    raw_imports: list[str] = field(default_factory=list)
    resolved_imports: list[str] = field(default_factory=list)  # repo-relative paths
    functions: list[FunctionNode] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)


@dataclass
class GraphStats:
    # file_path -> list of files it imports (within repo)
    import_edges: dict[str, list[str]] = field(default_factory=dict)
    # file_path -> in-degree (how many files import it)
    in_degree: dict[str, int] = field(default_factory=dict)
    circular_deps: list[list[str]] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)   # nothing imports these
    hub_files: list[tuple[str, int]] = field(default_factory=list)  # (path, in_degree) top-10
    # function_id "file::name" -> FunctionNode
    functions: dict[str, FunctionNode] = field(default_factory=dict)


@dataclass
class DtoField:
    name: str
    type_hint: str


@dataclass
class DtoModel:
    name: str
    file_path: str
    line: int
    fields: list[DtoField] = field(default_factory=list)
    kind: str = ""   # pydantic | dataclass | typeddict | interface | type | struct


@dataclass
class ApiEndpoint:
    method: str      # GET POST PUT DELETE PATCH WS ANY
    path: str
    handler: str
    file_path: str
    line: int
    framework: str   # Flask | FastAPI/Flask | Express | NestJS | Gin/Echo/Chi | actix-web | axum


@dataclass
class RepoAnalysis:
    root: str
    files: list[FileNode] = field(default_factory=list)
    file_analyses: dict[str, FileAnalysis] = field(default_factory=dict)
    stats: GraphStats = field(default_factory=GraphStats)
    endpoints: list[ApiEndpoint] = field(default_factory=list)
    dtos: list[DtoModel] = field(default_factory=list)
