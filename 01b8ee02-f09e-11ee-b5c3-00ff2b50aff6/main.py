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

global_i = 0
str_strategy = 'VDebug'
log_path = 'c:\\TradeLogs\\Trade' + str_strategy + '.txt'
ids_path_a1 = 'c:\\TradeLogs\\IDs-' + str_strategy + '-A1.txt'
ids_path_a2 = 'c:\\TradeLogs\\IDs-' + str_strategy + '-A2.txt'
pos_info_path = 'c:\\TradeLogs\\Pos-' + str_strategy + '.npy'
statistics_info_path = 'c:\\TradeLogs\\Sta-' + str_strategy + '.npy'
buy_info_path = 'c:\\TradeLogs\\Buy-' + str_strategy + '.npy'
mac_address_path = 'c:\\TradeLogs\\' + 'macAddress' + '.txt'

SECTION_HISTORY_STOCK_COUNT = 50
HISTORY_DATA_SEND_COUNT = 50
HISTORY_TODAY_DATA_SEND_COUNT = 50

OP_ID_S2C_STOCK_NAME_SEND = 100
OP_ID_S2C_HISTORY_DATA_SEND = 101
OP_ID_S2C_REAL_TIME_DATA_SEND = 102
OP_ID_S2C_HISTORY_TODAY_DATA_SEND = 104

OP_ID_C2S_QUICK_BUY = 120
OP_ID_C2S_QUICK_SELL = 121

#0v0
#=-=
#1234

def VolumeMonitorDebug():
    pass

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

# 策略中必须有init方法
def init(context):
    context.LENGTH_FORMAT = 'I'
    context.chunk_size = 1024
    context.operation_id_send = 0
    context.operation_id_recive = 0
    context.symbol_str = ''
    context.delelte_ready_for_send = None

    context.subscription_stock_arr = []
    context.mac_address_arr = []
    context.his_data = []
    context.his_data_for_today = []
    context.his_data_for_today_second = []
    context.his_25_amount_data = []
    context.his_25_today_amount_data = []

    context.symbol_arr = {}
    context.his_symbol_data_arr = set()
    context.his_data_dic = {}
    context.his_today_data_dic = {}
    context.cur_data_dic = {}
    context.cur_data_second_dic = {}
    context.socket_dic = {}
    context.new_socket_dic = {}
    context.client_init_complete_dic = {}
    context.init_client_socket_dic = {}

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
    context.is_subscribe = False
    context.iniclient_socket_lock = threading.Lock()

    context.temp_clear_curdata_index = 0
    context.temp_matching_dic = {}
    context.temp_test_index = 0
    context.temp_judge_second_data_dic = {}

    context.test_second_data_time = ''
    context.test_next_second_data_time = ''

    #订阅上证指数用于在on_tick里刷新    1
    subscribe(symbols='SHSE.000001', frequency='tick', count=1, unsubscribe_previous=False)

    #开启服务器就订阅, 等会试
    # subscribe_method(context)

    #current(symbols='SZSE.300130', fields='open')

    #读取mac地址    2
    load_mac_address(context)

    # 线程Server 正式服12345, 调试服12346   3
    # 这个是新版新版新版新版新版新版
    main_server_thread = MainServerTreadC("0.0.0.0", 12346, context)
    main_server_thread.start()

    # 关盘后，模拟on_bar用
    init_client_one_time(context)
    
    #测试获得当日历史数据
    # load_ids(context)
    # test_get_data(context)
    # get_history_data_in_today(context)


#模拟线程，关盘后调试用
def simulation_on_bar(context):

    test_count_index = 0

    test_time_d = '2024-07-05 '
    test_time_h = '10'
    test_time_m = '00'
    test_time_s = '00.00013+08:00'

    test_time_time = test_time_d + test_time_h + ':' + test_time_m + ':' + test_time_s
    #'2024-5-15 14:20:00+08:00'

    while True:
        time.sleep(3)
        for sy in context.subscription_stock_arr:
            context.cur_data_dic.clear()
            context.cur_data_dic[sy] = PackSecondDataFrame(sy, '10000', test_time_time).to_dict()

            #if context.socket_dic:
            #    for k,v in context.socket_dic.items():
         
            #        if context.client_init_complete_dic[v] == True:
                    
            #            send_message_second_method(v, context)

            if context.socket_dic:
                for k,v in context.socket_dic.items():
         
                    if context.client_init_complete_dic[v] == True:

                        send_message_second_method(v, context)

                        if len(context.ready_for_send) > 0:
                            for ready_data in context.ready_for_send:
                                context.cur_data_dic.clear()
                                context.cur_data_dic[ready_data['symbol']] = ready_data
                                send_message_second_method(v, context)

                            context.ready_for_send.clear()

                    else:
                        for data_key, data_value in context.cur_data_dic.items():
                            temp_ready_for_send_data = data_value
                            context.ready_for_send.append(temp_ready_for_send_data)

                        print(f"ready_for_send length:{len(context.ready_for_send)}")
        
        test_count_index += 1
        if test_count_index >= 5:#5
            test_count_index = 0
            temp_new_min = int(test_time_m) + 1

            test_time_m = temp_new_min

            if len(str(temp_new_min)) == 1:
                temp_test_time_m = '0' + str(temp_new_min)
            else:
                temp_test_time_m = str(temp_new_min)

            if temp_new_min == 60:
                temp_get_now_hour = int(test_time_h) + 1
                temp_new_min = 0 

                test_time_m = '00'

                test_time_time = test_time_d + str(temp_get_now_hour) + ":" + "00" + ":" + test_time_s
                
                test_time_h = str(temp_get_now_hour)
            else:
                test_time_time = test_time_d + test_time_h + ':' + temp_test_time_m + ':' + test_time_s


            # test_time_time = test_time_d + test_time_h + ':' + temp_test_time_m + ':' + test_time_s

            test_count_index = 0
        
            #time.sleep(0.01)

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

    subscribe(symbols=temp_ids_str, frequency='tick', count=1, unsubscribe_previous=False, wait_group=True)

    #这里尝试同时订阅on_bar,用来修补客户端中途启动时，所在那1-2分钟内掉的数据
    # subscribe(symbols=temp_ids_str, frequency='60s', count=1, unsubscribe_previous=False, wait_group=True)

    info = get_instruments(symbols = context.symbol_str, skip_suspended = False, skip_st = False, df = True)

    for i in range(len(info)):
        print(f"{info.symbol[i]}|{info.sec_name[i]}")
        context.temp_matching_dic[info.symbol[i]] = info.sec_name[i]

    print(f"ids count:{len(info)}")
    

