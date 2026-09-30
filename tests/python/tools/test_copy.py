import pytest

from walldye.tools import metadata, paths
from walldye.tools.lint.words import color_words, copy, sentences

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


def test_descriptions_are_short():
    long = " ".join(["dot"] * 31)
    assert copy({"description": long}) == ["description: 31 words, over 30"]
    assert copy({"description": "One line. Two lines. Three lines."}) == [
        "description: 3 sentences, over 2"
    ]
    assert (
        copy({"description": "A lamp drawn as Fig. 1 of a patent. Only the filament is lit."}) == []
    )
    assert [sentences(t) for t in ("One. Two", "No stop", "Ends here.", "Ask? Yes!")] == [
        2,
        1,
        1,
        2,
    ]


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
    ],
)  # fmt: skip
def test_banned_phrases(meta, found):
    assert copy(meta) == [found]


def test_accent_as_an_adjective_is_fine():
    assert copy({"description": "Square accent cells, one picked out."}) == []


def test_version_labels_and_descriptions():
    long = " ".join(["dot"] * 31)
    assert copy({
        "variants": {
            "default": {"label": "Seed 11"},
            "late": {"label": "Red sky", "description": "A stunning sweep."},
            "open-sea": {"label": "Open water", "description": long},
        }
    }) == [
        'variants.default.label: internal term "Seed"',
        "variants.late.label: color words red",
        'variants.late.description: evaluative adjective "stunning"',
        "variants.open-sea.description: 31 words, over 30",
    ]  # fmt: skip
    assert copy({"variants": {"late": {"label": "Params"}}}) == [
        'variants.late.label: internal term "Params"'
    ]
