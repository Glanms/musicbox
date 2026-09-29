#!/usr/bin/env python
import sys
import traceback

from . import __version__

Menu = None

# Keep the flock fd open for the TUI process lifetime (see daemon.acquire_lock).
_lock_fd: int | None = None


def start():
    argv = sys.argv[1:]
    if argv in (["--textual"], ["--tui", "textual"]):
        _start_textual()
        return
    if argv == ["--curses"]:
        argv = []
    if argv:
        from .cli import main

        sys.exit(main(argv))

    # TUI and daemon are mutually exclusive: both contend for the same flock.
    global _lock_fd
    from .daemon import acquire_lock, is_daemon_running

    if is_daemon_running():
        print(
            "musicbox daemon 正在运行，TUI 与 daemon 互斥。\n"
            "请先 `musicbox daemon stop`，或直接用 `musicbox status` 等命令控制播放。",
            file=sys.stderr,
        )
        sys.exit(4)
    _lock_fd = acquire_lock()
    if _lock_fd is None:
        print("无法获取 musicbox 运行锁，可能已有实例在运行。", file=sys.stderr)
        sys.exit(1)

    global Menu
    if Menu is None:
        from .menu import Menu as MenuClass

        Menu = MenuClass

    nembox_menu = Menu()
    try:
        nembox_menu.start_fork(__version__)
    except (OSError, TypeError, ValueError, KeyError, IndexError):
        # clean up terminal while failed
        try:
            import _curses
            import curses

            curses.echo()
            curses.nocbreak()
            curses.endwin()
        except _curses.error:
            pass
        traceback.print_exc()


def _start_textual() -> None:
    """Start the Textual TUI with the same single-owner lock as curses."""
    global _lock_fd
    from .daemon import acquire_lock, is_daemon_running

    if is_daemon_running():
        print(
            "musicbox daemon 正在运行，Textual TUI 与 daemon 互斥。\n"
            "请先 `musicbox daemon stop`。",
            file=sys.stderr,
        )
        raise SystemExit(4)
    _lock_fd = acquire_lock()
    if _lock_fd is None:
        print("无法获取 musicbox 运行锁，可能已有实例在运行。", file=sys.stderr)
        raise SystemExit(1)

    from .textual_app import build_app
    from .textual_controller import TextualController

    controller = TextualController()
    app = build_app(controller=controller)
    try:
        app.run()
    finally:
        controller.stop()


if __name__ == "__main__":
    start()
