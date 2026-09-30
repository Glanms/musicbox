from textual.widgets import Button, ContentSwitcher, DataTable, Label, ListView, Static

import NEMbox.textual_app as textual_app
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


def test_terminal_symbol_falls_back_when_encoding_cannot_render_glyph():
    assert textual_app.terminal_symbol("♥", "*", "ascii") == "*"
    assert textual_app.terminal_symbol("♥", "*", "utf-8") == "♥"


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


def test_textual_app_uses_reference_dashboard_layout():
    app = build_app(
        PlayerSnapshot(
            song_name="求你别离开我",
            artist="大牛",
            album_name="未完成",
            quality="48kHz",
            volume=75,
            mode="随机播放",
            elapsed=5,
            lyrics=("[00:01.00]第一句", "[00:10.00]第二句"),
            queue=({"song_name": "求你别离开我", "artist": "大牛"},),
        )
    )

    async def run_test(pilot):
        topbar = app.query_one("#topbar")
        now_playing = app.query_one("#now-playing")
        art = app.query_one("#art")
        sidebar = app.query_one("#sidebar")
        lyrics = app.query_one("#side-panel")
        queue = app.query_one("#queue-panel")
        shortcut_bar = app.query_one("#shortcut-bar")

        assert app.query_one("#quality", Static).content == "48kHz"
        assert app.query_one("#brand", Static).content == "▂▅▇  MusicBox"
        assert app.query_one("#volume-value", Static).content == "75%"
        assert app.query_one("#lyric-current", Label).content == "第一句"
        assert app.query_one("#lyric-next", Label).content == "第二句"
        assert app.query_one("#state", Label).content == "▶ 正在播放"
        assert app.query_one("#mode", Label).content == "⤨ 随机"
        assert app.query_one("#shuffle", Button).has_class("active")
        assert str(app.query_one("#play-toggle", Button).label) == "❚❚"
        assert "求你别离开我" in str(app.query_one("#topbar-current", Static).content)
        assert app.query_one("#topbar-current").styles.text_align == "center"
        assert (
            app.query_one("#topbar-current").region.right
            <= app.query_one("#volume").region.x
        )
        assert app.query_one("#queue-title", Static).content == "♫  播放列表"
        assert topbar.region.height == 4
        assert now_playing.region.height >= 16
        assert art.region.width >= 18
        assert sidebar.display is True
        assert lyrics.display is True
        sidebar_label = (
            app.query_one("#sidebar-list", ListView).children[0].query_one(Label)
        )
        assert sidebar_label.content == "♫  播放列表  1"
        assert app.query_one("#mode").region.right <= app.query_one("#time").region.x
        assert queue.region.height >= 8
        assert queue.region.y >= now_playing.region.bottom
        assert shortcut_bar.region.height == 1

    asyncio.run(_run_app_test(app, run_test, size=(140, 40)))


def test_textual_app_hides_only_sidebar_at_medium_width():
    app = build_app(PlayerSnapshot(queue=({"song_name": "歌曲"},)))

    async def run_test(pilot):
        assert app.query_one("#root").has_class("medium")
        assert app.query_one("#sidebar").display is False
        assert app.query_one("#side-panel").display is True
        assert (
            app.query_one("#queue-panel").region.bottom
            <= app.query_one("#notice").region.y
        )

    asyncio.run(_run_app_test(app, run_test, size=(100, 32)))


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
        assert app.query_one("#sidebar").display is False
        assert app.query_one("#side-panel").display is False
        for widget_id in (
            "#topbar",
            "#volume",
            "#lyric-current",
            "#now-playing",
            "#queue-panel",
            "#shortcut-bar",
        ):
            region = app.query_one(widget_id).region
            assert region.right <= 80
            assert region.bottom <= 24
        assert app.query_one("#shortcut-bar").region.bottom <= 24

    asyncio.run(_run_app_test(app, run_test, size=(80, 24)))


