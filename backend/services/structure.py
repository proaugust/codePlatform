from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.core.config import settings

SKIP_DIR_NAMES = frozenset(
    {
        "docs",
        ".git",
        "target",
        "build",
        "node_modules",
        ".idea",
        ".vscode",
        "__pycache__",
        "vendor",
    }
)

JAVA_MAPPING_RE = re.compile(
    r"@(RequestMapping|GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping)"
    r"(?:\s*\(([^)]*)\))?",
    re.MULTILINE,
)
JAVA_CLASS_RE = re.compile(r"\b(?:public\s+)?(?:@\w+(?:\([^)]*\))?\s+)*class\s+(\w+)")
JAVA_PACKAGE_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)
POM_DEP_RE = re.compile(
    r"<dependency>\s*<groupId>([^<]+)</groupId>\s*<artifactId>([^<]+)</artifactId>",
    re.DOTALL,
)
POM_PARENT_RE = re.compile(
    r"<parent>.*?<artifactId>([^<]+)</artifactId>.*?<version>([^<]+)</version>",
    re.DOTALL,
)
GO_HANDLE_RE = re.compile(
    r"""(?:\.HandleFunc|\.Handle)\(\s*["']([^"']+)["']"""
)
GO_METHOD_PATH_RE = re.compile(
    r"""(?:http\.(?:HandleFunc|Handle)|mux\.Handle(?:Func)?)\(\s*["']([^"']+)["']"""
)


