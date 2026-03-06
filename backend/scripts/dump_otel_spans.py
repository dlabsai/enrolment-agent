import argparse
import asyncio
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select

from app.core.db import get_session
from app.models import OtelSpan
from app.utils import ensure_dir


@dataclass
class SpanNode:
    span: OtelSpan
    children: list["SpanNode"]


def _format_span_line(span: OtelSpan) -> str:
    attributes = span.attributes or {}
    model = attributes.get("gen_ai.request.model")
    cost = attributes.get("operation.cost")
    conversation_id = attributes.get("app.conversation_id")
    message_id = attributes.get("app.message_id")
    agent_name = attributes.get("gen_ai.agent.name")

    extras: list[str] = []
    if agent_name:
        extras.append(f"agent={agent_name}")
    if model:
        extras.append(f"model={model}")
    if cost is not None:
        extras.append(f"cost={cost}")
    if conversation_id:
        extras.append(f"conversation_id={conversation_id}")
    if message_id:
        extras.append(f"message_id={message_id}")

    details = ", ".join(extras)
    duration = f"{span.duration_ms:.2f}ms" if span.duration_ms is not None else "n/a"

    return (
        f"{span.name} [span_id={span.span_id} parent={span.parent_span_id or '-'} "
        f"status={span.status_code or '-'} duration={duration}]"
        + (f" ({details})" if details else "")
    )


def _render_tree(node: SpanNode, lines: list[str], indent: int = 0) -> None:
    lines.append("  " * indent + "- " + _format_span_line(node.span))
    for child in sorted(
        node.children, key=lambda item: item.span.start_time or item.span.created_at
    ):
        _render_tree(child, lines, indent + 1)


async def _load_spans() -> list[OtelSpan]:
    async with get_session() as session:
        result = await session.execute(select(OtelSpan))
        return list(result.scalars().all())


def _build_trees(spans: list[OtelSpan]) -> dict[str, list[SpanNode]]:
    spans_by_trace: dict[str, list[OtelSpan]] = defaultdict(list)
    for span in spans:
        spans_by_trace[span.trace_id].append(span)

    trees: dict[str, list[SpanNode]] = {}
    for trace_id, trace_spans in spans_by_trace.items():
        nodes: dict[str, SpanNode] = {
            span.span_id: SpanNode(span=span, children=[]) for span in trace_spans
        }
        roots: list[SpanNode] = []

        for span in trace_spans:
            node = nodes[span.span_id]
            parent_id = span.parent_span_id
            if parent_id and parent_id in nodes:
                nodes[parent_id].children.append(node)
            else:
                roots.append(node)

        trees[trace_id] = roots

    return trees


def _render_output(spans: list[OtelSpan]) -> str:
    trees = _build_trees(spans)
    lines: list[str] = []

    for trace_id in sorted(trees.keys()):
        trace_spans = [span for span in spans if span.trace_id == trace_id]
        lines.append(f"Trace {trace_id} ({len(trace_spans)} spans)")
        for root in sorted(
            trees[trace_id], key=lambda item: item.span.start_time or item.span.created_at
        ):
            _render_tree(root, lines, indent=1)
        lines.append("")

    return "\n".join(lines).strip() + "\n"


async def _dump_spans(output_path: Path) -> None:
    spans = await _load_spans()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_render_output(spans), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump OTEL spans grouped by trace to a text file.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/otel_spans.txt"),
        help="Output file path (default: reports/otel_spans.txt)",
    )
    args = parser.parse_args()

    ensure_dir(args.output.parent)
    asyncio.run(_dump_spans(args.output))


if __name__ == "__main__":
    main()
