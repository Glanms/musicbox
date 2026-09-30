import pytest

from NEMbox.textual_controller import (
    TextualController,
    TextualState,
    lyric_window,
    mode_display,
    parse_lyrics,
)


class FakePlayer:
    def __init__(self):
        self.info = {
            "player_list": ["1", "2"],
            "idx": 0,
            "playing_mode": 0,
            "playing_volume": 60,
        }
        self.songs = {
            "1": {
                "song_id": 1,
                "song_name": "一",
                "artist": "甲",
                "album_name": "甲辑",
            },
            "2": {
                "song_id": 2,
                "song_name": "二",
                "artist": "乙",
                "album_name": "乙辑",
            },
        }
        self.playing_flag = False
        self.process_location = 0
        self.process_length = 200
        self.calls = []

    @property
    def current_song(self):
        return self.songs[self.info["player_list"][self.info["idx"]]]

    @property
    def is_empty(self):
        return not self.info["player_list"]

    def play_or_pause(self, index, switch):
        self.calls.append(("play", index, switch))

    def next(self):
        self.calls.append(("next",))

    def prev(self):
        self.calls.append(("prev",))

    def tune_volume(self, delta):
        self.calls.append(("volume", delta))

    def change_mode(self):
        self.calls.append(("mode",))

    def stop(self):
        self.calls.append(("stop",))

    def new_player_list(self, type_name, title, songs, offset):
        self.info["player_list"] = [str(song["song_id"]) for song in songs]
        self.info["idx"] = 0

    def append_songs(self, songs):
        self.info["player_list"].extend(str(song["song_id"]) for song in songs)


def test_controller_builds_live_state_from_player():
    player = FakePlayer()
    controller = TextualController(player=player)

    state = controller.refresh()

    assert isinstance(state, TextualState)
    assert state.current_song["song_name"] == "一"
    assert state.queue_index == 0
    assert state.volume == 60
    assert state.queue_count == 2


def test_controller_routes_core_playback_actions_to_player():
    player = FakePlayer()
    controller = TextualController(player=player)

    controller.play_index(1)
    controller.next()
    controller.previous()
    controller.change_volume(10)
    controller.change_mode()

    assert player.calls == [
        ("play", 1, True),
        ("next",),
        ("prev",),
        ("volume", 10),
        ("mode",),
    ]


def test_controller_search_normalizes_api_results():
    class FakeApi:
        def search(self, keyword, api_type, limit):
            assert (keyword, api_type, limit) == ("周杰伦", 1, 5)
            return {"result": {"songs": [{"id": 7}]}}

        def dig_info(self, items, datatype):
            assert datatype == "songs"
            return [{"song_id": 7, "song_name": "晴天"}]

    controller = TextualController(player=FakePlayer(), api=FakeApi())

    assert controller.search("周杰伦", limit=5) == [{"song_id": 7, "song_name": "晴天"}]


def test_controller_exposes_menu_and_help_pages_without_curses():
    controller = TextualController(player=FakePlayer())

    state = controller.show_menu()

    assert state.page == "menu"
    assert "搜索" in state.page_items
    assert controller.help_text().startswith("快捷键")


def test_controller_login_qr_flow_keeps_cookie_details_out_of_state():
    class LoginApi:
        def login_qr_key(self):
            return "unikey"

        @staticmethod
        def login_qr_url(unikey):
            return f"https://example.test/{unikey}"

        def login_qr_check(self, unikey):
            return {"code": 803}

        def get_account_info(self):
            return {"account": {"id": 42}, "profile": {"nickname": "测试用户"}}

    class Storage:
        database = {"user": {}}

        def login(self, username, password, userid, nickname):
            self.database["user"] = {"user_id": userid, "nickname": nickname}

    controller = TextualController(
        player=FakePlayer(), api=LoginApi(), storage=Storage()
    )

    key, qr = controller.begin_login()
    result = controller.check_login(key)

    assert key == "unikey"
    assert len(qr.splitlines()) > 5
    assert result == "登录成功：测试用户"
    assert controller.state.user["user_id"] == 42


def test_controller_can_append_remove_and_clear_queue():
    player = FakePlayer()
    controller = TextualController(player=player)

    controller.append_songs([{"song_id": 3, "song_name": "三"}])
    controller.remove_index(0)
    assert player.info["player_list"] == ["2", "3"]

    controller.clear_queue()
    assert player.info["player_list"] == []


