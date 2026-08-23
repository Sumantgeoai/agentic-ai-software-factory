import pytest

from software_factory.contracts import CodeBundle, GeneratedFile
from software_factory.security import SecurityAgent


@pytest.mark.asyncio
async def test_security_gate_blocks_embedded_private_key() -> None:
    bundle = CodeBundle(
        files=[
            GeneratedFile(
                path="app/config.py",
                content='KEY = "-----BEGIN PRIVATE KEY-----\\nsecret"',
            )
        ]
    )

    report = await SecurityAgent().run(bundle)

    assert not report.passed
    assert any(item.rule == "private-key" for item in report.findings)
