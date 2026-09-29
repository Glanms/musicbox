"""Textual dashboard UI for MusicBox.

The app is deliberately independent from the curses controller.  A later
adapter can turn ``Player`` state into ``PlayerSnapshot`` without coupling the
player thread to Textual widgets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import DataTable, Footer, Label, ProgressBar, Static


def _clock(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


@dataclass(frozen=True)
class PlayerSnapshot:
    """Immutable display state shared by the player adapter and the UI."""

    song_name: str = "暂无歌曲"
    artist: str = ""
    album_name: str = ""
    quality: str = ""
    elapsed: float = 0
    duration: float = 0
    playing: bool = True
    mode: str = "顺序播放"
    source: tuple[str, ...] = ("歌单来源", "网易云音乐")
    queue: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    index: int = 0

    @property
    def progress(self) -> float:
        return min(max(self.elapsed / self.duration, 0), 1) if self.duration else 0

    @property
    def time_text(self) -> str:
        return f"{_clock(self.elapsed)} / {_clock(self.duration)}"

    @property
    def queue_count_text(self) -> str:
        return f"共 {len(self.queue)} 首"


class MusicboxTextualApp(App[None]):
    CSS = """
    * { box-sizing: border-box; }
    Screen { background: #081117; color: #e7f0f4; }
    #root { padding: 1 2; height: 100%; }
    .panel { border: round #18d7e8; background: #0b151b; padding: 1 2; margin-bottom: 1; }
    #topbar { height: 4; color: #ff7280; }
    #topbar-current { color: #63f4ff; text-align: right; width: 1fr; }
    #now-playing { height: 11; }
    #art { width: 18; height: 7; border: solid #1cc9dc; color: #2de4ef; content-align: center middle; margin-right: 2; }
    #now-copy { width: 1fr; }
    #state { color: #a9ff3f; text-style: bold; }
    #song-title { color: #f5f8fa; text-style: bold; margin-top: 1; }
    #artist { color: #aebcc5; }
    #progress { margin-top: 1; width: 1fr; }
    #time { width: 13; color: #a9ff3f; text-align: right; padding-left: 1; }
    #source { height: 4; color: #63f4ff; }
    #source-path { color: #e7f0f4; padding-left: 2; }
    #queue-panel { height: 1fr; padding: 0 1; }
    #queue-header { height: 3; color: #63f4ff; padding: 1 1; border-bottom: solid #27cfe0; }
    #queue-count { color: #aebcc5; padding-left: 2; }
    DataTable { height: 1fr; background: #0b151b; }
    DataTable > .datatable--cursor { background: #063c4a; color: #ffffff; }
    Footer { background: #081117; }
    """

    BINDINGS = [("q", "quit", "退出"), ("space", "toggle_play", "播放/暂停")]

    def __init__(self, snapshot: PlayerSnapshot | None = None) -> None:
        super().__init__()
        self.snapshot = snapshot or PlayerSnapshot()

    def compose(self) -> ComposeResult:
        snapshot = self.snapshot
        yield Container(
            Horizontal(
                Static("♫  ♪  ♫  ♪   |   ", id="quality-prefix"),
                Static(snapshot.quality or "MusicBox", id="quality"),
                Static(self._current_text(), id="topbar-current"),
                classes="panel",
                id="topbar",
            ),
            Horizontal(
                Static("▂▃▅▇▅▃▂\n▂▅▇▃▅▂▃", id="art"),
                Vertical(
                    Label(f"▶  {snapshot.mode}", id="state"),
                    Label(snapshot.song_name, id="song-title"),
                    Label(f"{snapshot.artist}  ·  {snapshot.album_name}", id="artist"),
                    Horizontal(
                        ProgressBar(total=1, show_eta=False, id="progress"),
                        Label(snapshot.time_text, id="time"),
                    ),
                    id="now-copy",
                ),
                classes="panel",
                id="now-playing",
            ),
            Horizontal(
                Static("☷  歌单来源", id="source-label"),
                Static("  >  ".join(snapshot.source), id="source-path"),
                classes="panel",
                id="source",
            ),
            Vertical(
                Horizontal(
                    Static("♫  播放列表", id="queue-title"),
                    Static(snapshot.queue_count_text, id="queue-count"),
                    id="queue-header",
                ),
                DataTable(id="queue-table"),
                classes="panel",
                id="queue-panel",
            ),
            id="root",
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#queue-table", DataTable)
        table.add_columns("", "歌曲", "歌手", "专辑")
        for index, song in enumerate(self.snapshot.queue):
            table.add_row(
                "▶" if index == self.snapshot.index else str(index),
                str(song.get("song_name", "未知歌曲")),
                str(song.get("artist", "未知歌手")),
                f"< {song.get('album_name', '未知专辑')} >",
                key=str(index),
            )
        table.cursor_type = "row"
        if self.snapshot.queue:
            table.move_cursor(
                row=max(0, min(self.snapshot.index, len(self.snapshot.queue) - 1))
            )
        self.query_one("#progress", ProgressBar).progress = self.snapshot.progress

    def action_toggle_play(self) -> None:
        state = self.query_one("#state", Label)
        state.update(
            "❚❚  已暂停" if self.snapshot.playing else f"▶  {self.snapshot.mode}"
        )

    def _current_text(self) -> str:
        return f"正在播放：{self.snapshot.song_name}  -  {self.snapshot.artist}"


def build_app(snapshot: PlayerSnapshot | None = None) -> MusicboxTextualApp:
    return MusicboxTextualApp(snapshot)


if __name__ == "__main__":
    build_app().run()