#初始化客户端，一次性传输数据，
def init_client_one_time(context):

    if context.is_subscribe == False:

        subscribe_method(context)

        test_get_data(context)

        context.is_subscribe = True

    if_complete = 0

    while if_complete == 0:

        if context.init_client_socket_dic:

                client_socket = ""

                for val in context.init_client_socket_dic.values():

                    if val.is_initing == False and val.is_init == False:

                        val.is_initing = True

                        client_socket = val.client_socket

                        t = time.time()
                        print(f"ready for init client")

                        #这里需要判断客户端连接的此刻时间之前，是否有当日历史数据，如果有，需要全部传过去包括
                        #上面on_tick里，需要改成，只要客户端连接，就发送数据，不需要等待客户端发来完成初始化在发，以免漏掉数据
                        #已改成客户端连接上拉，服务器将数据临时存入，当客户端初始化完成后，再一同发送
                        get_history_data_in_today(context)

                        #分段传送9：25集合进价里的成交金额
                        now_data = context.now
                        print(f"{now_data}")

                        #OP_ID_S2C_STOCK_NAME_SEND
                        #这里先将名字传输过去
                        #===================================
                        #1-4 OP_ID_S2C_STOCK_NAME_SEND
                        ready_send_name_bytes = OP_ID_S2C_STOCK_NAME_SEND.to_bytes(4, byteorder="big")
                        #2-4 int32 标的名称总数量
                        stock_name_count = len(context.temp_matching_dic)
                        ready_send_name_bytes += stock_name_count.to_bytes(4, byteorder="big")

                        client_socket.sendall(ready_send_name_bytes)

                        for key, valume in context.temp_matching_dic.items():

                            #这里报错，暂时不太清，将这里改成字符串发送

                            # temp_symbol_letter = 0
                            # temp_symbol_num = 0

                            # #3-4 int32
                            # temp_symbol_arr = key.split(".")
                            # temp_symbol_letter = translate_letter_to_int(temp_symbol_arr[0])
                            # symbol_letter_bytes = temp_symbol_letter.to_bytes(4, byteorder='big')

                            # #4-4 int32
                            # temp_symbol_num = int(temp_symbol_arr[1])
                            # symbol_num_bytes = temp_symbol_num.to_bytes(4, byteorder='big')

                            # #6-? 中文名字byte
                            # name_bytes = valume.encode('utf-8')
                            # #5-4 int16 中文名字byte长度并转化为byte
                            # name_length = len(name_bytes)
                            # name_length_bytes = np.int16(name_length)

                            # ready_send_name_bytes = symbol_letter_bytes + symbol_num_bytes + name_length_bytes + name_bytes

                            # client_socket.sendall(ready_send_name_bytes)

                            #============================================================

                            ready_send_name_str = key + "+" + valume
                            send_data = ready_send_name_str.encode('utf-8')
                            send_length = len(send_data).to_bytes(4, byteorder='big')
                            client_socket.sendall(send_length)
                            print(f"{ready_send_name_str}")
                            client_socket.sendall(send_data)


                        # return
                        #===================================

                        yesterday_date = get_previous_or_friday_date()
                        temp_yesterday_eob = str(yesterday_date) + " " + "09:26:00+08:00"
                        #这里将头天的25分钟数据改为26分钟，是为了方便在客户端里的update_label_for_single中方便拿取历史记录
                        #当天的25分钟，不需要改为26分钟,在初始化当天历史时，需要改，如果不需要，则是25分钟
                        #这里直接将25分钟数据存入25分钟以及26分钟，方便客户端判断，暂时这样吧   '2024-06-07'
                        temp_num = 0
                        for i in range(2):
                            if i == 0:
                                test_yesterday_eob = str(yesterday_date) + " " + "09:25:00+08:00"
                            else:
                                test_yesterday_eob = str(yesterday_date) + " " + "09:26:00+08:00"

                            #先将25min数据装入dic
                            for his_25_val in context.his_25_amount_data:
                                context.his_data_dic[str({temp_num})] = PackHistoryDataFrame(his_25_val['symbol'], his_25_val['last_amount'], test_yesterday_eob, context.temp_matching_dic[his_25_val['symbol']]).to_dict()
                                temp_num += 1
                            #将没有数据的标的，赋予0.0值装入dic
                            for notin_his_25_val in context.notin_25_stock_arr:
                                context.his_data_dic[str({temp_num})] = PackHistoryDataFrame(notin_his_25_val, 0.0, test_yesterday_eob, context.temp_matching_dic[notin_his_25_val]).to_dict()
                                temp_num += 1

                        #打包历史数据对象,装入dic
                        for his_val in context.his_data:
                            context.his_data_dic[str({temp_num})] = PackHistoryDataFrame(his_val['symbol'], his_val['amount'], str(his_val['eob']), context.temp_matching_dic[his_val['symbol']]).to_dict()
                            temp_num += 1

                        #从这里开始改为二进制传输==============
                        # his_data_dic_json = json.dumps(context.his_data_dic)
                        # hddj_len = len(his_data_dic_json.encode('utf-8'))
                        # print(f"hddj_len:{hddj_len}")

                        # #耗时测试
                        # print(f"ReciveClientThreadC----总耗时为01:{time.time()-t:4f}s")

                        # #这里先传包头，然后传数据长度，最后传数据
                        # context.operation_id_send = 101
                        # operation_id_byte = context.operation_id_send.to_bytes(4, byteorder='big')
                        # client_socket.sendall(operation_id_byte)

                        # hddj_len_byte = hddj_len.to_bytes(4, byteorder='big')
                        # client_socket.sendall(hddj_len_byte)

                        #改为分段传输=========================先注释掉!
                        # off_set = 0

                        # while off_set < hddj_len:

                        #     chunk = his_data_dic_json[off_set:off_set + context.chunk_size]

                        #     client_socket.sendall(chunk.encode())

                        #     off_set += context.chunk_size
                        #=====================================

                        #这里接着改，尝试改为二进制传输==========
                        #包头+4，一次传输数量+4,(4+4+4+4+4)+(4+4+4+4+4)+.......(*传输数量)
                        #可以用for循环来拼接

                        #1-4 int32 包头
                        #OP_ID_S2C_HISTORY_DATA_SEND
                        
                        #2-4 int32 历史数据数量总数
                        history_data_count = len(context.his_data_dic)
                        history_data_count_bytes = history_data_count.to_bytes(4, byteorder="big")

                        ready_send_data_bytes = OP_ID_S2C_HISTORY_DATA_SEND.to_bytes(4, byteorder="big") + history_data_count_bytes

                        #先发送包头+数据总数
                        client_socket.sendall(ready_send_data_bytes)

                        arrive_index_for_send = 0
                        residue_data_count = history_data_count
                        #这里要判断一下，当dic中数据总数小于HISTORY_DATA_SEND_COUNT时，这里又可能用不上，但还是加上吧
                        if history_data_count < HISTORY_DATA_SEND_COUNT:
                            temp_send_count = history_data_count
                        else:
                            temp_send_count = HISTORY_DATA_SEND_COUNT
                        ready_send_data_bytes = temp_send_count.to_bytes(4, byteorder="big")
                        #拼接待发送的数据，byte类型
                        for valume in context.his_data_dic.values():
                            history_data_bytes = translate_send_data_to_bytes(context, valume['symbol'], valume['amount'], valume['eob'])
                            ready_send_data_bytes += history_data_bytes

                            arrive_index_for_send += 1
                            #达到发送的数量时，发送
                            if arrive_index_for_send == temp_send_count:
                                client_socket.sendall(ready_send_data_bytes)
                                residue_data_count -= arrive_index_for_send
                                arrive_index_for_send = 0

                                if residue_data_count > HISTORY_DATA_SEND_COUNT:
                                    temp_send_count = HISTORY_DATA_SEND_COUNT
                                else:
                                    temp_send_count = residue_data_count

                                ready_send_data_bytes = temp_send_count.to_bytes(4, byteorder="big")


                        #=====================================

                        # return

                        #这里需要判断客户端连接的此刻时间之前，是否有当日历史数据，如果有，需要全部传过去包括
                        get_now_time_arr = str(now_data).split("+")
                        get_now_time_arr_1 = get_now_time_arr[0].split(" ")
                        get_now_day = get_now_time_arr_1[0]
                        get_now_time_arr_2 = get_now_time_arr_1[1].split(":")

                        get_now_hour = get_now_time_arr_2[0]
                        get_now_min = get_now_time_arr_2[1]
                        get_now_second = get_now_time_arr_2[2]
                        temp_second_arr = get_now_second.split(".")
                        get_now_second_without_dot = temp_second_arr[0]

                        temp_temp_translate_time = get_now_hour + ":" + get_now_min + ":" + get_now_second_without_dot
                        temp_translate_time = datetime.strptime(temp_temp_translate_time, "%H:%M:%S").time()
                        now = datetime.now()  
                        combined = datetime.combine(now.date(), temp_translate_time)
                        one_minute_later = combined + timedelta(minutes=1) 
                        second_time_eob = str(get_now_time_arr_1[0]) + ' ' + one_minute_later.strftime("%H:%M:%S") + '+08:00'

                        temp_eob = get_now_day + " " + "09:25:00+08:00"
                        test_temp_eob = '2024-06-07' + " " + "09:30:00+08:00"

                        temp_num = 0
                        #将今天的25min数据装入dic
                        for his_today_25_val in context.his_25_today_amount_data:
                            #str(his_today_val['eob'])
                            context.his_today_data_dic[str({temp_num})] = PackHistoryDataFrame(his_today_25_val['symbol'], his_today_25_val['last_amount'], temp_eob, 'his_today_data').to_dict()
                            temp_num += 1
                        #将没有数据的标的，赋予0.0值
                        for notin_today_25_val in context.notin_25_today_stock_arr:
                            context.his_today_data_dic[str({temp_num})] = PackHistoryDataFrame(notin_today_25_val, 0.0, temp_eob, 'his_today_data').to_dict()
                            temp_num += 1
                        #打包今日此时段之前的历史数据
                        for his_today_val in context.his_data_for_today:
                            context.his_today_data_dic[str({temp_num})] = PackHistoryDataFrame(his_today_val['symbol'], his_today_val['amount'], str(his_today_val['eob']), 'his_today_data').to_dict()
                            temp_num += 1
                        #将当前分钟内的数据打包进dic里
                        #这里时间要需要+1分钟,等待删除此注释代码
                        # for key, value in context.temp_total_second_data.items():
                        #     # context.his_today_data_dic[str({temp_num})] = PackHistoryDataFrame(key, value, second_time_eob, 'his_today_data').to_dict()
                        #     context.ready_second_for_send.append(PackHistoryDataFrame(key, value, second_time_eob, 'his_today_data').to_dict())
                        #     temp_num += 1

                        #将今日历史数据改为二进制传输   HISTORY_TODAY_DATA_SEND_COUNT

                        # his_today_data_dic_json = json.dumps(context.his_today_data_dic)
                        # htddj_len = len(his_today_data_dic_json.encode('utf-8'))
                        # print(f"htddj_len:{htddj_len}")

                        # context.operation_id_send = 104
                        # operation_id_byte = context.operation_id_send.to_bytes(4, byteorder='big')
                        # client_socket.sendall(operation_id_byte)

                        # htddj_len_byte = htddj_len.to_bytes(4, byteorder='big')
                        # client_socket.sendall(htddj_len_byte)

                        #改为分段传输=========================
                        # off_set = 0

                        # while off_set < htddj_len:

                        #     chunk = his_today_data_dic_json[off_set:off_set + context.chunk_size]

                        #     client_socket.sendall(chunk.encode())

                        #     off_set += context.chunk_size
                        #=====================================

                        #这里接着改，尝试改为二进制传输==========

                        #1-4 int32 包头
                        #OP_ID_S2C_HISTORY_TODAY_DATA_SEND
                        
                        #2-4 int32 历史数据数量总数
                        history_today_data_count = len(context.his_today_data_dic)
                        history_today_data_count_bytes = history_today_data_count.to_bytes(4, byteorder="big")

                        ready_send_today_data_bytes = OP_ID_S2C_HISTORY_TODAY_DATA_SEND.to_bytes(4, byteorder="big") + history_today_data_count_bytes

                        #先发送包头+数据总数
                        client_socket.sendall(ready_send_today_data_bytes)

                        arrive_index_for_send = 0
                        residue_data_count = history_today_data_count
                        #这里要判断一下，当dic中数据总数小于HISTORY_TODAY_DATA_SEND_COUNT时，这里又可能用不上，但还是加上吧
                        if history_today_data_count < HISTORY_TODAY_DATA_SEND_COUNT:
                            temp_send_count = history_today_data_count
                        else:
                            temp_send_count = HISTORY_TODAY_DATA_SEND_COUNT
                        ready_send_today_data_bytes = temp_send_count.to_bytes(4, byteorder="big")
                        #拼接待发送的数据，byte类型
                        for valume in context.his_today_data_dic.values():
                            # print(f"{valume['symbol']}:{valume['amount']}:{valume['eob']}")
                            history_data_bytes = translate_send_data_to_bytes(context, valume['symbol'], valume['amount'], valume['eob'])
                            ready_send_today_data_bytes += history_data_bytes

                            arrive_index_for_send += 1
                            #达到发送的数量时，发送
                            if arrive_index_for_send == temp_send_count:
                                client_socket.sendall(ready_send_today_data_bytes)
                                residue_data_count -= arrive_index_for_send
                                arrive_index_for_send = 0

                                if residue_data_count > HISTORY_TODAY_DATA_SEND_COUNT:
                                    temp_send_count = HISTORY_TODAY_DATA_SEND_COUNT
                                else:
                                    temp_send_count = residue_data_count

                                ready_send_today_data_bytes = temp_send_count.to_bytes(4, byteorder="big")

                        #=====================================

                        val.is_init = True
                        val.is_initing = False

                        if_complete = 1

                        #耗时测试
                        print(f"ReciveClientThreadC----总耗时为02:{time.time()-t:4f}s")

        #当初始化完成后，删掉存在初始化字典里的对象
        if if_complete == 1:
            del_init_member = None

            for key, valume in context.init_client_socket_dic.items():
                if valume.is_init == True:
                    del_init_member = key
                    break

            # 不能在这里删除dict的item，因为你外面那层正在遍历中，先记录下来，出这个函数后再删
            context.delete_client_socket_arr.append(del_init_member)

            # 关盘后，模拟on_bar用,用这个
            # simulation_on_bar(context)

