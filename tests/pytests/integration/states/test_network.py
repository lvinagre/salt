"""
Tests for the network state
"""

import logging
import socket

import distro
import pytest

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
]


@pytest.fixture
def context(salt_call_cli):
    """
    establishes the context for each test, so each of them execute as an entire separate test.
    """

    # Map dummy interface
    dummy_interface = {
        "iface_enabled": True,
        "iface_name": "salttest0",
        "iface_proto": "manual" if "debian" in distro.id() + distro.like() else "none",
        "iface_type": "eth",
    }

    # Setup dummy interface
    salt_call_cli.run("kmod.present", name="dummy")
    salt_call_cli.run(
        "cmd.run", cmd="ip link add {} type dummy".format(dummy_interface["iface_name"])
    )
    # and backup config file in debian
    if "debian" in distro.id() + distro.like():
        salt_call_cli.run(
            "cmd.run", cmd="cp -p /etc/network/interfaces /etc/network/interfaces.bkp"
        )

    # Yield dummy interface data
    yield dummy_interface

    # Teardown dummy interface
    salt_call_cli.run("kmod.absent", name="dummy")
    # and restore OS network config to previous
    if "debian" in distro.id() + distro.like():
        salt_call_cli.run(
            "cmd.run", cmd="mv /etc/network/interfaces.bkp /etc/network/interfaces"
        )
    else:
        salt_call_cli.run(
            "cmd.run",
            cmd="rm /etc/sysconfig/network-scripts/ifcfg-{}".format(
                dummy_interface["iface_name"]
            ),
        )


