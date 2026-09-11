import streamlit as st


PALETTES = {
    "dark": {
        "bg": "#0b111a",
        "surface": "#111a27",
        "surface_soft": "rgba(17, 26, 39, 0.60)",
        "surface_strong": "rgba(17, 26, 39, 0.88)",
        "card": "rgba(8, 13, 21, 0.48)",
        "card_hover": "rgba(17, 26, 39, 0.72)",
        "input": "#111a27",
        "field_text": "#f3f7fb",
        "field_muted": "#a9b7c9",
        "border": "rgba(148, 163, 184, 0.20)",
        "border_strong": "rgba(56, 189, 248, 0.42)",
        "text": "#f3f7fb",
        "muted": "#a9b7c9",
        "primary": "#38bdf8",
        "on_primary": "#ffffff",
        "option_hover": "rgba(56, 189, 248, 0.14)",
        "environment_text": "#bae6fd",
        "focus": "rgba(56, 189, 248, 0.30)",
        "glow": "rgba(14, 165, 233, 0.08)",
        "shadow": "0 18px 45px rgba(0, 0, 0, 0.18)",
        "color_scheme": "dark",
    },
    "light": {
        "bg": "#f3f6fa",
        "surface": "#ffffff",
        "surface_soft": "rgba(255, 255, 255, 0.78)",
        "surface_strong": "rgba(255, 255, 255, 0.92)",
        "card": "rgba(255, 255, 255, 0.84)",
        "card_hover": "#ffffff",
        "input": "#ffffff",
        "field_text": "#152238",
        "field_muted": "#64748b",
        "border": "rgba(71, 85, 105, 0.20)",
        "border_strong": "rgba(2, 132, 199, 0.48)",
        "text": "#152238",
        "muted": "#526174",
        "primary": "#0284c7",
        "on_primary": "#ffffff",
        "option_hover": "rgba(2, 132, 199, 0.12)",
        "environment_text": "#075985",
        "focus": "rgba(2, 132, 199, 0.24)",
        "glow": "rgba(14, 165, 233, 0.10)",
        "shadow": "0 18px 45px rgba(15, 23, 42, 0.12)",
        "color_scheme": "light",
    },
}


