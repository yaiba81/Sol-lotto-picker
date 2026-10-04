# Sol Lotto Picker

Two apps for exploring PCSO lotto history and generating six-number tickets:

| App | Purpose | Tech stack |
| --- | --- | --- |
| [Desktop](lotto-desktop/README.md) | Local history, analysis, strategy experiments, and backtesting | Python 3.12+, PySide6, SQLAlchemy with SQLite, pandas, NumPy, SciPy, Matplotlib |
| [Mobile](lotto-mobile/README.md) | Recent results, schedule, analysis, and ticket generation on a phone | TypeScript, React Native, Expo SDK 57 |

Lotto draws are independent random events. Historical patterns and weighted selection do not improve the mathematical chance of winning.

## Features

| Feature | Desktop | Mobile |
| --- | --- | --- |
| Today's regular PCSO draw schedule in Philippine time | Yes | Yes |
| Recent official results for five supported games | Automatic sync and manual refresh | Refresh from PCSO LottoMatik |
| Six-number random and weighted generation | Built-in and saved strategy versions | Built-in strategies |
| Descriptive history and range analysis | Charts and tables | Number, parity, and range summaries |
| CSV history import, saved tickets, Strategy Lab, and chronological backtesting | Yes | No |

The supported games are Lotto 6/42, Mega Lotto 6/45, Super Lotto 6/49, Grand Lotto 6/55, and Ultra Lotto 6/58. Mobile needs an internet connection for fresh results and history-based strategies; it does not save draws or tickets offline. Desktop stores its data locally.

## Run the desktop app (Windows PowerShell)

Run these commands from the repository root:

```powershell
cd lotto-desktop
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m lotto_lab
```

The package uses a `src` layout, so the editable install must run **inside `lotto-desktop`**. The explicit `.venv` interpreter works without activating the environment. On later runs, use:

```powershell
cd lotto-desktop
.\.venv\Scripts\python.exe -m lotto_lab
```

The desktop database lives in the user's local application-data directory by default. Set `LOTTO_LAB_DATA_DIR` to another directory if needed. See the [desktop README](lotto-desktop/README.md) for strategy and backtesting details.

## Run the mobile app

Install Node.js and npm, then run these commands from the repository root:

```powershell
cd lotto-mobile
npm ci
npm start
```

Open the QR code with Expo Go on a phone connected to the development server. For a local Android development build, use `npm run android` after setting up the Android SDK and a device or emulator. That development build uses Metro on your computer. For a standalone Android build, follow the [mobile README](lotto-mobile/README.md). iOS simulator builds require macOS.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| `No module named lotto_lab` | Run `pip install -e ".[dev]"` from `lotto-desktop` using its `.venv` Python, then launch with `.\.venv\Scripts\python.exe -m lotto_lab`. A global `py -3` command can select a different or incorrectly installed Python. |
| PowerShell blocks `.venv\Scripts\Activate.ps1` | Use the explicit `.\.venv\Scripts\python.exe` commands above; activation is optional. |
| Desktop dependency install fails | Confirm `py -3 --version` is Python 3.12 or newer and that you are in `lotto-desktop`. Upgrade pip with `.\.venv\Scripts\python.exe -m pip install --upgrade pip`, then retry the install. |
| Desktop opens without recent results | Check your internet connection and use **Draw History → Check official results**. Previously stored local data remains available when the feed cannot be reached. |
| `npm start` cannot find Expo or modules | Run `npm ci` from `lotto-mobile` and retry. |
| Phone cannot connect to Expo | Put the phone and computer on the same network and check that a firewall or VPN is not blocking the development server. |
| `npm run android` fails or the installed app needs the laptop | Check the Android SDK, device or emulator, and Metro. A development build needs Metro; use the standalone build instructions in the mobile README for an app that opens without it. |
| Mobile results do not load | Check the phone's internet connection and retry **Refresh official results**. History-based strategies need recent result data. |
