"""Full Textual interface for MusicBox."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.events import Resize
from textual.widgets import (
    ContentSwitcher,
    DataTable,
    Footer,
    Input,
    Label,
    ListItem,
    ListView,
    ProgressBar,
    Select,
    Static,
)

from .textual_controller import TextualState


def _clock(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


@dataclass(frozen=True)
class PlayerSnapshot:
    """Compatibility input for previews and isolated widget tests."""

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


def _state_from_snapshot(snapshot: PlayerSnapshot) -> TextualState:
    return TextualState(
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
        queue=snapshot.queue,
        queue_index=snapshot.index,
        breadcrumbs=snapshot.source,
    )


class MusicboxTextualApp(App[None]):
    CSS = """
    * { box-sizing: border-box; }
    Screen { background: #05090c; color: #e7f0f4; }
    #root { height: 1fr; padding: 1 2 0 2; }
    .panel { border: round #18d7e8; background: #0b151b; padding: 1 2; margin-bottom: 1; }
    #topbar { height: 4; min-height: 4; padding: 0 1; color: #ff7280; align: left middle; }
    #quality-prefix { width: 19; color: #ff7280; content-align: left middle; }
    #quality { width: 12; color: #ff7280; text-style: bold; content-align: left middle; }
    #topbar-current { width: 1fr; color: #63f4ff; text-align: right; content-align: right middle; }
    #views { height: 1fr; }
    #dashboard { height: 1fr; }
    #now-playing { height: 13; min-height: 13; padding: 1 2; align: left middle; }
    #art { width: 22; height: 9; border: solid #1cc9dc; color: #2de4ef; content-align: center middle; margin-right: 2; }
    #now-copy { width: 1fr; height: 1fr; }
    #state { height: 1; color: #a9ff3f; text-style: bold; }
    #song-title { height: 2; color: #f5f8fa; text-style: bold; margin-top: 1; }
    #artist { height: 2; color: #aebcc5; }
    #progress-row { height: 3; align: left middle; }
    #progress { width: 1fr; height: 1; margin-top: 1; }
    #time { width: 14; height: 1; color: #a9ff3f; text-align: right; padding-left: 1; }
    #source { height: 3; min-height: 3; padding: 0 2; color: #63f4ff; align: left middle; }
    #source-label { width: 18; content-align: left middle; }
    #source-path { width: 1fr; color: #e7f0f4; content-align: left middle; }
    #queue-panel { height: 1fr; min-height: 10; padding: 0 1; margin-bottom: 0; }
    #queue-header { height: 3; min-height: 3; color: #63f4ff; padding: 0 1; border-bottom: solid #27cfe0; align: left middle; }
    #queue-title { content-align: left middle; }
    #queue-count { color: #aebcc5; padding-left: 2; content-align: left middle; }
    DataTable { height: 1fr; background: #0b151b; padding: 0 1; }
    DataTable > .datatable--header { color: #aebcc5; background: #0b151b; text-style: bold; }
    DataTable > .datatable--cursor { background: #064955; color: #ffffff; }
    #menu-panel, #search-panel, #browser-panel, #help-panel, #login-panel { height: 1fr; }
    #menu-list, #results-list { height: 1fr; border: round #18d7e8; }
    #search-input { margin-bottom: 1; }
    #search-type { width: 20; margin-left: 1; }
    #notice { color: #ffcf5a; height: 1; min-height: 1; }
    Footer { height: 1; min-height: 1; background: #05090c; color: #75838b; padding: 0 1; }
    Footer > .footer--key { color: #75838b; }
    Footer > .footer--key > .footer--description { color: #aebcc5; }

    #root.compact { padding: 0 1; }
    #root.compact #topbar { height: 3; min-height: 3; }
    #root.compact #quality-prefix { width: 13; }
    #root.compact #quality { width: 8; }
    #root.compact #now-playing { height: 8; min-height: 8; padding: 0 1; }
    #root.compact #art { width: 14; height: 6; margin-right: 1; }
    #root.compact #source { height: 2; min-height: 2; padding: 0 1; }
    #root.compact #source-label { width: 14; }
    #root.compact #queue-panel { min-height: 4; padding: 0; }
    #root.compact #queue-header { height: 2; min-height: 2; padding: 0 1; }
    #root.compact DataTable { padding: 0; }
    """

    BINDINGS = [
        ("q", "quit", "退出"),
        ("space", "toggle_play", "播放/暂停"),
        ("]", "next_song", "下一曲"),
        ("[", "previous_song", "上一曲"),
        ("+", "volume_up", "音量+"),
        ("-", "volume_down", "音量-"),
        ("P", "change_mode", "播放模式"),
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
        ("escape", "show_dashboard", "返回"),
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

    def compose(self) -> ComposeResult:
        yield Container(
            Horizontal(
                Static("♫  ♪  ♫  ♪   |   ", id="quality-prefix"),
                Static(self._quality(), id="quality"),
                Static(self._current_text(), id="topbar-current"),
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
            id="root",
        )
        yield Footer()

    def _dashboard(self) -> Container:
        state = self.state
        song = state.current_song
        return Container(
            Horizontal(
                Static("▂▃▅▇▅▃▂\n▂▅▇▃▅▂▃", id="art"),
                Vertical(
                    Label(self._state_text(), id="state"),
                    Label(song.get("song_name", "暂无歌曲"), id="song-title"),
                    Label(
                        f"{song.get('artist', '')}  ·  {song.get('album_name', '')}",
                        id="artist",
                    ),
                    Horizontal(
                        ProgressBar(total=1, show_eta=False, id="progress"),
                        Label(self._time_text(), id="time"),
                        id="progress-row",
                    ),
                    id="now-copy",
                ),
                classes="panel",
                id="now-playing",
            ),
            Horizontal(
                Static("☷  歌单来源", id="source-label"),
                Static("  >  ".join(state.breadcrumbs), id="source-path"),
                classes="panel",
                id="source",
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
        table.add_columns("", "歌曲", "歌手", "专辑")
        self._rebuild_queue(table)
        self.set_interval(0.5, self._refresh_from_controller)

    def on_resize(self, event: Resize) -> None:
        if event.control is self:
            self._update_responsive_layout()

    def _update_responsive_layout(self) -> None:
        root = self.query_one("#root", Container)
        root.set_class(self.size.width < 100, "compact")

    def _bind_configured_keys(self) -> None:
        if self.controller is None:
            return
        actions = {
            "playPause": "toggle_play",
            "nextSong": "next_song",
            "prevSong": "previous_song",
            "volume+": "volume_up",
            "volume-": "volume_down",
            "playingMode": "change_mode",
            "menu": "show_menu",
            "search": "show_search",
            "help": "show_help",
            "musicInfo": "show_lyrics",
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
                key=str(index),
            )
        table.cursor_type = "row"
        if self.state.queue:
            table.move_cursor(
                row=max(0, min(self.state.queue_index, len(self.state.queue) - 1))
            )

    def _refresh_from_controller(self) -> None:
        if self.controller is None:
            return
        self.state = self.controller.refresh()
        song = self.state.current_song
        self.query_one("#quality", Static).update(song.get("quality", "MusicBox"))
        self.query_one("#topbar-current", Static).update(self._current_text())
        self.query_one("#state", Label).update(self._state_text())
        self.query_one("#song-title", Label).update(song.get("song_name", "暂无歌曲"))
        self.query_one("#artist", Label).update(
            f"{song.get('artist', '')}  ·  {song.get('album_name', '')}"
        )
        self.query_one("#time", Label).update(self._time_text())
        self.query_one("#source-path", Static).update(
            "  >  ".join(self.state.breadcrumbs)
        )
        self.query_one("#queue-count", Static).update(f"共 {self.state.queue_count} 首")
        self.query_one("#progress", ProgressBar).progress = self._progress()
        self._rebuild_queue()

    def _progress(self) -> float:
        return (
            min(max(self.state.elapsed / self.state.duration, 0), 1)
            if self.state.duration
            else 0
        )

    def _state_text(self) -> str:
        return f"▶  {self.state.playing_mode}" if self.state.playing else "❚❚  已暂停"

    def _time_text(self) -> str:
        return f"{_clock(self.state.elapsed)} / {_clock(self.state.duration)}"

    def _quality(self) -> str:
        return self.state.current_song.get("quality", "MusicBox")

    def _current_text(self) -> str:
        song = self.state.current_song
        return f"正在播放：{song.get('song_name', '暂无歌曲')}  -  {song.get('artist', '')}"

    def _call(self, action: str, *args: Any) -> None:
        if self.controller is not None:
            getattr(self.controller, action)(*args)
            self._refresh_from_controller()

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

    def action_remove_queue(self) -> None:
        if self.controller is not None:
            table = self.query_one("#queue-table", DataTable)
            self._call("remove_index", table.cursor_row)

    def action_clear_queue(self) -> None:
        self._call("clear_queue")

    def action_show_dashboard(self) -> None:
        self.query_one("#views", ContentSwitcher).current = "dashboard"

    def action_show_menu(self) -> None:
        self.query_one("#views", ContentSwitcher).current = "menu-panel"

    def action_show_search(self) -> None:
        self.query_one("#views", ContentSwitcher).current = "search-panel"
        self.query_one("#search-input", Input).focus()

    def action_show_help(self) -> None:
        self.query_one("#views", ContentSwitcher).current = "help-panel"

    def action_show_login(self) -> None:
        self.query_one("#views", ContentSwitcher).current = "login-panel"
        if self.controller is not None:
            self.run_worker(self._login_worker(), exclusive=True)

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
        state = await asyncio.to_thread(getattr(self.controller, action))
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
        if event.list_view.id == "menu-list":
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
        if state.page == "list":
            self._show_browser_items(state.page_title, state.page_items)
            self.query_one("#notice", Static).update(
                f"已加载 {len(state.page_items)} 项"
            )
        elif state.error:
            self.query_one("#notice", Static).update(state.error)

    def _show_browser_items(self, title: str, items: tuple[Any, ...]) -> None:
        self.query_one("#views", ContentSwitcher).current = "browser-panel"
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
