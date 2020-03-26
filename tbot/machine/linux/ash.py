# tbot, Embedded Automation Tool
# Copyright (C) 2019  Harald Seiler
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import contextlib
import re
import shlex
import shutil
import typing

import tbot
from .. import channel
from . import linux_shell, util, special, path

TBOT_PROMPT = b"TBOT-VEJPVC1QUk9NUFQK$ "

Self = typing.TypeVar("Self", bound="Ash")


class Ash(linux_shell.LinuxShell):
    """Ash/Dash shell."""

    @contextlib.contextmanager
    def _init_shell(self) -> typing.Iterator:
        try:
            # Wait for shell to appear
            util.wait_for_shell(self.ch)

            # Set a blacklist of control characters.  These characters are
            # known to mess up the state of the shell.  They are:
            self.ch._write_blacklist = [
                0x03,  # ETX  | End of Text / Interrupt
                0x04,  # EOT  | End of Transmission
                0x08,  # BS   | Backspace
                0x09,  # HT   | Horizontal Tab
                0x0E,  # SO   | Shift Out
                0x10,  # DLE  | Data Link Escape
                0x11,  # DC1  | Device Control One (XON)
                0x12,  # DC2  | Device Control Two
                0x13,  # DC3  | Device Control Three (XOFF)
                0x14,  # DC4  | Device Control Four
                0x15,  # NAK  | Negative Acknowledge
                0x16,  # SYN  | Synchronous Idle
                0x17,  # ETB  | End of Transmission Block
                0x19,  # EM   | End of Medium
                0x1A,  # SUB  | Substitute / Suspend Process
                0x1B,  # ESC  | Escape
                0x1C,  # FS   | File Separator
                0x1F,  # US   | Unit Separator
                0x7F,  # DEL  | Delete
            ]

            # Set prompt to a known string
            #
            # `read_back=True` is needed here so the following
            # read_until_prompt() will not accidentally detect the prompt in
            # the sent command if the connection is slow.
            #
            # To safeguard the process even further, the prompt is mangled in a
            # way which will be unfolded by the shell.  This will ensure tbot
            # won't accidentally read the prompt back early.
            self.ch.sendline(
                b"PROMPT_COMMAND=''; PS1='"
                + TBOT_PROMPT[:6]
                + b"''"
                + TBOT_PROMPT[6:]
                + b"'",
                read_back=True,
            )
            self.ch.prompt = TBOT_PROMPT
            self.ch.read_until_prompt()

            # Disable history
            self.ch.sendline("unset HISTFILE")
            self.ch.read_until_prompt()

            # Disable line editing
            #
            # Not really possible on ash.  Instead, make the terminal really
            # wide and hope for the best ...
            self.ch.sendline("stty cols 1024")
            self.ch.read_until_prompt()

            # Set secondary prompt to ""
            self.ch.sendline("PS2=''")
            self.ch.read_until_prompt()

            yield None
        finally:
            pass

    def escape(
        self: Self, *args: typing.Union[str, special.Special[Self], path.Path[Self]]
    ) -> str:
        string_args = []
        for arg in args:
            if isinstance(arg, str):
                string_args.append(shlex.quote(arg))
            elif isinstance(arg, linux_shell.Special):
                string_args.append(arg._to_string(self))
            elif isinstance(arg, path.Path):
                if arg.host != self:
                    raise Exception(f"{arg!r} is for another host!")
                string_args.append(shlex.quote(arg._local_str()))
            else:
                raise TypeError(f"{type(arg)!r} is not a supported argument type!")

        return " ".join(string_args)

    def exec(
        self: Self, *args: typing.Union[str, special.Special[Self], path.Path[Self]]
    ) -> typing.Tuple[int, str]:
        cmd = self.escape(*args)

        with tbot.log_event.command(self.name, cmd) as ev:
            self.ch.sendline(cmd, read_back=True)
            with self.ch.with_stream(ev, show_prompt=False):
                out = self.ch.read_until_prompt()
            ev.data["stdout"] = out

            self.ch.sendline("echo $?", read_back=True)
            retcode = self.ch.read_until_prompt()

        return (int(retcode), out)

    def exec0(
        self: Self, *args: typing.Union[str, special.Special[Self], path.Path[Self]]
    ) -> str:
        retcode, out = self.exec(*args)
        if retcode != 0:
            cmd = self.escape(*args)
            raise Exception(f"command {cmd!r} failed")
        return out

    def test(
        self: Self, *args: typing.Union[str, special.Special[Self], path.Path[Self]]
    ) -> bool:
        retcode, _ = self.exec(*args)
        return retcode == 0

    def env(
        self: Self, var: str, value: typing.Union[str, path.Path[Self], None] = None
    ) -> str:
        return util.posix_environment(self, var, value)

    def open_channel(
        self: Self, *args: typing.Union[str, special.Special[Self], path.Path[Self]]
    ) -> channel.Channel:
        cmd = self.escape(*args)

        # Disable the interrupt key in the outer shell
        self.ch.sendline("stty -isig", read_back=True)
        self.ch.read_until_prompt()

        with tbot.log_event.command(self.name, cmd):
            # Append `; exit` to ensure the channel won't live past the command
            # exiting
            self.ch.sendline(cmd + "; exit", read_back=True)

        return self.ch.take()

    @contextlib.contextmanager
    def subshell(
        self: Self, *args: typing.Union[str, special.Special[Self], path.Path[Self]]
    ) -> "typing.Iterator[Ash]":
        if args == ():
            cmd = "ash"
        else:
            cmd = self.escape(*args)
        tbot.log_event.command(self.name, cmd)
        self.ch.sendline(cmd)

        try:
            with self._init_shell():
                yield self
        finally:
            self.ch.sendline("exit")
            self.ch.read_until_prompt()

    def interactive(self) -> None:
        # Generate the endstring instead of having it as a constant
        # so opening this files won't trigger an exit
        endstr = (
            "INTERACTIVE-END-"
            + hex(165_380_656_580_165_943_945_649_390_069_628_824_191)[2:]
        )

        termsize = shutil.get_terminal_size()
        self.ch.sendline(self.escape("stty", "cols", str(termsize.columns)))
        self.ch.sendline(self.escape("stty", "rows", str(termsize.lines)))

        # Outer shell which is used to detect the end of the interactive session
        self.ch.sendline(f"ash")
        self.ch.sendline(f"PS1={endstr}")
        self.ch.read_until_prompt(prompt=endstr)

        # Inner shell which will be used by the user
        self.ch.sendline("ash")
        prompt = self.escape(
            f"\\[\\033[36m\\]{self.name}: \\[\\033[32m\\]\\w\\[\\033[0m\\]> "
        )
        self.ch.sendline(f"PS1={prompt}")

        self.ch.read_until_prompt(prompt=re.compile(b"> (\x1B\\[.{0,10})?"))
        self.ch.sendline()
        tbot.log.message("Entering interactive shell ...")

        self.ch.attach_interactive(end_magic=endstr)

        tbot.log.message("Exiting interactive shell ...")

        try:
            self.ch.sendline("exit")
            self.ch.read_until_prompt(timeout=0.5)
        except TimeoutError:
            raise Exception("Failed to reacquire shell after interactive session!")