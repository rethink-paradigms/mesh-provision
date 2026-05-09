import pytest


class TestDeletedModulesGone:
    def test_deploy_app_module_gone(self):
        with pytest.raises(ModuleNotFoundError):
            from mesh.workloads.deploy_app import deploy_app  # noqa: F401

    def test_deploy_lite_web_service_module_gone(self):
        with pytest.raises(ModuleNotFoundError):
            from mesh.workloads.deploy_lite_web_service import deploy_lite_web_service  # noqa: F401

    def test_manage_secrets_module_gone(self):
        with pytest.raises(ModuleNotFoundError):
            from mesh.workloads.manage_secrets import manage  # noqa: F401


class TestDeployCommandGone:
    def test_deploy_command_gone(self):
        from mesh.cli.main import app

        command_names = [cmd.name for cmd in app.registered_commands]
        assert "deploy" not in command_names


class TestDeadSymbolsGone:
    def test_node_role_gone(self):
        with pytest.raises(ImportError):
            from mesh.shared import NodeRole  # noqa: F401

    def test_mesh_config_dir_gone(self):
        with pytest.raises(ImportError):
            from mesh.shared import MESH_CONFIG_DIR  # noqa: F401


class TestPreservedModules:
    def test_deploy_lite_ingress_preserved(self):
        from mesh.workloads.deploy_lite_ingress.deploy import deploy_lite_ingress  # noqa: F401
        assert True
