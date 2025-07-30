#!/usr/bin/env python
# coding: utf-8

# In[1]:


import os
import time
from datetime import datetime as dt
from trading_helper import TradingHelper
log_name="operar_precios"
if os.path.exists(f"{log_name}.log"):os.remove(f"{log_name}.log")
app = TradingHelper(log_name=log_name)
mail = "cirigliano.santiago@gmail.com"
cantidad_minima = 5
terms = ["24hs","CI"]
lista = ["TZX26", "TZX27", "TZXD6", "TZXD7", "TZXM6", "TZXM7", "TX26", "TX28","TX31",
         "AL30","GD30","GD35", "AL35","AL41","GD41","AE38","GD38","MR36O","LECHO","LECIO","MR37O"]
combinations = (lista, lista[::-1])  # Original y lista invertida
#while dt.now().hour < 11: time.sleep(60)
app.logger.info(f"arrancando {dt.now()}")
while 11 <= dt.now().hour < 17:
    try:
        app.get_cocos_prices(mail=mail,tickers=lista,timer=55)
    except:
        app.get_cocos_prices(mail=mail,tickers=lista,timer=55)
    if dt.now().hour == 17: break

