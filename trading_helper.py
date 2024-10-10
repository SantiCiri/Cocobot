from pycocos import Cocos
import pandas as pd
from datetime import datetime as dt, timedelta
from dotenv import load_dotenv
import os
import shutil
from ppi_client.models.order_budget import OrderBudget
from ppi_client.models.order_confirm import OrderConfirm
import time
import json
import plotly.express as px
import plotly.graph_objs as go
import sqlite3
import psycopg2
from psycopg2 import sql
import numpy as np
import string
from ppi_client.api.constants import ACCOUNTDATA_TYPE_ACCOUNT_NOTIFICATION, ACCOUNTDATA_TYPE_PUSH_NOTIFICATION, \
    ACCOUNTDATA_TYPE_ORDER_NOTIFICATION
from ppi_client.models.account_movements import AccountMovements
from ppi_client.models.order import Order
from ppi_client.ppi import PPI
from ppi_client.models.disclaimer import Disclaimer
from ppi_client.models.instrument import Instrument
import logging
#logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
import concurrent.futures
import asyncio
import ast
import traceback
import random
from concurrent.futures import ThreadPoolExecutor, as_completed


class TradingHelper:
    _app_instance=None

    def __init__(self,log_name="logs",cbu_uss=None,cbu_pesos=None):
        today=dt.today()
        self.today=today.strftime("%d%m%y")
        self.cbu_uss=cbu_uss
        self.cbu_pesos=cbu_pesos

        # Crear un logger específico para esta instancia
        self.logger = logging.getLogger(log_name)
        self.logger.setLevel(logging.INFO)

        # Crear un handler para escribir los logs en un archivo específico
        handler = logging.FileHandler(f'{log_name}.log')
        handler.setLevel(logging.INFO)

        # Definir el formato del log
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)

        # Agregar el handler al logger
        self.logger.addHandler(handler)
    
    @classmethod
    def get_ppi_app_instance(cls,mail=None):
        if cls._app_instance is None:
            # Cargar las variables de entorno desde .env
            ppi=PPI(sandbox=False)
            load_dotenv()
            ppi.account.login_api(os.getenv('CLAVE_PUBLICA_PPI'), os.getenv('CLAVE_PRIVADA_PPI'))
            cls._app_instance = ppi
        return cls._app_instance

    @classmethod
    def get_cocos_app_instance(cls,mail):
        if cls._app_instance is None:
            # Cargar las variables de entorno desde .env
            load_dotenv()
            cls._app_instance = Cocos(email=mail, 
                                      password=os.getenv('CLAVE_SECRETA_COCOS'), 
                                      api_key=None,
                                      topt_secret_key=os.getenv('topt_secret_key'))
        return cls._app_instance
    
    def latest_count(self):
        conn = psycopg2.connect(
            dbname="prices",
            user="postgres",
            password=os.getenv('CLAVE_POSGRES'),
            host="127.0.0.1"  # "/var/run/postgresql"  # Usar Unix domain socket en lugar de host y puerto
        )

        # Obtener la fecha de hoy
        today_start = dt.now().strftime('%Y/%m/%d 00:00:00.00')
        today_end = dt.now().strftime('%Y/%m/%d 23:59:59.999999')

        # Ejecutar la query y obtener el resultado directamente con un cursor
        with conn.cursor() as cur:
            cur.execute(f"""
                        SELECT MAX(count) AS last_count
                        FROM precios
                        WHERE timestamp >= '{today_start}' AND timestamp <= '{today_end}'
                        """)
            last_count = cur.fetchone()[0]

        if last_count is None: last_count=0
        else: last_count=last_count+1
        # Cerrar la conexión
        conn.close()
        return last_count

    def write_to_db(self,extracted_data,origin="cocos"):
        if origin=="cocos":
            #Renombra bid y ask por precio compra y venta
            extracted_data = [{"precio_compra" if key == "bid_price" 
                            else "precio_venta" if key == "ask_price" 
                            else "volumen_venta" if key == "ask_size" 
                            else "volumen_compra" if key == "bid_size" 
                            else key: value for key, value in item.items()} for item in extracted_data]
        else:pass
        # Conectar a la nueva base de datos Prices
        conn = psycopg2.connect(
            dbname="prices",
            user="postgres",
            password=os.getenv('CLAVE_POSGRES'),
            host="127.0.0.1"#"/var/run/postgresql"  # Usar Unix domain socket en lugar de host y puerto
        )
        
        # Crear un cursor
        cursor = conn.cursor()
        #Puede que la variable extracted data sea un diccionario o una lista de diccionarios. en cualquier caso aca se convierte siempre a una lista
        if isinstance(extracted_data, dict): extracted_data = [extracted_data]
        # Iterar sobre la lista de diccionarios y agregar cada elemento a la base de datos

        for row in extracted_data:
            cursor.execute("""
                            INSERT INTO precios (short_ticker, currency, term, volumen_venta, precio_venta, volumen_compra, precio_compra, timestamp,count)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s,%s)
                        """, (
                            row['short_ticker'],
                            row['currency'],
                            row['term'],
                            row['volumen_venta'],
                            row['precio_venta'],
                            row['volumen_compra'],
                            row['precio_compra'],
                            row['timestamp'],
                            row["count"]
                        ))

        # Guardar los cambios y cerrar la conexión
        conn.commit()
        cursor.close()
        conn.close()

    def empty_cocos_CI(self,mail, currency="usd"):
        """Withdraw all funds available in the "CI" (Current Investment) for the specified currency.

        Args:
            currency (str, optional): The type of currency to withdraw. Defaults to "usd", may also be "ars"
        """
        app = self.get_cocos_app_instance(mail=mail)  # Get the current application instance
        
        accounts = app.my_bank_accounts()  # Retrieve the list of bank accounts
        # Filter the list for the proper currency and select the first matching account
        account = [account for account in accounts if account['currency'] == currency.upper()][0]
        cbu_cvu = account["cbu_cvu"]  # Extract the CBU/CVU from the account information
        funds = app.funds_available()  # Get the available funds
        amount = funds["CI"][currency]  # Extract the amount available in the "CI" for the specified currency

        # Conditional operation based on the currency
        if currency == "usd":
            app.withdraw_funds(currency=app.currencies.USD, amount=amount, cbu_cvu=cbu_cvu)
        elif currency == "ars":
            app.withdraw_funds(currency=app.currencies.PESOS, amount=amount, cbu_cvu=cbu_cvu)
    
    def get_ppi_prices(self,tickers=None):
        ppi=self.get_ppi_app_instance()
        count=0
        with open('ppi_instruments.txt', 'r') as file:
            instruments = file.read()
            instruments = ast.literal_eval(instruments)
        # Search Current Book
        print("Searching Current Book")
        while dt.now().hour <11: time.sleep(60)
        while 11 <= dt.now().hour <17:
            for instrument in instruments:
                if instrument["type"]=="OBLIGACIONES-NEGOCIABLES":instrument["type"]="ON"
                for term in ["INMEDIATA", "A-24HS"]:
                  try:
                    #print({instrument["ticker"], instrument["type"],term})
                    response=ppi.marketdata.book(instrument["ticker"],instrument["type"],term)
                    #print(response)
                    if len (response["offers"])==0:break
                    precio_venta=response["offers"][0]["price"]
                    volumen_venta=response["offers"][0]["quantity"]
                    precio_compra=response["bids"][0]["price"]
                    volumen_compra=response["bids"][0]["quantity"]
                    if instrument["currency"]=='Pesos':currency="ARS"
                    elif instrument["currency"]=='Dolares billete | MEP':currency="USD"
                    if term=="INMEDIATA":term="CI",
                    elif term=="A-24HS":term="24hs"
                    now = dt.now()
                    row={"short_ticker":instrument["ticker"],
                        "currency":currency,
                        "term":term,
                        "volumen_venta":volumen_venta,
                        "precio_venta":precio_venta,
                        "volumen_compra":volumen_compra,
                        "precio_compra":precio_compra,
                        "timestamp":now.strftime("%Y/%m/%d %H:%M:%S.%f"),
                        "count":count
                        }
                    
                    self.write_to_db(row,origin="ppi")
                  except Exception as e:
                    print(e)
                    print(instrument,response)
                    pass
            count=count+1

    def get_simul_ppi_prices(self, tickers=None):
        def process_instrument(instrument, term, count):
            ppi = self.get_ppi_app_instance()
            try:
                response = ppi.marketdata.book(instrument["ticker"], instrument["type"], term)
                if len(response["offers"]) == 0:
                    return None
                timestamp = response["date"][:10] + ' ' + response["date"][11:22]
                if not timestamp[-1].isdigit():
                    timestamp = timestamp[:-1] + '5'
                precio_venta = response["offers"][0]["price"]
                volumen_venta = response["offers"][0]["quantity"]
                precio_compra = response["bids"][0]["price"]
                volumen_compra = response["bids"][0]["quantity"]
                currency = "ARS" if instrument["currency"] == 'Pesos' else "USD"
                term = "CI" if term == "INMEDIATA" else "24hs"
                row = {
                    "short_ticker": instrument["ticker"],
                    "currency": currency,
                    "term": term,
                    "volumen_venta": volumen_venta,
                    "precio_venta": precio_venta,
                    "volumen_compra": volumen_compra,
                    "precio_compra": precio_compra,
                    "timestamp": timestamp,
                    "count": count
                }
                self.write_to_db(row, origin="ppi")
            except Exception as e:
                print(e)
                print(instrument, response)
        
        # Load instruments from file
        with open('ppi_instruments.txt', 'r') as file:
            instruments = ast.literal_eval(file.read())

        # Update instrument type
        for instrument in instruments:
            if instrument["type"] == "OBLIGACIONES-NEGOCIABLES":
                instrument["type"] = "ON"

        # Search Current Book
        print("Searching Current Book")
        count = 0

        while 11 <= dt.now().hour < 24:
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = []
                for instrument in instruments:
                    for term in ["INMEDIATA", "A-24HS"]:
                        futures.append(executor.submit(process_instrument, instrument, term, count))
                # Wait for all futures to complete
                for future in concurrent.futures.as_completed(futures):
                    future.result()  # To catch any exceptions that occurred

            count += 1

    def place_buy_order(self,mail,ticker,quantity,price,term,currency):
        quantity=str(quantity)
        price=str(price)
        app = self.get_cocos_app_instance(mail=mail)
        if term == "CI": settlement = app.settlements.T0
        elif term == "24" or term =="24hs": settlement = app.settlements.T1
        if currency == "pesos": currency=app.currencies.PESOS
        elif currency == "dolares": currency=app.currencies.USD

        long_ticker = app.long_ticker(ticker=ticker, 
                                    settlement=settlement, 
                                    currency=currency)

        order = app.submit_buy_order(long_ticker=long_ticker, 
                                     quantity=quantity, 
                                     price=price)

        # Save to file
        #with open('tradebook.txt', 'w') as file:json.dump({"operation":"buy",
        #                                                   "ticker":ticker,
        #                                                   "quantity":quantity,
        #                                                   "price":price,
        #                                                   "term":term,
        #                                                   "currency":currency},
        #                                                   file, indent=1)
        return order
    
    def cancel_order_if_still_open(self,mail,order_number):
        start_time=time.time()
        max_duration = 5  # 5 minutes in seconds
        while True:
            time.sleep(0.01)
            app=self.get_cocos_app_instance(mail=mail)
            order_status=app.order_status(order_number)
            order_status=order_status["status"]
            if (time.time() - start_time > max_duration):
                cancelation=app.cancel_order(order_number=order_number)
                print("Order cancelled")
                return cancelation
            if order_status == "REJECTED":
                return "Order rejected"
            if order_status == "MARKET":
                pass
            if order_status == "EXECUTED":
                return {"Success": "EXECUTED"}#"Order executed in the market!"
            
    def check_order_status(self,mail,order_number):
        app=self.get_cocos_app_instance(mail=mail)
        order_status=app.order_status(order_number)
        return order_status["status"]
    
    def place_sell_order(self,mail,ticker,quantity,price,term,currency):
        quantity=str(quantity)
        price=str(price)
        app = self.get_cocos_app_instance(mail=mail)
        if term == "CI": settlement = app.settlements.T0
        elif term == "24" or term == "24hs": settlement = app.settlements.T1

        if currency == "pesos": currency=app.currencies.PESOS
        elif currency == "dolares": currency=app.currencies.USD

        long_ticker = app.long_ticker(ticker=ticker, 
                                    settlement=settlement, 
                                    currency=currency)

        order = app.submit_sell_order(long_ticker=long_ticker, 
                                    quantity=quantity, 
                                    price=price)
        
        #with open('tradebook.txt', 'w') as file:json.dump("{"operation":"sell",
        #                                            "ticker":ticker,
        #                                            "quantity":quantity,
        #                                            "price":price,
        #                                            "term":term,
        #                                            "currency":currency}",
        #                                            file, indent=1)
        return order
    
    def cancel_order(self,mail,order_number):
        app = self.get_cocos_app_instance(mail=mail)
        cancel=app.cancel_order(order_number=order_number)
        return cancel
    
    def get_snapshot(self,mail,ticker):
        try:
            app= self.get_cocos_app_instance(mail=mail)
        except Exception as e:
            print(e)
            app._refresh_access_token()
            app= self.get_cocos_app_instance(mail=mail)
        response=app.get_instrument_snapshot(ticker=ticker, segment=app.segments.DEFAULT)
        return response
    
    def get_cocos_simul_prices(self, mail, tickers=None, box_position=0):
        app = self.get_cocos_app_instance(mail=mail)
        count = self.latest_count()
        
        # Leer los tickers de un archivo si no se pasan como parámetro
        if tickers is None:
            with open('tickers.txt', 'r') as file:
                tickers = file.read()
                tickers = ast.literal_eval(tickers.strip())
                print(len(tickers))

        # Especificar los nombres de las columnas basándose en las claves del diccionario
        columnas = ["short_ticker", "currency", "term", "bid_size", "bid_price", "ask_size", "ask_price", "count"]

        def fetch_and_store_data(ticker):
            """Función para obtener datos de la API y guardarlos en la base de datos."""
            try:
                response = app.get_instrument_snapshot(ticker=ticker, segment=app.segments.DEFAULT)
                extracted_data = []
                for element in response:
                    # Desarmar precios y volúmenes de compra y venta para que queden cada uno en su columna
                    extracted_item = {
                        **element,
                        'bid_size': element['bids'][box_position]['size'] if element['bids'] else None,
                        'bid_price': element['bids'][box_position]['price'] if element['bids'] else None,
                        'ask_price': element['asks'][box_position]['price'] if element['asks'] else None,
                        'ask_size': element['asks'][box_position]['size'] if element['asks'] else None
                    }
                    extracted_item = {columna: extracted_item[columna] for columna in columnas if columna in extracted_item}
                    now = dt.now()
                    extracted_item.update({"timestamp": now.strftime("%Y/%m/%d %H:%M:%S.%f"), "count": count})
                    extracted_data.append(extracted_item)
                
                # Guardar los datos en la base de datos
                self.write_to_db(extracted_data)
            except Exception as e:
                print(f"ERROR {ticker}")
                if "Error code: 401" in str(e):
                    print("401")
                    app._refresh_access_token()
                logging.error(f"ERROR {ticker}: {str(e)}")

        # Ejecutar las solicitudes en paralelo utilizando ThreadPoolExecutor
        while True:
            hora_actual = dt.now().hour
            if 11 <= hora_actual < 17:
                with ThreadPoolExecutor(max_workers=2) as executor:  # Puedes ajustar max_workers según la cantidad de concurrencia deseada
                    futures = {executor.submit(fetch_and_store_data, ticker): ticker for ticker in tickers}
                    for future in as_completed(futures):
                        ticker = futures[future]
                        try:
                            future.result()  # Esto lanzará una excepción si ocurrió un error en el hilo
                        except Exception as e:
                            print(f"Error processing {ticker}: {e}")
                count += 1

    def get_cocos_prices(self,mail,tickers=None,box_position=0):
        app = self.get_cocos_app_instance(mail=mail)
        count=self.latest_count()
        if tickers==None:
            # Lee el contenido del archivo y lo guarda en la variable tickers
            with open('tickers.txt', 'r') as file: 
                tickers = file.read()
                tickers = ast.literal_eval(tickers.strip())
        while dt.now().hour < 11:
            time.sleep(60)
        # Especificar los nombres de las columnas basándose en las claves del diccionario
        while 11 <= dt.now().hour < 17:
            hora_actual=dt.now().hour
            if 11 <= hora_actual < 17:
                for ticker in tickers:
                    try: 
                        response=app.get_instrument_snapshot(ticker=ticker, segment=app.segments.DEFAULT)
                        columnas = ["short_ticker", "currency", "term", "bid_size","bid_price", "ask_size","ask_price","count"]
                        extracted_data = []
                        for element in response:
                            #Desarmar precios y volumenes de compra y venta para que queden cada uno en su columna
                            extracted_item = {
                                **element,
                                'bid_size': element['bids'][box_position]['size'] if element['bids'] else None,
                                'bid_price': element['bids'][box_position]['price'] if element['bids'] else None,
                                'ask_price':element['asks'][box_position]['price'] if element['asks'] else None,
                                'ask_size':element['asks'][box_position]['size'] if element['asks'] else None
                            }
                            extracted_item = {columna: extracted_item[columna] for columna in columnas if columna in extracted_item}
                            now=dt.now()
                            extracted_item.update({"timestamp":now.strftime("%Y/%m/%d %H:%M:%S.%f"),"count":count})
                            extracted_data.append(extracted_item)
                        self.write_to_db(extracted_data)
                    except Exception as e:
                        print(f"ERROR {ticker}")
                        if "Error code: 401" in str(e):
                            print("401")
                            app._refresh_access_token()
                        logging.error(f"ERROR {ticker}: {str(e)}")
                count=count+1

    def funds(self,mail):
        """
        Devuelve un diccionario con el formato 
        {'CI': {'ars': 3233.5, 'usd': 11.72, 'ext': 0}, '24hs': {'ars': 7343.5, 'usd': 11.72, 'ext': 0}, '48hs': {'ars': 7343.5, 'usd': 11.72, 'ext': 0}}
        """
        app = self.get_cocos_app_instance(mail=mail)
        try:
            funds=app.funds_available()
            return funds
        except Exception as e:
            if "Error code: 401" in str(e):
                print("401 on funds")
                app._refresh_access_token()
                funds=app.funds_available()
                return funds
    
    def portfolio(self,mail):
        try:
            app= self.get_cocos_app_instance(mail=mail)
        except Exception as e:
            if "Error code: 401" in str(e):
                print("401")
                app._refresh_access_token()
                app= self.get_cocos_app_instance(mail=mail)
        return app.my_portfolio()
    
    def stocks_available(self,mail,ticker,term,currency):
        app = self.get_cocos_app_instance(mail=mail)
        if term == "CI": settlement = app.settlements.T0
        elif term == "24" or term == "24hs": settlement = app.settlements.T1
        if currency == "pesos": currency=app.currencies.PESOS
        elif currency == "dolares": currency=app.currencies.USD
        attempts=20
        for attempt in range(attempts):  # Retry up to 3 times
            try:
                long_ticker = app.long_ticker(ticker=ticker, settlement=settlement, currency=currency)
                stocks_available = app.stocks_available(long_ticker)
                
                if stocks_available is None:
                    print(f"Warning: app.stocks_available returned None for {ticker} on attempt {attempt + 1}")
                    time.sleep(3*(attempt+1))  # Wait before retrying
                    continue
                
                return stocks_available
            
            except Exception as e:
                if "Error code: 401" in str(e):
                    print("401 error: Refreshing access token")
                    app._refresh_access_token()
                    app = self.get_cocos_app_instance(mail=mail)
                    continue  # Retry after refreshing the token
                else:
                    print(f"Error during stocks_available call: {e}")
                    break  # Exit loop if error is not related to token
        # If after retries we still got None, handle it
        print(f"Failed to retrieve stocks_available for {ticker} after {attempts} attempts")
        return None  # Return None or raise an exception depending on your needs

    def calculate_daily_rate(self,max_ratio=1.004,min_ratio=1.001,hora_negociacion=15):
        now = dt.now()
        # Definir los tiempos límite
        time_1500 = now.replace(hour=hora_negociacion, minute=0, second=0, microsecond=0)
        time_1630 = now.replace(hour=16, minute=30, second=0, microsecond=0)
        
        # Caso 1: Antes de las 15:00, y = 1.004
        if now < time_1500:
            return max_ratio
        
        # Caso 2: Entre las 15:00 y 16:30, y desciende linealmente
        elif time_1500 <= now <= time_1630:
            # Tiempo transcurrido desde las 15:00
            elapsed_time = (now - time_1500).total_seconds()
            # Duración total del descenso (90 minutos = 5400 segundos)
            total_time = (time_1630 - time_1500).total_seconds()
            # Cálculo de y según el descenso lineal
            return max_ratio - ((max_ratio-min_ratio) * (elapsed_time / total_time))
        
        # Caso 3: Después de las 16:30, y = 1.001
        else:
            return min_ratio

    def remove_d_from_ticker(self,ticker_time):
        """
        Removes the letter 'D' from the end of a ticker symbol in a combined ticker-time string.

        This function takes a string that combines a stock ticker and a timestamp, separated by a space. 
        If the ticker part of the string ends with the letter 'D', that letter is removed. The function 
        then returns the modified ticker-time string, preserving the original timestamp.

        Parameters:
        - ticker_time: A string containing a ticker symbol followed by a space and then a timestamp.

        Returns:
        - A string where the 'D' at the end of the ticker symbol is removed (if present), 
        followed by the original timestamp.
        """
        # Split the input string into ticker and time components based on the first space encountered.
        parts = ticker_time.split(' ', 1)  
        # Assign the first part to 'ticker' and the second part to 'time'.
        ticker, time = parts[0], parts[1]  
        # Check if the ticker ends with 'D'.
        if ticker.endswith('D'):  
            # If it does, remove the last character ('D') from the ticker.
            ticker = ticker[:-1]  
        # Reconstruct the ticker-time string with the modified ticker and original time part, and return it.
        return f"{ticker} {time}"  
    