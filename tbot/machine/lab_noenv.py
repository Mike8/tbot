"""
Labhost machine without environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
"""
import typing
import paramiko
import tbot
from . import machine

class MachineLabNoEnv(machine.Machine):
    """ Labhost machine without environment """
    def __init__(self) -> None:
        super().__init__()
        self.conn: typing.Optional[paramiko.SSHClient] = None

    def _setup(self,
               tb: 'tbot.TBot',
               previous: typing.Optional[machine.Machine] = None,
              ) -> 'MachineLabNoEnv':
        self.conn = tb.machines.connection
        super()._setup(tb, previous)
        return self

    def _exec(self,
              command: str,
              log_event: tbot.logger.ShellCommandLogEvent) -> typing.Tuple[int, str]:
        assert isinstance(self.conn, paramiko.SSHClient), \
            "Machine was not initialized correctly!"
        channel = self.conn.get_transport().open_session()
        channel.set_combine_stderr(True)
        channel.exec_command(command)
        stdout = channel.makefile().read()
        ret_code = channel.recv_exit_status()

        output = stdout.decode("utf-8") \
            .replace('\r\n', '\n') \
            .replace('\r', '\n')

        #FIXME: Make output appear instantly and not after the run is done
        for line in output.strip('\n').split('\n'):
            log_event.add_line(line)
        return ret_code, output

    @property
    def common_machine_name(self) -> str:
        """ Common name of this machine, always ``"labhost"`` """
        return "labhost"

    @property
    def unique_machine_name(self) -> str:
        """ Unique name of this machine, always ``"labhost-noenv"`` """
        return "labhost-noenv"
