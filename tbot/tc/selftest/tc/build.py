import typing
import tbot
from tbot.machine import linux, connector

__all__ = ("selftest_tc_build_toolchain",)


class LocalDummyBuildhost(connector.SubprocessConnector, linux.Bash, linux.Builder):
    name = "dummy-build"

    @property
    def toolchains(self) -> typing.Dict[str, linux.build.Toolchain]:
        """Return toolchains available on this host."""
        return {
            "selftest-toolchain": linux.build.EnvScriptToolchain(
                self.workdir / ".selftest-toolchain.sh"
            )
        }

    @staticmethod
    def prepare(h: linux.LinuxShell) -> None:
        h.exec0(
            "echo",
            "export CC=dummy-none-gcc",
            linux.RedirStdout(h.workdir / ".selftest-toolchain.sh"),
        )


@tbot.testcase
def selftest_tc_build_toolchain(lab: typing.Optional[linux.Lab] = None,) -> None:
    """Test connecting to a buildhost and enabling a toolchain on there."""
    with LocalDummyBuildhost() as bh:
        tbot.log.message("Creating dummy toolchain ...")
        bh.prepare(bh)

        tbot.log.message("Attempt using it ...")
        cc = bh.env("CC")
        assert cc != "dummy-none-gcc", repr(cc)

        with bh.enable("selftest-toolchain"):
            cc = bh.env("CC")
            assert cc == "dummy-none-gcc", repr(cc)

        cc = bh.env("CC")
        assert cc != "dummy-none-gcc", repr(cc)
