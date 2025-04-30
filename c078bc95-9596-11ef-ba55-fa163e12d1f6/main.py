# coding=utf-8
from __future__ import print_function, absolute_import
from gm.api import *
from datetime import datetime, timedelta, time
from concurrent.futures import ThreadPoolExecutor

import socket
import json
import threading
import time
import struct
import numpy as np
import re
import pickle
import subprocess
import math
import sys 
# import time
# import datetime

from openpyxl import Workbook
from openpyxl import load_workbook
from openpyxl.styles import Alignment
from openpyxl.styles import Font

global_i = 0
str_strategy = 'VDebug' # V--VDebug # 这个标的代码列表文本现在更改为固定每天全标的列表文本，每天选出的监控文本用下面的selected_ids_path
selected_ids_path = 'c:\\TradeLogs\\' + 'VDebug-Selected' + '.txt'    # V--VDebug # 监控每天选出的标的列表文本
str_load_history = 'AllHistoryInfo'
log_path = 'c:\\TradeLogs\\Trade' + str_strategy + '.txt'
ids_path_a1 = 'c:\\TradeLogs\\IDs-' + str_strategy + '-A1.txt'
ids_path_a2 = 'c:\\TradeLogs\\IDs-' + str_strategy + '-A2.txt'
pos_info_path = 'c:\\TradeLogs\\Pos-' + str_strategy + '.npy'
statistics_info_path = 'c:\\TradeLogs\\Sta-' + str_strategy + '.npy'
buy_info_path = 'c:\\TradeLogs\\Buy-' + str_strategy + '.npy'
mac_address_path = 'c:\\TradeLogs\\' + 'macAddress' + '.txt'
# 策略中必须有init方法
def init(context):

    temp_section_ids_str = "SHSE.688981, SHSE.688800, SHSE.605218, SHSE.605208, SHSE.603819, SHSE.603818, SZSE.301135, SZSE.300994"

    # subscribe(symbols=temp_section_ids_str, frequency='tick', count=1, unsubscribe_previous=False, wait_group=True)

    yesterday_date = '2024-10-28'
    s_25_hisroty_time = str(yesterday_date) + ' 09:15:00'
    e_25_hisroty_time = str(yesterday_date) + ' 09:30:00'

    s_25_hisroty_time = str(yesterday_date) + ' 09:24:57'
    e_25_hisroty_time = str(yesterday_date) + ' 09:25:05'

    temp_his_25_amount_data = history(symbol=temp_section_ids_str, frequency='tick', start_time=s_25_hisroty_time,  end_time=e_25_hisroty_time, fields='symbol, last_amount, created_at', skip_suspended=False, fill_missing='NaN', adjust=ADJUST_PREV, df=False)

    # temp_his_25_amount_data = history(symbol=temp_section_ids_str, frequency='60s', start_time=s_25_hisroty_time,  end_time=e_25_hisroty_time, fields='symbol, amount, eob, name', adjust=ADJUST_PREV, df=False)

    print(f"==========================================")
    print(f"{len(temp_his_25_amount_data)}")

    for temp_data in temp_his_25_amount_data:
        print(f"{temp_data}")


if __name__ == '__main__':
    '''
        strategy_id策略ID, 由系统生成
        filename文件名, 请与本文件名保持一致
        mode运行模式, 实时模式:MODE_LIVE回测模式:MODE_BACKTEST
        token绑定计算机的ID, 可在系统设置-密钥管理中生成
        backtest_start_time回测开始时间
        backtest_end_time回测结束时间
        backtest_adjust股票复权方式, 不复权:ADJUST_NONE前复权:ADJUST_PREV后复权:ADJUST_POST
        backtest_initial_cash回测初始资金
        backtest_commission_ratio回测佣金比例
        backtest_slippage_ratio回测滑点比例
        backtest_match_mode市价撮合模式，以下一tick/bar开盘价撮合:0，以当前tick/bar收盘价撮合：1
        '''
    run(strategy_id='c078bc95-9596-11ef-ba55-fa163e12d1f6',
        filename='main.py',
        mode=MODE_BACKTEST,
        token='4f0478a8560615e1a0049e2e2565955620b3ec02',
        backtest_start_time='2020-11-01 08:00:00',
        backtest_end_time='2020-11-10 16:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=10000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001,
        backtest_match_mode=1)

