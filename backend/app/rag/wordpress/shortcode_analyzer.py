import argparse
import json
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict, TypeGuard

from bs4 import BeautifulSoup

from app.rag.wordpress.config import WP_PAGES_PATH, WP_POSTS_PATH, WP_PROGRAMS_PATH, WP_TEMP_DIR
from app.utils import ensure_dir

_MAX_CONTENT_LENGTH = 10000
_MAX_ATTRIBUTE_LENGTH = 1000

# Matches shortcodes with content: [tag attr="value"]content[/tag]
SHORTCODE_PATTERN = re.compile(r"\[([^\s\]]+)([^\]]*)\](.*?)\[/\1\]", re.DOTALL)
# Matches attributes within shortcodes: attr="value"
_ATTRIBUTE_PATTERN = re.compile(r'(\w+)="([^"]*)"')
# Matches self-closing shortcodes: [tag attr="value"/]
SELF_CLOSING_PATTERN = re.compile(r"\[([^\s\]]+)([^\]]*)/\]")


class _StatsBase(TypedDict):
    count: int


class _ContentTypeStats(TypedDict):
    total_items: int
    items_with_shortcodes: int
    total_shortcodes: int


class _ContentLengthStats(_StatsBase):
    min: int
    max: int
    avg: float
    median: float
    total: int


class _NestingDepthStats(_StatsBase):
    min: int
    max: int
    avg: float


class _ContentCoverageStats(_StatsBase):
    min: float
    max: float
    avg: float


class _ReportDict(TypedDict):
    shortcode_counts: dict[str, int]
    self_closing_counts: dict[str, int]
    total_shortcodes: int
    unique_shortcode_types: int
    attribute_usage: dict[str, dict[str, int]]
    nesting_patterns: dict[str, dict[str, int]]
    content_length_stats: dict[str, _ContentLengthStats]
    nesting_depth_stats: dict[str, _NestingDepthStats]
    content_coverage: dict[str, _ContentCoverageStats]
    content_type_stats: dict[str, _ContentTypeStats]
    unusual_patterns: list[str]


@dataclass
class _AnalysisData:
    shortcode_counts: Counter[str] = field(default_factory=Counter[str])
    self_closing_counts: Counter[str] = field(default_factory=Counter[str])
    attribute_usage: dict[str, dict[str, int]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(int))
    )
    nesting_patterns: dict[str, dict[str, int]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(int))
    )
    content_lengths: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    shortcode_depths: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    content_coverage: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    content_type_stats: dict[str, _ContentTypeStats] = field(
        default_factory=lambda: defaultdict(
            lambda: {"total_items": 0, "items_with_shortcodes": 0, "total_shortcodes": 0}
        )
    )
    unusual_patterns: list[str] = field(default_factory=list[str])


def _load_json(file_path: Path) -> list[dict[str, Any]]:
    return json.loads(file_path.read_text())


def _is_dict(value: Any) -> TypeGuard[dict[str, Any]]:
    return isinstance(value, dict)


def _get_rendered_content(item: dict[str, Any]) -> str | None:
    content = item.get("content")
    if _is_dict(content):
        rendered = content.get("rendered")
        if isinstance(rendered, str):
            return rendered
    return None


def _find_all_shortcodes(content: str) -> list[tuple[str, list[tuple[str, str]], str, str]]:
    results: list[tuple[str, list[tuple[str, str]], str, str]] = []
    for match in SHORTCODE_PATTERN.finditer(content):
        sc_type, attrs_text, sc_content, full_sc = (
            match.groups()[0],
            match.groups()[1],
            match.groups()[2],
            match.group(0),
        )
        attrs = _ATTRIBUTE_PATTERN.findall(attrs_text)
        results.append((sc_type, attrs, sc_content, full_sc))
    return results


def _calculate_depth(content: str) -> int:
    depth = max_depth = 0
    for char in content:
        if char == "[":
            depth += 1
            max_depth = max(max_depth, depth)
        elif char == "]":
            depth = max(0, depth - 1)
    return max_depth


def _check_for_unusual_patterns(
    sc_type: str, attrs: list[tuple[str, str]], content: str
) -> list[str]:
    unusual: list[str] = []
    if len(content) > _MAX_CONTENT_LENGTH:
        unusual.append(f"Very long content ({len(content)} chars) in {sc_type}")
    if f"[{sc_type}" in content:
        unusual.append(f"Nested shortcode of same type: {sc_type}")

    for attr_name, attr_value in attrs:
        if len(attr_value) > _MAX_ATTRIBUTE_LENGTH:
            unusual.append(f"Very long attribute value for {attr_name} in {sc_type}")
        if attr_name.startswith("_"):
            unusual.append(f"Attribute with underscore prefix: {attr_name} in {sc_type}")

    return unusual


