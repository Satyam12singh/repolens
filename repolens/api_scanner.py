from __future__ import annotations

import ast
import re
from typing import Optional

from .models import ApiEndpoint, DtoField, DtoModel, FileNode

_HTTP_METHODS = frozenset({"get", "post", "put", "delete", "patch", "head", "options", "ws", "websocket"})

METHOD_COLORS = {
    "GET":    "#68d391",
    "POST":   "#63b3ed",
    "PUT":    "#f6ad55",
    "DELETE": "#fc8181",
    "PATCH":  "#b794f4",
    "WS":     "#fbd38d",
    "MSG":    "#fbd38d",
    "ANY":    "#718096",
}


# ── Python ────────────────────────────────────────────────────────────────────

def _extract_str(node: ast.expr) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _py_endpoints(file_node: FileNode) -> list[ApiEndpoint]:
    if not file_node.content:
        return []
    try:
        tree = ast.parse(file_node.content)
    except SyntaxError:
        return []

    results: list[ApiEndpoint] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            func = dec.func
            if not isinstance(func, ast.Attribute):
                continue
            method_name = func.attr.lower()
            if method_name not in _HTTP_METHODS and method_name != "route":
                continue
            path = _extract_str(dec.args[0]) if dec.args else None
            if not path:
                continue

            obj = ""
            if isinstance(func.value, ast.Name):
                obj = func.value.id.lower()

            if method_name == "route":
                methods = ["GET"]
                for kw in dec.keywords:
                    if kw.arg == "methods" and isinstance(kw.value, ast.List):
                        methods = [
                            e.value.upper()
                            for e in kw.value.elts
                            if isinstance(e, ast.Constant) and isinstance(e.value, str)
                        ]
                for m in methods:
                    results.append(ApiEndpoint(
                        method=m, path=path, handler=node.name,
                        file_path=file_node.path, line=node.lineno, framework="Flask",
                    ))
            elif method_name in ("ws", "websocket"):
                results.append(ApiEndpoint(
                    method="WS", path=path, handler=node.name,
                    file_path=file_node.path, line=node.lineno, framework="FastAPI/Flask",
                ))
            else:
                fw = "Flask" if obj in ("bp", "blueprint") else "FastAPI/Flask"
                results.append(ApiEndpoint(
                    method=method_name.upper(), path=path, handler=node.name,
                    file_path=file_node.path, line=node.lineno, framework=fw,
                ))
    return results


def _py_dtos(file_node: FileNode) -> list[DtoModel]:
    if not file_node.content:
        return []
    try:
        tree = ast.parse(file_node.content)
    except SyntaxError:
        return []

    results: list[DtoModel] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        base_names = set()
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_names.add(base.id)
            elif isinstance(base, ast.Attribute):
                base_names.add(base.attr)

        kind: Optional[str] = None
        if "BaseModel" in base_names:
            kind = "pydantic"
        elif "TypedDict" in base_names:
            kind = "typeddict"

        if not kind:
            for dec in node.decorator_list:
                if isinstance(dec, ast.Name) and dec.id == "dataclass":
                    kind = "dataclass"
                elif isinstance(dec, ast.Attribute) and dec.attr == "dataclass":
                    kind = "dataclass"

        if not kind:
            continue

        fields: list[DtoField] = []
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                fname = item.target.id
                if fname.startswith("_"):
                    continue
                try:
                    hint = ast.unparse(item.annotation)
                except Exception:
                    hint = "?"
                fields.append(DtoField(name=fname, type_hint=hint))

        results.append(DtoModel(
            name=node.name, file_path=file_node.path,
            line=node.lineno, fields=fields, kind=kind,
        ))
    return results


# ── TypeScript / JavaScript ───────────────────────────────────────────────────

_TS_EXPRESS_RE = re.compile(
    r"""(?:router|app|Router)\s*\.\s*(get|post|put|delete|patch|use)\s*\(\s*['"`]([^'"`\n]+)['"`]""",
    re.IGNORECASE | re.MULTILINE,
)
_TS_NEST_RE = re.compile(
    r"""@(Get|Post|Put|Delete|Patch|All|MessagePattern)\s*\(\s*['"`]([^'"`\n]*)['"`]\s*\)""",
    re.MULTILINE,
)
_TS_HANDLER_RE = re.compile(r"""(?:async\s+)?(\w+)\s*\(""")
_TS_INTERFACE_RE = re.compile(r"""interface\s+(\w+)\s*(?:extends\s+[^{]+)?\{([^}]*)\}""", re.DOTALL)
_TS_TYPE_OBJ_RE = re.compile(r"""type\s+(\w+)\s*=\s*\{([^}]*)\}""", re.DOTALL)
_TS_FIELD_RE = re.compile(r"""^\s*(?:readonly\s+)?(\w+)\??\s*:\s*([^\n;,]+)""", re.MULTILINE)


