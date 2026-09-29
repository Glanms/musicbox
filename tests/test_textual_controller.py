from NEMbox.textual_controller import TextualController, TextualState


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
