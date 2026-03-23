"""
MASKIT Security Assessment - 정량 지표 리포트 생성기
=====================================================
pytest --json-report 결과를 읽어 보안 지표를 집계하고
텍스트/JSON 리포트를 출력.

사용법:
  pip install pytest-json-report
  cd backend
  pytest tests/security/ -v --json-report --json-report-file=security_report.json
  python tests/security/generate_report.py [--json security_report.json]
"""

import json
import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

# CVSS v3.1 기준 점수 매핑 (취약점 유형별 추정)
# 실제 환경에 따라 조정 필요
CVSS_SCORES = {
    "CRITICAL": 9.1,   # AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N
    "HIGH":     7.5,   # AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N
    "MEDIUM":   5.3,   # AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N
    "LOW":      3.1,
}

# 테스트 클래스 → 심각도 매핑
SEVERITY_MAP = {
    "TestCriticalEndpoints":        "CRITICAL",
    "TestHighEndpoints":            "HIGH",
    "TestMediumEndpoints":          "MEDIUM",
    "TestExpiredToken":             "HIGH",
    "TestTamperedToken":            "HIGH",
    "TestNoneAlgorithmAttack":      "CRITICAL",
    "TestMalformedTokens":          "MEDIUM",
    "TestEmailIDOR":                "CRITICAL",
    "TestOriginalEmailIDOR":        "CRITICAL",
    "TestPolicyIDOR":               "HIGH",
    "TestVectorDBIDOR":             "HIGH",
    "TestRootAdminEndpoints":       "CRITICAL",
    "TestPolicyAdminEndpoints":     "HIGH",
    "TestAuditorEndpoints":         "HIGH",
    "TestSelfPrivilegeEscalation":  "CRITICAL",
    "TestCORSHeaders":              "MEDIUM",
    "TestCORSWithAuthentication":   "LOW",
    "TestPublicEndpoints":          "INFO",
    "TestValidTokenWorks":          "INFO",
}

OWASP_MAP = {
    "TestCriticalEndpoints":        "API2:2023 Broken Authentication",
    "TestHighEndpoints":            "API2:2023 Broken Authentication",
    "TestMediumEndpoints":          "API2:2023 Broken Authentication",
    "TestExpiredToken":             "API2:2023 Broken Authentication",
    "TestTamperedToken":            "API2:2023 Broken Authentication",
    "TestNoneAlgorithmAttack":      "API2:2023 Broken Authentication",
    "TestMalformedTokens":          "API2:2023 Broken Authentication",
    "TestEmailIDOR":                "API1:2023 Broken Object Level Authorization",
    "TestOriginalEmailIDOR":        "API1:2023 Broken Object Level Authorization",
    "TestPolicyIDOR":               "API1:2023 Broken Object Level Authorization",
    "TestVectorDBIDOR":             "API1:2023 Broken Object Level Authorization",
    "TestRootAdminEndpoints":       "API5:2023 Broken Function Level Authorization",
    "TestPolicyAdminEndpoints":     "API5:2023 Broken Function Level Authorization",
    "TestAuditorEndpoints":         "API5:2023 Broken Function Level Authorization",
    "TestSelfPrivilegeEscalation":  "API5:2023 Broken Function Level Authorization",
    "TestCORSHeaders":              "API8:2023 Security Misconfiguration",
    "TestCORSWithAuthentication":   "API8:2023 Security Misconfiguration",
}


def load_report(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def classify_test(nodeid: str) -> dict:
    """test nodeid에서 클래스명 추출 → 심각도/OWASP 분류"""
    parts = nodeid.split("::")
    class_name = parts[1] if len(parts) >= 3 else ""
    return {
        "severity": SEVERITY_MAP.get(class_name, "UNKNOWN"),
        "owasp": OWASP_MAP.get(class_name, "기타"),
        "class": class_name,
    }


def analyze(report: dict) -> dict:
    tests = report.get("tests", [])
    total = len(tests)

    counters = {
        "total": total,
        "passed": 0,
        "failed": 0,   # 취약점 발견
        "error": 0,
        "skipped": 0,
    }

    severity_vuln = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    owasp_vuln: dict[str, int] = {}
    vulnerable_tests = []
    protected_tests = []
    cvss_scores = []

    for t in tests:
        outcome = t.get("outcome", "unknown")
        nodeid = t.get("nodeid", "")
        cls = classify_test(nodeid)

        if cls["severity"] == "INFO":
            continue

        if outcome == "passed":
            counters["passed"] += 1
            protected_tests.append(nodeid)
        elif outcome == "failed":
            counters["failed"] += 1
            sev = cls["severity"]
            if sev in severity_vuln:
                severity_vuln[sev] += 1
            owasp = cls["owasp"]
            owasp_vuln[owasp] = owasp_vuln.get(owasp, 0) + 1
            cvss = CVSS_SCORES.get(sev, 0.0)
            cvss_scores.append(cvss)
            vulnerable_tests.append({
                "test": nodeid,
                "severity": sev,
                "owasp": owasp,
                "cvss": cvss,
                "message": t.get("call", {}).get("longrepr", "")[:200],
            })
        elif outcome == "error":
            counters["error"] += 1
        elif outcome == "skipped":
            counters["skipped"] += 1

    security_tests = counters["passed"] + counters["failed"]
    bypass_rate = (
        round(counters["failed"] / security_tests * 100, 1)
        if security_tests > 0 else 0.0
    )
    avg_cvss = round(sum(cvss_scores) / len(cvss_scores), 1) if cvss_scores else 0.0
    max_cvss = max(cvss_scores) if cvss_scores else 0.0

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "total_security_tests": security_tests,
            "protected_count": counters["passed"],
            "vulnerable_count": counters["failed"],
            "skipped_count": counters["skipped"],
            "error_count": counters["error"],
            "auth_bypass_rate_pct": bypass_rate,
            "avg_cvss_score": avg_cvss,
            "max_cvss_score": max_cvss,
            "cors_wildcard_detected": any(
                "CORS" in v["test"] for v in vulnerable_tests
            ),
        },
        "severity_distribution": severity_vuln,
        "owasp_distribution": owasp_vuln,
        "vulnerable_tests": vulnerable_tests,
        "protected_tests": protected_tests,
    }


