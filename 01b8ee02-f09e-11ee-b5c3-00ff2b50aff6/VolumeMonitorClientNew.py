from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QTextEdit, QMainWindow, QLineEdit, QScrollArea, QLabel, QHBoxLayout, QSizePolicy, QMessageBox
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

OP_ID_S2C_STOCK_NAME_SEND = 100
OP_ID_S2C_HISTORY_DATA_SEND = 101
OP_ID_S2C_REAL_TIME_DATA_SEND = 102
OP_ID_S2C_HISTORY_TODAY_DATA_SEND = 104

OP_ID_C2S_QUICK_BUY = 120
OP_ID_C2S_QUICK_SELL = 121

load_history_path = 'c:\\TradeLogs\\' + 'AllHistoryInfo' + '.npy'

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
    has_init_stock_name_single = pyqtSignal(bool)

    def __init__(self):  
        super().__init__()  
        self.initUI()  
  
    def initUI(self):  
        self.server_sokcet = None
        self.client_socket = None

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
        self.is_init_window = False #信号，初始UI相关容器
        self.is_init_window_stork_name = False #新版，信号，初始化标的代码，名称，以及相关w1--6相关容器
        self.is_w2_refresh = False #控制每分钟数据是否显示
        self.is_w6_refresh = False #控制当日所有数据是否显示
        self.server_port = 12346 #正式服12345, 调试服12346

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
        self.has_init_stock_name_single.connect(self.init_window_stork_name)

        # self.load_history_info()

        self.connect_server()


    def load_history_info(self):
        print(f"load_history_path:{load_history_path}")
        temp_history_dic = np.load(load_history_path, allow_pickle=True)
        temp_history_dic = dict(temp_history_dic.tolist())
        print(f"temp_history_dic length:{len(temp_history_dic)}")

        # for value in temp_history_dic.values():
        #     print(f"{value['symbol']}:{value['amount']}:{value['eob']}")

    def connect_server(self):
        #"8.137.48.212" - 127.0.0.1 # 线程Server 正式服12345, 调试服12346
        self.send_data_to_server("8.137.48.212", self.server_port, {"name": "Alice", "message": "Hello, server!"})
 
    def send_data_to_server(self, server_ip, server_port, data):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((server_ip, server_port))

        try:
            #尝试开启线程一直接受服务器响应,用QTread,thread会出问题
            self.rfs_thread = ReciveQThread(self.client_socket)
            self.rfs_thread.start()

            #尝试开启线程一直向服务器发送请求
            sts_thread = threading.Thread(target = self.send_to_server, args=(self.client_socket,))
            sts_thread.start()

            #开启心跳线程
            self.heart_thread = SendQThread(self.client_socket)
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
        
    # 向服务发送急速买入的命令
    def send_to_server_quick_buy(self, client_socket):
        input_box_str = self.input_box_search.text()
        if len(input_box_str) < 6:
            print(f"急速买入的标的ID长度不正常，正常长度不应该小于6位！请检查，目前内容为：[{input_box_str}]")
            return
        
        # 尝试拆分标的和买入金额，不一定会带金额，没有的话，就使用默认20w的设置
        buy_id = 0
        buy_amount = 20
        if "#" in input_box_str:
            str_arr = input_box_str.split('#')
            buy_id = int(str_arr[0])
            buy_amount = np.int16(str_arr[1])
        else:
            buy_id = int(input_box_str)
        
        reply = QMessageBox.question(None, '确认', f'您确定要急速买入标的[{buy_id}]---[{buy_amount}]w吗？', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        
        print(f"开始尝试急速买入标的[{buy_id}]")
        # 下面的int就是二进制，比如6位的标的：600001，用字符发送就要占6个字节，但是我们可以用int形式
        # 一般的int等于4字节，也就是numpy.int32，为了进一步压缩，我们可以使用2字节（numpy.int16）？？，2字节是不行的，只能到65536，不够，1字节更不行，因为1字节最大能表达的数据只有256，不够我们表达股票标的ID
        # 上面import numpy as np了，所以我们用np调用
        
        # 4 + 4 + 2 = 10字节
        # 标的必须用int，4字节
        # 买入金额用int16即可，可达到65536w，已经非常大了不可能超过，这样可节约2个字节
        client_socket.sendall(OP_ID_C2S_QUICK_BUY.to_bytes(4) + int(buy_id).to_bytes(4) + np.int16(buy_amount).tobytes())
        # print(f"search text:{buy_id}")
        
    # 向服务发送急速买入的命令
    def send_to_server_quick_sell(self, client_socket):
        input_box_str = self.input_box_search.text()
        if len(input_box_str) != 6:
            print(f"急速卖出的标的ID长度不正常，正常长度应该等于6位！请检查，目前内容为：[{input_box_str}]")
            return
        
        buy_id = int(input_box_str)
        reply = QMessageBox.question(None, '确认', f'您确定要急速卖出标的[{buy_id}]吗？', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        
        print(f"开始尝试急速卖出标的[{buy_id}]")
        
        # 4 + 4 = 8字节
        # 标的必须用int，4字节
        client_socket.sendall(OP_ID_C2S_QUICK_SELL.to_bytes(4) + int(buy_id).to_bytes(4))
        

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
        self.input_box_search = QLineEdit(self)
        self.input_box_search.returnPressed.connect(lambda: self.w1_select_stock(self.input_box_search))
        self.w1.top_function_widget_layout.addWidget(self.input_box_search)

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

        #____添加w2按钮支持急速买入
        btn_quick_buy = QPushButton(self)
        btn_quick_buy.setText("买入")
        btn_quick_buy.setFixedSize(QSize(60, 30))
        btn_quick_buy.pressed.connect(lambda: self.w1_quick_buy())
        self.w2.top_function_widget_layout.addWidget(btn_quick_buy)
        
        #____添加w2按钮支持急速卖出
        btn_quick_sell = QPushButton(self)
        btn_quick_sell.setText("卖出")
        btn_quick_sell.setFixedSize(QSize(60, 30))
        btn_quick_sell.pressed.connect(lambda: self.w1_quick_sell())
        self.w2.top_function_widget_layout.addWidget(btn_quick_sell)

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
            
    # w1中，添加的急速买入按钮功能
    def w1_quick_buy(self):
        self.send_to_server_quick_buy(self.client_socket)
        
    # w1中，添加的急速买入按钮功能
    def w1_quick_sell(self):
        self.send_to_server_quick_sell(self.client_socket)

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


    # 只初始化标的代码,名称,及相关w1-6中的各个容器
    def init_window_stork_name(self):
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

            self.simple_stock_with_stock[item[-6:]] = item

            #初始化所有标的的w6今日所有成交额的cunrrent_label，避免后面再刷新中创建
            # 新版本，这里后面可能会用到，先注释掉
            # temp_all_day_history_amount = 0.0
            # for key, valume in self.history_all_dic[item].items():
            #     temp_all_day_history_amount += float(valume.amount)

            # data_label = self.create_current_label('ALL DAY', temp_all_day_history_amount, '0.0', '0.0', self.w6.stock_widget_dic[item].widget)

            # self.w6.stock_widget_dic[item].layout.addWidget(data_label)
            # self.w6.label_with_time_dic[item].append(data_label)

            # temp_current_label_info = CurrentLabelInfo(data_label, 'ALL DAY', 0.0, temp_all_day_history_amount)
            # self.w6.stock_current_label_dic[item] = temp_current_label_info
            #================================ w6

        #初始化名称
        for key, valume in self.w1.stock_widget_dic.items():
                
            name = QLabel(f'{self.name_dic[key]}', temp_qwidget)  
            name.setMinimumWidth(self.MAX_H_SIZE)
            valume.layout.addWidget(name)


        #初始化完成后，向服务器发送已完成消息
        self.send_to_server_client_init_complete(self.server_sokcet)
        print(f"send message to server init client had complate")


    # 初始化窗口
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

                    self.simple_stock_with_stock[item[-6:]] = item

                    #这里要遍历所有标的的所有历史数据，抓出哪一分钟没有数据，并重新添加空的数据进去
                    #不要在刷新过程中来判断，尽量减少刷新负担。。吧。。
                    for hhmmss in self.hh_mm_ss:
                        if hhmmss not in self.history_all_dic[item].keys():
                            temp_his_date = AnalysisHistoryData(item, 0, hhmmss, 'temp')
                            self.history_all_dic[item][hhmmss] = temp_his_date

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

        #在这里设置一个临时变量，用于获取w2里面的当前时间，方便后面在w4里排序
        temp_w2_last_time = ''

        #这里not in用于刚打开客户端，第一次当前label的添加
        if self.is_w2_refresh == True and symbol not in self.w2.stock_current_label_dic.keys():

            data_label = self.create_current_label(cur_date.eob, his_d_a, cur_d_a, calculate_percent, self.w2.stock_widget_dic[symbol].widget)

            self.w2.stock_widget_dic[symbol].layout.addWidget(data_label)
            self.w2.label_with_time_dic[symbol].append(data_label)

            temp_current_label_info = CurrentLabelInfo(data_label, cur_date.eob, cur_d_a, his_d_a)
            self.w2.stock_current_label_dic[symbol] = temp_current_label_info
            self.w2.stock_time_labelinfo_dic[symbol][cur_date.eob] = temp_current_label_info

        #更新当前分钟数的label
        elif self.is_w2_refresh == True and self.w2.stock_current_label_dic[symbol].current_time != cur_date.eob:

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

            if temp_last_calculate_percent != 'N':
                #float后面的50后面需要改为在ui上可设置
                if float(temp_last_calculate_percent) >= float(1000):

                    temp_last_data_label = self.create_current_label(temp_last_time, temp_last_his_amount, temp_last_cur_amount, temp_last_calculate_percent, self.w3.stock_widget_dic[symbol].widget)

                    self.w3.stock_widget_dic[symbol].layout.addWidget(temp_last_data_label)

            self.w2.stock_current_label_dic[symbol] = CurrentLabelInfo(data_label, cur_date.eob, cur_d_a, his_d_a)
            self.w2.stock_time_labelinfo_dic[symbol][cur_date.eob] = CurrentLabelInfo(data_label, cur_date.eob, cur_d_a, his_d_a)

        #实时更新当前label中的amount
        #else -- elif
        elif self.is_w2_refresh == True:
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

        if self.is_w2_refresh == True:
            #根据百分比设置label颜色
            if calculate_percent == 'N':
                self.w2.stock_current_label_dic[symbol].label.setStyleSheet('QLabel { color: grey; }')
            elif calculate_percent > 0:
                self.w2.stock_current_label_dic[symbol].label.setStyleSheet('QLabel { color: red; }')  
            elif calculate_percent < 0:
                self.w2.stock_current_label_dic[symbol].label.setStyleSheet('QLabel { color: green; }')  
            #根据历史数据设置label颜色,这里要先转化为float再转化为int
            if int(float(his_date.amount)) == 0:
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
                
            # 灵活时间，由此时段，进入下一时段，！！这里后期想办法简化下！！
            elif is_can_in_agility == True and datetime.strptime(cur_date.eob, "%H:%M:%S").time() != datetime.strptime('11:30:00', "%H:%M:%S").time():
                
                #可以尝试在这里补全，避免在w2里补全
                #这里需要补全灵活分钟label,例如40分到41分，有些票来数据，就会添加灵活分钟当前label
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


        if self.is_w6_refresh == True:
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
                
                    # print(f"{item.symbol}::{item.eob}")

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

                    #防止超过11:30:00报错
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

        self.test_index += 1
        # print(f"self.test_index::{self.test_index}")

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
        
        #调试时，可以注释掉这里，方便查看问题!
        if int(float(cur_d.amount)) != 0:
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
                #这里更改为二进制接收标的名称       100
                if operation_id == OP_ID_S2C_STOCK_NAME_SEND:
                    self.receive_100()

                #初始化窗口     101
                elif operation_id == OP_ID_S2C_HISTORY_DATA_SEND:
                    self.init_ui_101()

                #持续更新实时数据,以秒为单位    102
                elif operation_id == OP_ID_S2C_REAL_TIME_DATA_SEND:
                    self.real_time_refresh_data()

                #当客户端未及时开启，需要初始化此时段之前的所有数据     104
                elif operation_id == OP_ID_S2C_HISTORY_TODAY_DATA_SEND:
                    self.init_ui_104()


    # 封装 OP_ID_S2C_REAL_TIME_DATA_SEND--102, 实时数据刷新
    def real_time_refresh_data(self):
        #将解析symbol, amount, eob，分别封装到方法里，方便其他地方调用

        #2-4 int32
        symbol_letter_bytes = self.client_socket.recv(4)
        symbol_letter_str = int.from_bytes(symbol_letter_bytes, byteorder='big')
        symbol_letter = self.re_translate_letter_to_int(str(symbol_letter_str))
        # print(f"symbol_letter:{symbol_letter}")

        #3-4 int32
        symbol_num_bytes = self.client_socket.recv(4)
        symbol_num = str(int.from_bytes(symbol_num_bytes, byteorder='big'))
        #___这里需要补全标的代码前面的0
        if len(symbol_num) < 6:
            need_complement = 6 - len(symbol_num)
            for i in range(need_complement):
                i += 1
                symbol_num = '0' + symbol_num
        # print(f"symbol_num:{symbol_num}")

        #4-4 int32
        amount_bytes = self.client_socket.recv(4)
        amount = str(round(float(int.from_bytes(amount_bytes, byteorder='big')), 2))
        # print(f"amount:{amount}")

        #5-4 int32
        eob_date_bytes = self.client_socket.recv(4)
        eob_date_str = str(int.from_bytes(eob_date_bytes, byteorder='big'))
        eob_date = self.re_complement_date(eob_date_str)
        # print(f"eob_date:{eob_date}")

        #6-4 int32
        eob_time_bytes = self.client_socket.recv(4)
        eob_time_str = str(int.from_bytes(eob_time_bytes, byteorder='big'))
        eob_time = self.re_complement_time(eob_time_str)
        # print(f"eob_time:{eob_time}")

        symbol = symbol_letter + '.' + symbol_num
        eob = eob_date + " " + eob_time

        temp_current_data = AnalysisSecondData(symbol, amount, eob)

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

                #str转换int,需要先将其转化为float,再转化为int
                if int(float(temp_item.amount)) != 0:
                    print(f"put in update list::{temp_item.symbol}||{temp_item.amount}||{temp_item.eob}")

            #清空临时list,准备接新的数据
            main_window.temp_wait_for_update_list.clear()

            main_window.test_index = 0

            main_window.is_in_updating = True

            main_window.is_has_new_data = True
            main_window.has_new_data_single.emit(main_window.is_has_new_data)
            main_window.is_has_new_data = False


    # 封装 OP_ID_S2C_HISTORY_TODAY_DATA_SEND--104， 初始化中途开启时间段之前所有当日数据
    def init_ui_104(self):
        temp_history_today_data_list = []

        # 2-4 int32
        history_today_data_count_bytes = self.client_socket.recv(4)
        history_today_data_count = int.from_bytes(history_today_data_count_bytes, byteorder='big')
        print(f"history_data_count::{history_today_data_count}")

        had_recive_count = 0

        #这个接收循环是有问题的，应该不是这样接收的
        for i in range(history_today_data_count):
            history_today_recive_count_bytes = self.client_socket.recv(4)
            history_today_recive_count = int.from_bytes(history_today_recive_count_bytes, byteorder='big')

            for n in range(history_today_recive_count):
                symbol_letter_bytes = self.client_socket.recv(4)
                symbol_num_bytes = self.client_socket.recv(4)
                symbol = self.translate_symbol_in_bytes(symbol_letter_bytes, symbol_num_bytes)

                amount_bytes = self.client_socket.recv(4)
                amount = self.translate_amount_in_bytes(amount_bytes)

                eob_date_bytes = self.client_socket.recv(4)
                eob_time_bytes = self.client_socket.recv(4)
                eob = self.translate_eob_in_bytes(eob_date_bytes, eob_time_bytes)

                # print(f"{symbol}:{amount}:{eob}:{main_window.name_dic[symbol]}")
                temp_history_today_data_list.append(AnalysisHistoryData(symbol, float(amount), eob, main_window.name_dic[symbol]))

            had_recive_count += history_today_recive_count
            if had_recive_count == history_today_data_count:
                break

        thtd_dic = {}
        #将装有历史数据的临时集合里的数据，装入shdf_dic(懒得改后面了，先将就着吧)
        t_i = 0
        for item in temp_history_today_data_list:
            thtd_dic[t_i] = item
            t_i += 1

        print(f"thtd_dic::@{len(thtd_dic)}")

        for key, value in thtd_dic.items():
        #    print(f"value.eob::{value.eob}")
            if value.symbol not in main_window.history_today_all_dic.keys():
                
                temp_dic = {}

                thtd_dic[key].eob = value.eob
                temp_dic[value.eob] = value

                main_window.history_today_all_dic[value.symbol] = temp_dic

            else:
                #这里遍历出每一个标的代码对应的此刻时段之前的所有历史数据，数据类型是 一个key对应一个dic
                thtd_dic[key].eob = value.eob #shdf_dic
                main_window.history_today_all_dic[value.symbol][value.eob] = value

        #注意，客户端实在接受完昨日历史数据，就开始进行初始化UI，可能会发生，这里还在接收，UI就在初始化，后面可能会出问题
        #如果出问题，就把101里的初始化UI搬这里来
        #牛逼，真出问题了，搬这里来试试!!
        main_window.is_init_window = True
        main_window.has_init_window_single.emit(main_window.is_init_window)

    # 封装 OP_ID_S2C_HISTORY_DATA_SEND--101， 初始化窗口
    def init_ui_101(self):
        temp_history_data_list = []

        # 2-4 int32
        history_data_count_bytes = self.client_socket.recv(4)
        history_data_count = int.from_bytes(history_data_count_bytes, byteorder='big')
        print(f"history_data_count::{history_data_count}")

        had_recive_count = 0

        #这个接收循环是有问题的，应该不是这样接收的
        for i in range(history_data_count):
            history_recive_count_bytes = self.client_socket.recv(4)
            history_recive_count = int.from_bytes(history_recive_count_bytes, byteorder='big')

            for n in range(history_recive_count):
                symbol_letter_bytes = self.client_socket.recv(4)
                symbol_num_bytes = self.client_socket.recv(4)
                symbol = self.translate_symbol_in_bytes(symbol_letter_bytes, symbol_num_bytes)

                amount_bytes = self.client_socket.recv(4)
                amount = self.translate_amount_in_bytes(amount_bytes)

                eob_date_bytes = self.client_socket.recv(4)
                eob_time_bytes = self.client_socket.recv(4)
                eob = self.translate_eob_in_bytes(eob_date_bytes, eob_time_bytes)

                # print(f"{symbol}:{amount}:{eob}:{main_window.name_dic[symbol]}")

                if symbol in main_window.name_dic.keys():
                    temp_history_data_list.append(AnalysisHistoryData(symbol, float(amount), eob, main_window.name_dic[symbol]))

            had_recive_count += history_recive_count
            if had_recive_count == history_data_count:
                break

        shdf_dic = {}
        #将装有历史数据的临时集合里的数据，装入shdf_dic(懒得改后面了，先将就着吧)
        t_i = 0
        for item in temp_history_data_list:
            shdf_dic[t_i] = item
            t_i += 1

        print(f"shdf_dic::@{len(shdf_dic)}")

        for key, value in shdf_dic.items():
            # print(f"{key}")
            if value.symbol not in main_window.history_all_dic.keys():
                
                #遍历出标的代码，单独装进一个字典中
                # 注意!!!新版这里添加到 100里面，这里再添加就会出错 2024-7-15
                # 新版后面，应该就不会用到这个函数了 2024-7-15
                main_window.symbol_arr.append(value.symbol)
                #上面100里面已经装填了，测试没问题就删了
                # main_window.name_dic[value.symbol] = value.name

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

            # print(f"{value}")

        #注意！！这里socket如果出问题，也搬到104最后面去
        # 新版，这里搬到100里试试
        main_window.server_sokcet = self.client_socket

        #放在104最后面试试
        # main_window.is_init_window = True
        # main_window.has_init_window_single.emit(main_window.is_init_window)

    # 封装 OP_ID_S2C_STOCK_NAME_SEND--100，接收标的代码以及名称
    def receive_100(self):
        name_count_bytes = self.client_socket.recv(4)
        name_count = int.from_bytes(name_count_bytes, byteorder='big')

        #这里报错，暂时不太清，将这里改成字符串接收
        #symbol_and_name_recive.decode('utf-8'),这里改为utf-8后暂时没发现报错，但还需要观察!!
        name_index = 0
        for i in range(name_count):

            symbol_and_name_length_bytes = self.client_socket.recv(4)
            symbol_and_name_length = int.from_bytes(symbol_and_name_length_bytes, byteorder='big')

            symbol_and_name_recive = self.client_socket.recv(symbol_and_name_length)
            symbol_and_name = symbol_and_name_recive.decode('utf-8')
            symbol_name_arr = symbol_and_name.split("+")

            name_index += 1
            print(f"{symbol_name_arr[0]}:{symbol_name_arr[1]}|{name_index}")

            main_window.name_dic[symbol_name_arr[0]] = symbol_name_arr[1]

            # 这里为新版,在这里将标的代码添加进集合
            main_window.symbol_arr.append(symbol_name_arr[0])
            
        # 新版，socket赋值
        main_window.server_sokcet = self.client_socket

        # 这里为新版，更改服务器运算，有问题就注释掉
        main_window.is_init_window_stork_name = True
        main_window.has_init_stock_name_single.emit(main_window.is_init_window_stork_name)


    #解析标的时间
    def translate_eob_in_bytes(self, eob_date_bytes, eob_time_bytes):
        eob_date_str = str(int.from_bytes(eob_date_bytes, byteorder='big'))
        eob_date = self.re_complement_date(eob_date_str)

        eob_time_str = str(int.from_bytes(eob_time_bytes, byteorder='big'))
        eob_time = self.re_complement_time(eob_time_str)

        eob = eob_date + " " + eob_time

        return eob

    #解析标的成交金额
    def translate_amount_in_bytes(self, amount_bytes):
        amount = str(round(float(int.from_bytes(amount_bytes, byteorder='big')), 2))
        return amount

    #解析标的名称
    def translate_symbol_in_bytes(self, symbol_letter_bytes, symbol_num_bytes):

        symbol_letter_str = int.from_bytes(symbol_letter_bytes, byteorder='big')
        symbol_letter = self.re_translate_letter_to_int(str(symbol_letter_str))

        symbol_num = str(int.from_bytes(symbol_num_bytes, byteorder='big'))
        #___这里需要补全标的代码前面的0
        if len(symbol_num) < 6:
            need_complement = 6 - len(symbol_num)
            for i in range(need_complement):
                i += 1
                symbol_num = '0' + symbol_num

        symbol = symbol_letter + '.' + symbol_num

        return symbol

    #拼接hh:mm:ss+8:00
    def re_complement_time(self, str_time):
        # 使用列表推导式和字符串切片来拆解字符串  
        # chunks = [str_time[i:i+2] for i in range(0, len(str_time), 2)]  
        #这里通过长度来判断是否需要补全，例如93103代表 9:30:03，就需要补全，其实只有9点需要补全
        if len(str_time) == 5:
            chunks_1 = str_time[0]
            chunks_2 = str_time[1:]
            # print(f"{chunks_1}::{chunks_2}")
            chunks = [chunks_2[i:i+2] for i in range(0, len(chunks_2), 2)]  
        else:
            chunks = [str_time[i:i+2] for i in range(0, len(str_time), 2)]

        temp_split_joint_letter = ''

        index = 0
        for letter in chunks:
            if index == 0:
                temp_split_joint_letter = letter
            else:
                temp_split_joint_letter = temp_split_joint_letter + ':' + letter
            index += 1

        #在补全一下，例如9点--补全到09
        if len(temp_split_joint_letter) == 5:
            temp_split_joint_letter = '0' + chunks_1 + ":" + temp_split_joint_letter

        return temp_split_joint_letter + '+08:00'

    #拼接年月日
    def re_complement_date(self, str_date):
        # 使用列表推导式和字符串切片来拆解字符串  
        chunks = [str_date[i:i+4] for i in range(0, len(str_date), 4)]  
        chunks_day = [chunks[1][i:i+2] for i in range(0, len(chunks[1]), 2)]

        temp_split_joint_letter = ''

        index = 0
        for letter in chunks_day:
            if index == 0:
                temp_split_joint_letter = letter
            else:
                temp_split_joint_letter = temp_split_joint_letter + '-' + letter
            index += 1

        return chunks[0] + '-' + temp_split_joint_letter

    #将标的前面的英文转化为int类型
    def re_translate_letter_to_int(self, stork_letter):

        # 使用列表推导式和字符串切片来拆解字符串  
        chunks = [stork_letter[i:i+2] for i in range(0, len(stork_letter), 2)]  
        
        temp_split_joint_letter = ''

        for letter in chunks:
            temp_int_letter = self.re_translate_letter_one_by_one(int(letter))
            temp_split_joint_letter = temp_split_joint_letter + temp_int_letter

        return temp_split_joint_letter

    #将单个字母转换为自定义的int类型
    def re_translate_letter_one_by_one(self, letter):

        #99,999,999 int32

        temp_int = 0

        if letter == 10:
            temp_int = 'A'
        elif letter == 11:
            temp_int = 'B'
        elif letter == 12:
            temp_int = 'C'
        elif letter == 13:
            temp_int = 'D'
        elif letter == 14:
            temp_int = 'E'
        elif letter == 15:
            temp_int = 'F'
        elif letter == 16:
            temp_int = 'G'
        elif letter == 17:
            temp_int = 'H'
        elif letter == 18:
            temp_int = 'I'
        elif letter == 19:
            temp_int = 'J'
        elif letter == 20:
            temp_int = 'K'
        elif letter == 21:
            temp_int = 'L'
        elif letter == 22:
            temp_int = 'M'
        elif letter == 23:
            temp_int = 'N'
        elif letter == 24:
            temp_int = 'O'
        elif letter == 25:
            temp_int = 'P'
        elif letter == 26:
            temp_int = 'Q'
        elif letter == 27:
            temp_int = 'R'
        elif letter == 28:
            temp_int = 'S'
        elif letter == 29:
            temp_int = 'T'
        elif letter == 30:
            temp_int = 'U'
        elif letter == 31:
            temp_int = 'V'
        elif letter == 32:
            temp_int = 'W'
        elif letter == 33:
            temp_int = 'X'
        elif letter == 34:
            temp_int = 'Y'
        elif letter == 35:
            temp_int = 'Z'

        return str(temp_int)

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

