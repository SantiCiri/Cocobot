#!/usr/bin/env python
# coding: utf-8

# In[1]:


import os
import time
import math
from datetime import datetime as dt
from trading_helper import TradingHelper
#if os.path.exists("operar_MR36O_LECHO.log"):os.remove("operar_MR36O_LECHO.log")
app = TradingHelper(log_name=f"operar_TZX26_TZXM6")
mail = "cirigliano.santiago@gmail.com"
cantidad_minima = 5
terms = ["24hs"]
lista = ["TZX26", "TZXM6"]
combinations = (lista, lista[::-1])  # Original y lista invertida
while dt.now().hour < 11:
    time.sleep(60)  
app.logger.info(f"arrancando {dt.now()}")

while (11 <= dt.now().hour < 16) or (dt.now().hour == 16 and dt.now().minute < 57):
    time.sleep(2)
    try:
        for position in [0, 1]:
            for term in terms:
                tickers = combinations[position]
                try:
                    amount_in_portfolio = app.stocks_available(mail=mail, ticker=tickers[0], term=term, currency="pesos")[term]
                except Exception as e:
                    app.logger.error(f"Error al obtener stocks disponibles para {tickers[0]}: {e}")
                    amount_in_portfolio = app.stocks_available(mail=mail, ticker=tickers[0], term=term, currency="pesos")[term]

                if amount_in_portfolio != 0:
                    try:
                        numerador = app.get_snapshot(mail=mail, ticker=tickers[0])
                        denominador = app.get_snapshot(mail=mail, ticker=tickers[1])
                        while not isinstance(numerador, list) or not isinstance(denominador, list):
                            numerador = app.get_snapshot(mail=mail, ticker=tickers[0])
                            denominador = app.get_snapshot(mail=mail, ticker=tickers[1])
                            time.sleep(0.5)
                    except Exception as e:
                        app.logger.error(f"Error al obtener snapshot para {tickers}: {e}")
                        while not isinstance(numerador, list) or not isinstance(denominador, list):
                            try:
                                numerador = app.get_snapshot(mail=mail, ticker=tickers[0])
                                denominador = app.get_snapshot(mail=mail, ticker=tickers[1])
                                break
                            except Exception as e:
                                if "Error code: 500" not in str(e):
                                    app.logger.error(f"Error no 500 al obtener snapshot: {e}")
                                    break
                                continue

                    numerador = [item for item in numerador if item['currency'] == 'ARS' and item['term'] == term][0]
                    denominador = [item for item in denominador if item['currency'] == 'ARS' and item['term'] == term][0]
                    
                    precio_venta_numerador = numerador['bids'][0]['price']
                    vol_venta_numerador = numerador['bids'][0]['size']
                    precio_compra_denominador = denominador['asks'][0]['price']
                    vol_compra_denominador = denominador['asks'][0]['size']
                    
                    app.logger.info(f"{tickers[0]}, {term}, {amount_in_portfolio}")
                    if tickers[0] == 'TZX26': maximum_vol = 367000
                    if tickers[0] == 'TZXM6': maximum_vol = 607600
                    amount_in_portfolio = min(amount_in_portfolio, maximum_vol)
                    minimum_vol = min(vol_compra_denominador, vol_venta_numerador, amount_in_portfolio)
                    
                    if precio_venta_numerador == 0 or precio_compra_denominador == 0 or minimum_vol == 0:
                        break

                    ratio = precio_venta_numerador / precio_compra_denominador
                    if tickers[0]=="TZX26": min_ratio=1.655
                    elif tickers[0]=="TZXM6": min_ratio = 0.608

                    app.logger.info(f"Ratio {ratio}, vendiendo {vol_venta_numerador} de {tickers[0]} a {precio_venta_numerador} y comprando {vol_compra_denominador} de {tickers[1]} a {precio_compra_denominador}")

                    if ratio > min_ratio and minimum_vol > 2:
                        app.auto_beep()
                        if minimum_vol == vol_venta_numerador:
                            vol_compra_denominador = math.floor(vol_venta_numerador * ratio)
                        elif minimum_vol == amount_in_portfolio:
                            vol_venta_numerador = amount_in_portfolio
                            vol_compra_denominador = math.floor(vol_venta_numerador * ratio)
                        elif minimum_vol == vol_compra_denominador:
                            vol_venta_numerador = math.ceil(vol_compra_denominador / ratio)

                        if vol_venta_numerador * precio_venta_numerador < vol_compra_denominador * precio_compra_denominador:
                            vol_compra_denominador -= 1

                        app.logger.info(f"Oportunidad ratio {ratio}, vendiendo {vol_venta_numerador} de {tickers[0]} a {precio_venta_numerador} y comprando {vol_compra_denominador} de {tickers[1]} a {precio_compra_denominador}")

                        sell_order = app.place_sell_order(mail=mail,
                                                          ticker=tickers[0],
                                                          quantity=vol_venta_numerador,
                                                          price=precio_venta_numerador,
                                                          term=term,
                                                          currency="pesos")
                        app.logger.info(f"Orden de venta {tickers[0]}: {sell_order}")

                        order_status = app.check_order_status(mail=mail, order_number=sell_order["Orden"])
                        
                        app.logger.info(f"Estado de la orden de venta: {order_status}")

                        start_time = time.time()
                        max_time = 4
                        while order_status == "MARKET" or order_status=="PARTIALLY_EXECUTED" or order_status=="PENDING_OMS":
                            if order_status == "PARTIALLY_EXECUTED":
                              app.logger.info(f"Orden PARTIALLY_EXECUTED: {order_status}")
                              elapsed_time = time.time() - start_time
                              if elapsed_time > max_time:
                                try:
                                    cancel_order=app.cancel_order(mail=mail,order_number=sell_order["Orden"])
                                    funds=app.funds(mail=mail)
                                    funds = funds['24hs']['ars']
                                    app.logger.info(f"Fondos actuales: ${funds}")
                                    order_status = app.check_order_status(mail=mail, order_number=sell_order["Orden"])
                                except Exception as e:
                                    app.logger.warning(f"Error al obtener fondos a 24 horas: {e}")
                                    app.logger.warning(f"Reintentando obtener fondos:")
                                    funds=app.funds(mail=mail)
                                    funds = funds['24hs']['ars']
                                    app.logger.info(f"Fondos actuales: ${funds}")
                                    order_status = app.check_order_status(mail=mail, order_number=sell_order["Orden"])
                              else:
                                  time.sleep(1)
                                  order_status = app.check_order_status(mail=mail, order_number=sell_order["Orden"])

                            elif order_status == "MARKET":
                                app.logger.info(f"Orden MARKET: {order_status}")
                                elapsed_time = time.time() - start_time
                                if elapsed_time > max_time:
                                    try:
                                        cancel_order=app.cancel_order(mail=mail,order_number=sell_order["Orden"])
                                        app.logger.info(f"Orden cancelada por Timeout: {cancel_order}")
                                        order_status = app.check_order_status(mail=mail, order_number=sell_order["Orden"])
                                        break
                                    except Exception as e:
                                        order_status = app.check_order_status(mail=mail, order_number=sell_order["Orden"])
                                        if "PENDING_OMS" or "FILLED" in str(e):
                                            app.logger.info(f"Estado de la orden de venta {tickers[0]}: {e}")
                                            pass
                                else: 
                                    time.sleep(0.5)
                                    order_status = app.check_order_status(mail=mail, order_number=sell_order["Orden"])
                            
                            elif order_status == "PENDING_OMS":
                                app.logger.info(f"Orden PENDING_OMS: {order_status}")
                                time.sleep(0.5)
                                order_status = app.check_order_status(mail=mail, order_number=sell_order["Orden"])
                            app.logger.info(f"Estado de la orden de venta: {order_status}")

                        if order_status == "EXECUTED" or order_status == "PARTIALLY_EXECUTED":
                            if order_status == "PARTIALLY_EXECUTED":
                                vol_compra_denominador=math.floor(funds/(precio_compra_denominador*1000))
                            buy_order = app.place_buy_order(mail=mail,
                                                            ticker=tickers[1],
                                                            quantity=vol_compra_denominador,
                                                            price=precio_compra_denominador,
                                                            term=term,
                                                            currency="pesos")
                            
                            app.logger.info(f"Orden de compra {tickers[1]}: {buy_order}")
                            time.sleep(4)
                            order_status = app.check_order_status(mail=mail, order_number=buy_order["Orden"])
                            while order_status == "MARKET" or order_status=="PENDING_OMS" or order_status=="REJECTED":
                                if order_status == "PENDING_OMS":
                                    app.logger.info(f"Orden PENDING_OMS: {order_status}")
                                    time.sleep(0.5)
                                    order_status = app.check_order_status(mail=mail, order_number=buy_order["Orden"])
                                elif order_status == "MARKET":
                                    try:
                                        cancel_order = app.cancel_order(mail=mail, order_number=buy_order["Orden"])
                                        app.logger.info(f"Orden de compra cancelada: {cancel_order}")
                                        precio_compra_denominador += 0.1
                                        vol_compra_denominador -= 1
                                        buy_order = app.place_buy_order(mail=mail,
                                                                        ticker=tickers[1],
                                                                        quantity=vol_compra_denominador,
                                                                        price=precio_compra_denominador,
                                                                        term=term,
                                                                        currency="pesos")
                                        time.sleep(4)
                                        order_status = app.check_order_status(mail=mail, order_number=buy_order["Orden"])
                                        app.logger.info(f"Orden MARKET + $0.1: {order_status}")
                                    except Exception as e:
                                        app.logger.error(f"Error en la compra de {tickers[1]}: {e}")
                                        order_status = app.check_order_status(mail=mail, order_number=buy_order["Orden"])
                                elif order_status=="REJECTED":
                                    buy_order = app.place_buy_order(mail=mail,
                                                            ticker=tickers[1],
                                                            quantity=vol_compra_denominador,
                                                            price=precio_compra_denominador,
                                                            term=term,
                                                            currency="pesos")
                                    order_status = app.check_order_status(mail=mail, order_number=buy_order["Orden"])


                            app.logger.info(f"Estado de la orden de compra: {order_status}")
                            if buy_order["Success"]:
                                app.logger.info(f"Negocio exitoso con {tickers[1]}")
                                if vol_compra_denominador<10:continue
                                time.sleep(5)

    except Exception as e:
        app.logger.error(f"Error general: {e}")