#这里尝试更改为线程，去拿取所有历史数据，包括当天历史数据, 暂时不考虑
def init_client_when_get_all_data(context):
    pass

#初始化客户端，分段传输数据，暂时没用
def init_client_fragments(context):

    if_complete = 0

    while if_complete == 0:
            time.sleep(0.1)
            if context.init_client_socket_dic:
                client_socket = ""
                for val in context.init_client_socket_dic.values():
                    client_socket = val

                t = time.time()
                print(f"ready")

                test_get_data(context)

                temp_num = 0
                for his_val in context.his_data:
                    context.his_data_dic[str({temp_num})] = PackHistoryDataFrame(his_val['symbol'], his_val['amount'], str(his_val['eob'])).to_dict()
                    temp_num += 1

                print(f"===={len(context.his_data_dic)}")


                his_data_dic_json = json.dumps(context.his_data_dic)
                hddj_len = len(his_data_dic_json.encode('utf-8'))
                print(f"hddj_len:{hddj_len}")

                #耗时测试
                print(f"ReciveClientThreadC----总耗时为01:{time.time()-t:4f}s")

                off_set = 0

                while off_set < hddj_len:

                    time.sleep(0.1)

                    chunk = his_data_dic_json[off_set:off_set + context.chunk_size]
                    length = len(chunk)

                    print(f"{chunk}")

                    packed_length = struct.pack(context.LENGTH_FORMAT, length)


                    client_socket.sendall(packed_length)

                    client_socket.sendall(chunk.encode())

                    off_set += context.chunk_size

                #耗时测试
                print(f"ReciveClientThreadC----总耗时为02:{time.time()-t:4f}s")
                if_complete = 1

def handle_pre_order(context, tick):
    
    # 如果client order还没有处理完，也返回
    if tick.symbol in context.client_order.keys():
        print(f'{tick.symbol}订单没有处理完毕，直接返回')
        return
    
    # 检测处理标的是否存在于队列中
    if tick.symbol in context.pre_quick_buy_dict.keys():
        print(f"准备开始处理急速购买标的[{tick.symbol}]-[{context.pre_quick_buy_dict[tick.symbol].pre_quick_buy_amount / 10000}]w")
        base_num = 1
        # 我们需要读取从tick中获取的数据，才能计算需要买入的数量，否则我们默认只买入100股（这里还有其他问题没有处理，比如科创股必须买200，可以参考策略B脚本）
        # TODO:科创至少200
        buy_in_num = math.floor(context.pre_quick_buy_dict[tick.symbol].pre_quick_buy_amount / (tick.price * 1.002)) # 预留0.2%的手续费，先观察是否合理
        base_num = math.floor(buy_in_num / 100)
        
        # 科创股至少买200，检查如果是100的话，能买的起200就买
        tech_flag = ((tick.symbol.find('.688') != -1) or (tick.symbol.find('.689') != -1))
        if tech_flag and base_num == 1:
            base_num = 2
        
        # 直接使用市价买入，则可以不指定买入价格（居然根据佳哥需求）
        log(f"------try buy with symbol[{tick.symbol}]--[{base_num * 100}]")
        list_order = order_volume(symbol=tick.symbol, volume=base_num * 100, side=OrderSide_Buy, order_type=OrderType_Market, position_effect=PositionEffect_Open)
        
        # 记录order的client id，避免出现之前的重复购买
        # 只有当id在order status的回掉中，出现已成（不是部成）或者被拒绝的时候，才开放再次购买
        # 需要一定的数据格式，记录在context全局变量中，这样不会被擦除
        # 数据信息：{symbol:[list_order]}，直接把list_order一下装进去吧，也不用费事单独拆一些数据了
        context.client_order[tick.symbol] = list_order
        
    if tick.symbol in context.pre_quick_sell_dict.keys():
        
        sell_num = 100        
        if (tick.symbol in context.ids_info_dict.keys()) and (context.ids_info_dict[tick.symbol].hold_available > 0):
            sell_num = context.ids_info_dict[tick.symbol].hold_available
        
        # 直接使用市价卖出，则可以不指定卖出价格（居然根据佳哥需求）
        log(f"------try sell with symbol[{tick.symbol}]--[{sell_num}]")
        list_order = order_volume(symbol=tick.symbol, volume=sell_num, side=OrderSide_Sell, order_type=OrderType_Market, position_effect=PositionEffect_Close)
        
        # 记录order的client id，避免出现之前的重复购买
        # 只有当id在order status的回掉中，出现已成（不是部成）或者被拒绝的时候，才开放再次购买
        # 需要一定的数据格式，记录在context全局变量中，这样不会被擦除
        # 数据信息：{symbol:[list_order]}，直接把list_order一下装进去吧，也不用费事单独拆一些数据了
        context.client_order[tick.symbol] = list_order

