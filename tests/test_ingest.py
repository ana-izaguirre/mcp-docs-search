"""Casos limite de chunking. Los valores esperados estan verificados.

Las reglas que verifica cada bloque:
  R1  encabezados dentro de bloques cercados no cuentan
  R2  fusionar primero, partir despues
  R3  el chunk fusionado conserva la ruta y el start_line de la seccion superior,
      y el encabezado absorbido se mantiene como texto
  R4  seccion corta al final -> fusion hacia atras
"""

from mcp_docs_search.ingest import chunk_markdown

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