def test_controller_accepts_lyrics_returned_as_lines():
    class LyricsApi:
        def song_lyric(self, song_id):
            assert song_id == 1
            return ["[00:01.00]第一句", "[00:02.00]第二句"]

    player = FakePlayer()
    controller = TextualController(player=player, api=LyricsApi())
    controller.state.current_song = {"song_id": 1, "song_name": "测试"}

    state = controller.show_lyrics()

    assert state.page == "lyrics"
    assert state.page_items == ("[00:01.00]第一句", "[00:02.00]第二句")


def test_controller_opens_album_from_selected_song():
    class AlbumApi:
        def album(self, album_id):
            assert album_id == 9
            return [{"id": 3, "name": "专辑歌曲"}]

        def dig_info(self, items, datatype):
            assert datatype == "songs"
            return [{"song_id": 3, "song_name": items[0]["name"]}]

    player = FakePlayer()
    player.songs["3"] = {"song_id": 3, "song_name": "专辑歌曲"}
    controller = TextualController(player=player, api=AlbumApi())
    controller.state.page = "list"
    controller.state.page_title = "搜索结果"
    controller.state.page_items = (
        {"song_id": 7, "song_name": "歌曲", "album_id": 9, "album_name": "专辑"},
    )

    state = controller.open_album(0)

    assert state.page == "queue"
    assert state.page_title == "专辑"
    assert state.queue[0]["song_id"] == 3


def test_controller_adds_and_lists_local_collection():
    player = FakePlayer()
    storage = type(
        "Storage",
        (),
        {"database": {"user": {}, "collections": []}},
    )()
    controller = TextualController(player=player, storage=storage)
    controller.state.current_song = player.songs["1"]

    controller.add_to_collection()
    controller.add_to_collection()
    state = controller.show_collection()

    assert state.page == "collection"
    assert len(state.page_items) == 1
    assert state.page_items[0]["song_id"] == 1


@pytest.mark.parametrize(
    ("mode", "expected"),
    ((0, 3), (1, 4), (2, 3), (3, 0), (4, 1)),
)
def test_controller_toggles_shuffle_without_reusing_mode_cycle(mode, expected):
    player = FakePlayer()
    player.info["playing_mode"] = mode
    controller = TextualController(player=player)

    state = controller.toggle_shuffle()

    assert player.info["playing_mode"] == expected
    assert state.playing_mode == (
        "随机播放"
        if expected == 3
        else "随机循环"
        if expected == 4
        else "顺序循环"
        if expected == 1
        else "顺序播放"
    )


@pytest.mark.parametrize(
    ("mode", "expected"),
    ((0, 1), (1, 2), (2, 0), (3, 4), (4, 2)),
)
def test_controller_cycles_repeat_modes_independently(mode, expected):
    player = FakePlayer()
    player.info["playing_mode"] = mode
    controller = TextualController(player=player)

    controller.cycle_repeat()

    assert player.info["playing_mode"] == expected


def test_controller_derives_collection_count_and_current_membership():
    class Storage:
        database = {
            "user": {},
            "collections": [
                {"song_id": 1, "song_name": "一"},
                {"song_id": 9, "song_name": "九"},
            ],
        }

    state = TextualController(player=FakePlayer(), storage=Storage()).refresh()

    assert state.collection_count == 2
    assert state.current_collected is True


def test_controller_toggles_current_song_in_local_collection():
    class Storage:
        database = {
            "user": {},
            "collections": [{"song_id": 1, "song_name": "一"}],
        }

    controller = TextualController(player=FakePlayer(), storage=Storage())

    removed = controller.toggle_collection().current_collected
    restored = controller.toggle_collection().current_collected

    assert removed is False
    assert restored is True
    assert [song["song_id"] for song in Storage.database["collections"]] == [1]


def test_parse_lyrics_supports_multiple_timestamps_and_translation():
    lyrics = parse_lyrics(
        ["[00:01.00][00:02.50]第一句", "[00:04.00]第二句", '{"t": 1}'],
        ["[00:01.00]译句"],
    )

    assert [(line.timestamp, line.text, line.translation) for line in lyrics] == [
        (1.0, "第一句", "译句"),
        (2.5, "第一句", ""),
        (4.0, "第二句", ""),
    ]
    assert lyric_window(lyrics, 0) == (-1, "", "译句 || 第一句")
    assert lyric_window(lyrics, 1.5) == (0, "译句 || 第一句", "第一句")
    assert lyric_window(lyrics, 99) == (2, "第二句", "")


def test_mode_display_uses_short_icon_labels():
    assert mode_display("顺序播放") == "▶ 顺序"
    assert mode_display("顺序循环") == "↻ 循环"
    assert mode_display("单曲循环") == "↺ 单曲"
    assert mode_display("随机播放") == "⤨ 随机"
    assert mode_display("随机循环") == "⤨ 循环"