def _ts_endpoints(file_node: FileNode) -> list[ApiEndpoint]:
    if not file_node.content:
        return []
    content = file_node.content
    results: list[ApiEndpoint] = []

    for m in _TS_EXPRESS_RE.finditer(content):
        method = m.group(1).upper()
        if method == "USE":
            method = "ANY"
        path = m.group(2)
        line = content[: m.start()].count("\n") + 1
        after = content[m.end() :]
        hm = _TS_HANDLER_RE.search(after[:200])
        handler = hm.group(1) if hm else "anonymous"
        results.append(ApiEndpoint(
            method=method, path=path, handler=handler,
            file_path=file_node.path, line=line, framework="Express",
        ))

    for m in _TS_NEST_RE.finditer(content):
        method = m.group(1).upper()
        if method == "MESSAGEPATTERN":
            method = "MSG"
        path = m.group(2) or "/"
        line = content[: m.start()].count("\n") + 1
        after = content[m.end() :]
        hm = _TS_HANDLER_RE.search(after[:300])
        handler = hm.group(1) if hm else "unknown"
        results.append(ApiEndpoint(
            method=method, path=path, handler=handler,
            file_path=file_node.path, line=line, framework="NestJS",
        ))

    return results


def _ts_dtos(file_node: FileNode) -> list[DtoModel]:
    if not file_node.content:
        return []
    content = file_node.content
    results: list[DtoModel] = []

    for m in _TS_INTERFACE_RE.finditer(content):
        name, body = m.group(1), m.group(2)
        line = content[: m.start()].count("\n") + 1
        fields = [
            DtoField(name=fm.group(1), type_hint=fm.group(2).strip().rstrip(",;"))
            for fm in _TS_FIELD_RE.finditer(body)
            if not fm.group(1).startswith("//")
        ]
        results.append(DtoModel(name=name, file_path=file_node.path, line=line, fields=fields, kind="interface"))

    for m in _TS_TYPE_OBJ_RE.finditer(content):
        name, body = m.group(1), m.group(2)
        line = content[: m.start()].count("\n") + 1
        fields = [
            DtoField(name=fm.group(1), type_hint=fm.group(2).strip().rstrip(",;"))
            for fm in _TS_FIELD_RE.finditer(body)
            if not fm.group(1).startswith("//")
        ]
        if fields:
            results.append(DtoModel(name=name, file_path=file_node.path, line=line, fields=fields, kind="type"))

    return results


# ── Go ────────────────────────────────────────────────────────────────────────

_GO_ROUTE_RE = re.compile(
    r"""\w+\s*\.\s*(GET|POST|PUT|DELETE|PATCH|Any|Handle|HandleFunc)\s*\(\s*"([^"]*)"\s*,\s*(\w+)""",
    re.IGNORECASE,
)
_GO_HTTP_HANDLE_RE = re.compile(r"""http\s*\.\s*HandleFunc\s*\(\s*"([^"]+)"\s*,\s*(\w+)""")
_GO_STRUCT_RE = re.compile(r"""type\s+(\w+)\s+struct\s*\{([^}]+)\}""", re.DOTALL)
_GO_FIELD_RE = re.compile(r"""^\s+(\w+)\s+([\w\[\]*\.]+)\s*(?:`[^`]*json:"([^",]*)[^`]*`)?""", re.MULTILINE)


def _go_endpoints(file_node: FileNode) -> list[ApiEndpoint]:
    if not file_node.content:
        return []
    content = file_node.content
    results: list[ApiEndpoint] = []

    for m in _GO_ROUTE_RE.finditer(content):
        method = m.group(1).upper()
        if method in ("HANDLE", "HANDLEFUNC"):
            method = "ANY"
        path, handler = m.group(2) or "/", m.group(3)
        line = content[: m.start()].count("\n") + 1
        results.append(ApiEndpoint(
            method=method, path=path, handler=handler,
            file_path=file_node.path, line=line, framework="Gin/Echo/Chi",
        ))

    for m in _GO_HTTP_HANDLE_RE.finditer(content):
        path, handler = m.group(1), m.group(2)
        line = content[: m.start()].count("\n") + 1
        results.append(ApiEndpoint(
            method="ANY", path=path, handler=handler,
            file_path=file_node.path, line=line, framework="net/http",
        ))

    return results


