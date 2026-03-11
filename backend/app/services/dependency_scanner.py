from __future__ import annotations

import json
import logging
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from xml.etree import ElementTree

import httpx
from git import Repo as GitRepo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models.dependency import (
    DependencyFinding,
    DepFindingSeverity,
    DepFindingStatus,
    DepScanRun,
)

if TYPE_CHECKING:
    from app.services.sync_logger import SyncLogger

logger = logging.getLogger(__name__)

OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"
OSV_BATCH_SIZE = 1000

ECOSYSTEM_REGISTRY: dict[str, str] = {
    "PyPI": "https://pypi.org/pypi/{name}/json",
    "npm": "https://registry.npmjs.org/{name}/latest",
    "crates.io": "https://crates.io/api/v1/crates/{name}",
    "Go": "https://proxy.golang.org/{name}/@latest",
    "RubyGems": "https://rubygems.org/api/v1/gems/{name}.json",
    "NuGet": "https://api.nuget.org/v3-flatcontainer/{name}/index.json",
    "Maven": "https://search.maven.org/solrsearch/select?q=g:{group}+AND+a:{artifact}&rows=1&wt=json",
}

DEPENDENCY_FILE_PATTERNS: dict[str, tuple[str, str]] = {
    "requirements.txt": ("requirements_txt", "PyPI"),
    "requirements-*.txt": ("requirements_txt", "PyPI"),
    "requirements/*.txt": ("requirements_txt", "PyPI"),
    "Pipfile": ("pipfile", "PyPI"),
    "pyproject.toml": ("pyproject_toml", "PyPI"),
    "setup.cfg": ("setup_cfg", "PyPI"),
    "package.json": ("package_json", "npm"),
    "pnpm-lock.yaml": ("pnpm_lock", "npm"),
    "yarn.lock": ("yarn_lock", "npm"),
    "go.mod": ("go_mod", "Go"),
    "Cargo.toml": ("cargo_toml", "crates.io"),
    "Gemfile": ("gemfile", "RubyGems"),
    "pom.xml": ("pom_xml", "Maven"),
    "build.gradle": ("build_gradle", "Maven"),
    "build.gradle.kts": ("build_gradle_kts", "Maven"),
    "*.csproj": ("csproj", "NuGet"),
    "packages.config": ("packages_config", "NuGet"),
    "Dockerfile": ("dockerfile", "Docker"),
    "Dockerfile.*": ("dockerfile", "Docker"),
    "docker-compose.yml": ("docker_compose", "Docker"),
    "docker-compose.yaml": ("docker_compose", "Docker"),
    "docker-compose.*.yml": ("docker_compose", "Docker"),
    "docker-compose.*.yaml": ("docker_compose", "Docker"),
    "compose.yml": ("docker_compose", "Docker"),
    "compose.yaml": ("docker_compose", "Docker"),
}

OSV_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


@dataclass
class ParsedDep:
    name: str
    version: str | None
    is_direct: bool = True


@dataclass
class VulnInfo:
    vuln_id: str
    summary: str
    severity: str
    fixed_version: str | None
    url: str


@dataclass
class DepFileResult:
    file_path: str
    file_type: str
    ecosystem: str
    packages: list[ParsedDep] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Worktree helpers (shared pattern with sast_scanner)
# ---------------------------------------------------------------------------

def _prepare_worktree(bare_repo_path: str) -> str:
    worktree_dir = tempfile.mkdtemp(prefix="contributr_dep_")
    try:
        git_repo = GitRepo(bare_repo_path)
        git_repo.git.worktree("add", "--detach", worktree_dir, "HEAD")
        return worktree_dir
    except Exception:
        shutil.rmtree(worktree_dir, ignore_errors=True)
        raise


