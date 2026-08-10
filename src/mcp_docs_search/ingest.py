"""Markdown ingestion: heading-based chunking."""

import re
from dataclasses import dataclass

MIN_SECTION_LENGTH = 100
MAX_SECTION_LENGTH = 1500


@dataclass(frozen=True)
class Chunk:
    heading_path: tuple[str, ...]
    level: int
    text: str
    start_line: int


def chunk_markdown(source: str) -> list[Chunk]:
    """Parse markdown text into heading-based chunks.

    Args:
        source: Markdown text to parse.

    Returns:
        List of chunks with heading path, level, text, and start line.
    """
    lines = _normalise(source)
    sections = _split_sections(lines)
    sections = _merge_short_sections(sections)
    return _emit_chunks(sections)


def format_heading_path(rel_path: str, heading_path: tuple[str, ...]) -> str:
    """Format a document path and heading path tuple for display.

    Args:
        rel_path: Relative path of the markdown file (e.g. "guide.md").
        heading_path: Tuple of heading titles (e.g. ("Setup", "Config")).

    Returns:
        Formatted string like "guide.md > Setup > Config", or just "guide.md"
        if heading_path is empty.
    """
    if not heading_path:
        return rel_path
    return " > ".join([rel_path, *heading_path])


def _normalise(raw: str) -> list[str]:
    """Normalise line endings and drop leading/trailing blank lines."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    while lines and lines[0].strip() == "":
        lines.pop(0)
    while lines and lines[-1].strip() == "":
        lines.pop()
    return lines


@dataclass
class _Section:
    heading_markdown: str
    heading_path: tuple[str, ...]
    level: int
    start_line: int
    content: list[tuple[int, str]]


def _split_sections(lines: list[str]) -> list[_Section]:
    """Turn raw lines into sections, honouring fenced code blocks."""
    sections: list[_Section] = []
    stack: list[tuple[int, str]] = []
    cur: _Section | None = None
    content_lines: list[tuple[int, str]] = []
    fence: tuple[str, int] | None = None

    for i, line in enumerate(lines):
        line_no = i + 1
        if fence is not None:
            content_lines.append((line_no, line))
            if _fence_closes(line, fence[0], fence[1]):
                fence = None
            continue

        info = _fence_info(line)
        if info is not None:
            content_lines.append((line_no, line))
            fence = info
            continue

        match = _HEADING_RE.match(line)
        if match is not None:
            if cur is not None:
                sections.append(_Section(
                    heading_markdown=cur.heading_markdown,
                    heading_path=cur.heading_path,
                    level=cur.level,
                    start_line=cur.start_line,
                    content=content_lines,
                ))
            level = len(match.group(2))
            text = _strip_attr_list(_strip_trailing_hashes(match.group(3).strip()))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, text))
            cur = _Section(
                heading_markdown=line,
                heading_path=tuple(t for _, t in stack),
                level=level,
                start_line=i + 1,
                content=[],
            )
            content_lines = []
            continue

        content_lines.append((line_no, line))
        if cur is None:
            cur = _Section(
                heading_markdown="",
                heading_path=(),
                level=0,
                start_line=1,
                content=[],
            )

    if cur is not None:
        sections.append(_Section(
            heading_markdown=cur.heading_markdown,
            heading_path=cur.heading_path,
            level=cur.level,
            start_line=cur.start_line,
            content=content_lines,
        ))

    return sections


def _strip_trailing_hashes(text: str) -> str:
    """Remove trailing ATX closing sequence (e.g. '## Setup ##' -> 'Setup')."""
    return re.sub(r"\s+#{1,6}\s*$", "", text).strip()


def _strip_attr_list(text: str) -> str:
    """Remove trailing MkDocs attr_list block (e.g. 'Setup { #setup }' -> 'Setup')."""
    return re.sub(r"\s*\{[^}]*\}\s*$", "", text).strip()


_HEADING_RE = re.compile(r"^( {0,3})(#{1,6})[ \t]+(.*)$")


def _fence_info(line: str) -> tuple[str, int] | None:
    """Return (fence char, run length) if line opens a fenced block."""
    indent = len(line) - len(line.lstrip(" "))
    if indent > 3:
        return None
    s = line[indent:]
    if not s or s[0] not in "`~":
        return None
    run = len(s) - len(s.lstrip(s[0]))
    if run < 3:
        return None
    return (s[0], run)


def _fence_closes(line: str, char: str, min_len: int) -> bool:
    indent = len(line) - len(line.lstrip(" "))
    if indent > 3:
        return False
    s = line[indent:]
    run = len(s) - len(s.lstrip(char))
    return run >= min_len and s[run:].strip() == ""


def _merge_short_sections(sections: list[_Section]) -> list[_Section]:
    """Merge sections whose body is shorter than MIN_SECTION_LENGTH."""
    if len(sections) <= 1:
        return sections

    result = sections
    changed = True
    while changed:
        changed = False
        for i in range(len(result)):
            if _body_length(result[i]) >= MIN_SECTION_LENGTH:
                continue
            if len(result) == 1:
                break
            if i == len(result) - 1:
                _absorb(result[i - 1], result[i])
                result.pop(i)
            else:
                _absorb(result[i], result[i + 1])
                result.pop(i + 1)
            changed = True
            break
    return result


def _body_length(section: _Section) -> int:
    """Return length of section body after stripping (no heading path)."""
    if not section.content:
        return 0
    text = "\n".join(l for _, l in section.content).strip()
    return len(text)


def _absorb(target: _Section, other: _Section) -> None:
    """Fold ``other`` into ``target``, keeping target's path and start line."""
    # Build content: target content + other's heading line + other content
    new_content = list(target.content)
    if other.heading_markdown:
        new_content.append((other.start_line, other.heading_markdown))
    new_content.extend(other.content)
    target.content = new_content


