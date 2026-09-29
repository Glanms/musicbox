from textual.widgets import ContentSwitcher, DataTable, Footer, Label, Static

from NEMbox.textual_app import PlayerSnapshot, build_app
from NEMbox.textual_controller import TextualState


def test_player_snapshot_formats_progress_and_queue_count():
    snapshot = PlayerSnapshot(
        song_name="求你别离开我",
        artist="大牛",
        album_name="未完成",
        quality="48kHz",
        elapsed=255,
        duration=295,
        queue=(
            {"song_name": "海呐你", "artist": "马也_Crabbit", "album_name": "海呐你"},
            {"song_name": "求你别离开我", "artist": "大牛", "album_name": "未完成"},
        ),
        index=1,
    )

    assert snapshot.progress == 255 / 295
    assert snapshot.time_text == "04:15 / 04:55"
    assert snapshot.queue_count_text == "共 2 首"


import asyncio


def test_textual_app_renders_now_playing_and_queue_rows():
    app = build_app(
        PlayerSnapshot(
            song_name="求你别离开我",
            artist="大牛",
            album_name="未完成",
            quality="48kHz",
            elapsed=255,
            duration=295,
            queue=(
                {
                    "song_name": "海呐你",
                    "artist": "马也_Crabbit",
                    "album_name": "海呐你",
                },
                {"song_name": "求你别离开我", "artist": "大牛", "album_name": "未完成"},
            ),
            index=1,
        )
    )

    async def run_test(pilot):
        assert app.query_one("#song-title", Label).content == "求你别离开我"
        assert app.query_one("#artist", Label).content == "大牛  ·  未完成"
        assert app.query_one("#queue-count", Static).content == "共 2 首"
        assert app.query_one("DataTable", DataTable).row_count == 2

    asyncio.run(_run_app_test(app, run_test))


def test_textual_app_uses_compact_design_layout():
    app = build_app(
        PlayerSnapshot(
            song_name="求你别离开我",
            artist="大牛",
            album_name="未完成",
            quality="48kHz",
            queue=({"song_name": "求你别离开我", "artist": "大牛"},),
        )
    )

    async def run_test(pilot):
        topbar = app.query_one("#topbar")
        now_playing = app.query_one("#now-playing")
        art = app.query_one("#art")
        source = app.query_one("#source")
        queue = app.query_one("#queue-panel")
        footer = app.query_one(Footer)

        assert app.query_one("#quality", Static).content == "48kHz"
        assert "求你别离开我" in str(app.query_one("#topbar-current", Static).content)
        assert (
            app.query_one("#source-path", Static).content == "歌单来源  >  网易云音乐"
        )
        assert app.query_one("#queue-title", Static).content == "♫  播放列表"
        assert topbar.region.height == 4
        assert now_playing.region.height == 13
        assert art.region.width == 22
        assert source.region.height == 3
        assert queue.region.height >= 10
        assert footer.region.height == 1
        assert footer.styles.background.hex.lower() == "#05090c"

    asyncio.run(_run_app_test(app, run_test, size=(120, 40)))


def test_textual_app_stays_inside_narrow_terminal():
    app = build_app(
        PlayerSnapshot(
            song_name="窄屏测试歌曲",
            artist="测试歌手",
            album_name="测试专辑",
            queue=({"song_name": "窄屏测试歌曲", "artist": "测试歌手"},),
        )
    )

    async def run_test(pilot):
        assert app.query_one("#root").has_class("compact")
        for widget_id in ("#topbar", "#now-playing", "#source", "#queue-panel"):
            region = app.query_one(widget_id).region
            assert region.right <= 80
            assert region.bottom <= 24
        assert app.query_one(Footer).region.bottom <= 24

    asyncio.run(_run_app_test(app, run_test, size=(80, 24)))


def test_textual_app_routes_space_to_live_controller():
    class Controller:
        state = TextualState(
            current_song={"song_name": "现场", "artist": "歌手", "album_name": "专辑"},
            queue=({"song_id": 1, "song_name": "现场"},),
        )
        calls = []
        keymap = {"playPause": " "}

        def toggle(self):
            self.calls.append("toggle")

        def refresh(self):
            return self.state

    controller = Controller()
    app = build_app(controller=controller)

    async def run_test(pilot):
        await pilot.press("space")
        assert controller.calls == ["toggle"]

    asyncio.run(_run_app_test(app, run_test))


def test_textual_app_supports_legacy_navigation_and_back_keys():
    app = build_app(
        PlayerSnapshot(
            queue=(
                {"song_id": 1, "song_name": "第一首"},
                {"song_id": 2, "song_name": "第二首"},
            )
        )
    )

    async def run_test(pilot):
        table = app.query_one("#queue-table", DataTable)
        await pilot.press("j")
        assert table.cursor_row == 1
        await pilot.press("k")
        assert table.cursor_row == 0

        await pilot.press("m")
        assert app.query_one("#views", ContentSwitcher).current == "menu-panel"
        await pilot.press("escape")
        assert app.query_one("#views", ContentSwitcher).current == "dashboard"

    asyncio.run(_run_app_test(app, run_test))


def test_textual_app_browser_pages_use_back_stack():
    app = build_app(PlayerSnapshot(song_name="当前歌曲"))

    async def run_test(pilot):
        app._show_browser_items("歌词：当前歌曲", ("第一句", "第二句"))
        assert app.query_one("#views", ContentSwitcher).current == "browser-panel"
        assert app.query_one("#browser-list").children

        await pilot.press("escape")
        assert app.query_one("#views", ContentSwitcher).current == "dashboard"

    asyncio.run(_run_app_test(app, run_test))


async def _run_app_test(app, callback, size=(120, 40)):
    async with app.run_test(size=size) as pilot:
        await callback(pilot)