@pytest.mark.skip_if_not_root
@pytest.mark.skipif(
    "debian" not in distro.id() + distro.like()
    and "rhel" not in distro.id() + distro.like(),
    reason="Network state only supports Debian and RHEL based systems.",
)
@pytest.mark.usefixtures("context", "salt_call_cli", "salt_master")
class TestNetwork:
    def addInterface(
        self,
        context,
        salt_call_cli,
        salt_master,
        iname=None,
        ienabled=None,
        iproto=None,
        itype=None,
        testFlag=False,
    ):
        """
        Shortcut to add interface in each test as needed.
        """
        # Map default values to context
        iname = context["iface_name"] if iname is None else iname
        ienabled = context["iface_enabled"] if ienabled is None else ienabled
        iproto = context["iface_proto"] if iproto is None else iproto
        itype = context["iface_type"] if itype is None else itype

        # Map state content
        state_contents = """
            {0}_interface:
              network.managed:
                - name: {0}
                - enabled: {1}
                - proto: {2}
                - type: {3}
            """.format(
            iname, ienabled, iproto, itype
        )

        # "Add" state to salt-master base env
        state_tempfile = salt_master.state_tree.base.temp_file(
            "dummy_interface.sls", state_contents
        )

        # "Get" a run of the state
        with state_tempfile:
            return salt_call_cli.run("state.apply", "dummy_interface", test=testFlag)

    def test_managed_addInterface0(self, context, salt_call_cli, salt_master):
        """
        network.managed add new interface with test flag
        """
        # Execute test
        ret = self.addInterface(
            context=context,
            salt_call_cli=salt_call_cli,
            salt_master=salt_master,
            testFlag=True,
        )

        ## and validate results
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is None
        assert state_run["comment"] == "Interface {} is set to be added.".format(
            context["iface_name"]
        )
        assert state_run["changes"] == {}

    def test_managed_addInterface1(self, context, salt_call_cli, salt_master):
        """
        network.managed add new interface
        """
        # Execute test
        ret = self.addInterface(
            context=context, salt_call_cli=salt_call_cli, salt_master=salt_master
        )

        ## and validate results
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Interface {} added.".format(
            context["iface_name"]
        )
        assert state_run["changes"]["interface"] == "Added network interface."

    def test_managed_existingInterfaceNoChanges0(
        self, context, salt_call_cli, salt_master
    ):
        """
        network.managed with existing interfaces without changing configs with test flag
        """
        # Add test interface
        self.addInterface(
            context=context, salt_call_cli=salt_call_cli, salt_master=salt_master
        )

        # Execute test
        ret = self.addInterface(
            context=context,
            salt_call_cli=salt_call_cli,
            salt_master=salt_master,
            testFlag=True,
        )

        # and validate results
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Interface {} is up to date.".format(
            context["iface_name"]
        )
        assert state_run["changes"] == {}

    def test_managed_existingInterfaceNoChanges1(
        self, context, salt_call_cli, salt_master
    ):
        """
        network.managed with existing interfaces without changing configs
        """
        # Add test interface
        self.addInterface(
            context=context, salt_call_cli=salt_call_cli, salt_master=salt_master
        )

        # Execute test
        ret = self.addInterface(
            context=context, salt_call_cli=salt_call_cli, salt_master=salt_master
        )

        # and validate results
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True
        assert state_run["comment"] == "Interface {} is up to date.".format(
            context["iface_name"]
        )
        assert state_run["changes"] == {}

    def test_managed_existingInterfaceWithChanges0(
        self, context, salt_call_cli, salt_master
    ):
        """
        network.managed with changes to existing interface with test flag
        """
        # Add test interface
        self.addInterface(
            context=context, salt_call_cli=salt_call_cli, salt_master=salt_master
        )

        # Execute test
        ret = self.addInterface(
            context=context,
            salt_call_cli=salt_call_cli,
            salt_master=salt_master,
            iproto="dhcp",
            testFlag=True,
        )

        ## and validate results
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is None
        assert (
            "Interface {} is set to be updated:".format(context["iface_name"])
            in state_run["comment"]
        )

    def test_managed_existingInterfaceWithChanges1(
        self, context, salt_call_cli, salt_master
    ):
        """
        network.managed with changes to existing interface and try to start it (previously down)
        """
        # Add test interface
        self.addInterface(
            context=context,
            salt_call_cli=salt_call_cli,
            salt_master=salt_master,
            ienabled=False,
        )

        # Map change per OS
        temp_iproto = "loopback" if "debian" in distro.id() + distro.like() else "bootp"

        # Execute test
        ret = self.addInterface(
            context=context,
            salt_call_cli=salt_call_cli,
            salt_master=salt_master,
            iproto=temp_iproto,
        )

        # and validate results
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True
        assert (
            "Interface {} updated.".format(context["iface_name"])
            in state_run["comment"]
        )
        assert (
            "Interface {} is up".format(context["iface_name"])
            in state_run["changes"]["status"]
        )

    def test_managed_existingInterfaceWithChanges2(
        self, context, salt_call_cli, salt_master
    ):
        """
        network.managed with changes to existing interface and set disabled (previously enabled)
        """
        # Add test interface
        self.addInterface(
            context=context, salt_call_cli=salt_call_cli, salt_master=salt_master
        )

        # Map change per OS
        temp_iproto = "loopback" if "debian" in distro.id() + distro.like() else "bootp"

        # Execute test
        ret = self.addInterface(
            context=context,
            salt_call_cli=salt_call_cli,
            salt_master=salt_master,
            ienabled=False,
            iproto=temp_iproto,
        )

        # and validate results
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True
        assert (
            "Interface {} updated.".format(context["iface_name"])
            in state_run["comment"]
        )
        assert (
            "Interface {} down".format(context["iface_name"])
            in state_run["changes"]["status"]
        )

    def test_managed_existingInterfaceWithChanges3(
        self, context, salt_call_cli, salt_master
    ):
        """
        network.managed with changes to existing interface and try to restart it (previously enabled)
        """
        # Add test interface
        self.addInterface(
            context=context, salt_call_cli=salt_call_cli, salt_master=salt_master
        )

        # Map change per OS
        temp_iproto = "loopback" if "debian" in distro.id() + distro.like() else "bootp"

        # Execute test
        ret = self.addInterface(
            context=context,
            salt_call_cli=salt_call_cli,
            salt_master=salt_master,
            iproto=temp_iproto,
        )

        # and validate results
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is True
        assert (
            "Interface {} updated.".format(context["iface_name"])
            in state_run["comment"]
        )
        assert (
            "Interface {} restart to validate".format(context["iface_name"])
            in state_run["changes"]["status"]
        )

    def test_routes(self, salt_call_cli, salt_master):
        """
        network.routes add empty routes
        """
        # Set test route name
        test_route = "salttest_route"

        # Map state content
        state_contents = """
            {0}:
              network.routes:
                - name: {0}
                - routes: []
            """.format(
            test_route
        )

        # "Add" state to salt-master base env
        state_tempfile = salt_master.state_tree.base.temp_file(
            "dummy_route.sls", state_contents
        )

        # "Get" a run of the state
        with state_tempfile:
            ret = salt_call_cli.run("state.apply", "dummy_route", test=True)

        # and validate results
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        if "debian" in distro.id() + distro.like():
            assert state_run["result"] is None
            assert (
                state_run["comment"]
                == f"Interface {test_route} routes are set to be added."
            )
        else:
            assert state_run["result"] is True
            assert (
                state_run["comment"] == f"Interface {test_route} routes are up to date."
            )

    def test_system(self, salt_call_cli, salt_master):
        """
        network.system add/change with test flag
        """
        # Map state content
        state_contents = """
            test_network_system:
              network.system:
                - enabled: true
                - hostname: {}
            """.format(
            socket.gethostname()
        )

        # "Add" state to salt-master base env
        state_tempfile = salt_master.state_tree.base.temp_file(
            "dummy_system.sls", state_contents
        )

        # Get network settings
        global_settings = salt_call_cli.run("ip.get_network_settings")

        # "Get" a run of the state
        with state_tempfile:
            ret = salt_call_cli.run("state.apply", "dummy_system", test=True)

        # and validate results
        assert ret.returncode == 0
        assert ret.data
        state_run = next(iter(ret.data.values()))
        assert state_run["result"] is None
        assert (
            "Global network settings are set to be {}".format(
                "added" if not global_settings else "updated"
            )
            in state_run["comment"]
        )