GLOBAL_STYLES = """
<style>
    :root {
        color-scheme: __COLOR_SCHEME__;
        --sar-bg: __BG__;
        --sar-surface: __SURFACE__;
        --sar-surface-soft: __SURFACE_SOFT__;
        --sar-surface-strong: __SURFACE_STRONG__;
        --sar-card: __CARD__;
        --sar-card-hover: __CARD_HOVER__;
        --sar-input: __INPUT__;
        --sar-field-text: __FIELD_TEXT__;
        --sar-field-muted: __FIELD_MUTED__;
        --sar-border: __BORDER__;
        --sar-border-strong: __BORDER_STRONG__;
        --sar-text: __TEXT__;
        --sar-muted: __MUTED__;
        --sar-primary: __PRIMARY__;
        --sar-on-primary: __ON_PRIMARY__;
        --sar-option-hover: __OPTION_HOVER__;
        --sar-environment-text: __ENVIRONMENT_TEXT__;
        --sar-focus: __FOCUS__;
        --sar-glow: __GLOW__;
        --sar-shadow: __SHADOW__;
        --background-color: __BG__;
        --secondary-background-color: __SURFACE__;
        --text-color: __TEXT__;
        --primary-color: __PRIMARY__;
        --border-color: __BORDER__;
    }

    .stApp {
        background:
            radial-gradient(circle at 8% 0%, var(--sar-glow), transparent 28rem),
            var(--sar-bg);
        color: var(--sar-text);
    }

    .stMainBlockContainer {
        position: relative;
        max-width: 1500px;
        padding-top: 1rem;
        padding-bottom: 1.5rem;
    }

    header[data-testid="stHeader"] {
        background: transparent;
        pointer-events: none;
    }

    [data-testid="stToolbar"],
    [data-testid="stStatusWidget"] {
        display: none;
    }

    .sar-app-header {
        min-height: 68px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        padding: 0.75rem 19rem 0.75rem 1rem;
        margin: 0 0 1.6rem;
        border: 1px solid var(--sar-border);
        border-radius: 16px;
        background: var(--sar-surface-strong);
        box-shadow: var(--sar-shadow);
        backdrop-filter: blur(14px);
    }

    .sar-brand {
        display: flex;
        align-items: center;
        gap: 0.8rem;
        min-width: 0;
    }

    .sar-brand-mark {
        width: 42px;
        height: 42px;
        flex: 0 0 42px;
        display: grid;
        place-items: center;
        border: 1px solid var(--sar-border-strong);
        border-radius: 12px;
        background: linear-gradient(145deg, var(--sar-option-hover), var(--sar-glow));
    }

    .sar-brand-mark img {
        width: 25px;
        height: 25px;
        display: block;
    }

    .sar-brand-name {
        color: var(--sar-text);
        font-size: 1.08rem;
        font-weight: 750;
        line-height: 1.15;
        letter-spacing: -0.01em;
    }

    .sar-brand-description {
        color: var(--sar-muted);
        font-size: 0.78rem;
        line-height: 1.25;
        margin-top: 0.15rem;
    }

    .sar-page-intro {
        margin-bottom: 1.15rem;
    }

    .sar-eyebrow {
        color: var(--sar-primary);
        font-size: 0.72rem;
        font-weight: 750;
        letter-spacing: 0.11em;
        text-transform: uppercase;
        margin-bottom: 0.35rem;
    }

    .sar-page-title {
        color: var(--sar-text);
        font-size: clamp(1.45rem, 2.2vw, 2rem);
        font-weight: 760;
        line-height: 1.18;
        letter-spacing: -0.025em;
        margin: 0;
    }

    .sar-page-description {
        color: var(--sar-muted);
        font-size: 0.95rem;
        margin: 0.45rem 0 0;
    }

    .sar-institution-list {
        color: var(--sar-muted);
        margin: 0.9rem 0 0.15rem;
        padding-left: 1.3rem;
    }

    .sar-institution-list li {
        line-height: 1.55;
        padding-left: 0.2rem;
        margin: 0.25rem 0;
    }

    .sar-institution-list li::marker {
        color: var(--sar-primary);
        font-size: 0.9em;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-color: var(--sar-border);
        border-radius: 14px;
        background: var(--sar-surface-soft);
    }

    div[class*="st-key-sar_module_card_"] {
        padding: 1.35rem 1.1rem;
        border-color: var(--sar-border) !important;
        border-radius: 16px !important;
        background: var(--sar-card) !important;
        transition: transform 160ms ease, border-color 160ms ease,
            box-shadow 160ms ease, background-color 160ms ease;
    }

    div[data-testid="stColumn"]:has(.sar-module-card-content) > div[data-testid="stVerticalBlock"],
    div[data-testid="stColumn"]:has(.sar-module-card-content) > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"],
    div[data-testid="stColumn"]:has(.sar-module-card-content) div[class*="st-key-sar_module_card_"] {
        height: 100%;
    }

    div[class*="st-key-sar_module_card_"]:hover {
        transform: translateY(-3px);
        border-color: var(--sar-border-strong) !important;
        background: var(--sar-card-hover) !important;
        box-shadow: var(--sar-shadow);
    }

    .sar-module-card-content {
        display: flex;
        flex-direction: column;
        align-items: center;
        color: var(--sar-text);
        text-align: center;
    }

    .sar-module-card-content h2 {
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--sar-text);
        font-size: 1.08rem;
        line-height: 1.25;
        margin: 0 0 0.75rem;
    }

    .sar-module-card-content p {
        color: var(--sar-muted);
        font-size: 0.86rem;
        line-height: 1.55;
        margin: 0;
    }

    .sar-module-icon {
        width: 62px;
        height: 62px;
        display: block;
        flex: 0 0 62px;
        object-fit: contain;
        margin: 0 auto 1rem;
    }

    .sar-diagnostic-state,
    .sar-diagnostic-table-wrap,
    .sar-diagnostic-empty {
        color: var(--sar-text);
        border: 1px solid var(--sar-border);
        border-radius: 12px;
        background: var(--sar-surface);
    }

    .sar-diagnostic-state {
        padding: 0.85rem 1rem;
        margin: 0.35rem 0 0.75rem;
    }

    .sar-diagnostic-state dl {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
        gap: 0.7rem 1rem;
        margin: 0;
    }

    .sar-diagnostic-state dt {
        color: var(--sar-muted);
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }

    .sar-diagnostic-state dd {
        color: var(--sar-text);
        font-size: 0.9rem;
        font-weight: 650;
        margin: 0.2rem 0 0;
        overflow-wrap: anywhere;
    }

    .sar-diagnostic-table-wrap {
        max-height: 26rem;
        overflow: auto;
        margin: 0.45rem 0 1.1rem;
    }

    .sar-diagnostic-table {
        width: 100%;
        border-collapse: collapse;
        color: var(--sar-text);
        font-size: 0.78rem;
    }

    .sar-diagnostic-table th {
        position: sticky;
        top: 0;
        z-index: 1;
        padding: 0.68rem 0.75rem;
        color: var(--sar-muted);
        text-align: left;
        font-size: 0.7rem;
        font-weight: 720;
        letter-spacing: 0.04em;
        background: var(--sar-surface);
        border-bottom: 1px solid var(--sar-border);
    }

    .sar-diagnostic-table td {
        padding: 0.62rem 0.75rem;
        color: var(--sar-text);
        border-bottom: 1px solid var(--sar-border);
        overflow-wrap: anywhere;
    }

    .sar-diagnostic-table tr:last-child td {
        border-bottom: 0;
    }

    .sar-diagnostic-empty {
        padding: 1rem;
        color: var(--sar-muted);
        margin: 0.45rem 0 1.1rem;
    }

    div[data-testid="stButton"] > button,
    div[data-testid="stDownloadButton"] > button,
    div[data-testid="stFormSubmitButton"] > button {
        min-height: 2.55rem;
        color: var(--sar-text) !important;
        border-color: var(--sar-border) !important;
        border-radius: 10px;
        background: var(--sar-surface) !important;
        font-weight: 680;
    }

    div[data-testid="stButton"] > button:hover,
    div[data-testid="stDownloadButton"] > button:hover,
    div[data-testid="stFormSubmitButton"] > button:hover {
        color: var(--sar-primary) !important;
        border-color: var(--sar-border-strong) !important;
    }

    div[data-testid="stButton"] > button[kind="primary"],
    div[data-testid="stDownloadButton"] > button[kind="primary"],
    div[data-testid="stFormSubmitButton"] > button[kind="primary"],
    button[data-testid="stBaseButton-primary"] {
        color: var(--sar-on-primary) !important;
        -webkit-text-fill-color: var(--sar-on-primary) !important;
        border-color: var(--sar-primary) !important;
        background: var(--sar-primary) !important;
    }

    button[data-testid="stBaseButton-primary"] *,
    div[data-testid="stButton"] > button[kind="primary"] *,
    div[data-testid="stDownloadButton"] > button[kind="primary"] *,
    div[data-testid="stFormSubmitButton"] > button[kind="primary"] * {
        color: var(--sar-on-primary) !important;
        -webkit-text-fill-color: var(--sar-on-primary) !important;
    }

    .stApp input,
    .stApp textarea,
    .stApp [data-baseweb="select"] {
        color: var(--sar-field-text) !important;
        -webkit-text-fill-color: var(--sar-field-text);
    }

    .stApp [data-testid="stWidgetLabel"] p,
    .stApp [data-testid="stRadio"] label p,
    .stApp [data-testid="stCheckbox"] label p,
    .stApp [data-testid="stToggle"] label p,
    .stApp [data-testid="stCaptionContainer"],
    .stApp [data-testid="stFileUploaderDropzoneInstructions"] {
        color: var(--sar-text) !important;
    }

    .stApp input::placeholder,
    .stApp textarea::placeholder {
        color: var(--sar-field-muted) !important;
        -webkit-text-fill-color: var(--sar-field-muted);
        opacity: 1;
    }

    .stApp [data-testid="stTextInputRootElement"],
    .stApp [data-testid="stTextAreaRootElement"],
    .stApp [data-testid="stNumberInput"] [data-baseweb="input"],
    .stApp [data-testid="stDateInput"] [data-baseweb="input"],
    .stApp [data-testid="stTextArea"] [data-baseweb="textarea"],
    .stApp [data-testid="stSelectbox"] [data-baseweb="select"] > div,
    .stApp [data-testid="stMultiSelect"] [data-baseweb="select"] > div {
        color: var(--sar-field-text) !important;
        background-color: var(--sar-input) !important;
        border-color: var(--sar-border) !important;
        border-radius: 10px !important;
    }

    .stApp div[data-baseweb="select"] span,
    .stApp div[data-baseweb="select"] input,
    .stApp div[data-baseweb="input"] input,
    .stApp div[data-baseweb="base-input"] input,
    .stApp div[data-baseweb="textarea"] textarea,
    .stApp [data-testid="stDateInput"] input,
    .stApp [data-testid="stNumberInput"] input {
        color: var(--sar-field-text) !important;
        -webkit-text-fill-color: var(--sar-field-text) !important;
        background-color: transparent !important;
    }

    /* The border belongs only to the BaseWeb root. Styling its inner wrappers
       produced the white notches previously visible around text areas. */
    .stApp [data-testid="stTextArea"] [data-baseweb="textarea"] {
        overflow: hidden;
        border: 1px solid var(--sar-border) !important;
        background: var(--sar-input) !important;
    }

    .stApp [data-testid="stTextAreaRootElement"] {
        overflow: hidden;
        border: 1px solid var(--sar-border) !important;
        border-radius: 10px !important;
        background: var(--sar-input) !important;
    }

    .stApp [data-testid="stTextArea"] [data-baseweb="textarea"] > div,
    .stApp [data-testid="stTextArea"] textarea {
        border: 0 !important;
        outline: 0 !important;
        background: transparent !important;
        box-shadow: none !important;
    }

    /* BaseWeb selection indicators do not inherit Streamlit's manual theme. */
    .stApp input[type="checkbox"],
    .stApp input[type="radio"] {
        accent-color: var(--sar-primary) !important;
    }

    .stApp [data-testid="stCheckbox"] label > div:first-of-type {
        color: var(--sar-field-text) !important;
        border: 1px solid var(--sar-border-strong) !important;
        border-color: var(--sar-border-strong) !important;
        background: var(--sar-input) !important;
    }

    .stApp [data-testid="stCheckbox"] label:has(input:checked) > div:first-of-type {
        color: var(--sar-on-primary) !important;
        border-color: var(--sar-primary) !important;
        background: var(--sar-primary) !important;
    }

    /* Horizontal radios use an option wrapper around the indicator. Keep the
       wrapper invisible so only the circular control is rendered. */
    .stApp [data-testid="stRadioOption"] > div {
        border: 0 !important;
        background: transparent !important;
    }

    .stApp [data-testid="stRadioOption"] > div > div > div:first-child {
        border: 1px solid var(--sar-border-strong) !important;
        border-radius: 50% !important;
        background: var(--sar-input) !important;
    }

    .stApp [data-testid="stRadioOption"] > div > div > div:first-child > div {
        background: transparent !important;
    }

    .stApp [data-testid="stRadioOption"][data-selected="true"] > div > div > div:first-child {
        border-color: var(--sar-primary) !important;
        background: var(--sar-primary) !important;
    }

    .stApp [data-testid="stRadioOption"][data-selected="true"] > div > div > div:first-child > div {
        background: var(--sar-on-primary) !important;
    }

    .stApp [data-testid="stSelectbox"] [data-baseweb="select"] *,
    .stApp [data-testid="stMultiSelect"] [data-baseweb="select"] *,
    .stApp [data-testid="stTextInput"] [data-baseweb="input"] *,
    .stApp [data-testid="stDateInput"] [data-baseweb="input"] *,
    .stApp [data-testid="stNumberInput"] [data-baseweb="input"] * {
        color: var(--sar-field-text) !important;
        -webkit-text-fill-color: var(--sar-field-text) !important;
    }

    .stApp div[data-baseweb="select"] svg,
    .stApp div[data-baseweb="input"] svg,
    .stApp div[data-baseweb="base-input"] svg {
        color: var(--sar-muted) !important;
        fill: var(--sar-muted) !important;
    }

    .stApp [data-testid="stExpander"] details,
    .stApp [data-testid="stExpander"] summary {
        color: var(--sar-text) !important;
        border-color: var(--sar-border) !important;
        background-color: var(--sar-surface-soft) !important;
    }

    .stApp [data-testid="stExpander"] summary p,
    .stApp [data-testid="stExpander"] summary svg,
    .stApp [data-testid="stTabs"] button,
    .stApp [data-testid="stTabs"] button p {
        color: var(--sar-text) !important;
        -webkit-text-fill-color: var(--sar-text) !important;
    }

    .stApp [data-testid="stTabs"] [aria-selected="true"],
    .stApp [data-testid="stTabs"] [aria-selected="true"] p {
        color: var(--sar-primary) !important;
        -webkit-text-fill-color: var(--sar-primary) !important;
    }

    .stApp [data-testid="stDataFrame"],
    .stApp [data-testid="stDataEditor"] {
        --gdg-bg-cell: var(--sar-input);
        --gdg-bg-header: var(--sar-surface);
        --gdg-text-dark: var(--sar-text);
        --gdg-text-medium: var(--sar-muted);
        color: var(--sar-text) !important;
        border-color: var(--sar-border) !important;
    }

    div[class*="st-key-sar_theme_selector"] {
        width: 100%;
        padding: 0.2rem;
        border: 1px solid var(--sar-border-strong);
        border-radius: 12px;
        background: var(--sar-surface);
        box-shadow: var(--sar-shadow);
    }

    div[class*="st-key-sar_profile_menu"] {
        position: absolute;
        top: 1.55rem;
        right: 7rem;
        z-index: 11;
        width: max-content;
        max-width: 11rem;
    }

    div[class*="st-key-sar_profile_menu"] button[data-testid="stPopoverButton"] {
        min-height: 2.55rem;
        max-width: 11rem;
        overflow: hidden;
        color: var(--sar-text) !important;
        border-color: var(--sar-border-strong) !important;
        border-radius: 12px !important;
        background: var(--sar-surface) !important;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    div[class*="st-key-sar_module_card_"] {
        position: relative;
        cursor: pointer;
    }

    div[class*="st-key-sar_module_card_"] div[class*="st-key-open_module_"] {
        position: absolute;
        inset: 0;
        z-index: 3;
        margin: 0;
    }

    div[class*="st-key-sar_module_card_"] div[data-testid="stButton"],
    div[class*="st-key-sar_module_card_"] div[data-testid="stButton"] *,
    div[class*="st-key-sar_module_card_"] div[data-testid="stButton"] button {
        width: 100%;
        height: 100%;
        min-height: 100%;
        padding: 0;
        cursor: pointer;
    }

    div[class*="st-key-sar_module_card_"] div[data-testid="stButton"] button {
        color: transparent !important;
        border: 0 !important;
        background: transparent !important;
        box-shadow: none !important;
        opacity: 0 !important;
    }

    div[class*="st-key-sar_module_card_"]:has(button:focus-visible) {
        outline: 3px solid var(--sar-focus);
        outline-offset: 3px;
    }

    div[class*="st-key-sar_theme_selector"] [data-testid="stSegmentedControl"] {
        padding: 0.18rem;
        border: 0;
        border-radius: 9px;
        background: transparent;
        box-shadow: none;
    }

    div[class*="st-key-sar_theme_selector"] button {
        width: 2.15rem;
        min-height: 2.15rem;
        padding: 0.25rem;
        color: var(--sar-muted) !important;
        border: 0 !important;
        background: transparent !important;
        font-size: 0.76rem;
        font-weight: 680;
    }

    div[class*="st-key-sar_theme_selector"] button[aria-checked="true"] {
        color: var(--sar-on-primary) !important;
        background: var(--sar-primary) !important;
    }

    div[class*="st-key-sar_theme_selector"] button span,
    div[class*="st-key-sar_theme_selector"] button p {
        color: var(--sar-muted) !important;
        -webkit-text-fill-color: var(--sar-muted) !important;
    }

    div[class*="st-key-sar_theme_selector"] button[aria-checked="true"] span,
    div[class*="st-key-sar_theme_selector"] button[aria-checked="true"] p {
        color: var(--sar-on-primary) !important;
        -webkit-text-fill-color: var(--sar-on-primary) !important;
    }

    div[data-baseweb="popover"] [role="listbox"],
    div[data-baseweb="popover"] [role="option"] {
        color: var(--sar-text) !important;
        background-color: var(--sar-surface) !important;
    }

    div[data-baseweb="popover"] [role="option"]:hover,
    div[data-baseweb="popover"] [aria-selected="true"] {
        background-color: var(--sar-surface-soft) !important;
    }

    div[data-testid="stTextInputRootElement"],
    div[data-baseweb="select"] > div,
    div[data-testid="stDateInput"] div[data-baseweb="input"] {
        border-radius: 10px;
    }

    div[data-testid="stTabs"] [data-baseweb="tab-list"] {
        gap: 0.35rem;
    }

    div[data-testid="stTabs"] button[role="tab"] {
        border-radius: 9px 9px 0 0;
        padding-left: 1rem;
        padding-right: 1rem;
    }

    @media (max-width: 820px) {
        .stMainBlockContainer {
            padding-left: 1rem;
            padding-right: 1rem;
        }

        div[data-testid="stHorizontalBlock"] {
            flex-wrap: wrap;
        }

        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
            min-width: min(100%, 18rem) !important;
            flex: 1 1 18rem !important;
            width: auto !important;
        }

        div[class*="st-key-sar_profile_menu"] {
            right: 3rem;
        }
    }

    @media (max-width: 560px) {
        .sar-app-header {
            min-height: 60px;
            padding-right: 12rem;
            margin-bottom: 1.2rem;
        }

        .sar-brand-description {
            display: none;
        }

        div[class*="st-key-sar_profile_menu"] {
            top: 1.42rem;
            right: 2rem;
            max-width: 6rem;
        }

        div[class*="st-key-sar_profile_menu"] button[data-testid="stPopoverButton"] {
            max-width: 6rem;
        }

    }

    @media (prefers-reduced-motion: reduce) {
        div[class*="st-key-sar_module_card_"] {
            transition: none;
        }
    }
</style>
"""


