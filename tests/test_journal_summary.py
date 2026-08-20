from hermes_trader.journal import Journal


def test_set_summary_overwrites_previous_summary(tmp_path):
    journal = Journal(tmp_path / "journal.sqlite")
    first = "older trades lost money in choppy markets"
    second = "newer summary: momentum works after 09:30 UTC"

    assert journal.get_summary() == ""
    journal.set_summary(first)
    assert journal.get_summary() == first

    journal.set_summary(second)
    assert journal.get_summary() == second


def test_should_refresh_summary_tick_does_not_fire_for_zero_interval():
    assert Journal.should_refresh_summary_tick(60, every_n=0) is False


def test_should_refresh_summary_tick_does_not_fire_for_negative_interval():
    assert Journal.should_refresh_summary_tick(60, every_n=-5) is False


def test_should_refresh_summary_tick_skips_tick_zero():
    assert Journal.should_refresh_summary_tick(0, every_n=5) is False


def test_should_refresh_summary_tick_fires_only_on_multiples():
    assert Journal.should_refresh_summary_tick(59, every_n=60) is False
    assert Journal.should_refresh_summary_tick(60, every_n=60) is True
    assert Journal.should_refresh_summary_tick(120, every_n=60) is True
    assert Journal.should_refresh_summary_tick(121, every_n=60) is False