def on_tick(context, tick):

    # return

    # 更新对应标的的一些保存信息----------------------------------------
    if tick.symbol in context.ids_info_dict.keys():
        context.ids_info_dict[tick.symbol].price = tick.price
        
        if context.ids_info_dict[tick.symbol].name == "":
            info = get_instruments(symbols = tick.symbol, skip_suspended = False, df = True)
            # empty情况一般就是ST的股票，直接先跳过不处理
            if info.empty:
                print(f"[init][{tick.symbol}]get cache info null, this should not happen[可能是停牌]......")
            else:
                context.ids_info_dict[tick.symbol].name = info.sec_name[0]
        
        # 持仓不要一直获取，下面拿pos的函数延迟很大，需要特别注意！！！
        if context.ids_info_dict[tick.symbol].hold_available == 0:
            # 获取当前持仓
            curHolding = 0
            # 这里的Side一定要标注正确，比如我是买入的脚本，里面有个都是使用的Buy类型
            # 验证了下，获取买入后的持仓都是Buy类型，不是我想象的sell就要获取sell类型，我估计期货才用这个
            pos = context.account().position(symbol = tick.symbol, side = OrderSide_Buy)
            if not pos:
                context.ids_info_dict[tick.symbol].hold_available = 0
            else:
                context.ids_info_dict[tick.symbol].hold_available = pos.available_now
                # print(f"{tick.symbol} 今持：{context.ids_info_dict[tick.symbol].hold_available} 总持：{pos.volume} 可用：{pos.available_now}")
                
    # 处理待买入或者卖出的列表--------------------------------------------------
    handle_pre_order(context, tick)

    #客户端断开连接后，从socket_dic中移除相应sokcet
    if len(context.delete_temp_adress_arr) > 0:

        for key in context.delete_temp_adress_arr:
            del context.client_init_complete_dic[context.socket_dic[key]]
            del context.socket_dic[key]

        context.delete_temp_adress_arr = []

    if context.init_client_socket_dic:

        context.iniclient_socket_lock.acquire()

        for key, valume in context.init_client_socket_dic.items():

            if valume.is_init == False and valume.is_initing == False and valume.check_mac_flag == True:
                init_client_one_time(context)
        # 在这里检测是否需要删除，需要的话，从这儿删除
        if len(context.delete_client_socket_arr) > 0:
            for key in context.delete_client_socket_arr:
                del context.init_client_socket_dic[key]
            # 重置数组为空（删除后）
            context.delete_client_socket_arr = []

        context.iniclient_socket_lock.release()

    #=-===============================================================
    if context.is_subscribe == True:

        if tick['symbol'] != 'SHSE.000001' :
            
            context.cur_data_dic.clear()
            context.cur_data_dic[tick['symbol']] = PackSecondDataFrame(tick['symbol'], tick['last_amount'], str(tick['created_at'])).to_dict()

            #这段用于测试1分钟内，掉的数据,离开了当前分钟就不想客户端发送数据,暂时不用了!!!
            # if context.socket_dic:
            #     for k,v in context.socket_dic.items():
            #         if context.client_init_complete_dic[v] == False:
            #             temp_current_time_arr = str(tick['created_at']).split(" ")
            #             temp_c_hour_arr = temp_current_time_arr[1].split("+")
            #             temp_int_c_hour_arr = temp_c_hour_arr[0].split(".")
            #             temp_h_m_s = temp_int_c_hour_arr[0].split(":")

            #             now_time_h = temp_h_m_s[0]
            #             now_time_m = temp_h_m_s[1]
            #             now_time_s = temp_h_m_s[2]

            #             context.test_second_data_time = now_time_m

            #         else:
            #             temp_current_time_arr = str(tick['created_at']).split(" ")
            #             temp_c_hour_arr = temp_current_time_arr[1].split("+")
            #             temp_int_c_hour_arr = temp_c_hour_arr[0].split(".")
            #             temp_h_m_s = temp_int_c_hour_arr[0].split(":")

            #             now_time_h = temp_h_m_s[0]
            #             now_time_m = temp_h_m_s[1]
            #             now_time_s = temp_h_m_s[2]

            #             context.test_next_second_data_time = now_time_m
            
            if context.socket_dic:
                for k,v in context.socket_dic.items():

                    if context.client_init_complete_dic[v] == True:

                        #这里先发获得历史中的当前分钟内的数据
                        if len(context.ready_second_for_send) > 0:
                            print(f"context.ready_second_for_send::{len(context.ready_second_for_send)}")
                            for second_data in context.ready_second_for_send:
                                context.cur_data_dic.clear()
                                context.cur_data_dic[second_data['symbol']] = second_data
                                print(f"context.ready_second_for_send::{second_data['symbol']}::{second_data['amount']}::{second_data['eob']}")
                                send_message_second_method(v, context)
                            #不能再这里做清空，下面需要对比是否有重复数据
                            # context.ready_second_for_send.clear()

                        #这里在初始化完成后，第一次发送数据，这里可能会有点问题！！！
                        if len(context.ready_for_send) > 0:
                            print(f"context.ready_for_send::{len(context.ready_for_send)}")
                            for ready_data in context.ready_for_send:
                                context.cur_data_dic.clear()
                                context.cur_data_dic[ready_data['symbol']] = ready_data
                                # print(f"context.ready_for_send::{ready_data['symbol']}::{ready_data['amount']}::{ready_data['eob']}")
                                
                                #这里需要遍历ready_second_for_send,查看是否有重复数据
                                for second_data in context.ready_second_for_send:
                                    if ready_data['symbol'] == second_data['symbol']:
                                        if ready_data['eob'] != second_data['eob']:
                                            send_message_second_method(v, context)
                                        #这里将break tab了一下，不知道会不会有啥问题，看看先    
                                        break

                        if len(context.ready_for_send) > 0:
                            context.ready_for_send.clear()
                        if len(context.ready_second_for_send) > 0:
                            context.ready_second_for_send.clear()

                        #用于测试1分钟内，tick掉的数据，暂时不用了
                        # if context.test_second_data_time == context.test_next_second_data_time:
                        #     context.cur_data_dic.clear()
                        #     context.cur_data_dic[tick['symbol']] = PackSecondDataFrame(tick['symbol'], tick['last_amount'], str(tick['created_at'])).to_dict()
                        #     print(f"current::{tick['symbol']}::{tick['last_amount']}::{str(tick['created_at'])}")
                        #     send_message_second_method(v, context)

                        context.cur_data_dic.clear() 
                        context.cur_data_dic[tick['symbol']] = PackSecondDataFrame(tick['symbol'], tick['last_amount'], str(tick['created_at'])).to_dict()
                        send_message_second_method(v, context)

                    #当有客户端连接进来，但是还没初始化完成时，先将来的数据存入等待发送的队列里
                    else:
                        #这里发现，00秒的数据有可能会重复，这里需要遍历一下ready_second_for_send里 是否已经有00秒数据，如果有 就不进行存入
                        #这里有点问题，可能会有重复数据出现，后面记得来改!!!
                        for data_key, data_value in context.cur_data_dic.items():
                            temp_ready_for_send_data = data_value

                            temp_index = 0

                            #这里需要优化，如果标的多，中途开启，这里会堆积数万条数据待发送，后期可能会数10万条，虽然最后面可能不会有中途开启情况，但先优化再说
                            for find_symbol_data in context.ready_for_send:

                                temp_index += 1

                                if temp_ready_for_send_data['symbol'] == find_symbol_data['symbol']:
                                    #获得当前数据的当前分钟
                                    temp_cur_data_time = temp_ready_for_send_data['eob']

                                    get_A_time_arr = temp_cur_data_time.split("+")
                                    get_A_time_arr_1 = get_A_time_arr[0].split(" ")
                                    get_A_time_arr_2 = get_A_time_arr_1[1].split(":")

                                    get_A_min = get_A_time_arr_2[1]

                                    #获得在集合中数据的当前分钟
                                    temp_in_list_data_time = find_symbol_data['eob']

                                    get_B_time_arr = temp_in_list_data_time.split("+")
                                    get_B_time_arr_1 = get_B_time_arr[0].split(" ")
                                    get_B_time_arr_2 = get_B_time_arr_1[1].split(":")

                                    get_B_min = get_B_time_arr_2[1]

                                    if get_A_min == get_B_min:

                                        temp_delete_amount = find_symbol_data['amount']
                                        temp_now_amount = temp_ready_for_send_data['amount']
                                        #当前分钟内同一只标的，数据相加
                                        temp_adding_amount = round(float(temp_delete_amount), 2) + round(float(temp_now_amount), 2)

                                        #对这只标的，相关数据重新赋值，理论上应该将该只标的先删除，在重新添加进集合，先重新赋值看看有没有什么问题吧
                                        find_symbol_data['amount'] = str(temp_adding_amount)
                                        find_symbol_data['eob'] = temp_ready_for_send_data['eob']

                                        break

                            if temp_index == len(context.ready_for_send):
                                context.ready_for_send.append(temp_ready_for_send_data)    

                        print(f"ready_for_send length:{len(context.ready_for_send)}")
                        
def on_bar(context, bars):

    print(f"bars length:{len(bars)}")

    temp_bars_symbol_arr =[]
    for item in bars:
        temp_bars_symbol_arr.append(item.symbol)

    temp_eob = None
    for item in bars:
        temp_eob = item.eob
        print(f"temp_eob temp_eob:{item.eob}")
        break

    for item in context.subscription_stock_arr:
        if item not in temp_bars_symbol_arr:
            print(f"not in bar symbol:{item}")
            context.cur_data_dic[item] = PackCurrentDataFrame(item, 0, str(temp_eob)).to_dict()

    temp_bars_symbol_arr.clear()

    for item in bars:
        context.cur_data_dic[item.symbol] = PackCurrentDataFrame(item.symbol, item.amount, str(item.eob)).to_dict()

    print(f"cur_data_dic lenth:{len(context.cur_data_dic)}|subscription_stock_arr length:{len(context.subscription_stock_arr)}")

    if len(context.cur_data_dic) == len(context.subscription_stock_arr):
        if context.socket_dic:
            for k,v in context.socket_dic.items():
                send_message_method(v, context)

# 委托状态更新事件
# 响应委托状态更新事情，下单后及委托状态更新时被触发。
#注意：
# 1、交易账户重连后，会重新推送一遍交易账户登录成功后查询回来的所有委托
# 2、撤单拒绝，会推送撤单委托的最终状态
'''
order.status
OrderStatus_Unknown = 0
OrderStatus_New = 1                   # 已报
OrderStatus_PartiallyFilled = 2       # 部成
OrderStatus_Filled = 3                # 已成
OrderStatus_Canceled = 5              # 已撤
OrderStatus_PendingCancel = 6         # 待撤
OrderStatus_Rejected = 8              # 已拒绝
OrderStatus_Suspended = 9             # 挂起 （无效）
OrderStatus_PendingNew = 10           # 待报
OrderStatus_Expired = 12              # 已过期
'''
# 处理订单状态变化函数--------
def on_order_status(context, order):
    #print('--------on_order_status')
    #print(order)

    name = ""
    if order.symbol in context.ids_info_dict.keys():
        name = context.ids_info_dict[order.symbol].name

    if order.ord_rej_reason != 0:
        log(f"{order.symbol}:{name} 委托已被拒绝！具体原因如下：{order.ord_rej_reason_detail}")
        # 被拒绝后，可以消除订单的记录
        if order.symbol in context.client_order.keys():
            del context.client_order[order.symbol]
        if order.symbol in context.pre_quick_buy_dict.keys():
            del context.pre_quick_buy_dict[order.symbol]
        if order.symbol in context.pre_quick_sell_dict.keys():
            del context.pre_quick_sell_dict[order.symbol]

    # 订单全部成交的话（status == 3），可以消除订单记录
    if order.status == OrderStatus_Filled:
        # 更新买卖方向的相关信息
        if order.side == OrderSide_Sell:
            log(f'{order.symbol}:{name} 所有委托订单已成[卖出]，成交均价为：{round(order.filled_vwap, 3)}，已成量：{order.filled_volume}')
        elif order.side == OrderSide_Buy:
            log(f'{order.symbol}:{name} 所有委托订单已成[买入]，成交均价为：{round(order.filled_vwap, 3)}，已成量：{order.filled_volume}')
        
        if order.symbol in context.client_order.keys():
            del context.client_order[order.symbol]
        if order.symbol in context.pre_quick_buy_dict.keys():
            del context.pre_quick_buy_dict[order.symbol]
        if order.symbol in context.pre_quick_sell_dict.keys():
            del context.pre_quick_sell_dict[order.symbol]

