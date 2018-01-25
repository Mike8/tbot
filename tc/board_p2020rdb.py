"""
P2020RDB-PCA board specific testcases
-------------------------------------
"""
import os
import tbot

@tbot.testcase
def board_p2020rdb(tb):
    """
    P2020RDB-PCA board specific testcase to build U-Boot, flash it into
    NAND and run the U-Boot test suite
    """
    assert tb.shell.shell_type[0] == "sh", "Need an sh shell"

    tb.log.doc_log("""U-Boot on the P2020RDB-PCA board
============
""")
    tb.call("build_uboot")

    tb.call("p2020rdb_install_uboot")

    with tb.new_boardshell() as tbn:
        tbn.boardshell.poweron()

        tbn.call("check_uboot_version", uboot_bin="{builddir}/u-boot-with-spl.bin")

        env = tbn.boardshell.exec0("printenv", log_show=False)
        tbn.log.doc_appendix("U-Boot environment", f"""```sh
{env}
```""")

    tb.call("uboot_tests")

@tbot.testcase
def p2020rdb_install_uboot(tb):
    """ Install U-Boot into NAND flash of the P2020RDB-PCA """
    assert tb.shell.shell_type[0] == "sh", "Need an sh shell"

    tb.log.doc_log("""
## Installing U-Boot into NAND flash ##

In this guide, we are going to install U-Boot into NAND flash. Set the `SW3` switch \
to `11101010` to enable NAND boot. A copy of the U-Boot environment used, can be found \
in the appendix of this document.
Copy U-Boot into your tftp directory:
""")

    tftpdir = tb.call("setup_tftpdir")
    tb.call("cp_to_tftpdir", name="u-boot-with-spl.bin")

    tb.log.doc_log("Find out the size of the U-Boot binary, as we will need it later:\n")

    filename = os.path.join(tftpdir, "u-boot-with-spl.bin")
    size = tb.shell.exec0(f"printf '%x' `stat -c '%s' {filename}`")

    @tb.call
    def install(tb): #pylint: disable=unused-variable
        """ Actually flash to nand """

        tb.log.doc_log("Power on the board and download U-Boot via TFTP:\n")

        with tb.new_boardshell() as tbn:
            tbn.boardshell.poweron()
            filename = os.path.join(tb.config.get("tftp.boarddir"),
                                    tb.config.get("tftp.tbotsubdir"),
                                    "u-boot-with-spl.bin")
            tbn.boardshell.exec0(f"tftp 10000000 {filename}", log_show_stdout=False)

            tbn.log.doc_log("Write it into flash:\n")

            tbn.boardshell.exec0(f"nand device 0", log_show_stdout=False)
            tbn.boardshell.exec0(f"nand erase.spread 0 {size}")
            tbn.boardshell.exec0(f"nand write 10000000 0 {size}")

            tb.log.doc_log("Powercycle the board and check the U-Boot version:\n")