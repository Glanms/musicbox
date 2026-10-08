#!/usr/bin/env python
import argparse
import ipaddress
import os
import shlex
import subprocess
import sys
import traceback
from importlib import import_module

from . import __version__

Menu = None

# Keep the flock fd open for the TUI process lifetime (see daemon.acquire_lock).
_lock_fd: int | None = None


def start():
    argv = sys.argv[1:]
    if argv and argv[0] == "--web":
        options = _parse_web_options(argv[1:])
        _start_textual_web(options.host, options.port)
        return
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


def _parse_loopback_host(value: str) -> str:
    """Accept only numeric loopback addresses for the unauthenticated server."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "host must be a numeric loopback address"
        ) from error
    if not address.is_loopback:
        raise argparse.ArgumentTypeError("host must be a loopback address")
    return value


def _parse_web_options(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="musicbox --web")
    parser.add_argument("--host", type=_parse_loopback_host, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    options = parser.parse_args(argv)
    if not 1 <= options.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    return options


def _textual_web_command() -> str:
    """Return the fixed command textual-serve runs for each browser session."""
    command = [sys.executable, "-m", "NEMbox", "--textual"]
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return shlex.join(command)


def _start_textual_web(host: str, port: int) -> None:
    """Serve the Textual dashboard over a loopback-only browser connection."""
    try:
        server_module = import_module("textual_serve.server")
    except ImportError:
        print(
            "Web mode requires the optional dependency. Run `uv sync --extra web`.",
            file=sys.stderr,
        )
        raise SystemExit(2) from None

    server = server_module.__dict__["Server"](
        _textual_web_command(),
        host=host,
        port=port,
        title="NetEase MusicBox",
    )
    server.serve()


if __name__ == "__main__":
    start()