#拿到前一天的去全部历史数据，以每分钟为间隔
def test_get_data(context):

    yesterday_date = get_previous_or_friday_date()
    s_time = str(yesterday_date) + ' 9:15:0'
    e_time = str(yesterday_date) + ' 15:00:0'
    test_s_time = '2024-07-04' + ' 9:15:0'
    test_e_time = '2024-07-04' + ' 15:00:0'
    #测试的时候用，重新赋值，不用后面老是替换了,不用的时候注释掉
    # s_time = test_s_time
    # e_time = test_e_time

    print(f"{s_time} To {e_time}")
    print(f"SECTION_HISTORY_STOCK_COUNT::{SECTION_HISTORY_STOCK_COUNT}")

    #这里将改为分批次获取历史数据，history中df=False时，返回的是一个集合
    temp_ids_str = ''
    temp_index = 0
    #这里我们用一个临时集合来接取数据，再将临时集合中的数据添加到context.his_data中
    temp_his_data = []
    #先将存入集合中的标的代码，以SECTION_HISTORY_STOCK_COUNT为准拼接未字符串，用来分批次获得历史数据
    for item in context.subscription_stock_arr:
            if temp_index == 0:
                temp_ids_str = item
            else:
                temp_ids_str = temp_ids_str + ',' + item
            temp_index += 1

            #当达到批次的数量时，开始获得历史数据
            if temp_index == SECTION_HISTORY_STOCK_COUNT:
                temp_his_data = history(symbol=temp_ids_str, frequency='60s', start_time=s_time,  end_time=e_time, fields='symbol, amount, eob, name', adjust=ADJUST_PREV, df=False)
                print(f"temp_his_data length::{len(temp_his_data)}")

                #重置temp_index以及temp_ids_str
                temp_index = 0
                temp_ids_str = ''

                #将temp_his_data装入context.his_data里面
                for temp_data in temp_his_data:
                    #这里应该要新创建一个变量
                    temp_temp_data = temp_data
                    context.his_data.append(temp_temp_data)

                #重置temp_his_data方便接受下一批次
                temp_his_data.clear()

    #这里还需要判断，当出了for循环以后，如果还有剩余的票需要再用temp_his_data拿取剩余标的的历史数据
    #这里应该可以直接判断，直接拿取到context.his_data里，节省一个for循环时间，但以后这种情况可能会比较少，所以暂时也就无所谓了！
    if temp_ids_str != '':
        temp_his_data = history(symbol=temp_ids_str, frequency='60s', start_time=s_time,  end_time=e_time, fields='symbol, amount, eob, name', adjust=ADJUST_PREV, df=False)
        print(f"temp_his_data length::{len(temp_his_data)}")

        temp_ids_str = ''

        #将temp_his_data装入context.his_data里面
        for temp_data in temp_his_data:
            #这里应该要新创建一个变量
            temp_temp_data = temp_data
            context.his_data.append(temp_temp_data)

        temp_his_data.clear()

    print(f"context.his_data length::{len(context.his_data)}")


