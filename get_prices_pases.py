from trading_helper import TradingHelper
app=TradingHelper()
tickers=["DIP0","TVPP","PARP","CUAP","DICP","TO26","T4X4","T5X4","T2X5","TC25P","TX25","TX26","TX28","TZX25","TZX26","TZX27","TZX28","TZXD5","TZXD6","TZXD7","TZV25","TV25","S13S4","S30S4","S14O4","S29N4","S17E5","S13D4","S31E5","S28F5","S31M5"]
app.get_cocos_prices(mail="cirigliano.santiago@gmail.com",tickers=tickers)