def _cleanup_worktree(bare_repo_path: str, worktree_dir: str) -> None:
    try:
        git_repo = GitRepo(bare_repo_path)
        git_repo.git.worktree("remove", "-f", worktree_dir)
    except Exception:
        logger.warning("git worktree remove failed, falling back to rm", exc_info=True)
    shutil.rmtree(worktree_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def _matches_pattern(filename: str, pattern: str) -> bool:
    if "*" not in pattern:
        return filename == pattern
    regex = re.escape(pattern).replace(r"\*", ".*")
    return bool(re.fullmatch(regex, filename))


def discover_dependency_files(worktree_path: str) -> list[DepFileResult]:
    results: list[DepFileResult] = []
    worktree = Path(worktree_path)

    for root, _dirs, files in os.walk(worktree):
        rel_root = Path(root).relative_to(worktree)
        if any(part.startswith(".") for part in rel_root.parts):
            continue
        if "node_modules" in rel_root.parts or "vendor" in rel_root.parts:
            continue

        for fname in files:
            for pattern, (file_type, ecosystem) in DEPENDENCY_FILE_PATTERNS.items():
                if "/" in pattern:
                    full_rel = str(rel_root / fname)
                    if _matches_pattern(full_rel, pattern):
                        full_path = str(Path(root) / fname)
                        results.append(DepFileResult(
                            file_path=str(rel_root / fname),
                            file_type=file_type,
                            ecosystem=ecosystem,
                        ))
                        break
                elif _matches_pattern(fname, pattern):
                    results.append(DepFileResult(
                        file_path=str(rel_root / fname) if str(rel_root) != "." else fname,
                        file_type=file_type,
                        ecosystem=ecosystem,
                    ))
                    break

    return results


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _safe_read(filepath: str) -> str:
    try:
        return Path(filepath).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def parse_requirements_txt(filepath: str) -> list[ParsedDep]:
    deps: list[ParsedDep] = []
    content = _safe_read(filepath)
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        match = re.match(r"^([A-Za-z0-9_][A-Za-z0-9._-]*)\s*(?:\[.*?\])?\s*(==|>=|<=|~=|!=|>|<)\s*([^\s,;#]+)", line)
        if match:
            deps.append(ParsedDep(name=match.group(1).lower(), version=match.group(3)))
        else:
            name_match = re.match(r"^([A-Za-z0-9_][A-Za-z0-9._-]*)", line)
            if name_match:
                deps.append(ParsedDep(name=name_match.group(1).lower(), version=None))
    return deps


def parse_pyproject_toml(filepath: str) -> list[ParsedDep]:
    deps: list[ParsedDep] = []
    content = _safe_read(filepath)
    if not content:
        return deps

    in_deps_section = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped in ("dependencies = [", "[project.dependencies]", "[tool.poetry.dependencies]"):
            in_deps_section = True
            continue
        if in_deps_section:
            if stripped == "]" or (stripped.startswith("[") and not stripped.startswith("[")):
                in_deps_section = False
                continue
            match = re.search(r""""([A-Za-z0-9_][A-Za-z0-9._-]*)(?:\[.*?\])?\s*(?:(==|>=|~=|<=|!=|>|<)\s*([^"',\s]+))?""", stripped)
            if match:
                deps.append(ParsedDep(name=match.group(1).lower(), version=match.group(3)))
            else:
                kv_match = re.match(r"""^([A-Za-z0-9_][A-Za-z0-9._-]*)\s*=\s*["{]?\s*(?:version\s*=\s*)?[">~=!<]*\s*([0-9][^"'}, ]*)?""", stripped)
                if kv_match:
                    deps.append(ParsedDep(name=kv_match.group(1).lower(), version=kv_match.group(2)))
    return deps


def parse_pipfile(filepath: str) -> list[ParsedDep]:
    deps: list[ParsedDep] = []
    content = _safe_read(filepath)
    in_packages = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped in ("[packages]", "[dev-packages]"):
            in_packages = True
            continue
        if stripped.startswith("[") and in_packages:
            in_packages = False
            continue
        if in_packages:
            match = re.match(r'^([A-Za-z0-9_][A-Za-z0-9._-]*)\s*=\s*"([=~><!]*\s*[0-9][^"]*)"', stripped)
            if match:
                ver = re.sub(r"^[=~><!]+\s*", "", match.group(2))
                deps.append(ParsedDep(name=match.group(1).lower(), version=ver))
            elif re.match(r'^([A-Za-z0-9_][A-Za-z0-9._-]*)\s*=', stripped):
                name = stripped.split("=")[0].strip()
                deps.append(ParsedDep(name=name.lower(), version=None))
    return deps


def parse_setup_cfg(filepath: str) -> list[ParsedDep]:
    deps: list[ParsedDep] = []
    content = _safe_read(filepath)
    in_install = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "install_requires =":
            in_install = True
            continue
        if in_install:
            if not stripped or (not stripped.startswith(" ") and not line.startswith("\t") and "=" in stripped):
                in_install = False
                continue
            match = re.match(r"([A-Za-z0-9_][A-Za-z0-9._-]*)(?:\[.*?\])?\s*(?:==|>=|~=)\s*([^\s,;]+)", stripped)
            if match:
                deps.append(ParsedDep(name=match.group(1).lower(), version=match.group(2)))
    return deps


def parse_package_json(filepath: str) -> list[ParsedDep]:
    deps: list[ParsedDep] = []
    content = _safe_read(filepath)
    if not content:
        return deps
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return deps
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        for name, ver_spec in (data.get(section) or {}).items():
            ver = re.sub(r"^[\^~>=<]+", "", str(ver_spec)).strip()
            is_direct = section == "dependencies"
            deps.append(ParsedDep(name=name, version=ver if ver else None, is_direct=is_direct))
    return deps


def parse_pnpm_lock(filepath: str) -> list[ParsedDep]:
    deps: list[ParsedDep] = []
    content = _safe_read(filepath)
    for match in re.finditer(r"'?/?([^@\s]+)@([^':\s]+)", content):
        name, version = match.group(1), match.group(2)
        if name and version and not name.startswith("/"):
            deps.append(ParsedDep(name=name, version=version, is_direct=False))
    seen: set[str] = set()
    unique: list[ParsedDep] = []
    for d in deps:
        if d.name not in seen:
            seen.add(d.name)
            unique.append(d)
    return unique


def parse_yarn_lock(filepath: str) -> list[ParsedDep]:
    deps: list[ParsedDep] = []
    content = _safe_read(filepath)
    current_name = None
    seen: set[str] = set()
    for line in content.splitlines():
        match = re.match(r'^"?(@?[^@\s"]+)@', line)
        if match:
            current_name = match.group(1)
        elif current_name and line.strip().startswith("version "):
            ver_match = re.search(r'"([^"]+)"', line)
            if ver_match and current_name not in seen:
                seen.add(current_name)
                deps.append(ParsedDep(name=current_name, version=ver_match.group(1), is_direct=False))
            current_name = None
    return deps


def parse_go_mod(filepath: str) -> list[ParsedDep]:
    deps: list[ParsedDep] = []
    content = _safe_read(filepath)
    in_require = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("require ("):
            in_require = True
            continue
        if in_require and stripped == ")":
            in_require = False
            continue
        if in_require or stripped.startswith("require "):
            dep_line = stripped.removeprefix("require ").strip()
            match = re.match(r"^(\S+)\s+(v\S+)", dep_line)
            if match:
                indirect = "// indirect" in line
                deps.append(ParsedDep(name=match.group(1), version=match.group(2), is_direct=not indirect))
    return deps


def parse_cargo_toml(filepath: str) -> list[ParsedDep]:
    deps: list[ParsedDep] = []
    content = _safe_read(filepath)
    in_deps = False
    for line in content.splitlines():
        stripped = line.strip()
        if re.match(r"^\[(.*dependencies.*)\]", stripped):
            in_deps = True
            continue
        if stripped.startswith("[") and in_deps:
            in_deps = False
            continue
        if in_deps:
            match = re.match(r'^([A-Za-z0-9_-]+)\s*=\s*"([^"]+)"', stripped)
            if match:
                deps.append(ParsedDep(name=match.group(1), version=match.group(2)))
            else:
                kv = re.match(r'^([A-Za-z0-9_-]+)\s*=\s*\{.*?version\s*=\s*"([^"]+)"', stripped)
                if kv:
                    deps.append(ParsedDep(name=kv.group(1), version=kv.group(2)))
    return deps


def parse_dockerfile(filepath: str) -> list[ParsedDep]:
    deps: list[ParsedDep] = []
    content = _safe_read(filepath)
    for match in re.finditer(r"^FROM\s+(?:--platform=\S+\s+)?(\S+?)(?::(\S+?))?(?:\s+(?:AS|as)\s+\S+)?$", content, re.MULTILINE):
        image = match.group(1)
        tag = match.group(2) or "latest"
        if image.lower() != "scratch":
            deps.append(ParsedDep(name=image, version=tag))
    return deps


def parse_docker_compose(filepath: str) -> list[ParsedDep]:
    deps: list[ParsedDep] = []
    content = _safe_read(filepath)
    for match in re.finditer(r"image:\s*['\"]?([^'\"\s:]+)(?::([^'\"\s]+))?", content):
        image = match.group(1)
        tag = match.group(2) or "latest"
        deps.append(ParsedDep(name=image, version=tag))
    return deps


def parse_gemfile(filepath: str) -> list[ParsedDep]:
    deps: list[ParsedDep] = []
    content = _safe_read(filepath)
    for match in re.finditer(r"gem\s+['\"]([^'\"]+)['\"]\s*(?:,\s*['\"]([~>=<!]*\s*[0-9][^'\"]*)['\"])?", content):
        ver = re.sub(r"^[~>=<!]+\s*", "", match.group(2)) if match.group(2) else None
        deps.append(ParsedDep(name=match.group(1), version=ver))
    return deps


def parse_pom_xml(filepath: str) -> list[ParsedDep]:
    deps: list[ParsedDep] = []
    content = _safe_read(filepath)
    if not content:
        return deps
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        return deps
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"
    for dep in root.iter(f"{ns}dependency"):
        gid = dep.findtext(f"{ns}groupId", "")
        aid = dep.findtext(f"{ns}artifactId", "")
        ver = dep.findtext(f"{ns}version", "")
        if gid and aid:
            name = f"{gid}:{aid}"
            ver_clean = ver if ver and not ver.startswith("$") else None
            deps.append(ParsedDep(name=name, version=ver_clean))
    return deps


def parse_gradle(filepath: str) -> list[ParsedDep]:
    deps: list[ParsedDep] = []
    content = _safe_read(filepath)
    for match in re.finditer(
        r"""(?:implementation|api|compile|runtimeOnly|testImplementation)\s*[\('"]+([^:'"]+):([^:'"]+):([^)'\"]+)""",
        content,
    ):
        name = f"{match.group(1)}:{match.group(2)}"
        deps.append(ParsedDep(name=name, version=match.group(3)))
    return deps


def parse_csproj(filepath: str) -> list[ParsedDep]:
    deps: list[ParsedDep] = []
    content = _safe_read(filepath)
    if not content:
        return deps
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        return deps
    for ref in root.iter("PackageReference"):
        name = ref.get("Include", "")
        version = ref.get("Version", "")
        if name:
            deps.append(ParsedDep(name=name, version=version or None))
    return deps


def parse_packages_config(filepath: str) -> list[ParsedDep]:
    deps: list[ParsedDep] = []
    content = _safe_read(filepath)
    if not content:
        return deps
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError:
        return deps
    for pkg in root.iter("package"):
        name = pkg.get("id", "")
        version = pkg.get("version", "")
        if name:
            deps.append(ParsedDep(name=name, version=version or None))
    return deps


PARSER_MAP: dict[str, callable] = {
    "requirements_txt": parse_requirements_txt,
    "pyproject_toml": parse_pyproject_toml,
    "pipfile": parse_pipfile,
    "setup_cfg": parse_setup_cfg,
    "package_json": parse_package_json,
    "pnpm_lock": parse_pnpm_lock,
    "yarn_lock": parse_yarn_lock,
    "go_mod": parse_go_mod,
    "cargo_toml": parse_cargo_toml,
    "dockerfile": parse_dockerfile,
    "docker_compose": parse_docker_compose,
    "gemfile": parse_gemfile,
    "pom_xml": parse_pom_xml,
    "build_gradle": parse_gradle,
    "build_gradle_kts": parse_gradle,
    "csproj": parse_csproj,
    "packages_config": parse_packages_config,
}


# ---------------------------------------------------------------------------
# OSV.dev vulnerability queries
# ---------------------------------------------------------------------------

def _osv_ecosystem_name(ecosystem: str) -> str | None:
    mapping = {
        "PyPI": "PyPI",
        "npm": "npm",
        "Go": "Go",
        "crates.io": "crates.io",
        "RubyGems": "RubyGems",
        "Maven": "Maven",
        "NuGet": "NuGet",
    }
    return mapping.get(ecosystem)


def _worst_severity_from_vulns(vulns: list[VulnInfo]) -> DepFindingSeverity:
    if not vulns:
        return DepFindingSeverity.NONE
    best = 999
    for v in vulns:
        rank = OSV_SEVERITY_ORDER.get(v.severity.upper(), 3)
        best = min(best, rank)
    reverse = {0: DepFindingSeverity.CRITICAL, 1: DepFindingSeverity.HIGH, 2: DepFindingSeverity.MEDIUM, 3: DepFindingSeverity.LOW}
    return reverse.get(best, DepFindingSeverity.LOW)


def _extract_severity_from_osv(vuln: dict) -> str:
    for sv in vuln.get("severity", []):
        score_str = sv.get("score", "")
        if sv.get("type") == "CVSS_V3" and score_str:
            try:
                score = float(score_str.split("/")[0]) if "/" in score_str else float(score_str)
            except (ValueError, IndexError):
                continue
            if score >= 9.0:
                return "CRITICAL"
            if score >= 7.0:
                return "HIGH"
            if score >= 4.0:
                return "MEDIUM"
            return "LOW"
    db_severity = vuln.get("database_specific", {}).get("severity", "")
    if db_severity:
        return db_severity.upper()
    return "MEDIUM"


def _extract_fixed_version(vuln: dict, package_name: str) -> str | None:
    for affected in vuln.get("affected", []):
        pkg = affected.get("package", {})
        if pkg.get("name", "").lower() == package_name.lower():
            for r in affected.get("ranges", []):
                for event in r.get("events", []):
                    if "fixed" in event:
                        return event["fixed"]
    return None


async def query_osv_batch(
    packages: list[tuple[str, str, str | None]],
) -> dict[tuple[str, str], list[VulnInfo]]:
    """Query OSV.dev for vulnerabilities. packages = [(ecosystem, name, version), ...]"""
    results: dict[tuple[str, str], list[VulnInfo]] = {}
    if not packages:
        return results

    queryable = []
    for eco, name, version in packages:
        osv_eco = _osv_ecosystem_name(eco)
        if osv_eco and version:
            queryable.append((eco, name, version, osv_eco))

    for batch_start in range(0, len(queryable), OSV_BATCH_SIZE):
        batch = queryable[batch_start : batch_start + OSV_BATCH_SIZE]
        queries = []
        for _eco, name, version, osv_eco in batch:
            queries.append({"version": version, "package": {"name": name, "ecosystem": osv_eco}})

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(OSV_BATCH_URL, json={"queries": queries})
                resp.raise_for_status()
                data = resp.json()
        except Exception:
            logger.warning("OSV batch query failed", exc_info=True)
            continue

        for i, result in enumerate(data.get("results", [])):
            eco, name, version, _ = batch[i]
            vulns_raw = result.get("vulns", [])
            if not vulns_raw:
                continue
            vuln_list: list[VulnInfo] = []
            for v in vulns_raw:
                vuln_list.append(VulnInfo(
                    vuln_id=v.get("id", ""),
                    summary=v.get("summary", v.get("details", ""))[:500],
                    severity=_extract_severity_from_osv(v),
                    fixed_version=_extract_fixed_version(v, name),
                    url=f"https://osv.dev/vulnerability/{v.get('id', '')}",
                ))
            results[(eco, name)] = vuln_list

    return results


# ---------------------------------------------------------------------------
# Latest version queries
# ---------------------------------------------------------------------------

async def _fetch_latest_pypi(client: httpx.AsyncClient, name: str) -> str | None:
    try:
        resp = await client.get(f"https://pypi.org/pypi/{name}/json", timeout=15)
        if resp.status_code == 200:
            return resp.json().get("info", {}).get("version")
    except Exception:
        pass
    return None


async def _fetch_latest_npm(client: httpx.AsyncClient, name: str) -> str | None:
    try:
        resp = await client.get(f"https://registry.npmjs.org/{name}/latest", timeout=15)
        if resp.status_code == 200:
            return resp.json().get("version")
    except Exception:
        pass
    return None


async def _fetch_latest_crates(client: httpx.AsyncClient, name: str) -> str | None:
    try:
        resp = await client.get(
            f"https://crates.io/api/v1/crates/{name}",
            headers={"User-Agent": "contributr-dep-scanner"},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("crate", {}).get("newest_version")
    except Exception:
        pass
    return None


async def _fetch_latest_go(client: httpx.AsyncClient, name: str) -> str | None:
    try:
        resp = await client.get(f"https://proxy.golang.org/{name}/@latest", timeout=15)
        if resp.status_code == 200:
            return resp.json().get("Version")
    except Exception:
        pass
    return None


async def _fetch_latest_rubygems(client: httpx.AsyncClient, name: str) -> str | None:
    try:
        resp = await client.get(f"https://rubygems.org/api/v1/gems/{name}.json", timeout=15)
        if resp.status_code == 200:
            return resp.json().get("version")
    except Exception:
        pass
    return None


async def _fetch_latest_nuget(client: httpx.AsyncClient, name: str) -> str | None:
    try:
        resp = await client.get(
            f"https://api.nuget.org/v3-flatcontainer/{name.lower()}/index.json",
            timeout=15,
        )
        if resp.status_code == 200:
            versions = resp.json().get("versions", [])
            if versions:
                return versions[-1]
    except Exception:
        pass
    return None


async def _fetch_latest_maven(client: httpx.AsyncClient, name: str) -> str | None:
    parts = name.split(":")
    if len(parts) != 2:
        return None
    group, artifact = parts
    try:
        resp = await client.get(
            f"https://search.maven.org/solrsearch/select?q=g:{group}+AND+a:{artifact}&rows=1&wt=json",
            timeout=15,
        )
        if resp.status_code == 200:
            docs = resp.json().get("response", {}).get("docs", [])
            if docs:
                return docs[0].get("latestVersion")
    except Exception:
        pass
    return None


_LATEST_FETCHERS: dict[str, callable] = {
    "PyPI": _fetch_latest_pypi,
    "npm": _fetch_latest_npm,
    "crates.io": _fetch_latest_crates,
    "Go": _fetch_latest_go,
    "RubyGems": _fetch_latest_rubygems,
    "NuGet": _fetch_latest_nuget,
    "Maven": _fetch_latest_maven,
}


async def query_latest_versions(
    packages: list[tuple[str, str]],
) -> dict[tuple[str, str], str]:
    """Fetch latest versions for [(ecosystem, name), ...]. Returns {(eco, name): version}."""
    import asyncio

    results: dict[tuple[str, str], str] = {}
    if not packages:
        return results

    async with httpx.AsyncClient() as client:
        sem = asyncio.Semaphore(20)

        async def _fetch(eco: str, name: str) -> None:
            fetcher = _LATEST_FETCHERS.get(eco)
            if not fetcher:
                return
            async with sem:
                ver = await fetcher(client, name)
                if ver:
                    results[(eco, name)] = ver

        tasks = [_fetch(eco, name) for eco, name in packages]
        await asyncio.gather(*tasks, return_exceptions=True)

    return results


def _compare_versions(current: str | None, latest: str | None) -> bool:
    """Return True if current is outdated compared to latest."""
    if not current or not latest:
        return False
    if current == latest:
        return False
    current_clean = re.sub(r"^v", "", current)
    latest_clean = re.sub(r"^v", "", latest)
    if current_clean == latest_clean:
        return False
    try:
        from packaging.version import Version, InvalidVersion
        return Version(current_clean) < Version(latest_clean)
    except (InvalidVersion, Exception):
        return current_clean != latest_clean


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def scan_repository_dependencies(
    db: AsyncSession,
    repo,
    scan_run: DepScanRun,
    slog: SyncLogger | None = None,
) -> int:
    bare_repo_path = os.path.join(settings.repos_cache_dir, str(repo.id))

    if not os.path.exists(bare_repo_path):
        raise FileNotFoundError(
            f"Repository cache not found at {bare_repo_path}. Sync the repository first."
        )

    if slog:
        slog.info("worktree", "Creating temporary working tree for dependency scan...")

    worktree_dir = _prepare_worktree(bare_repo_path)

    try:
        if slog:
            slog.info("discover", "Scanning for dependency manifest files...")

        dep_files = discover_dependency_files(worktree_dir)

        if slog:
            slog.info("discover", f"Found {len(dep_files)} dependency files")

        if not dep_files:
            if slog:
                slog.info("complete", "No dependency files found")
            return 0

        all_packages: list[tuple[str, str, str | None, str, str, bool]] = []

        for df in dep_files:
            parser = PARSER_MAP.get(df.file_type)
            if not parser:
                continue
            abs_path = os.path.join(worktree_dir, df.file_path)
            parsed = parser(abs_path)
            df.packages = parsed
            if slog:
                slog.info("parse", f"  {df.file_path}: {len(parsed)} packages")
            for p in parsed:
                all_packages.append((df.ecosystem, p.name, p.version, df.file_path, df.file_type, p.is_direct))

        if slog:
            slog.info("vuln", f"Querying OSV.dev for vulnerabilities across {len(all_packages)} packages...")

        osv_input = [(eco, name, ver) for eco, name, ver, *_ in all_packages]
        vuln_map = await query_osv_batch(osv_input)

        if slog:
            vuln_count = sum(1 for v in vuln_map.values() if v)
            slog.info("vuln", f"Found vulnerabilities in {vuln_count} packages")

        unique_pkgs = list({(eco, name) for eco, name, *_ in all_packages})
        if slog:
            slog.info("version", f"Checking latest versions for {len(unique_pkgs)} unique packages...")

        latest_map = await query_latest_versions(unique_pkgs)

        if slog:
            slog.info("persist", "Persisting findings...")

        count = await _persist_findings(db, scan_run, all_packages, vuln_map, latest_map)

        if slog:
            slog.info("complete", f"Dependency scan complete: {count} findings")

        return count

    finally:
        if slog:
            slog.info("cleanup", "Removing temporary working tree...")
        _cleanup_worktree(bare_repo_path, worktree_dir)


async def _persist_findings(
    db: AsyncSession,
    scan_run: DepScanRun,
    all_packages: list[tuple[str, str, str | None, str, str, bool]],
    vuln_map: dict[tuple[str, str], list[VulnInfo]],
    latest_map: dict[tuple[str, str], str],
) -> int:
    now = datetime.now(timezone.utc)

    existing_q = select(DependencyFinding).where(
        DependencyFinding.repository_id == scan_run.repository_id,
        DependencyFinding.status == DepFindingStatus.ACTIVE,
    )
    existing_rows = (await db.execute(existing_q)).scalars().all()
    existing_map: dict[tuple[str, str], DependencyFinding] = {
        (f.file_path, f.package_name): f for f in existing_rows
    }

    seen_keys: set[tuple[str, str]] = set()
    total = 0
    vulnerable_count = 0
    outdated_count = 0

    for eco, name, version, file_path, file_type, is_direct in all_packages:
        key = (file_path, name)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        vulns = vuln_map.get((eco, name), [])
        latest = latest_map.get((eco, name))
        is_outdated = _compare_versions(version, latest)
        is_vulnerable = len(vulns) > 0
        severity = _worst_severity_from_vulns(vulns)

        vuln_dicts = [
            {"id": v.vuln_id, "summary": v.summary, "severity": v.severity, "fixed_version": v.fixed_version, "url": v.url}
            for v in vulns
        ]

        existing = existing_map.get(key)
        if existing:
            existing.scan_run_id = scan_run.id
            existing.last_detected_at = now
            existing.current_version = version
            existing.latest_version = latest
            existing.is_outdated = is_outdated
            existing.is_vulnerable = is_vulnerable
            existing.severity = severity
            existing.vulnerabilities = vuln_dicts
            existing.is_direct = is_direct
        else:
            db.add(DependencyFinding(
                scan_run_id=scan_run.id,
                repository_id=scan_run.repository_id,
                project_id=scan_run.project_id,
                file_path=file_path,
                file_type=file_type,
                ecosystem=eco,
                package_name=name,
                current_version=version,
                latest_version=latest,
                is_outdated=is_outdated,
                is_vulnerable=is_vulnerable,
                is_direct=is_direct,
                severity=severity,
                vulnerabilities=vuln_dicts,
                first_detected_at=now,
                last_detected_at=now,
            ))

        total += 1
        if is_vulnerable:
            vulnerable_count += 1
        if is_outdated:
            outdated_count += 1

    for key, finding in existing_map.items():
        if key not in seen_keys:
            finding.status = DepFindingStatus.FIXED

    scan_run.findings_count = total
    scan_run.vulnerable_count = vulnerable_count
    scan_run.outdated_count = outdated_count
    await db.flush()
    return total