def print_report(result: dict) -> None:
    s = result["summary"]
    sev = result["severity_distribution"]
    owasp = result["owasp_distribution"]

    line = "─" * 60
    print(f"\n{'='*60}")
    print(f"  MASKIT API Security Assessment Report")
    print(f"  생성: {result['generated_at']}")
    print(f"{'='*60}")
    print(f"\n{'[ 전체 요약 ]':^60}")
    print(line)
    print(f"  총 보안 테스트 수          : {s['total_security_tests']:>6} 개")
    print(f"  보호된 엔드포인트          : {s['protected_count']:>6} 개")
    print(f"  취약 (인증 우회 성공)      : {s['vulnerable_count']:>6} 개")
    print(f"  인증 우회 성공률           : {s['auth_bypass_rate_pct']:>5.1f} %")
    print(line)
    print(f"\n{'[ 심각도 분포 ]':^60}")
    print(line)
    print(f"  🔴 Critical               : {sev.get('CRITICAL', 0):>6} 개  (CVSS ≥ 9.0)")
    print(f"  🟠 High                   : {sev.get('HIGH', 0):>6} 개  (CVSS 7.0~8.9)")
    print(f"  🟡 Medium                 : {sev.get('MEDIUM', 0):>6} 개  (CVSS 4.0~6.9)")
    print(f"  🟢 Low                    : {sev.get('LOW', 0):>6} 개  (CVSS < 4.0)")
    print(line)
    print(f"\n{'[ CVSS 점수 ]':^60}")
    print(line)
    print(f"  평균 CVSS Score            : {s['avg_cvss_score']:>5.1f} / 10.0")
    print(f"  최고 CVSS Score            : {s['max_cvss_score']:>5.1f} / 10.0")
    print(line)
    print(f"\n{'[ OWASP API Security Top 10 분포 ]':^60}")
    print(line)
    for cat, cnt in sorted(owasp.items(), key=lambda x: -x[1]):
        print(f"  {cnt:>3}건  {cat}")
    print(line)
    print(f"\n{'[ 기타 ]':^60}")
    print(line)
    print(f"  CORS 와일드카드 취약       : {'예 ⚠' if s['cors_wildcard_detected'] else '아니오 ✓'}")
    print(f"{'='*60}\n")

    if result["vulnerable_tests"]:
        print(f"{'[ 발견된 취약점 목록 ]':^60}")
        print(line)
        for v in result["vulnerable_tests"]:
            print(f"  [{v['severity']}] CVSS {v['cvss']:.1f} | {v['owasp']}")
            print(f"        {v['test']}")
        print(line)


def main():
    parser = argparse.ArgumentParser(description="MASKIT Security Report Generator")
    parser.add_argument(
        "--json",
        default="security_report.json",
        help="pytest --json-report 결과 파일 경로",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="결과 JSON 저장 경로 (미지정 시 stdout만 출력)",
    )
    args = parser.parse_args()

    report_path = Path(args.json)
    if not report_path.exists():
        print(f"[ERROR] 리포트 파일 없음: {report_path}", file=sys.stderr)
        print("  → 먼저 실행: pytest tests/security/ -v --json-report --json-report-file=security_report.json")
        sys.exit(1)

    raw = load_report(str(report_path))
    result = analyze(raw)
    print_report(result)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"[저장] {args.output}")

    # CI exit code: 취약점 있으면 1
    sys.exit(1 if result["summary"]["vulnerable_count"] > 0 else 0)


if __name__ == "__main__":
    main()
