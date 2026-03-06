import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict, TypeGuard

from app.rag.wordpress.config import (
    WP_PAGES_PATH,
    WP_POSTS_PATH,
    WP_PROCESSED_DIR,
    WP_PROGRAMS_PATH,
)
from app.rag.wordpress.shortcode_analyzer import SELF_CLOSING_PATTERN, SHORTCODE_PATTERN


class _ContentTypeCleaningStats(TypedDict):
    total_items: int
    items_with_shortcodes_original: int
    items_with_shortcodes_remaining: int
    total_shortcodes_original: int
    total_shortcodes_remaining: int
    cleaning_effectiveness: float


class _ItemWithRemainingShortcodes(TypedDict):
    id: str
    type: str
    title: str
    url: str
    original_shortcodes: dict[str, int]
    remaining_shortcodes: dict[str, int]


class _CleaningReportDict(TypedDict):
    original_shortcode_counts: dict[str, int]
    remaining_shortcode_counts: dict[str, int]
    original_self_closing_counts: dict[str, int]
    remaining_self_closing_counts: dict[str, int]
    total_original_shortcodes: int
    total_remaining_shortcodes: int
    content_type_stats: dict[str, _ContentTypeCleaningStats]
    items_with_remaining_shortcodes: list[_ItemWithRemainingShortcodes]
    overall_cleaning_effectiveness: float
    shortcode_cleaning_effectiveness: dict[str, float]


@dataclass
class _AnalysisData:
    original_shortcode_counts: Counter[str] = field(default_factory=Counter[str])
    remaining_shortcode_counts: Counter[str] = field(default_factory=Counter[str])
    original_self_closing_counts: Counter[str] = field(default_factory=Counter[str])
    remaining_self_closing_counts: Counter[str] = field(default_factory=Counter[str])
    content_type_stats: dict[str, _ContentTypeCleaningStats] = field(
        default_factory=lambda: defaultdict(
            lambda: {
                "total_items": 0,
                "items_with_shortcodes_original": 0,
                "items_with_shortcodes_remaining": 0,
                "total_shortcodes_original": 0,
                "total_shortcodes_remaining": 0,
                "cleaning_effectiveness": 0.0,
            }
        )
    )
    items_with_remaining_shortcodes: list[_ItemWithRemainingShortcodes] = field(
        default_factory=list[_ItemWithRemainingShortcodes]
    )


def _load_json(file_path: Path) -> list[dict[str, Any]]:
    if not file_path.exists():
        print(f"Warning: {file_path} does not exist")
        return []

    with file_path.open() as f:
        return json.load(f)


def _is_dict(value: Any) -> TypeGuard[dict[str, Any]]:
    return isinstance(value, dict)


def _get_rendered_content(item: dict[str, Any]) -> str | None:
    content = item.get("content")
    if _is_dict(content):
        rendered = content.get("rendered")
        if isinstance(rendered, str):
            return rendered
    return None


def _get_rag_content(item: dict[str, Any]) -> str | None:
    rag_content = item.get("html_content")
    if isinstance(rag_content, str):
        return rag_content
    return None


def _count_shortcodes(content: str) -> dict[str, int]:
    result: dict[str, int] = defaultdict(int)

    shortcodes = SHORTCODE_PATTERN.findall(content)
    for sc_type, _, _ in shortcodes:
        result[sc_type] += 1

    self_closing = SELF_CLOSING_PATTERN.findall(content)
    for sc_type, _ in self_closing:
        result[sc_type] += 1

    return dict(result)


def _analyze_original_content(content: str, content_type: str, data: _AnalysisData) -> bool:
    has_shortcodes = False

    shortcodes = SHORTCODE_PATTERN.findall(content)

    for sc_type, _, _ in shortcodes:
        has_shortcodes = True
        data.original_shortcode_counts[sc_type] += 1
        data.content_type_stats[content_type]["total_shortcodes_original"] += 1

    self_closing = SELF_CLOSING_PATTERN.findall(content)
    for sc_type, _ in self_closing:
        has_shortcodes = True
        data.original_self_closing_counts[sc_type] += 1
        data.content_type_stats[content_type]["total_shortcodes_original"] += 1

    return has_shortcodes


def _analyze_rag_content(content: str, content_type: str, data: _AnalysisData) -> bool:
    has_shortcodes = False

    shortcodes = SHORTCODE_PATTERN.findall(content)

    for sc_type, _, _ in shortcodes:
        has_shortcodes = True
        data.remaining_shortcode_counts[sc_type] += 1
        data.content_type_stats[content_type]["total_shortcodes_remaining"] += 1

    self_closing = SELF_CLOSING_PATTERN.findall(content)
    for sc_type, _ in self_closing:
        has_shortcodes = True
        data.remaining_self_closing_counts[sc_type] += 1
        data.content_type_stats[content_type]["total_shortcodes_remaining"] += 1

    return has_shortcodes


