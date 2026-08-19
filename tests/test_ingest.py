"""Casos limite de chunking. Los valores esperados estan verificados.

Las reglas que verifica cada bloque:
  R1  encabezados dentro de bloques cercados no cuentan
  R2  fusionar primero, partir despues
  R3  el chunk fusionado conserva la ruta y el start_line de la seccion superior,
      y el encabezado absorbido se mantiene como texto
  R4  seccion corta al final -> fusion hacia atras
"""

from mcp_docs_search.ingest import chunk_markdown, format_heading_path

MIN_CHARS = 100
MAX_CHARS = 1500


# --- R3: fusion aislada, sin que intervenga el split --------------------------

def test_merge_keeps_upper_path_start_line_and_absorbed_heading() -> None:
    source = (
        "# Intro\n"                                       # linea 1
        "Texto breve.\n"                                  # linea 2  (12 chars < 100)
        "\n"
        "# Cuerpo\n"                                       # linea 4
        "Este cuerpo tiene mas de cien caracteres, de modo que no se fusiona "
        "con nada mas y el total no supera el limite superior.\n"
    )
    chunks = chunk_markdown(source)

    assert len(chunks) == 1
    c = chunks[0]
    assert c.heading_path == ("Intro",)     # ruta de la seccion SUPERIOR
    assert c.level == 1
    assert c.start_line == 1                # linea del encabezado superior
    assert c.text.startswith("Texto breve.")
    assert "# Cuerpo" in c.text             # el encabezado absorbido sigue siendo texto
    assert "Cuerpo" not in c.heading_path   # y NO entra en la ruta


# --- R2: el caso discriminante del orden -------------------------------------

def _long_body(n_paragraphs: int) -> str:
    return "\n\n".join(
        f"Parrafo numero {n}. " + "relleno " * 25 for n in range(1, n_paragraphs + 1)
    )


def test_merge_happens_before_split() -> None:
    source = "# Intro\nTexto breve.\n\n# Cuerpo\n" + _long_body(7) + "\n"
    chunks = chunk_markdown(source)

    # se fusiono y luego se partio: >1 chunk, todos con la ruta de Intro
    assert len(chunks) > 1
    assert all(c.heading_path == ("Intro",) for c in chunks)
    assert all(c.level == 1 for c in chunks)

    # el encabezado absorbido viaja en el PRIMER trozo, no en la ruta
    assert "# Cuerpo" in chunks[0].text

    # ningun trozo excede el limite, y los start_line son crecientes y unicos
    assert all(len(c.text) <= MAX_CHARS for c in chunks)
    lines = [c.start_line for c in chunks]
    assert lines == sorted(lines)
    assert len(set(lines)) == len(lines)


def test_split_does_not_cut_inside_a_paragraph() -> None:
    source = "# Solo\n" + _long_body(7) + "\n"
    for c in chunk_markdown(source):
        assert not c.text.startswith("relleno")   # ningun trozo empieza a media frase
        assert c.text.rstrip().endswith("relleno")


# --- R4: seccion corta al final ----------------------------------------------

def test_trailing_short_section_merges_backwards() -> None:
    source = (
        "# Uno\n"
        "Cuerpo con longitud suficiente para no fusionarse, mas de cien caracteres "
        "de sobra para superar el umbral minimo establecido.\n"
        "\n"
        "# Dos\n"
        "Corto.\n"
    )
    chunks = chunk_markdown(source)

    assert len(chunks) == 1
    assert chunks[0].heading_path == ("Uno",)
    assert chunks[0].start_line == 1
    assert "# Dos" in chunks[0].text
    assert "Corto." in chunks[0].text


def test_single_short_section_is_kept_as_is() -> None:
    chunks = chunk_markdown("# Solo\nCorto.\n")
    assert len(chunks) == 1
    assert chunks[0].heading_path == ("Solo",)
    assert chunks[0].text == "Corto."


# --- R1: bloques cercados ----------------------------------------------------

def test_heading_inside_fenced_block_is_not_a_heading() -> None:
    source = "# Setup\n\n```bash\n# instala las dependencias\nuv sync\n```\n"
    chunks = chunk_markdown(source)

    assert len(chunks) == 1
    assert chunks[0].heading_path == ("Setup",)
    assert "# instala las dependencias" in chunks[0].text


def test_tilde_fence_and_unclosed_fence() -> None:
    assert len(chunk_markdown("# A\n\n~~~\n# no soy encabezado\n~~~\n")) == 1
    assert len(chunk_markdown("# A\n\n```\n# no soy encabezado\nsin cerrar\n")) == 1


# --- MkDocs attr_list: "{ #anchor }" no es parte del titulo ----------------