def test_textual_app_animates_waveform_while_playing_and_freezes_when_paused():
    playing_app = build_app(PlayerSnapshot(playing=True))

    async def run_playing(pilot):
        art = playing_app.query_one("#art", Static)
        first = art.content
        playing_app._animate_visualizer()
        assert art.content != first

    asyncio.run(_run_app_test(playing_app, run_playing, size=(120, 40)))

    paused_app = build_app(PlayerSnapshot(playing=False))

    async def run_paused(pilot):
        art = paused_app.query_one("#art", Static)
        first = art.content
        paused_app._animate_visualizer()
        assert art.content == first

    asyncio.run(_run_app_test(paused_app, run_paused, size=(120, 40)))


def test_textual_app_switches_between_lyrics_and_visualizer():
    app = build_app(
        PlayerSnapshot(
            elapsed=11,
            lyrics=(
                "[00:01.00]第一句",
                "[00:10.00]第二句",
                "[00:20.00]第三句",
            ),
        )
    )

    async def run_test(pilot):
        assert "第二句" in str(app.query_one("#lyrics-body", Static).content)
        await pilot.click("#visualizer-tab")
        assert app.query_one("#lyrics-body").display is False
        assert app.query_one("#visualizer-body").display is True

    asyncio.run(_run_app_test(app, run_test, size=(140, 40)))


def test_textual_app_routes_dashboard_control_buttons():
    class Controller:
        state = TextualState(
            current_song={"song_id": 1, "song_name": "现场"},
            queue=({"song_id": 1, "song_name": "现场"},),
        )
        calls = []
        keymap = {"playPause": " ", "star": "s", "shuffle": "?"}
        MENU_ITEMS = ()

        def refresh(self):
            return self.state

        def toggle(self):
            self.calls.append("toggle")

        def toggle_shuffle(self):
            self.calls.append("shuffle")

        def cycle_repeat(self):
            self.calls.append("repeat")

        def toggle_collection(self):
            self.calls.append("star")

    controller = Controller()
    app = build_app(controller=controller)

    async def run_test(pilot):
        await pilot.click("#favorite")
        await pilot.click("#shuffle")
        await pilot.click("#play-toggle")
        await pilot.click("#repeat")
        assert controller.calls == ["star", "shuffle", "toggle", "repeat"]
        shortcuts = str(app.query_one("#shortcut-bar", Static).content)
        assert "[Space] 播放/暂停" in shortcuts
        assert "[?] 随机" in shortcuts
        assert "[s] 收藏" in shortcuts

    asyncio.run(_run_app_test(app, run_test, size=(140, 40)))


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


def test_textual_app_exposes_local_collection_actions():
    class Controller:
        state = TextualState(
            current_song={"song_id": 1, "song_name": "当前歌曲"},
            queue=({"song_id": 1, "song_name": "当前歌曲"},),
        )
        keymap = {"star": "s", "collection": "c"}
        calls = []

        def toggle_collection(self):
            self.calls.append("star")
            return self.state

        def show_collection(self):
            self.calls.append("collection")
            self.state.page = "collection"
            self.state.page_title = "本地收藏"
            self.state.page_items = ({"song_id": 1, "song_name": "当前歌曲"},)
            return self.state

        def refresh(self):
            return self.state

    controller = Controller()
    app = build_app(controller=controller)

    async def run_test(pilot):
        await pilot.press("s")
        assert controller.calls == ["star"]
        await pilot.press("c")
        assert controller.calls == ["star", "collection"]
        assert app.query_one("#browser-title", Static).content == "本地收藏"

    asyncio.run(_run_app_test(app, run_test))


def test_textual_app_sidebar_search_and_help_open_their_views():
    class Controller:
        state = TextualState()
        keymap = {}
        MENU_ITEMS = tuple(f"项目 {index}" for index in range(10)) + ("搜索", "帮助")

        def refresh(self):
            return self.state

        def load_menu_item(self, index):
            self.state.page = "search" if index == 10 else "help"
            return self.state

    app = build_app(controller=Controller())

    async def run_test(pilot):
        await app._load_menu_worker(10)
        assert app.query_one("#views", ContentSwitcher).current == "search-panel"
        await app._load_menu_worker(11)
        assert app.query_one("#views", ContentSwitcher).current == "help-panel"

    asyncio.run(_run_app_test(app, run_test, size=(140, 40)))


async def _run_app_test(app, callback, size=(120, 40)):
    async with app.run_test(size=size) as pilot:
        await callback(pilot)
