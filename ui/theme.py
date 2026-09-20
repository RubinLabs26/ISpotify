"""iSpotify's visual system.

A quiet, near-monochrome palette in the spirit of a hand-tuned Wayland
compositor theme: one background, a handful of tonal surfaces, soft
low-alpha borders, and a single warm-white accent used sparingly. Colour
is not used to carry meaning on its own -- weight, spacing and opacity do
most of the work, so the accent stays rare and therefore legible.
"""

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette


COLORS = {
    "background": "#0c0c0d",
    "surface": "#131314",
    "surface_raised": "#19191b",
    "surface_hover": "#212123",
    "surface_active": "#28282a",
    "border": "rgba(255, 255, 255, 0.06)",
    "border_bright": "rgba(255, 255, 255, 0.14)",
    "text": "#e9e9ea",
    "text_secondary": "#9c9c9f",
    "text_muted": "#7d7d81",  # 4.8:1 on the background (was 3.5:1)
    "accent": "#f2f1ec",
    "accent_press": "#cfcec7",
    "accent_text": "#101010",
    "accent_wash": "rgba(242, 241, 236, 0.10)",
    "accent_soft": "rgba(242, 241, 236, 0.22)",
    "scroll": "rgba(255, 255, 255, 0.18)",
    "scroll_hover": "rgba(255, 255, 255, 0.30)",
    "scroll_press": "rgba(255, 255, 255, 0.42)",
    "danger": "#d99a95",
    "danger_wash": "rgba(217, 154, 149, 0.12)",
    "success": "#a7c9a8",
    "warning": "#d3bd8a",
    "info": "#9fb2c9",
}