def _go_dtos(file_node: FileNode) -> list[DtoModel]:
    if not file_node.content:
        return []
    content = file_node.content
    results: list[DtoModel] = []

    for m in _GO_STRUCT_RE.finditer(content):
        name, body = m.group(1), m.group(2)
        if 'json:"' not in body:
            continue
        fields: list[DtoField] = []
        for fm in _GO_FIELD_RE.finditer(body):
            json_name = fm.group(3) or fm.group(1)
            if json_name and json_name != "-":
                fields.append(DtoField(name=json_name, type_hint=fm.group(2)))
        line = content[: m.start()].count("\n") + 1
        results.append(DtoModel(name=name, file_path=file_node.path, line=line, fields=fields, kind="struct"))

    return results


# ── Rust ──────────────────────────────────────────────────────────────────────

_RUST_ATTR_RE = re.compile(
    r"""#\[(get|post|put|delete|patch)\s*\(\s*"([^"]+)"\s*\)\]\s*(?:#\[[^\]]+\]\s*)*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)""",
    re.IGNORECASE | re.DOTALL,
)
_RUST_AXUM_RE = re.compile(r"""\.route\s*\(\s*"([^"]+)"\s*,\s*(?:get|post|put|delete|patch)\s*\((\w+)\)""")
_RUST_SERDE_RE = re.compile(
    r"""#\[derive\([^\]]*(?:Serialize|Deserialize)[^\]]*\)\]\s*(?:#\[[^\]]+\]\s*)*(?:pub\s+)?struct\s+(\w+)\s*\{([^}]*)\}""",
    re.DOTALL,
)
_RUST_FIELD_RE = re.compile(r"""(?:pub\s+)?(\w+)\s*:\s*([\w<>\[\]&:,\s]+?)\s*[,\n}]""")


def _rust_endpoints(file_node: FileNode) -> list[ApiEndpoint]:
    if not file_node.content:
        return []
    content = file_node.content
    results: list[ApiEndpoint] = []

    for m in _RUST_ATTR_RE.finditer(content):
        method, path, handler = m.group(1).upper(), m.group(2), m.group(3)
        line = content[: m.start()].count("\n") + 1
        results.append(ApiEndpoint(
            method=method, path=path, handler=handler,
            file_path=file_node.path, line=line, framework="actix-web",
        ))

    for m in _RUST_AXUM_RE.finditer(content):
        path, handler = m.group(1), m.group(2)
        line = content[: m.start()].count("\n") + 1
        results.append(ApiEndpoint(
            method="ANY", path=path, handler=handler,
            file_path=file_node.path, line=line, framework="axum",
        ))

    return results


def _rust_dtos(file_node: FileNode) -> list[DtoModel]:
    if not file_node.content:
        return []
    content = file_node.content
    results: list[DtoModel] = []

    for m in _RUST_SERDE_RE.finditer(content):
        name, body = m.group(1), m.group(2)
        line = content[: m.start()].count("\n") + 1
        fields = [
            DtoField(name=fm.group(1), type_hint=fm.group(2).strip())
            for fm in _RUST_FIELD_RE.finditer(body)
            if not fm.group(1).startswith("_")
        ]
        results.append(DtoModel(name=name, file_path=file_node.path, line=line, fields=fields, kind="struct"))

    return results


# ── Public API ────────────────────────────────────────────────────────────────

def scan_all(files: list[FileNode]) -> tuple[list[ApiEndpoint], list[DtoModel]]:
    all_endpoints: list[ApiEndpoint] = []
    all_dtos: list[DtoModel] = []

    _ep = {
        "python": _py_endpoints,
        "javascript": _ts_endpoints,
        "typescript": _ts_endpoints,
        "go": _go_endpoints,
        "rust": _rust_endpoints,
    }
    _dto = {
        "python": _py_dtos,
        "javascript": _ts_dtos,
        "typescript": _ts_dtos,
        "go": _go_dtos,
        "rust": _rust_dtos,
    }

    for fn in files:
        ep_fn = _ep.get(fn.language)
        dto_fn = _dto.get(fn.language)
        if ep_fn:
            all_endpoints.extend(ep_fn(fn))
        if dto_fn:
            all_dtos.extend(dto_fn(fn))

    return all_endpoints, all_dtos
