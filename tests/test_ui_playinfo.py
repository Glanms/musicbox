from NEMbox.scrollstring import truelen
from NEMbox.ui import playinfo_song_start


class FakeScreen:
    def __init__(self):
        self.writes = []

    def move(self, *_args):
        pass

    def clrtoeol(self):
        pass

    def refresh(self):
        pass

    def addstr(self, *args):
        self.writes.append(
            tuple(arg.decode("utf-8") if isinstance(arg, bytes) else arg for arg in args)
        )


def test_playinfo_song_start_accounts_for_long_quality_label():
    prefix = "♫  ♪ ♫  ♪ "
    quality = "LOSSLESS"

    start = playinfo_song_start(0, prefix, quality)

    assert start == truelen(prefix + quality) + 2
    assert start > 18


def _playinfo_view(screen, volume=60, content_width=80, endcol=80):
    from NEMbox import ui

    view = object.__new__(ui.Ui)
    view.screen = screen
    view.indented_startcol = 0
    view.indented_endcol = endcol - 3
    view.startcol = 3
    view.endcol = endcol
    view.content_width = content_width
    view.space = " - "
    view.storage = type("StorageStub", (), {"database": {"player_info": {}}})()
    if volume is not None:
        view.storage.database["player_info"]["playing_volume"] = volume
    return view


def test_build_playinfo_renders_volume_on_top_right(monkeypatch):
    from NEMbox import ui

    monkeypatch.setattr(ui.curses, "noecho", lambda: None)
    monkeypatch.setattr(ui, "_safe_curs_set", lambda _visibility: None)
    monkeypatch.setattr(ui.curses, "color_pair", lambda pair: pair)
    screen = FakeScreen()
    view = _playinfo_view(screen)

    view.build_playinfo("Song", "Artist", "Album", "48kHz", 0)

    assert any("音量 60%" in str(args) for args in screen.writes)


def test_build_playinfo_omits_volume_when_terminal_is_too_narrow(monkeypatch):
    from NEMbox import ui

    monkeypatch.setattr(ui.curses, "noecho", lambda: None)
    monkeypatch.setattr(ui, "_safe_curs_set", lambda _visibility: None)
    monkeypatch.setattr(ui.curses, "color_pair", lambda pair: pair)
    screen = FakeScreen()
    view = _playinfo_view(screen, content_width=10, endcol=13)

    view.build_playinfo("A very long song", "Artist", "Album", "48kHz", 0)

    assert not any("音量" in str(args) for args in screen.writes)


def test_build_playinfo_handles_missing_volume(monkeypatch):
    from NEMbox import ui

    monkeypatch.setattr(ui.curses, "noecho", lambda: None)
    monkeypatch.setattr(ui, "_safe_curs_set", lambda _visibility: None)
    monkeypatch.setattr(ui.curses, "color_pair", lambda pair: pair)
    screen = FakeScreen()
    view = _playinfo_view(screen, volume=None)

    view.build_playinfo("Song", "Artist", "Album", "48kHz", 0)

    assert not any("音量" in str(args) for args in screen.writes)


def test_build_playinfo_handles_invalid_volume(monkeypatch):
    from NEMbox import ui

    monkeypatch.setattr(ui.curses, "noecho", lambda: None)
    monkeypatch.setattr(ui, "_safe_curs_set", lambda _visibility: None)
    monkeypatch.setattr(ui.curses, "color_pair", lambda pair: pair)
    screen = FakeScreen()
    view = _playinfo_view(screen, volume="not-a-number")

    view.build_playinfo("Song", "Artist", "Album", "48kHz", 0)

    assert not any("音量" in str(args) for args in screen.writes)