LIGHT_COMPONENT_STYLES = """
<style>
    div[data-baseweb="popover"],
    div[data-baseweb="popover"] > div,
    div[data-baseweb="menu"],
    div[data-baseweb="calendar"],
    div[data-baseweb="calendar"] > div,
    div[data-baseweb="datepicker"],
    [role="listbox"],
    [role="dialog"] {
        color: var(--sar-field-text) !important;
        background-color: var(--sar-input) !important;
        border-color: var(--sar-border) !important;
    }

    div[data-baseweb="popover"] [role="option"],
    div[data-baseweb="popover"] [role="option"] *,
    div[data-baseweb="menu"] [role="option"],
    div[data-baseweb="menu"] [role="option"] *,
    [role="listbox"] [role="option"],
    [role="listbox"] [role="option"] *,
    div[data-baseweb="calendar"] button,
    div[data-baseweb="calendar"] [role="button"],
    div[data-baseweb="calendar"] select {
        color: var(--sar-field-text) !important;
        -webkit-text-fill-color: var(--sar-field-text) !important;
        background-color: transparent !important;
    }

    div[data-baseweb="popover"] [role="option"]:hover,
    div[data-baseweb="popover"] [role="option"][aria-selected="true"],
    div[data-baseweb="menu"] [role="option"]:hover,
    div[data-baseweb="menu"] [role="option"][aria-selected="true"] {
        background-color: var(--sar-option-hover) !important;
    }

    div[data-baseweb="calendar"] button[aria-selected="true"],
    div[data-baseweb="calendar"] [role="button"][aria-selected="true"] {
        color: var(--sar-on-primary) !important;
        -webkit-text-fill-color: var(--sar-on-primary) !important;
        background-color: var(--sar-primary) !important;
    }

    div[data-baseweb="calendar"] button:disabled,
    div[data-baseweb="calendar"] [aria-disabled="true"] {
        color: var(--sar-field-muted) !important;
        -webkit-text-fill-color: var(--sar-field-muted) !important;
    }

    [aria-label*="Choose date"] {
        color: var(--sar-field-text) !important;
        background: var(--sar-input) !important;
        border-color: var(--sar-border) !important;
    }

    div:has(> [aria-label*="Choose date"]) {
        background: var(--sar-input) !important;
        border-color: var(--sar-border) !important;
        box-shadow: var(--sar-shadow) !important;
    }

    [aria-label*="Choose date"] * {
        color: var(--sar-field-text) !important;
        -webkit-text-fill-color: var(--sar-field-text) !important;
    }

    [aria-label*="Choose date"] [aria-disabled="true"],
    [aria-label*="Choose date"] button:disabled {
        color: var(--sar-field-muted) !important;
        -webkit-text-fill-color: var(--sar-field-muted) !important;
    }

    [aria-label*="Choose date"] [aria-selected="true"],
    [aria-label*="Choose date"] [aria-selected="true"] * {
        color: var(--sar-on-primary) !important;
        -webkit-text-fill-color: var(--sar-on-primary) !important;
        background-color: var(--sar-primary) !important;
    }

    .stApp [data-testid="stTextInputRootElement"],
    .stApp [data-baseweb="input"],
    .stApp [data-baseweb="base-input"],
    .stApp [data-baseweb="select"],
    .stApp [data-baseweb="select"] > div,
    .stApp [data-testid="stNumberInput"] [data-baseweb="input"],
    .stApp [data-testid="stDateInput"] [data-baseweb="input"],
    .stApp [data-testid="stTextArea"] [data-baseweb="textarea"],
    .stApp [data-testid="stSelectbox"] [data-baseweb="select"],
    .stApp [data-testid="stSelectbox"] [data-baseweb="select"] > div,
    .stApp [data-testid="stMultiSelect"] [data-baseweb="select"],
    .stApp [data-testid="stMultiSelect"] [data-baseweb="select"] > div {
        color: var(--sar-field-text) !important;
        background-color: var(--sar-input) !important;
        border-color: var(--sar-border) !important;
    }

    .stApp [data-baseweb="input"] input,
    .stApp [data-baseweb="base-input"] input,
    .stApp [data-baseweb="select"] > div,
    .stApp [data-baseweb="select"] > div > div {
        background: var(--sar-input) !important;
    }

    .stApp [role="combobox"],
    .stApp [role="combobox"] > *,
    .stApp [role="spinbutton"],
    .stApp [role="spinbutton"] > *,
    .stApp div:has(> [role="combobox"]),
    .stApp div:has(> [role="spinbutton"]) {
        color: var(--sar-field-text) !important;
        -webkit-text-fill-color: var(--sar-field-text) !important;
        background: var(--sar-input) !important;
    }

    .stApp input[type="number"],
    .stApp div:has(> input[type="number"]),
    .stApp div:has(> button[aria-label="Decrement"]),
    .stApp div:has(> button[aria-label="Increment"]),
    .stApp button[aria-label="Decrement"],
    .stApp button[aria-label="Increment"],
    .stApp button[aria-label="Open"],
    .stApp div:has(> button[aria-label="Open"]),
    .stApp div:has(> [role="combobox"]) > button,
    .stApp [role="combobox"] ~ button {
        color: var(--sar-field-text) !important;
        -webkit-text-fill-color: var(--sar-field-text) !important;
        background: var(--sar-input) !important;
    }

    .stApp div:has(> [role="combobox"]) > button svg,
    .stApp [role="combobox"] ~ button svg,
    .stApp button[aria-label="Decrement"] svg,
    .stApp button[aria-label="Increment"] svg {
        color: var(--sar-muted) !important;
        fill: var(--sar-muted) !important;
    }

    .stApp button[aria-label="Open"] svg {
        color: var(--sar-muted) !important;
        fill: var(--sar-muted) !important;
    }

    .stApp [data-testid="stTextInputRootElement"] input,
    .stApp [data-testid="stNumberInput"] input,
    .stApp [data-testid="stDateInput"] input,
    .stApp [data-testid="stTextArea"] textarea,
    .stApp [data-testid="stSelectbox"] [data-baseweb="select"] *,
    .stApp [data-testid="stMultiSelect"] [data-baseweb="select"] * {
        color: var(--sar-field-text) !important;
        -webkit-text-fill-color: var(--sar-field-text) !important;
    }

    .stApp [data-testid="stTextInputRootElement"] input::placeholder,
    .stApp [data-testid="stNumberInput"] input::placeholder,
    .stApp [data-testid="stDateInput"] input::placeholder,
    .stApp [data-testid="stTextArea"] textarea::placeholder,
    .stApp [data-testid="stMultiSelect"] input::placeholder {
        color: var(--sar-field-muted) !important;
        -webkit-text-fill-color: var(--sar-field-muted) !important;
        opacity: 1 !important;
    }

    .stApp [data-testid="stTextArea"] [data-baseweb="textarea"],
    .stApp [data-testid="stTextArea"] textarea {
        color: var(--sar-field-text) !important;
        -webkit-text-fill-color: var(--sar-field-text) !important;
    }

    .stApp [data-testid="stTextArea"] [data-baseweb="textarea"] {
        background: var(--sar-input) !important;
        border-color: var(--sar-border) !important;
        color-scheme: light !important;
    }

    .stApp [data-testid="stTextArea"] textarea {
        background: transparent !important;
        border: 0 !important;
    }

    .stApp div[class*="st-key-sar_profile_menu"] button[data-testid="stPopoverButton"],
    .stApp div[class*="st-key-sar_profile_menu"] button[data-testid="stPopoverButton"] p,
    .stApp div[class*="st-key-sar_profile_menu"] button[data-testid="stPopoverButton"] span,
    .stApp div[class*="st-key-sar_profile_menu"] button[data-testid="stPopoverButton"] svg {
        color: var(--sar-field-text) !important;
        -webkit-text-fill-color: var(--sar-field-text) !important;
        fill: var(--sar-field-text) !important;
        background: var(--sar-surface) !important;
    }

    .stApp [data-testid="stSelectbox"] svg,
    .stApp [data-testid="stMultiSelect"] svg,
    .stApp [data-testid="stDateInput"] svg,
    .stApp [data-testid="stNumberInput"] svg {
        color: var(--sar-muted) !important;
        fill: var(--sar-muted) !important;
    }

    .stApp [data-testid="stTabs"] [role="tab"],
    .stApp [data-testid="stTabs"] [role="tab"] * {
        color: var(--sar-muted) !important;
        -webkit-text-fill-color: var(--sar-muted) !important;
    }

    .stApp [data-testid="stTabs"] [role="tab"][aria-selected="true"],
    .stApp [data-testid="stTabs"] [role="tab"][aria-selected="true"] * {
        color: var(--sar-primary) !important;
        -webkit-text-fill-color: var(--sar-primary) !important;
    }

    .stApp [data-testid="stAlert"],
    .stApp [data-testid="stAlert"] p,
    .stApp [data-testid="stAlert"] div {
        color: var(--sar-field-text) !important;
        -webkit-text-fill-color: var(--sar-field-text) !important;
    }

    .stApp button[data-testid="stBaseButton-primary"],
    .stApp button[data-testid="stBaseButton-primary"] p,
    .stApp button[data-testid="stBaseButton-primary"] span,
    .stApp button[data-testid="stBaseButton-primary"] [data-testid="stIconMaterial"] {
        color: var(--sar-on-primary) !important;
        -webkit-text-fill-color: var(--sar-on-primary) !important;
    }
</style>
"""