def _emit_chunks(sections: list[_Section]) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section in sections:
        chunks.extend(_split_section(section))
    return chunks


def _split_section(section: _Section) -> list[Chunk]:
    """Split a section into chunks, respecting MAX_SECTION_LENGTH."""
    if not section.content:
        return [Chunk(
            heading_path=section.heading_path,
            level=section.level,
            text="",
            start_line=section.start_line,
        )]

    body_lines = [l for _, l in section.content]
    body = "\n".join(body_lines).strip()
    if not body:
        return [Chunk(
            heading_path=section.heading_path,
            level=section.level,
            text="",
            start_line=section.start_line,
        )]

    if len(body) <= MAX_SECTION_LENGTH:
        return [Chunk(
            heading_path=section.heading_path,
            level=section.level,
            text=body,
            start_line=section.start_line,
        )]

    paragraphs = _split_paragraphs(section.content)
    return _group_paragraphs(section, paragraphs)


def _split_paragraphs(content: list[tuple[int, str]]) -> list[list[tuple[int, str]]]:
    """Split content into paragraphs, respecting fenced code blocks."""
    paragraphs: list[list[tuple[int, str]]] = []
    cur: list[tuple[int, str]] = []
    fence: tuple[str, int] | None = None

    for line_no, line in content:
        if fence is not None:
            cur.append((line_no, line))
            if _fence_closes(line, fence[0], fence[1]):
                fence = None
            continue

        info = _fence_info(line)
        if info is not None:
            if cur:
                paragraphs.append(cur)
                cur = []
            cur.append((line_no, line))
            fence = info
            continue

        if line.strip() == "":
            if cur:
                paragraphs.append(cur)
                cur = []
            continue

        cur.append((line_no, line))

    if cur:
        paragraphs.append(cur)

    return paragraphs


def _group_paragraphs(section: _Section, paragraphs: list[list[tuple[int, str]]]) -> list[Chunk]:
    """Group paragraphs into chunks respecting MAX_SECTION_LENGTH."""
    chunks: list[Chunk] = []
    current_paras: list[list[tuple[int, str]]] = []

    for para in paragraphs:
        para_text = "\n".join(l for _, l in para).strip()
        if not current_paras:
            current_paras.append(para)
            continue

        # Check if adding this paragraph would exceed limit
        candidate_text = "\n\n".join(
            "\n".join(l for _, l in p).strip() for p in [*current_paras, para]
        )
        if len(candidate_text) > MAX_SECTION_LENGTH:
            # Emit current group
            group_text = "\n\n".join(
                "\n".join(l for _, l in p).strip() for p in current_paras
            )
            first_line = current_paras[0][0][0]
            chunks.append(Chunk(
                heading_path=section.heading_path,
                level=section.level,
                text=group_text,
                start_line=first_line,
            ))
            current_paras = [para]
        else:
            current_paras.append(para)

    if current_paras:
        group_text = "\n\n".join(
            "\n".join(l for _, l in p).strip() for p in current_paras
        )
        first_line = current_paras[0][0][0]
        chunks.append(Chunk(
            heading_path=section.heading_path,
            level=section.level,
            text=group_text,
            start_line=first_line,
        ))

    return chunks