def _calculate_length_stats(values: list[int]) -> _ContentLengthStats | None:
    if not values:
        return None

    total = sum(values)
    return {
        "min": min(values),
        "max": max(values),
        "avg": total / len(values),
        "median": statistics.median(values),
        "total": total,
        "count": len(values),
    }


def _calculate_nesting_depth_stats(values: list[int]) -> _NestingDepthStats | None:
    if not values:
        return None

    return {
        "min": min(values),
        "max": max(values),
        "avg": sum(values) / len(values),
        "count": len(values),
    }


def _calculate_content_coverage_stats(values: list[float]) -> _ContentCoverageStats | None:
    if not values:
        return None

    return {
        "min": min(values),
        "max": max(values),
        "avg": sum(values) / len(values),
        "count": len(values),
    }


def _load_content_data() -> dict[str, list[dict[str, Any]]]:
    data_files = {"post": WP_POSTS_PATH, "page": WP_PAGES_PATH, "program": WP_PROGRAMS_PATH}

    content_by_type = {
        content_type: _load_json(file_path) for content_type, file_path in data_files.items()
    }

    for content_type, items in content_by_type.items():
        print(f"Loaded {len(items)} {content_type}s")

    return content_by_type


def _analyze_single_content(content: str, content_type: str, data: _AnalysisData) -> bool:
    total_content_length = len(content)
    shortcode_content_length = 0
    has_shortcodes = False

    shortcodes = _find_all_shortcodes(content)
    for sc_type, attrs, sc_content, full_sc in shortcodes:
        has_shortcodes = True
        data.shortcode_counts[sc_type] += 1
        shortcode_content_length += len(full_sc)
        data.content_type_stats[content_type]["total_shortcodes"] += 1

        for attr_name, _ in attrs:
            data.attribute_usage[sc_type][attr_name] += 1

        data.content_lengths[sc_type].append(len(sc_content))

        for nested_type, _, _, _ in _find_all_shortcodes(sc_content):
            data.nesting_patterns[sc_type][nested_type] = (
                data.nesting_patterns[sc_type].get(nested_type, 0) + 1
            )

        data.shortcode_depths[sc_type].append(_calculate_depth(sc_content))

        data.unusual_patterns.extend(_check_for_unusual_patterns(sc_type, attrs, sc_content))

    for sc_type, _ in SELF_CLOSING_PATTERN.findall(content):
        has_shortcodes = True
        data.self_closing_counts[sc_type] += 1
        data.content_type_stats[content_type]["total_shortcodes"] += 1

    if total_content_length > 0:
        coverage = (shortcode_content_length / total_content_length) * 100
        data.content_coverage[content_type].append(coverage)

    return has_shortcodes


def _analyze_content_data(content_by_type: dict[str, list[dict[str, Any]]]) -> _AnalysisData:
    data = _AnalysisData()

    for content_type, items in content_by_type.items():
        data.content_type_stats[content_type]["total_items"] = len(items)

        for item in items:
            content = _get_rendered_content(item)
            if content is None:
                continue

            has_shortcodes = _analyze_single_content(content, content_type, data)

            soup = BeautifulSoup(markup=content, features="html.parser")
            content_pretty_html = soup.prettify()

            subdir = "sc" if has_shortcodes else "no_sc"
            path = WP_TEMP_DIR / content_type / subdir / f"{item['id']}.pretty.html"

            if has_shortcodes:
                data.content_type_stats[content_type]["items_with_shortcodes"] += 1

            ensure_dir(path.parent)
            path.write_text(str(content_pretty_html))

        print(f"Analyzed {len(items)} {content_type}s")

    return data


def _generate_report(data: _AnalysisData) -> _ReportDict:
    report: _ReportDict = {
        "shortcode_counts": dict(data.shortcode_counts),
        "self_closing_counts": dict(data.self_closing_counts),
        "total_shortcodes": sum(data.shortcode_counts.values())
        + sum(data.self_closing_counts.values()),
        "unique_shortcode_types": len(data.shortcode_counts) + len(data.self_closing_counts),
        "attribute_usage": {k: dict(v) for k, v in data.attribute_usage.items()},
        "nesting_patterns": {k: dict(v) for k, v in data.nesting_patterns.items()},
        "content_length_stats": {},
        "nesting_depth_stats": {},
        "content_coverage": {},
        "content_type_stats": dict(data.content_type_stats),
        "unusual_patterns": list(set(data.unusual_patterns)),
    }

    report["content_length_stats"] = {}
    for sc_type, lengths in data.content_lengths.items():
        stats = _calculate_length_stats(lengths)
        if stats:
            report["content_length_stats"][sc_type] = stats

    report["nesting_depth_stats"] = {}
    for sc_type, depths in data.shortcode_depths.items():
        stats = _calculate_nesting_depth_stats(depths)
        if stats:
            report["nesting_depth_stats"][sc_type] = stats

    report["content_coverage"] = {}
    for content_type, coverages in data.content_coverage.items():
        stats = _calculate_content_coverage_stats(coverages)
        if stats:
            report["content_coverage"][content_type] = stats

    return report


