from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QTextEdit, QMainWindow, QLineEdit, QScrollArea, QLabel,QHBoxLayout,QSizePolicy
from PyQt5.QtCore import Qt, QSize, QThread, pyqtSignal, QTimer, QObject
from PyQt5.QtGui import QTextOption, QResizeEvent, QTextDocument
from datetime import datetime, time, timedelta

import socket
import json
import time
import threading
import struct
import sys 
import numpy as np
import subprocess
import re
import uuid

class AnalysisHistoryData():
    def __init__(self, symbol, amount, eob, name):
        self.symbol = symbol
        self.amount = amount
        self.eob = eob
        self.name = name

    @staticmethod  
    def from_dict(d):  
        # 从字典中创建一个新的CustomObject实例  
        return AnalysisHistoryData(d['symbol'], d['amount'], d['eob'], d['name'])  

class AnalysisCurrentData():
    def __init__(self, symbol, amount, eob):
        self.symbol = symbol
        self.amount = amount
        self.eob = eob

    @staticmethod  
    def from_dict(d):  
        # 从字典中创建一个新的CustomObject实例  
        return AnalysisCurrentData(d['symbol'], d['amount'], d['eob'])  
    
class AnalysisSecondData():
    def __init__(self, symbol, amount, eob):
        self.symbol = symbol
        self.amount = amount
        self.eob = eob

    @staticmethod  
    def from_dict(d):  
        # 从字典中创建一个新的CustomObject实例  
        return AnalysisSecondData(d['symbol'], d['amount'], d['eob'])  