def _load_content_data() -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    original_data_files = {
        "post": WP_POSTS_PATH,
        "page": WP_PAGES_PATH,
        "program": WP_PROGRAMS_PATH,
    }

    original_content_by_type = {
        content_type: _load_json(file_path)
        for content_type, file_path in original_data_files.items()
    }

    for content_type, items in original_content_by_type.items():
        print(f"Loaded {len(items)} original {content_type}s")

    rag_data_files = {
        "post": WP_PROCESSED_DIR / "post_rag_content.json",
        "page": WP_PROCESSED_DIR / "page_rag_content.json",
        "program": WP_PROCESSED_DIR / "program_rag_content.json",
    }

    rag_content_by_type = {
        content_type: _load_json(file_path) for content_type, file_path in rag_data_files.items()
    }

    for content_type, items in rag_content_by_type.items():
        print(f"Loaded {len(items)} RAG {content_type}s")

    return original_content_by_type, rag_content_by_type


def _analyze_content_data(
    original_content_by_type: dict[str, list[dict[str, Any]]],
    rag_content_by_type: dict[str, list[dict[str, Any]]],
) -> _AnalysisData:
    data = _AnalysisData()

    rag_content_by_id: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for content_type, items in rag_content_by_type.items():
        for item in items:
            rag_content_by_id[content_type][item["id"]] = item

    for content_type, items in original_content_by_type.items():
        data.content_type_stats[content_type]["total_items"] = len(items)

        for item in items:
            original_content = _get_rendered_content(item)
            if original_content is None:
                continue

            item_id = item["id"]

            rag_item = rag_content_by_id[content_type].get(item_id)
            if not rag_item:
                continue

            rag_content = _get_rag_content(rag_item)
            if rag_content is None:
                continue

            has_original_shortcodes = _analyze_original_content(
                original_content, content_type, data
            )
            has_remaining_shortcodes = _analyze_rag_content(rag_content, content_type, data)

            if has_original_shortcodes:
                data.content_type_stats[content_type]["items_with_shortcodes_original"] += 1

            if has_remaining_shortcodes:
                data.content_type_stats[content_type]["items_with_shortcodes_remaining"] += 1

                title = "Unknown"
                if (
                    "title" in item
                    and isinstance(item["title"], dict)
                    and "rendered" in item["title"]
                    and isinstance(item["title"]["rendered"], str)
                ):
                    title = item["title"]["rendered"]

                data.items_with_remaining_shortcodes.append(
                    {
                        "id": item_id,
                        "type": content_type,
                        "title": title,
                        "url": item.get("link", "Unknown"),
                        "original_shortcodes": _count_shortcodes(original_content),
                        "remaining_shortcodes": _count_shortcodes(rag_content),
                    }
                )

        original_count = data.content_type_stats[content_type]["total_shortcodes_original"]
        remaining_count = data.content_type_stats[content_type]["total_shortcodes_remaining"]

        if original_count > 0:
            effectiveness = ((original_count - remaining_count) / original_count) * 100
            data.content_type_stats[content_type]["cleaning_effectiveness"] = effectiveness
        else:
            data.content_type_stats[content_type]["cleaning_effectiveness"] = 100.0

        print(f"Analyzed {len(items)} {content_type}s")

    return data


def _generate_report(data: _AnalysisData) -> _CleaningReportDict:
    report: _CleaningReportDict = {
        "original_shortcode_counts": dict(data.original_shortcode_counts),
        "remaining_shortcode_counts": dict(data.remaining_shortcode_counts),
        "original_self_closing_counts": dict(data.original_self_closing_counts),
        "remaining_self_closing_counts": dict(data.remaining_self_closing_counts),
        "total_original_shortcodes": sum(data.original_shortcode_counts.values())
        + sum(data.original_self_closing_counts.values()),
        "total_remaining_shortcodes": sum(data.remaining_shortcode_counts.values())
        + sum(data.remaining_self_closing_counts.values()),
        "content_type_stats": dict(data.content_type_stats),
        "items_with_remaining_shortcodes": data.items_with_remaining_shortcodes,
        "overall_cleaning_effectiveness": 0.0,
        "shortcode_cleaning_effectiveness": {},
    }

    if report["total_original_shortcodes"] > 0:
        report["overall_cleaning_effectiveness"] = (
            (report["total_original_shortcodes"] - report["total_remaining_shortcodes"])
            / report["total_original_shortcodes"]
        ) * 100
    else:
        report["overall_cleaning_effectiveness"] = 100.0

    shortcode_effectiveness: dict[str, float] = {}

    for sc_type, original_count in data.original_shortcode_counts.items():
        remaining_count = data.remaining_shortcode_counts.get(sc_type, 0)
        if original_count > 0:
            effectiveness = ((original_count - remaining_count) / original_count) * 100
            shortcode_effectiveness[sc_type] = effectiveness
        else:
            shortcode_effectiveness[sc_type] = 100.0

    for sc_type, original_count in data.original_self_closing_counts.items():
        remaining_count = data.remaining_self_closing_counts.get(sc_type, 0)
        if original_count > 0:
            effectiveness = ((original_count - remaining_count) / original_count) * 100
            shortcode_effectiveness[sc_type] = effectiveness
        else:
            shortcode_effectiveness[sc_type] = 100.0

    report["shortcode_cleaning_effectiveness"] = shortcode_effectiveness

    return report


