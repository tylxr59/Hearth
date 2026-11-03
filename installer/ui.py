"""Terminal presentation for the guided wizards.

Standard library only: the wizard runs from an extracted source archive before
any virtual environment exists. Colour is used only on an interactive terminal
and honours ``NO_COLOR``/``TERM=dumb``. Every helper degrades to plain text, so
captured output and logs stay readable.
"""

import os
import re
import shutil
import sys
import textwrap
import time

_CODES = {
    "bold": "1",
    "dim": "2",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
}


def _tty():
    return sys.stdout.isatty()


def _color():
    return _tty() and not os.environ.get("NO_COLOR") and os.environ.get("TERM") != "dumb"


def _unicode():
    return "utf" in (getattr(sys.stdout, "encoding", "") or "").lower()


def _glyph(fancy, plain):
    return fancy if _unicode() else plain


def style(text, *names):
    if not names or not _color():
        return text
    return "\033[" + ";".join(_CODES[name] for name in names) + "m" + text + "\033[0m"


def width():
    return max(48, min(shutil.get_terminal_size((88, 24)).columns, 88))


def _wrap(text, indent="  ", hang=None):
    hang = indent if hang is None else hang
    lines = []
    for paragraph in str(text).split("\n"):
        lines.append(
            textwrap.fill(
                paragraph,
                width=width(),
                initial_indent=indent,
                subsequent_indent=hang,
                break_on_hyphens=False,
                break_long_words=False,
            )
            if paragraph.strip()
            else ""
        )
    return "\n".join(lines)


def blank():
    print()


def say(text):
    """An ordinary explanatory paragraph."""
    print(_wrap(text))


def muted(text):
    print(style(_wrap(text), "dim"))


def _mark(symbol, colour, text):
    print(_wrap(text, "  " + style(symbol, colour, "bold") + " ", "    "))


def ok(text):
    _mark(_glyph("✔", "OK"), "green", text)


def warn(text):
    _mark(_glyph("⚠", "!"), "yellow", text)


def fail(text):
    _mark(_glyph("✖", "X"), "red", text)


def info(text):
    _mark(_glyph("•", "-"), "cyan", text)


def action(text):
    """Something the person must physically do now."""
    _mark(_glyph("➜", "->"), "magenta", style(text, "bold"))


def bullets(items):
    for item in items:
        print(_wrap(item, "    " + _glyph("•", "-") + " ", "      "))


def numbered(items):
    for index, item in enumerate(items, 1):
        print(_wrap(item, f"    {index}. ", "       "))


def banner(title, subtitle=None, tag=None):
    rule = _glyph("━", "=") * width()
    print()
    print(style(rule, "dim"))
    print("  " + style(title, "bold", "yellow"))
    if subtitle:
        print("  " + subtitle)
    if tag:
        print("  " + style(tag, "dim"))
    print(style(rule, "dim"))


def step(number, total, title):
    label = f" Step {number} of {total} " + _glyph("·", "-") + f" {title} "
    lead = _glyph("━━", "==")
    tail = _glyph("━", "=") * max(2, width() - len(label) - len(lead))
    print()
    print(style(lead, "dim") + style(label, "bold", "cyan") + style(tail, "dim"))


def section(title):
    print()
    print("  " + style(title, "bold"))


def box(title, lines, colour="yellow"):
    """A highlighted block for decisions and important warnings."""
    bar = style(_glyph("┃", "|"), colour, "bold")
    print()
    print(f"  {bar} " + style(title, colour, "bold"))
    for line in lines:
        for wrapped in _wrap(line, "", "").split("\n"):
            print(f"  {bar} {wrapped}")


def prompt(text, hint=None):
    """Format a question for ``input``; the hint names the accepted answer."""
    arrow = style(_glyph("›", ">"), "cyan", "bold")
    suffix = f" {style(hint, 'dim')}" if hint else ""
    return f"\n  {arrow} {text}{suffix}: "


def confirm(ask, question):
    """A y/N question: only y or yes proceeds; Enter or anything else means no.

    Typed words are reserved for flash writes (INSTALL, RESTORE).
    """
    return ask(prompt(question, "[y/N]")).strip().lower() in ("y", "yes")


def duration(seconds):
    seconds = int(seconds)
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}m {seconds:02d}s" if minutes else f"{seconds}s"


def stage(number, total, label):
    """Announce a long-running stage. Workers print this; the wizard parses it."""
    print(f"[stage {number}/{total}] {label}", flush=True)


STAGE = re.compile(rb"\[stage (\d+)/(\d+)\] ([^\r\n]+)")


class Live:
    """One self-updating status line: spinner, bar, stage, elapsed time.

    The bar shows a real percentage when one is known (flash backup), otherwise
    completed stages. On a captured stream it prints only stage changes, 10%
    steps and an occasional heartbeat, so logs stay short.
    """

    FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    HEARTBEAT = 60

    def __init__(self, label):
        self.label, self.started = label, time.monotonic()
        self.stage = self.percent = None
        self.drawn, self.frame, self.reported = False, 0, -1
        self.heartbeat = self.started

    def set_label(self, label):
        if label != self.label:
            self.label = label
            if not _tty():
                print(f"  {label}")
            self.refresh()

    def set_stage(self, number, total, label):
        if (number, total) != self.stage:
            self.stage, self.percent, self.label = (number, total), None, label
            if not _tty():
                print(f"  [{number}/{total}] {label}")
            self.refresh()

    def set_percent(self, percent):
        percent = max(0, min(100, int(percent)))
        if self.percent is not None and percent <= self.percent:
            return
        self.percent = percent
        if not _tty() and (percent // 10 > self.reported // 10 or percent == 100):
            print(f"  {self.label}: {percent}%")
            self.reported = percent
        self.refresh()

    def _bar(self, fraction, size=24):
        full = round(fraction * size)
        return style(_glyph("█", "#") * full + _glyph("░", ".") * (size - full), "cyan")

    def refresh(self):
        now = time.monotonic()
        elapsed = duration(now - self.started)
        if not _tty():
            if now - self.heartbeat >= self.HEARTBEAT:
                print(f"  Still working ({elapsed} so far)")
                self.heartbeat = now
            return
        self.frame = (self.frame + 1) % len(self.FRAMES)
        spinner = style(self.FRAMES[self.frame] if _unicode() else "|/-\\"[self.frame % 4], "cyan")
        if self.percent is not None:
            gauge = f"{self._bar(self.percent / 100)} {self.percent:3d}%  "
        elif self.stage:
            done, total = self.stage
            gauge = f"{self._bar((done - 1) / total)} {done}/{total}  "
        else:
            gauge = ""
        tail = style(f"  {elapsed}", "dim")
        visible_gauge = len(re.sub(r"\033\[[0-9;]*m", "", gauge))
        room = max(8, width() - 6 - len(elapsed) - visible_gauge)
        label = self.label if len(self.label) <= room else self.label[: room - 1] + "…"
        text = gauge + label
        sys.stdout.write(f"\r\033[K  {spinner} {text}{tail}")
        sys.stdout.flush()
        self.drawn = True

    def clear(self):
        """Remove the status line before printing anything else."""
        if self.drawn:
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()
            self.drawn = False