@dataclass
class StructureScan:
    lang: str
    root: str
    has_code: bool = False
    build: dict[str, Any] = field(default_factory=dict)
    jpa: dict[str, Any] = field(default_factory=dict)
    layers: dict[str, list[str]] = field(default_factory=dict)
    apis: list[dict[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "lang": self.lang,
            "root": self.root,
            "has_code": self.has_code,
            "build": self.build,
            "jpa": self.jpa,
            "layers": {k: v for k, v in self.layers.items() if k != "_tree"},
            "tree": list(self.layers.get("_tree") or [])[:80],
            "apis": self.apis,
            "notes": self.notes,
        }

    def to_markdown(self) -> str:
        lines: list[str] = [
            f"# 工程结构（{self.lang}）",
            "",
            f"- 扫描根目录：`{self.root}`",
            f"- 是否存在代码：{'是' if self.has_code else '否（空工程 / 仅 docs）'}",
            "",
        ]
        if self.lang == "java":
            lines.extend(self._md_java_build())
            lines.extend(self._md_jpa())
            lines.extend(self._md_layers())
            lines.extend(self._md_apis())
        else:
            lines.extend(self._md_go_build())
            lines.extend(self._md_layers())
            lines.extend(self._md_apis())
        if self.notes:
            lines.append("## 备注")
            lines.append("")
            for n in self.notes:
                lines.append(f"- {n}")
            lines.append("")
        return "\n".join(lines)

    def _md_java_build(self) -> list[str]:
        out = ["## 构建（pom.xml）", ""]
        pom = self.build.get("pom")
        if not pom:
            out.append("- 未找到 `pom.xml`")
            out.append("")
            return out
        out.append(f"- 路径：`{pom.get('path', 'pom.xml')}`")
        if pom.get("parent"):
            out.append(f"- parent：`{pom['parent']}`")
        deps = pom.get("key_deps") or []
        if deps:
            out.append("- 关键依赖：")
            for d in deps:
                out.append(f"  - `{d}`")
        else:
            out.append("- 关键依赖：无（未识别到 spring / jpa 相关）")
        out.append("")
        return out

    def _md_go_build(self) -> list[str]:
        out = ["## 构建（go.mod）", ""]
        mod = self.build.get("go_mod")
        if not mod:
            out.append("- 未找到 `go.mod`")
            out.append("")
            return out
        out.append(f"- 路径：`{mod.get('path', 'go.mod')}`")
        if mod.get("module"):
            out.append(f"- module：`{mod['module']}`")
        if mod.get("go"):
            out.append(f"- go：`{mod['go']}`")
        out.append("")
        return out

    def _md_jpa(self) -> list[str]:
        out = ["## JPA", ""]
        j = self.jpa
        out.append(f"- 依赖启用：{'是' if j.get('dependency') else '否'}")
        entities = j.get("entities") or []
        repos = j.get("repositories") or []
        cfg = j.get("config_hints") or []
        if entities:
            out.append("- Entity：")
            for p in entities:
                out.append(f"  - `{p}`")
        else:
            out.append("- Entity：无")
        if repos:
            out.append("- Repository：")
            for p in repos:
                out.append(f"  - `{p}`")
        else:
            out.append("- Repository：无")
        if cfg:
            out.append("- 配置线索：")
            for c in cfg:
                out.append(f"  - `{c}`")
        out.append("")
        return out

    def _md_layers(self) -> list[str]:
        out = ["## 三层路径", ""]
        order = ("controller", "service", "repository") if self.lang == "java" else ("handler", "service", "repository")
        labels = {
            "controller": "Controller",
            "handler": "Handler",
            "service": "Service",
            "repository": "Repository",
        }
        any_hit = False
        for key in order:
            files = self.layers.get(key) or []
            out.append(f"### {labels[key]}")
            out.append("")
            if files:
                any_hit = True
                for p in files:
                    out.append(f"- `{p}`")
            else:
                out.append("- （无）")
            out.append("")
        if not any_hit:
            out.append("> 未按命名约定识别到三层目录/类；见下方文件树摘要。")
            out.append("")
        tree = self.layers.get("_tree") or []
        if tree:
            out.append("### 源码路径摘要")
            out.append("")
            for p in tree[:80]:
                out.append(f"- `{p}`")
            if len(tree) > 80:
                out.append(f"- … 另有 {len(tree) - 80} 个文件")
            out.append("")
        return out

    def _md_apis(self) -> list[str]:
        out = ["## API 面", ""]
        if not self.apis:
            out.append("- 未解析到映射")
            out.append("")
            return out
        for api in self.apis:
            method = api.get("method") or "*"
            path = api.get("path") or "?"
            src = api.get("source") or ""
            out.append(f"- `{method} {path}` — `{src}`")
        out.append("")
        return out


def _iter_source_files(root: Path) -> list[Path]:
    files: list[Path] = []
    if not root.is_dir():
        return files
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        files.append(path)
    return files


def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _read_text(path: Path, limit: int = 200_000) -> str:
    try:
        data = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        data = path.read_text(encoding="utf-8", errors="ignore")
    if len(data) > limit:
        return data[:limit]
    return data


def _parse_pom(root: Path) -> dict[str, Any] | None:
    pom = root / "pom.xml"
    if not pom.is_file():
        found = next((p for p in root.rglob("pom.xml") if "docs" not in p.parts), None)
        pom = found if found else pom
    if not pom.is_file():
        return None
    text = _read_text(pom)
    parent_m = POM_PARENT_RE.search(text)
    parent = ""
    if parent_m:
        parent = f"{parent_m.group(1)}:{parent_m.group(2)}"
    key_deps: list[str] = []
    for g, a in POM_DEP_RE.findall(text):
        ga = f"{g.strip()}:{a.strip()}"
        low = ga.lower()
        if "spring" in low or "jpa" in low or "h2" in low or "mybatis" in low:
            key_deps.append(ga)
    return {"path": _rel(root, pom), "parent": parent, "key_deps": sorted(set(key_deps))}


def _parse_go_mod(root: Path) -> dict[str, Any] | None:
    gom = root / "go.mod"
    if not gom.is_file():
        return None
    text = _read_text(gom)
    module = ""
    go_ver = ""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("module "):
            module = s[7:].strip()
        elif s.startswith("go "):
            go_ver = s[3:].strip()
    return {"path": "go.mod", "module": module, "go": go_ver}


def _java_layer_key(rel: str, text: str) -> str | None:
    low = rel.lower().replace("\\", "/")
    name = Path(rel).stem
    if "/controller/" in f"/{low}" or name.endswith("Controller") or "@RestController" in text or "@Controller" in text:
        return "controller"
    if "/service/" in f"/{low}" or name.endswith("Service") or name.endswith("ServiceImpl"):
        return "service"
    if (
        "/repository/" in f"/{low}"
        or "/repo/" in f"/{low}"
        or name.endswith("Repository")
        or "JpaRepository" in text
        or "CrudRepository" in text
    ):
        return "repository"
    return None


def _go_layer_key(rel: str) -> str | None:
    low = rel.lower().replace("\\", "/")
    name = Path(rel).stem.lower()
    if "/handler" in f"/{low}" or name.endswith("handler") or "/api/" in f"/{low}":
        return "handler"
    if "/service" in f"/{low}" or name.endswith("service"):
        return "service"
    if "/repository" in f"/{low}" or "/repo/" in f"/{low}" or name.endswith("repository") or name.endswith("repo"):
        return "repository"
    return None


def _extract_java_mappings(rel: str, text: str) -> list[dict[str, str]]:
    if "@RestController" not in text and "@Controller" not in text and "Controller" not in Path(rel).stem:
        # still allow files with RequestMapping
        if "@RequestMapping" not in text and "@GetMapping" not in text:
            return []

    class_m = JAVA_CLASS_RE.search(text)
    class_name = class_m.group(1) if class_m else Path(rel).stem
    pkg_m = JAVA_PACKAGE_RE.search(text)
    source = f"{pkg_m.group(1)}.{class_name}" if pkg_m else class_name

    # class-level RequestMapping
    class_base = ""
    for m in JAVA_MAPPING_RE.finditer(text):
        ann, raw = m.group(1), (m.group(2) or "").strip()
        # crude: first RequestMapping before class body used as base — take first RequestMapping with path
        if ann == "RequestMapping" and raw and not class_base:
            class_base = _normalize_path_literal(raw)
            break
    # better: find RequestMapping immediately preceding class
    before_class = text[: class_m.start()] if class_m else text[:800]
    bases = []
    for m in JAVA_MAPPING_RE.finditer(before_class):
        if m.group(1) == "RequestMapping":
            bases.append(_normalize_path_literal(m.group(2) or ""))
    if bases:
        class_base = bases[-1]

    method_map = {
        "GetMapping": "GET",
        "PostMapping": "POST",
        "PutMapping": "PUT",
        "DeleteMapping": "DELETE",
        "PatchMapping": "PATCH",
        "RequestMapping": "*",
    }
    apis: list[dict[str, str]] = []
    # method-level: scan whole file, skip the class-level one by requiring annotations inside class roughly
    body = text[class_m.end() :] if class_m else text
    for m in JAVA_MAPPING_RE.finditer(body):
        ann = m.group(1)
        raw = (m.group(2) or "").strip()
        path = _join_paths(class_base, _normalize_path_literal(raw) if raw else "")
        method = method_map.get(ann, "*")
        if ann == "RequestMapping" and not raw and path == (class_base or "/"):
            continue
        apis.append({"method": method, "path": path or "/", "source": f"{source} (@{ann})"})
    return apis


def _normalize_path_literal(raw: str) -> str:
    raw = raw.strip()
    # take first quoted string if present
    qm = re.search(r'["\']([^"\']*)["\']', raw)
    if qm:
        p = qm.group(1).strip()
    else:
        p = raw.split(",")[0].strip().strip("\"'")
    if not p:
        return ""
    if not p.startswith("/"):
        p = "/" + p
    return p.rstrip("/") or "/"


def _join_paths(base: str, child: str) -> str:
    b = (base or "").rstrip("/")
    c = (child or "").strip()
    if not c or c == "/":
        return b or "/"
    if not c.startswith("/"):
        c = "/" + c
    if not b:
        return c
    return (b + c).replace("//", "/")


def _scan_java_jpa(root: Path, files: list[Path], pom: dict[str, Any] | None) -> dict[str, Any]:
    dep = False
    if pom:
        dep = any("jpa" in d.lower() for d in pom.get("key_deps") or [])
        if pom.get("parent") and "spring-boot" in (pom.get("parent") or "").lower():
            pass
    entities: list[str] = []
    repos: list[str] = []
    cfg: list[str] = []
    for path in files:
        rel = _rel(root, path)
        if path.suffix.lower() not in {".java", ".yml", ".yaml", ".properties"}:
            continue
        text = _read_text(path)
        low = text.lower()
        if path.suffix == ".java":
            if "@Entity" in text:
                entities.append(rel)
            if "JpaRepository" in text or "CrudRepository" in text or rel.endswith("Repository.java"):
                repos.append(rel)
            if "spring-boot-starter-data-jpa" in text:
                dep = True
        else:
            if "jpa." in low or "hibernate" in low or "ddl-auto" in low:
                for line in text.splitlines():
                    s = line.strip()
                    if not s or s.startswith("#"):
                        continue
                    if "jpa" in s.lower() or "hibernate" in s.lower() or "datasource" in s.lower():
                        cfg.append(f"{rel}: {s}")
                        if len(cfg) >= 12:
                            break
        if "data-jpa" in low or "springframework.boot.autoconfigure.orm.jpa" in low:
            dep = True
    return {
        "dependency": dep,
        "entities": sorted(set(entities)),
        "repositories": sorted(set(repos)),
        "config_hints": cfg,
    }


def _scan_java(root: Path) -> StructureScan:
    scan = StructureScan(lang="java", root=str(root))
    files = _iter_source_files(root)
    code_files = [p for p in files if p.suffix.lower() in {".java", ".xml", ".yml", ".yaml", ".properties"}]
    # exclude empty-ish: only .gitkeep
    scan.has_code = any(p.name != ".gitkeep" for p in files)
    pom = _parse_pom(root)
    if pom:
        scan.build["pom"] = pom
    else:
        scan.notes.append("缺少 pom.xml")

    layers: dict[str, list[str]] = {"controller": [], "service": [], "repository": [], "_tree": []}
    apis: list[dict[str, str]] = []
    for path in code_files:
        rel = _rel(root, path)
        if path.suffix.lower() == ".java":
            layers["_tree"].append(rel)
            text = _read_text(path)
            key = _java_layer_key(rel, text)
            if key:
                layers[key].append(rel)
            apis.extend(_extract_java_mappings(rel, text))
        elif path.name in {"application.yml", "application.yaml", "application.properties"} or path.name.startswith(
            "application-"
        ):
            layers["_tree"].append(rel)

    for k in ("controller", "service", "repository"):
        layers[k] = sorted(set(layers[k]))
    layers["_tree"] = sorted(set(layers["_tree"]))
    scan.layers = layers
    scan.apis = apis
    scan.jpa = _scan_java_jpa(root, code_files, pom)
    if scan.has_code and not layers["controller"] and not apis:
        scan.notes.append("未识别到 Controller / RequestMapping，可能尚未生成或命名不规范")
    return scan


def _scan_go(root: Path) -> StructureScan:
    scan = StructureScan(lang="go", root=str(root))
    files = _iter_source_files(root)
    go_files = [p for p in files if p.suffix.lower() == ".go"]
    scan.has_code = any(p.name != ".gitkeep" for p in files)
    mod = _parse_go_mod(root)
    if mod:
        scan.build["go_mod"] = mod
    else:
        if scan.has_code:
            scan.notes.append("缺少 go.mod")

    layers: dict[str, list[str]] = {"handler": [], "service": [], "repository": [], "_tree": []}
    apis: list[dict[str, str]] = []
    for path in go_files:
        rel = _rel(root, path)
        layers["_tree"].append(rel)
        text = _read_text(path)
        key = _go_layer_key(rel)
        if key:
            layers[key].append(rel)
        for m in GO_HANDLE_RE.finditer(text):
            apis.append({"method": "*", "path": m.group(1), "source": rel})
        for m in GO_METHOD_PATH_RE.finditer(text):
            path_s = m.group(1)
            if not any(a["path"] == path_s and a["source"] == rel for a in apis):
                apis.append({"method": "*", "path": path_s, "source": rel})
        # method + path string pairs like `"GET /health"`
        for m in re.finditer(r'["\'](GET|POST|PUT|DELETE|PATCH)\s+(/[^"\']*)["\']', text):
            apis.append({"method": m.group(1), "path": m.group(2), "source": rel})

    for k in ("handler", "service", "repository"):
        layers[k] = sorted(set(layers[k]))
    layers["_tree"] = sorted(set(layers["_tree"]))
    scan.layers = layers
    # dedupe apis
    seen: set[tuple[str, str, str]] = set()
    uniq: list[dict[str, str]] = []
    for a in apis:
        key_t = (a.get("method", ""), a.get("path", ""), a.get("source", ""))
        if key_t in seen:
            continue
        seen.add(key_t)
        uniq.append(a)
    scan.apis = uniq
    return scan


def scan_project(lang: str) -> StructureScan:
    """只认 auto_code/{java|go}，不接受外部路径。"""
    lang = lang.lower().strip()
    if lang not in {"java", "go"}:
        raise ValueError(f"不支持的语言: {lang}")
    root = settings.auto_code_dir(lang)
    root.mkdir(parents=True, exist_ok=True)
    if lang == "java":
        return _scan_java(root)
    return _scan_go(root)


def write_structure_doc(lang: str) -> dict[str, str]:
    """扫描并写入 auto_code/{lang}/docs/05-structure.md。"""
    scan = scan_project(lang)
    out_dir = settings.auto_code_dir(lang) / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = "05-structure.md"
    body = scan.to_markdown()
    if not body.endswith("\n"):
        body += "\n"
    path = out_dir / filename
    path.write_text(body, encoding="utf-8", newline="\n")
    return {
        "key": "structure",
        "title": "工程结构",
        "path": f"docs/{filename}",
        "content": body,
        "has_code": "true" if scan.has_code else "false",
    }
