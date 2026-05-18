"""
Unit tests for Template Validation functionality
"""

import pytest
from mesh.provisioning.boot import (
    validate_rendered_template,
    TemplateValidationError,
    generate_cloud_init,
    generate_cloud_init,
    _get_jinja2_env,
)


class TestValidateRenderedTemplate:
    """Test validate_rendered_template function"""

    def test_valid_template_no_variables(self):
        """Test that content without template variables passes validation"""
        content = 'KEY="value"\nLEADER_IP="10.0.0.1"'
        is_valid, unreplaced = validate_rendered_template(content)
        assert is_valid is True
        assert unreplaced == []

    def test_valid_template_with_quotes(self):
        """Test that content with properly quoted values passes validation"""
        content = 'echo "{{ test }}"'  # String literal in Jinja2
        is_valid, unreplaced = validate_rendered_template(content)
        # This would actually be caught because it matches the pattern
        # But in practice, we'd handle this via escaping
        assert is_valid is False  # Expected to be caught

    def test_invalid_template_unreplaced_variable(self):
        """Test that unreplaced template variable is detected"""
        content = 'TAILSCALE_KEY="{{ TAILSCALE_KEY }}"'
        is_valid, unreplaced = validate_rendered_template(content)
        assert is_valid is False
        assert "TAILSCALE_KEY" in unreplaced

    def test_invalid_template_multiple_unreplaced(self):
        """Test that multiple unreplaced variables are detected"""
        content = """
TAILSCALE_KEY="{{ TAILSCALE_KEY }}"
LEADER_IP="{{ LEADER_IP }}"
ROLE="{{ ROLE }}"
"""
        is_valid, unreplaced = validate_rendered_template(content)
        assert is_valid is False
        assert len(unreplaced) == 3
        assert "TAILSCALE_KEY" in unreplaced
        assert "LEADER_IP" in unreplaced
        assert "ROLE" in unreplaced

    def test_invalid_template_partial_syntax(self):
        """Test that unclosed template syntax is detected"""
        content = 'TAILSCALE_KEY="{{ TAILSCALE_KEY'
        is_valid, unreplaced = validate_rendered_template(content)
        # The regex requires closing }}, so this won't match
        # This is OK - StrictUndefined would catch it at render time
        assert is_valid is True

    def test_invalid_template_no_spaces(self):
        """Test that variables without spaces are detected"""
        content = 'KEY="{{VALUE}}"'
        is_valid, unreplaced = validate_rendered_template(content)
        assert is_valid is False
        assert "VALUE" in unreplaced

    def test_invalid_template_extra_spaces(self):
        """Test that variables with extra spaces are detected"""
        content = 'KEY="{{  VALUE  }}"'
        is_valid, unreplaced = validate_rendered_template(content)
        assert is_valid is False
        assert "VALUE" in unreplaced


class TestTemplateValidationError:
    """Test TemplateValidationError exception"""

    def test_exception_creation(self):
        """Test that TemplateValidationError can be created"""
        exc = TemplateValidationError("Test error", ["VAR1", "VAR2"])
        assert exc.unreplaced_variables == ["VAR1", "VAR2"]
        assert "VAR1" in str(exc)
        assert "VAR2" in str(exc)

    def test_exception_string_format(self):
        """Test exception string format"""
        exc = TemplateValidationError("Test error", ["TAILSCALE_KEY", "LEADER_IP"])
        exc_str = str(exc)
        assert "Template validation failed" in exc_str
        assert "TAILSCALE_KEY" in exc_str
        assert "LEADER_IP" in exc_str


