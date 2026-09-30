import pytest

from walldye.tools import metadata, paths
from walldye.tools.lint.words import color_words, copy, docstring, sentences

# Committed copy that breaks a rule, pending the owner's rewrite; delete an entry once its
# meta.yaml is fixed.
KNOWN: dict[str, list[str]] = {}


@pytest.mark.parametrize("slug", paths.slugs())
def test_catalog_copy(slug):
    assert copy(metadata.load_meta(slug)) == KNOWN.get(slug, [])


def test_color_words_but_not_token_names():
    assert color_words("A terracotta disc on Grey ground, lit in ORANGE_DARK and BLUE.") == {
        "grey",
        "terracotta",
    }
    assert copy({"title": "Red moon"}) == ["title: color words red"]
    assert copy({"notes": "Drawn in amber."}) == ["notes: color words amber"]
    assert color_words("reddish Blueprint") == set()
    assert color_words("Greys and whites under the ambers; GREYS, BLUES, crimsons") == {
        "ambers",
        "crimsons",
        "greys",
        "whites",
    }


def test_descriptions_and_alt_texts_are_short():
    assert copy({"description": " ".join(["dot"] * 21)}) == ["description: 21 words, over 20"]
    assert copy({"alt": " ".join(["dot"] * 26)}) == ["alt: 26 words, over 25"]
    assert copy({"description": "One line. Two lines."}) == ["description: 2 sentences, over 1"]
    assert copy({"description": "A lamp drawn as Fig. 1 of a patent."}) == []
    assert [sentences(t) for t in ("One. Two", "No stop", "Ends here.", "Ask? Yes!")] == [
        2,
        1,
        1,
        2,
    ]


def test_only_the_alt_text_describes_the_highlight():
    assert copy({"description": "A lamp with its filament lit."}) == [
        'description: describes the picture "lit" (the alt text does)'
    ]
    assert copy({"alt": "A lamp with its filament lit.", "notes": "The filament is lit."}) == []
    assert copy({"alt": "Clocks, one picked out."}) == [
        'alt: "picked out" (say what the set-apart thing is or shows)'
    ]


def test_descriptions_leave_credit_to_the_sources():
    assert copy({"description": "A bamboo grove, after East Asian ink painting."}) == [
        'description: credit "after East" (sources and notes carry it)'
    ]
    assert copy({"description": "Smoke turns turbulent after a few centimeters."}) == []


def test_titles_name_the_subject():
    assert copy({"title": "De Jong veil"}) == ['title: imagery "veil" (name the subject)']
    assert copy({"description": "Iron filings in a veil."}) == []


def test_docstrings_are_one_plain_line():
    assert docstring("A radio telescope in Atkinson dither.") == []
    assert docstring("A dish.\n\nIn dither.") == [
        "more than one line (the subject and the technique)"
    ]
    assert docstring("A take on Riley in rows.") == ['gesture phrase "A take on"']


@pytest.mark.parametrize(
    ("meta", "found"),
    [
        ({"description": "A stunning, timeless grid."}, 'description: evaluative adjective "stunning"'),
        ({"description": "A grid that quietly delves into order."}, 'description: stock phrase "quietly"'),
        ({"notes": "Each seed picks a preset."}, 'notes: internal term "seed"'),
        ({"notes": "Released under CC0."}, 'notes: license identifier "CC0"'),
        ({"notes": "Within 2 RGB units."}, 'notes: machinery number "RGB units"'),
        ({"description": "Squares 12px wide."}, 'description: machinery number "12px"'),
        ({"description": "One square in the accent."}, 'description: theme role as a noun "the accent"'),
        ({"notes": "This variant sets one param."}, 'notes: internal term "variant"'),
        ({"notes": "It nods to Hasui's prints."}, 'notes: gesture phrase "nods to"'),
        ({"alt": "A grid that evokes rain."}, 'alt: gesture phrase "evokes"'),
    ],
)  # fmt: skip
def test_banned_phrases(meta, found):
    assert copy(meta) == [found]


def test_accent_as_an_adjective_is_fine():
    assert copy({"alt": "Square accent cells, one set apart."}) == []


def test_version_labels_descriptions_and_alt_texts():
    long = " ".join(["dot"] * 21)
    assert copy({
        "variants": {
            "default": {"label": "Seed 11"},
            "late": {"label": "Red sky", "description": "A stunning sweep."},
            "open-sea": {"label": "Open water", "description": long, "alt": "Sea. Sky."},
        }
    }) == [
        'variants.default.label: internal term "Seed"',
        "variants.late.label: color words red",
        'variants.late.description: evaluative adjective "stunning"',
        "variants.open-sea.description: 21 words, over 20",
        "variants.open-sea.alt: 2 sentences, over 1",
    ]  # fmt: skip
    assert copy({"variants": {"late": {"label": "Params"}}}) == [
        'variants.late.label: internal term "Params"'
    ]
