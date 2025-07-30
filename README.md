# Automated Asset Trading on Cocos

This repository is built upon [pyCocos](https://github.com/nacho-herrera/pyCocos).  
It includes a set of Python scripts designed to automatically trade Argentine bonds using the **Cocos Capital** API, and retrieve reference prices from **PPI**.  
The system operates by monitoring prices, detecting arbitrage opportunities, and executing buy/sell orders in real time.

---

🧠 What does this system do?

- Fetches real-time prices for multiple assets using the Cocos API.
- Stores market data in a PostgreSQL database for analysis and backtesting.
- Executes automated trading strategies (e.g., ratio arbitrage).
- Supports per-script logging to separate files.
- Emits sound alerts when opportunities are detected.
- Automatically executes trades when an arbitrage opportunity arises.
- Can be integrated with the Windscribe API for IP rotation or remote access.

---

⚙️ Requirements

- Python ≥ 3.8
- PostgreSQL (with a `prices` database)
- A `.env` file with the following keys:

CLAVE_SECRETA_COCOS=...
CLAVE_PUBLICA_PPI=...
CLAVE_PRIVADA_PPI=...
CLAVE_POSGRES=...

To save market data during trading hours, simply run:
```bash python operar_precios.py```

To automate daily trading, add the appropriate command to your crontab, adjusting for your local file path.

🛠️ Key Features

- Multithreaded system for concurrent price fetching.
- Automatic recovery from token errors (401).
- Dynamic minimum-ratio threshold using the calculate_daily_rate() function.
- Per-strategy logging.
- Configurable sound alerts for trading opportunities (auto_beep()).

🧾 Additional Notes

- Order logic is designed to minimize volume and reduce slippage risk.
- Execution is restricted to the Argentine market hours (11:00 to 17:00).


