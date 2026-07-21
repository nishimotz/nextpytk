"""Tests for nextpytk.types constants and helpers."""

import sys
from unittest import mock

import pytest

from nextpytk.types import (
    EventSeq,
    _primary_button_number,
    primary_button_release,
    primary_click,
    primary_double_click,
)


class TestEventSeqMouseConstants:
    """Mouse event sequences follow tkinter names."""

    def test_double_button_numbers(self):
        assert EventSeq.DOUBLE_BUTTON_1 == "<Double-Button-1>"
        assert EventSeq.DOUBLE_BUTTON_2 == "<Double-Button-2>"
        assert EventSeq.DOUBLE_BUTTON_3 == "<Double-Button-3>"

    def test_double_click_alias_points_to_double_button_1(self):
        assert EventSeq.DOUBLE_CLICK == EventSeq.DOUBLE_BUTTON_1


class TestPrimaryButtonDetection:
    """Best-effort OS primary-button detection."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        """Clear the per-process cache around every test."""
        _primary_button_number.cache_clear()
        yield
        _primary_button_number.cache_clear()

    def test_defaults_to_1_when_detection_fails(self):
        with mock.patch.object(sys, "platform", "unknown"):
            assert _primary_button_number() == 1

    def test_windows_swapped_returns_3(self):
        fake_user32 = mock.MagicMock()
        fake_user32.GetSystemMetrics = mock.MagicMock(return_value=1)
        ctypes_module = mock.MagicMock()
        ctypes_module.windll = mock.MagicMock()
        ctypes_module.windll.user32 = fake_user32

        with mock.patch.object(sys, "platform", "win32"):
            with mock.patch.dict("sys.modules", {"ctypes": ctypes_module}):
                assert _primary_button_number() == 3

    def test_windows_not_swapped_returns_1(self):
        fake_user32 = mock.MagicMock()
        fake_user32.GetSystemMetrics = mock.MagicMock(return_value=0)
        ctypes_module = mock.MagicMock()
        ctypes_module.windll = mock.MagicMock()
        ctypes_module.windll.user32 = fake_user32

        with mock.patch.object(sys, "platform", "win32"):
            with mock.patch.dict("sys.modules", {"ctypes": ctypes_module}):
                assert _primary_button_number() == 1

    def test_macos_swapped_returns_3(self):
        fake_defaults = mock.MagicMock()
        fake_defaults.boolForKey_ = mock.MagicMock(return_value=True)
        foundation_module = mock.MagicMock()
        foundation_module.NSUserDefaults = mock.MagicMock()
        foundation_module.NSUserDefaults.standardUserDefaults = mock.MagicMock(return_value=fake_defaults)

        with mock.patch.object(sys, "platform", "darwin"):
            with mock.patch.dict("sys.modules", {"Foundation": foundation_module}):
                assert _primary_button_number() == 3

    def test_macos_not_swapped_returns_1(self):
        fake_defaults = mock.MagicMock()
        fake_defaults.boolForKey_ = mock.MagicMock(return_value=False)
        foundation_module = mock.MagicMock()
        foundation_module.NSUserDefaults = mock.MagicMock()
        foundation_module.NSUserDefaults.standardUserDefaults = mock.MagicMock(return_value=fake_defaults)

        with mock.patch.object(sys, "platform", "darwin"):
            with mock.patch.dict("sys.modules", {"Foundation": foundation_module}):
                assert _primary_button_number() == 1

    def test_linux_left_handed_true_returns_3(self):
        fake_result = mock.MagicMock()
        fake_result.stdout = "true\n"
        fake_result.strip = mock.MagicMock(return_value="true")

        with mock.patch.object(sys, "platform", "linux"):
            with mock.patch("subprocess.run", return_value=fake_result) as mock_run:
                assert _primary_button_number() == 3
                mock_run.assert_called_once_with(
                    ["gsettings", "get", "org.gnome.desktop.peripherals.mouse", "left-handed"],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )

    def test_linux_left_handed_false_returns_1(self):
        fake_result = mock.MagicMock()
        fake_result.stdout = "false\n"

        with mock.patch.object(sys, "platform", "linux"):
            with mock.patch("subprocess.run", return_value=fake_result):
                assert _primary_button_number() == 1


class TestPrimaryEventSequences:
    """primary_* helpers format event sequences based on primary button."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        _primary_button_number.cache_clear()
        yield
        _primary_button_number.cache_clear()

    def test_primary_click_defaults_to_button_1(self):
        assert primary_click() == "<Button-1>"

    def test_primary_double_click_defaults_to_double_button_1(self):
        assert primary_double_click() == "<Double-Button-1>"

    def test_primary_button_release_defaults_to_button_release_1(self):
        assert primary_button_release() == "<ButtonRelease-1>"

    def test_primary_click_uses_cached_button_3(self):
        with mock.patch.object(sys, "platform", "unknown"):
            # Stub _primary_button_number to return 3
            with mock.patch(
                "nextpytk.types._primary_button_number",
                return_value=3,
            ):
                assert primary_click() == "<Button-3>"
                assert primary_double_click() == "<Double-Button-3>"
                assert primary_button_release() == "<ButtonRelease-3>"


class TestEventSeqPrimaryDescriptors:
    """EventSeq.PRIMARY_* are lazy descriptors that re-evaluate on access."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        _primary_button_number.cache_clear()
        yield
        _primary_button_number.cache_clear()

    def test_primary_click_descriptor_defaults_to_button_1(self):
        assert EventSeq.PRIMARY_CLICK == "<Button-1>"

    def test_primary_double_click_descriptor_defaults_to_double_button_1(self):
        assert EventSeq.PRIMARY_DOUBLE_CLICK == "<Double-Button-1>"

    def test_primary_button_release_descriptor_defaults_to_button_release_1(self):
        assert EventSeq.PRIMARY_BUTTON_RELEASE == "<ButtonRelease-1>"

    def test_descriptors_reevaluate_when_button_swapped(self):
        with mock.patch.object(sys, "platform", "unknown"):
            with mock.patch(
                "nextpytk.types._primary_button_number",
                return_value=3,
            ):
                assert EventSeq.PRIMARY_CLICK == "<Button-3>"
                assert EventSeq.PRIMARY_DOUBLE_CLICK == "<Double-Button-3>"
                assert EventSeq.PRIMARY_BUTTON_RELEASE == "<ButtonRelease-3>"
