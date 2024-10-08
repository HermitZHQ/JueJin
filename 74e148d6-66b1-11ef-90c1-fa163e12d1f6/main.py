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
str_strategy = 'VDebug' # V--VDebug
str_load_history = 'AllHistoryInfo'
log_path = 'c:\\TradeLogs\\Trade' + str_strategy + '.txt'
ids_path_a1 = 'c:\\TradeLogs\\IDs-' + str_strategy + '-A1.txt'
ids_path_a2 = 'c:\\TradeLogs\\IDs-' + str_strategy + '-A2.txt'
pos_info_path = 'c:\\TradeLogs\\Pos-' + str_strategy + '.npy'
statistics_info_path = 'c:\\TradeLogs\\Sta-' + str_strategy + '.npy'
buy_info_path = 'c:\\TradeLogs\\Buy-' + str_strategy + '.npy'
mac_address_path = 'c:\\TradeLogs\\' + 'macAddress' + '.txt'

def TempOutputExcel():
    pass

class DataLimitToSend:
    def __init__(self):
        self.min_limit = 20000 # 1分钟实时数据超过这个界限,就send
        self.agility_limit = 800 # 灵活实时数据超过这个界限，就sned

class StorkInfo:
    def __init__(self):
        self.symbol = ""
        self.today_data = {} # 今天每分钟数据 key<min>, value<min_today_amount>
        self.history_data = {} # 昨日历史每分钟数据 key<min>, value<min_history_amount>
        self.agility_data = {} # 灵活时间数据，其中包括历史数据换算成的灵活时间数据和今日的灵活时间数据，key<agility_min>, value<AgilityDataInfo()>
        self.history_amount = 0
        self.current_amount = 0
        self.pre_close = 0.0 # 昨日关盘价
        self.current_price = 0.0 # 实时价格
        self.sec_name = "" # 标的中文名称
        self.record_agility_data = [] # 记录灵活时间达标的数据, []{agility_time, percent}

class AgilityDataInfo:
    def __init__(self):
        self.symbol = ""
        self.agility_time = ""
        self.history_amount = 0
        self.current_amount = 0

class TargetInfo:
    def __init__(self):
        self.name = ""
        self.hold_available = 0 # 可用持仓，一般只需要初始化一次，反复初始化会很卡
        self.price = 0
        self.first_record_flag = False
        self.pre_close = 0
        self.vwap = 0
        self.upper_limit = 0 # 涨停价
        self.lower_limit = 0
        self.suspended = False # 是否停牌
        self.sold_flag = False
        self.sold_price = 0 # 虚拟卖出时的记录价格，用于统计信息
        self.sold_mv = 0 # 虚拟卖出后锁定的市值
        self.fpr = -1 # 浮动盈亏缓存
        self.total_holding = 0 # 这里的总量并不从pos中取，而是从完成（部成）的order中记录，因为我发现完全用pos中的有时候数据更新不及时，比如部成的数量都已经显示有10000股了，且已经输出到日志中，但是紧接着马上取pos中的持仓，却还没有更新到该值，取出来可能是4，5000，虽然这个发生的几率很小，但是还是需要处理
        self.partial_holding = 0 # 记录部成的临时值
        self.fixed_buy_in_base_num = 0 # 强制买入所有目标下使用的变量，记录需要买入的base数量（手，最后需要乘100）
        self.pre_quick_buy_amount = 0 # 准备急速买入的额度

class BuyMode:
    def __init__(self):
        # 注意每个策略下面只能设定一种对应的买入模式（也就是只有一种可以激活到1）！！
        self.buy_all = 0 # 是否和策略B一样，直接从列表一次性全部买入，使用读出的配置数据就可以动态算出每只票的分配仓位
        self.buy_one = 1 # 买一只，并指定对应的价格
        self.buy_all_force = 0 # 一定要保证买入所有（对应数量非常大的买入，且有很多高价股，均分值无法覆盖高价股）

class OrderTypeBuy:
    def __init__(self):
        # 选择整体的订单交易模式，限价或者市价，只能激活一种！！
        self.Limit = 1
        self.Market = 0

class OrderTypeSell:
    def __init__(self):
        # 选择整体的订单交易模式，限价或者市价，只能激活一种！！
        self.Limit = 0
        self.Market = 1