def _print_report(report: _CleaningReportDict) -> None:
    print("\n=== DIVI SHORTCODE CLEANING ANALYSIS REPORT ===\n")

    print(f"Total original shortcodes: {report['total_original_shortcodes']}")
    print(f"Total remaining shortcodes: {report['total_remaining_shortcodes']}")
    print(f"Overall cleaning effectiveness: {report['overall_cleaning_effectiveness']:.2f}%")

    print("\n--- CONTENT TYPE STATISTICS ---")
    for content_type, stats in report["content_type_stats"].items():
        total = stats["total_items"]
        with_original = stats["items_with_shortcodes_original"]
        with_remaining = stats["items_with_shortcodes_remaining"]

        if total > 0:
            original_percentage = (with_original / total) * 100
            remaining_percentage = (with_remaining / total) * 100

            print(f"{content_type}s:")
            print(f"  - Original: {with_original}/{total}", end=" ")
            print(f"({original_percentage:.1f}%) contained shortcodes")
            print(f"  - Remaining: {with_remaining}/{total}", end=" ")
            print(f"({remaining_percentage:.1f}%) contain shortcodes")
            print(f"  - Original shortcodes: {stats['total_shortcodes_original']}")
            print(f"  - Remaining shortcodes: {stats['total_shortcodes_remaining']}")
            print(f"  - Cleaning effectiveness: {stats['cleaning_effectiveness']:.2f}%")

    print("\n--- SHORTCODE CLEANING EFFECTIVENESS ---")
    for sc_type, effectiveness in sorted(
        report["shortcode_cleaning_effectiveness"].items(), key=lambda x: x[1]
    ):
        original_count = report["original_shortcode_counts"].get(sc_type, 0) + report[
            "original_self_closing_counts"
        ].get(sc_type, 0)
        remaining_count = report["remaining_shortcode_counts"].get(sc_type, 0) + report[
            "remaining_self_closing_counts"
        ].get(sc_type, 0)
        print(f"{sc_type}: {effectiveness:.2f}% ({remaining_count}/{original_count} remaining)")

    print("\n--- TOP REMAINING SHORTCODES ---")
    for sc_type, count in sorted(
        report["remaining_shortcode_counts"].items(), key=lambda x: x[1], reverse=True
    )[:10]:
        original_count = report["original_shortcode_counts"].get(sc_type, 0)
        print(f"{sc_type}: {count}/{original_count} remaining")

    print("\n--- TOP REMAINING SELF-CLOSING SHORTCODES ---")
    for sc_type, count in sorted(
        report["remaining_self_closing_counts"].items(), key=lambda x: x[1], reverse=True
    )[:10]:
        original_count = report["original_self_closing_counts"].get(sc_type, 0)
        print(f"{sc_type}: {count}/{original_count} remaining")

    print("\n--- ITEMS WITH REMAINING SHORTCODES ---")
    remaining_count = len(report["items_with_remaining_shortcodes"])
    print(f"Total items with remaining shortcodes: {remaining_count}")

    for item in sorted(
        report["items_with_remaining_shortcodes"],
        key=lambda x: sum(x["remaining_shortcodes"].values()),
        reverse=True,
    )[:10]:
        total_remaining = sum(item["remaining_shortcodes"].values())
        print(f"\n{item['type'].capitalize()} ID {item['id']}: {item['title']}")
        print(f"  URL: {item['url']}")
        print(f"  Total remaining shortcodes: {total_remaining}")
        for sc_type, count in sorted(
            item["remaining_shortcodes"].items(), key=lambda x: x[1], reverse=True
        ):
            print(f"    - {sc_type}: {count}")


def _save_report(report: _CleaningReportDict, output_file: Path) -> None:
    output_file.write_text(json.dumps(report, indent=2))
    print(f"\nDetailed report saved to {output_file}")


def _main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Divi shortcode cleaning effectiveness")
    parser.add_argument(
        "--output",
        type=str,
        default="shortcode_cleaning_report.json",
        help="Output file for the detailed report",
    )
    args = parser.parse_args()
    output_file = Path(args.output)
    original_content_by_type, rag_content_by_type = _load_content_data()
    analysis_data = _analyze_content_data(original_content_by_type, rag_content_by_type)
    report = _generate_report(analysis_data)
    _print_report(report)
    _save_report(report, output_file)


if __name__ == "__main__":
    _main()
