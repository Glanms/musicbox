"""Full Textual interface for MusicBox."""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.events import Resize
from textual.widgets import (
    Button,
    ContentSwitcher,
    DataTable,
    Input,
    Label,
    ListItem,
    ListView,
    ProgressBar,
    Select,
    Static,
)

from .textual_controller import (
    TextualState,
    lyric_window,
    mode_display,
    parse_lyrics,
)


def _clock(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


VISUALIZER_FRAMES = (
    "  ▂▅▃▇▆▂  \n▃▇▂▅▇▃▂▅\n  ▅▂▆▃▅▂  ",
    "▂▆▃▅▇▂▅▃\n  ▇▂▆▃▂▇  \n▅▃▂▇▅▃▂▆",
    "  ▇▃▂▆▅▇  \n▅▂▇▃▅▂▆▃\n▂▅▃▇▂▅▃▂",
    "▅▂▆▃▂▇▅▃\n▂▇▃▅▇▂▅▆\n  ▃▅▂▆▃▇  ",
)
ASCII_VISUALIZER_FRAMES = (
    "  .:+##:  \n:+.-##:+\n  +:#.+:  ",
    "+#.-#:+.\n  #:+.-#  \n:+.#:+.-",
)


def terminal_symbol(symbol: str, fallback: str, encoding: str | None = None) -> str:
    """Return a terminal-safe glyph without requiring a specific font/encoding."""
    stream_encoding = getattr(sys.stdout, "encoding", None)
    try:
        symbol.encode(encoding or stream_encoding or "utf-8")
    except (LookupError, UnicodeEncodeError):
        return fallback
    return symbol


@dataclass(frozen=True)
class PlayerSnapshot:
    """Compatibility input for previews and isolated widget tests."""

    song_name: str = "暂无歌曲"
    artist: str = ""
    album_name: str = ""
    quality: str = ""
    volume: int = 60
    elapsed: float = 0
    duration: float = 0
    playing: bool = True
    mode: str = "顺序播放"
    source: tuple[str, ...] = ("歌单来源", "网易云音乐")
    queue: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    index: int = 0
    lyrics: tuple[str, ...] = field(default_factory=tuple)
    translated_lyrics: tuple[str, ...] = field(default_factory=tuple)

    @property
    def progress(self) -> float:
        return min(max(self.elapsed / self.duration, 0), 1) if self.duration else 0

    @property
    def time_text(self) -> str:
        return f"{_clock(self.elapsed)} / {_clock(self.duration)}"

    @property
    def queue_count_text(self) -> str:
        return f"共 {len(self.queue)} 首"


def _state_from_snapshot(snapshot: PlayerSnapshot) -> TextualState:
    lyrics = parse_lyrics(snapshot.lyrics, snapshot.translated_lyrics)
    state = TextualState(
        current_song={
            "song_name": snapshot.song_name,
            "artist": snapshot.artist,
            "album_name": snapshot.album_name,
            "quality": snapshot.quality,
        },
        elapsed=snapshot.elapsed,
        duration=snapshot.duration,
        playing=snapshot.playing,
        playing_mode=snapshot.mode,
        volume=snapshot.volume,
        queue=snapshot.queue,
        queue_index=snapshot.index,
        breadcrumbs=snapshot.source,
        lyrics=lyrics,
    )
    state.lyric_index, state.current_lyric, state.next_lyric = lyric_window(
        lyrics, state.elapsed
    )
    if not lyrics:
        state.current_lyric = "暂无歌词"
    return state


class MusicboxTextualApp(App[None]):
    CSS = """
    * { box-sizing: border-box; }
    Screen { background: #03070b; color: #e7f0f4; }
    #root { height: 1fr; padding: 0 1; }
    .panel { border: round #16d9e8; background: #071117; }
    #topbar { height: 4; min-height: 4; padding: 0 1; align: left middle; }
    #brand { width: 24; color: #30f3ee; text-style: bold; content-align: left middle; }
    #topbar-current { width: 1fr; color: #aebcc5; text-align: center; content-align: center middle; overflow: hidden; text-overflow: ellipsis; }
    #clock { width: 8; color: #f1f5f7; content-align: right middle; }
    #volume { width: 10; align: right middle; content-align: right middle; }
    #volume-icon { width: 3; color: #d9e7ed; content-align: right middle; }
    #volume-value { width: 1fr; color: #a9ff3f; text-align: right; content-align: right middle; }
    #quality { width: 12; color: #ff6ee7; text-style: bold; text-align: right; content-align: right middle; }
    #views, #dashboard { height: 1fr; }
    #dashboard-shell { height: 1fr; padding-top: 1; }
    #sidebar { width: 27; min-width: 27; height: 1fr; padding: 1; margin-right: 1; }
    #sidebar-title { height: 2; color: #30f3ee; text-style: bold; }
    #sidebar-list { height: 1fr; background: #071117; }
    #sidebar-list > ListItem { padding: 0 1; }
    #sidebar-list > ListItem.--highlight { background: #064d55; color: #ffffff; }
    #workspace { width: 1fr; height: 1fr; }
    #upper { height: 18; min-height: 18; margin-bottom: 1; }
    #now-playing { width: 2fr; height: 1fr; padding: 1 2; margin-right: 1; }
    #now-summary { height: 9; }
    #art { width: 20; min-width: 18; height: 8; border: solid #8f54dd; color: #d76cff; content-align: center middle; margin-right: 2; }
    #now-copy { width: 1fr; height: 1fr; }
    #state { height: 1; color: #d76cff; text-style: bold; }
    #song-title { height: 2; color: #f5f8fa; text-style: bold; margin-top: 1; }
    #artist { height: 1; color: #aebcc5; }
    #lyric-current { height: 1; color: #30f3ee; text-style: bold; margin-top: 1; overflow: hidden; text-overflow: ellipsis; }
    #lyric-next { height: 1; color: #718a9a; overflow: hidden; text-overflow: ellipsis; }
    #progress-row { height: 2; align: left middle; }
    #progress { width: 1fr; height: 1; }
    #mode { width: 9; height: 1; color: #a9ff3f; text-align: right; padding-left: 1; }
    #time { width: 14; height: 1; color: #d9e7ed; text-align: right; padding-left: 1; }
    #controls { height: 4; align: center middle; }
    #controls Button { width: 7; min-width: 5; height: 3; min-height: 3; margin: 0 1; border: none; background: transparent; color: #cbd7dd; text-style: bold; }
    #controls Button:hover, #controls Button:focus { background: #11232d; color: #ffffff; }
    #controls Button.active { color: #30f3ee; }
    #controls #play-toggle { width: 9; border: round #b75df4; color: #d76cff; background: #170d22; }
    #side-panel { width: 1fr; min-width: 30; height: 1fr; padding: 0 1 1 1; }
    #side-tabs { height: 3; border-bottom: solid #31434e; }
    #side-tabs Button { width: 1fr; height: 3; border: none; background: transparent; color: #8fa0aa; }
    #side-tabs Button.active { color: #30f3ee; text-style: bold; border-bottom: solid #30f3ee; }
    #lyrics-body, #visualizer-body { height: 1fr; padding: 1; }
    #visualizer-body { display: none; color: #d76cff; content-align: center middle; text-align: center; }
    #queue-panel { height: 1fr; min-height: 8; padding: 0 1; }
    #queue-header { height: 3; min-height: 3; color: #30f3ee; padding: 0 1; border-bottom: solid #1a5863; align: left middle; }
    #queue-title { content-align: left middle; text-style: bold; }
    #queue-count { color: #aebcc5; padding-left: 2; content-align: left middle; }
    DataTable { height: 1fr; background: #071117; padding: 0 1; }
    DataTable > .datatable--header { color: #aebcc5; background: #071117; text-style: bold; }
    DataTable > .datatable--cursor { background: #07565d; color: #ffffff; text-style: bold; }
    #menu-panel, #search-panel, #browser-panel, #help-panel, #login-panel { height: 1fr; padding-top: 1; }
    #menu-list, #results-list { height: 1fr; border: round #18d7e8; }
    #search-input { margin-bottom: 1; }
    #search-type { width: 20; margin-left: 1; }
    #notice { color: #ffcf5a; height: 1; min-height: 1; }
    #shortcut-bar { height: 1; min-height: 1; background: #070a10; color: #75838b; padding: 0 1; overflow: hidden; text-overflow: ellipsis; }

    #root.medium #sidebar { display: none; }
    #root.medium #upper { height: 16; min-height: 16; }
    #root.compact { padding: 0; }
    #root.compact #sidebar, #root.compact #side-panel { display: none; }
    #root.compact #topbar { height: 3; min-height: 3; }
    #root.compact #brand { width: 18; }
    #root.compact #clock { display: none; }
    #root.compact #quality { width: 9; }
    #root.compact #dashboard-shell { padding-top: 0; }
    #root.compact #upper { height: 11; min-height: 11; margin-bottom: 0; }
    #root.compact #now-playing { margin-right: 0; padding: 0 1; }
    #root.compact #now-summary { height: 6; }
    #root.compact #art { width: 13; min-width: 13; height: 6; margin-right: 1; }
    #root.compact #song-title { height: 1; margin-top: 0; }
    #root.compact #lyric-current { margin-top: 0; }
    #root.compact #lyric-next { display: none; }
    #root.compact #progress-row { height: 1; }
    #root.compact #mode { width: 8; }
    #root.compact #time { width: 12; }
    #root.compact #controls { height: 3; }
    #root.compact #controls Button { height: 3; margin: 0; }
    #root.compact #queue-panel { min-height: 4; padding: 0; }
    #root.compact #queue-header { height: 2; min-height: 2; padding: 0 1; }
    #root.compact DataTable { padding: 0; }
    #root.short #upper { height: 12; min-height: 10; }
    #root.short #queue-panel { min-height: 4; }
    """

    BINDINGS = [
        ("q", "quit", "退出"),
        ("space", "toggle_play", "播放/暂停"),
        ("]", "next_song", "下一曲"),
        ("[", "previous_song", "上一曲"),
        ("+", "volume_up", "音量+"),
        ("-", "volume_down", "音量-"),
        ("?", "toggle_shuffle", "随机"),
        ("P", "cycle_repeat", "循环"),
        ("v", "toggle_side_panel", "歌词/可视化"),
        ("r", "remove_queue", "删除歌曲"),
        ("D", "clear_queue", "清空队列"),
        ("m", "show_menu", "菜单"),
        ("f", "show_search", "搜索"),
        ("?", "show_help", "帮助"),
        ("l", "show_login", "登录"),
        ("i", "show_lyrics", "歌词"),
        ("I", "show_comments", "评论"),
        ("comma", "like_current", "喜欢"),
        ("C", "cache_current", "缓存"),
        ("slash", "next_fm", "下一 FM"),
        ("period", "trash_fm", "删除 FM"),
        ("escape", "go_back", "返回"),
        ("j", "cursor_down", "下移"),
        ("k", "cursor_up", "上移"),
        ("u", "page_up", "上页"),
        ("d", "page_down", "下页"),
        ("h", "go_back", "返回"),
        ("l", "page_forward", "下页"),
        ("a", "add_selected", "添加"),
        ("A", "open_selected_album", "专辑"),
        ("s", "star_current", "收藏"),
        ("c", "show_collection", "本地收藏"),
    ]

    def __init__(self, snapshot=None, controller=None) -> None:
        super().__init__()
        self.controller = controller
        self.snapshot = snapshot
        self.state = (
            controller.state
            if controller
            else _state_from_snapshot(snapshot or PlayerSnapshot())
        )
        self._queue_signature: tuple[Any, ...] = ()
        self._sidebar_signature: tuple[Any, ...] = ()
        self._view_stack = ["dashboard"]
        self._visualizer_index = 0
        self._side_panel = "lyrics"

    def compose(self) -> ComposeResult:
        yield Container(
            Horizontal(
                Static(terminal_symbol("▂▅▇  MusicBox", "|||  MusicBox"), id="brand"),
                Static(self._current_text(), id="topbar-current"),
                Static(self._clock_text(), id="clock"),
                Horizontal(
                    Static(terminal_symbol("♪", "*"), id="volume-icon"),
                    Static(f"{self.state.volume}%", id="volume-value"),
                    id="volume",
                ),
                Static(self._quality(), id="quality"),
                classes="panel",
                id="topbar",
            ),
            ContentSwitcher(
                self._dashboard(),
                self._menu_view(),
                self._search_view(),
                self._help_view(),
                self._browser_view(),
                self._login_view(),
                initial="dashboard",
                id="views",
            ),
            Static("", id="notice"),
            Static(self._shortcut_text(), id="shortcut-bar"),
            id="root",
        )

    def _dashboard(self) -> Container:
        state = self.state
        song = state.current_song
        return Container(
            Horizontal(
                Vertical(
                    Static("♫  资料库", id="sidebar-title"),
                    ListView(id="sidebar-list"),
                    classes="panel",
                    id="sidebar",
                ),
                Vertical(
                    Horizontal(
                        Vertical(
                            Horizontal(
                                Static(self._visualizer_frame(0), id="art"),
                                Vertical(
                                    Label(self._state_text(), id="state"),
                                    Label(
                                        song.get("song_name", "暂无歌曲"),
                                        id="song-title",
                                    ),
                                    Label(self._artist_text(), id="artist"),
                                    Label(
                                        self.state.current_lyric,
                                        id="lyric-current",
                                    ),
                                    Label(self.state.next_lyric, id="lyric-next"),
                                    id="now-copy",
                                ),
                                id="now-summary",
                            ),
                            Horizontal(
                                ProgressBar(total=1, show_eta=False, id="progress"),
                                Label(self._mode_text(), id="mode"),
                                Label(self._time_text(), id="time"),
                                id="progress-row",
                            ),
                            Horizontal(
                                Button(
                                    self._symbol("♡", "F"),
                                    id="favorite",
                                    classes="control",
                                ),
                                Button(
                                    self._symbol("⤨", "S"),
                                    id="shuffle",
                                    classes="control",
                                ),
                                Button(
                                    self._symbol("◀", "["),
                                    id="previous",
                                    classes="control",
                                ),
                                Button(self._play_symbol(), id="play-toggle"),
                                Button(
                                    self._symbol("▶", "]"), id="next", classes="control"
                                ),
                                Button(
                                    self._symbol("↻", "R"),
                                    id="repeat",
                                    classes="control",
                                ),
                                id="controls",
                            ),
                            classes="panel",
                            id="now-playing",
                        ),
                        Vertical(
                            Horizontal(
                                Button("▤  歌词", id="lyrics-tab", classes="active"),
                                Button("▥  可视化", id="visualizer-tab"),
                                id="side-tabs",
                            ),
                            Static(self._lyrics_content(), id="lyrics-body"),
                            Static(self._visualizer_frame(0), id="visualizer-body"),
                            classes="panel",
                            id="side-panel",
                        ),
                        id="upper",
                    ),
                    Vertical(
                        Horizontal(
                            Static("♫  播放列表", id="queue-title"),
                            Static(f"共 {state.queue_count} 首", id="queue-count"),
                            id="queue-header",
                        ),
                        DataTable(id="queue-table"),
                        classes="panel",
                        id="queue-panel",
                    ),
                    id="workspace",
                ),
                id="dashboard-shell",
            ),
            id="dashboard",
        )

    def _menu_view(self) -> Container:
        items = getattr(self.controller, "MENU_ITEMS", ()) if self.controller else ()
        return Container(
            Static("主菜单", classes="panel"),
            ListView(*(ListItem(Label(item)) for item in items), id="menu-list"),
            id="menu-panel",
        )

    def _search_view(self) -> Container:
        return Container(
            Horizontal(
                Input(placeholder="输入搜索关键词，回车搜索", id="search-input"),
                Select(
                    [
                        ("歌曲", "song"),
                        ("艺术家", "artist"),
                        ("专辑", "album"),
                        ("歌单", "playlist"),
                    ],
                    value="song",
                    id="search-type",
                ),
            ),
            ListView(id="results-list"),
            id="search-panel",
        )

    def _help_view(self) -> Container:
        return Container(
            Static(
                "快捷键\n\n"
                "j/k 选择项目    Enter 播放/进入\n"
                "Space 播放/暂停    [ / ] 上一曲/下一曲\n"
                "+/- 音量         P 播放模式\n"
                "m 菜单            f 搜索\n"
                "Esc 返回          q 退出",
                classes="panel",
                id="help-content",
            ),
            id="help-panel",
        )

    def _browser_view(self) -> Container:
        return Container(
            Static("浏览", classes="panel", id="browser-title"),
            ListView(id="browser-list"),
            id="browser-panel",
        )

    def _login_view(self) -> Container:
        return Container(
            Static("扫码登录", classes="panel"),
            Static("按 l 获取二维码", id="login-status"),
            Static("", id="login-qr"),
            id="login-panel",
        )

    def on_mount(self) -> None:
        self._bind_configured_keys()
        self._update_responsive_layout()
        table = self.query_one("#queue-table", DataTable)
        table.add_columns("", "歌曲", "歌手", "专辑", "时长")
        self._rebuild_queue(table)
        self._rebuild_sidebar()
        self._refresh_controls()
        self.set_interval(0.5, self._refresh_from_controller)
        self.set_interval(0.5, self._animate_visualizer)

    def on_resize(self, event: Resize) -> None:
        if event.control is self:
            self._update_responsive_layout()

    def _update_responsive_layout(self) -> None:
        root = self.query_one("#root", Container)
        root.set_class(self.size.width < 90, "compact")
        root.set_class(90 <= self.size.width < 120, "medium")
        root.set_class(self.size.height < 32, "short")

    def _bind_configured_keys(self) -> None:
        if self.controller is None:
            return
        actions = {
            "down": "cursor_down",
            "up": "cursor_up",
            "back": "go_back",
            "forward": "page_forward",
            "prevPage": "page_up",
            "nextPage": "page_down",
            "playPause": "toggle_play",
            "nextSong": "next_song",
            "prevSong": "previous_song",
            "volume+": "volume_up",
            "volume-": "volume_down",
            "shuffle": "toggle_shuffle",
            "playingMode": "cycle_repeat",
            "menu": "show_menu",
            "search": "show_search",
            "help": "show_help",
            "musicInfo": "show_lyrics",
            "add": "add_selected",
            "enterAlbum": "open_selected_album",
            "presentHistory": "show_dashboard",
            "remove": "remove_queue",
            "star": "star_current",
            "collection": "show_collection",
            "like": "like_current",
            "cache": "cache_current",
            "nextFM": "next_fm",
            "trashFM": "trash_fm",
            "quit": "quit",
        }
        configured = getattr(self.controller, "keymap", {})
        for name, action in actions.items():
            key = configured.get(name)
            if key:
                if key == " ":
                    key = "space"
                self.bind(key, action, show=False)

    def _rebuild_queue(self, table=None) -> None:
        table = table or self.query_one("#queue-table", DataTable)
        signature = tuple(
            (s.get("song_id"), s.get("song_name"), s.get("artist"))
            for s in self.state.queue
        )
        signature += (self.state.queue_index,)
        if signature == self._queue_signature:
            return
        self._queue_signature = signature
        table.clear()
        for index, song in enumerate(self.state.queue):
            table.add_row(
                "▶" if index == self.state.queue_index else str(index),
                str(song.get("song_name", "未知歌曲")),
                str(song.get("artist", "未知歌手")),
                f"< {song.get('album_name', '未知专辑')} >",
                self._song_duration(song),
                key=str(index),
            )
        table.cursor_type = "row"
        if self.state.queue:
            table.move_cursor(
                row=max(0, min(self.state.queue_index, len(self.state.queue) - 1))
            )

    def _rebuild_sidebar(self) -> None:
        menu_items = tuple(getattr(self.controller, "MENU_ITEMS", ()))
        signature = (
            self.state.queue_count,
            self.state.collection_count,
            menu_items,
        )
        if signature == self._sidebar_signature:
            return
        self._sidebar_signature = signature
        sidebar = self.query_one("#sidebar-list", ListView)
        sidebar.clear()
        labels = (
            f"{self._symbol('♫', '>')}  播放列表  {self.state.queue_count}",
            f"{self._symbol('♡', 'F')}  本地收藏  {self.state.collection_count}",
            *(f"·  {item}" for item in menu_items),
        )
        sidebar.extend(ListItem(Label(label)) for label in labels)

    def _refresh_from_controller(self) -> None:
        if self.controller is None:
            return
        self.state = self.controller.refresh()
        song = self.state.current_song
        self.query_one("#quality", Static).update(song.get("quality", "MusicBox"))
        self.query_one("#topbar-current", Static).update(self._current_text())
        self.query_one("#clock", Static).update(self._clock_text())
        self.query_one("#volume-value", Static).update(f"{self.state.volume}%")
        self.query_one("#state", Label).update(self._state_text())
        self.query_one("#mode", Label).update(self._mode_text())
        self.query_one("#song-title", Label).update(song.get("song_name", "暂无歌曲"))
        self.query_one("#artist", Label).update(self._artist_text())
        self.query_one("#lyric-current", Label).update(self.state.current_lyric)
        self.query_one("#lyric-next", Label).update(self.state.next_lyric)
        self.query_one("#time", Label).update(self._time_text())
        self.query_one("#queue-count", Static).update(f"共 {self.state.queue_count} 首")
        self.query_one("#progress", ProgressBar).progress = self._progress()
        self.query_one("#lyrics-body", Static).update(self._lyrics_content())
        self.query_one("#notice", Static).update(self.state.error)
        self._rebuild_queue()
        self._rebuild_sidebar()
        self._refresh_controls()

    def _progress(self) -> float:
        return (
            min(max(self.state.elapsed / self.state.duration, 0), 1)
            if self.state.duration
            else 0
        )

    def _state_text(self) -> str:
        if self.state.playing:
            return f"{self._symbol('▶', '>')} 正在播放"
        return f"{self._symbol('❚❚', '||')}  已暂停"

    def _mode_text(self) -> str:
        return mode_display(self.state.playing_mode)

    def _animate_visualizer(self) -> None:
        if not self.state.playing:
            return
        frames = self._visualizer_frames()
        self._visualizer_index = (self._visualizer_index + 1) % len(frames)
        frame = frames[self._visualizer_index]
        self.query_one("#art", Static).update(frame)
        self.query_one("#visualizer-body", Static).update(frame)

    def _time_text(self) -> str:
        return f"{_clock(self.state.elapsed)} / {_clock(self.state.duration)}"

    def _quality(self) -> str:
        return self.state.current_song.get("quality", "MusicBox")

    def _clock_text(self) -> str:
        return datetime.now().strftime("%H:%M")

    def _artist_text(self) -> str:
        song = self.state.current_song
        values = [song.get("artist", ""), song.get("album_name", "")]
        return "  ·  ".join(str(value) for value in values if value)

    def _play_symbol(self) -> str:
        return (
            self._symbol("❚❚", "||") if self.state.playing else self._symbol("▶", ">")
        )

    @staticmethod
    def _symbol(symbol: str, fallback: str) -> str:
        return terminal_symbol(symbol, fallback)

    @staticmethod
    def _visualizer_frames() -> tuple[str, ...]:
        first = VISUALIZER_FRAMES[0]
        return (
            VISUALIZER_FRAMES if terminal_symbol(first, "") else ASCII_VISUALIZER_FRAMES
        )

    def _visualizer_frame(self, index: int) -> str:
        frames = self._visualizer_frames()
        return frames[index % len(frames)]

    @staticmethod
    def _song_duration(song: dict[str, Any]) -> str:
        duration = song.get("duration", 0) or 0
        try:
            seconds = float(duration)
        except (TypeError, ValueError):
            return "--:--"
        if seconds > 36000:
            seconds /= 1000
        return _clock(seconds) if seconds else "--:--"

    def _lyrics_content(self) -> Text:
        lyrics = self.state.lyrics
        if not lyrics:
            return Text(self.state.current_lyric or "暂无歌词", style="#718a9a")
        current = max(0, self.state.lyric_index)
        start = max(0, min(current - 3, len(lyrics) - 9))
        visible = lyrics[start : start + 9]
        content = Text()
        for offset, line in enumerate(visible):
            index = start + offset
            style = "bold #30f3ee" if index == self.state.lyric_index else "#aebcc5"
            content.append(line.display, style=style)
            if offset < len(visible) - 1:
                content.append("\n")
        return content

    def _refresh_controls(self) -> None:
        mode = self.state.playing_mode
        favorite = self.query_one("#favorite", Button)
        shuffle = self.query_one("#shuffle", Button)
        repeat = self.query_one("#repeat", Button)
        play = self.query_one("#play-toggle", Button)
        favorite.set_class(self.state.current_collected, "active")
        shuffle.set_class(mode in ("随机播放", "随机循环"), "active")
        repeat.set_class(mode in ("顺序循环", "单曲循环", "随机循环"), "active")
        favorite.label = (
            self._symbol("♥", "*")
            if self.state.current_collected
            else self._symbol("♡", "F")
        )
        repeat.label = (
            self._symbol("↺¹", "R1") if mode == "单曲循环" else self._symbol("↻", "R")
        )
        play.label = self._play_symbol()

    def _shortcut_text(self) -> str:
        configured = getattr(self.controller, "keymap", {}) if self.controller else {}
        hints = (
            (configured.get("playPause", "Space"), "播放/暂停"),
            (configured.get("prevSong", "["), "上一首"),
            (configured.get("nextSong", "]"), "下一首"),
            (configured.get("star", "s"), "收藏"),
            (configured.get("shuffle", "?"), "随机"),
            (configured.get("playingMode", "P"), "循环"),
            ("v", "歌词/可视化"),
            (configured.get("menu", "m"), "菜单"),
            (configured.get("quit", "q"), "退出"),
        )
        return "   ".join(f"[{self._display_key(key)}] {label}" for key, label in hints)

    @staticmethod
    def _display_key(key: str) -> str:
        return "Space" if key == " " else str(key)

    def _current_text(self) -> str:
        song = self.state.current_song
        return f"正在播放：{song.get('song_name', '暂无歌曲')}  -  {song.get('artist', '')}"

    def _call(self, action: str, *args: Any) -> None:
        if self.controller is not None:
            getattr(self.controller, action)(*args)
            self._refresh_from_controller()

    def _set_view(self, view_id: str, *, push: bool = True) -> None:
        if push and self._view_stack[-1] != view_id:
            self._view_stack.append(view_id)
        self.query_one("#views", ContentSwitcher).current = view_id

    def _active_navigator(self) -> ListView | DataTable | None:
        view_id = self.query_one("#views", ContentSwitcher).current
        if view_id == "dashboard":
            return self.query_one("#queue-table", DataTable)
        if view_id == "menu-panel":
            return self.query_one("#menu-list", ListView)
        if view_id == "search-panel":
            return self.query_one("#results-list", ListView)
        if view_id == "browser-panel":
            return self.query_one("#browser-list", ListView)
        return None

    def _move_cursor(self, direction: str) -> None:
        navigator = self._active_navigator()
        if navigator is not None:
            getattr(navigator, f"action_cursor_{direction}")()

    def _page_cursor(self, direction: str) -> None:
        navigator = self._active_navigator()
        if navigator is not None:
            getattr(navigator, f"action_page_{direction}")()

    def action_toggle_play(self) -> None:
        self._call("toggle")

    def action_next_song(self) -> None:
        self._call("next")

    def action_previous_song(self) -> None:
        self._call("previous")

    def action_volume_up(self) -> None:
        self._call("change_volume", 5)

    def action_volume_down(self) -> None:
        self._call("change_volume", -5)

    def action_change_mode(self) -> None:
        self._call("change_mode")

    def action_toggle_shuffle(self) -> None:
        self._call("toggle_shuffle")

    def action_cycle_repeat(self) -> None:
        self._call("cycle_repeat")

    def action_toggle_side_panel(self) -> None:
        target = "visualizer" if self._side_panel == "lyrics" else "lyrics"
        self._show_side_panel(target)

    def _show_side_panel(self, target: str) -> None:
        self._side_panel = target
        show_lyrics = target == "lyrics"
        self.query_one("#lyrics-body").display = show_lyrics
        self.query_one("#visualizer-body").display = not show_lyrics
        self.query_one("#lyrics-tab", Button).set_class(show_lyrics, "active")
        self.query_one("#visualizer-tab", Button).set_class(not show_lyrics, "active")

    def action_cursor_down(self) -> None:
        self._move_cursor("down")

    def action_cursor_up(self) -> None:
        self._move_cursor("up")

    def action_page_up(self) -> None:
        self._page_cursor("up")

    def action_page_down(self) -> None:
        self._page_cursor("down")

    def action_page_forward(self) -> None:
        self.action_page_down()

    def action_remove_queue(self) -> None:
        if self.controller is not None:
            table = self.query_one("#queue-table", DataTable)
            self._call("remove_index", table.cursor_row)

    def action_clear_queue(self) -> None:
        self._call("clear_queue")

    def action_show_dashboard(self) -> None:
        self._view_stack = ["dashboard"]
        self._set_view("dashboard", push=False)

    def action_go_back(self) -> None:
        if len(self._view_stack) > 1:
            self._view_stack.pop()
        self._set_view(self._view_stack[-1], push=False)

    def action_show_menu(self) -> None:
        self._set_view("menu-panel")

    def action_show_search(self) -> None:
        self._set_view("search-panel")
        self.query_one("#search-input", Input).focus()

    def action_show_help(self) -> None:
        self._set_view("help-panel")

    def action_show_login(self) -> None:
        self._set_view("login-panel")
        if self.controller is not None:
            self.run_worker(self._login_worker(), exclusive=True)

    def action_add_selected(self) -> None:
        if self.controller is None:
            return
        navigator = self._active_navigator()
        if not isinstance(navigator, ListView) or navigator.index is None:
            return
        items = self.state.page_items
        if not 0 <= navigator.index < len(items):
            return
        item = items[navigator.index]
        if not isinstance(item, dict) or not item.get("song_id"):
            self.query_one("#notice", Static).update("当前项目不是歌曲")
            return
        self._call("append_songs", [item])
        self.query_one("#notice", Static).update("已添加到播放列表")

    def action_open_selected_album(self) -> None:
        if self.controller is None:
            return
        navigator = self._active_navigator()
        if not isinstance(navigator, ListView) or navigator.index is None:
            return
        self.run_worker(self._open_album_worker(navigator.index), exclusive=True)

    def action_star_current(self) -> None:
        self._call("toggle_collection")
        message = (
            "已添加到本地收藏" if self.state.current_collected else "已取消本地收藏"
        )
        self.query_one("#notice", Static).update(message)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        actions = {
            "favorite": self.action_star_current,
            "shuffle": self.action_toggle_shuffle,
            "previous": self.action_previous_song,
            "play-toggle": self.action_toggle_play,
            "next": self.action_next_song,
            "repeat": self.action_cycle_repeat,
            "lyrics-tab": lambda: self._show_side_panel("lyrics"),
            "visualizer-tab": lambda: self._show_side_panel("visualizer"),
        }
        action = actions.get(event.button.id or "")
        if action is not None:
            action()

    def action_show_collection(self) -> None:
        if self.controller is None:
            return
        state = self.controller.show_collection()
        self.state = state
        self._show_browser_items(state.page_title, state.page_items)

    async def _open_album_worker(self, index: int) -> None:
        controller = self.controller
        if controller is None:
            return
        try:
            state = await asyncio.to_thread(controller.open_album, index)
        except Exception as exc:  # noqa: BLE001
            self.query_one("#notice", Static).update(f"打开专辑失败：{exc}")
            return
        if state.page == "queue":
            self.action_show_dashboard()
        elif state.error:
            self.query_one("#notice", Static).update(state.error)

    def action_show_lyrics(self) -> None:
        self._run_state_page("show_lyrics")

    def action_show_comments(self) -> None:
        self._run_state_page("show_comments")

    def action_like_current(self) -> None:
        self._call("like_current")

    def action_cache_current(self) -> None:
        self._call("cache_current")

    def action_next_fm(self) -> None:
        self._call("next_fm")

    def action_trash_fm(self) -> None:
        self._call("trash_fm")

    def _run_state_page(self, action: str) -> None:
        if self.controller is not None:
            self.run_worker(self._state_page_worker(action), exclusive=True)

    async def _state_page_worker(self, action: str) -> None:
        try:
            state = await asyncio.to_thread(getattr(self.controller, action))
        except Exception as exc:  # noqa: BLE001
            self.query_one("#notice", Static).update(f"加载失败：{exc}")
            return
        if state.page in ("lyrics", "comments"):
            self._show_browser_items(state.page_title, state.page_items)

    async def _login_worker(self) -> None:
        if self.controller is None:
            return
        status = self.query_one("#login-status", Static)
        qr_view = self.query_one("#login-qr", Static)
        try:
            key, qr = await asyncio.to_thread(self.controller.begin_login)
            qr_view.update(qr)
            for _ in range(150):
                await asyncio.sleep(2)
                message = await asyncio.to_thread(self.controller.check_login, key)
                status.update(message)
                if message.startswith("登录成功") or "过期" in message:
                    self._refresh_from_controller()
                    return
        except Exception as exc:  # noqa: BLE001
            status.update(f"登录失败：{exc}")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "sidebar-list":
            index = event.list_view.index
            if index == 0:
                self.action_show_dashboard()
            elif index == 1:
                self.action_show_collection()
            elif index is not None and self.controller is not None:
                self.run_worker(self._load_menu_worker(index - 2), exclusive=True)
        elif event.list_view.id == "menu-list":
            index = event.list_view.index
            if index is None:
                return
            if index == 10:
                self.action_show_search()
            elif index == 11:
                self.action_show_help()
            elif self.controller is not None:
                self.run_worker(self._load_menu_worker(index), exclusive=True)
        elif event.list_view.id in ("browser-list", "results-list"):
            index = event.list_view.index
            if index is not None and self.controller is not None:
                self.run_worker(self._open_browser_worker(index), exclusive=True)

    async def _open_browser_worker(self, index: int) -> None:
        if self.controller is None:
            return
        if self.state.page in ("lyrics", "comments"):
            return
        try:
            state = await asyncio.to_thread(self.controller.open_item, index)
        except Exception as exc:  # noqa: BLE001
            self.query_one("#notice", Static).update(f"打开失败：{exc}")
            return
        if state.page == "queue":
            self.action_show_dashboard()
        else:
            self._show_browser_items(state.page_title, state.page_items)

    async def _load_menu_worker(self, index: int) -> None:
        if self.controller is None:
            return
        self.query_one("#notice", Static).update("正在加载...")
        try:
            state = await asyncio.to_thread(self.controller.load_menu_item, index)
        except Exception as exc:  # noqa: BLE001
            self.query_one("#notice", Static).update(f"加载失败：{exc}")
            return
        if state.page == "search":
            self.action_show_search()
        elif state.page == "help":
            self.action_show_help()
        elif state.page == "list":
            self._show_browser_items(state.page_title, state.page_items)
            self.query_one("#notice", Static).update(
                f"已加载 {len(state.page_items)} 项"
            )
        elif state.error:
            self.query_one("#notice", Static).update(state.error)

    def _show_browser_items(self, title: str, items: tuple[Any, ...]) -> None:
        self._set_view("browser-panel")
        self.query_one("#browser-title", Static).update(title)
        browser = self.query_one("#browser-list", ListView)
        browser.clear()
        for item in items:
            if isinstance(item, str):
                label = item
            elif isinstance(item, dict):
                label = (
                    item.get("song_name")
                    or item.get("playlist_name")
                    or item.get("artists_name")
                    or item.get("albums_name")
                    or item.get("name")
                    or "未知项目"
                )
            else:
                label = str(item)
            browser.append(ListItem(Label(str(label))))

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "queue-table":
            self._call("play_index", event.cursor_row)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input" and event.value.strip():
            category = str(self.query_one("#search-type", Select).value)
            self.run_worker(
                self._search_worker(event.value.strip(), category), exclusive=True
            )

    async def _search_worker(self, keyword: str, category: str) -> None:
        if self.controller is None:
            return
        self.query_one("#notice", Static).update("正在搜索...")
        try:
            items = await asyncio.to_thread(self.controller.search, keyword, category)
        except Exception as exc:  # noqa: BLE001
            self.query_one("#notice", Static).update(f"搜索失败：{exc}")
            return
        self.controller.state.page = "list"
        self.controller.state.page_title = f"搜索：{keyword}"
        self.controller.state.page_items = tuple(items)
        results = self.query_one("#results-list", ListView)
        results.clear()
        for item in items:
            label = (
                item.get("song_name")
                or item.get("playlist_name")
                or item.get("artists_name")
                or item.get("albums_name")
                or "未知结果"
            )
            results.append(ListItem(Label(str(label))))
        self.query_one("#notice", Static).update(f"找到 {len(items)} 条结果")


def build_app(snapshot=None, controller=None) -> MusicboxTextualApp:
    return MusicboxTextualApp(snapshot=snapshot, controller=controller)


if __name__ == "__main__":
    build_app().run()
