from trading_helper import TradingHelper

import time
from datetime import datetime

end_time = datetime.now().replace(hour=10, minute=58, second=0)
if datetime.now() > end_time:
    end_time = end_time.replace(day=end_time.day + 1)

while datetime.now() < end_time:
    time.sleep(60)

app=TradingHelper()
app.get_cocos_prices(mail="cirigliano.santiago@gmail.com")