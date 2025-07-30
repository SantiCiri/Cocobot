from trading_helper import TradingHelper
import time
import math
from datetime import datetime as dt
import ast
app=TradingHelper()
mail="cirigliano.santiago@gmail.com"
with open('tickers_backup.txt', 'r') as file:
    tickers = file.read()
    tickers = ast.literal_eval(tickers.strip())
currencies={
    "ARS":"pesos",
    #"USD":"dolares"
}
while dt.now().hour < 11: time.sleep(60)
while (11 <= dt.now().hour < 16) or (dt.now().hour == 16 and dt.now().minute < 20):
  if dt.now().hour >= 17:break
  for currency in currencies:
    try:
        funds_ci=app.funds(mail=mail)["CI"][currency.lower()]
    except Exception as e:
        print(e)
        print("otro intento de funds_ci")
        time.spleep(1)
        funds_ci=app.funds(mail=mail)["CI"][currency.lower()]
    for ticker in tickers: 
        try:
            response = app.get_snapshot(mail=mail, ticker=ticker)
        except Exception as e:
            # Reintentar mientras el error sea un 500
            while "Error code: 500" in str(e):
                try:
                    response = app.get_snapshot(mail=mail, ticker=ticker)
                    break  # Salir del bucle si la solicitud es exitosa
                except Exception as e:
                    if "Error code: 500" not in str(e):
                        print(f"Error al obtener snapshot: {e}")  # Registro del error diferente
                        break  # Salir del bucle si es otro error
                    continue  # Continúa reintentando si es un error 500
        ci = [item for item in response if item['currency'] == currency and item['term'] == 'CI'][0]
        hs =  [item for item in response if item['currency'] == currency and item['term'] == '24hs'][0]
        price_factor =  [item for item in response if item['currency'] == currency and item['term'] == '24hs'][0]["price_factor"]
        #print(f"CI {ci}")
        #print(f"hs {hs}")
        #print(price_factor)
        precio_compra=ci['asks'][0]['price']
        vol_compra=ci['asks'][0]['size']
        precio_venta=hs['bids'][0]['price']
        vol_venta=hs['bids'][0]['size']
        monto_compra=precio_compra*vol_compra/price_factor
        monto_venta=precio_venta*vol_venta/price_factor
        minimum_monto = min(monto_compra,monto_compra,funds_ci)
        if minimum_monto == 0:break
        #Este bloque gestiona la cantidad de papeles a comprar y vender según dónde este la limitante del volumen
        #Maximiza la cantidad de recompra a 24 horas para hacer interes compuesto
        if minimum_monto == monto_compra:
            vol_venta = math.floor(vol_compra * (precio_venta/precio_compra))
        elif minimum_monto == monto_venta:
            vol_compra = math.floor(vol_venta / (precio_venta/precio_compra))
        elif minimum_monto == funds_ci:
            vol_compra = math.floor(funds_ci*price_factor/precio_compra)
            vol_venta = math.floor(vol_compra*(precio_venta/precio_compra))
        #termina bloque de volumenes
        if precio_venta == 0 or precio_compra == 0 or vol_venta==0 or vol_compra==0: break
        ratio=precio_venta/precio_compra
        #print(f"Ticker {ticker} ratio {ratio}, compro {vol_compra} nominales a {precio_compra}, vendo {vol_venta} nominales a {precio_venta}")
        rate=app.calculate_daily_rate()
        if ratio > rate and ratio < 1.2:#actualmente la caucion esta en 1.0009
            print(f"RATIO {ratio} con {ticker}. Compro {vol_compra} nominales a {precio_compra} y vendo {vol_venta} nominales a {precio_venta}")
            buy_order=app.place_buy_order(mail=mail,
                                            ticker=ticker,
                                            quantity=vol_compra,
                                            price=precio_compra,
                                            term="CI",
                                            currency=currencies[currency])
            print(f"Orden de venta {ticker} {buy_order}")
            order_status=app.check_order_status(mail=mail,
                                                order_number=buy_order["Orden"])
            print(order_status)
            start_time = time.time()
            while order_status == "MARKET":
                elapsed_time = time.time() - start_time
                if elapsed_time > 2:
                    cancel_order=app.cancel_order(mail=mail,order_number=buy_order["Orden"])
                    print(f"Orden cancelada por Timeout: {cancel_order}")
                    break
                order_status=app.check_order_status(mail=mail,
                                                order_number=buy_order["Orden"])
                print(f"Order Status de compra CI {order_status}")

            if order_status == "EXECUTED":
                sell_order=app.place_sell_order(mail=mail,
                                            ticker=ticker,
                                            quantity=vol_venta,
                                            price=precio_venta,
                                            term="24",
                                            currency=currencies[currency])
                print(f"Orden de venta 24hs {ticker} {buy_order}")
                order_status=app.check_order_status(mail=mail,
                                                    order_number=buy_order["Orden"])
                while order_status == "MARKET":
                    try:
                        time.sleep(1)
                        order_status=app.check_order_status(mail=mail, order_number=buy_order["Orden"])
                        if order_status =="FILLED": break
                    except Exception as e: print(e)
                print(f"Order status de Venta {order_status}")
                if buy_order["Success"] == True: print("Negocio ATR")