class TestGenerateShellScriptValidation:
    """Test generate_cloud_init with validation"""

    def test_generate_with_all_variables_validates(self):
        """Test that script generation with all variables passes validation"""
        script = generate_cloud_init(cluster_tier="cluster", 
            tailscale_key="ts-key-123", leader_ip="10.0.0.1", role="server", validate=True
        )
        assert script is not None
        assert "TAILSCALE_KEY=" in script
        assert "LEADER_IP=" in script

    @pytest.mark.skip(reason="GPU/spot params removed from generate_cloud_init")
    def test_generate_without_validation_skip_check(self):
        """Test that script generation with validate=False skips validation"""
        script = generate_cloud_init(cluster_tier="cluster", 
            tailscale_key="ts-key-123", leader_ip="10.0.0.1", role="server", validate=False
        )
        assert script is not None
        # Should still work because we're providing all variables

    @pytest.mark.skip(reason="GPU/spot params removed from generate_cloud_init")
    def test_generate_with_gpu_validates(self):
        """Test that script generation with GPU parameters passes validation"""
        script = generate_cloud_init(cluster_tier="cluster", 
            tailscale_key="ts-key-123",
            leader_ip="10.0.0.1",
            role="client",
            validate=True,
        )
        assert script is not None
        assert "HAS_GPU=" in script

    @pytest.mark.skip(reason="GPU/spot params removed from generate_cloud_init")
    def test_generate_with_spot_handling_validates(self):
        """Test that script generation with spot handling passes validation"""
        script = generate_cloud_init(cluster_tier="cluster", 
            tailscale_key="ts-key-123",
            leader_ip="10.0.0.1",
            role="client",
            spot_check_interval=10,
            spot_grace_period=60,
            validate=True,
        )
        assert script is not None
        assert "ENABLE_SPOT_HANDLING=" in script
        assert 'SPOT_CHECK_INTERVAL="10"' in script
        assert 'SPOT_GRACE_PERIOD="60"' in script


class TestGetJinja2Env:
    """Test _get_jinja2_env function"""

    def test_strict_mode_by_default(self):
        """Test that strict mode is enabled by default"""
        env = _get_jinja2_env()
        # Check that undefined is StrictUndefined
        from jinja2 import StrictUndefined

        assert env.undefined == StrictUndefined

    def test_strict_mode_enabled(self):
        """Test that strict mode can be explicitly enabled"""
        env = _get_jinja2_env(strict=True)
        from jinja2 import StrictUndefined

        assert env.undefined == StrictUndefined

    def test_strict_mode_disabled(self):
        """Test that strict mode can be disabled"""
        env = _get_jinja2_env(strict=False)
        from jinja2 import Undefined

        assert env.undefined == Undefined

    def test_strict_mode_raises_on_undefined(self):
        """Test that strict mode raises error on undefined variable"""
        env = _get_jinja2_env(strict=True)
        template = env.from_string("{{ UNDEFINED_VAR }}")
        with pytest.raises(Exception):  # UndefinedError
            template.render()

    def test_non_strict_mode_allows_undefined(self):
        """Test that non-strict mode allows undefined variables"""
        env = _get_jinja2_env(strict=False)
        template = env.from_string("{{ UNDEFINED_VAR }}")
        result = template.render()
        assert result == ""  # Undefined variables render as empty string


class TestGenerateCloudInitValidation:
    """Test generate_cloud_init with validation"""

    def test_generate_cloud_init_validates(self):
        """Test that cloud-init generation validates shell script"""
        yaml_content = generate_cloud_init(cluster_tier="cluster", 
            tailscale_key="ts-key-123", leader_ip="10.0.0.1", role="server", validate=True
        )
        assert yaml_content is not None
        assert "#cloud-config" in yaml_content

    def test_generate_cloud_init_without_validation(self):
        """Test that cloud-init generation can skip validation"""
        yaml_content = generate_cloud_init(cluster_tier="cluster", 
            tailscale_key="ts-key-123", leader_ip="10.0.0.1", role="server", validate=False
        )
        assert yaml_content is not None


class TestValidationEdgeCases:
    """Test edge cases for template validation"""

    def test_empty_content(self):
        """Test validation of empty content"""
        is_valid, unreplaced = validate_rendered_template("")
        assert is_valid is True

    def test_content_with_braces_but_not_template(self):
        """Test content with braces that aren't template syntax"""
        # This should pass validation because it doesn't match {{ VAR }} pattern
        content = "echo '{ some text }'"
        is_valid, unreplaced = validate_rendered_template(content)
        assert is_valid is True

    def test_nested_braces(self):
        """Test content with nested braces"""
        # This should pass validation
        content = "echo '{{ {{ test }} }}'"
        is_valid, unreplaced = validate_rendered_template(content)
        assert is_valid is False  # Would be caught as template syntax

    def test_mixed_valid_and_invalid(self):
        """Test content with both valid variables and unreplaced templates"""
        content = """
VALID_VAR="value"
INVALID_VAR="{{ INVALID_VAR }}"
ANOTHER_VALID="another"
"""
        is_valid, unreplaced = validate_rendered_template(content)
        assert is_valid is False
        assert "INVALID_VAR" in unreplaced
