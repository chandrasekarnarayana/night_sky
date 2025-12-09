"""Module entrypoint to allow `python -m night_sky`."""
from .app import run


def main():
    raise SystemExit(run())


if __name__ == '__main__':
    main()
