"""Static lints, each returning what it finds as messages: `source` for design.py, `templates`
for a rendered SVG, `piece` for meta.yaml and the folder, `words` for the words visitors
read."""

from walldye.tools.lint import piece, source, templates, words

__all__ = ["piece", "source", "templates", "words"]