def get_history_data_in_today(context):
    now_data = context.now
    print(f"{now_data}")
    print(f"{context.symbol_str}")
    
    get_now_time_arr = str(now_data).split("+")
    get_now_time_arr_1 = get_now_time_arr[0].split(" ")
    get_now_time_arr_2 = get_now_time_arr_1[1].split(":")

    get_now_hour = get_now_time_arr_2[0]
    get_now_min = get_now_time_arr_2[1]
    get_now_second = get_now_time_arr_2[2]
    temp_second_arr = get_now_second.split(".")
    get_now_second_without_dot = temp_second_arr[0]

    print(f"time::{get_now_hour}:{get_now_min}:{get_now_second_without_dot}")
    
    #关盘时间外测试用===========
    if int(get_now_hour) > 15:
        get_now_hour = 14
    elif int(get_now_hour) < 9:
        get_now_hour = 9
    #==========================

    #计算当前时间之前，以每分钟为单位，共有多少条数据, 暂时用不上
    # min_count = 0
    # if int(get_now_hour) >= 13:
    #     min_count = (int(get_now_hour) - 13) * 60 + 120 + int(get_now_min)
    # else:
    #     min_count = (int(get_now_hour) - 9) * 60 + int(int(get_now_min))

    # print(f"min_count::{min_count}")
    
    temp_ids_str = ''
    temp_index = 0
    for item in context.subscription_stock_arr:
            if temp_index == 0:
                temp_ids_str = item
            else:
                temp_ids_str = temp_ids_str + ',' + item
            temp_index += 1

    context.symbol_str = temp_ids_str

    #这里为获取当日现在时间     1
    s_time= str(get_now_time_arr_1[0]) + ' 09:15:00'
    e_time = str(get_now_time_arr_1[0]) + ' ' + str(get_now_hour) + ':' + str(get_now_min) + ':' + '00'
    #test为测试时用的时间
    test_s_time = '2024-07-05' + ' ' + '09:15:00'
    test_e_time = '2024-07-05' + ' ' + '10:00:00'
    #测试的时候用，重新赋值，不用后面老是替换了,不用的时候注释掉
    # s_time = test_s_time
    # e_time = test_e_time

    #这里为获取当日9:25的集合进价时间   2
    s_25_today_time = str(get_now_time_arr_1[0]) + ' 09:24:57'
    e_25_today_time = str(get_now_time_arr_1[0]) + ' 09:25:00'
    yesterday_date = get_previous_or_friday_date()
    s_25_hisroty_time = str(yesterday_date) + ' 09:25:00'
    e_25_hisroty_time = str(yesterday_date) + ' 09:25:00'

    #这里为拿到当前分钟内的数据的时间     3
    e_second_time = str(get_now_time_arr_1[0]) + ' ' + str(get_now_hour) + ':' + str(get_now_min) + ':' + str(get_now_second)
    #注意!!!开始时间，例如9：53：00秒，此开始时间并不包含00秒数据，需要开始从9:52:59秒开始遍历!!!!!!!!!!
    temp_temp_translate_time = str(get_now_hour) + ":" + str(get_now_min) + ":" + '59'
    temp_translate_time = datetime.strptime(temp_temp_translate_time, "%H:%M:%S").time()
    now = datetime.now()  
    combined = datetime.combine(now.date(), temp_translate_time)
    one_minute_early = combined - timedelta(minutes=1) 
    s_second_time = str(one_minute_early)

    print(f"is stuck here 1?")
    print(f"SECTION_HISTORY_STOCK_COUNT::{SECTION_HISTORY_STOCK_COUNT}")

    #这里同样需要像history那样，改成分段式拿取今天的此时段之前的所有数据
    temp_section_ids_str = ''
    temp_section_index = 0
    temp_his_today_data = []
    temp_his_data_for_today_second = []
    temp_his_25_amount_data = []
    temp_his_25_today_amount_data = []
    #先将存入集合中的标的代码，以SECTION_HISTORY_STOCK_COUNT为准拼接未字符串，用来分批次获得历史数据
    for item in context.subscription_stock_arr:
            if temp_section_index == 0:
                temp_section_ids_str = item
            else:
                temp_section_ids_str = temp_section_ids_str + ',' + item
            temp_section_index += 1

            #当达到批次的数量时，开始获得历史数据
            if temp_section_index == SECTION_HISTORY_STOCK_COUNT:
                temp_his_today_data = history(symbol=temp_section_ids_str, frequency='60s', start_time=s_time,  end_time=e_time, fields='symbol, amount, eob, name', adjust=ADJUST_PREV, df=False)
                print(f"temp_his_today_data length::{len(temp_his_today_data)}")

                #将temp_his_today_data装入context.his_data_for_today里面
                for temp_data in temp_his_today_data:
                    #这里应该要新创建一个变量
                    temp_temp_data = temp_data
                    context.his_data_for_today.append(temp_temp_data)

                #这里为分批次获取当前分钟内的数据
                temp_his_data_for_today_second = history(symbol=temp_section_ids_str, frequency='tick', start_time=s_second_time,  end_time=e_second_time, fields='symbol, last_amount, created_at', skip_suspended=False, fill_missing='NaN', adjust=ADJUST_PREV, df=False)

                for temp_data in temp_his_data_for_today_second:
                    #这里应该要新创建一个变量
                    temp_temp_data = temp_data
                    context.his_data_for_today_second.append(temp_temp_data)

                #这里为分批次获取昨日25分钟时集合进价数据
                temp_his_25_amount_data = history(symbol=temp_section_ids_str, frequency='tick', start_time=s_25_hisroty_time,  end_time=e_25_hisroty_time, fields='symbol, last_amount, created_at', skip_suspended=False, fill_missing='NaN', adjust=ADJUST_PREV, df=False)

                for temp_data in temp_his_25_amount_data:
                    #这里应该要新创建一个变量
                    temp_temp_data = temp_data
                    context.his_25_amount_data.append(temp_temp_data)

                #这里为分批次获取今日25分钟集合进价数据
                temp_his_25_today_amount_data = history(symbol=temp_section_ids_str, frequency='tick', start_time=s_25_today_time,  end_time=e_25_today_time, fields='symbol, last_amount, created_at', skip_suspended=False, fill_missing='NaN', adjust=ADJUST_PREV, df=False)

                for temp_data in temp_his_25_today_amount_data:
                    #这里应该要新创建一个变量
                    temp_temp_data = temp_data
                    context.his_25_today_amount_data.append(temp_temp_data)

                #重置temp_index以及temp_section_ids_str
                temp_section_index = 0
                temp_section_ids_str = ''

                #重置,方便接受下一批次
                temp_his_today_data.clear()
                temp_his_data_for_today_second.clear()
                temp_his_25_amount_data.clear()
                temp_his_25_today_amount_data.clear()

    #这里还需要判断，当出了for循环以后，如果还有剩余的票需要再用temp_his_data拿取剩余标的的历史数据
    #这里应该可以直接判断，直接拿取到context.his_data_for_today里，节省一个for循环时间，但以后这种情况可能会比较少，所以暂时也就无所谓了！
    if temp_section_ids_str != '':
        temp_his_today_data = history(symbol=temp_section_ids_str, frequency='60s', start_time=s_time,  end_time=e_time, fields='symbol, amount, eob, name', adjust=ADJUST_PREV, df=False)
        print(f"temp_his_today_data length::{len(temp_his_today_data)}")


        #将temp_his_data装入context.his_data_for_today里面
        for temp_data in temp_his_today_data:
            #这里应该要新创建一个变量
            temp_temp_data = temp_data
            context.his_data_for_today.append(temp_temp_data)

        #这里为分批次获取当前分钟内的数据
        temp_his_data_for_today_second = history(symbol=temp_section_ids_str, frequency='tick', start_time=s_second_time,  end_time=e_second_time, fields='symbol, last_amount, created_at', skip_suspended=False, fill_missing='NaN', adjust=ADJUST_PREV, df=False)

        for temp_data in temp_his_data_for_today_second:
            #这里应该要新创建一个变量
            temp_temp_data = temp_data
            context.his_data_for_today_second.append(temp_temp_data)

        #这里为分批次获取昨日25分钟时集合进价数据
        temp_his_25_amount_data = history(symbol=temp_section_ids_str, frequency='tick', start_time=s_25_hisroty_time,  end_time=e_25_hisroty_time, fields='symbol, last_amount, created_at', skip_suspended=False, fill_missing='NaN', adjust=ADJUST_PREV, df=False)

        for temp_data in temp_his_25_amount_data:
            #这里应该要新创建一个变量
            temp_temp_data = temp_data
            context.his_25_amount_data.append(temp_temp_data)

        #这里为分批次获取今日25分钟集合进价数据
        temp_his_25_today_amount_data = history(symbol=temp_section_ids_str, frequency='tick', start_time=s_25_today_time,  end_time=e_25_today_time, fields='symbol, last_amount, created_at', skip_suspended=False, fill_missing='NaN', adjust=ADJUST_PREV, df=False)

        for temp_data in temp_his_25_today_amount_data:
            #这里应该要新创建一个变量
            temp_temp_data = temp_data
            context.his_25_today_amount_data.append(temp_temp_data)

        temp_section_ids_str = ''

        #清空临时list
        temp_his_today_data.clear()
        temp_his_data_for_today_second.clear()
        temp_his_25_amount_data.clear()
        temp_his_25_today_amount_data.clear()

    print(f"context.his_data_for_today length::{len(context.his_data_for_today)}")
    print(f"his_25_amount_data length:{len(context.his_25_amount_data)}")
    print(f"his_25_today_amount_data length:{len(context.his_25_today_amount_data)}")
    print(f"here 1")


    temp_25_stock_arr = []
    temp_25_today_stock_arr = []
    for item in context.his_25_amount_data:
        # print(f"{item['symbol']}::{item['last_amount']}|{item['created_at']}")
        temp_25_stock_arr.append(item['symbol'])

    for item in context.his_25_today_amount_data:
        # print(f"{item['symbol']}::{item['last_amount']}|{item['created_at']}")
        temp_25_today_stock_arr.append(item['symbol'])

    context.notin_25_stock_arr = []
    context.notin_25_today_stock_arr = []

    for temp_stock in context.subscription_stock_arr:
        if temp_stock not in temp_25_stock_arr:
            context.notin_25_stock_arr.append(temp_stock)

        if temp_stock not in temp_25_today_stock_arr:
            context.notin_25_today_stock_arr.append(temp_stock)

    print(f"context.notin_25_stock_arr::{len(context.notin_25_stock_arr)}")
    print(f"context.notin_25_today_stock_arr::{len(context.notin_25_today_stock_arr)}")

    # for item in context.his_data_for_today:
    #     print(f"{item['symbol']}::{item['amount']}|{item['eob']}")
    # print(f"e_time:::{e_time}==========")

    # for item in context.his_data_for_today_second:
    #     print(f"{item['symbol']}::{item['last_amount']}|{item['created_at']}")
    # print(f"e_time:::{e_time}==========")

    #拿到当前分钟中的每一条数据，并做相加，减少数据堆积造成的发送压力
    context.temp_total_second_data = {}
    for item_symbol in context.subscription_stock_arr:
        temp_total_valume = 0
        temp_second_time = None
        for item in context.his_data_for_today_second:
            if item['symbol'] == item_symbol:
                temp_total_valume += float(item['last_amount'])
                temp_second_time = str(item['created_at'])
        context.temp_total_second_data[item_symbol] = temp_total_valume
        context.ready_second_for_send.append(PackHistoryDataFrame(item_symbol, temp_total_valume, temp_second_time, 'his_today_data').to_dict())

    # for key, value in context.temp_total_second_data.items():
    #     print(f"{key}:::{value}")

    # for item in context.ready_second_for_send:
    #     print(f"total@@@{item['symbol']}:::{item['amount']}:::{item['eob']}")


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

#发送消息线程---101
def send_message_method(client_socket, context):
    try:
        #耗时测试
        t = time.time()

        context.operation_id_send = 100
        operation_id_byte = context.operation_id_send.to_bytes(4, byteorder='big')
        client_socket.sendall(operation_id_byte)

        cur_data_dic_json = json.dumps(context.cur_data_dic)
        cur_len = len(cur_data_dic_json.encode('utf-8'))
        print(f"hddj_len:{cur_len}")

        cur_len_byte = cur_len.to_bytes(4, byteorder='big')
        client_socket.sendall(cur_len_byte)

        #耗时测试
        print(f"SendClientThreadC----总耗时为02:{time.time()-t:4f}s")

        time.sleep(0.01)
        client_socket.sendall(cur_data_dic_json.encode('utf-8'))

         #耗时测试
        print(f"SendClientThreadC----总耗时为01:{time.time()-t:4f}s")

    except ConnectionResetError:
         client_socket.close()
         print("Client disconnected unexpectedly.")

    finally:
         #client_socket.close()
         #context.cur_data_dic.clear()

         context.temp_clear_curdata_index += 1

         if context.temp_clear_curdata_index == len(context.socket_dic):
            context.cur_data_dic.clear()
            context.temp_clear_curdata_index = 0

         #pass


#发送消息线程---102
def send_message_second_method_backup(client_socket, context):
    try:
        #耗时测试
        #t = time.time()

        #先尝试将102改成二进制发送

        context.operation_id_send = 102
        operation_id_byte = context.operation_id_send.to_bytes(4, byteorder='big')
        client_socket.sendall(operation_id_byte)

        cur_data_dic_json = json.dumps(context.cur_data_dic)
        cur_len = len(cur_data_dic_json.encode('utf-8'))
        print(f"cur_len:{cur_len}")

        cur_len_byte = cur_len.to_bytes(4, byteorder='big')
        client_socket.sendall(cur_len_byte)

        #耗时测试
        #print(f"SendClientThreadC----总耗时为02:{time.time()-t:4f}s")

        time.sleep(0.002)
        client_socket.sendall(cur_data_dic_json.encode('utf-8'))

         #耗时测试
        #print(f"SendClientThreadC----总耗时为01:{time.time()-t:4f}s")

    except ConnectionResetError:
         client_socket.close()
         print("Client disconnected unexpectedly.")
         print("In send method.")
         
         for key, valume in context.socket_dic.items():
                    if client_socket == valume:
                        context.delete_temp_adress_arr.append(key)
                        context.client_init_complete_dic[client_socket] = False
                        break

    finally:
        context.temp_clear_curdata_index += 1
        if context.temp_clear_curdata_index == len(context.socket_dic):
            context.cur_data_dic.clear()
            context.temp_clear_curdata_index = 0


#重写发送消息线程---102，改为二进制发送
def send_message_second_method(client_socket, context):
    try:

        #先尝试将102改成二进制发送  OP_ID_S2C_REAL_TIME_DATA_SEND - 102
        #这里使用for循环，有一次发现dic里存在多条数据，但是几率非常非常小
        for key, valume in context.cur_data_dic.items():
            sned_data_bytes = translate_send_data_to_bytes(context, valume['symbol'], valume['amount'], valume['eob'])

            #4+4+4+4+4+4 = 24字节
            client_socket.sendall(OP_ID_S2C_REAL_TIME_DATA_SEND.to_bytes(4, byteorder='big') + sned_data_bytes)

    except ConnectionResetError:
         client_socket.close()
         print("Client disconnected unexpectedly.")
         print("In send method.")
         
         for key, valume in context.socket_dic.items():
                    if client_socket == valume:
                        context.delete_temp_adress_arr.append(key)
                        context.client_init_complete_dic[client_socket] = False
                        break

    finally:
        context.temp_clear_curdata_index += 1
        if context.temp_clear_curdata_index == len(context.socket_dic):
            context.cur_data_dic.clear()
            context.temp_clear_curdata_index = 0

