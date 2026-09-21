from types import SimpleNamespace
from unittest.mock import Mock

import sar.ui.theme as theme
from sar.ui.theme import GLOBAL_STYLES, LIGHT_COMPONENT_STYLES, _styles_for
from sar.ui.views.home import ADMIN_MODULE, MODULES


def test_light_theme_targets_current_streamlit_widget_roots():
    styles = _styles_for("light")

    assert '[data-testid="stTextAreaRootElement"]' in styles
    assert '[data-testid="stCheckbox"] label > div:first-of-type' in styles
    assert '[data-testid="stRadioOption"] > div' in styles
    assert 'background: transparent !important' in styles
    assert "background: var(--sar-input) !important" in styles
    assert "border: 1px solid var(--sar-border) !important" in styles


def test_light_component_overrides_use_theme_variables_for_colors():
    lowered = LIGHT_COMPONENT_STYLES.lower()

    assert "#" not in lowered
    assert "rgb(" not in lowered
    assert " black" not in lowered
    assert " white" not in lowered


def test_module_cards_do_not_have_legacy_fixed_heights():
    assert "min-height: 360px" not in GLOBAL_STYLES
    assert "min-height: 255px" not in GLOBAL_STYLES
    assert ':has(.sar-module-card-content)' in GLOBAL_STYLES


def test_theme_widget_styles_follow_the_current_widget_key():
    assert "st-key-sar_theme_selector" in GLOBAL_STYLES
    assert "st-key-sar_color_theme" not in GLOBAL_STYLES


def test_user_module_has_a_distinct_people_icon():
    assert ADMIN_MODULE[2] == "users.svg"
    assert ADMIN_MODULE[2] not in {module[2] for module in MODULES}


def test_theme_restores_browser_preference_after_new_session(monkeypatch):
    browser = SimpleNamespace(
        session_state={}, context=SimpleNamespace(cookies={"sar_color_theme": "light"}), html=Mock()
    )
    monkeypatch.setattr(theme, "st", browser)

    theme.apply_theme()

    assert browser.session_state["sar_color_theme"] == "light"
    assert browser.html.call_count == 2
    assert "color-scheme: light" in browser.html.call_args_list[0].args[0]
    header = browser.html.call_args_list[1].args[0]
    assert 'class="sar-app-header"' in header
    assert "sar_color_theme=light" in header


def test_theme_ignores_invalid_browser_preference(monkeypatch):
    browser = SimpleNamespace(
        session_state={}, context=SimpleNamespace(cookies={"sar_color_theme": "invalid"}), html=Mock()
    )
    monkeypatch.setattr(theme, "st", browser)

    theme.apply_theme()

    assert browser.session_state["sar_color_theme"] == "dark"
