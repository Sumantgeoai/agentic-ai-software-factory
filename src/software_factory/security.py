from __future__ import annotations

import re

from .contracts import CodeBundle, SecurityFinding, SecurityReport


class SecurityAgent:
    _secret_patterns = (
        ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
        ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
        ("api-secret", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    )
    _unsafe_code = (
        ("shell-exec", "os.system("),
        ("shell-exec", "shell=True"),
        ("dynamic-exec", "eval("),
        ("dynamic-exec", "exec("),
    )

    async def run(self, bundle: CodeBundle) -> SecurityReport:
        findings: list[SecurityFinding] = []
        for file in bundle.files:
            lower_path = file.path.lower()
            if lower_path.endswith(".env") or lower_path.endswith("credentials.json"):
                findings.append(
                    SecurityFinding(
                        severity="high",
                        rule="credential-file",
                        file=file.path,
                        message="Credential-bearing files are not allowed in generated artifacts.",
                    )
                )
            for rule, pattern in self._secret_patterns:
                if pattern.search(file.content):
                    findings.append(
                        SecurityFinding(
                            severity="high",
                            rule=rule,
                            file=file.path,
                            message="Potential embedded secret detected.",
                        )
                    )
            if file.path.endswith(".py"):
                for rule, token in self._unsafe_code:
                    if token in file.content:
                        findings.append(
                            SecurityFinding(
                                severity="high",
                                rule=rule,
                                file=file.path,
                                message=f"Unsafe execution primitive detected: {token}",
                            )
                        )
        return SecurityReport(
            passed=not any(finding.severity == "high" for finding in findings),
            findings=findings,
        )
