"""
MASKIT 라우트 정적 분석 (SAST) - 인증 커버리지 체커
====================================================
모든 라우터 파일을 AST로 파싱하여 각 엔드포인트의
인증 의존성(Depends) 적용 여부를 자동 탐지.

배포 없이 코드만으로 인증 누락 엔드포인트를 찾을 수 있음.
GitHub Actions SAST 단계에서 실행.

사용법:
  python tests/security/check_auth_coverage.py [--fail-on-missing]
"""

import ast
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# 인증 관련 의존성 함수명 (auth_utils.py에서 확인)
AUTH_DEPS = {
    "get_current_user",
    "get_current_root_admin",
    "get_current_auditor",
    "get_current_policy_admin",
    "get_current_approver",
    "get_current_admin_or_approver",
    "get_current_admin_user",
}

# 의도적으로 공개된 엔드포인트 (허용 목록)
INTENTIONAL_PUBLIC = {
    # 인증 엔드포인트
    ("POST", "register"),
    ("POST", "login"),
    # 헬스체크
    ("GET", "health_check"),
    ("GET", "read_root"),
}

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}


@dataclass
class Endpoint:
    file: str
    function: str
    method: str
    path: str
    has_auth: bool
    auth_dep: Optional[str] = None
    line: int = 0


def find_router_files(base_path: Path) -> list[Path]:
    """app/ 디렉토리에서 라우터 파일 탐색"""
    return list(base_path.rglob("*.py"))


def extract_depends_names(decorator: ast.Call) -> list[str]:
    """@router.X() 데코레이터의 Depends 인자에서 함수명 추출"""
    deps = []
    for kw in decorator.keywords:
        if kw.arg == "dependencies" and isinstance(kw.value, ast.List):
            for elt in kw.value.elts:
                if isinstance(elt, ast.Call):
                    func = elt.func
                    if isinstance(func, ast.Name):
                        deps.append(func.id)
                    elif isinstance(func, ast.Attribute):
                        deps.append(func.attr)
    return deps


def has_auth_in_params(func_def: ast.FunctionDef) -> tuple[bool, Optional[str]]:
    """함수 파라미터에서 Depends(auth_function) 패턴 탐지"""
    for arg in func_def.args.args:
        # 기본값에서 Depends 찾기
        pass

    # 기본값 확인
    defaults = func_def.args.defaults + func_def.args.kw_defaults
    for default in defaults:
        if default is None:
            continue
        if isinstance(default, ast.Call):
            func = default.func
            if isinstance(func, ast.Name) and func.id == "Depends":
                if default.args:
                    arg0 = default.args[0]
                    dep_name = None
                    if isinstance(arg0, ast.Name):
                        dep_name = arg0.id
                    elif isinstance(arg0, ast.Attribute):
                        dep_name = arg0.attr
                    if dep_name in AUTH_DEPS:
                        return True, dep_name
    return False, None


def analyze_file(filepath: Path, app_root: Path) -> list[Endpoint]:
    """한 파일을 AST로 파싱하여 엔드포인트 목록 반환"""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return []

    endpoints = []
    rel_path = str(filepath.relative_to(app_root))

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        for decorator in node.decorator_list:
            # @router.get(...) / @app.post(...) 형태 탐지
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            if not isinstance(func, ast.Attribute):
                continue
            method = func.attr.lower()
            if method not in HTTP_METHODS:
                continue

            # 경로 추출
            path_arg = ""
            if decorator.args:
                arg0 = decorator.args[0]
                if isinstance(arg0, ast.Constant):
                    path_arg = str(arg0.value)

            # 1) 데코레이터 dependencies= 에서 auth 확인
            dep_names = extract_depends_names(decorator)
            auth_in_dec = any(d in AUTH_DEPS for d in dep_names)
            auth_dep_name = next((d for d in dep_names if d in AUTH_DEPS), None)

            # 2) 함수 파라미터에서 Depends(auth_func) 확인
            auth_in_params, param_dep_name = has_auth_in_params(node)

            has_auth = auth_in_dec or auth_in_params
            dep = auth_dep_name or param_dep_name

            # 허용 목록 확인
            if (method.upper(), node.name) in INTENTIONAL_PUBLIC:
                continue

            endpoints.append(Endpoint(
                file=rel_path,
                function=node.name,
                method=method.upper(),
                path=path_arg,
                has_auth=has_auth,
                auth_dep=dep,
                line=node.lineno,
            ))

    return endpoints


def main():
    parser = argparse.ArgumentParser(description="MASKIT Auth Coverage SAST")
    parser.add_argument(
        "--app-dir",
        default="app",
        help="분석할 앱 디렉토리 (기본: app)",
    )
    parser.add_argument(
        "--fail-on-missing",
        action="store_true",
        help="인증 누락 엔드포인트 발견 시 exit code 1 반환 (CI용)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="출력 형식",
    )
    args = parser.parse_args()

    app_root = Path(args.app_dir).resolve()
    if not app_root.exists():
        # backend/ 에서 실행 시 경로 조정
        app_root = Path(__file__).parent.parent.parent / "app"

    files = find_router_files(app_root)
    all_endpoints: list[Endpoint] = []
    for f in files:
        all_endpoints.extend(analyze_file(f, app_root.parent))

    protected = [e for e in all_endpoints if e.has_auth]
    missing = [e for e in all_endpoints if not e.has_auth]

    if args.format == "json":
        import json
        result = {
            "total": len(all_endpoints),
            "protected": len(protected),
            "missing_auth": len(missing),
            "coverage_pct": round(len(protected) / len(all_endpoints) * 100, 1) if all_endpoints else 0,
            "missing_endpoints": [
                {"file": e.file, "function": e.function, "method": e.method, "path": e.path, "line": e.line}
                for e in missing
            ],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"  MASKIT Auth Coverage (Static Analysis)")
        print(f"{'='*60}")
        print(f"  총 엔드포인트  : {len(all_endpoints):>5} 개")
        print(f"  인증 적용      : {len(protected):>5} 개")
        print(f"  인증 누락      : {len(missing):>5} 개")
        coverage = round(len(protected) / len(all_endpoints) * 100, 1) if all_endpoints else 0
        print(f"  인증 커버리지  : {coverage:>5.1f} %")
        print(f"{'='*60}")

        if missing:
            print(f"\n[인증 누락 엔드포인트 목록]")
            print(f"{'─'*60}")
            for e in missing:
                print(f"  {e.method:<7} {e.path or '(경로 미상)':<40} {e.file}:{e.line}")
            print(f"{'─'*60}")
        else:
            print("\n  ✅ 모든 엔드포인트에 인증이 적용되어 있습니다.")

    if args.fail_on_missing and missing:
        sys.exit(1)


if __name__ == "__main__":
    main()
