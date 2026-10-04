from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from lotto_lab.domain import GameCode
from lotto_lab.schedule import ScheduleService, ScheduledGame


def test_regular_wednesday_schedule_uses_manila_time():
    service = ScheduleService()
    now = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
    draws = service.today(now)
    assert [draw.game.code for draw in draws] == [GameCode.GRAND_LOTTO_6_55, GameCode.MEGA_LOTTO_6_45]
    assert all(draw.status == "UPCOMING" for draw in draws)
    assert all(draw.at.isoformat().endswith("+08:00") for draw in draws)
    assert all(draw.status == "DRAW_COMPLETED" for draw in service.today(datetime(2026, 9, 30, 14, tzinfo=timezone.utc)))


def test_empty_day_finds_next_active_draw():
    service = ScheduleService((ScheduledGame(GameCode.LOTTO_6_42, (1,), time(21)),))
    now = datetime(2026, 9, 30, 12, tzinfo=ZoneInfo("Asia/Manila"))
    assert service.today(now) == ()
    assert service.next_draw(now).at.date().isoformat() == "2026-10-06"


def test_local_schedule_override(tmp_path):
    path = tmp_path / "schedule.json"
    path.write_text('{"games":[{"id":"6/42","drawDays":[2],"drawTime":"20:30","active":true}]}')
    service = ScheduleService.from_json(path)
    assert len(service.today(datetime(2026, 9, 30, 12, tzinfo=ZoneInfo("Asia/Manila")))) == 1
    assert service.games[0].draw_time == time(20, 30)
