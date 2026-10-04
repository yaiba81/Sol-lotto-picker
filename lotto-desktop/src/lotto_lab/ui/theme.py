"""Application-wide visual tokens expressed as a Qt stylesheet."""

APP_STYLESHEET = """
QWidget {
    color: #020617;
    background: #F8FAFC;
    font-family: "Segoe UI", "Noto Sans", sans-serif;
    font-size: 14px;
}
QMainWindow { background: #F8FAFC; }
QFrame#sidebar {
    background: #0F172A;
    border: none;
}
QFrame#sidebar QLabel { background: transparent; }
QLabel#brand {
    color: #FFFFFF;
    font-size: 22px;
    font-weight: 700;
    padding: 4px 8px 16px 8px;
}
QLabel#eyebrow {
    color: #0369A1;
    font-size: 12px;
    font-weight: 700;
}
QLabel#pageTitle {
    color: #020617;
    font-size: 28px;
    font-weight: 700;
}
QLabel#pageDescription {
    color: #475569;
    font-size: 15px;
}
QLabel#notice {
    color: #334155;
    background: #E8ECF1;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    padding: 12px;
}
QPushButton#navButton {
    color: #CBD5E1;
    background: transparent;
    border: none;
    border-radius: 7px;
    padding: 11px 12px;
    text-align: left;
    min-height: 24px;
}
QPushButton#navButton:hover { background: #1E293B; color: #FFFFFF; }
QPushButton#navButton:checked { background: #0369A1; color: #FFFFFF; font-weight: 600; }
QPushButton#navButton:focus { border: 2px solid #7DD3FC; }
QStatusBar { background: #FFFFFF; color: #475569; border-top: 1px solid #E2E8F0; }
QFrame#controlPanel, QGroupBox {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 12px;
}
QGroupBox { font-weight: 600; margin-top: 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QLineEdit {
    background: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 7px;
    padding: 8px 10px;
    min-height: 22px;
}
QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus, QLineEdit:focus, QListWidget:focus, QCheckBox:focus, QTabBar::tab:focus, QTableWidget:focus { border: 2px solid #0369A1; }
QPushButton#primaryButton {
    background: #0369A1;
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 9px 18px;
    min-height: 24px;
    font-weight: 600;
}
QPushButton#primaryButton:hover { background: #075985; }
QPushButton#primaryButton:pressed { background: #0C4A6E; }
QPushButton#primaryButton:focus { border: 2px solid #7DD3FC; }
QPushButton#primaryButton:disabled { background: #94A3B8; }
QPushButton#linkButton {
    background: transparent;
    color: #0369A1;
    border: none;
    text-decoration: underline;
    padding: 7px;
}
QPushButton#linkButton:focus { border: 2px solid #0369A1; }
QLabel#numberBall {
    background: #0F172A;
    color: #FFFFFF;
    border-radius: 21px;
    min-width: 42px;
    max-width: 42px;
    min-height: 42px;
    max-height: 42px;
    font-size: 16px;
    font-weight: 700;
}
QLabel#scoreLabel { color: #0369A1; font-size: 16px; font-weight: 700; }
QLabel#ticketDetails { color: #334155; background: #F8FAFC; padding: 10px; }
QLabel#statusMessage { color: #334155; min-height: 22px; }
QTableWidget {
    background: #FFFFFF;
    alternate-background-color: #F1F5F9;
    border: 1px solid #E2E8F0;
    gridline-color: #E2E8F0;
}
QHeaderView::section {
    background: #E8ECF1;
    color: #0F172A;
    border: none;
    border-bottom: 1px solid #CBD5E1;
    padding: 8px;
    font-weight: 600;
}
"""

APP_STYLESHEET += """
QPushButton { padding: 8px 12px; min-height: 24px; }
QPushButton:focus { border: 2px solid #0369A1; }
QTabBar::tab { padding: 8px 12px; }
QTabBar::tab:selected { background: #E8ECF1; color: #0F172A; }
QProgressBar { border: 1px solid #CBD5E1; text-align: center; min-height: 20px; }
QProgressBar::chunk { background: #0369A1; }
"""