class TestClientUI(QMainWindow):  

    #不知道为啥需要方在这里，放在initUI里面self.就不行
    has_new_data_single = pyqtSignal(bool)
    has_today_history_update_single = pyqtSignal(bool)
    has_init_window_single = pyqtSignal(bool)

    def __init__(self):  
        super().__init__()  
        self.initUI()  
  
    def initUI(self):  
        self.server_sokcet = None

        self.MAX_H_SIZE = 70
        self.MAX_V_SIZE = 85

        self.current_data = None
        self.second_window_dic = dict
        self.window_index = ""
        self.judge_update_comlete_count = 0
        self.last_label_count = 0
        self.set_agility_update_time = 5
        self.sort_time_set = 10
        self.update_scrollArea_current_time = 0
        self.update_scrollArea_last_time = 0
        self.win_list = {}
        self.is_can_statistics = False
        self.is_can_ready_statistics = False

        self.LENGTH_FORMAT = 'I'
        self.current_data_symbol = ''
        self.last_set_red_style_stock = ''
        self.symbol_arr = []
        self.temp_symbol_arr = []
        self.child_widget_arr = []
        self.hh_mm_ss = []
        self.select_stork_list = []

        self.current_data_dic = {}
        self.temp_current_data_dic = {}
        self.history_all_dic = {}
        self.history_today_all_dic = {}
        self.name_dic = {}
        self.agility_data_dic = {}
        self.simple_stock_with_stock = {}

        self.order_widget_dic = {}
        self.onemin_update_widget_dic = {}
        self.onemin_reach_set_widget_dir = {}
        self.agilitymin_update_widget_dic = {}
        self.agilitymin_reach_set_widget_dic = {}

        self.temp_wait_for_update_dic = {}
        self.temp_wait_for_update_list = []
        self.wait_for_update_list = []

        self.is_has_new_data = False
        self.is_has_today_history_data = False
        self.is_in_updating = False
        self.is_complate_all_init = False
        self.is_init_window = False

        self.test_index = 0

        # 定时器，用于刷新scrollbar
        self.timer = 0
        self.timer_init_flag = False

        self.setWindowTitle('VolumeMonitorClient')
        self.setGeometry(400, 400, 800, 600)  

        #初始化窗口内的所有容器 w1-w6
        self.init_widget()

        #连接函数，刷新UI
        self.has_new_data_single.connect(self.update_label_for_single)
        self.has_today_history_update_single.connect(self.init_today_history_for_single)
        self.has_init_window_single.connect(self.init_window)

        self.connect_server()

        # mac_address = self.get_mac_info()
        # # 使用upper()方法转换为大写  
        # mac_address_uppercase = mac_address.upper()  
        # print(f"{mac_address_uppercase}")


    def connect_server(self):
        #"8.137.48.212" - 127.0.0.1 # 线程Server 正式服12345, 调试服12346
        self.send_data_to_server("8.137.48.212", 12346, {"name": "Alice", "message": "Hello, server!"})
 
    def send_data_to_server(self, server_ip, server_port, data):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((server_ip, server_port))

        try:
            #尝试开启线程一直接受服务器响应,用QTread,thread会出问题
            self.rfs_thread = ReciveQThread(client_socket)
            self.rfs_thread.start()

            #尝试开启线程一直向服务器发送请求
            sts_thread = threading.Thread(target = self.send_to_server, args=(client_socket,))
            sts_thread.start()

            #开启心跳线程
            self.heart_thread = SendQThread(client_socket)
            self.heart_thread.start()

            pass

        except ConnectionResetError:
            print("Connection to server was lost.")

        finally:
            #client_socket.close()
            #print(f"client had closed")
            pass

    #获得本机MAC地址
    def get_mac_info(self):
        
        mac = uuid.UUID(int=uuid.getnode()).hex[-12:]  
        return ":".join([mac[e:e+2] for e in range(0, 11, 2)]) 


    def send_to_server(self, client_socket):
        operation_id = 101
        client_socket.sendall(operation_id.to_bytes(4))

        mac_address = self.get_mac_info()
        # 使用upper()方法转换为大写  
        mac_address_uppercase = mac_address.upper()  
        print(f"{mac_address_uppercase}")

        mac_address_json = json.dumps(mac_address_uppercase)
        mac_address_len = len(mac_address_json.encode('utf-8'))
        print(f"cur_len:{mac_address_len}")

        mac_address_len_byte = mac_address_len.to_bytes(4, byteorder='big')
        client_socket.sendall(mac_address_len_byte)

        client_socket.sendall(mac_address_json.encode('utf-8'))

        

    #向服务器发送初始化已完成的片头
    def send_to_server_client_init_complete(self, client_socket):
        operation_id = 103
        client_socket.sendall(operation_id.to_bytes(4))

    #初始化所有容器
    def init_widget(self):

        #主容器
        self.main_window = QWidget()
        self.setCentralWidget(self.main_window)
        self.main_window_layout = QHBoxLayout(self.main_window)
        self.main_window_layout.setSpacing(0)

        #标的代码与名称
        self.w1 = InitChildQwidGet()
        self.w1.overall_widget.setFixedWidth(self.MAX_H_SIZE * 3)
        self.main_window_layout.addWidget(self.w1.overall_widget, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        stock_label = QLabel(f'标的代码', self.w1.up_contnet_widget)
        self.w1.up_contnet_widget_layout.addWidget(stock_label)
        name_label = QLabel(f'名称', self.w1.up_contnet_widget)
        self.w1.up_contnet_widget_layout.addWidget(name_label)
        #____添加w1里最上方的功能模块
        input_box = QLineEdit(self)
        input_box.returnPressed.connect(lambda: self.w1_select_stock(input_box))
        self.w1.top_function_widget_layout.addWidget(input_box)

        #1分钟实时数据
        self.w2 = InitChildQwidGet()
        self.main_window_layout.addWidget(self.w2.overall_widget, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        #向数据刷新子容器添加总容器的伸缩按钮
        btn = QPushButton('S')
        btn.setFixedSize(20,20)
        btn.clicked.connect(lambda: self.on_click_data_update_stretch(self.w2))
        self.w2.up_contnet_widget_layout.addWidget(btn)
        content_label = QLabel(f'1分钟实时数据(9:25--15:30)', self.w2.up_contnet_widget)
        self.w2.up_contnet_widget_layout.addWidget(content_label)

        #1分钟达到预设次数
        self.w3 = InitChildQwidGet()
        self.main_window_layout.addWidget(self.w3.overall_widget, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        btn = QPushButton('S')
        btn.setFixedSize(20,20)
        btn.clicked.connect(lambda: self.on_click_data_update_stretch(self.w3))
        self.w3.up_contnet_widget_layout.addWidget(btn)
        content_label = QLabel(f'1分钟达到预设值次数:{'N'}', self.w3.up_contnet_widget)
        self.w3.up_contnet_widget_layout.addWidget(content_label)

        #灵活分钟刷新
        self.w4 = InitChildQwidGet()
        self.main_window_layout.addWidget(self.w4.overall_widget, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        btn = QPushButton('S')
        btn.setFixedSize(20,20)
        btn.clicked.connect(lambda: self.on_click_data_update_stretch(self.w4))
        self.w4.up_contnet_widget_layout.addWidget(btn)
        content_label = QLabel(f'灵活设置分钟实时数据(9:25--15:30)', self.w4.up_contnet_widget)
        self.w4.up_contnet_widget_layout.addWidget(content_label)

        #灵活分钟刷新，达到预设次数
        self.w5 = InitChildQwidGet()
        self.main_window_layout.addWidget(self.w5.overall_widget, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        btn = QPushButton('S')
        btn.setFixedSize(20,20)
        btn.clicked.connect(lambda: self.on_click_data_update_stretch(self.w5))
        self.w5.up_contnet_widget_layout.addWidget(btn)
        content_label = QLabel(f'灵活分钟达到预设值次数:{'N'}', self.w5.up_contnet_widget)
        self.w5.up_contnet_widget_layout.addWidget(content_label)

        #当日成交额
        self.w6 = InitChildQwidGet()
        self.w6.overall_widget.setFixedWidth(self.MAX_H_SIZE * 2)
        self.main_window_layout.addWidget(self.w6.overall_widget, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        content_label = QLabel(f'当日成交金额', self.w6.up_contnet_widget)
        self.w6.up_contnet_widget_layout.addWidget(content_label)
        
        #将所有容器添加到集合中，方便后续调用
        self.child_widget_arr.append(self.w1)
        self.child_widget_arr.append(self.w2)
        self.child_widget_arr.append(self.w3)
        self.child_widget_arr.append(self.w4)
        self.child_widget_arr.append(self.w5)
        self.child_widget_arr.append(self.w6)

        #同步垂直方向滚动条操作
        self.w1.bottom_scroll_area.verticalScrollBar().valueChanged.connect(self.w2.bottom_scroll_area.verticalScrollBar().setValue)
        self.w2.bottom_scroll_area.verticalScrollBar().valueChanged.connect(self.w1.bottom_scroll_area.verticalScrollBar().setValue)

        self.w2.bottom_scroll_area.verticalScrollBar().valueChanged.connect(self.w3.bottom_scroll_area.verticalScrollBar().setValue)
        self.w3.bottom_scroll_area.verticalScrollBar().valueChanged.connect(self.w2.bottom_scroll_area.verticalScrollBar().setValue)

        self.w3.bottom_scroll_area.verticalScrollBar().valueChanged.connect(self.w4.bottom_scroll_area.verticalScrollBar().setValue)
        self.w4.bottom_scroll_area.verticalScrollBar().valueChanged.connect(self.w3.bottom_scroll_area.verticalScrollBar().setValue)

        self.w4.bottom_scroll_area.verticalScrollBar().valueChanged.connect(self.w5.bottom_scroll_area.verticalScrollBar().setValue)
        self.w5.bottom_scroll_area.verticalScrollBar().valueChanged.connect(self.w4.bottom_scroll_area.verticalScrollBar().setValue)

        self.w5.bottom_scroll_area.verticalScrollBar().valueChanged.connect(self.w6.bottom_scroll_area.verticalScrollBar().setValue)
        self.w6.bottom_scroll_area.verticalScrollBar().valueChanged.connect(self.w5.bottom_scroll_area.verticalScrollBar().setValue)
        
    #自动调整主窗口尺寸变化，恶心至极！！！！！！
    def adjust_window_size(self):
        #要先设置一下，才能重新调整主窗口尺寸，800参数随便多少都可以
        #自动调整窗口尺寸功能，贼TM的恶心！恶心！恶心！！！！！！
        self.resize(800,self.height()) #self.main_window.resize(800,self.height())
        #先设置主窗口固定高度，以避免下方重新调整主窗口尺寸时，窗口高度发生变化
        self.setFixedHeight(self.height())
        #重新调整主窗口尺寸
        self.adjustSize()
        #这里取消掉设置主窗口的固定高度
        self.setMaximumHeight(16777215)
        self.setMinimumHeight(0)

    #伸缩按钮
    def on_click_data_update_stretch(self, overall_widget):
        if overall_widget.is_stretch == False:
            overall_widget.overall_widget.setFixedWidth(self.MAX_H_SIZE * 10) #self.data_update_overall_widget
            overall_widget.is_stretch = True
        else:
            overall_widget.overall_widget.setFixedWidth(self.MAX_H_SIZE * 2)
            overall_widget.is_stretch = False

        self.keep_scroll_bar_right()
        # self.adjust_window_size()

        if (not self.timer_init_flag):
            self.timer_init_flag = True
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.on_time_adjust_window_size)
            self.timer.start(50)

    #w1中，搜索功能添加回车功能
    def w1_select_stock(self, line_edit):

        target_stork = line_edit.text()

        print(f"{target_stork}")

        #将上一个标的的所有widget取消红色边框
        if target_stork in self.simple_stock_with_stock.keys():
            if self.last_set_red_style_stock != '':
                for child_widget in self.child_widget_arr:
                    child_widget.stock_widget_dic[self.last_set_red_style_stock].widget.setStyleSheet("")

        if target_stork in self.simple_stock_with_stock.keys():

            temp_index = 0

            #查看当前选中的标的的widget处于第几个位置
            for item in self.select_stork_list:

                if self.simple_stock_with_stock[target_stork] == item:
                    break

                temp_index += 1

            #这里再加一次1是因为index是从0开始的
            temp_index += 1
            target_height = self.MAX_V_SIZE * temp_index

            self.w1.bottom_scroll_area.verticalScrollBar().setValue(target_height)

            #将选中的标的的widget设置为红色边框
            for child_widget in self.child_widget_arr:
                child_widget.stock_widget_dic[self.simple_stock_with_stock[target_stork]].widget.setStyleSheet("QWidget { border: 1px solid red; }")

            self.last_set_red_style_stock = self.simple_stock_with_stock[target_stork]

    def create_new_window(self, title, w_num):
        return ScrollableLabels(title, w_num)

    #初始化客户端
    def teat_thread_1(self):
        self.init_thread()

    #实时更新数据
    def teat_thread_2(self):
        self.update_label_thread()

    # 定时器更新
    def on_timer(self):
        self.keep_scroll_bar_right()
        self.timer.stop()
        self.timer_init_flag = False
        # print(f"stop timer........")

    #定时器更新伸缩窗口大小
    def on_time_adjust_window_size(self):
        self.adjust_window_size()
        self.timer.stop()
        self.timer_init_flag = False


    #初始化客户端QT线程
    def init_thread(self):  
        # 创建并启动线程  
        self.thread = WorkerThread()  
        self.thread.finished.connect(self.init_window)  
        self.thread.start()  
    #初实时更新数据QT线程，注意不用这个线程更新就无法为UI更新，原因跨线程，暂时不知如何解决!!!!!!!!!!!!!!已解决!!!!!!!!!!!!!!
    def update_label_thread(self):
        self.thread = WorkerThreadUpdateData()  
        self.thread.finished.connect(self.update_label)#self.update_label
        self.thread.start()  

    def init_window(self):
        if len(self.symbol_arr) != 0:
                
                #时间列表,后面判断没有的时间段
                t_hour = 9
                t_min = 15  #30
                t_second = '00'

                temp_hh_mm_ss = ''
                temp_t_hour = ''
                temp_t_min = ''

                for n in range(136):    #121
                    if t_min == 60:
                        t_hour += 1
                        temp_hh_mm_ss = str(t_hour) + ':' + '00' + ':' + str(t_second)
                        t_min = 0
                    else:
                        if len(str(t_hour)) == 1:
                            temp_t_hour = '0'+ str(t_hour)
                        else:
                            temp_t_hour = str(t_hour)

                        if len(str(t_min)) == 1:
                            temp_t_min = '0' + str(t_min)
                        else:
                            temp_t_min = str(t_min)

                        temp_hh_mm_ss = temp_t_hour + ':' + temp_t_min + ':' + str(t_second)

                    self.hh_mm_ss.append(temp_hh_mm_ss)

                    t_min += 1

                t_hour = 13
                t_min = 0

                for n in range(151):
                    if t_min == 60:
                        t_hour += 1
                        temp_hh_mm_ss = str(t_hour) + ':' + '00' + ':' + str(t_second)
                        t_min = 0
                    else:
                        if len(str(t_hour)) == 1:
                            temp_t_hour = '0'+ str(t_hour)
                        else:
                            temp_t_hour = str(t_hour)

                        if len(str(t_min)) == 1:
                            temp_t_min = '0' + str(t_min)
                        else:
                            temp_t_min = str(t_min)

                        temp_hh_mm_ss = temp_t_hour + ':' + temp_t_min + ':' + str(t_second)

                    self.hh_mm_ss.append(temp_hh_mm_ss)

                    t_min += 1

                # for item in hh_mm_ss:
                #     print(f":::::::::{item}")

                #初始化标的代码
                for item in self.symbol_arr:
                    #初始化标的代码与名称刷新容器内容
                    temp_qwidget = QWidget()
                    temp_qwidget.setObjectName(item)
                    temp_qwidget_layout = QHBoxLayout(temp_qwidget)
                    temp_qwidget.setFixedWidth(self.MAX_H_SIZE * 3)
                    temp_qwidget.setFixedHeight(self.MAX_V_SIZE)

                    self.w1.bottom_update_widget_layout.addWidget(temp_qwidget)

                    stock = QLabel(f'{item}', temp_qwidget)  
                    stock.setMinimumWidth(self.MAX_H_SIZE)
                    temp_qwidget_layout.addWidget(stock)

                    self.w1.stock_widget_dic[item] = LabelOrderInfo(item, temp_qwidget, temp_qwidget_layout)
                    # self.w1.stock_widget_dic[item].widget.setObjectName(item)

                    self.init_update_area_widget(item, self.w2)
                    self.init_update_area_widget(item, self.w3)
                    self.init_update_area_widget(item, self.w4)
                    self.init_update_area_widget(item, self.w5)
                    self.init_update_area_widget(item, self.w6)

                    temp_list = []
                    self.agility_data_dic[item] = temp_list

                    self.order_widget_dic[item] = 0

                    print(f"{item}")

                    # print(f"{item[-6:]}")

                    self.simple_stock_with_stock[item[-6:]] = item


                    #获得当前时间
                    # temp_translate_time = datetime.strptime(temp_joint_current_time, "%H:%M:%S").time()
                    # now = datetime.now()  
                    # combined = datetime.combine(now.date(), temp_translate_time)
                    # one_minute_later = combined + timedelta(minutes=1) 
                    # temp_joint_history_time = one_minute_later.strftime("%H:%M:%S")

                    #这里要遍历所有标的的所有历史数据，抓出哪一分钟没有数据，并重新添加空的数据进去
                    #不要在刷新过程中来判断，尽量减少刷新负担。。吧。。
                    for hhmmss in self.hh_mm_ss:
                        if hhmmss not in self.history_all_dic[item].keys():
                            temp_his_date = AnalysisHistoryData(item, 0, hhmmss, 'temp')
                            self.history_all_dic[item][hhmmss] = temp_his_date

                        #补全当日的里数据，因为在single函数里的格式问题，所以要+08:00
                        #这里需要补全到当前分钟数
                        # if hhmmss not in self.history_today_all_dic[item].keys():
                        #     temp_hhmmss ='xxxx-xx-xx ' + hhmmss + '+08:00'
                        #     temp_his_today_data = AnalysisHistoryData(item, 0, temp_hhmmss, 'temp')
                        #     self.history_today_all_dic[item][hhmmss] = temp_his_today_data

                    #初始化所有标的的w6今日所有成交额的cunrrent_label，避免后面再刷新中创建
                    temp_all_day_history_amount = 0.0
                    for key, valume in self.history_all_dic[item].items():
                        temp_all_day_history_amount += float(valume.amount)

                    data_label = self.create_current_label('ALL DAY', temp_all_day_history_amount, '0.0', '0.0', self.w6.stock_widget_dic[item].widget)

                    self.w6.stock_widget_dic[item].layout.addWidget(data_label)
                    self.w6.label_with_time_dic[item].append(data_label)

                    temp_current_label_info = CurrentLabelInfo(data_label, 'ALL DAY', 0.0, temp_all_day_history_amount)
                    self.w6.stock_current_label_dic[item] = temp_current_label_info

                #初始化名称
                for key, valume in self.w1.stock_widget_dic.items():
                        
                    name = QLabel(f'{self.name_dic[key]}', temp_qwidget)  
                    name.setMinimumWidth(self.MAX_H_SIZE)
                    valume.layout.addWidget(name)

                #初始化完成后，向服务器发送已完成消息,现在这个放在了update_label_for_single最后面，以便初始化当日历史数据后再发送
                # self.send_to_server_client_init_complete(self.server_sokcet)
                # print(f"send message to server init client had complate")

                #发出信号，开始初始化今日数据UI
                main_window.is_has_today_history_data = True
                main_window.has_today_history_update_single.emit(main_window.is_has_today_history_data)

    #初始化各个子容器里的各个widget,预装填,方便后续调用
    def init_update_area_widget(self, item, qwidget):
        temp_qwidget = QWidget()
        temp_qwidget_layout = QHBoxLayout(temp_qwidget)
        temp_qwidget.setFixedHeight(self.MAX_V_SIZE)
        qwidget.stock_widget_dic[item] = LabelOrderInfo(item, temp_qwidget, temp_qwidget_layout)
        qwidget.bottom_update_widget_layout.addWidget(temp_qwidget)
        qwidget.label_with_time_dic[item] = []
        qwidget.stock_time_labelinfo_dic[item] = {}

    #当客户端在开盘后开启后，需要在初始化客户端后，再次初始化当日的当前时段之前的所有数据
    def init_today_history_for_single(self):

        print(f"begin to update today history data label")

        print(f"history_today_all_dic length :: {len(self.history_today_all_dic)}")

        print(f"==========================================")

        for key, value in self.history_today_all_dic.items():

            print(f"{key}::length::{len(value)}")

            for item_key, item_value in value.items():

                self.wait_for_update_list.append(item_value)

        main_window.is_has_new_data = True
        main_window.has_new_data_single.emit(main_window.is_has_new_data)
        main_window.is_has_new_data = False


    #跟新横向滚轮条，保持在最右侧
    def keep_scroll_bar_right(self):
        # 设置滚动条到最右侧（这通常在内容完全加载后执行）  
        self.w2.bottom_scroll_area.horizontalScrollBar().setValue(self.w2.bottom_scroll_area.horizontalScrollBar().maximum()) 
        self.w3.bottom_scroll_area.horizontalScrollBar().setValue(self.w3.bottom_scroll_area.horizontalScrollBar().maximum()) 
        self.w4.bottom_scroll_area.horizontalScrollBar().setValue(self.w4.bottom_scroll_area.horizontalScrollBar().maximum()) 
        self.w5.bottom_scroll_area.horizontalScrollBar().setValue(self.w5.bottom_scroll_area.horizontalScrollBar().maximum()) 
        self.w6.bottom_scroll_area.horizontalScrollBar().setValue(self.w6.bottom_scroll_area.horizontalScrollBar().maximum()) 
    
    #on_bar用
    def update_label_date(self, symbol, his_date, cur_date):

        his_d_a = round(float(his_date.amount), 2)
        cur_d_a = round(float(cur_date.amount), 2)

        if his_d_a != 0:
            calculate_percent = round(((float(cur_date.amount) - float(his_date.amount))/float(his_date.amount)) * 100, 2)
        else:
            calculate_percent = 'N'
            
        if calculate_percent == 'N':
            self.order_widget_dic[symbol] = -1000.0
        else:
            self.order_widget_dic[symbol] = calculate_percent

        data_label = QLabel(f'{cur_date.eob}\n{his_d_a}\n{cur_d_a}\n{calculate_percent}%', self.main_window)  
        data_label.setMinimumHeight(self.MAX_V_SIZE)  
        data_label.setMinimumWidth(self.MAX_H_SIZE)

        self.w2.stock_widget_dic[symbol].layout.addWidget(data_label)

        if calculate_percent != 'N':
            if float(calculate_percent) >= float(50):
                temp_data_label = QLabel(f'{cur_date.eob}\n{his_d_a}\n{cur_d_a}\n{calculate_percent}%', self.main_window)  
                temp_data_label.setMinimumHeight(self.MAX_V_SIZE)  
                temp_data_label.setMinimumWidth(self.MAX_H_SIZE)
                self.w3.stock_widget_dic[symbol].layout.addWidget(temp_data_label)

        #对灵活分钟数相关计算 ======================
        # temp_atsi = AgilityTimeStorkInfo(symbol, his_d_a, cur_d_a, cur_date.eob)
        # self.agility_data_dic[symbol].append(temp_atsi)

        #==后面的值，例如2就是统计2分钟内的，如果是5就是溶剂5分钟内的每分钟相加的成交额
        #后面需要再UI上做成可手动设置的值
        #灵活设置需要以预设值倍数的方式开始统计
        #例如设置5分钟，统计的数据就需要是第00-05分，或者10-15分 这样
        #例如设置3分钟，统计的数据就需要是第00-03分，或者03-06，或者06-09，或者09-12 这样

        get_now = datetime.now()
        get_now_min = get_now.minute

        temp_is_can = (get_now_min - 1) % self.set_agility_update_time

        print(f"{get_now_min}")
        print(f"{get_now_min}")
        print(f"{temp_is_can}|{self.is_can_ready_statistics}|{self.is_can_statistics}")
        print(f"{temp_is_can}|{self.is_can_ready_statistics}|{self.is_can_statistics}")

        #这里判断灵活设置开始搜集数据，当达到设置分钟要求时，应该是这里判断可以开始搜集数据
        #然后需要运行到下一轮，搜集下一分钟的数据开始
        #例如设置为5分钟搜集一轮，当此刻为10：05分时候，就会开启准备搜集，下一分钟10:06开始真正装入数据
        # if self.is_can_ready_statistics == True:
        #     self.is_can_statistics = True

        # if temp_is_can == 0 and self.is_can_ready_statistics == False:
        #     self.is_can_ready_statistics = True

        if temp_is_can == 0 and self.is_can_statistics == False:
            self.is_can_statistics = True

        if self.is_can_statistics == True:
            temp_atsi = AgilityTimeStorkInfo(symbol, his_d_a, cur_d_a, cur_date.eob)
            self.agility_data_dic[symbol].append(temp_atsi)
        
        if len(self.agility_data_dic[symbol]) == self.set_agility_update_time:
            temp_c_d = 0.0
            temp_h_d = 0.0
            temp_e = None

            temp_index = 0

            for item in self.agility_data_dic[symbol]:
                temp_index += 1
                temp_h_d += float(item.his_data)
                temp_c_d += float(item.cur_data)

                #注意这里的值需要与灵活设置的分钟数一致,以便获取最后一分钟刷新时间
                if temp_index == self.set_agility_update_time:
                    temp_e = item.eob

            if temp_h_d != 0:
                agility_calculate_percent = round(((float(temp_c_d) - float(temp_h_d))/float(temp_h_d)) * 100, 2)
            else:
                agility_calculate_percent = 'N'

            #为灵活刷新添加数据label
            temp_data_label = QLabel(f'{temp_e}\n{temp_h_d}\n{temp_c_d}\n{agility_calculate_percent}%', self.main_window)  
            temp_data_label.setMinimumHeight(self.MAX_V_SIZE)  
            temp_data_label.setMinimumWidth(self.MAX_H_SIZE)
            self.w4.stock_widget_dic[symbol].layout.addWidget(temp_data_label)

            #结束后重置灵活刷新dic，以便下一次的统计
            self.agility_data_dic[symbol].clear()
            # self.is_can_statistics = False

            #为达到目标的灵活数据添加label
            if agility_calculate_percent != 'N':
                if float(agility_calculate_percent) >= float(100):
                    temp_data_label = QLabel(f'{cur_date.eob}\n{his_d_a}\n{cur_d_a}\n{agility_calculate_percent}%', self.main_window)  
                    temp_data_label.setMinimumHeight(self.MAX_V_SIZE)  
                    temp_data_label.setMinimumWidth(self.MAX_H_SIZE)
                    self.w5.stock_widget_dic[symbol].layout.addWidget(temp_data_label)
        #==========================================

        if calculate_percent == 'N':
            data_label.setStyleSheet('QLabel { color: grey; }')
        elif calculate_percent > 0:
            data_label.setStyleSheet('QLabel { color: red; }')  
        elif calculate_percent < 0:
            data_label.setStyleSheet('QLabel { color: green; }')  
        
        if int(his_date.amount) == 0:
            data_label.setStyleSheet('QLabel { color: blue; }')
        if int(cur_date.amount) == 0:
            data_label.setStyleSheet('QLabel { color: grey; }')

        if cur_d_a != 0:
            print(f"%:{(int(cur_date.amount) - int(his_date.amount))/int(cur_date.amount)}")
        else:
            print(f"N")
        
        print(f"{cur_date.symbol}: update label success")

        self.judge_update_comlete_count += 1
        print(f"self.judge_update_comlete_count:{self.judge_update_comlete_count}")
        if self.judge_update_comlete_count == len(self.symbol_arr):

            #重新排序，从高往下，当calculate为N时，暂时将数值设置为-1000.0
            sorted_items_desc = sorted(self.order_widget_dic.items(), key=lambda item: item[1], reverse=True)

            for key, val in sorted_items_desc:
                print(f"{key}|{val}")

            for child_widget in self.child_widget_arr:

                for key, val in child_widget.stock_widget_dic.items():
                    # 先移除widget，用于后面重新添加排序后得内容
                    child_widget.bottom_update_widget_layout.removeWidget(val.widget)

                #重新添加排序过后的widget
                for key, val in sorted_items_desc:
                    child_widget.bottom_update_widget_layout.addWidget(child_widget.stock_widget_dic[key].widget)

            self.judge_update_comlete_count = 0

    #计算百分比
    def calculate_percent_mathod(self, history_data, current_data):

        if history_data != 0:
            calculate_percent = round(((float(current_data) - float(history_data))/float(history_data)) * 100, 2)
        else:
            calculate_percent = 'N'

        return calculate_percent

    #创建当下需要操作的label
    def create_current_label(self, cur_time, his_data, cur_data, percent, parent_widget):
            data_label = QLabel(f'{cur_time}\n{his_data}\n{cur_data}\n{percent}%', parent_widget)  
            data_label.setMinimumHeight(self.MAX_V_SIZE)  
            data_label.setMinimumWidth(self.MAX_H_SIZE)

            return data_label
    #on_tick用
    def update_label_date_for_second(self, symbol, his_date, cur_date):

        # print(f"cur_date.eob::{cur_date.eob}")

        his_d_a = round(float(his_date.amount), 2)
        cur_d_a = round(float(cur_date.amount), 2)

        calculate_percent = self.calculate_percent_mathod(his_date.amount, cur_date.amount)

        #这里为重新排序记录的数据，移动到w6里，根据w6排序
        # if calculate_percent == 'N':
        #     self.order_widget_dic[symbol] = -1000.0
        # else:
        #     self.order_widget_dic[symbol] = calculate_percent

        #===============================================

        #在这里设置一个临时变量，用于获取w2里面的当前时间，方便后面在w4里排序
        temp_w2_last_time = ''

        #这里not in用于刚打开客户端，第一次当前label的添加
        if symbol not in self.w2.stock_current_label_dic.keys():

            data_label = self.create_current_label(cur_date.eob, his_d_a, cur_d_a, calculate_percent, self.w2.stock_widget_dic[symbol].widget)

            self.w2.stock_widget_dic[symbol].layout.addWidget(data_label)
            self.w2.label_with_time_dic[symbol].append(data_label)
            

            temp_current_label_info = CurrentLabelInfo(data_label, cur_date.eob, cur_d_a, his_d_a)
            self.w2.stock_current_label_dic[symbol] = temp_current_label_info
            self.w2.stock_time_labelinfo_dic[symbol][cur_date.eob] = temp_current_label_info

        #更新当前分钟数的label
        elif self.w2.stock_current_label_dic[symbol].current_time != cur_date.eob:

            #这里需要补全灵活分钟label,例如40分到41分，有些票来数据，就会添加灵活分钟当前label
            #有些票如果这一分钟没来数据，到下一分钟41分后来，就会创建41-46(例灵活时间为5分钟)
            #需要在这里补全

            #创建新的当前label
            data_label = self.create_current_label(cur_date.eob, his_d_a, cur_d_a, calculate_percent, self.w2.stock_widget_dic[symbol].widget)

            self.w2.stock_widget_dic[symbol].layout.addWidget(data_label)
            self.w2.label_with_time_dic[symbol].append(data_label)

            temp_last_time = self.w2.stock_current_label_dic[symbol].current_time
            temp_last_cur_amount = self.w2.stock_current_label_dic[symbol].amount
            temp_last_his_amount = self.w2.stock_current_label_dic[symbol].history_amount

            #这里对w2的临时变量赋值,用于w4尾巴上的else里
            temp_w2_last_time = self.w2.stock_current_label_dic[symbol].current_time

            #1分钟到达预设值，添加到w3
            temp_last_calculate_percent = self.calculate_percent_mathod(temp_last_his_amount, temp_last_cur_amount)

            #重新排序=======================
            #这里记录每一次灵活设置切换到下一阶段时，上一阶段的值，以便后面排序
            #这里需要改成1分钟重新排序，把这个搬到上面w2里面，试试
            #这里还需要改，更改为根据灵活数据，每分钟拍一次序,把这个放到w4最后的else里面试试
            # if temp_last_calculate_percent == 'N':
            #     self.order_widget_dic[symbol] = -1000.0
            # else:
            #     self.order_widget_dic[symbol] = temp_last_calculate_percent

            if temp_last_calculate_percent != 'N':
                #float后面的50后面需要改为在ui上可设置
                if float(temp_last_calculate_percent) >= float(1000):

                    temp_last_data_label = self.create_current_label(temp_last_time, temp_last_his_amount, temp_last_cur_amount, temp_last_calculate_percent, self.w3.stock_widget_dic[symbol].widget)

                    self.w3.stock_widget_dic[symbol].layout.addWidget(temp_last_data_label)

                    #重新排序
                    # sorted_items_desc = sorted(self.order_widget_dic.items(), key=lambda item: item[1], reverse=True)

                    # for child_widget in self.child_widget_arr:

                    #     for key, val in child_widget.stock_widget_dic.items():
                    #         # 先移除widget，用于后面重新添加排序后得内容
                    #         child_widget.bottom_update_widget_layout.removeWidget(val.widget)

                    #     #重新添加排序过后的widget
                    #     for key, val in sorted_items_desc:
                    #         child_widget.bottom_update_widget_layout.addWidget(child_widget.stock_widget_dic[key].widget)

            # temp_current_label_info = CurrentLabelInfo(data_label, cur_date.eob, cur_d_a, his_d_a)
            self.w2.stock_current_label_dic[symbol] = CurrentLabelInfo(data_label, cur_date.eob, cur_d_a, his_d_a)
            self.w2.stock_time_labelinfo_dic[symbol][cur_date.eob] = CurrentLabelInfo(data_label, cur_date.eob, cur_d_a, his_d_a)

        #实时更新当前label中的amount
        else:
            #当前成交额与上一此成交相加，得到当前总共成交额
            # temp_current_amount = round(float(self.w2.stock_current_label_dic[symbol].amount + cur_d_a), 2)
            temp_current_amount = round(float(self.w2.stock_time_labelinfo_dic[symbol][cur_date.eob].amount + cur_d_a), 2)
            #重新赋值，以便再次计算
            self.w2.stock_current_label_dic[symbol].amount = temp_current_amount
            self.w2.stock_time_labelinfo_dic[symbol][cur_date.eob].amount = temp_current_amount

            calculate_percent = self.calculate_percent_mathod(his_date.amount, temp_current_amount)
            #更新label
            # self.w2.stock_current_label_dic[symbol].label.setText(f'{cur_date.eob}\n{his_d_a}\n{temp_current_amount}\n{calculate_percent}%')
            self.w2.stock_time_labelinfo_dic[symbol][cur_date.eob].label.setText(f'{cur_date.eob}\n{his_d_a}\n{temp_current_amount}\n{calculate_percent}%')

        #根据百分比设置label颜色
        if calculate_percent == 'N':
            self.w2.stock_current_label_dic[symbol].label.setStyleSheet('QLabel { color: grey; }')
        elif calculate_percent > 0:
            self.w2.stock_current_label_dic[symbol].label.setStyleSheet('QLabel { color: red; }')  
        elif calculate_percent < 0:
            self.w2.stock_current_label_dic[symbol].label.setStyleSheet('QLabel { color: green; }')  
        #根据历史数据设置label颜色
        if int(his_date.amount) == 0:
            self.w2.stock_current_label_dic[symbol].label.setStyleSheet('QLabel { color: blue; }')
        if self.w2.stock_current_label_dic[symbol].amount == 0:
            self.w2.stock_current_label_dic[symbol].label.setStyleSheet('QLabel { color: grey; }')

        
        #对灵活分钟数相关计算 ===============================================
        # temp_atsi = AgilityTimeStorkInfo(symbol, his_d_a, cur_d_a, cur_date.eob)
        # self.agility_data_dic[symbol].append(temp_atsi)

        #==后面的值，例如2就是统计2分钟内的，如果是5就是溶剂5分钟内的每分钟相加的成交额
        #后面需要再UI上做成可手动设置的值
        #灵活设置需要以预设值倍数的方式开始统计
        #例如设置5分钟，统计的数据就需要是第00-05分，或者10-15分 这样
        #例如设置3分钟，统计的数据就需要是第00-03分，或者03-06，或者06-09，或者09-12 这样

        #正式盘用=================
        # get_now = datetime.now()
        # get_now_hour = get_now.hour
        # get_now_min = get_now.minute
        # get_now_second = '00'

        #关盘后，模拟用============正式盘好像也可以用
        get_now = cur_date.eob
        get_now_time_arr = get_now.split(":")
        get_now_hour = get_now_time_arr[0]
        get_now_min = get_now_time_arr[1]
        get_now_second = '00'
        get_now_second_for_sort = get_now_time_arr[2]

        #print(f"{get_now_hour}:::{get_now_min}")

        #on_bar 调用时:get_now_min - 1

        temp_is_can = 1

        #这里判断灵活设置开始搜集数据，当达到设置分钟要求时，应该是这里判断可以开始搜集数据
        #然后需要运行到下一轮，搜集下一分钟的数据开始
        #例如设置为5分钟搜集一轮，当此刻为10：05分时候，就会开启准备搜集，下一分钟10:06开始真正装入数据
        #此段注释用于on_bar。on_tick逻辑变了
        #本来想法是只创建9：30分以后的label，这里有问题，但不影响，后面可以来改
        if datetime.strptime(cur_date.eob, "%H:%M:%S").time() >= datetime.strptime('09:30:00', "%H:%M:%S").time():

            if (int(get_now_min) - 1) == 0:
                    temp_is_can = 0
            else:
                temp_is_can = (int(get_now_min) - 1) % self.set_agility_update_time


        #这里需要分情况进入灵活运算里面，当初始化当日数据时候，当实时运算时
        if self.is_can_statistics == True and symbol in self.w4.stock_current_label_dic.keys():
            # if self.is_complate_all_init == True:
            #     is_can_in_agility = datetime.strptime(cur_date.eob, "%H:%M:%S").time() >= datetime.strptime(self.w4.stock_current_label_dic[symbol].current_time, "%H:%M:%S").time()
            # else:
            #     is_can_in_agility = datetime.strptime(cur_date.eob, "%H:%M:%S").time() > datetime.strptime(self.w4.stock_current_label_dic[symbol].current_time, "%H:%M:%S").time()

            is_can_in_agility = datetime.strptime(cur_date.eob, "%H:%M:%S").time() > datetime.strptime(self.w4.stock_current_label_dic[symbol].current_time, "%H:%M:%S").time()

        if temp_is_can == 0 and self.is_can_statistics == False:
            self.is_can_statistics = True

        if self.is_can_statistics == True:
        
            #创建此灵活时间段的label
            if symbol not in self.w4.stock_current_label_dic.keys():
                
                #当该标的，已经过了创建灵活时间的正确时间段后，从其他标的处，获取正确的创建时间
                #这里重新改，应该是当is_can_statistics = True时，代表已经开始收集灵活时间数据，
                #不从其他标的获取，根据设置的灵活时间，往前遍历判断正确的时间
                if temp_is_can != 0:

                    temp_temp_is_can = -1

                    get_right_cur_time = int(get_now_min)

                    for i in range(self.set_agility_update_time):

                        if get_right_cur_time - i == 0:
                            temp_temp_is_can = 0
                        else:
                            temp_temp_is_can = (get_right_cur_time - i) % self.set_agility_update_time

                        if (temp_temp_is_can == 0):
                            get_right_cur_time = get_right_cur_time - i
                            break

                agility_history_total_amount = 0.0
                temp_time_str = ''

                #temp_next_min = get_right_cur_time
                if temp_is_can != 0:
                    temp_next_min = int(get_right_cur_time) + 1
                else:
                    temp_next_min = int(get_now_min)

                temp_next_min_to_str = ''

                #遍历根据设置的灵活时间，获取后几分钟的历史数据
                for i in range(self.set_agility_update_time):

                    #实时运算时，这里要先算，历史数据运算时候，要后算，因为
                    #例如实时是10:25:01秒就会进这里，历史是10:26:00进这里
                    #这里可能不需要了，因为现在例如10:25:01秒的数据，会被设定为10:26:00时间
                    # if self.is_complate_all_init == True:
                    #     temp_next_min += 1

                    #当时间在0-9分钟时，需要在前面加上0，例如1--01， 3--03
                    if len(str(temp_next_min)) == 1:
                        temp_next_min_to_str = '0' + str(temp_next_min)
                    else:
                        temp_next_min_to_str = str(temp_next_min)

                    if temp_next_min == 60:
                        temp_get_now_hour = int(get_now_hour) + 1
                        temp_next_min = 0 

                        temp_time_str = str(temp_get_now_hour) + ":" + "00" + ":" + str(get_now_second)
                    else:
                        temp_time_str = str(get_now_hour) + ":" + temp_next_min_to_str + ":" + str(get_now_second)

                    # temp_time_str = str(get_now_hour) + ":" + temp_next_min_to_str + ":" + str(get_now_second)

                    # print(f"temp_next_min_to_str::{temp_next_min_to_str}|||one amount::{self.history_all_dic[symbol][temp_time_str].amount}")

                    agility_history_total_amount += float(self.history_all_dic[symbol][temp_time_str].amount)

                    # if self.is_complate_all_init == False:
                    #     temp_next_min += 1

                    temp_next_min += 1

                # print(f"agility_total_amount:::{agility_history_total_amount}")

                agility_calculate_percent = self.calculate_percent_mathod(agility_history_total_amount, cur_d_a)

                temp_agility_data_label  = self.create_current_label(temp_time_str, agility_history_total_amount, cur_d_a, agility_calculate_percent, self.w4.stock_widget_dic[symbol].widget)

                self.w4.stock_widget_dic[symbol].layout.addWidget(temp_agility_data_label)

                self.w4.stock_current_label_dic[symbol] = CurrentLabelInfo(temp_agility_data_label, temp_time_str, cur_d_a, agility_history_total_amount)
                self.w4.stock_time_labelinfo_dic[symbol][cur_date.eob] = CurrentLabelInfo(temp_agility_data_label, temp_time_str, cur_d_a, agility_history_total_amount)
                
            # 灵活时间，由此时段，进入下一时段，！！这里后期想办法简化下！！     >=
            # datetime.strptime(cur_date.eob, "%H:%M:%S").time() > datetime.strptime(self.w4.stock_current_label_dic[symbol].current_time, "%H:%M:%S").time()
            elif is_can_in_agility == True and datetime.strptime(cur_date.eob, "%H:%M:%S").time() != datetime.strptime('11:30:00', "%H:%M:%S").time():
                
                #可以尝试在这里补全，避免在w2里补全
                #这里需要补全灵活分钟label,例如40分到41分，有些票来数据，就会添加灵活分钟当前label
                #有些票如果这一分钟没来数据，到下一分钟41分后来，就会创建41-46(例灵活时间为5分钟)
                #需要在这里补全
                #这里重新改，应该是当is_can_statistics = True时，代表已经开始收集灵活时间数据，
                #不从其他标的获取，根据设置的灵活时间，往前遍历判断正确的时间
                #这里有问题，当例如11 21 或31 等等 没有数据时候 就会出错
                if temp_is_can != 0:

                    temp_temp_is_can = -1

                    get_right_cur_time = int(get_now_min)

                    print(f"get_now_min::{get_now_min}")

                    for i in range(self.set_agility_update_time):

                        if get_right_cur_time - i == 0:
                            temp_temp_is_can = 0
                        else:
                            temp_temp_is_can = (get_right_cur_time - i) % self.set_agility_update_time

                        if (temp_temp_is_can == 0):
                            get_right_cur_time = get_right_cur_time - i
                            
                            print(f"get_right_cur_time:::{get_right_cur_time}")

                            break

                #将上一条数据拿出，判断是否达到预设值，达到则添加
                temp_last_time = self.w4.stock_current_label_dic[symbol].current_time
                temp_last_cur_amount = self.w4.stock_current_label_dic[symbol].amount
                temp_last_his_amount = self.w4.stock_current_label_dic[symbol].history_amount

                #灵活分钟到达预设值，添加到w5
                temp_last_calculate_percent = self.calculate_percent_mathod(temp_last_his_amount, temp_last_cur_amount)

                #重新排序=====================================================================================

                #这里达到预设值，将显示在UI上
                if temp_last_calculate_percent != 'N':
                    #float后面的50后面需要改为在ui上可设置
                    if float(temp_last_calculate_percent) >= float(1000):
                        temp_last_data_label = self.create_current_label(temp_last_time, round(float(temp_last_his_amount), 2), temp_last_cur_amount, temp_last_calculate_percent, self.w5.stock_widget_dic[symbol].widget)
                        
                        self.w5.stock_widget_dic[symbol].layout.addWidget(temp_last_data_label)

                #创建当前灵活时段
                agility_history_total_amount = 0.0
                temp_time_str = ''

                #当没有处于正确的时间创建，就需要找到正确的时间，例如5分钟灵活，此刻为41分钟，就需要找到第40分钟
                #这里的话，需要在13:00:00插入一个值为0的进入history以及today_history里，正常运行时间不会出错，但是初始化今天历史数据，就会出错
                #temp_next_min = get_right_cur_time
                if temp_is_can != 0:
                    temp_next_min = int(get_right_cur_time) + 1
                    print(f"temp_next_min:::{temp_next_min}")
                else:
                    temp_next_min = int(get_now_min)
                    

                for i in range(self.set_agility_update_time):

                    #实时运算时，这里要先算，历史数据运算时候，要后算，因为
                    #例如实时是10:25:01秒就会进这里，历史是10:26:00进这里
                    #这里可能不需要了，因为现在例如10:25:01秒的数据，会被设定为10:26:00时间
                    # if self.is_complate_all_init == True:
                    #     temp_next_min += 1

                    #当时间在0-9分钟时，需要在前面加上0，例如1--01， 3--03
                    if len(str(temp_next_min)) == 1:
                        temp_next_min_to_str = '0' + str(temp_next_min)
                    else:
                        temp_next_min_to_str = str(temp_next_min)

                    if temp_next_min == 60:
                        temp_get_now_hour = int(get_now_hour) + 1
                        temp_next_min = 0 

                        temp_time_str = str(temp_get_now_hour) + ":" + "00" + ":" + str(get_now_second)
                    else:
                        temp_time_str = str(get_now_hour) + ":" + temp_next_min_to_str + ":" + str(get_now_second)

                    agility_history_total_amount += float(self.history_all_dic[symbol][temp_time_str].amount)

                    temp_next_min += 1

                # print(f"agility_total_amount:::{agility_history_total_amount}")

                agility_calculate_percent = self.calculate_percent_mathod(agility_history_total_amount, cur_d_a)

                temp_agility_data_label  = self.create_current_label(temp_time_str, agility_history_total_amount, cur_d_a, agility_calculate_percent, self.w4.stock_widget_dic[symbol].widget)

                self.w4.stock_widget_dic[symbol].layout.addWidget(temp_agility_data_label)

                self.w4.stock_current_label_dic[symbol] = CurrentLabelInfo(temp_agility_data_label, temp_time_str, cur_d_a, agility_history_total_amount)
                self.w4.stock_time_labelinfo_dic[symbol][cur_date.eob] = CurrentLabelInfo(temp_agility_data_label, temp_time_str, cur_d_a, agility_history_total_amount)
                
            #为这一灵活时间段，持续跟新
            else:

                #当前成交额与上一此成交相加，得到当前总共成交额
                temp_agility_current_amount = round(float(self.w4.stock_current_label_dic[symbol].amount + cur_d_a), 2)
                #重新赋值，以便再次计算
                self.w4.stock_current_label_dic[symbol].amount = temp_agility_current_amount

                calculate_percent = self.calculate_percent_mathod(self.w4.stock_current_label_dic[symbol].history_amount, temp_agility_current_amount)
                #更新label
                self.w4.stock_current_label_dic[symbol].label.setText(f'{self.w4.stock_current_label_dic[symbol].current_time}\n{round(float(self.w4.stock_current_label_dic[symbol].history_amount), 2)}\n{temp_agility_current_amount}\n{calculate_percent}%')

                #每分钟排序放到这里来试试--- and self.is_complate_all_init == True
                if temp_w2_last_time != cur_date.eob:

                    if calculate_percent == 'N':
                        self.order_widget_dic[symbol] = -1000.0
                    else:
                        self.order_widget_dic[symbol] = calculate_percent

                    if calculate_percent != 'N' and int(calculate_percent) >= 500:
                        #重新排序
                        sorted_items_desc = sorted(self.order_widget_dic.items(), key=lambda item: item[1], reverse=True)

                        temp_for_select_stork_index = 0
                        self.select_stork_list.clear()

                        for child_widget in self.child_widget_arr:

                            for key, val in child_widget.stock_widget_dic.items():
                                # 先移除widget，用于后面重新添加排序后得内容
                                child_widget.bottom_update_widget_layout.removeWidget(val.widget)

                            #重新添加排序过后的widget
                            for key, val in sorted_items_desc:
                                child_widget.bottom_update_widget_layout.addWidget(child_widget.stock_widget_dic[key].widget)

                                if temp_for_select_stork_index == 0:
                                    self.select_stork_list.append(key)

                            temp_for_select_stork_index += 1



        #根据百分比设置label颜色
        #灵活设置时间的label颜色，先放在这里，不然会报错, 第一次加入的label没有颜色，要在上面的elif里面加上才有，暂时这样吧
        #这里要改好的话，放在else外面，并附加判断是否有当前时段的label
        if symbol in self.w4.stock_current_label_dic.keys(): 

            if calculate_percent == 'N':
                self.w4.stock_current_label_dic[symbol].label.setStyleSheet('QLabel { color: grey; }')
            elif calculate_percent > 0:
                self.w4.stock_current_label_dic[symbol].label.setStyleSheet('QLabel { color: red; }')  
            elif calculate_percent < 0:
                self.w4.stock_current_label_dic[symbol].label.setStyleSheet('QLabel { color: green; }')  
            #根据历史数据设置label颜色
            if self.w4.stock_current_label_dic[symbol].amount == 0:
                self.w4.stock_current_label_dic[symbol].label.setStyleSheet('QLabel { color: grey; }')


        #当日所有成交额刷新
        temp_all_day_current_amount = round(float(self.w6.stock_current_label_dic[symbol].amount + cur_d_a), 2)

        #重新赋值，以便再次计算
        self.w6.stock_current_label_dic[symbol].amount = temp_all_day_current_amount

        temp_all_day_calculate_percent = self.calculate_percent_mathod(self.w6.stock_current_label_dic[symbol].history_amount, temp_all_day_current_amount)

        self.w6.stock_current_label_dic[symbol].label.setText(f'ALL DAY\n{round(float(self.w6.stock_current_label_dic[symbol].history_amount), 2)}\n{temp_all_day_current_amount}\n{temp_all_day_calculate_percent}%')

        print(f"{cur_date.symbol}: update label success")


    #on_bar用
    def update_label(self):

        now_time = None
        for item in main_window.symbol_arr:
            temp_current_time_arr = self.current_data_dic[item].eob.split(" ")
            temp_c_hour_arr = temp_current_time_arr[1].split("+")
            now_time = temp_c_hour_arr[0]
            break

        for item in main_window.symbol_arr:

            temp_one_his = None
            is_matching = False

            #获得数据时间
            temp_current_time_arr = self.current_data_dic[item].eob.split(" ")
            temp_c_hour_arr = temp_current_time_arr[1].split("+")

            temp_his_hour_arr = []
            
            #分解日期，提取时间，hh-mm-ss
            for one_his in self.history_all_dic[item]:

                temp_history_time_arr = one_his.eob.split(" ")
                temp_h_hour_arr = temp_history_time_arr[1].split("+")

                if temp_c_hour_arr[0] == temp_h_hour_arr[0]:
                    self.current_data_dic[item].eob = temp_c_hour_arr[0]
                    temp_one_his = one_his

                    is_matching = True
                    #for on_bar
                    #self.update_label_date(item, temp_one_his, self.current_data_dic[item])
                    #for on_tick
                    self.update_label_date_for_second(item, temp_one_his, self.current_data_dic[item])
                    break

            #当前历史时段如果没有匹配上时，说明历史里的没有当前时段的数据，抓出没有匹配上的那个时段上的时间
            if is_matching == False:

                #赋予历史数据中没有的当前时段的数据，然后更新UI，以防止UI少更新一次Label
                if temp_c_hour_arr[0] not in temp_his_hour_arr:
                    self.current_data_dic[item].eob = now_time
                    #self.current_data_dic[item].eob - temp_c_hour_arr[0]
                    temp_his_date = AnalysisHistoryData(item, 0, self.current_data_dic[item].eob, 'temp')
                    #for on_bar
                    # self.update_label_date(item, temp_his_date, self.current_data_dic[item])
                    #for on_tick
                    self.update_label_date_for_second(item, temp_his_date, self.current_data_dic[item])

        if (not self.timer_init_flag):
            self.timer_init_flag = True
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.on_timer)
            self.timer.start(50)

        main_window.temp_symbol_arr.clear()
    #on_tick用
    def update_label_for_single(self):

        now_time_h = None
        now_time_m = None
        now_time_s = None
        now_time = None

        temp_symbol = ' '

        # t = time.time()
        
        # print(f"self.wait_for_update_list length::{len(self.wait_for_update_list)}")
        
        temp_index = 0

        # print(f"ReciveClientThreadC----总耗时为01:{time.time()-t:4f}s")

        if len(self.wait_for_update_list) > 0:

            for item in self.wait_for_update_list:

                if item != None and item.eob != None:
                
                    # print(f"{item}")

                    temp_current_time_arr = item.eob.split(" ")
                    temp_c_hour_arr = temp_current_time_arr[1].split("+")
                    temp_int_c_hour_arr = temp_c_hour_arr[0].split(".")
                    temp_h_m_s = temp_int_c_hour_arr[0].split(":")

                    now_time_h = temp_h_m_s[0]
                    now_time_m = temp_h_m_s[1]
                    now_time_s = temp_h_m_s[2]

                    temp_one_his = None
                    #用于每分钟刷新滚动条
                    self.update_scrollArea_current_time = int(now_time_m)

                    temp_joint_current_time = now_time_h + ":" + now_time_m + ":" + "00"

                    item.eob = temp_joint_current_time
                    #datetime.strptime(cur_date.eob, "%H:%M:%S").time()
                    #这里的历史时间应该根据当前时间加一分钟，不然1分钟的对比显示是有误的(以当前分钟对比历史中下一分钟)
                    temp_translate_time = datetime.strptime(temp_joint_current_time, "%H:%M:%S").time()
                    now = datetime.now()  
                    combined = datetime.combine(now.date(), temp_translate_time)
                    one_minute_later = combined + timedelta(minutes=1) 
                    temp_joint_history_time = one_minute_later.strftime("%H:%M:%S")

                    temp_judge_cur = datetime.strptime(temp_joint_history_time, "%H:%M:%S").time()
                    temp_judge_s = datetime.strptime('11:30:00', "%H:%M:%S").time()
                    temp_judge_e = datetime.strptime('13:00:00', "%H:%M:%S").time()

                    #防止超过11:30:00报错，尝试中。。。
                    if temp_judge_cur > temp_judge_s and temp_judge_cur < temp_judge_e:
                        temp_joint_history_time = str(datetime.strptime('11:30:00', "%H:%M:%S").time())

                    #这里实施刷新的时候，需要在当时分钟数+1，例如13:01:03的数据，应该是13:02:00的数据
                    #13：01分---13:02分 叫做13点2分数据
                    #这里需要注意一下，current_time和history_time是相反的，实时更新的时候，用的是history_time
                    if self.is_complate_all_init == True:
                        item.eob = temp_joint_history_time
                    else:
                        item.eob = temp_joint_current_time

                    #这里需要判断是否在初始化中,如果初始化未完成，则会去拿11：31：00的历史数据，就会报错
                    #这里依然在报错，记得来改
                    if self.is_complate_all_init == True:
                        temp_one_his = self.history_all_dic[item.symbol][str(temp_joint_history_time)]
                    else:
                        temp_one_his = self.history_all_dic[item.symbol][str(temp_joint_current_time)]

                    # temp_one_his = self.history_all_dic[item.symbol][str(temp_joint_current_time)]
                    
                    self.update_label_date_for_second(item.symbol, temp_one_his, item)
                    temp_symbol = item.symbol

                    temp_index += 1

        #等待列表中更新完后，清空列表
        self.wait_for_update_list.clear()

        #耗时测试
        # print(f"ReciveClientThreadC----总耗时为02:{time.time()-t:4f}s")

        #用于刷新滚动条,注意！这里00分钟的时候不会刷新,现在为1分钟刷新
        if int(self.update_scrollArea_current_time) > int(self.update_scrollArea_last_time):

            if temp_symbol != ' ' and self.is_complate_all_init == True:

                if self.last_label_count != len(self.w2.label_with_time_dic[temp_symbol]):

                    if (not self.timer_init_flag):
                        self.timer_init_flag = True
                        self.timer = QTimer(self)
                        self.timer.timeout.connect(self.on_timer)
                        self.timer.start(50)

                    self.last_label_count = len(self.w2.label_with_time_dic[temp_symbol])

        self.update_scrollArea_last_time = self.update_scrollArea_current_time

        #初次更新，进这里
        if self.is_complate_all_init == False:
            #这个time.sleep用于模拟数据量过大，导致的卡顿，没事别打开
            # time.sleep(2)
            self.send_to_server_client_init_complete(self.server_sokcet)
            print(f"send message to server init client had complate")
            self.is_complate_all_init = True

            # for key, valume in self.w2.stock_time_labelinfo_dic.items():
            #     for kk, vv in valume.items():
            #         print(f"symbol::{key}||eob::{kk}||amount::{vv.amount}")
            #     print(f"========================================================================")

        self.test_index += 1
        # print(f"self.test_index::{self.test_index}")

        #跟新滚动条
        #初始化完成之前，不做这个, 搬到上面去
        # if temp_symbol != ' ' and self.is_complate_all_init == True:

        #     if self.last_label_count != len(self.w2.label_with_time_dic[temp_symbol]):

        #         if (not self.timer_init_flag):
        #             self.timer_init_flag = True
        #             self.timer = QTimer(self)
        #             self.timer.timeout.connect(self.on_timer)
        #             self.timer.start(50)

        #         self.last_label_count = len(self.w2.label_with_time_dic[temp_symbol])

        # main_window.temp_symbol_arr.clear()
        # self.current_data_dic.clear()
        self.is_in_updating = False

    def time_for_update_scroll_bar(self):
        if (not self.timer_init_flag):
            self.timer_init_flag = True
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.on_timer)
            self.timer.start(50)

    def closeEvent(self, event):  
        # 在主窗口关闭时，关闭所有次要窗口  
        for val in self.win_list.values():  
            val.close() 
        super().closeEvent(event)  # 调用基类的closeEvent方法  

    class DataUpdateSingeC(QObject):
        data_changed = pyqtSignal(str)  # 定义一个字符串类型的信号  
  
        def set_data(self, new_data):  
            self.data_changed.emit(new_data)  # 当数据更改时发出信号  

class ScrollableLabels(QWidget):  

    def __init__(self, title, w_count):  
        super().__init__()  
        x_interval = 30
        y_interval = 20
  
        # 创建一个垂直布局作为主布局  
        self.main_layout = QVBoxLayout(self)  
  
        # 创建一个滚动区域  
        self.scroll_area = QScrollArea(self)  
        self.scroll_area.setWidgetResizable(True)  

        # 创建一个QWidget作为滚动区域的内容  
        self.scroll_area_widget = QWidget()  
        self.scroll_area_layout = QHBoxLayout(self.scroll_area_widget)  
  
        interval_time = "09:35"
        history_amount = "1.65e"
        current_amount = "1.75e"

        # 添加多个QLabel到滚动区域的内容中  
        for i in range(1):  # 假设添加10个QLabel  
            label = QLabel(f'{interval_time}{i+1}\n{history_amount}\n{current_amount}', self.scroll_area_widget)  
            label.setMinimumWidth(50)  # 设置每个标签的最小宽度  
            self.scroll_area_layout.addWidget(label)  
  
        # 将QWidget设置为滚动区域的子控件  
        self.scroll_area.setWidget(self.scroll_area_widget)  
  
        # 将滚动区域添加到主布局中  
        self.main_layout.addWidget(self.scroll_area)  

        self.initUI(title, x_interval, y_interval, w_count)
    
    def initUI(self, title, x_interval, y_interval, w_count):  
        self.setWindowTitle(title)  
        self.setGeometry(500 + x_interval * w_count, 350 + y_interval * w_count, 400, 100)  
  
        # 这里可以添加更多的控件到新的窗口中  
        
        # 显示窗口  
        self.show()  

    def add_data_label(self, his_d, cur_d):

        print(f"his_d:{his_d}")

        his_d_a = round(float(his_d.amount), 2)
        cur_d_a = round(float(cur_d.amount), 2)

        if cur_d_a != 0:
            calculate_percent = round((float(cur_d.amount) - float(his_d.amount))/float(cur_d.amount), 2)
        else:
            calculate_percent = 'N'
            

        label = QLabel(f'{cur_d.eob}\n{his_d_a}\n{cur_d_a}\n{calculate_percent}', self.scroll_area_widget)  
        label.setMinimumWidth(70)  # 设置每个标签的最小
        self.scroll_area_layout.addWidget(label)  
        self.scroll_area.horizontalScrollBar().setValue(self.scroll_area.horizontalScrollBar().maximum() + 30)

        if calculate_percent == 'N':
            label.setStyleSheet('QLabel { color: grey; }')
        elif calculate_percent >= 0:
            label.setStyleSheet('QLabel { color: red; }')  
        elif calculate_percent < 0:
            label.setStyleSheet('QLabel { color: green; }')  

        if cur_d_a != 0:
            print(f"%:{(int(cur_d.amount) - int(his_d.amount))/int(cur_d.amount)}")
        else:
            print(f"N")
        

        print(f"{cur_d.symbol}: update label success")

    def flicker_background(self):
            if self.scroll_area.styleSheet() == "QWidget { background-color: white; }":  
                self.scroll_area.setStyleSheet("QWidget { background-color: red; }")  
            else:  
                self.scroll_area.setStyleSheet("QWidget { background-color: white; }")

    def flicker_background_timer(self):
        self.timer.timeout.connect(self.flicker_background)  
        self.timer.start(500)  # 每500毫秒切换一次颜色  

class InitChildQwidGet(QWidget):
    def __init__(self):  
        super().__init__()  
        self.initUI()  

    def initUI(self):  
        self.MAX_H_SIZE = 70
        self.MAX_V_SIZE = 85

        self.stock_widget_dic = {}  #一个标的对应一个widget
        self.stock_current_label_dic = {}   #当前正在操作的label
        self.label_with_time_dic = {}   #这个dic是一个标的对应一个装有label info的list,暂时只用于刷新滚动条用
        self.stock_time_labelinfo_dic = {}    #一个标的，对应一个以每分钟为key的label info
        self.time_label_dic = {} #以每分钟为key的一个装有label info的dic

        self.is_stretch = False

        #1-总容器
        self.overall_widget = QWidget()
        self.overall_widget_layout = QVBoxLayout(self.overall_widget)
        self.overall_widget_layout.setContentsMargins(0,0,0,0)

        #新增，总容器内最上方的功能容器
        self.top_function_widget = QWidget()
        self.top_function_widget_layout = QHBoxLayout(self.top_function_widget)
        self.top_function_widget.setFixedHeight(int(self.MAX_V_SIZE / 2))
        self.overall_widget_layout.addWidget(self.top_function_widget)

        #总容器中, 上方内容子容器，与下方数据刷新子容器
        self.up_contnet_widget = QWidget()
        self.up_contnet_widget_layout = QHBoxLayout(self.up_contnet_widget)
        self.up_contnet_widget.setFixedHeight(self.MAX_V_SIZE)
        self.overall_widget_layout.addWidget(self.up_contnet_widget)
        #给下方子容器中添加滚轮区域
        self.bottom_update_widget = QWidget()
        self.bottom_update_widget_layout = QVBoxLayout(self.bottom_update_widget)
        # self.bottom_update_widget.setFixedWidth(self.MAX_H_SIZE * 3)
        self.bottom_scroll_area = QScrollArea()  
        self.bottom_scroll_area.setWidgetResizable(True)  
        #这里area设置了qwidget后,下面添加应该是添加area而不是qwidget
        #下面添加label等，要添加到layout里面，不要添加到area里
        self.bottom_scroll_area.setWidget(self.bottom_update_widget)
        self.overall_widget_layout.addWidget(self.bottom_scroll_area)

class WorkerThread(QThread):  
    finished = pyqtSignal()  
  
    def run(self):  
        # 模拟后台任务  
        #注意！！注意！！注意！！
        #这里不sleep一下，UI不会刷新出来
        time.sleep(3)  
        self.finished.emit()  

class WorkerThreadUpdateData(QThread):  
    finished = pyqtSignal()  
  
    def run(self):  
        self.finished.emit() 

class LabelOrderInfo():
    def __init__(self, label_symbol, widget, layout):
        self.label_symbol = label_symbol
        self.widget = widget
        self.layout = layout

class AgilityTimeStorkInfo():
    def __init__(self, symbol, his_data, cur_data, eob):
        self.symbol = symbol
        self.his_data = his_data
        self.cur_data = cur_data
        self.eob = eob

class CurrentLabelInfo():
    def __init__(self, label, current_time, amount, history_amount):
        self.label = label
        self.current_time = current_time
        self.amount = amount
        self.history_amount = history_amount

class ReciveQThread(QThread):
    def __init__(self, client_socket):  
        super(ReciveQThread, self).__init__()  
        self.client_socket = client_socket
        self.recive_data = ''
        self.recive_today_history_data = ''
  
    # 重写 QThread 的 run 方法  
    def run(self):  
        while True:
            
            operation_id_data = self.client_socket.recv(4)
            
            #response
            if operation_id_data:
                # 解析JSON响应
                operation_id = int.from_bytes(operation_id_data, byteorder='big')

                print(f"{operation_id}")

                #持续更新实时数据,此100暂时不使用
                if operation_id == 100:

                    single_data = self.client_socket.recv(4)
                    current_data_len = int.from_bytes(single_data, byteorder='big')
                    print(f"cur_data_len:{current_data_len}")

                    json_his_data = self.client_socket.recv(current_data_len)
                    current_data = json.loads(json_his_data.decode('utf-8'))  

                    main_window.temp_current_data_dic.clear()
                    main_window.temp_current_data_dic = {key : AnalysisCurrentData.from_dict(value) for key, value in current_data.items()}

                    for key, valume in main_window.temp_current_data_dic.items():
                        main_window.temp_symbol_arr.append(valume.symbol)
                        main_window.current_data_dic[key] = valume
                        print(f"++++++++++++++++++++++++++++++++++++++++++++++{len(main_window.temp_symbol_arr)}")

                    if len(main_window.temp_symbol_arr) == len(main_window.symbol_arr):
                        main_window.teat_thread_2()

                    print(f"{main_window.current_data_dic}")

                #初始化窗口
                elif operation_id == 101:

                    single_data = self.client_socket.recv(4)
                    his_data_len = int.from_bytes(single_data, byteorder='big')
                    print(f"his_data_len:{his_data_len}")

                    #改为分段接收===================================
                    remaining = his_data_len  
                    while remaining > 0:  

                        chunk = self.client_socket.recv(min(remaining, 1024))  # 最多接收1024字节  
                        
                        if not chunk:  
                            break  # 如果连接关闭或没有数据，则退出循环  

                        self.recive_data += chunk.decode()
                        remaining -= len(chunk)  

                    print(f"self.recive_data length::{len(self.recive_data)} ")
                    #===============================================

                    his_data = json.loads(self.recive_data.encode('utf-8'))  
                    shdf_dic = {key : AnalysisHistoryData.from_dict(value) for key, value in his_data.items()}

                    print(f"shdf_dic::@{len(shdf_dic)}")

                    for key, value in shdf_dic.items():
                       if value.symbol not in main_window.history_all_dic.keys():
                           
                            #遍历出标的代码，单独装进一个字典中
                            main_window.symbol_arr.append(value.symbol)
                            main_window.name_dic[value.symbol] = value.name

                            temp_history_time_arr = value.eob.split(" ")
                            temp_h_hour_arr = temp_history_time_arr[1].split("+")

                            temp_dic = {}
                            shdf_dic[key].eob = temp_h_hour_arr[0]
                            temp_dic[temp_h_hour_arr[0]] = value

                            main_window.history_all_dic[value.symbol] = temp_dic


                       else:
                            #这里遍历出每一个标的代码对应的历史数据，数据类型是 一个key对应一个dic

                            temp_history_time_arr = value.eob.split(" ")
                            temp_h_hour_arr = temp_history_time_arr[1].split("+")

                            shdf_dic[key].eob = temp_h_hour_arr[0]
                            main_window.history_all_dic[value.symbol][temp_h_hour_arr[0]] = value

                    #注意！！这里socket如果出问题，也搬到104最后面去
                    main_window.server_sokcet = self.client_socket

                    # main_window.teat_thread_1()
                    #这里尝试通过用发送信号的方式，替换掉通过线程的方式初始化导致的，当大量数据过来的时候，会掉数据，看看能不能解决
                    #放在104最后面试试
                    # main_window.is_init_window = True
                    # main_window.has_init_window_single.emit(main_window.is_init_window)

                #持续更新实时数据,以秒为单位
                elif operation_id == 102:

                    single_data = self.client_socket.recv(4)
                    current_data_len = int.from_bytes(single_data, byteorder='big')
                    #print(f"cur_data_len:{current_data_len}")

                    json_his_data = self.client_socket.recv(current_data_len)
                    current_data = json.loads(json_his_data.decode('utf-8')) 

                    #print(f"current_data::{current_data}")

                    main_window.temp_current_data_dic.clear()
                    main_window.temp_current_data_dic = {key : AnalysisSecondData.from_dict(value) for key, value in current_data.items()}

                    temp_current_data = None

                    for key, valume in main_window.temp_current_data_dic.items():
                        temp_current_data = valume

                    #======================list方式,等待刷新

                    #现在需要无论什么时候开启客户端，都有前面的数据
                    #这里现在需要设置一个bool，当客户端还在初始化时候，就需要接收数据
                    #以免再初始化的时候，漏掉1s左右的数据

                    main_window.temp_wait_for_update_list.append(temp_current_data)

                    #当数据来时，UI还在更新，则添加先添加到等待集合里
                    if main_window.is_in_updating == False:

                        #将临时存放等待刷新的数据集合给准备刷新的集合
                        for item in main_window.temp_wait_for_update_list:
                            temp_item = item
                            main_window.wait_for_update_list.append(temp_item)    
                            print(f"put in update list::{temp_item.symbol}||{temp_item.amount}||{temp_item.eob}")

                        # for item in main_window.wait_for_update_list:
                        #     print(f"begin update::{item.symbol}||{item.amount}||{item.eob}")

                        #清空临时list,准备接新的数据
                        main_window.temp_wait_for_update_list.clear()

                        main_window.test_index = 0

                        main_window.is_in_updating = True

                        main_window.is_has_new_data = True
                        main_window.has_new_data_single.emit(main_window.is_has_new_data)
                        main_window.is_has_new_data = False

                #当客户端未及时开启，需要初始化此时段之前的所有数据
                elif operation_id == 104:

                    single_data = self.client_socket.recv(4)
                    his_today_data_len = int.from_bytes(single_data, byteorder='big')
                    print(f"his_today_data_len:{his_today_data_len}")

                    #改为分段接收===================================
                    remaining = his_today_data_len  
                    while remaining > 0:  

                        chunk = self.client_socket.recv(min(remaining, 1024))  # 最多接收1024字节  
                        
                        if not chunk:  
                            break  # 如果连接关闭或没有数据，则退出循环  

                        self.recive_today_history_data += chunk.decode()
                        remaining -= len(chunk)  

                    print(f"self.recive_today_history_data length::{len(self.recive_today_history_data)} ")
                    #===============================================

                    his_today_data = json.loads(self.recive_today_history_data.encode('utf-8')) 

                    thtd_dic = {key : AnalysisHistoryData.from_dict(value) for key, value in his_today_data.items()}

                    print(f"thtd_dic::@{len(thtd_dic)}")

                    for key, value in thtd_dic.items():
                       
                    #    print(f"{key}:::{value.symbol}")

                       if value.symbol not in main_window.history_today_all_dic.keys():
                           
                            temp_history_time_arr = value.eob.split(" ")
                            temp_h_hour_arr = temp_history_time_arr[1].split("+")

                            temp_dic = {}
                            shdf_dic[key].eob = temp_h_hour_arr[0]
                            temp_dic[temp_h_hour_arr[0]] = value

                            main_window.history_today_all_dic[value.symbol] = temp_dic


                       else:
                            #这里遍历出每一个标的代码对应的此刻时段之前的所有历史数据，数据类型是 一个key对应一个dic

                            temp_history_time_arr = value.eob.split(" ")
                            temp_h_hour_arr = temp_history_time_arr[1].split("+")

                            shdf_dic[key].eob = temp_h_hour_arr[0]
                            main_window.history_today_all_dic[value.symbol][temp_h_hour_arr[0]] = value

                    #注意，客户端实在接受完昨日历史数据，就开始进行初始化UI，可能会发生，这里还在接收，UI就在初始化，后面可能会出问题
                    #如果出问题，就把101里的初始化UI搬这里来
                    #牛逼，真出问题了，搬这里来试试!!
                    main_window.is_init_window = True
                    main_window.has_init_window_single.emit(main_window.is_init_window)

                    # main_window.teat_thread_1()

class SendQThread(QThread):
    def __init__(self, client_socket):  
        super(SendQThread, self).__init__()  
        self.client_socket = client_socket
        
  
    # 重写 QThread 的 run 方法  
    def run(self):  
        while True:
            time.sleep(60)
            operation_id = 900
            self.client_socket.sendall(operation_id.to_bytes(4))
            

if __name__ == '__main__':  
    app = QApplication(sys.argv)  
    main_window = TestClientUI()  
    main_window.show()  
    sys.exit(app.exec_())

