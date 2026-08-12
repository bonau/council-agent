"""Unit tests for ANSI-stripped CLI text helpers."""

from conftest import visible_cli_text


def test_visible_cli_text_rejoins_rich_split_long_options() -> None:
    raw = (
        "\x1b[1;36m-\x1b[0m\x1b[1;36m-yes\x1b[0m "
        "\x1b[1;36m-\x1b[0m\x1b[1;36m-trust-tier\x1b[0m"
    )
    visible = visible_cli_text(raw)
    assert "--yes" not in raw
    assert "--trust-tier" not in raw
    assert "--yes" in visible
    assert "--trust-tier" in visible