class StrategyInfo:
    def __init__(self):
        # 指定策略对应的模式，策略A就对应A=1，一次只能激活一种策略！！
        self.A = 0
        self.AC = 0
        self.A1 = 0
        self.AA = 0
        self.B = 1
        self.B1 = 0
        self.BA = 0
        self.C = 0
        self.M = 0

        self.buy_mode = BuyMode()
        self.order_type_buy = OrderTypeBuy()
        self.order_type_sell = OrderTypeSell()

        self.slip_step = 5 # 滑点级别，1-5，要突破5的话，可以自己算？

class IsShowPrint:
    def __init__(self):
        self.is_show_tick_print = True



# 策略中必须有init方法
def init(context):
    context.LENGTH_FORMAT = 'I'
    context.chunk_size = 1024
    context.set_agility_time = 5 # 设置灵活分钟数，例如为5时，5分钟内的历史数据与实时5分钟内的数据
    context.operation_id_send = 0
    context.operation_id_recive = 0
    context.estimate_index = 0 # 灵活时间段下标，用于判断当前时间属于哪一段灵活时间，可用于estimate_dic中的key值
    context.symbol_str = ''
    context.delelte_ready_for_send = None
    context.datetime_noon_time_s = datetime.strptime('11:30:00', "%H:%M:%S").time()
    context.datetime_noon_time_e = datetime.strptime('13:00:00', "%H:%M:%S").time() 
    context.datetime_afternoon_time_s = datetime.strptime('15:00:00', "%H:%M:%S").time()
    context.datetime_morning_time_s = datetime.strptime('09:30:00', "%H:%M:%S").time()
    context.datetime_output_excel_time = datetime.strptime('10:30:00', "%H:%M:%S").time() # datetime.strptime('11:00:00', "%H:%M:%S").time()

    context.subscription_stock_arr = []
    context.mac_address_arr = []
    context.his_data = []
    context.his_data_for_today = []
    context.his_data_for_today_second = []
    context.his_25_amount_data = []
    context.his_25_today_amount_data = []
    context.refresh_select_stock_arr = [] # 发送在此集合中的标的信息，如果没达标则发送，达标就不管了
    context.top_stock_arr = [] # 置顶标的集合
    context.halfway_agility_data_for_send_arr = [] # 中途开启时或关盘后开启，用于发送此dic中的灵活时间达标数据, arr<{"symbol", "percent", "eob"}>

    context.symbol_arr = {}
    context.his_symbol_data_arr = set()
    context.his_data_dic = {}
    context.all_his_data_dic = {} # 所有标的历史数据，其中也包含未在列表中的标的，key--symbol, value--list(包含当日所有历史数据的list)
    context.all_his_data_with_min_dic = {} # 所有标的历史数据，只包含在列表的标的，key--symbol，value--dic(dic=key--min, value--min_data)(每分钟所对应的历史数据)
    context.all_cur_data_info_dic = {} # 所有标的，只包含在列表的标的，今日所有的实时数据，key--symbol，value--dic(dic=key--min, value--min_data)
    context.all_agility_data_info_dic = {} # 所有标的的灵活时间对比dic，key--symbol，value--dic(dic=key--agilite_time, value--AgilityDataInfo(CLASS))
    context.all_stock_info_dic = {} # 所有标的的相关信息 key<symbol_id>, value<StorkInfo()>
    context.his_today_data_dic = {}
    context.cur_data_dic = {}
    context.cur_data_second_dic = {}
    context.socket_dic = {}
    context.new_socket_dic = {}
    context.client_init_complete_dic = {}
    context.init_client_socket_dic = {}
    context.client_order = {}
    context.estimate_dic = {} # 灵活时间段中的每一时段，key--min, value--agilite_end_time(当前时间段，所对应的结束时间，方便后续其他dic直接调用),此dic为多个key指向同一个value

    context.delete_client_socket_arr = []
    context.delete_temp_adress_arr = []
    context.ready_for_send = []
    context.ready_second_for_send = []
    context.init_complete_client = {}
    context.ids = {}
    context.ids_info_dict = {} # 记录一些tick中的标的数据，方便在其他地方的时候可以使用，数据格式为：key：标的字符串  value：是TargetInfo类型
    context.client_order = {} # 记录正在进行中的订单，防止重复买入和卖出
    context.pre_quick_buy_dict = {} # 在socket收到消息后，不要马上买入，因为价格并不准确，需要在tick激活时买入
    context.pre_quick_sell_dict = {} # 同上，用于卖出    
    context.strategy_info = StrategyInfo() # 保存策略信息以及买入方式到全局变量中
    
    if context.strategy_info.order_type_buy.Limit == 1:
        context.order_type_buy = OrderType_Limit
    elif context.strategy_info.order_type_buy.Market == 1:
        context.order_type_buy = OrderType_Market

    if context.strategy_info.order_type_sell.Limit == 1:
        context.order_type_sell = OrderType_Limit
    elif context.strategy_info.order_type_sell.Market == 1:
        context.order_type_sell = OrderType_Market
    
    context.is_subscribe = False
    context.is_can_show_print = False
    context.is_output_excel = False
    context.iniclient_socket_lock = threading.Lock()

    context.temp_clear_curdata_index = 0
    context.temp_matching_dic = {}
    context.temp_test_index = 0
    context.temp_judge_second_data_dic = {}

    context.test_second_data_time = ''
    context.test_next_second_data_time = ''

    context.is_show_print = IsShowPrint()
    context.data_limit_to_send = DataLimitToSend()

    #------
    subscribe_method(context)
    load_history_from_file(context)
    load_today_history_from_file(context)


