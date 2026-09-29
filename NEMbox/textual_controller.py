"""Application state and domain actions for the Textual interface."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

MODE_NAMES = ("顺序播放", "顺序循环", "单曲循环", "随机播放", "随机循环")


@dataclass
class TextualState:
    current_song: dict[str, Any] = field(default_factory=dict)
    elapsed: float = 0
    duration: float = 0
    playing: bool = False
    volume: int = 60
    playing_mode: str = "顺序播放"
    queue: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    queue_index: int = 0
    page: str = "home"
    page_title: str = "网易云音乐"
    page_items: tuple[Any, ...] = field(default_factory=tuple)
    selected_index: int = 0
    loading: bool = False
    error: str = ""
    user: dict[str, Any] = field(default_factory=dict)
    breadcrumbs: tuple[str, ...] = ("歌单来源", "网易云音乐")

    @property
    def queue_count(self) -> int:
        return len(self.queue)


class TextualUiBridge:
    """Player UI dependency that never touches curses."""

    def build_playinfo(self, *args: Any, **kwargs: Any) -> None:
        return None

    def update_size(self, *args: Any, **kwargs: Any) -> None:
        return None


class TextualController:
    MENU_ITEMS = (
        "排行榜",
        "艺术家",
        "新碟上架",
        "精选歌单",
        "我的歌单",
        "我的云盘",
        "主播电台",
        "每日推荐歌曲",
        "每日推荐歌单",
        "私人FM",
        "搜索",
        "帮助",
    )

    def __init__(self, player: Any = None, api: Any = None, storage: Any = None):
        if storage is None:
            if player is None or api is None:
                from .storage import Storage

                storage = Storage()
                storage.load()
            else:
                storage = type("MemoryStorage", (), {"database": {"user": {}}})()
        if api is None:
            if player is None:
                from .api import NetEase

                api = NetEase()
            else:
                api = type("MissingApi", (), {})()
        if player is None:
            from .player import Player

            player = Player(ui=TextualUiBridge())
        self.player: Any = player
        self.api: Any = api
        self.storage: Any = storage
        self.state = TextualState()
        self.refresh()

    def refresh(self) -> TextualState:
        player = self.player
        info = player.info
        songs = player.songs
        queue = tuple(
            songs[str(song_id)]
            for song_id in info.get("player_list", [])
            if str(song_id) in songs
        )
        current = player.current_song if not player.is_empty else {}
        self.state.current_song = current or {}
        self.state.elapsed = float(getattr(player, "process_location", 0) or 0)
        self.state.duration = float(
            getattr(player, "process_length", 0) or current.get("duration", 0) or 0
        )
        self.state.playing = bool(getattr(player, "playing_flag", False))
        self.state.volume = int(info.get("playing_volume", 60))
        mode = int(info.get("playing_mode", 0))
        self.state.playing_mode = (
            MODE_NAMES[mode] if 0 <= mode < len(MODE_NAMES) else MODE_NAMES[0]
        )
        self.state.queue = queue
        self.state.queue_index = int(info.get("idx", 0))
        self.state.user = dict(self.storage.database.get("user", {}))
        return self.state

    def toggle(self) -> TextualState:
        if not self.player.is_empty:
            self.player.play_or_pause(self.player.index, True)
        return self.refresh()

    def play_index(self, index: int) -> TextualState:
        if 0 <= index < len(self.player.info.get("player_list", [])):
            self.player.play_or_pause(index, True)
        return self.refresh()

    def next(self) -> TextualState:
        if not self.player.is_empty:
            self.player.next()
        return self.refresh()

    def previous(self) -> TextualState:
        if not self.player.is_empty:
            self.player.prev()
        return self.refresh()

    def change_volume(self, delta: int) -> TextualState:
        self.player.tune_volume(delta)
        return self.refresh()

    def change_mode(self) -> TextualState:
        self.player.change_mode()
        return self.refresh()

    def stop(self) -> TextualState:
        self.player.stop()
        return self.refresh()

    def show_menu(self) -> TextualState:
        self.state.page = "menu"
        self.state.page_title = "主菜单"
        self.state.page_items = self.MENU_ITEMS
        self.state.selected_index = 0
        return self.state

    def load_menu_item(self, index: int) -> TextualState:
        """Load one of the legacy main-menu channels without creating curses."""
        if not 0 <= index < len(self.MENU_ITEMS):
            return self.state
        label = self.MENU_ITEMS[index]
        if label in ("搜索", "帮助"):
            self.state.page = "search" if label == "搜索" else "help"
            self.state.page_title = label
            return self.state

        user_id = self.state.user.get("user_id")
        handlers = {
            "排行榜": (lambda: self.api.toplists, "toplists", "排行榜"),
            "艺术家": (self.api.top_artists, "artists", "艺术家"),
            "新碟上架": (self.api.new_albums, "albums", "新碟上架"),
            "精选歌单": (self.api.top_playlists, "top_playlists", "精选歌单"),
            "我的歌单": (
                lambda: self.api.user_playlist(user_id),
                "playlists",
                "我的歌单",
            ),
            "我的云盘": (lambda: self.api.user_cloud(), "cloud_songs", "我的云盘"),
            "主播电台": (self.api.djRadios, "djRadios", "主播电台"),
            "每日推荐歌曲": (self.api.recommend_playlist, "songs", "每日推荐歌曲"),
            "每日推荐歌单": (
                self.api.recommend_resource,
                "top_playlists",
                "每日推荐歌单",
            ),
            "私人FM": (self.api.personal_fm, "fmsongs", "私人FM"),
        }
        callback, datatype, title = handlers[label]
        if not user_id and label in (
            "我的歌单",
            "我的云盘",
            "每日推荐歌曲",
            "每日推荐歌单",
        ):
            self.state.error = "请先登录"
            return self.state
        raw_items = callback() or []
        items = (
            self.api.dig_info(raw_items, datatype)
            if datatype not in ("djRadios", "toplists")
            else raw_items
        )
        self.state.page = "list"
        self.state.page_title = title
        self.state.page_items = tuple(items)
        self.state.selected_index = 0
        self.state.breadcrumbs = ("网易云音乐", title)
        self.state.error = ""
        return self.state

    def help_text(self) -> str:
        return (
            "快捷键\n\n"
            "j/k 选择项目    Enter 播放/进入\n"
            "Space 播放/暂停  [ / ] 上一曲/下一曲\n"
            "+/- 音量         P 播放模式\n"
            "m 菜单            f 搜索\n"
            "Esc 返回          q 退出"
        )

    @property
    def keymap(self) -> dict[str, str]:
        from .config import Config

        return dict(Config().get("keymap"))

    def begin_login(self) -> tuple[str, str]:
        unikey = self.api.login_qr_key()
        if not unikey:
            raise RuntimeError("无法获取登录二维码")
        import qrcode

        qr = qrcode.QRCode(border=1)
        qr.add_data(self.api.login_qr_url(unikey))
        qr.make(fit=True)
        buffer = io.StringIO()
        qr.print_ascii(out=buffer, invert=True)
        return unikey, buffer.getvalue().rstrip()

    def check_login(self, unikey: str) -> str:
        response = self.api.login_qr_check(unikey)
        code = response.get("code")
        status = {801: "等待扫码...", 802: "已扫码，请确认", 800: "二维码已过期"}
        if code != 803:
            return status.get(code, f"登录状态：{code}")
        info = self.api.get_account_info()
        account = info.get("account") or {}
        profile = info.get("profile") or {}
        nickname = profile.get("nickname") or ""
        self.storage.login(nickname, "", account.get("id"), nickname)
        self.state.user = dict(self.storage.database.get("user", {}))
        return f"登录成功：{nickname}"

    def search(
        self, keyword: str, category: str = "song", limit: int = 20
    ) -> list[dict[str, Any]]:
        type_map = {
            "song": (1, "songs"),
            "artist": (100, "artists"),
            "album": (10, "albums"),
            "playlist": (1000, "playlists"),
        }
        api_type, result_key = type_map[category]
        result = self.api.search(keyword, api_type, limit=limit) or {}
        payload = result.get("result", result)
        items = payload.get(result_key, [])
        return self.api.dig_info(items, result_key) if items else []

    def load_songs(
        self,
        title: str,
        songs: list[dict[str, Any]],
        source: tuple[str, ...] | None = None,
    ) -> TextualState:
        self.player.new_player_list("songs", title, songs, -1)
        self.state.page = "queue"
        self.state.page_title = title
        self.state.breadcrumbs = source or ("歌单来源", title)
        return self.refresh()

    def append_songs(self, songs: list[dict[str, Any]]) -> TextualState:
        self.player.append_songs(songs)
        return self.refresh()

    def open_item(self, index: int) -> TextualState:
        items = list(self.state.page_items)
        if not 0 <= index < len(items):
            return self.state
        item = items[index]
        if isinstance(item, dict) and item.get("song_id"):
            self.load_songs(self.state.page_title, items)
            return self.play_index(index)
        if isinstance(item, dict) and item.get("playlist_id"):
            songs = self.api.playlist_songlist(item["playlist_id"])
            normalized = self.api.dig_info(songs, "songs")
            return self.load_songs(
                item.get("playlist_name", self.state.page_title), normalized
            )
        if isinstance(item, dict) and item.get("album_id"):
            songs = self.api.dig_info(self.api.album(item["album_id"]), "songs")
            return self.load_songs(
                item.get("albums_name", self.state.page_title), songs
            )
        if isinstance(item, dict) and item.get("artist_id"):
            albums = self.api.dig_info(
                self.api.get_artist_album(item["artist_id"]), "albums"
            )
            self.state.page_items = tuple(albums)
            self.state.page_title = item.get("artists_name", self.state.page_title)
            return self.state
        if self.state.page_title == "排行榜" and isinstance(item, str):
            songs = self.api.dig_info(self.api.top_songlist(index), "songs")
            return self.load_songs(item, songs)
        if isinstance(item, dict) and item.get("id") and item.get("name"):
            programs = self.api.dig_info(
                self.api.alldjprograms(item["id"]), "djprograms"
            )
            self.state.page_items = tuple(programs)
            self.state.page_title = item["name"]
        return self.state

    def remove_index(self, index: int) -> TextualState:
        items = self.player.info.get("player_list", [])
        if not 0 <= index < len(items):
            return self.refresh()
        if index == self.player.info.get("idx", 0):
            self.player.stop()
        items.pop(index)
        current = int(self.player.info.get("idx", 0))
        self.player.info["idx"] = max(0, min(current, len(items) - 1)) if items else 0
        save = getattr(self.storage, "save", None)
        if callable(save):
            save()
        return self.refresh()

    def clear_queue(self) -> TextualState:
        self.player.stop()
        self.player.new_player_list("", "", [], -1)
        self.player.info["idx"] = 0
        save = getattr(self.storage, "save", None)
        if callable(save):
            save()
        return self.refresh()

    def show_lyrics(self) -> TextualState:
        song_id = self.state.current_song.get("song_id")
        if not song_id:
            self.state.error = "当前没有歌曲"
            return self.state
        lyric = self.api.song_lyric(song_id) or {}
        lines = tuple(lyric.get("lyric", []) or [])
        self.state.page = "lyrics"
        self.state.page_title = f"歌词：{self.state.current_song.get('song_name', '')}"
        self.state.page_items = lines
        return self.state

    def show_comments(self) -> TextualState:
        song_id = self.state.current_song.get("song_id")
        if not song_id:
            self.state.error = "当前没有歌曲"
            return self.state
        response = self.api.song_comments(song_id, limit=100) or {}
        comments = list(response.get("hotComments", [])) + list(
            response.get("comments", [])
        )
        self.state.page = "comments"
        self.state.page_title = f"评论：{self.state.current_song.get('song_name', '')}"
        self.state.page_items = tuple(
            f"{comment.get('user', {}).get('nickname', '用户')}：{comment.get('content', '')}"
            for comment in comments
        )
        return self.state

    def like_current(self) -> TextualState:
        song_id = self.state.current_song.get("song_id")
        if song_id:
            self.api.song_like(song_id, like=True)
        return self.refresh()

    def cache_current(self) -> TextualState:
        song = self.state.current_song
        if song and song.get("mp3_url"):
            self.player.cache_song(
                song.get("song_id"),
                song.get("song_name", ""),
                song.get("artist", ""),
                song.get("mp3_url"),
                song.get("type", ""),
                song.get("level", ""),
            )
        return self.refresh()

    def next_fm(self) -> TextualState:
        songs = self.api.dig_info(self.api.personal_fm() or [], "fmsongs")
        if songs:
            self.load_songs("私人FM", songs, ("网易云音乐", "私人FM"))
            return self.play_index(0)
        return self.refresh()

    def trash_fm(self) -> TextualState:
        song_id = self.state.current_song.get("song_id")
        if song_id:
            self.api.fm_trash(song_id)
        return self.next_fm()