#将待发送数据，转化为byte
def translate_send_data_to_bytes(context, symbol, amount, eob):

    temp_symbol_letter = 0
    temp_symbol_num = 0
    temp_amount = 0
    temp_eob_date = 0
    temp_eob_time = 0

    #2-4 int32
    temp_symbol_arr = symbol.split(".")
    temp_symbol_letter = translate_letter_to_int(temp_symbol_arr[0])
    symbol_letter_bytes = temp_symbol_letter.to_bytes(4, byteorder='big')

    #3-4 int32
    temp_symbol_num = int(temp_symbol_arr[1])
    symbol_num_bytes = temp_symbol_num.to_bytes(4, byteorder='big')

    #4-4 int32
    temp_amount_without_dot = str(amount).split(".")
    temp_amount = int(temp_amount_without_dot[0])
    amount_bytes = temp_amount.to_bytes(4, byteorder='big')

    #5-4 int32
    if eob == None:
        context_now = context.now
        temp_eob_arr = str(context_now).split(" ")
    else:
        temp_eob_arr = eob.split(" ")

    temp_eob_arr_date_arr = temp_eob_arr[0].split("-")
    temp_temp_date = ''
    for chunk in temp_eob_arr_date_arr:
        temp_temp_date = temp_temp_date + chunk
    temp_eob_date = int(temp_temp_date)
    eob_date_bytes = temp_eob_date.to_bytes(4, byteorder='big')

    #6-4 int32
    temp_eob_arr_time_arr = temp_eob_arr[1].split("+")
    temp_hhmmss_arr = temp_eob_arr_time_arr[0].split(":")
    temp_temp_hhmmss = ''
    for chunk in temp_hhmmss_arr:
        temp_temp_hhmmss = temp_temp_hhmmss + chunk
    #这里会有毫秒的情况，例如13:13:13.0000013的情况,如果没有，好像split也不会报错
    temp_temp_hhmmss_without_dot = temp_temp_hhmmss.split(".")
    temp_eob_time = int(temp_temp_hhmmss_without_dot[0])
    eob_time_bytes = temp_eob_time.to_bytes(4, byteorder='big')

    #4+4+4+4+4 = 20字节
    send_bytes = symbol_letter_bytes + symbol_num_bytes + amount_bytes + eob_date_bytes + eob_time_bytes
    
    return send_bytes

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

#读取允许连入的MAC地址
def load_mac_address(context):

    # ！！！这里读取的配置文件，要根据策略改变
    file_obj = open(mac_address_path, 'r')
    lines = file_obj.readlines()

    buy_flag = True
    for line in lines:
        should_add = True
        str_tmp = line.strip() # 去掉换行符

        # 属于一个技巧性地读取，首先Buy在配置文件的上面，Sell在下面
        # 所以上面都是true，当读取到--------Sell标志行的时候，转为False，这样下面的都是False
        if (str_tmp.find('--------Sell') != -1):
            buy_flag = False
        first3 = str_tmp[:3]

        if len(str_tmp) >= 3:
            third3 = str_tmp[2]

        if(third3 == ':'):
            pass
        elif(third3 == ''):
            should_add = False
        elif (first3 == 'fsa'):
            should_add = False
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
            for item in context.mac_address_arr:
                print(f"{item}")
            print(f"init total mac address length : {len(context.mac_address_arr)}")
            print(f"init address down=========================")
            break
        else:
            if should_add == True:
                if str_tmp not in context.mac_address_arr:
                    if len(str_tmp) > 0:
                        context.mac_address_arr.append(str_tmp)
                        

#将标的前面的英文转化为int类型
def translate_letter_to_int(stork_letter):

    # 使用列表推导式和字符串切片来拆解字符串  
    chunks = [stork_letter[i:i+1] for i in range(0, len(stork_letter), 1)]  
    
    temp_split_joint_letter = ''

    for letter in chunks:
        temp_int_letter = translate_letter_one_by_one(letter)
        temp_split_joint_letter = temp_split_joint_letter + temp_int_letter

    return int(temp_split_joint_letter)


#将单个字母转换为自定义的int类型
def translate_letter_one_by_one(letter):

    #99,999,999 int32

    temp_int = 0

    if letter == 'A':
        temp_int = 10
    elif letter == 'B':
        temp_int = 11
    elif letter == 'C':
        temp_int = 12
    elif letter == 'D':
        temp_int = 13
    elif letter == 'E':
        temp_int = 14
    elif letter == 'F':
        temp_int = 15
    elif letter == 'G':
        temp_int = 16
    elif letter == 'H':
        temp_int = 17
    elif letter == 'I':
        temp_int = 18
    elif letter == 'J':
        temp_int = 19
    elif letter == 'K':
        temp_int = 20
    elif letter == 'L':
        temp_int = 21
    elif letter == 'M':
        temp_int = 22
    elif letter == 'N':
        temp_int = 23
    elif letter == 'O':
        temp_int = 24
    elif letter == 'P':
        temp_int = 25
    elif letter == 'Q':
        temp_int = 26
    elif letter == 'R':
        temp_int = 27
    elif letter == 'S':
        temp_int = 28
    elif letter == 'T':
        temp_int = 29
    elif letter == 'U':
        temp_int = 30
    elif letter == 'V':
        temp_int = 31
    elif letter == 'W':
        temp_int = 32
    elif letter == 'X':
        temp_int = 33
    elif letter == 'Y':
        temp_int = 34
    elif letter == 'Z':
        temp_int = 35

    return str(temp_int)

def log(msg):
    file_obj = open(log_path, 'a')

    nowtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
    finalMsg = nowtime + ": " + msg + "\n"
    file_obj.write(finalMsg)

    # 我们也可以把所有日志打印到控制台查看
    print(finalMsg)

#封装历史数据对象，以便传输
class PackHistoryDataFrame():
    def __init__(self, symbol, amount, eob, name):
        self.symbol = symbol
        self.amount = amount
        self.eob = eob
        self.name = name

    def to_dict(self):
        # 将对象转换为字典，以便可以被JSON序列化
        return {'symbol': self.symbol, 'amount': self.amount, 'eob': self.eob, 'name': self.name}

#封装实时数据对象，以便传输
class PackCurrentDataFrame():
    def __init__(self, symbol, amount, eob):
        self.symbol = symbol
        self.amount = amount
        self.eob = eob

    def to_dict(self):
        # 将对象转换为字典，以便可以被JSON序列化
        return {'symbol': self.symbol, 'amount': self.amount, 'eob': self.eob}

#封装3s实时数据对象，以便传输
class PackSecondDataFrame():
    def __init__(self, symbol, amount, eob):
        self.symbol = symbol
        self.amount = amount
        self.eob = eob

    def to_dict(self):
        # 将对象转换为字典，以便可以被JSON序列化
        return {'symbol': self.symbol, 'amount': self.amount, 'eob': self.eob}

#初始化客户端，初始化状态分别
class InitClientSocketC():
    def __init__(self, client_socket):
        self.client_socket = client_socket
        self.is_initing = False
        self.is_init = False
        self.check_mac_flag = False

#主线程服务器
class MainServerTreadC(threading.Thread):
    def __init__(self, server_ip, server_port, context):
        super().__init__()
        self.server_ip = server_ip
        self.context = context
        self.server_port = server_port
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()
        print("线程已停止")

    def run(self):
        #主动停止线程while not self._stop_event.is_set():
        while not self._stop_event.is_set():
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.bind((self.server_ip, self.server_port))
            server_socket.listen(5)
            print(f"Server is listening on {self.server_ip}:{self.server_port}...")

            while True:
                client_socket, client_address = server_socket.accept()
                print(f"in in in:{client_address}")

                self.context.iniclient_socket_lock.acquire()

                #正在运行中的socket dic
                #这里尝试把context.socket_dic放到接受线程里，如果验证mac地址成功，就添加到这个socket_dic里
                # self.context.socket_dic[client_address] = client_socket
                #需要初始化客户端用到的socket dic，注：这里会在on_tick中调用进行初始化
                self.context.init_client_socket_dic[client_address] = InitClientSocketC(client_socket)
                #设置客户端初始化未完成，当接收到103，即客户端已初始化完成，可以开始发送数据
                self.context.client_init_complete_dic[client_socket] = False

                self.context.iniclient_socket_lock.release()

                print(f"socket{client_socket}")
                print(f"New connection from: {client_address}")

                # #尝试开启线程，持续接受客户端消息
                rfc_thread = ReciveClientThreadC(client_socket, self.context, client_address)
                rfc_thread.start()

                 # #尝试开启线程，持续向客户端发送消息
                # sct_thread = SendClientThreadC(client_socket)
                # sct_thread.start()

                #simulation_on_bar(self.context)

        print("线程已停止")

        def get_client_socket_infomation(self):
            pass