def get_todat_date():
        # 获取当前日期
        today = datetime.now().date()

        # 获取前一天的日期  - timedelta(days=1)
        previous_day = today

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

#__tick__计算百分比
def calculate_percent_mathod(history_data, current_data):

    if history_data != 0:
        calculate_percent = round(((float(current_data) - float(history_data))/float(history_data)) * 100, 2)
    else:
        calculate_percent = 0 #'N'

    return calculate_percent

def comparison_record_data(context):
    for symbol_val in  context.all_agility_data_info_dic.values():
        for s_v in symbol_val.values():
            # print(f"{s_v.symbol}::{s_v.agility_time}:{s_v.history_amount}:{s_v.current_amount}")
            temp_agility_percent = calculate_percent_mathod(s_v.history_amount, s_v.current_amount)
            if int(temp_agility_percent) >= context.data_limit_to_send.agility_limit:
                # 将达标的数据添加进本标的信息中
                context.all_stock_info_dic[s_v.symbol].record_agility_data.append({"agility_time":s_v.agility_time, "percent":temp_agility_percent})


def record_data_in_excel(context):
    wb = Workbook()  
    ws = wb.active  
    ws.title = "S1" 

    data = []
    first_row = []
    data.append(first_row)
    data[0].append("代码")
    data[0].append("名称")
    last_record_count = 0
    
    for symbol_val in context.all_stock_info_dic.values():
    
        if len(symbol_val.record_agility_data) != 0:

            temp_data_frist_row = []
            temp_data_second_row = []

            # print(f"{symbol_val.symbol}|{symbol_val.sec_name}|{len(symbol_val.record_agility_data)}")

            temp_data_frist_row.append(symbol_val.symbol)
            temp_data_frist_row.append(symbol_val.sec_name)
                
            for recor_data_info in symbol_val.record_agility_data:
                temp_data_frist_row.append(recor_data_info["percent"])

            data.append(temp_data_frist_row)

            if last_record_count == 0:
                last_record_count = len(symbol_val.record_agility_data)
                for i in range(last_record_count):
                    data[0].append(i + 1)
            else:
                if len(symbol_val.record_agility_data) > last_record_count:
                    temp_count = len(symbol_val.record_agility_data) - last_record_count
                    for i in range(temp_count):
                        data[0].append(last_record_count + i + 1)
                    last_record_count = len(symbol_val.record_agility_data)

    print(f"begin output excel, data length:{len(data)}")

    # 遍历数据，并将每行添加到工作表中  
    for row in data:  
        ws.append(row)

    file_path = 'E:\\DataForExcel\\RecordStockCount' + str(get_todat_date()) + '.xlsx'
    wb.save(file_path)

    context.is_output_excel = True


def get_previous_or_friday_date():
    # 获取当前日期
    today = datetime.now().date()

    # 获取前一天的日期
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


# 分解时间，得到分钟数, 返回的是数组,0-hour, 1-minute, 2-second
def resolve_time_minute(date_time):
    temp_current_time_arr = str(date_time).split(" ")
    temp_c_hour_arr = temp_current_time_arr[1].split("+")
    temp_int_c_hour_arr = temp_c_hour_arr[0].split(".")
    temp_h_m_s = temp_int_c_hour_arr[0].split(":")

    # now_time_h = temp_h_m_s[0]
    # now_time_m = temp_h_m_s[1]
    # now_time_s = temp_h_m_s[2]

    # 这里直接返回一个数组
    return temp_h_m_s


# 初始化灵活时间dic，并补全没有的分钟数
def init_agilit_dictionary(context, symbol_id):

    is_replenish = False
    temp_his_begin_time = ""
    temp_time_index = 0
    temp_run_count = 0

    agility_amount = 0.0
    temp_agility_amount = 0.0

    is_estimate_init = False
    temp_estimate_arr = []

    for i in range(2):

        if temp_run_count == 0:
            temp_his_begin_time = "09:16:00"    # "09:31:00"
        elif temp_run_count == 1:
            temp_his_begin_time = "13:01:00"
            is_replenish = False

        # 注意！！！这是while循环
        while is_replenish == False and temp_run_count <= 1:

            if temp_his_begin_time in context.all_his_data_with_min_dic[symbol_id].keys():
                temp_agility_amount = context.all_his_data_with_min_dic[symbol_id][temp_his_begin_time]
            else:
                temp_agility_amount = 0.0
                # 这里如果历史数据中没有此分钟的数据就补全
                context.all_his_data_with_min_dic[symbol_id][temp_his_begin_time] = 0.0

            temp_hh_mm_ss = temp_his_begin_time.split(":")
            
            temp_hour = temp_hh_mm_ss[0]
            temp_min = temp_hh_mm_ss[1]

            temp_next_min = int(temp_min) + 1
            # 这里需要判断当前分钟是否为个位数，如果是就会与key匹配不上，例如10:9:00-对应应该是10:09:00
            if len(str(temp_next_min)) == 1:
                temp_min = '0' + str(temp_next_min)
            else:
                temp_min = str(temp_next_min)
            # 这里需要判断当前分钟是否满了60，如果满了60，小时就需要+1，并且将当前分钟数重置为00
            if temp_min == '60':
                temp_hour = str(int(temp_hour) + 1)
                temp_min = '00'

            temp_time_index += 1
            agility_amount += temp_agility_amount
            temp_estimate_arr.append(temp_his_begin_time)
            # print(f"temp_his_begin_time|{temp_his_begin_time}--temp_agility_amount|{temp_agility_amount}")

            # 判断是否达到所设置的灵活时间，达到就进行赋值，否则进行相加
            if temp_time_index == context.set_agility_time:

                temp_agilityinfo = AgilityDataInfo()
                temp_agilityinfo.symbol = symbol_id
                temp_agilityinfo.agility_time = temp_his_begin_time # 这里的begin_time指的是此灵活时间段的结束时间
                temp_agilityinfo.current_amount = 0.0
                temp_agilityinfo.history_amount = agility_amount

                # 初始化agility_amount,并赋值
                context.all_agility_data_info_dic[symbol_id][temp_his_begin_time] = temp_agilityinfo

                temp_time_index = 0
                agility_amount = 0

                # 初始化灵活时间，每分钟所对应的灵活时间段，方便后续其他dic直接调用，不用花费时间去对比
                if is_estimate_init == False:
                    for estimate_time in temp_estimate_arr:
                        context.estimate_dic[estimate_time] = temp_his_begin_time
                    temp_estimate_arr.clear()

                # print(f"{temp_agilityinfo.symbol}|{temp_agilityinfo.agility_time}|{temp_agilityinfo.history_amount}")
                
            # 重新拼接时间
            temp_his_begin_time = temp_hour + ":" + temp_min + ":" + "00"
            # 当时间为11:31:00，代表上午时间段结束，退出while循坏
            if temp_his_begin_time == "11:31:00" or temp_his_begin_time == "15:01:00":
                is_replenish = True
                temp_run_count += 1

    # 第一次跑完for循环，代表estimate_dic初始化完成，后面就不用再初始化了
    is_estimate_init = True
    # 初始化stock info dic的agility_data
    context.all_stock_info_dic[symbol_id].agility_data = context.all_agility_data_info_dic[symbol_id]

    # for key, value in context.estimate_dic.items():
    #     print(f"{key}-{value}")

    # for p_value in context.all_agility_data_info_dic.values():
    #     for c_key, c_val in p_value.items():
    #         print(f"{c_key}|{c_val.agility_time}|{c_val.current_amount}|{c_val.history_amount}")


#从文件中获取历史数据，其中包括了集合进价
def load_history_from_file(context):
    yesterday_date = get_previous_or_friday_date()
    load_history_path = 'e:\\HistoryFiles\\' + str_load_history + " " + str(yesterday_date) + '.npy' #加上日期，方便后面查找调用

    context.his_data = np.load(load_history_path, allow_pickle=True)
    context.his_data = dict(context.his_data.tolist())

    # for value in context.his_data.values():
    #     print(f"{value['symbol']}:{value['amount']}:{value['eob']}")

    #这里需要改下，改为dic类型，一个symbol对应其相应历史数据list
    #这样为了后续方便遍历已订阅的历史数据并发送给客户端，而不是发送全部历史数据(包含位订阅的)
    #key--symbol, value--list   context.all_his_data_dic, 新版本，这里后面可能会用到，当特别关注的标的，就会需要发送全天历史数据! 
    # 注意！！后面可能不会发送全天数据，所有标的历史数据可能会拷贝到客户端，客户端也会直接从文件中直接读取历史数据！！   
    for val_data in context.his_data.values():
        if val_data['symbol'] not in context.all_his_data_dic.keys():
            temp_list = []
            context.all_his_data_dic[val_data['symbol']] = temp_list

    for value in context.his_data.values():
        context.all_his_data_dic[value['symbol']].append(value)

    #新版本，因为要在服务器上进行数据运算,将历史数据都添加到dic中，dic类型, 一个symbol对应一个dic
    #key--symbol, value--dic(dic::key--time, value--data)
    for symbol_id in context.subscription_stock_arr:

        temp_min_dic = {}
        context.all_his_data_with_min_dic[symbol_id] = temp_min_dic
        # 初始化所有标的相关信息的dic
        context.all_stock_info_dic[symbol_id].history_data = context.all_his_data_with_min_dic[symbol_id]

        if symbol_id in context.all_his_data_dic.keys():
            for min_data in context.all_his_data_dic[symbol_id]:
                amount = min_data['amount']
                eob = min_data['eob']

                temp_hh_mm_ss = resolve_time_minute(eob)
                temp_data_time = temp_hh_mm_ss[0] + ":" + temp_hh_mm_ss[1] + ":" + temp_hh_mm_ss[2]

                context.all_his_data_with_min_dic[symbol_id][temp_data_time] = amount

                # print(f"{symbol_id}|{amount}|{temp_data_time}")

        # 在这补全09:15:00-09:30:00的数据，注意！09:25:00，09:26:00不需要补全
        # 或者！！直接从下载历史数据工具补全

        # 这里需要初始化下，当日所有标的实时数据dic
        temp_dic = {}
        context.all_cur_data_info_dic[symbol_id] = temp_dic
        context.all_stock_info_dic[symbol_id].today_data = context.all_cur_data_info_dic[symbol_id]

        # 这里初始化，灵活时间的数据，时间从开始一直初始化到结束 09:16-15:00
        # 注意！！这里需要一个写一个方法，来判断实时数据中，当前分钟数，是属于哪一段灵活时间
        # 这里在context中添加一个dic以及一个index，来快速判断当前时间是属于哪一段灵活时间，避免后续大量实时数据来的时候每一次都需要判断  estimate_index - estimate_dic
        temp_agility_dic = {}
        context.all_agility_data_info_dic[symbol_id] = temp_agility_dic
        # 这错了，没有today_agility_data这个属性！！后面来改
        context.all_stock_info_dic[symbol_id].today_agility_data = context.all_agility_data_info_dic[symbol_id]

        init_agilit_dictionary(context, symbol_id)


    print(f"load history success :{len(context.his_data)}")


def load_today_history_from_file(context):
    yesterday_date = get_previous_or_friday_date()
    load_history_path = 'e:\\HistoryFiles\\' + str_load_history + " " + str(yesterday_date) + '.npy' #加上日期，方便后面查找调用

    context.his_data_for_today = np.load(load_history_path, allow_pickle=True)
    context.his_data_for_today = dict(context.his_data_for_today.tolist())

    context.all_his_today_data_dic = {}

    for val_data in context.his_data_for_today.values():
        if val_data['symbol'] not in context.all_his_today_data_dic.keys():
            temp_list = []
            context.all_his_today_data_dic[val_data['symbol']] = temp_list

    for value in context.his_data_for_today.values():
        context.all_his_today_data_dic[value['symbol']].append(value)

    for symbol_id in context.subscription_stock_arr:
        if symbol_id in context.all_his_today_data_dic.keys():
            for min_data in context.all_his_data_dic[symbol_id]:
                amount = min_data['amount']
                eob = min_data['eob']

                temp_hh_mm_ss = resolve_time_minute(eob)
                temp_data_time = temp_hh_mm_ss[0] + ":" + temp_hh_mm_ss[1] + ":" + temp_hh_mm_ss[2]

                agility_time = context.estimate_dic[temp_data_time]
                context.all_agility_data_info_dic[min_data['symbol']][agility_time].current_amount += amount


    print(f"load today history success :{len(context.his_data_for_today)}")


def subscribe_method(context):
    load_ids(context)

    temp_ids_str = ''
    temp_index = 0
    for item in context.subscription_stock_arr:
            if temp_index == 0:
                temp_ids_str = item
            else:
                temp_ids_str = temp_ids_str + ',' + item
            temp_index += 1

    context.symbol_str = temp_ids_str

    # subscribe(symbols=temp_ids_str, frequency='tick', count=1, unsubscribe_previous=False, wait_group=True)

    #这里尝试同时订阅on_bar,用来修补客户端中途启动时，所在那1-2分钟内掉的数据
    # subscribe(symbols=temp_ids_str, frequency='60s', count=1, unsubscribe_previous=False, wait_group=True)

    info = get_instruments(symbols = context.symbol_str, skip_suspended = False, skip_st = False, df = True)

    # current_data = current(symbols = context.symbol_str, fields='symbol, price')

    # for i in range(len(current_data)):
    #     print(f"{current_data[i]["symbol"]}|{current_data[i]["price"]}")

    #这里需要加一个过滤停牌的功能
    # print(f"{info}")

    for i in range(len(info)):
        print(f"{info.symbol[i]}|{info.sec_name[i]}|{info.is_suspended[i]}|{info.pre_close[i]}")
        context.temp_matching_dic[info.symbol[i]] = info.sec_name[i]
        # 初始化所有标的，相关信息，部分数据在其他地方初始化
        context.all_stock_info_dic[info.symbol[i]] = StorkInfo()
        context.all_stock_info_dic[info.symbol[i]].symbol = info.symbol[i]
        context.all_stock_info_dic[info.symbol[i]].sec_name = info.sec_name[i]
        context.all_stock_info_dic[info.symbol[i]].pre_close = info.pre_close[i]

    print(f"ids count:{len(info)}")


def load_ids(context):
    # 看股票代码就能分辨，上证股票是在上海交易所上市的股票，股票代码以600、601、603开头，科创板（在上海交易所上市）股票代码以688开头
    # 深市股票是在深市交易所上市的股票，股票代码以000、002、003开头，创业板（在深圳交易所上市）股票代码以300开头。
    #
    # 简化使用的话，就是6开头就都是上交所的，其他都是深交所（当然这种情况没有处理错误的存在）
    # SHSE(上交所), SZSE(深交所)

    # ！！！这里读取的配置文件，要根据策略改变
    file_obj = open(ids_path_a1, 'r')
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
                log(f"did not find valid market value, need re-calculate")
            else:
                log(f"find valid total market value:{mv}")
        else:
            should_add = False
            print(f'读取IDs配置错误：{str_tmp}')

        if buy_flag == False:
            # for item in context.subscription_stock_arr:
            #     print(f"{item}")
            print(f"init total ids : {len(context.subscription_stock_arr)}")
            print(f"init ids down=========================")
            break
        else:
            if should_add == True and context.is_subscribe == False:
                if str_tmp not in context.subscription_stock_arr:
                    context.subscription_stock_arr.append(str_tmp)
                    context.temp_judge_second_data_dic[str_tmp] = False
                    context.ids_info_dict[str_tmp] = TargetInfo()


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
    run(strategy_id='74e148d6-66b1-11ef-90c1-fa163e12d1f6',
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

