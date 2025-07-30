#!/usr/bin/env python
# coding: utf-8

# In[1]:


from trading_helper import TradingHelper
import time
import math
import os
from datetime import datetime as dt
#if os.path.exists("operar_pase.log"):os.remove("operar_pase.log")
# Configurar el logger para que guarde en 'operar_pase.logs'
app = TradingHelper(log_name=f"operar_pase")
mail="cirigliano.santiago@gmail.com"
tickers_in_portfolio=("NU","TX26","TZX26","TZXM6","TX28")

while dt.now().hour < 11: time.sleep(60)
app.logger.info(f"arrancando {dt.now()} {tickers_in_portfolio}")
while (11 <= dt.now().hour < 16) or (dt.now().hour == 16 and dt.now().minute < 25):
  for ticker in tickers_in_portfolio:
    try:
        time.sleep(0.01)
        stocks_available=app.stocks_available(mail=mail,ticker=ticker,term="CI",currency="pesos")
        if stocks_available==None: 
            app.logger.warning(f"stocks_available es None para {ticker}")
            count=0
            while count<30:
                app.logger.warning(f"Intento nro {count} para obtener stocks de {ticker}")
                stocks_available=app.stocks_available(mail=mail,ticker=ticker,term="CI",currency="pesos")
                if stocks_available is not None: break
                time.sleep(1)
                count=count+1
        if stocks_available["CI"]>0:
            amount_in_portfolio=stocks_available["CI"]
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
                            app.logger.error(f"Error al obtener snapshot para {ticker}: {e}")  # Registro del error diferente
                            break  # Salir del bucle si es otro error
                        continue  # Continúa reintentando si es un error 500
            ci = [item for item in response if item['currency'] == 'ARS' and item['term'] == 'CI'][0]
            hs =  [item for item in response if item['currency'] == 'ARS' and item['term'] == '24hs'][0]
            #print(f"CI {ci}")
            #print(f"hs {hs}")
            precio_venta=ci['bids'][0]['price']
            vol_venta=ci['bids'][0]['size']
            precio_compra=hs['asks'][0]['price']
            vol_compra=hs['asks'][0]['size']
            minimum_vol = min(vol_compra,vol_venta,amount_in_portfolio)
            if minimum_vol == 0: continue
            #Este bloque gestiona la cantidad de papeles a comprar y vender según dónde este la limitante del volumen
            #Maximiza la cantidad de recompra a 24 horas para hacer interes compuesto
            if minimum_vol == vol_venta:
                vol_compra = math.floor(vol_venta * (precio_venta/precio_compra))
            elif minimum_vol == amount_in_portfolio:
                vol_venta= amount_in_portfolio
                vol_compra = math.floor(vol_venta * (precio_venta/precio_compra))
            elif minimum_vol== vol_compra:
                vol_venta = math.ceil(vol_compra /(precio_venta/precio_compra))
            #termina bloque de volumenes
            if precio_venta == 0 or precio_compra == 0: break
            ratio=precio_venta/precio_compra
            app.logger.info(f"Procesando ticker: {ticker} ratio {ratio}")
            #print(f"RATIO {ratio} con {ticker}. Vendo {vol_venta} nominales y compro {vol_compra} nominales. venta CI a ${precio_venta} y compra 24hs a ${precio_compra}")
            rate=app.calculate_daily_rate(max_ratio=1.005,min_ratio=1.001,hora_negociacion=16)
            if ratio > 1.002 and ratio < 1.1:
                app.auto_beep()
                app.logger.info(f"RATIO {ratio} con {ticker}. Vendo {vol_venta} nominales a ${precio_venta} y compro {vol_compra} nominales a ${precio_compra}.")
                sell_order=app.place_sell_order(mail=mail,
                                                ticker=ticker,
                                                quantity=vol_venta,
                                                price=precio_venta,
                                                term="CI",
                                                currency="pesos")
                app.logger.info(f"Orden de venta {ticker}: {sell_order}")
                order_status=app.check_order_status(mail=mail,
                                                    order_number=sell_order["Orden"])
                app.logger.info(f"Estado de la orden de venta {ticker}: {order_status}")
                start_time = time.time()
                while order_status == "MARKET":
                    elapsed_time = time.time() - start_time
                    if elapsed_time > 6:
                        try:
                            cancel_order=app.cancel_order(mail=mail,order_number=sell_order["Orden"])
                            app.logger.info(f"Orden cancelada por Timeout: {cancel_order}")
                            break
                        except Exception as e:
                             if "PENDING_OMS" or "FILLED" in str(e):
                                 app.logger.info(f"Estado de la orden de venta {ticker}: {e}")
                                 pass
                    order_status=app.check_order_status(mail=mail,
                                                    order_number=sell_order["Orden"])
                    app.logger.info(f"Estado de la orden de venta {ticker}: {order_status}")
                    
                if order_status == "EXECUTED":
                    buy_order=app.place_buy_order(mail=mail,
                                                ticker=ticker,
                                                quantity=vol_compra,
                                                price=precio_compra,
                                                term="24",
                                                currency="pesos")
                    app.logger.info(f"Orden de compra {ticker}: {buy_order}")
                    order_status=app.check_order_status(mail=mail,
                                                        order_number=buy_order["Orden"])
                    while order_status == "MARKET":
                        try:
                            time.sleep(1)
                            order_status=app.check_order_status(mail=mail, order_number=buy_order["Orden"])
                            if order_status =="FILLED": break
                            cancel_order=app.cancel_order(mail=mail,order_number=buy_order["Orden"])
                            app.logger.info(f"Orden cancelada de compra: {cancel_order}")
                            if ticker == "NU": precio_compra = precio_compra + 10
                            else: precio_compra = precio_compra + 0.1
                            buy_order=app.place_buy_order(mail=mail,
                                ticker=ticker,
                                quantity=vol_compra,
                                price=precio_compra,
                                term="24",
                                currency="pesos")
                        except Exception as e: 
                            app.logger.error(f"Error en la compra para {ticker}: {e}")
                        
                    app.logger.info(f"Estado de la orden de compra {ticker}: {order_status}")
                    if buy_order["Success"] == True: 
                        app.logger.info(f"Negocio ATR con {ticker}")
    except Exception as e: 
      print("error general")
      app.logger.error(f"Error general en la ejecución: {e}")


# In[ ]:





# In[ ]:




