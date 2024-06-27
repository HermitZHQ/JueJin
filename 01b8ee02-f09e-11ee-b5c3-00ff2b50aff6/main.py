# coding=utf-8
from __future__ import print_function, absolute_import
from gm.api import *

import matplotlib.pyplot as plt
import numpy as np
import time
import datetime
import math
import pickle
import re
import os

# excel库
import openpyxl
from openpyxl.utils import get_column_letter #导入合并单元格模块
from openpyxl.styles import Alignment # 导入对齐模块
from openpyxl.styles import Font # 导入字体模块
from openpyxl.styles import Border, Side # 导入边框线和颜色模块
from openpyxl.styles import PatternFill # 导入填充模块

def VolumeMonitor():
    pass

def on_parameter(context, parameter):
    #print(parameter)
    if (parameter.key == 'Reduce_Rate'):
        print(f'Reduce_Rate 参数已经调整为：{parameter.value}')
        context.Reduce_Rate = parameter.value
    elif (parameter.key == 'Base_Line'):
        print(f'Base_Line 参数已经调整为：{parameter.value}')
        context.Base_Line = parameter.value
    elif (parameter.key == 'Year'):
        print(f'Year 参数已经调整为：{parameter.value}')
        context.Year = parameter.value
    elif (parameter.key == 'Refresh'):
        print(f'Refresh 参数已经调整为：{parameter.value}')
        context.Refresh = parameter.value
        Refresh(context)

def traverse_files(folder, context, year):
    for root, dirs, files in os.walk(folder):
        for file in files:
            file_path = os.path.join(root, file)

            find_pos = file_path.find("连续")
            if (find_pos == -1):
                print(f"[Error]发现命名有问题的文件：{file_path}")
                continue
            
            # 需要找到最后一个反斜杠，系信函数自动join上的是反斜杠（\），不是我们自己写的路径的斜杠
            find_pos2 = file_path.find("\\")

            str_time = file_path[find_pos2 + 1 : find_pos]
            # 调试信息
            # print(f"test time string:{str_time}")

            # 下跌数量
            find_num_pos1 = file_path.find("（")
            find_num_pos2 = file_path.find("）")
            if (find_num_pos1 == -1 or find_num_pos2 == -1):
                print (f"[Error]找不到有效的括号位置，文件名可能存在问题：{file_path}")
                continue
            fall_num = int(file_path[find_num_pos1 + 1 : find_num_pos2])
            # 调试信息
            # print(f"test fall num:{fall_num}")

            if len(str_time) == 8:
                # 长度符合的情况下，则不需要做额外处理（比如20230410）
                context.excel_info[str_time] = fall_num
            elif(len(str_time) == 4):
                # 不等于的情况下，默认需要连接年份（比如0410，老版本的文件名）
                context.excel_info[year + str_time] = fall_num
            else:
                print(f"[Error]获取的日期长度有问题，请检查：{str_time}")

def load_excel_info(context, year):
    traverse_files("c:/users/administrator/desktop/Fall/", context, year)
    # 调试信息
    # print(f"the excel info:{context.excel_info}")

def generate_shangzhengzhishu_curve(context, year):

    t = time.time()

    # 初始化想要查询的数据
    config_start_time = year + '-01-01'
    config_end_time = year + '-12-31'
    print(f"开始查询历史数据，范围区间：[{config_start_time}]-[{config_end_time}]")

    # 查询上证指数
    # 我们查询的时候还是直接查询一年，因为这样速度很快，后面再取我们需要的数据就好（我开始想的根据excel每天查，其实那样效率很低）
    shangzheng_zhishu_info_year = history(symbol = 'SHSE.000001', frequency = '1d', start_time = config_start_time,  end_time = config_end_time, fields='close, eob', adjust = ADJUST_PREV, df = True)
    # 调试信息
    # print(f"shangzheng zhishu(with close):\n len[{len(shangzheng_zhishu_info_year)}] {shangzheng_zhishu_info_year}")

    # 初始化字体
    plt.rcParams['font.sans-serif']=['SimHei'] #用来正常显示中文标签
    plt.rcParams['axes.unicode_minus']=False #用来正常显示负号

    # 创建一些数据点
    # x = np.linspace(0, 10, 10)  # 创建一个从0到10的等差数列，共100个点
    # # y = np.sin(x)  # 使用正弦函数生成y值
    # y = [1, 2, 3, 4, 15, 6, 7, 8, 19, 10]
    # # 使用matplotlib绘制曲线图
    # plt.plot(x, y)

    # 子区域绘制-方式01（但是这种不能带右上角的曲线名称，一般可能用legend比较好）
    # 前面的参数是行，列，一般我们采用1，1的设置，就可以把子曲线绘制在同一个坐标系下了，非（1，1）的情况有需要再看吧，现在没必要
    # plt.subplot(1,1,1)
    # a=[1,2,3,4,5]
    # b=[5,4,3,2,1]
    # c2 = plt.plot(a,b)

    # 设置标题和标签
    plt.title('上证指数-下跌数量-关系图')
    plt.xlabel('')
    plt.ylabel('')

    # Warning：dataFrame需要转换为数组
    close_arr = shangzheng_zhishu_info_year['close']
    tmp_date_list = shangzheng_zhishu_info_year['eob'] # 用于和excel表的日期进行对应，由于表格可能不完整（比如哪天的没有，很难完整对应，所以必须要以时间来形成最终的对齐曲线）
    count = 0
    for date in tmp_date_list:
        split1 = str(date).split(' ')
        split2 = split1[0].split('-')
        date = ""
        # 重新组合出有效的（我们需要使用的字符串格式）
        for str_split in split2:
            date += str_split
        context.szzs_date_list[date] = close_arr[count]# 这里记录到全局以后，我们在excel的处理函数中，需要用到这个时间数据
        # print(f"count:{count} val:{close_arr[count]}")
        count += 1

    # print(f"test point01:{context.szzs_date_list}")

    # 调试信息，查看重新组合后的时间是否满足我们的需求
    # print(f"re-combined-date:{context.szzs_date_list}")

    print(f"------完成上证指数的统计总计耗时为：{time.time() - t:.4f}s")
    # 开始处理读取excel相关的内容---------------------------------
    load_excel_info(context, year)
    x_fall_num = np.arange(len(context.excel_info))
    y_fall_num = []
    for k,v in context.excel_info.items():
        y_fall_num.append(v / context.Reduce_Rate + context.Base_Line)

    # 我们需要重新整理出需要的上证指数数据（因为excel的表格可能不全，某个月，某天都可能没有）
    y_szzs = []
    for k,v in context.excel_info.items():
        if k in context.szzs_date_list.keys():
            y_szzs.append(context.szzs_date_list[k])

    # 注意：必须要先用变量记录作出的线且变量要以英文逗号结尾，然后再使用legend函数
    # Warning：特别注意下面的赋值写法，不是等号，是[,=]
    line1_szzs ,= plt.plot(x_fall_num, y_szzs) # 这里的x轴应该和下跌是一样的，因为我们是从excel中重新筛选了对应的上证日期和数据
    line2_fall_num ,= plt.plot(x_fall_num, y_fall_num)
    plt.legend([line1_szzs, line2_fall_num], ["上证指数", "下跌数量"], loc = "upper right")

    # 使用grid函数为图像设置网格线
    plt.grid(True)

    # save要放在show之前，否则是空白图片
    # dpi不用设置到600，600的话都是4k的分辨率了，320已经有2k的分辨率了
    plt.savefig("上证指数和下跌关系曲线图.png", dpi = 320)

    print(f"------查询总计耗时为：{time.time() - t:.4f}s")
    # 显示图形
    plt.show()

def Refresh(context):
    plt.close()
    generate_shangzhengzhishu_curve(context, str(int(context.Year)))

# 策略中必须有init方法
def init(context):

    # 初始化参数----------------
    context.Reduce_Rate = 20
    add_parameter(key='Reduce_Rate', value=context.Reduce_Rate, min=1, max=1000, name='缩小比例', intro='', group='1', readonly=False)
    context.Base_Line = 3000
    add_parameter(key='Base_Line', value=context.Base_Line, min=0, max=100000, name='抬升基准', intro='', group='1', readonly=False)
    context.Year = 2023
    add_parameter(key='Year', value=context.Year, min=0, max=10000, name='年份设置', intro='', group='1', readonly=False)
    context.Refresh = 0
    add_parameter(key='Refresh', value=context.Refresh, min=0, max=1, name='刷新', intro='', group='1', readonly=False)

    # 下面如何dict中要使用数组的话，记得都封装成struct，不要直接使用下标读取，看起来很模糊
    context.szzs_date_list = {} # 用于全局记录上证指数查询（调整后）的时间数组，格式和excel_info差不多
    context.excel_info = {} # excel表的dict数据，内容为时间的字符串+下跌数量，比如{'20230301' : 300, '20230302' : 510}
    generate_shangzhengzhishu_curve(context, str(int(context.Year)))

    # 查询成交量
    # history_data = history(symbol='SHSE.000300', frequency='600s', start_time=start_time1,  end_time=end_time1, fields='volume', adjust = ADJUST_PREV, df = True)
    # print(f"this is the history res2:{history_data}")


def on_tick(context, tick):
    print(f"enter on tick")

def on_bar(context, bars):
    print(f"enter on bar")


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
    run(strategy_id='01b8ee02-f09e-11ee-b5c3-00ff2b50aff6',
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

