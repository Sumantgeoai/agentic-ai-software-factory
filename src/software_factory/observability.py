from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from threading import Lock

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .config import Settings

_lock = Lock()
_configured = False
_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def configure_observability(settings: Settings) -> None:
    global _configured
    if _configured:
        return
    with _lock:
        if _configured:
            return
        provider = TracerProvider(
            resource=Resource.create({"service.name": settings.otel_service_name})
        )
        if settings.otel_exporter_otlp_endpoint:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            provider.add_span_processor(
                BatchSpanProcessor(
                    OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
                )
            )
        trace.set_tracer_provider(provider)
        _configured = True


def get_tracer():  # type: ignore[no-untyped-def]
    return trace.get_tracer("software_factory")


def current_correlation_id() -> str | None:
    return _correlation_id.get()


@contextmanager
def correlation_context(correlation_id: str) -> Iterator[None]:
    token: Token[str | None] = _correlation_id.set(correlation_id)
    try:
        yield
    finally:
        _correlation_id.reset(token)