#接收线程，由主线程服务器监听开启，当客户端连接服务器时，将会开启一条接收线程
class ReciveClientThreadC(threading.Thread):
    def __init__(self, client_socket, context, client_address):
        super().__init__()
        self.client_socket = client_socket
        self.context = context
        self.client_address = client_address
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()
        print("线程已停止")
        
    # 插入字符函数
    def insert_char(self, string, index, char):
        return string[:index] + char + string[index:]

    def change_stock_int_to_string(self, id):
        str_tmp = str(id)
        # 需要修复例如000300，这种的标的ID，因为这种ID转换为int后，前面的0就没有了，需要我们自己添加，所以需要检测字符串长度
        str_len = len(str_tmp)
        missing_len = 6 - str_len
        for i in range(0, missing_len):
            str_tmp = self.insert_char(str_tmp, 0, '0')
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
        
        return str_tmp
        
    def socket_receive_quick_buy(self):
        quick_buy_id = self.client_socket.recv(4)
        quick_buy_amount = self.client_socket.recv(2)
        buy_id = int.from_bytes(quick_buy_id, byteorder='big')
        str_symbol = self.change_stock_int_to_string(buy_id)
        buy_amount = int.from_bytes(quick_buy_amount, byteorder='little')
        
        # 如果client order还没有处理完，也返回
        if str_symbol in self.context.client_order.keys():
            print(f'{str_symbol}订单没有处理完毕，直接返回')
            return
        
        leftCash = self.context.account().cash['available'] # 余额
        leftCash = math.floor(float('%.2f' % leftCash))
        leftCash_int = int(leftCash)
        # 限制买入的最大额度不会超过余额！
        if ((buy_amount * 10000) > leftCash_int) and (leftCash_int > 0):
            buy_amount = math.floor(leftCash_int / 10000);
        # totalCash = self.context.account().cash['nav'] # 总资金
        # totalCash = float('%.2f' % totalCash)
        
        # 没有初始化的话，就先初始化，将要买入的目标记录到列表中，待下次tick激活处理
        if str_symbol not in self.context.pre_quick_buy_dict.keys():
            self.context.pre_quick_buy_dict[str_symbol] = TargetInfo()
        self.context.pre_quick_buy_dict[str_symbol].pre_quick_buy_amount = buy_amount * 10000
        
    def socket_receive_quick_sell(self):
        quick_sell_id = self.client_socket.recv(4)
        buy_id = int.from_bytes(quick_sell_id, byteorder='big')
        str_symbol = self.change_stock_int_to_string(buy_id)
        
        # 如果client order还没有处理完，也返回
        if str_symbol in self.context.client_order.keys():
            print(f'{str_symbol}订单没有处理完毕，直接返回')
            return
        
        # 没有初始化的话，就先初始化，将要买入的目标记录到列表中，待下次tick激活处理
        if str_symbol not in self.context.pre_quick_sell_dict.keys():
            self.context.pre_quick_sell_dict[str_symbol] = TargetInfo()

    def run(self):
        #主动停止线程while not self._stop_event.is_set():
        while not self._stop_event.is_set():
            try:
                #先接受包头，以通知需要做什么，客户端暂时只需要像服务器发送初始化请求，暂时
                #没有其他相关功能需求
                self.context.operation_id_recive = self.client_socket.recv(4)

                t = time.time()
                if self.context.operation_id_recive:

                    self.context.operation_id_recive = int.from_bytes(self.context.operation_id_recive, byteorder='big')
                    print(f"operation_id:{self.context.operation_id_recive}")

                    if(self.context.operation_id_recive == 101):
                        print(f"recognition MAC====")
                        mac_data_len = self.client_socket.recv(4)
                        mac_len = int.from_bytes(mac_data_len, byteorder='big')
                        print(f"cur_data_len:{mac_len}")

                        mac_address_data = self.client_socket.recv(mac_len)
                        mac_address_str = json.loads(mac_address_data.decode('utf-8')) 

                        print(f"mac_address_str::{mac_address_str}")

                        if mac_address_str in self.context.mac_address_arr:
                            self.context.init_client_socket_dic[self.client_address].check_mac_flag = True
                            self.context.socket_dic[self.client_address] = self.client_socket
                        else :
                            print(f"not in not in not in not in not in ")
                            self.client_socket.close()
                            self.stop()

                    #客户端初始化完成，可以开始发送数据
                    elif self.context.operation_id_recive == 103:
                        self.context.client_init_complete_dic[self.client_socket] = True
                        
                    elif self.context.operation_id_recive == OP_ID_C2S_QUICK_BUY:
                        self.socket_receive_quick_buy()
                        
                    elif self.context.operation_id_recive == OP_ID_C2S_QUICK_SELL:
                        self.socket_receive_quick_sell()
                        
                    #心跳测试，防止中午时段socket断开
                    elif self.context.operation_id_recive == 900:
                        print(f"this is heartbeat")
                    #未注册的MAC地址，直接关闭socket以及接收thread
                    else:
                        print(f"this is no recognition MAC, close socket!!!")
                        self.client_socket.close()
                        self.stop()


            except ConnectionResetError:
                #这里客户端断开连接后会抛出异常，暂时不知道怎么处理，暂时没看到不影响主线程!!!
                self.client_socket.close()
                self.stop()
                print("Client disconnected unexpectedly.")
                print("this is recive thread")

                for key, valume in self.context.socket_dic.items():
                    if self.client_socket == valume:
                        self.context.delete_temp_adress_arr.append(key)
                        #当客户端退出时，第一时间在这里将这个值设置为False，不然服务器会报错，暂时只能想到这个办法
                        #还是会报错！！还是会报错！！还是会报错！！还是会报错！！还是会报错！
                        self.context.client_init_complete_dic[self.client_socket] = False
                        break

            finally:
                #client_socket.close()
                # print(f"conecting!!!")
                pass
        print("线程已停止")

#发送线程，暂时没用
class SendClientThreadC(threading.Thread):
    def __init__(self, client_socket):
        super().__init__()
        self.client_socket = client_socket
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()
        print("线程已停止")

    def run(self):
        #主动停止线程while not self._stop_event.is_set():
        while not self._stop_event.is_set():

            try:
                #耗时测试
                t = time.time()

                # 封装响应数据为JSON
                response_data = {"message": "Received your data."}
                response = json.dumps(response_data).encode()
                #耗时测试
                print(f"SendClientThreadC----总耗时为02:{time.time()-t:4f}s")
                # 发送响应
                self.client_socket.sendall(response)

                #耗时测试
                print(f"SendClientThreadC----总耗时为01:{time.time()-t:4f}s")

                time.sleep(30)

            except ConnectionResetError:
                self.client_socket.close()
                self.stop
                print("Client disconnected unexpectedly.")

            finally:
                #client_socket.close()
                pass

        print("线程已停止")

#通过线程去拿取历史数据，尝试！
class GetHistoryDataThreadC(threading.Thread):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()
        print("线程已停止")

    def run(self):
        get_history_data_in_today(self.context)
        print("线程已停止")

#用于初始化客户端时，读取存在IDs-V-A1.txt中的id
class LoadedIDsInfo:
    def __init__(self):
        self.buy_flag = 0 # 0->卖出，1->买入，2->??暂留空
        self.already_buy_in_flag = False # 已经被买入标记（用于order中更新，并自动收盘后更新ids文档）
        self.high_expected_flag = 0 # 策略A的高预期标记
        self.force_sell_flag = 0 # 无视其他条件直接卖出
        self.force_buy_flag = 0 # 无视其他条件直接买入
        self.buy_amount = 0 # 单个买入模式，可以支持设置买入资金，或者余额比例
        #self.buy_rate = 0 # 不记录buy_rate，因为rate会随着余额的变化而变化，我们只在第一次设置ids的时候，计算一次应该买入的值，[TODO]实际这个值还应该记录进入文件
        self.buy_with_rate = 1
        self.buy_with_time = "15:51"
        self.buy_with_price = 0
        self.buy_with_num = 0 # 设定的单次买入股数，买入后，再次刷新的话会再次买入指定数量，需要注意
        self.buy_with_num_need_handle = False # 是否需要处理买入股数（设定数量大于0时，把标记激活）
        self.buy_with_num_handled_flag = False # 是否已经处理完毕（已经调用了买入接口，把标记激活，用于后续逻辑判断）
        self.sell_with_rate = 1
        self.sell_with_time = "15:51"
        self.sell_with_price = 0
        self.sell_with_num = 0 # 指定卖出的股数（非全部卖出时使用）

        # 加入变量，控制tick的处理次数，主要为了处理AA这种数量太多的情况，如果每次tick都处理，会造成很大的延迟，导致refresh卡很久
        # 像B这种少的话，我们就每次处理就好
        self.tick_cur_count = 0
        self.tick_handle_frequence = 1

        # 多次上涨后买入，相关配置参数
        self.enable_multi_up_buy_flag = False # 多次上涨才买入的启用开关
        self.multi_up_time_line = "09:45" # 检测多次上涨的时间线
        self.highest_open_fpr = -1.0 # 记录时间线前最高的涨幅情况，针对今开价格
        self.multi_up_buy_flag = False # 多次上涨到目标比例后才买入（为了应对2次或更多到达目标后买入）
        self.multi_up_buy_need_check = True # 用于开启脚本后的检查，比如当下超过X%，就认为是需要处理（进一步等待下跌到X以下，加一次cur_count)
        self.multi_up_total_count = 1 # 总共需要检查的次数，虽然目前需求是1，但是直接做成多次的以后方便
        self.multi_up_cur_count = 0

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
    run(strategy_id='ef37e598-22d7-11ef-896e-00ff2b50aff6',
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

