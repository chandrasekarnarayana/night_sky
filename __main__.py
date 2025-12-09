"""Module entrypoint to allow `python -m night_sky`.

Delegates to :func:`night_sky.app.run` so the package can be executed as
a script and will start the GUI just like the console script entrypoint.
"""
from .app import run


if __name__ == "__main__":
    run()
"""Module entrypoint to allow `python -m night_sky`."""
from .app import run


def main():
    raise SystemExit(run())


if __name__ == '__main__':
    main()