def _print_report(report: _ReportDict) -> None:
    print("\n=== DIVI SHORTCODE ANALYSIS REPORT ===\n")
    print(f"Total shortcodes found: {report['total_shortcodes']}")
    print(f"Unique shortcode types: {report['unique_shortcode_types']}")

    print("\n--- CONTENT TYPE STATISTICS ---")
    for content_type, stats in report.get("content_type_stats", {}).items():
        total = stats.get("total_items", 0)
        with_sc = stats.get("items_with_shortcodes", 0)
        total_sc = stats.get("total_shortcodes", 0)

        if total > 0:
            percentage = (with_sc / total) * 100
            avg_per_item = total_sc / total if total > 0 else 0
            avg_per_item_with_sc = total_sc / with_sc if with_sc > 0 else 0

            print(f"{content_type}s: {with_sc}/{total} ({percentage:.1f}%) contain shortcodes")
            print(f"  - Total shortcodes: {total_sc}")
            print(f"  - Avg shortcodes per item: {avg_per_item:.2f}")
            print(f"  - Avg shortcodes per item with shortcodes: {avg_per_item_with_sc:.2f}")

    print("\n--- TOP SHORTCODE TYPES ---")
    for sc_type, count in sorted(
        report.get("shortcode_counts", {}).items(), key=lambda x: x[1], reverse=True
    )[:15]:
        print(f"{sc_type}: {count}")

    print("\n--- TOP SELF-CLOSING SHORTCODES ---")
    for sc_type, count in sorted(
        report.get("self_closing_counts", {}).items(), key=lambda x: x[1], reverse=True
    )[:10]:
        print(f"{sc_type}: {count}")

    print("\n--- TOP NESTING PATTERNS ---")
    for parent, children in sorted(
        report.get("nesting_patterns", {}).items(), key=lambda x: sum(x[1].values()), reverse=True
    )[:10]:
        if children:
            print(f"\n{parent} contains:")
            for child, count in sorted(children.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"  - {child}: {count} times")

    print("\n--- CONTENT COVERAGE ---")
    for content_type, stats in report.get("content_coverage", {}).items():
        avg = stats.get("avg", 0)
        min_val = stats.get("min", 0)
        max_val = stats.get("max", 0)
        print(
            f"{content_type}: {avg:.2f}% average coverage (range: {min_val:.2f}% - {max_val:.2f}%)"
        )

    print("\n--- TOP ATTRIBUTE USAGE ---")
    for sc_type, attrs in sorted(
        report.get("attribute_usage", {}).items(), key=lambda x: sum(x[1].values()), reverse=True
    )[:10]:
        print(f"\n{sc_type} attributes:")
        for attr, count in sorted(attrs.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  - {attr}: {count} times")

    print("\n--- CONTENT LENGTH STATISTICS ---")
    for sc_type, stats in sorted(
        report.get("content_length_stats", {}).items(),
        key=lambda x: x[1].get("total", 0),
        reverse=True,
    )[:10]:
        avg = stats.get("avg", 0)
        min_val = stats.get("min", 0)
        max_val = stats.get("max", 0)
        median = stats.get("median", 0)
        print(
            f"{sc_type}: avg {avg:.1f} chars (min: {min_val}, max: {max_val}, median: {median:.1f})"
        )

    print("\n--- NESTING DEPTH STATISTICS ---")
    for sc_type, stats in sorted(
        report.get("nesting_depth_stats", {}).items(),
        key=lambda x: x[1].get("max", 0),
        reverse=True,
    )[:10]:
        max_val = stats.get("max", 0)
        avg = stats.get("avg", 0)
        print(f"{sc_type}: max depth {max_val} (avg: {avg:.1f})")

    print("\n--- UNUSUAL PATTERNS ---")
    for pattern in report.get("unusual_patterns", [])[:20]:
        print(f"- {pattern}")


def _save_report(report: _ReportDict, output_file: Path) -> None:
    output_file.write_text(json.dumps(report, indent=2))
    print(f"\nDetailed report saved to {output_file}")


def _main() -> None:
    parser = argparse.ArgumentParser(description="Analyze Divi shortcodes in WordPress content")
    parser.add_argument(
        "--output",
        type=str,
        default="shortcode_analysis_report.json",
        help="Output file for the detailed report",
    )
    args = parser.parse_args()
    output_file = Path(args.output)
    content_by_type = _load_content_data()
    analysis_data = _analyze_content_data(content_by_type)
    report = _generate_report(analysis_data)
    _print_report(report)
    _save_report(report, output_file)


if __name__ == "__main__":
    _main()
