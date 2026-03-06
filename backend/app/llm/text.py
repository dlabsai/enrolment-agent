def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n")
    lines = text.split("\n")
    result_lines: list[str] = []
    last_was_empty = False

    for line in lines:
        if not line.strip():
            if not last_was_empty:
                result_lines.append("")
                last_was_empty = True
        else:
            result_lines.append(line.lstrip())
            last_was_empty = False

    return "\n".join(result_lines).strip()
