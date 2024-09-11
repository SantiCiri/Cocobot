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
logging.basicConfig(filename='logs.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
import concurrent.futures
import asyncio
import ast
import traceback
import random

class TradingHelper:
    _app_instance=None

    def __init__(self,cbu_uss=None,cbu_pesos=None):
        today=dt.today()
        self.today=today.strftime("%d%m%y")
        self.cbu_uss=cbu_uss
        self.cbu_pesos=cbu_pesos
    
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

    def write_to_db(self,extracted_data):
        #Renombra bid y ask por precio compra y venta
        extracted_data = [{"precio_compra" if key == "bid_price" 
                           else "precio_venta" if key == "ask_price" 
                           else "volumen_venta" if key == "ask_size" 
                           else "volumen_compra" if key == "bid_size" 
                           else key: value for key, value in item.items()} for item in extracted_data]
        
        # Conectar a la nueva base de datos Prices
        conn = psycopg2.connect(
            dbname="prices",
            user="postgres",
            password=os.getenv('CLAVE_POSGRES'),
            host="127.0.0.1"#"/var/run/postgresql"  # Usar Unix domain socket en lugar de host y puerto
        )

        # Crear un cursor
        cursor = conn.cursor()

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
    
    def fetch_book(self,ppi, instrument, term):
        current_book = ppi.marketdata.book(instrument["ticker"], instrument["type"], term)
        try: 
            timestamp = dt.strptime(current_book["date"], '%Y-%m-%dT%H:%M:%S.%f%z').strftime("%d/%m/%y %H:%M:%S.%f")
        except:
            return []

        if term == "INMEDIATA":
            plazo = "CI"
        elif term == "A-24HS":
            plazo = "24hs"
        elif term == "A-48HS":
            plazo = "48hs"

        if len(current_book['bids']) > 0:
            sell_price = current_book['bids'][0]['price']
            sell_quantity = current_book['bids'][0]['quantity']
        else:
            sell_price = 0
            sell_quantity = 0

        if len(current_book['offers']) > 0:
            buy_price = current_book['offers'][0]['price']
            buy_quantity = current_book['offers'][0]['quantity']
        else:
            buy_price = 0
            buy_quantity = 0

        if instrument["currency"] == "Pesos":
            currency = "ARS"
        elif instrument["currency"] == "Dolares billete | MEP":
            currency = "USD"
        else: 
            c=instrument["currency"]
            print(f"currency fantasma: {c}")

        now=dt.now()

        min_extracted_data = [{
            "short_ticker": instrument["ticker"],
            "currency": currency,
            "term": plazo,
            "bid_size": sell_quantity,
            "bid_price": sell_price,
            "ask_size": buy_quantity,
            "ask_price": buy_price,
            "timestamp":now.strftime("%d/%m/%y %H:%M:%S.%f")
        }]
        return min_extracted_data
    
    def get_ppi_prices(self):
        ppi=self.get_ppi_app_instance()
        print("Searching instruments")
        instruments=[]
        for letter in ["AL30"]:
                a = ppi.marketdata.search_instrument(letter, "", "","BONOS")
                print(a)
                instruments=instruments+a
        #remove duplicates
        instruments=[x for i, x in enumerate(instruments) if instruments.index(x) == i]

        # Convert list of dictionaries to JSON string
        json_string = json.dumps(instruments)
        print(json_string)
        # Write JSON string to a .txt file
        with open("instruments.txt", "w") as file:
            file.write(json_string)
        #remover el CCL
        instruments = [d for d in instruments if all("Dolares divisa | CCL" not in value for value in d.values())]
        terms=["A-48HS", "INMEDIATA", "A-24HS"]

        # Search Current Book
        print("Searching Current Book")
        while True:
            hora_actual=dt.now().hour            
            if 11<= hora_actual<=17:
                with concurrent.futures.ProcessPoolExecutor() as executor:
                    for instrument in instruments:
                        try:
                            a=executor.submit(self.fetch_book,ppi,instrument,terms[0])
                            b=executor.submit(self.fetch_book,ppi,instrument,terms[1])
                            c=executor.submit(self.fetch_book,ppi,instrument,terms[2])
                            print(a.result()+b.result()+c.result())
                            self.write_to_db(a.result()+b.result()+c.result(),"prices_ppi.db")
                        except:pass

    def place_buy_order(self,mail,ticker,quantity,price,term,currency):
        quantity=str(quantity)
        price=str(price)
        app = self.get_cocos_app_instance(mail=mail)
        if term == "CI": settlement = app.settlements.T0
        elif term == "24": settlement = app.settlements.T1
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
        elif term == "24": settlement = app.settlements.T1
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

    def get_cocos_prices(self,mail,tickers=None,box_position=0):
        app = self.get_cocos_app_instance(mail=mail)
        count=self.latest_count()
        if tickers==None:
            # Lee el contenido del archivo y lo guarda en la variable tickers
            with open('tickers.txt', 'r') as file: 
                tickers = file.read()
                tickers = ast.literal_eval(tickers.strip())

        # Especificar los nombres de las columnas basándose en las claves del diccionario
        while True:
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
        return app.funds_available()
    
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
        elif term == "24": settlement = app.settlements.T1
        if currency == "pesos": currency=app.currencies.PESOS
        elif currency == "dolares": currency=app.currencies.USD
        try: long_ticker = app.long_ticker(ticker=ticker, 
                                        settlement=settlement, 
                                        currency=currency)
        except Exception as e:
            if "Error code: 401" in str(e):
                print("401")
                app._refresh_access_token()
                app= self.get_cocos_app_instance(mail=mail)
                long_ticker = app.long_ticker(ticker=ticker, 
                                        settlement=settlement, 
                                        currency=currency)
        stocks_available=app.stocks_available(long_ticker)
        #print(stocks_available)
        return stocks_available

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
    