"""QSS theme (modern dark) for Cheat Engine 2X.

The CE original used the default Windows-LCL look (flat blue, 2005-ish). This
replaces it with a dark, modern palette and control styling.
"""

from __future__ import annotations
from ..config import C

_STYLESHEET = f"""

/* ---- base window ---- */
QWidget {{
    background: {C['bg']};
    color: {C['text']};
    font-family: "{C['FONT']}";
    font-size: {C['SIZE']['base']}pt;
}}

/* ---- app window (titlebar-less, frameless feel) ---- */
QMainWindow, QDialog {{
    background: {C['bg']};
    border: none;
}}

QMenuBar {{
    background: {C['bg_panel']};
    border-bottom: 1px solid {C['border']};
    padding: 2px;
}}
QMenuBar::item {{
    background: transparent;
    padding: 4px 12px;
    border: none;
}}
QMenuBar::item:selected {{
    background: {C['bg_surface']};
    border-radius: 4px;
}}
QMenu {{
    background: {C['bg_panel']};
    border: 1px solid {C['border']};
    selection-background-color: {C['select']};
    color: {C['text']};
}}
QMenu::item {{
    padding: 4px 24px 4px 12px;
}}
QMenu::item:selected {{
    background: {C['select']};
    color: {C['text']};
}}

/* ---- toolbars / search ---- */
QToolBar {{
    background: {C['bg_shelf']};
    border: none;
    border-bottom: 1px solid {C['border']};
    padding: 4px;
    min-height: 28px;
}}
QToolButton {{
    background: {C['bg_surface']};
    border: 1px solid {C['border']};
    border-radius: 4px;
    padding: 4px 8px;
    color: {C['text']};
}}
QToolButton:hover {{
    background: {C['bg']};
    border-color: {C['accent']};
}}
QToolButton:checked {{
    background: {C['accent']};
    border-color: {C['accent']};
    color: #fff;
}}
QComboBox, QLineEdit, QTextEdit, QPlainTextEdit {{
    background: {C['bg_input']};
    border: 1px solid {C['border']};
    border-radius: 4px;
    padding: 4px 8px;
    color: {C['text']};
    selection-background-color: {C['select']};
}}
QComboBox:editable {{
    background: {C['bg_input']};
}}
QComboBox QLineEdit {{
    border: none;
}}
QComboBox::drop-down {{
    border: none;
    width: 18px;
}}
QComboBox::down-arrow {{
    image: none;
    border: 1px solid {C['border']};
    border-radius: 3px;
    width: 8px; height: 8px;
    background: {C['bg_shelf']};
}}
QComboBox QAbstractItemView {{
    background: {C['bg']};
    border: 1px solid {C['border']};
    selection-background-color: {C['select']};
    alternating-row-color: {C['bg_shelf']};
}}
QSpinBox, QDoubleSpinBox {{
    background: {C['bg_input']};
    border: 1px solid {C['border']};
    border-radius: 4px;
    padding: 2px 6px;
    color: {C['text']};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background: {C['bg_shelf']};
    border: 1px solid {C['border']};
    width: 14px; height: 14px;
    border-radius: 3px;
}}
QSpinBox::up-arrow, QSpinBox::down-arrow {{
    background: {C['bg_shelf']};
}}
QSlider::groove:horizontal {{
    background: {C['bg_shelf']};
    height: 6px;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {C['accent']};
    border: 1px solid {C['accent']};
    width: 12px;
    height: 12px;
    border-radius: 6px;
    margin: -4px 0;
}}
QSlider::groove:vertical {{
    background: {C['bg_shelf']};
    width: 6px;
    border-radius: 3px;
}}
QSlider::handle:vertical {{
    background: {C['accent']};
    border: 1px solid {C['accent']};
    width: 12px;
    height: 12px;
    border-radius: 6px;
    margin: 0 -4px;
}}

/* ---- buttons / tool buttons ---- */
QPushButton {{
    background: {C['bg_surface']};
    border: 1px solid {C['border']};
    border-radius: 4px;
    padding: 4px 10px;
    color: {C['text']};
}}
QPushButton:hover {{
    background: {C['bg']};
    border-color: {C['accent']};
}}
QPushButton:pressed {{
    background: {C['accent']};
    border-color: {C['accent']};
    color: #fff;
}}
QPushButton:disabled {{
    background: {C['bg_shelf']};
    color: {C['text_muted']};
    border-color: {C['border']};
}}
QPushButton[flat=true] {{
    border: none;
    background: transparent;
    padding: 2px 6px;
}}
QPushButton[flat=true]:hover {{
    background: {C['bg']};
    border-radius: 3px;
}}

/* ---- checkboxes / radio ---- */
QCheckBox, QRadioButton {{
    spacing: 6px;
    color: {C['text']};
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {C['border']};
    background: {C['bg_surface']};
    border-radius: 3px;
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {C['accent']};
    border-color: {C['accent']};
}}
QCheckBox:hover::indicator, QRadioButton:hover::indicator {{
    border-color: {C['accent']};
}}
QGroupBox {{
    border: 1px solid {C['border']};
    border-radius: 5px;
    margin-top: 8px;
    padding-top: 6px;
}}
QGroupBox::title {{
    color: {C['text_muted']};
    font-weight: normal;
}}

/* ---- list views / tables ---- */
QListView, QListWidget, QListWidget::item {{
    background: {C['bg_surface']};
    border: 1px solid {C['border']};
    selection-background-color: {C['select']};
    alternate-background-color: {C['bg_shelf']};
    spacing: 2px;
}}
QListView::item:selected {{
    background: {C['select']};
    color: {C['text']};
}}
QTableView, QTableWidget, QTableWidget::item {{
    background: {C['bg_surface']};
    border: 1px solid {C['border']};
    gridline-color: {C['border']};
    alternating-row-color: {C['bg_shelf']};
    show-decoration-background: 1;
}}
QTableView::item:selected, QTableWidget::item:selected {{
    background: {C['select']};
    color: {C['select_fg']};
}}
QTreeView, QTreeWidget {{
    background: {C['bg_surface']};
    border: 1px solid {C['border']};
    gridline-color: {C['border']};
    alternating-row-color: {C['bg_shelf']};
    selection-background-color: {C['select']};
}}
QTableView::item:selected {{
    background: {C['select']};
    color: {C['select_fg']};
}}

/* ---- status / progress ---- */
QStatusBar {{
    background: {C['bg_panel']};
    border-top: 1px solid {C['border']};
    color: {C['text_muted']};
    font-size: {C['SIZE']['sm']}pt;
}}
QProgressBar {{
    background: {C['bg_shelf']};
    border: 1px solid {C['border']};
    border-radius: 4px;
    height: 18px;
    text-align: center;
    color: {C['text']};
}}
QProgressBar::chunk {{
    background: {C['accent']};
    border-radius: 3px;
}}
QProgressBar::chunk:success {{
    background: {C['green']};
}}
QProgressBar::chunk:error {{
    background: {C['red']};
}}

/* ---- scrollbars ---- */
QScrollBar:horizontal {{
    background: {C['scrollbar']};
    height: 12px;
    border: none;
    border-radius: 6px;
}}
QScrollBar:vertical {{
    background: {C['scrollbar']};
    width: 12px;
    border: none;
    border-radius: 6px;
}}
QScrollBar::handle:horizontal, QScrollBar::handle:vertical {{
    background: {C['scrollbar_thumb']};
    border: none;
    border-radius: 6px;
}}
QScrollBar::handle:horizontal:hover, QScrollBar::handle:vertical:hover {{
    background: {C['accent']};
}}
QScrollBar::add-line, QScrollBar::sub-line {{
    background: none;
    height: 0;
}}
QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
}}

/* ---- glass / semi-transparent overlays ---- */
QWidget[glass=true] {{
    background: rgba(22,24,28,0.85);
}}

/* ---- specific panels ---- */
#mainBody {{
    background: {C['bg']};
}}
#panelTop {{
    background: {C['bg_panel']};
    border-bottom: 1px solid {C['border']};
}}
#panelLeft {{
    background: {C['bg_panel']};
    border-right: 1px solid {C['border']};
}}
#panelRight {{
    background: {C['bg_panel']};
    border-left: 1px solid {C['border']};
}}
#statusPanel {{
    background: {C['bg_panel']};
    border-top: 1px solid {C['border']};
}}
#toolbarSearch {{
    background: {C['bg_shelf']};
    border: none;
    border-bottom: 1px solid {C['border']};
    padding: 4px;
}}
#toolbarSearch QLineEdit {{
    background: {C['bg_shelf']};
    border: 1px solid {C['border']};
    color: {C['text']};
}}
#contentArea {{
    background: {C['bg']};
}}
"""


def style_sheet() -> str:
    return _STYLESHEET