def test_attr_list_suffix_stripped_from_heading() -> None:
    cases = [
        ("## Quotes { #quotes }\n\nBody.\n", ("Quotes",)),
        ("## Setup { #setup .class }\n\nBody.\n", ("Setup",)),
        ("## Setup { #setup } ##\n\nBody.\n", ("Setup",)),
        ("## Use {braces} in text\n\nBody.\n", ("Use {braces} in text",)),
        ("## Setup\n\nBody.\n", ("Setup",)),
    ]
    for source, expected_path in cases:
        chunks = chunk_markdown(source)
        assert len(chunks) == 1, source
        assert chunks[0].heading_path == expected_path, source


# --- degenerate input ---------------------------------------------------------

def test_empty_source_produces_no_chunks() -> None:
    assert chunk_markdown("") == []


def test_whitespace_only_source_produces_no_chunks() -> None:
    assert chunk_markdown("   \n\n\t\n  ") == []


def test_text_without_any_heading_is_still_one_chunk() -> None:
    """A README fragment with no heading must not be dropped silently."""
    source = "Just a paragraph. " * 20
    chunks = chunk_markdown(source)

    assert len(chunks) == 1
    assert chunks[0].heading_path == ()
    assert "Just a paragraph." in chunks[0].text


def test_preamble_before_the_first_heading_is_kept() -> None:
    source = "Intro text before any heading. " * 8 + "\n\n# Title\n\n" + "body " * 40
    chunks = chunk_markdown(source)

    assert any("Intro text before any heading." in c.text for c in chunks)


def test_crlf_and_cr_line_endings_normalise() -> None:
    body = "content " * 30
    lf = chunk_markdown(f"# Title\n\n{body}\n")
    crlf = chunk_markdown(f"# Title\r\n\r\n{body}\r\n")
    cr = chunk_markdown(f"# Title\r\r{body}\r")

    assert [c.text for c in lf] == [c.text for c in crlf] == [c.text for c in cr]


def test_deep_heading_levels_are_chunked() -> None:
    """SPEC names #/##/### but real corpora go deeper; nothing may be lost."""
    source = "".join(
        f"{'#' * level} Level {level}\n\n{'body ' * 40}\n\n" for level in range(1, 7)
    )
    chunks = chunk_markdown(source)

    assert len(chunks) == 6
    assert chunks[-1].level == 6
    assert chunks[-1].heading_path[-1] == "Level 6"


def test_heading_path_nests_through_levels() -> None:
    source = (
        "# Guide\n\n" + "a" * 150 + "\n\n"
        "## Installation\n\n" + "b" * 150 + "\n\n"
        "### Configuration\n\n" + "c" * 150 + "\n"
    )
    chunks = chunk_markdown(source)
    paths = [c.heading_path for c in chunks]

    assert ("Guide",) in paths
    assert ("Guide", "Installation") in paths
    assert ("Guide", "Installation", "Configuration") in paths


def test_format_heading_path_without_headings_is_just_the_file() -> None:
    assert format_heading_path("guide.md", ()) == "guide.md"


def test_format_heading_path_joins_with_the_separator() -> None:
    assert (
        format_heading_path("guide.md", ("Setup", "Config"))
        == "guide.md > Setup > Config"
    )


# --- splitting ----------------------------------------------------------------

def test_oversized_section_splits_into_several_chunks() -> None:
    paragraph = "word " * 100
    source = "# Title\n\n" + "\n\n".join([paragraph] * 8)
    chunks = chunk_markdown(source)

    assert len(chunks) > 1
    assert all(c.heading_path == ("Title",) for c in chunks)


def test_split_chunks_keep_every_paragraph() -> None:
    """Splitting must lose nothing — the failure mode is silent content loss."""
    paragraphs = [f"paragraph{i} " + "filler " * 60 for i in range(10)]
    source = "# Title\n\n" + "\n\n".join(paragraphs)

    rejoined = " ".join(c.text for c in chunk_markdown(source))

    for i in range(10):
        assert f"paragraph{i}" in rejoined


def test_single_oversized_paragraph_is_not_cut() -> None:
    """An unsplittable paragraph stays whole rather than being cut mid-sentence."""
    paragraph = "word " * 600
    chunks = chunk_markdown("# Title\n\n" + paragraph)

    assert len(chunks) == 1
    assert len(chunks[0].text) > MAX_CHARS


def test_code_block_is_never_cut_in_half() -> None:
    fence = "```python\n" + "x = 1\n" * 300 + "```"
    chunks = chunk_markdown("# Title\n\n" + fence)

    for chunk in chunks:
        assert chunk.text.count("```") % 2 == 0
