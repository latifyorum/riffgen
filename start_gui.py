"""Double-click (or run `python start_gui.py`) to start the UI.

The working directory does not matter; the riffgen package is found next to this file.
Extra flags are passed on: python start_gui.py --port 8800 --no-browser --lang tr
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from riffgen import i18n  # noqa: E402  (no third-party imports, safe before the mido check)

i18n.set_lang(i18n.pick_lang(sys.argv[1:]))
t = i18n.t


def _pause():
    try:
        input("\n" + t("s.enter"))
    except EOFError:
        pass


try:
    from riffgen.gui import main
except ModuleNotFoundError as e:
    print(t("s.missing", name=e.name))
    print(t("s.fix"))
    _pause()
    sys.exit(1)

if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except SystemExit as e:
        if isinstance(e.code, str):
            print(e.code)
            _pause()
        raise
    except Exception as e:  # keep the window open so the message can be read
        print(t("s.error", e=e))
        _pause()
        sys.exit(1)
