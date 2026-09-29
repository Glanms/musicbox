from textual.widgets import DataTable, Label, Static

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


async def _run_app_test(app, callback):
    async with app.run_test() as pilot:
        await callback(pilot)