APP_HEADER = """
<div class="sar-app-header" role="banner">
    <div class="sar-brand">
        <div class="sar-brand-mark" aria-hidden="true">
            <img alt="" src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZD0iTTQgMTlWOW01IDEwVjVtNSAxNHYtN201IDdWMyIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMzhiZGY4IiBzdHJva2Utd2lkdGg9IjEuOSIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIi8+PC9zdmc+">
        </div>
        <div>
            <div class="sar-brand-name">SAR</div>
            <div class="sar-brand-description">Sistema de Automatização de Relatórios · PoP-CE / RNP</div>
        </div>
    </div>
</div>
"""


def _styles_for(theme: str) -> str:
    palette = PALETTES[theme]
    replacements = {
        "__COLOR_SCHEME__": palette["color_scheme"],
        "__BG__": palette["bg"],
        "__SURFACE__": palette["surface"],
        "__SURFACE_SOFT__": palette["surface_soft"],
        "__SURFACE_STRONG__": palette["surface_strong"],
        "__CARD__": palette["card"],
        "__CARD_HOVER__": palette["card_hover"],
        "__INPUT__": palette["input"],
        "__FIELD_TEXT__": palette["field_text"],
        "__FIELD_MUTED__": palette["field_muted"],
        "__BORDER__": palette["border"],
        "__BORDER_STRONG__": palette["border_strong"],
        "__TEXT__": palette["text"],
        "__MUTED__": palette["muted"],
        "__PRIMARY__": palette["primary"],
        "__ON_PRIMARY__": palette["on_primary"],
        "__OPTION_HOVER__": palette["option_hover"],
        "__ENVIRONMENT_TEXT__": palette["environment_text"],
        "__FOCUS__": palette["focus"],
        "__GLOW__": palette["glow"],
        "__SHADOW__": palette["shadow"],
    }
    styles = GLOBAL_STYLES
    for token, value in replacements.items():
        styles = styles.replace(token, value)
    if theme == "light":
        styles += LIGHT_COMPONENT_STYLES
    return styles


def _persist_theme_selection():
    selected = st.session_state.get("sar_theme_selector")
    if selected in PALETTES:
        st.session_state["sar_color_theme"] = selected


def render_theme_selector():
    current = st.session_state.get("sar_color_theme", "dark")
    if st.session_state.get("sar_theme_selector") not in PALETTES:
        st.session_state["sar_theme_selector"] = current
    st.caption("Tema da interface")
    st.segmented_control(
        "Tema da interface",
        options=("dark", "light"),
        format_func=lambda option: (
            ":material/dark_mode:" if option == "dark" else ":material/light_mode:"
        ),
        key="sar_theme_selector",
        label_visibility="collapsed",
        width="stretch",
        on_change=_persist_theme_selection,
        help="Alternar entre os temas escuro e claro",
    )


def apply_theme():
    if "sar_color_theme" not in st.session_state:
        st.session_state["sar_color_theme"] = "dark"

    theme = st.session_state["sar_color_theme"]
    if theme not in PALETTES:
        theme = "dark"
        st.session_state["sar_color_theme"] = theme

    st.html(_styles_for(theme))
    st.html(APP_HEADER)