def install_theme(app) -> None:
    available_fonts = set(QFontDatabase.families())
    font_family = next(
        (
            family for family in (
                "Inter", "Manrope", "Avenir Next",
                "Plus Jakarta Sans", "Segoe UI", "Noto Sans", "DejaVu Sans",
            )
            if family in available_fonts
        ),
        "DejaVu Sans",
    )
    check_icon = (
        Path(__file__).resolve().parents[1] / "assets" / "icons" / "SP_Check.svg"
    ).as_posix()
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(COLORS["background"]))
    palette.setColor(QPalette.WindowText, QColor(COLORS["text"]))
    palette.setColor(QPalette.Base, QColor(COLORS["surface"]))
    palette.setColor(QPalette.AlternateBase, QColor(COLORS["surface_raised"]))
    palette.setColor(QPalette.Text, QColor(COLORS["text"]))
    palette.setColor(QPalette.Button, QColor(COLORS["surface_raised"]))
    palette.setColor(QPalette.ButtonText, QColor(COLORS["text"]))
    palette.setColor(QPalette.Highlight, QColor(COLORS["accent"]))
    palette.setColor(QPalette.HighlightedText, QColor(COLORS["accent_text"]))
    app.setPalette(palette)
    app.setFont(QFont(font_family, 10))
    app.setStyleSheet(
        f"""
        * {{
            outline: none;
        }}
        QWidget {{
            color: {COLORS["text"]};
            font-family: "{font_family}";
            font-size: 10pt;
            selection-background-color: {COLORS["accent_soft"]};
            selection-color: {COLORS["text"]};
        }}
        QMainWindow, QWidget#appRoot, QScrollArea,
        QScrollArea > QWidget > QWidget {{
            background: {COLORS["background"]};
            border: none;
        }}
        QToolTip {{
            background: {COLORS["surface_hover"]};
            color: {COLORS["text"]};
            border: 1px solid {COLORS["border_bright"]};
            border-radius: 6px;
            padding: 5px 8px;
            font-size: 8.5pt;
        }}

        /* ---------- typography ---------- */
        QLabel#brand {{
            color: {COLORS["text"]};
            font-size: 14.5pt;
            font-weight: 600;
            letter-spacing: 0.2px;
        }}
        QLabel#brandMark {{
            color: {COLORS["text_muted"]};
            font-size: 8pt;
            font-weight: 500;
            letter-spacing: 0.3px;
        }}
        QLabel#eyebrow {{
            color: {COLORS["text_muted"]};
            font-size: 8pt;
            font-weight: 500;
            letter-spacing: 0.6px;
        }}
        QLabel#pageTitle {{
            color: {COLORS["text"]};
            font-size: 17pt;
            font-weight: 600;
            letter-spacing: -0.2px;
        }}
        QLabel#pageSubtitle {{
            color: {COLORS["text_muted"]};
            font-size: 9.5pt;
        }}
        QLabel#muted {{
            color: {COLORS["text_muted"]};
        }}
        QLabel#secondary {{
            color: {COLORS["text_secondary"]};
            font-size: 9pt;
        }}
        QLabel#sectionTitle {{
            color: {COLORS["text"]};
            font-size: 10.5pt;
            font-weight: 600;
        }}
        QLabel#cardTitle, QLabel#resultTitle {{
            color: {COLORS["text"]};
            font-size: 10pt;
            font-weight: 600;
        }}
        QLabel#playerTitle {{
            color: {COLORS["text"]};
            font-size: 9.5pt;
            font-weight: 600;
        }}
        QLabel#heroArtwork {{
            border-radius: 16px;
        }}
        QLabel#dot {{
            color: {COLORS["text_muted"]};
            font-size: 9pt;
        }}
        QLabel#dot[state="on"] {{
            color: {COLORS["text_secondary"]};
        }}

        /* ---------- structure ---------- */
        QFrame#sidebar {{
            background: {COLORS["background"]};
            border-right: 1px solid {COLORS["border"]};
        }}
        QFrame#card {{
            background: {COLORS["surface"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 14px;
        }}
        QFrame#card:hover {{
            border-color: {COLORS["border_bright"]};
            background: {COLORS["surface_raised"]};
        }}
        QFrame#hero {{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {COLORS["surface_raised"]}, stop:1 {COLORS["surface"]});
            border: 1px solid {COLORS["border"]};
            border-radius: 18px;
        }}
        QWidget#player {{
            background: {COLORS["surface"]};
            border-top: 1px solid {COLORS["border"]};
            border-radius: 0;
        }}
        QFrame#downloadIntro {{
            background: {COLORS["surface"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 14px;
        }}
        QFrame#downloadCard {{
            background: {COLORS["surface_raised"]};
            border: 1px solid {COLORS["border_bright"]};
            border-radius: 14px;
        }}
        QFrame#downloadQueue {{
            background: {COLORS["surface"]};
            border: 1px dashed {COLORS["border_bright"]};
            border-radius: 12px;
        }}
        QLabel#downloadPercent {{
            color: {COLORS["text"]};
            font-size: 16pt;
            font-weight: 600;
        }}
        QLabel#downloadStatus {{
            color: {COLORS["text_secondary"]};
            font-size: 9pt;
        }}
        QLabel#queueTitle {{
            color: {COLORS["text_muted"]};
            font-size: 8pt;
            font-weight: 500;
            letter-spacing: 0.5px;
        }}
        QLabel#queueText {{
            color: {COLORS["text_secondary"]};
            font-size: 9pt;
        }}
        QFrame#songCard, QFrame#resultCard {{
            background: transparent;
            border: 1px solid transparent;
            border-radius: 12px;
        }}
        QFrame#songCard:hover, QFrame#resultCard:hover {{
            background: {COLORS["surface"]};
            border-color: {COLORS["border"]};
        }}
        QFrame#resultCard[selected="true"] {{
            background: {COLORS["surface_raised"]};
            border-color: {COLORS["border_bright"]};
        }}
        QFrame#songCard[playing="true"] {{
            background: {COLORS["accent_wash"]};
            border-color: {COLORS["accent_soft"]};
        }}

        /* ---------- buttons: text ---------- */
        QPushButton {{
            background: {COLORS["surface_raised"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 10px;
            min-height: 32px;
            padding: 7px 14px;
            color: {COLORS["text_secondary"]};
            font-weight: 500;
        }}
        QPushButton:hover {{
            background: {COLORS["surface_hover"]};
            color: {COLORS["text"]};
            border-color: {COLORS["border_bright"]};
        }}
        QPushButton:pressed {{
            background: {COLORS["surface_active"]};
        }}
        QPushButton:focus {{
            border-color: {COLORS["border_bright"]};
        }}
        QPushButton:disabled {{
            color: {COLORS["text_muted"]};
            border-color: transparent;
            background: transparent;
        }}

        QPushButton#destructiveButton {{
            color: {COLORS["text_muted"]};
            background: transparent;
            border-color: transparent;
            min-width: 36px;
            max-width: 36px;
            min-height: 36px;
            max-height: 36px;
            border-radius: 18px;
            padding: 0;
        }}
        QPushButton#destructiveButton:hover {{
            color: {COLORS["danger"]};
            background: {COLORS["danger_wash"]};
        }}
        QPushButton#destructiveButton:pressed {{
            color: {COLORS["danger"]};
            background: {COLORS["danger_wash"]};
        }}

        QPushButton#accentButton {{
            background: {COLORS["accent"]};
            border: 1px solid {COLORS["accent"]};
            color: {COLORS["accent_text"]};
            font-weight: 600;
        }}
        QPushButton#accentButton:hover {{
            background: #ffffff;
            border-color: #ffffff;
        }}
        QPushButton#accentButton:focus {{
            background: #ffffff;
            border-color: #ffffff;
        }}
        QPushButton#accentButton:pressed {{
            background: {COLORS["accent_press"]};
            border-color: {COLORS["accent_press"]};
        }}
        QPushButton#accentButton:disabled {{
            background: {COLORS["surface_raised"]};
            border-color: {COLORS["border"]};
            color: {COLORS["text_muted"]};
        }}

        QPushButton#ghostButton {{
            background: transparent;
            border-color: transparent;
            color: {COLORS["text_secondary"]};
            padding: 6px 4px;
            min-height: 24px;
            text-decoration: none;
        }}
        QPushButton#ghostButton:hover {{
            color: {COLORS["text"]};
            background: transparent;
        }}
        QPushButton#ghostButton:pressed {{
            color: {COLORS["text_secondary"]};
            background: transparent;
        }}
        QPushButton#ghostButton:disabled {{
            color: {COLORS["text_muted"]};
            background: transparent;
        }}

        /* ---------- buttons: icon-only ---------- */
        QPushButton#iconButton {{
            min-width: 34px;
            max-width: 34px;
            min-height: 34px;
            max-height: 34px;
            padding: 0;
            border-radius: 17px;
            background: transparent;
            border: 1px solid transparent;
        }}
        QPushButton#iconButton:hover {{
            background: {COLORS["surface_hover"]};
            border-color: {COLORS["border"]};
        }}
        QPushButton#iconButton:pressed {{
            background: {COLORS["surface_active"]};
        }}
        QPushButton#iconButton:focus {{
            border-color: {COLORS["border_bright"]};
        }}
        QPushButton#iconButton:disabled {{
            background: transparent;
        }}

        QPushButton#saveButton {{
            min-width: 36px;
            max-width: 36px;
            min-height: 36px;
            max-height: 36px;
            padding: 0;
            border-radius: 18px;
            background: {COLORS["surface_raised"]};
            border: 1px solid {COLORS["border"]};
        }}
        QPushButton#saveButton:hover, QPushButton#saveButton:focus {{
            background: {COLORS["surface_hover"]};
            border-color: {COLORS["text_muted"]};
        }}
        QPushButton#saveButton:pressed {{
            background: {COLORS["surface_active"]};
            border-color: {COLORS["text_muted"]};
        }}
        QPushButton#saveButton:disabled {{
            background: transparent;
            border-color: {COLORS["border"]};
        }}

        QPushButton#backButton {{
            background: transparent;
            border-color: transparent;
            color: {COLORS["text_secondary"]};
            min-width: 32px;
            max-width: 32px;
            min-height: 32px;
            max-height: 32px;
            padding: 0;
            border-radius: 16px;
        }}
        QPushButton#backButton:hover {{
            background: {COLORS["surface_hover"]};
            color: {COLORS["text"]};
        }}
        QPushButton#backButton:pressed {{
            background: {COLORS["surface_active"]};
        }}

        QPushButton#playButton {{
            min-width: 42px;
            max-width: 42px;
            min-height: 42px;
            max-height: 42px;
            padding: 0;
            border-radius: 21px;
            background: {COLORS["accent"]};
            border: 1px solid {COLORS["accent"]};
        }}
        QPushButton#playButton:hover {{
            background: #ffffff;
            border-color: #ffffff;
        }}
        QPushButton#playButton:focus {{
            background: #ffffff;
            border-color: #ffffff;
        }}
        QPushButton#playButton:pressed {{
            background: {COLORS["accent_press"]};
            border-color: {COLORS["accent_press"]};
        }}
        QPushButton#playButton:disabled {{
            background: {COLORS["surface_raised"]};
            border-color: {COLORS["border"]};
        }}
        QFrame#songCard QPushButton#playButton,
        QFrame#card QPushButton#playButton {{
            min-width: 36px;
            max-width: 36px;
            min-height: 36px;
            max-height: 36px;
            border-radius: 18px;
        }}

        QLabel#playingPill {{
            color: {COLORS["text"]};
            background: {COLORS["accent_wash"]};
            border: 1px solid {COLORS["accent_soft"]};
            border-radius: 8px;
            padding: 2px 7px;
            font-size: 7.5pt;
            font-weight: 600;
        }}

        QPushButton#navButton {{
            text-align: left;
            background: transparent;
            border: 1px solid transparent;
            color: {COLORS["text_secondary"]};
            padding: 9px 12px;
            border-radius: 10px;
            font-weight: 500;
            min-height: 22px;
        }}
        QPushButton#navButton:hover {{
            background: {COLORS["surface"]};
            color: {COLORS["text"]};
        }}
        QPushButton#navButton:checked {{
            background: {COLORS["surface_raised"]};
            border-color: {COLORS["border"]};
            color: {COLORS["text"]};
            font-weight: 600;
        }}

        QPushButton#modeButton {{
            background: transparent;
            border: 1px solid transparent;
            border-bottom: 2px solid transparent;
            color: {COLORS["text_muted"]};
            padding: 6px 3px;
            margin-right: 14px;
            border-radius: 0;
            font-weight: 500;
            min-height: 22px;
        }}
        QPushButton#modeButton:hover {{
            color: {COLORS["text_secondary"]};
            background: transparent;
        }}
        QPushButton#modeButton:checked {{
            color: {COLORS["text"]};
            border-bottom: 2px solid {COLORS["accent"]};
            font-weight: 600;
        }}

        QPushButton#chevronButton {{
            min-width: 28px;
            max-width: 28px;
            min-height: 28px;
            max-height: 28px;
            padding: 0;
            border-radius: 14px;
            background: transparent;
            border: 1px solid transparent;
        }}
        QPushButton#chevronButton:hover {{
            background: {COLORS["surface_hover"]};
        }}
        QPushButton#chevronButton:pressed {{
            background: {COLORS["surface_active"]};
        }}

        /* ---------- inputs ---------- */
        QLineEdit {{
            background: {COLORS["surface"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 10px;
            padding: 9px 13px;
            color: {COLORS["text"]};
            selection-background-color: {COLORS["accent_soft"]};
            selection-color: {COLORS["text"]};
        }}
        QLineEdit:hover {{
            border-color: {COLORS["border_bright"]};
        }}
        QLineEdit:focus {{
            border-color: {COLORS["border_bright"]};
            background: {COLORS["surface_raised"]};
        }}
        QTextEdit#cookieBox {{
            background: {COLORS["surface"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 12px;
            padding: 10px 12px;
            color: {COLORS["text"]};
            font-family: "DejaVu Sans Mono", "Consolas", monospace;
            font-size: 8.5pt;
            selection-background-color: {COLORS["accent_soft"]};
            selection-color: {COLORS["text"]};
        }}
        QTextEdit#cookieBox:focus {{
            border-color: {COLORS["border_bright"]};
            background: {COLORS["surface_raised"]};
        }}
        QCheckBox {{
            spacing: 8px;
            color: {COLORS["text_secondary"]};
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
        }}
        QCheckBox::indicator:unchecked {{
            border: 1px solid {COLORS["text_muted"]};
            border-radius: 5px;
            background: transparent;
        }}
        QCheckBox::indicator:unchecked:hover {{
            border-color: {COLORS["text_secondary"]};
            background: {COLORS["surface_hover"]};
        }}
        QCheckBox::indicator:checked {{
            border: 1px solid {COLORS["accent"]};
            border-radius: 5px;
            background: {COLORS["accent"]};
            image: url("{check_icon}");
        }}
        QCheckBox::indicator:checked:hover {{
            border-color: #ffffff;
            background: #ffffff;
        }}

        /* ---------- scroll & sliders ---------- */
        QScrollBar:vertical {{
            background: transparent;
            width: 8px;
            margin: 4px 0;
        }}
        QScrollBar::handle:vertical {{
            background: {COLORS["scroll"]};
            border-radius: 4px;
            min-height: 28px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {COLORS["scroll_hover"]};
        }}
        QScrollBar::handle:vertical:pressed {{
            background: {COLORS["scroll_press"]};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: transparent;
        }}
        QScrollBar:horizontal {{
            background: transparent;
            height: 8px;
            margin: 0 4px;
        }}
        QScrollBar::handle:horizontal {{
            background: {COLORS["scroll"]};
            border-radius: 4px;
            min-width: 28px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {COLORS["scroll_hover"]};
        }}
        QScrollBar::handle:horizontal:pressed {{
            background: {COLORS["scroll_press"]};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: transparent;
        }}
        QSlider:horizontal {{
            min-height: 18px;
        }}
        QSlider::groove:horizontal {{
            height: 3px;
            background: {COLORS["border_bright"]};
            border-radius: 2px;
        }}
        QSlider::sub-page:horizontal {{
            background: {COLORS["text"]};
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {COLORS["text"]};
            width: 11px;
            height: 11px;
            margin: -4px 0;
            border-radius: 5px;
        }}
        QSlider::handle:horizontal:hover {{
            background: {COLORS["accent"]};
            width: 13px;
            height: 13px;
            margin: -5px 0;
            border-radius: 6px;
        }}
        QSlider::handle:horizontal:pressed {{
            background: {COLORS["accent_press"]};
            width: 13px;
            height: 13px;
            margin: -5px 0;
            border-radius: 6px;
        }}
        QProgressBar {{
            background: {COLORS["border"]};
            border: 0;
            border-radius: 4px;
            text-align: center;
            color: transparent;
            height: 6px;
            min-height: 6px;
            max-height: 6px;
        }}
        QProgressBar#downloadProgress {{
            background: {COLORS["surface_active"]};
            border: 0;
            border-radius: 4px;
            text-align: center;
            color: transparent;
            height: 8px;
            min-height: 8px;
            max-height: 8px;
        }}
        QProgressBar#downloadProgress::chunk {{
            background: {COLORS["text"]};
            border-radius: 4px;
        }}
        QProgressBar::chunk {{
            background: {COLORS["text"]};
            border-radius: 4px;
        }}
        """
    )
