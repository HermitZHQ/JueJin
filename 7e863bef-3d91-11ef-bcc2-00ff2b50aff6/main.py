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

def ToolsScript():
    pass

class DownloadHistoryC():

    def __init__(self, context):
        self.SECTION_HISTORY_STOCK_COUNT = 50

        self.context = context
        self.str_strategy = 'AllHistoryInfo'
        self.str_load_ids_strategy = 'VDebug'
        self.save_history_path = 'c:\\TradeLogs\\' + self.str_strategy + " " + str(self.get_todat_date()) #加上日期，方便后面查找调用
        self.load_history_path = 'c:\\TradeLogs\\' + self.str_strategy + " " + str(self.get_todat_date()) + '.npy' #加上日期，方便后面查找调用
        self.ids_path_a1 = 'c:\\TradeLogs\\IDs-' + self.str_load_ids_strategy + '-A1.txt'

        self.subscription_stock_arr = []
        self.his_25_amount_data_arr = []
        self.his_data_arr = []
        self.notin_25_stock_arr = []

        self.his_data_dic = {}
        
        self.load_ids(context)

    def get_todat_date(self):
        # 获取当前日期
        today = datetime.now().date()

        # 获取前一天的日期  - timedelta(days=1)
        previous_day = today - timedelta(days=1)

        # 获取前一天的星期几（0是星期一，6是星期天）
        weekday = previous_day.weekday()

        # 如果前一天是星期六（weekday == 5）或星期天（weekday == 6）
        if weekday >= 5:
            # 获取星期五的日期（如果是星期天，需要减去2天；如果是星期六，需要减去1天）
            friday_date = previous_day - timedelta(days=weekday - 4)
            return friday_date
        else:
            # 前一天不是星期六或星期天，直接返回前一天的日期
            return previous_day

    def download_history(self):
        yesterday_date = self.get_todat_date()
        print(f"today_date:{yesterday_date}")
        s_time = str(yesterday_date) + ' 9:15:0'
        e_time = str(yesterday_date) + ' 15:00:0'
        test_s_time = '2024-07-04' + ' 9:15:0'
        test_e_time = '2024-07-04' + ' 15:00:0'
        #测试的时候用，重新赋值，不用后面老是替换了,不用的时候注释掉
        # s_time = test_s_time
        # e_time = test_e_time
        #历史数据中，集合进价时间
        s_25_hisroty_time = str(yesterday_date) + ' 09:25:00'
        e_25_hisroty_time = str(yesterday_date) + ' 09:25:00'

        print(f"{s_time} To {e_time}")
        print(f"SECTION_HISTORY_STOCK_COUNT::{self.SECTION_HISTORY_STOCK_COUNT}")

        #这里将改为分批次获取历史数据，history中df=False时，返回的是一个集合
        temp_ids_str = ''
        temp_index = 0
        temp_history_dic_index = 0

        #这里我们用一个临时集合来接取数据，再将临时集合中的数据添加到his_data中
        temp_his_data = []
        temp_his_25_amount_data = []
        #先将存入集合中的标的代码，以SECTION_HISTORY_STOCK_COUNT为准拼接未字符串，用来分批次获得历史数据
        for item in self.context.subscription_stock_arr:
                if temp_index == 0:
                    temp_ids_str = item
                else:
                    temp_ids_str = temp_ids_str + ',' + item
                temp_index += 1

                #当达到批次的数量时，开始获得历史数据
                if temp_index == self.SECTION_HISTORY_STOCK_COUNT:
                    temp_his_data = history(symbol=temp_ids_str, frequency='60s', start_time=s_time,  end_time=e_time, fields='symbol, amount, eob, name', adjust=ADJUST_PREV, df=False)
                    print(f"temp_his_data length::{len(temp_his_data)}")

                    temp_his_25_amount_data = history(symbol=temp_ids_str, frequency='tick', start_time=s_25_hisroty_time,  end_time=e_25_hisroty_time, fields='symbol, last_amount, created_at', skip_suspended=False, fill_missing='NaN', adjust=ADJUST_PREV, df=False)

                    #重置temp_index以及temp_ids_str
                    temp_index = 0
                    temp_ids_str = ''

                    for temp_data in temp_his_25_amount_data:
                        #这里应该要新创建一个变量
                        temp_temp_data = temp_data
                        # self.his_data[temp_history_dic_index] = {'symbol':temp_data['symbol'], 'amount':temp_data['last_amount'], 'eob':temp_data['created_at']}
                        self.his_25_amount_data_arr.append(temp_temp_data)
                        # temp_history_dic_index += 1

                    #将temp_his_data装入his_data里面
                    for temp_data in temp_his_data:
                        #这里应该要新创建一个变量
                        temp_temp_data = temp_data
                        # self.his_data.append(temp_temp_data)
                        # self.his_data[temp_history_dic_index] = temp_temp_data
                        self.his_data_arr.append(temp_temp_data)
                        # temp_history_dic_index += 1

                    #重置temp_his_data方便接受下一批次
                    temp_his_data.clear()

        #这里还需要判断，当出了for循环以后，如果还有剩余的票需要再用temp_his_data拿取剩余标的的历史数据
        #这里应该可以直接判断，直接拿取到his_data里，节省一个for循环时间，但以后这种情况可能会比较少，所以暂时也就无所谓了！
        if temp_ids_str != '':
            temp_his_data = history(symbol=temp_ids_str, frequency='60s', start_time=s_time,  end_time=e_time, fields='symbol, amount, eob, name', adjust=ADJUST_PREV, df=False)
            print(f"temp_his_data length::{len(temp_his_data)}")

            temp_his_25_amount_data = history(symbol=temp_ids_str, frequency='tick', start_time=s_25_hisroty_time,  end_time=e_25_hisroty_time, fields='symbol, last_amount, created_at', skip_suspended=False, fill_missing='NaN', adjust=ADJUST_PREV, df=False)

            print(f"temp_his_data length::{len(temp_his_25_amount_data)}")

            temp_ids_str = ''

            for temp_data in temp_his_25_amount_data:
                #这里应该要新创建一个变量
                temp_temp_data = temp_data
                # self.his_data[temp_history_dic_index] = {'symbol':temp_data['symbol'], 'amount':temp_data['last_amount'], 'eob':temp_data['created_at']}
                self.his_25_amount_data_arr.append(temp_temp_data)
                # temp_history_dic_index += 1

            #将temp_his_data装入his_data里面
            for temp_data in temp_his_data:
                #这里应该要新创建一个变量
                temp_temp_data = temp_data
                # self.his_data[temp_history_dic_index] = temp_temp_data
                self.his_data_arr.append(temp_temp_data)
                # temp_history_dic_index += 1

            temp_his_data.clear()

        temp_25_stock_arr = []
        for item in self.his_25_amount_data_arr:
            temp_25_stock_arr.append(item['symbol'])

        for temp_stock in self.context.subscription_stock_arr:
            if temp_stock not in temp_25_stock_arr:
                self.notin_25_stock_arr.append(temp_stock)

        #将所有数据添加到his_data中
        temp_history_dic_index = 0
        for i in range(2):
            if i == 0:
                test_yesterday_eob = str(yesterday_date) + " " + "09:25:00+08:00"
            else:
                test_yesterday_eob = str(yesterday_date) + " " + "09:26:00+08:00"

            #先将25min数据装入dic
            for his_25_val in self.his_25_amount_data_arr:
                self.his_data_dic[temp_history_dic_index] = {'symbol':his_25_val['symbol'], 'amount':his_25_val['last_amount'], 'eob':test_yesterday_eob}
                temp_history_dic_index += 1
            #将没有数据的标的，赋予0.0值装入dic
            for notin_his_25_val in self.notin_25_stock_arr:
                self.his_data_dic[temp_history_dic_index] = {'symbol':notin_his_25_val, 'amount':0.0, 'eob':test_yesterday_eob}
                temp_history_dic_index += 1

        for item in self.his_data_arr:
            temp_item = item
            self.his_data_dic[temp_history_dic_index] = temp_item
            temp_history_dic_index += 1

        print(f"25 stock arr length:{len(self.his_25_amount_data_arr)}")
        print(f"not in 25 stock arr length:{len(self.notin_25_stock_arr)}")
        print(f"his_data length::{len(self.his_data_dic)}")

    def load_ids(self, context):
        # 看股票代码就能分辨，上证股票是在上海交易所上市的股票，股票代码以600、601、603开头，科创板（在上海交易所上市）股票代码以688开头
        # 深市股票是在深市交易所上市的股票，股票代码以000、002、003开头，创业板（在深圳交易所上市）股票代码以300开头。
        #
        # 简化使用的话，就是6开头就都是上交所的，其他都是深交所（当然这种情况没有处理错误的存在）
        # SHSE(上交所), SZSE(深交所)

        # ！！！这里读取的配置文件，要根据策略改变
        file_obj = open(self.ids_path_a1, 'r')
        lines = file_obj.readlines()

        buy_flag = True
        for line in lines:
            should_add = True
            str_tmp = line.strip() # 去掉换行符
            original_id = str_tmp

            # 属于一个技巧性地读取，首先Buy在配置文件的上面，Sell在下面
            # 所以上面都是true，当读取到--------Sell标志行的时候，转为False，这样下面的都是False
            if (str_tmp.find('--------Sell') != -1):
                buy_flag = False
            first3 = str_tmp[:3]

            if (first3 == '600'):
                str_tmp = 'SHSE.' + str_tmp[:6]
            elif (first3 == '601'):
                str_tmp = 'SHSE.' + str_tmp[:6]
            elif (first3 == '603'):
                str_tmp = 'SHSE.' + str_tmp[:6]
            elif (first3 == '605'):
                str_tmp = 'SHSE.' + str_tmp[:6]
            elif (first3 == '688'):
                str_tmp = 'SHSE.' + str_tmp[:6]
            elif (first3 == '689'):
                str_tmp = 'SHSE.' + str_tmp[:6]
            elif (first3 == '000'):
                str_tmp = 'SZSE.' + str_tmp[:6]
            elif (first3 == '001'):
                str_tmp = 'SZSE.' + str_tmp[:6]
            elif (first3 == '002'):
                str_tmp = 'SZSE.' + str_tmp[:6]
            elif (first3 == '003'):
                str_tmp = 'SZSE.' + str_tmp[:6]
            elif (first3 == '300'):
                str_tmp = 'SZSE.' + str_tmp[:6]
            elif (first3 == '301'):
                str_tmp = 'SZSE.' + str_tmp[:6]
            elif (first3 == 'fsa'):
                should_add = False
                context.force_sell_all_flag = True
            elif (first3 == 'mv:'):
                should_add = False
                mv = float(str_tmp[3:]) if (str_tmp[3:] != '') else 0.0
                if -1 == mv: # 初始化的情况（应该只有每天第一次启动脚本的时候执行这里）
                    #context.calculate_total_market_value_flag = True
                    print(f"did not find valid market value, need re-calculate") #log
                else:
                    print(f"find valid total market value:{mv}")  #log
            else:
                should_add = False
                print(f'读取IDs配置错误：{str_tmp}')

            if buy_flag == False:
                print(f"init total ids : {len(context.subscription_stock_arr)}")
                print(f"init ids down=========================")
                break
            else:
                if should_add == True:
                    if str_tmp not in context.subscription_stock_arr:
                        context.subscription_stock_arr.append(str_tmp)


    def save_history_info(self):
        np.save(self.save_history_path, self.his_data_dic)

    def load_history_info(self):
        temp_history_dic = np.load(self.load_history_path, allow_pickle=True)
        temp_history_dic = dict(temp_history_dic.tolist())

        # for value in temp_history_dic.values():
        #     print(f"{value['symbol']}:{value['amount']}:{value['eob']}")

        print(f"load history success :{len(temp_history_dic)}")


# 策略中必须有init方法
def init(context):

    context.subscription_stock_arr = []

    get_history = DownloadHistoryC(context)
    get_history.download_history()
    get_history.save_history_info()
    get_history.load_history_info()

    pass


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
    run(strategy_id='7e863bef-3d91-11ef-bcc2-00ff2b50aff6',
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

