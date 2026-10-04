from datetime import date

from lotto_lab.domain import GameCode
from lotto_lab.draw_history.importer import DrawCsvImporter


def test_csv_importer_accepts_codes_and_names_and_reports_bad_rows(tmp_path) -> None:
    source = tmp_path / "draws.csv"
    source.write_text(
        "game,date,n1,n2,n3,n4,n5,n6\n"
        "6/42,2026-01-01,1,2,3,4,5,42\n"
        "Mega Lotto 6/45,01/02/2026,6,7,8,9,10,45\n"
        "6/42,2026-01-03,1,1,2,3,4,5\n",
        encoding="utf-8",
    )

    result = DrawCsvImporter().parse(source)

    assert len(result.draws) == 2
    assert result.draws[0].game_code == GameCode.LOTTO_6_42
    assert result.draws[1].draw_date == date(2026, 1, 2)
    assert result.issues[0].row_number == 4
    assert "distinct" in result.issues[0].message


def test_csv_importer_requires_documented_columns(tmp_path) -> None:
    source = tmp_path / "invalid.csv"
    source.write_text("game,date,numbers\n6/42,2026-01-01,1 2 3 4 5 6\n", encoding="utf-8")

    try:
        DrawCsvImporter().parse(source)
    except ValueError as exc:
        assert "Missing CSV columns" in str(exc)
    else:
        raise AssertionError("Expected missing-column error")

