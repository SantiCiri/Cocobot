from trading_helper import TradingHelper
import sqlite3
import threading

app=TradingHelper()
app.get_ppi_prices()
