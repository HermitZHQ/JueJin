# coding=utf-8
# ------------------测试策略AA
# 相关指标：solo up 7% loss limit -3.5% total up 2% total sell time 13:35
from __future__ import print_function, absolute_import
from gm.api import *
from threading import Timer

import time
import datetime
import math
import numpy as np
import pickle
import re

# ！！警告！！复制这份代码的时候一定要注意修改下面的文件路径 + 策略模式 + 买入模式，其他不用改
# 这样就可以把使用策略在一份代码内进行维护了，虽然量大，但是封装好的话，问题不大
def StrategyAA():
    pass

# 全局需要修改的变量，如果策略变化（比如买卖变化，策略本身变化）都应该调整下面的值
str_strategy = 'AA'
log_path = 'c:\\TradeLogs\\Trade' + str_strategy + '.txt'
ids_path = 'c:\\TradeLogs\\IDs-' + str_strategy + '.txt'
pos_info_path = 'c:\\TradeLogs\\Pos-' + str_strategy + '.npy'
statistics_info_path = 'c:\\TradeLogs\\Sta-' + str_strategy + '.npy'
buy_info_path = 'c:\\TradeLogs\\Buy-' + str_strategy + '.npy'

side_type = OrderSide_Buy # 设置买卖方向，买卖是不一样的，脚本切换后，需要修改
order_overtime = 15 # 设置的委托超时时间，超时后撤单，单位秒
sell_all_time = "15:35"

class BuyMode:
    def __init__(self):
        # 注意每个策略下面只能设定一种对应的买入模式（也就是只有一种可以激活到1）！！
        self.buy_all = 0 # 是否和策略B一样，直接从列表一次性全部买入，使用读出的配置数据就可以动态算出每只票的分配仓位
        self.buy_one = 0 # 买一只，并指定对应的价格
        self.buy_all_force = 1 # 一定要保证买入所有（对应数量非常大的买入，且有很多高价股，均分值无法覆盖高价股）

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
        self.AA = 1
        self.B = 0
        self.B1 = 0
        self.BA = 0
        self.C = 0
        self.M = 0

        self.buy_mode = BuyMode()
        self.order_type_buy = OrderTypeBuy()
        self.order_type_sell = OrderTypeSell()

        self.slip_step = 2 # 滑点级别，1-5，要突破5的话，可以自己算？

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
        self.tick_handle_frequence = 2

        # 多次上涨后买入，相关配置参数
        self.enable_multi_up_buy_flag = False # 多次上涨才买入的启用开关
        self.multi_up_time_line = "09:45" # 检测多次上涨的时间线
        self.highest_open_fpr = -1.0 # 记录时间线前最高的涨幅情况，针对今开价格
        self.multi_up_buy_flag = False # 多次上涨到目标比例后才买入（为了应对2次或更多到达目标后买入）
        self.multi_up_buy_need_check = True # 用于开启脚本后的检查，比如当下超过X%，就认为是需要处理（进一步等待下跌到X以下，加一次cur_count)
        self.multi_up_total_count = 1 # 总共需要检查的次数，虽然目前需求是1，但是直接做成多次的以后方便
        self.multi_up_cur_count = 0

class TargetInfo:
    def __init__(self):
        self.name = ""
        self.hold = 0
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

class MaxMinInfo:
    def __init__(self):
        self.max = -1.0
        self.min = 1.0
        self.time = None

class StatisticsInfo:
    def __init__(self):
        # 最高最低整体盈利记录
        self.lowest_total_fpr = 1.0
        self.lowest_total_fpr_time = None
        self.highest_total_fpr = -1.0
        self.highest_total_fpr_time = None
        self.cur_fpr = 0

        # limit ver为统计的虚拟止盈止损版本
        self.lowest_total_fpr_limit_ver = 1.0
        self.lowest_total_fpr_time_limit_ver = None
        self.highest_total_fpr_limit_ver = -1.0
        self.highest_total_fpr_time_limit_ver = None
        self.cur_fpr_limit_ver = 0

        # 各个卖出标的的当日最高和最低值记录
        # key:symbol, value: MaxMinFin()
        self.max_min_info_dict = {}
        

def log(msg):
    file_obj = open(log_path, 'a')

    nowtime = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
    finalMsg = nowtime + ": " + msg + "\n"
    file_obj.write(finalMsg)

    # 我们也可以把所有日志打印到控制台查看
    print(finalMsg)

def refresh(context):
    context.ids = {}
    load_ids(context)
    context.get_all_buy_price_flag = False
    context.get_all_sell_price_flag = False

    # 开始订阅目标，这里就比较麻烦了，无法快速输入
    # 统计买入和卖出的单独数量
    t = time.time()
    buy_num = 0
    handled_num = 0 # 用于计算初始化进度
    context.ids_buy = []
    context.ids_sell = []
    for k, v in context.ids.items():
        if (v.buy_flag == 1):
            if k not in context.ids_buy_target_info_dict.keys():
                context.ids_buy_target_info_dict[k] = TargetInfo()

            # 在初始化的时候就直接获取各项缓存值（反正后面也会获取，而且这里获取，会更集中）
            # 主要在这里我们可以过滤掉停牌的标的
            suspended = False
            if context.ids_buy_target_info_dict[k].pre_close == 0:
                info = get_instruments(symbols = k, skip_suspended = False, df = True)
                # empty情况一般就是ST的股票，直接先跳过不处理
                if info.empty:
                    print(f"[init][{k}]get cache info null, this should not happen......")
                    continue
                    
                # 最好不要直接使用df的值，很多奇怪的现象，比如下面的float相除，如果插入了df数据，结果是对的，但是小数点只有2位。。。。
                # 一定要先从数组里拿出来
                context.ids_buy_target_info_dict[k].pre_close = info.pre_close[0]
                context.ids_buy_target_info_dict[k].name = info.sec_name[0]
                context.ids_buy_target_info_dict[k].upper_limit = info.upper_limit[0]
                context.ids_buy_target_info_dict[k].suspended = True if (info.is_suspended[0] == 1) else False

            suspended = context.ids_buy_target_info_dict[k].suspended

            if not suspended:
                buy_num += 1
                context.ids_buy.append(k)
            else:
                del context.ids_buy_target_info_dict[k]
        else:
            context.ids_sell.append(k)
            if k not in context.ids_virtual_sell_target_info_dict.keys():
                context.ids_virtual_sell_target_info_dict[k] = TargetInfo()
            if k not in context.statistics.max_min_info_dict.keys():
                context.statistics.max_min_info_dict[k] = MaxMinInfo()
        handled_num += 1
        print(f"初始化数据进度：Key[{k}] [{round(handled_num / len(context.ids.items()) * 100, 2)}%]")
    print(f"初始化总计耗时:[{time.time() - t:.4f}]s，标的总数[{len(context.ids.items())}]")
    context.buy_num = buy_num
    context.sell_num = len(context.ids) - buy_num

    # 检测一次是否有删除的id，在保存的ids_virtual_sell_target_info_dict中，应该去除（停牌等），否则无法正常统计
    del_keys = []
    for k in context.ids_virtual_sell_target_info_dict.keys():
        # 这里的条件不能是不存在就删，因为还有一种情况需要保留，就是sell列表为空的时候（否则删除后无法继续统计信息）
        # 也就是说，我们在sell为空时，并不删除缓存对象，只在sell列表存在，并只清除一部分的时候才删除（这时候我们是删除不需要，或者停牌之类的）
        if (k not in context.ids.keys()) and (len(context.ids_sell) > 0):
            # 不能在迭代的途中去删除目标中的值，会出现运行错误，先记录下来，然后再单独删除
            del_keys.append(k)
    for k in del_keys:
        del context.ids_virtual_sell_target_info_dict[k]

    # ------看是否需要重新统计卖出票的总市值（注意是卖出票，不含买入）
    # 即便设置不是-1，我们也应该检查一次（我之前就误操作，前一天下午开过脚本，忘记重置-1，结果load的都是昨天的sell，导致今天的脚本完全无法正常运行）
    if context.calculate_total_market_value_flag:
        context.total_market_value_for_all_sell = 0
        for symb in context.ids_sell:
            pos = context.account().position(symbol = symb, side = OrderSide_Buy)
            amount = (pos.available_now * pos.vwap) if pos else 0
            context.total_market_value_for_all_sell += amount
        
        if context.total_market_value_for_all_sell > 0:
            over_write_mv(context.total_market_value_for_all_sell)
            save_sell_position_info_with_init(context)
            save_statistics_info(context)
            load_buy_info(context)
    # else:
    #     tmp_total_market_value_for_all_sell = 0
    #     for symb in context.ids_sell:
    #         pos = context.account().position(symbol = symb, side = OrderSide_Buy)
    #         amount = (pos.available_now * pos.vwap) if pos else 0
    #         tmp_total_market_value_for_all_sell += amount

    #     if (tmp_total_market_value_for_all_sell != context.total_market_value_for_all_sell) and (tmp_total_market_value_for_all_sell > 0):
    #         context.total_market_value_for_all_sell = tmp_total_market_value_for_all_sell
    #         over_write_mv(context.total_market_value_for_all_sell)
    #         save_sell_position_info_with_init(context)
    #         save_statistics_info(context)
    #         load_buy_info(context)

    # 频率, 支持 ‘tick’, ‘60s’, ‘300s’, ‘900s’ 等, 默认’1d’
    # 60s以上都是走on_bar，只有tick走的on_tick，一般来说交易肯定是要走tick的
    subscribe(symbols=context.ids.keys(), frequency='tick', count=1, unsubscribe_previous=True)
    # 用1s频率的bar函数来更新总盈亏，否则tick中循环用current很慢
    #subscribe(symbols='SZSE.000001', frequency='15s', count=1, unsubscribe_previous=False)
    #log(f'已订阅目标：{context.ids.keys()} 总数量：{len(context.ids)} 买入数量：{buy_num} 卖出数量：{len(context.ids) - buy_num}')
    #log(f'已订阅：{context.symbols} 数量：{len(context.symbols)}')    

    # 手动清空buy info，里面记录的买入价格，文件太大需要清空，则修改控制参数后，点击刷新
    if (context.clear_buy_info_flag):
        context.buy_pos_dict = {}
        save_buy_info(context)


def refresh_statistics_info(context):
    # 刷新后显示一下目前最新的最高值和最低值
    print(f"最高：{round(context.statistics.highest_total_fpr * 100, 3)}% 出现时间：{context.statistics.highest_total_fpr_time}")
    print(f"最低：{round(context.statistics.lowest_total_fpr * 100, 3)}% 出现时间：{context.statistics.lowest_total_fpr_time}")
    print(f"当前盈利：{round(context.statistics.cur_fpr * 100, 3)}%\n")

    print(f"[止]最高：{round(context.statistics.highest_total_fpr_limit_ver * 100, 3)}% 出现时间：{context.statistics.highest_total_fpr_time_limit_ver}")
    print(f"[止]最低：{round(context.statistics.lowest_total_fpr_limit_ver * 100, 3)}% 出现时间：{context.statistics.lowest_total_fpr_time_limit_ver}")
    print(f"[止]当前盈利：{round(context.statistics.cur_fpr_limit_ver * 100, 3)}%\n")

    # print(f"---------------------------------Sell-Emu-Info:\n")
    # for k,v in context.ids_virtual_sell_target_info_dict.items():
    #     print(f"[{k}], sold[{v.sold_flag}], vwap[{round(v.vwap, 3)}], sold_price[{round(v.sold_price, 3)}], mv[{round(v.sold_mv, 3)}]")

    # print(f"---------------------------------Sell-Pos-Info:\n")
    # cur_mv = 0
    # for k,v in context.sell_pos_dict.items():
    #     print(f"[{k}], hold[{v[0]}] sold[{v[1]}] sold_price[{v[2]}]")
    #     if not v[1]:
    #         cur_mv += v[0] * context.ids_virtual_sell_target_info_dict[k].price
    #     else:            
    #         cur_mv += v[0] * v[2]
    # print(f"cur mv:[{cur_mv}], sell_total_mv[{context.total_market_value_for_all_sell}], total_fpr[{((cur_mv - context.total_market_value_for_all_sell) / context.total_market_value_for_all_sell) if context.total_market_value_for_all_sell != 0 else 0}]")


# 统一所有策略的配置文件读取，不然每个策略都要重写没有必要，想办法加入必要的配置就好
def load_ids(context):
    # 看股票代码就能分辨，上证股票是在上海交易所上市的股票，股票代码以600、601、603开头，科创板（在上海交易所上市）股票代码以688开头
    # 深市股票是在深市交易所上市的股票，股票代码以000、002、003开头，创业板（在深圳交易所上市）股票代码以300开头。
    # 
    # 简化使用的话，就是6开头就都是上交所的，其他都是深交所（当然这种情况没有处理错误的存在）
    # SHSE(上交所), SZSE(深交所)
    # ！！！这里读取的配置文件，要根据策略改变
    file_obj = open(ids_path, 'r')
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
                context.calculate_total_market_value_flag = True
                log(f"did not find valid market value, need re-calculate")
            else:
                log(f"find valid total market value:{mv}")
                context.calculate_total_market_value_flag = False
                context.total_market_value_for_all_sell = mv
                load_sell_position_info_with_init(context)
                load_statistics_info(context)
                load_buy_info(context)
        else:
            should_add = False
            print(f'读取IDs配置错误：{str_tmp}')

        # 开始我固定了一些特殊标记的位置，比如高预期一定要是最后一位的h，卖出时倒数第二位，其实没有必要
        # 我们判断长度大于6（股票代码）后，直接把后几位的字符都拿出来保存，然后判断有没有就可以了
        flags = []
        if should_add and len(original_id) > 6:
            for i in range(0, len(original_id) - 6):
                flags.append(original_id[6 + i])

            #print(flags)

        # 判断是否为High Expect（高预期）股票
        high_expect = True if 'h' in flags else False
        # 判断是否要无视条件直接卖出
        force_sell = True if 's' in flags else False
        # 判断是否要无视条件直接买入
        force_buy = True if 'b' in flags else False

        buy_amount = 0
        buy_rate = 0
        # 判定是否设置了单独买入的数量或者比例
        if ('#' in flags):
            if '%' in flags:
                buy_rate = float(re.findall(r"#(.*?)%#", original_id)[0]) / 100.0
            else:
                buy_amount = float(re.findall(r"#(.*?)#", original_id)[0]) * 10000.0

            #print(f"buy amount:{buy_amount}, buy_rate:{buy_rate}")

        left_cash = context.account().cash['available'] # 余额
        left_cash = float('%.2f' % left_cash)
        
        if buy_rate > 0:
            buy_amount = left_cash * buy_rate
        # if buy_amount > left_cash:
        #     log(f"[Error]设置的买入金额:{buy_amount}超过了余额:{left_cash}，自动将数值降低到目前余额")
        #     buy_amount = left_cash

        # 判定是否设定了卖出（买入）的比例（R）或者时间（T），比如设定卖出比例就是SR1SR，表示上涨超过1%卖出
        # ST10:35ST，标识到达时间10点35分后就卖出，买入的话就是把S改为B，记得一定要大写，和小写的强制买入卖出标记区别开来
        sell_with_rate = 1
        sell_with_time = "17:31" # 初始化到收盘后
        sell_with_price = 0
        sell_with_num = 0
        buy_with_rate = 1
        buy_with_time = "17:31"
        buy_with_price = 0
        buy_with_num = 0

        if ('S' in flags) and ('R' in flags):
            sell_with_rate = float(re.findall(r"SR(.*?)SR", original_id)[0]) / 100.0
        if ('S' in flags) and ('T' in flags):
            sell_with_time = re.findall(r"ST(.*?)ST", original_id)[0]
        if ('S' in flags) and ('P' in flags):
            sell_with_price = float(re.findall(r"SP(.*?)SP", original_id)[0])
        if ('S' in flags) and ('N' in flags):
            sell_with_num = float(re.findall(r"SN(.*?)SN", original_id)[0])
        if ('B' in flags) and ('R' in flags):
            buy_with_rate = float(re.findall(r"BR(.*?)BR", original_id)[0]) / 100.0
        if ('B' in flags) and ('T' in flags):
            buy_with_time = re.findall(r"BT(.*?)BT", original_id)[0]
        if ('B' in flags) and ('P' in flags):
            buy_with_price = float(re.findall(r"BP(.*?)BP", original_id)[0])
        if ('B' in flags) and ('N' in flags):
            buy_with_num = float(re.findall(r"BN(.*?)BN", original_id)[0])

        # 取数组最后n位（-1，-2......）
        #print(f"test -1::::: {str_tmp[-1:]}")sss
        
        # test info, open it when you need debug
        #print(f'high expect:{high_expect} force sell:{force_sell} force buy:{force_buy} buy_amount:{buy_amount} buy_rate:{buy_rate} sell_with_up:{sell_with_rate} sell_with_time:{sell_with_time} buy_with_up:{buy_with_rate} buy_with_time:{buy_with_time}')
        if (should_add):
            if str_tmp in context.ids.keys():
                context.ids[str_tmp].buy_flag = 1 if buy_flag else 0
                context.ids[str_tmp].high_expected_flag = high_expect
                context.ids[str_tmp].force_sell_flag = force_sell
                context.ids[str_tmp].force_buy_flag = force_buy

                context.ids[str_tmp].buy_with_rate = buy_with_rate
                context.ids[str_tmp].buy_with_time = buy_with_time
                context.ids[str_tmp].buy_with_price = buy_with_price
                context.ids[str_tmp].buy_with_num = buy_with_num
                if buy_with_num > 0:
                    context.ids[str_tmp].buy_with_num_need_handle = True
                    context.ids[str_tmp].buy_with_num_handled_flag = False
                else:
                    context.ids[str_tmp].buy_with_num_need_handle = False
                context.ids[str_tmp].sell_with_rate = sell_with_rate
                context.ids[str_tmp].sell_with_time = sell_with_time
                context.ids[str_tmp].sell_with_price = sell_with_price
                context.ids[str_tmp].sell_with_num = sell_with_num

                # 在ids已经存在的情况下，我们不刷新买入数额，数额只在key不存在的时候记录
                # 否则有些问题，比如我们设置的10%，但是余额是变化的，如果变多了，我们就会去买入更多，就不正常了
                # 没有设置买入百分比的话，我们可以重置买入数量
                if buy_rate == 0:
                    context.ids[str_tmp].buy_amount = buy_amount
            else:
                context.ids[str_tmp] = LoadedIDsInfo()
                context.ids[str_tmp].buy_flag = 1 if buy_flag else 0
                context.ids[str_tmp].high_expected_flag = high_expect
                context.ids[str_tmp].force_sell_flag = force_sell
                context.ids[str_tmp].force_buy_flag = force_buy

                context.ids[str_tmp].buy_with_rate = buy_with_rate
                context.ids[str_tmp].buy_with_time = buy_with_time
                context.ids[str_tmp].buy_with_price = buy_with_price
                context.ids[str_tmp].buy_with_num = buy_with_num
                if buy_with_num > 0:
                    context.ids[str_tmp].buy_with_num_need_handle = True
                    context.ids[str_tmp].buy_with_num_handled_flag = False
                else:
                    context.ids[str_tmp].buy_with_num_need_handle = False
                context.ids[str_tmp].sell_with_rate = sell_with_rate
                context.ids[str_tmp].sell_with_time = sell_with_time
                context.ids[str_tmp].sell_with_price = sell_with_price
                context.ids[str_tmp].sell_with_num = sell_with_num

                # 只在初始化时，计算一次应该买入的量，否则后面余额发生变化就不对了
                # [TODO]应该保存文件更稳
                context.ids[str_tmp].buy_amount = buy_amount
                

    #print(f"below is context ids info:\n{context.ids}")


def over_write_mv(new_val):
    # 有一个test.txt文件内容为：    查找在字符串里第一个出现的子串并替换
    # 打开文件，读取文件
    f = open(ids_path, mode='r')
    data = f.read()
    # print(data)

    # 获取开始索引和结束索引，获得需要替换的值
    index = data.find('mv:')
    if -1 == index:
        print("did not find target string.....")
        return

    start = index + len('mv:')
    # end = data.find('出现', start)
    end = len(data)
    str1 = data[start:end]
    str2 = str(new_val) # 需要替换的值，注意这里替换是替换所有相同值，所以初始值不能用0，否则像300这种也会被替换
    # print(f"str1{str1} str2{str2}")
    data_new = data.replace(str1, str2)
    # print("----------------------start replace----------------------------")
    # print(data_new)
    # print("----------------------end replace----------------------------")

    # 把修改的内容写回文件
    f_new = open(ids_path, mode='w')
    f_new.write(data_new)

def over_write_force_sell_all_flag(new_val):
    # 有一个test.txt文件内容为：    查找在字符串里第一个出现的子串并替换
    # 打开文件，读取文件
    f = open(ids_path, mode='r')
    data = f.read()
    # print(data)

    # 获取开始索引和结束索引，获得需要替换的值
    index = data.find('fsa------')
    if -1 == index:
        print("did not find target string.....")
        return
    # start = index + len('fsa')
    start = index

    # end = data.find('出现', start)
    end = index + len('fsa------')

    str1 = data[start:end]
    str2 = 'fs------' # 需要替换的值，注意这里替换是替换所有相同值，所以初始值不能用0，否则像300这种也会被替换
    # print(f"str1{str1} str2{str2}")
    data_new = data.replace(str1, str2)

    # print("----------------------start replace----------------------------")
    # print(data_new)
    # print("----------------------end replace----------------------------")

    # 把修改的内容写回文件
    f_new = open(ids_path, mode='w')
    f_new.write(data_new)

def auto_generate_sell_list_with_ids_file(context):
    f = open(ids_path, mode='r')
    data = f.read()

    # 获取开始索引和结束索引，获得需要替换的值
    index = data.find('fs------')
    if -1 == index:
        print("did not find target string.....")
        return
    #start = index + len('fs------')
    start = index

    end = data.find('--------MarketValueRecord', start)
    #end = index + len('--------MarketValueRecord')

    # 拿到从fs-----开始，到列表最后的所有内容，到时候整体替换
    str1 = data[start:end]
    #print(f"test auto move----------\n{str1.strip()}\nend")

    # strtest = "SZSE.600601"
    # print(f"test arr, {strtest[5:]}")

    # 重新组合应该替换的内容
    rep_str = "fs------\n"
    for pos in context.account().positions(symbol='', side=None):
        rep_str += pos.symbol[5:]
        rep_str += "\n"

    data_new = data.replace(str1, rep_str)
    #print(f"after replace context:\n{data_new}\nend")

    # 把修改的内容写回文件
    f_new = open(ids_path, mode='w')
    f_new.write(data_new)


def save_sell_position_info_with_init(context):
    context.sell_pos_dict.clear()
    for symb in context.ids_sell:
        pos = context.account().position(symbol = symb, side = OrderSide_Buy)
        curHolding = pos.available_now if pos else 0
        # 如果持仓为0，则不要进行记录，比如有时候ID列表里面设置了错误的ID,该ID并没有持仓，这会造成后续的统计错误
        if curHolding == 0:
            continue
        # 数据说明：持仓量，是否已经卖出，卖出时的均价（用于计算整体盈利）
        context.sell_pos_dict[symb] = [curHolding, False, 0.0]
    
    np.save(pos_info_path, context.sell_pos_dict)

# 更新信息只在全部卖出后，才记录卖出的成交均价，持仓量，我们只在当天第一次开启脚本的时候获取就可以了
def update_sell_position_info(context, symbol, sell_flag, sell_price):
    if symbol in context.sell_pos_dict.keys():
        context.sell_pos_dict[symbol][1] = sell_flag
        context.sell_pos_dict[symbol][2] = sell_price
        print(f"update sell pos info sym:{symbol} sell_flag:{sell_flag}")
        np.save(pos_info_path, context.sell_pos_dict)

    # 卖出后，清理buy_pos_dict中保存的值
    # 和2点全部清理进行互补，万一2点之前就开始买入了，这里也能有较大的作用，只要不是通过手动卖出的
    if symbol in context.buy_pos_dict.keys():
        del context.buy_pos_dict[symbol]

    for k,v in context.sell_pos_dict.items():
        if not v[1]:
            return # 只要还有没卖出的，我们就不统计精确的整体盈利值

    cur_market_value = 0
    for k,v in context.sell_pos_dict.items():
        if not v[1]:
            # mv = float(current(k)[0]['price']) * v[0]
            # cur_market_value += mv
            log(f"should never happen...., just in case")
        else:
            cur_market_value += (v[0] * v[2])

    # 现在策略AB应该是可以共用一套了，因为不管是否存在买入和卖出的混合，我们有了当天的文件缓存后，都可以计算正确的整体盈利了
    # 之前的话，因为没有文件缓存，所以逻辑上有点混乱，现在是很清晰的
    total_float_profit_rate = (cur_market_value - context.total_market_value_for_all_sell) / context.total_market_value_for_all_sell if context.total_market_value_for_all_sell != 0 else 0
    log(f"[statistics]全部卖出后的精确统计值(不加税费)，整体盈利为：{round(total_float_profit_rate * 100, 3)}%")


def load_sell_position_info_with_init(context):
    context.sell_pos_dict = np.load(pos_info_path, allow_pickle=True) # 输出即为Dict类型
    context.sell_pos_dict = dict(context.sell_pos_dict.tolist())
    # print("--------------------start load sell pos info")
    # print(context.sell_pos_dict)
    # print("--------------------end load sell pos info\n")

    for k,v in context.sell_pos_dict.items():
        if (k in context.ids.keys()) and (context.ids[k].buy_flag == 0) and (k not in context.ids_virtual_sell_target_info_dict.keys()):
            context.ids_virtual_sell_target_info_dict[k] = TargetInfo()
        

#change mark2
def save_buy_info(context):
    np.save(buy_info_path, context.buy_pos_dict)

def update_buy_info(context, symbol, price):
    if not context.buy_pos_dict:
        return
    log(f"[statistics]{symbol} 更新记录买入价格：{price}")
    context.buy_pos_dict[symbol] = price
    np.save(buy_info_path, context.buy_pos_dict)

def load_buy_info(context):
    context.buy_pos_dict = np.load(buy_info_path, allow_pickle=True) # 输出即为Dict类型
    context.buy_pos_dict = dict(context.buy_pos_dict.tolist())
    #print("--------------------start load buy pos info")
    #print(context.buy_pos_dict)
    #print("--------------------end load buy pos info\n")


def save_statistics_info(context):
    f = open(statistics_info_path, 'wb')
    pickle.dump(context.statistics, f, pickle.HIGHEST_PROTOCOL)


def load_statistics_info(context):
    f = open(statistics_info_path, 'rb')
    context.statistics = pickle.load(f) # 输出即为Dict类型
    #print("--------------------start load statistics info")
    #print(context.statistics.max_min_info_dict)
    #print("--------------------end load statistics info\n")


def on_parameter(context, parameter):
    #print(parameter)
    if (parameter.key == 'Buy_In_Fall_Rate'):
        print(f'Buy_In_Fall_Rate 参数已经调整为：{parameter.value}')
        context.Buy_In_Fall_Rate = parameter.value
    if (parameter.key == 'Buy_In_Up_Rate'):
        print(f'Buy_In_Up_Rate 参数已经调整为：{parameter.value}')
        context.Buy_In_Up_Rate = parameter.value
    elif (parameter.key == 'Buy_In_Limit_Num'):
        print(f'Buy_In_Limit_Num 参数已经调整为：{parameter.value}')
        context.Buy_In_Limit_Num = parameter.value
    elif (parameter.key == 'Use_Close'):
        print(f'Use_Close 参数已经调整为：{parameter.value}')
        context.Use_Close = parameter.value
    elif (parameter.key == 'Sell_Increase_Rate'):
        print(f'Sell_Increase_Rate 参数已经调整为：{parameter.value}')
        context.Sell_Increase_Rate = parameter.value
    elif (parameter.key == 'Sell_All_Increase_Rate'):
        print(f'Sell_All_Increase_Rate 参数已经调整为：{parameter.value}')
        context.Sell_All_Increase_Rate = parameter.value
    elif (parameter.key == 'Sell_All_Loss_Rate'):
        print(f'Sell_All_Loss_Rate 参数已经调整为：{parameter.value}')
        context.Sell_All_Loss_Rate = parameter.value
    elif (parameter.key == 'Sell_Loss_Limit'):
        print(f'Sell_Loss_Limit 参数已经调整为：{parameter.value}')
        context.Sell_Loss_Limit = parameter.value
    elif (parameter.key == 'clear_buy_info_flag'):
        print(f'clear_buy_info_flag 参数已经调整为：{parameter.value}')
        context.clear_buy_info_flag = parameter.value
    elif (parameter.key == 'test_info'):
        print(f'test_info 参数已经调整为：{parameter.value}')
        context.test_info = parameter.value
        refresh_statistics_info(context)
        if context.test_info == 99:
            # over_write_mv(-1) # 这里重置为0问题不大，因为市值一般都是两位小数的float，比如1234.68，目前感觉是不会替换到有效id数据的
            # over_write_force_sell_all_flag('') # 重置强制卖出标记，避免忘记后，第二天被直接全卖
            # auto_generate_sell_list_with_ids_file(context)
            output_final_statistics(context)
    elif (parameter.key == 'Refresh'):
        log("重新载入ids，重新订阅！")
        refresh(context)


# 策略中必须有init方法
def init(context):
    # 订阅行情数量（-1表示全部订阅）
    # context.max_count = 5000
    # all_stock = get_instruments(exchanges='SHSE, SZSE', sec_types=1, fields='symbol, delisted_date', df=True)
    # subscribe(symbols=all_stock['symbol'].tolist()[:context.max_count], frequency='60s', count=5)
    # print('订阅标的数量', len(context.symbols))
    # return

    # 初始化一些全局用变量--------
    # 保存策略信息以及买入方式到全局变量中
    context.strategy_info = StrategyInfo()

    log("\n\n\n\n\n\n\n\n策略脚本初始化开始--------")
    context.test_info = 0
    context.record_sell_time = 0 # 用于记录整体卖出时的时间和瞬间整体盈利值
    context.record_sell_tfpr = 0
    add_parameter(key='test_info', value=context.test_info, min=-1, max=1, name='TestInfo', intro='', group='3', readonly=False)
    #print(f'{context.now.strftime("%H:%M:%S")}')
    context.tick_count_for_statistics = 0 # 记录经过的tick次数，有些函数不需要每次tick都调用，会造成性能损耗，用这个变量进行控制
    context.tick_count_for_sell = 0 # 用于控制sell函数中一些消耗较大的代码块的运行频率
    context.tick_count_limit_rate_for_sell = 0.5 # 具体的控制百分比（针对context.ids的长度），比如有1000标的，那么0.2就是20%，200只标的经过后，再运行一次
    context.tick_count_for_sell_ok = False # 记录当前是否满足频率，避免每次都要和rate做乘法后比较
    context.tick_count_for_buy = 0
    context.tick_count_limit_rate_for_buy = 0.5
    context.tick_count_for_buy_ok = False 
    context.get_all_sell_price_flag = False
    context.get_all_buy_price_flag = False

    if context.strategy_info.order_type_buy.Limit == 1:
        context.order_type_buy = OrderType_Limit
    elif context.strategy_info.order_type_buy.Market == 1:
        context.order_type_buy = OrderType_Market

    if context.strategy_info.order_type_sell.Limit == 1:
        context.order_type_sell = OrderType_Limit
    elif context.strategy_info.order_type_sell.Market == 1:
        context.order_type_sell = OrderType_Market

    context.start_operation_time = "09:30"
    if context.strategy_info.A1 == 1:
        context.start_operation_time = "09:30"
    elif context.strategy_info.A == 1:
        context.start_operation_time = "09:30"

    # 整体数据为ditc，key=symbol，value = LoadedIDsInfo()
    context.ids = {}
    # 强制整体卖出（配置文件）标记
    context.force_sell_all_flag = False
    # 记录已买入的key（实际执行了买入接口的）
    context.already_buy_in_keys = []
    # 记录买入后的订单信息，防止重复买入
    context.client_order = {}
    # 记录最高的整理盈利情况以及当时的时间（该值只在连续运行脚本的情况下有效，统一在下午的2点59分输出到日志一次）
    context.statistics = StatisticsInfo()
    # 手动产生statistics info的初始文件（修改结构体后，之前的文件无法使用）
    if 0:
        context.statistics.highest_total_fpr = 0.3
        context.statistics.highest_total_fpr_time = context.now
        context.statistics.lowest_total_fpr = -0.05
        context.statistics.lowest_total_fpr_time = context.now
        context.statistics.cur_fpr = 0.123

        context.statistics.highest_total_fpr_limit_ver = 0.3
        context.statistics.highest_total_fpr_time_limit_ver = context.now
        context.statistics.lowest_total_fpr_limit_ver = -0.05
        context.statistics.lowest_total_fpr_time_limit_ver = context.now
        context.statistics.cur_fpr_limit_ver = 0.123
        print("start save statistics info................................")
        save_statistics_info(context)

    # 是否达到全局设定的盈利目标，初始化为false，但是后续条件一旦触发后，不再改回false
    # 因为操作那几秒，没法预估情况，有可能下降到1.99%，或者是先卖出了盈利高的，剩下的继续计算总盈利就不正确了
    # 所以一旦激活就直接全部卖出，忽略过程中的变化
    context.sell_with_total_float_profit_flag = False
    context.sell_with_total_float_loss_flag = False
    context.sell_with_time_limit_flag = False
    # 计算总市值，在开启脚本，且mv:0时统计一次，这样好计算全局的1.17%涨幅，关键要想办法自动重置到mv:0
    # 我目前想法是2点59分的时候，去把这个值覆写到mv:0
    context.calculate_total_market_value_flag = False
    context.total_market_value_for_all_sell = 0
    # 记录卖出持仓信息dict，这样才能保证全部卖出后，或者重新启动脚本时，能够拿到正常值    
    context.sell_pos_dict = {}
    
    # 记录买入的持仓信息，解决连续买入和卖出同一标的导致的成本上升或下降问题
    # 直接使用记录的成本值来替代持仓均价vwap
    # 这个数据的重置时间不是3点了，3点重置的是卖出相关数据，买入的话我们在1点35分，也就是设置的整体卖出之后重置它
    # 重置的时候有可能没有卖完，使用要判断使用的数据是否正常，比如为0的话，肯定就还是要用vwap替代
    # 暂时没有想到其他问题了
    context.buy_pos_dict = {} # buy info，需要手动清空
    context.clear_buy_info_flag = 0
    add_parameter(key='clear_buy_info_flag', value=context.clear_buy_info_flag, min=-1, max=1, name='是否清空BuyInfo', intro='', group='1', readonly=False)
    
    # 我们更新market value不能太频繁，否则就会出现如果有50只票，50个tick，每个都需要两秒，相当于100秒才能循环一次
    # 我开始思考过用时间差，比如控制1秒更新一次，其实也不行，因为数量上去以后，更新一次就要1秒多2秒，相当于还是一直更新
    # 目前看来靠谱的办法，就只有缓存上一帧的所有tick price，这样速度肯定最快，不用去服务器查询（current）
    # 只是这种方式，在第一次拿到所有有效值之前，肯定有很多0的价格，需要特殊处理，否则可能会激活整体亏损？（虽然暂时没有加这个）
    context.tfpr = 0.0 # total float profit rate
    # 该dict用于临时缓存所有标的的价格以及持仓成本，为了移除current查询价格带来的缓慢问题
    # 数据格式：key->symbol, value->TargetInfo()类
    # 该dict是用于虚拟止盈止损版本的信息统计，有些数据不能乱用，比如sold_mv，不是真实的卖出mv，需要注意！！
    context.ids_virtual_sell_target_info_dict = {}
    context.ids_buy_target_info_dict = {}

    # 手动产生buy_info的初始文件
    # save_buy_info(context)
    # 初始化动态加载的id文件--------
    load_ids(context)

    # 初始化动态参数--------
    # 买入参数
    context.Buy_In_Fall_Rate = 0.01
    add_parameter(key='Buy_In_Fall_Rate', value=context.Buy_In_Fall_Rate, min=-1, max=1, name='买入时下跌比例', intro='', group='1', readonly=False)
    context.Buy_In_Up_Rate = 0.03
    add_parameter(key='Buy_In_Up_Rate', value=context.Buy_In_Up_Rate, min=-1, max=1, name='买入时上涨比例', intro='', group='1', readonly=False)

    context.Buy_In_Limit_Num = 5000
    add_parameter(key='Buy_In_Limit_Num', value=context.Buy_In_Limit_Num, min=0, max=1, name='策略买入数量', intro='', group='1', readonly=False)
    context.Use_Close = 1
    add_parameter(key='Use_Close', value=context.Use_Close, min=0, max=1, name='是否使用昨收', intro='', group='1', readonly=False)
    # 卖出参数
    context.Sell_Increase_Rate = 0.2
    if context.strategy_info.B == 1:
        context.Sell_Increase_Rate = 0.07
    elif context.strategy_info.BA == 1:
        context.Sell_Increase_Rate = 0.07
    elif context.strategy_info.AA == 1:
        context.Sell_Increase_Rate = 0.12
    add_parameter(key='Sell_Increase_Rate', value=context.Sell_Increase_Rate, min=-1, max=1, name='卖出时涨幅比例', intro='', group='2', readonly=False)

    context.Sell_Loss_Limit = -0.2
    if context.strategy_info.B == 1:
        context.Sell_Loss_Limit = -0.035
    elif context.strategy_info.BA == 1:
        context.Sell_Loss_Limit = -0.035
    elif context.strategy_info.AA == 1:
        context.Sell_Loss_Limit = -0.04
    add_parameter(key='Sell_Loss_Limit', value=context.Sell_Loss_Limit, min=-1, max=1, name='止损比例', intro='', group='2', readonly=False)

    context.Sell_All_Increase_Rate = 0.2
    context.sell_all_chase_raise_flag = False
    context.sell_all_chase_highest_record = -1.0
    context.sell_all_lower_limit = 0.0066
    if context.strategy_info.B == 1:
        context.Sell_All_Increase_Rate = 0.0066
    elif context.strategy_info.BA == 1:
        context.Sell_All_Increase_Rate = 0.0045
    elif context.strategy_info.A == 1:
        context.Sell_All_Increase_Rate = 0.0113
    elif context.strategy_info.AA == 1:
        context.Sell_All_Increase_Rate = 0.02
        
    context.Sell_All_Loss_Rate = -0.2
    if context.strategy_info.B == 1:
        context.Sell_All_Loss_Rate = -0.016
    elif context.strategy_info.BA == 1:
        context.Sell_All_Loss_Rate = -0.016
    elif context.strategy_info.AA == 1:
        context.Sell_All_Loss_Rate = -1.035
    add_parameter(key='Sell_All_Increase_Rate', value=context.Sell_All_Increase_Rate, min=-1, max=1, name='整体涨幅', intro='', group='2', readonly=False)
    add_parameter(key='Sell_All_Loss_Rate', value=context.Sell_All_Loss_Rate, min=-1, max=1, name='整体止损', intro='', group='2', readonly=False)
    # 取巧参数（参数赋值没有实际意义，只是用来重载ids配置文件），该参数变化后，重新load ids，重新订阅最新加载的ids
    context.Refresh = 0.01
    add_parameter(key='Refresh', value=context.Refresh, min=-1, max=1, name='刷新', intro='', group='4', readonly=False)

    # 开始订阅目标，这里就比较麻烦了，无法快速输入
    # 统计买入和卖出的单独数量
    t = time.time()
    buy_num = 0
    handled_num = 0 # 用于显示处理进度
    context.ids_buy = []
    context.ids_sell = []
    for k, v in context.ids.items():
        if (v.buy_flag == 1):
            context.ids_buy_target_info_dict[k] = TargetInfo()

            # 在初始化的时候就直接获取各项缓存值（反正后面也会获取，而且这里获取，会更集中）
            # 主要在这里我们可以过滤掉停牌的标的
            suspended = False
            if context.ids_buy_target_info_dict[k].pre_close == 0:
                info = get_instruments(symbols = k, skip_suspended = False, df = True)
                # empty情况一般就是ST的股票，直接先跳过不处理
                if info.empty:
                    print(f"[init][{k}]get cache info null, this should not happen......")
                    continue
                    
                # 最好不要直接使用df的值，很多奇怪的现象，比如下面的float相除，如果插入了df数据，结果是对的，但是小数点只有2位。。。。
                # 一定要先从数组里拿出来
                context.ids_buy_target_info_dict[k].pre_close = info.pre_close[0]
                context.ids_buy_target_info_dict[k].name = info.sec_name[0]
                context.ids_buy_target_info_dict[k].upper_limit = info.upper_limit[0]
                context.ids_buy_target_info_dict[k].suspended = True if (info.is_suspended[0] == 1) else False

            suspended = context.ids_buy_target_info_dict[k].suspended

            # 没有停牌的情况，才处理
            if not suspended:
                buy_num += 1
                context.ids_buy.append(k)
            else:
                del context.ids_buy_target_info_dict[k]
        else:
            context.ids_sell.append(k)
            context.ids_virtual_sell_target_info_dict[k] = TargetInfo()
            context.statistics.max_min_info_dict[k] = MaxMinInfo()
        handled_num += 1
        print(f"初始化数据进度：Key[{k}] [{round(handled_num / len(context.ids.items()) * 100, 2)}%]")
    print(f"初始化总计耗时:[{time.time() - t:.4f}]s，标的总数[{len(context.ids.items())}]")
    context.buy_num = buy_num
    context.sell_num = len(context.ids) - buy_num

    # 检测一次是否有删除的id，在保存的ids_virtual_sell_target_info_dict中，应该去除（停牌等），否则无法正常统计
    del_keys = []
    for k in context.ids_virtual_sell_target_info_dict.keys():
        # 这里的条件不能是不存在就删，因为还有一种情况需要保留，就是sell列表为空的时候（否则删除后无法继续统计信息）
        # 也就是说，我们在sell为空时，并不删除缓存对象，只在sell列表存在，并只清除一部分的时候才删除（这时候我们是删除不需要，或者停牌之类的）
        if (k not in context.ids.keys()) and (len(context.ids_sell) > 0):
            # 不能在迭代的途中去删除目标中的值，会出现运行错误，先记录下来，然后再单独删除
            del_keys.append(k)
    for k in del_keys:
        del context.ids_virtual_sell_target_info_dict[k]

    # ------看是否需要重新统计卖出票的总市值（注意是卖出票，不含买入）
    # 即便设置不是-1，我们也应该检查一次（我之前就误操作，前一天下午开过脚本，忘记重置-1，结果load的都是昨天的sell，导致今天的脚本完全无法正常运行）
    if context.calculate_total_market_value_flag:
        context.total_market_value_for_all_sell = 0
        for symb in context.ids_sell:
            pos = context.account().position(symbol = symb, side = OrderSide_Buy)
            amount = (pos.available_now * pos.vwap) if pos else 0
            context.total_market_value_for_all_sell += amount
        
        if context.total_market_value_for_all_sell > 0:
            over_write_mv(context.total_market_value_for_all_sell)
            save_sell_position_info_with_init(context)
            save_statistics_info(context)
            load_buy_info(context)
    # else:
    #     tmp_total_market_value_for_all_sell = 0
    #     for symb in context.ids_sell:
    #         pos = context.account().position(symbol = symb, side = OrderSide_Buy)
    #         amount = (pos.available_now * pos.vwap) if pos else 0
    #         tmp_total_market_value_for_all_sell += amount

    #     if (tmp_total_market_value_for_all_sell != context.total_market_value_for_all_sell) and (tmp_total_market_value_for_all_sell > 0):
    #         context.total_market_value_for_all_sell = tmp_total_market_value_for_all_sell
    #         over_write_mv(context.total_market_value_for_all_sell)
    #         save_sell_position_info_with_init(context)
    #         save_statistics_info(context)
    #         load_buy_info(context)

    # 手动生成buy_info，现在流程还不太稳定，有时候会误删，这里是手动生成
    # 注意是从buy还是sell的list生成，可能需要改动
    if 0:
        for symb in context.ids_sell:
            context.buy_pos_dict[symb] = 0
            pos = context.account().position(symbol = symb, side = OrderSide_Buy)
            update_buy_info(context, symb, pos.vwap)


    # --------订阅接口
    # 频率, 支持 ‘tick’, ‘60s’, ‘300s’, ‘900s’ 等, 默认’1d’
    # 60s以上都是走on_bar，只有tick走的on_tick，一般来说交易肯定是要走tick的
    subscribe(symbols=context.ids.keys(), frequency='tick', count=1, unsubscribe_previous=True)
    # 用1s频率的bar函数来更新总盈亏，否则tick中循环用current很慢
    #subscribe(symbols='SZSE.000001', frequency='1s', count=1, unsubscribe_previous=False)
    #log(f'已订阅目标：{context.ids.keys()} 总数量：{len(context.ids)} 买入数量：{buy_num} 卖出数量：{len(context.ids) - buy_num}')
    #log(f'已订阅：{context.symbols} 数量：{len(context.symbols)}')

    # 查询所有A股代码，暂时用不到，记录在这里
    #id_list = get_instruments(exchanges='SZSE,SHSE', sec_types=1, fields='symbol',df=1)['symbol'].tolist()
    #print(f"A股总数量：{len(id_list)}")

    print(context.now)
    #history_data = history(symbol='SHSE.600021', frequency='1d', start_time='2023-05-16',  end_time=datetime.datetime.now().strftime('%Y-%m-%d'), fields='symbol, open, close, low, high, amount', adjust=ADJUST_PREV, df= True)
    #print(history_data)
    #print(history_data.symbol[0])
    #print(history_data.amount)
    
    leftCash = context.account().cash['available'] # 余额
    leftCash = float('%.2f' % leftCash)
    totalCash = context.account().cash['nav'] # 总资金
    totalCash = float('%.2f' % totalCash)
    print(f'当前总市值：{totalCash} 资金余额：{leftCash}')
    
    totalBuyNum = len(context.ids_buy)
    curHoldTypeNum = len(context.account().positions(symbol='', side=None))
    print(f'策略设置买入品种数量：{totalBuyNum} 当前品种数量：{curHoldTypeNum}')
    
    buy_in_down_rate = context.Buy_In_Fall_Rate
    buy_in_up_rate = context.Buy_In_Up_Rate
    useClose = (context.Use_Close == 1)
    print(f'设置买入时（单只）下跌比例：{buy_in_down_rate}，买入时（单只）上涨比例：{buy_in_up_rate}， 是否使用昨收:{useClose}')
    
    avgBuyAmount = (totalCash / totalBuyNum) if (totalBuyNum > 0) else 0
    
    avgBuyAmount = ("%.2f" % avgBuyAmount)
    msg = f"设置的买入下跌比例为:{buy_in_down_rate} 买入总量:{totalBuyNum} 是否使用昨收:{useClose}"
    msg += f"\n资产总值:{totalCash} 目前已持仓种类数量:{curHoldTypeNum} 剩余现金:{leftCash}元 每股均分金额:{avgBuyAmount}元"
    log(msg)    

    # --------init中的测试函数，如果是循环执行的，应该加入到tick或者bar中
    
    '''
    pos = context.account().position(symbol = 'SHSE.605003', side = OrderSide_Buy)
    if not pos:
        curHolding = 0
        print(f'123 cur holding: 0')
    else:
        curHolding = pos.available_now
        #print(f'{tick.symbol} cur holding: {curHolding}')
        print(f"今持：{curHolding} 总持：{pos.volume} 可用：{pos.available_now}")
    '''


def reach_time(context, target_time):
    now = datetime.datetime.strptime(str(context.now.date()) + str(context.now.hour) + ":" + str(context.now.minute), '%Y-%m-%d%H:%M')
    target_time = datetime.datetime.strptime(str(context.now.date()) + target_time, '%Y-%m-%d%H:%M')

    return (now >= target_time)


def check_multi_up_flag(context, tick, rate, buy_in_up_rate):
    # 检测多次上涨后买入相关逻辑
    # 逻辑略微有点复杂，我们的多次上涨检测，需要检测是否超过目标值，超过的话，则计数count+=1
    # 且反转检测标记，开始检测是否低于目标值，低于以后，再次反转，准备检测下一次超过目标值，然后计数继续加1
    multi_up_buy_complete = True # 默认为已完成，在下列流程中修改（流程不开启的话，也是默认完成）
    
    if context.ids[tick.symbol].enable_multi_up_buy_flag:
        # 次数不等，就还需要进一步检测
        # 暂时用不到总次数了，注释记录一下，不过后面可能会用
        #if context.ids[tick.symbol].multi_up_cur_count != context.ids[tick.symbol].multi_up_total_count:
        reach_0945 = reach_time(context, context.ids[tick.symbol].multi_up_time_line)

        # 初始化（需要一个初始化检测）以及check标记为真的检查
        if context.ids[tick.symbol].multi_up_buy_need_check:
            if (rate > buy_in_up_rate) and (not reach_0945):
                # check标记为真的时候，rate高于目标后，计数加1，且转换check标记
                context.ids[tick.symbol].multi_up_buy_need_check = False
                context.ids[tick.symbol].multi_up_cur_count += 1
                log(f"[multi_up] tick.symbol reach {round(rate * 100, 3)}% with count{context.ids[tick.symbol].multi_up_cur_count}")
            else:
                # 需要check时，如果rate还低于目标，则什么都不做
                pass
        # 低于X%后的检测逻辑
        else:
            if (rate > buy_in_up_rate):
                # check标记反转后，表示已经高于目标值，这时如果继续高于，则说明都不做
                pass
            else:
                # check标记反转后，表示已经高于目标值，这时如果低于了，则应该把check标记为真，准备检测是否可以再次超过目标
                context.ids[tick.symbol].multi_up_buy_need_check = True

        # 在目标时间（比如09:45）之前，需要统计更新最高值
        if not reach_0945:
            open_fpr = (tick.price - tick.open) / tick.open
            if open_fpr > context.ids[tick.symbol].highest_open_fpr:
                context.ids[tick.symbol].highest_open_fpr = open_fpr
            # 时间线之前不进行购买，直接返回
            return False
        else:
            # 到达时间线后，目前的策略是，之前没有到过目标值的（count为0），我们才可以买入
            if context.ids[tick.symbol].multi_up_cur_count == 0:
                return True
            else:
                return False

    return multi_up_buy_complete


def check_buy_all_force_flag(context):

    unfixed_arr = {}
    buy_all_with_100 = 0
    for k,v in context.ids_buy_target_info_dict.items():
        if k not in context.ids_buy:
            continue
        # 只要还有无效数据，就不能开始计算分配，返回False
        if not context.ids_buy_target_info_dict[k].first_record_flag:
            if context.tick_count_for_buy_ok:
                print(f"未取得全部有效price，目前[{k}]还未进行过价格记录，返回False")
            return False
        # 已经分配好的情况（有任意一只分配好，即视为都分配好了，因为首先要通过每只都能买一手的验证）
        elif context.ids_buy_target_info_dict[k].fixed_buy_in_base_num > 0:
            return True
        
        # 因为存在停牌的特殊情况（涨停和跌停price好像不是0，是买卖5价格为0），我们需要自己跳过价格为0的标的，不处理它们
        if v.price == 0:
            continue
        
        unfixed_arr[k] = v.price
        buy_base_num = 1
        # 688开头的至少要买2手，需要特殊处理
        if ((".688" in k) or (".689" in k)):
            buy_base_num += 1

        buy_all_with_100 += (v.price * buy_base_num * 100.0)

    if len(unfixed_arr) == 0:
        return

    total_cash = context.account().cash['nav'] # 总资金
    total_cash = float('%.2f' % total_cash)
    left_cash = total_cash

    if (buy_all_with_100 > total_cash):
        print(f"[{context.now}]每只股买入1手的情况下，[{buy_all_with_100}]已经超过了总资金[{total_cash}]，策略无法实施！！")
        print(f"已经取消所有订阅，调整ID列表后，重新刷新")
        unsubscribe(symbols='*', frequency='tick')
        return False
    elif (buy_all_with_100 / total_cash) > 0.9:
        if context.tick_count_for_buy_ok:
            print(f"[警告]尝试买入所有目标的情况下，每个目标购买一手的情况下，占比超过总资金的90%！！很可能无法买入全部！！")

    avg_for_one = total_cash / len(context.ids_buy_target_info_dict) / 100.0

    fixed_arr = {}
    total_fixed_cash = 0

    need_handle_flag = True
    # 循环检测高于均值的对象，并剔除，同时记录剩余对象
    while need_handle_flag:
        left_arr = {}

        for k,v in unfixed_arr.items():
            if v > avg_for_one:

                buy_base_num = 1
                # 检测688的特殊情况
                if ((".688" in k) or (".689" in k)):
                    buy_base_num += 1

                fixed_arr[k] = v * buy_base_num
                total_fixed_cash += (v * buy_base_num * 100.0)
                left_cash -= (v * buy_base_num * 100.0)
                context.ids_buy_target_info_dict[k].fixed_buy_in_base_num = buy_base_num
            else:
                # 单价小于平均值的情况，也不能说明就直接归类到剩余了，688的x2后，其实也算是超过了
                if ((".688" in k) or (".689" in k)) and (v * 2.0 > avg_for_one):
                    buy_base_num = 2
                    fixed_arr[k] = v * buy_base_num
                    total_fixed_cash += (v * buy_base_num * 100.0)
                    left_cash -= (v * buy_base_num * 100.0)
                    context.ids_buy_target_info_dict[k].fixed_buy_in_base_num = buy_base_num
                else:
                    left_arr[k] = v

        # 先判断是否退出，当left_arr和unfixed_arr长度一样时，说明没有找到高于平均值的目标
        if len(left_arr) == len(unfixed_arr):
            print(f"已找到所有高于平均值的目标，进行后续分配计算")
            break

        # 没有退出while的话，说明需要计算下一轮，更新均值（根据剩余资金和剩余目标）
        avg_for_one = left_cash / len(left_arr) / 100.0
        # 更新剩余数组
        unfixed_arr = left_arr.copy()

    # 计算剩余数组中的对象，应该买入的基础数量
    avg_amount = avg_for_one * 100.0
    test_remainder = 10 # 循环测试余数，每次加10，找到一个临界值，各个不会超过剩余资金
    need_test_flag = True # 从10开始测试，一般都会超过剩余资金，直到找到合适的余数

    unfixed_total_use_cash = 0
    while need_test_flag:
        test_total_use_cash = 0

        for k,v in unfixed_arr.items():
            buy_in_num = math.floor(avg_amount / v)
            base_num = math.floor(buy_in_num / 100)
            remainder = buy_in_num % 100

            # 这个地方的处理还有待商榷，虽然之前测试情况可以买完，但是不一定适用所有情况，还需要思考
            if (remainder > test_remainder):
                base_num += 1
            
            context.ids_buy_target_info_dict[k].fixed_buy_in_base_num = base_num
            test_total_use_cash += (base_num * 100.0 * v)

        # 检查是否通过测试，没有超过总剩余资金的话，就是通过了
        if test_total_use_cash < left_cash:
            log(f"[statictics]余数检测成功，将使用余数[{test_remainder}]计算base_num，left_case:[{left_cash}] will_use[{test_total_use_cash}]")
            unfixed_total_use_cash = test_total_use_cash
            break
        
        # 没有通过测试的话，余数加10，余数越大，用到的剩余资金就会越少
        test_remainder += 10

    # 调试输出信息，不需要时可以关闭（不过这个只会输出一次，应该也没什么）
    fixed_all_equal_1 = True
    unfixed_all_greater_than_1 = True
    for k,v in fixed_arr.items():
        if context.ids_buy_target_info_dict[k].fixed_buy_in_base_num != 1:
            fixed_all_equal_1 = False
            break
    
    for k,v in unfixed_arr.items():
        if context.ids_buy_target_info_dict[k].fixed_buy_in_base_num < 1:
            unfixed_all_greater_than_1 = False
            break

    msg = f"[statistics]fixed_arr总共会使用cash为：[{total_fixed_cash}]， 总计使用cash:[{total_fixed_cash + unfixed_total_use_cash}]"
    msg += f"\nfixed_num[{len(fixed_arr)}], unfixed_num[{len(unfixed_arr)}], total_num[{len(unfixed_arr) + len(fixed_arr)}]"
    msg += f"\nfixed_arr all equal 1:[{fixed_all_equal_1}], unfixed_arr all greater than 1:[{unfixed_all_greater_than_1}]"
    log(msg)

    return True


def try_buy_strategyA(context, tick):

    # 如果client order还没有处理完，也返回
    if tick.symbol in context.client_order.keys():
        #print(f'{tick.symbol}订单没有处理完毕，直接返回')
        return

    # 获取当前持仓
    curHolding = 0
    # 这里的Side一定要标注正确，比如我是买入的脚本，里面有个都是使用的Buy类型
    pos = context.account().position(symbol = tick.symbol, side = side_type)
    if not pos:
        curHolding = 0
        #print(f'{tick.symbol} cur holding: 0')
    else:
        curHolding = pos.volume_today if (side_type == OrderSide_Buy) else pos.available_now
        #print(f"{tick.symbol} 今持：{curHolding} 总持：{pos.volume} 可用：{pos.available_now}")

    if tick.symbol not in context.ids_buy_target_info_dict.keys():
        return

    # 检测持仓取值是否出现问题（有小概率出现，部成的值已经记录，且大于这里取出的持仓），还是需要处理
    if curHolding < context.ids_buy_target_info_dict[tick.symbol].total_holding:
        #log(f"[Warning][{tick.symbol}]出现了仓位{curHolding}刷新不及时问题，已通过记录数据更新到{context.ids_buy_target_info_dict[tick.symbol].total_holding}")
        curHolding = context.ids_buy_target_info_dict[tick.symbol].total_holding
        #log(f"[Warning][{tick.symbol}]出现了仓位{curHolding}刷新不及时问题，已通过记录数据更新到{context.ids_buy_target_info_dict[tick.symbol].total_holding}")
        curHolding = context.ids_buy_target_info_dict[tick.symbol].total_holding

    # 股票提供买卖5档数据, list[0]~list[4]分别对应买卖一档到五档
    #print(f"买卖信息：{tick.quotes[0]['bid_p']} {tick.quotes[1]['bid_p']} {tick.quotes[2]['bid_p']} {tick.quotes[3]['bid_p']} {tick.quotes[4]['bid_p']}---- cur val{tick.price}")
    buy_in_down_rate = context.Buy_In_Fall_Rate
    buy_in_up_rate = context.Buy_In_Up_Rate
    useClose = (context.Use_Close == 1)
    # 这里和策略A不一样，数量是动态的
    totalBuyNum = context.buy_num
    # 获取所有持仓信息时，side可以使用None，但是如果你只想获取买入的所有持仓，那也需要调整
    curHoldTypeNum = len(context.account().positions(symbol='', side=None))
    # 品种数量达标后，还不能返回，因为有些票可能是部成，然后我又撤销了，这样会导致资金用不完
    # if (curHoldTypeNum >= totalBuyNum):
    #     return

    if len(context.already_buy_in_keys) >= context.Buy_In_Limit_Num:
        return;

    # 跳过集合竞价的不正常价格区间
    if (tick.price == 0):
        return
    
    # 检测设定买入股数的情况下，是否已经处理完毕需要返回（一般这种情况都是小股数，但是可能存在被撤单失败的情况，如果出现，则需要去check_unfinished_order函数调整条件）
    if (context.ids[tick.symbol].buy_with_num_need_handle) and (context.ids[tick.symbol].buy_with_num_handled_flag):
        return
    
    leftCash = context.account().cash['available'] # 余额
    leftCash = float('%.2f' % leftCash)
    totalCash = context.account().cash['nav'] # 总资金
    totalCash = float('%.2f' % totalCash)
    
    avgBuyAmount = 0
    limitBuyAmountFlag = False # 某些情况需要限制买入数量，比如设定了买入量的话，我们在下面就不要去加1的BaseNum了，不然会多用钱
    if context.strategy_info.buy_mode.buy_all == 1:
        avgBuyAmount = totalCash / totalBuyNum
    elif context.strategy_info.buy_mode.buy_one == 1:
        avgBuyAmount = context.ids[tick.symbol].buy_amount
        limitBuyAmountFlag = True
    elif context.strategy_info.buy_mode.buy_all_force == 1:
        if not check_buy_all_force_flag(context):
            #print(f"还未拿到强制买入所有标的的有效标识，先返回")
            return
        avgBuyAmount = context.ids_buy_target_info_dict[tick.symbol].fixed_buy_in_base_num * 100.0 * tick.price


    # 持仓大于0，就不买入了，我们用的是今日买入量volume_today，不会出现判断问题，今天买过就不买了
    # 【MAYBE TODO】这里可能有待改进？？？因为会不会出现部成的情况，剩下的委托被我撤销？？需要观察
    # 如果要改进，那就需要判断当前持仓是否达到了均分的额度，没有的话，就还可以买入剩余额度，但是这样就会比较复杂，先观察吧    
    # 已出现上面提到的TODO情况，就是部成以后，撤销订单，就只买了一部分，这样钱会用不完，还需要判断该股买入数量是否达标
    buy_enough_flag = False
    vwap = 0.0 if (not pos) else pos.vwap
    left_space = avgBuyAmount - (vwap * curHolding)
    if ((left_space >= 0) and (left_space / (tick.price * 100.0) < 0.1)) or (left_space < 0):
        buy_enough_flag = True
    if (curHolding > 0) and (buy_enough_flag) and (context.ids[tick.symbol].buy_with_num == 0):
        return
    # 强制买入所有，持仓达标情况下，不进行任何补买动作
    elif (context.strategy_info.buy_mode.buy_all_force == 1) and ((curHolding / 100) == context.ids_buy_target_info_dict[tick.symbol].fixed_buy_in_base_num):
        return
    
    # 基础条件：
    # 和策略A不一样，B的话，直接买入，持仓>0前面判断过了，order在处理中也判断过了，使用下面的买入不需要任何条件了，直接买就ok
    buyCondition = True

    # 实盘附加条件：除了满足测试条件外，还需要满足下降百分比条件
    # dynainfo3：昨收，dynainfo4：今开，dynainfo7：最新
    if context.ids_buy_target_info_dict[tick.symbol].pre_close == 0:
        info = get_instruments(symbols = tick.symbol, df = True)
        # empty情况一般就是ST的股票，直接先跳过不处理
        if info.empty:
            print(f"get info null, this should not happen......")
            return
            
        # 最好不要直接使用df的值，很多奇怪的现象，比如下面的float相除，如果插入了df数据，结果是对的，但是小数点只有2位。。。。
        # 一定要先从数组里拿出来
        context.ids_buy_target_info_dict[tick.symbol].pre_close = info.pre_close[0]
        context.ids_buy_target_info_dict[tick.symbol].name = info.sec_name[0]
        context.ids_buy_target_info_dict[tick.symbol].upper_limit = info.upper_limit[0]
        
    pre_close = context.ids_buy_target_info_dict[tick.symbol].pre_close
    name = context.ids_buy_target_info_dict[tick.symbol].name

    # print(f"pre close {info.pre_close}")
    # print(f"test--------------[{tick.symbol} {info.empty}")
    # 下面的basePrice暂时不需要计算，是策略A根据跌幅买入的条件，先屏蔽
    #basePrice = info.pre_close if not info.empty else tick.open
    # if useClose:
    #     basePrice = info.pre_close if not info.empty else tick.open
    #     basePrice = float(basePrice[0]) if not info.empty else tick.open# 转换dataframe，df出来的数据都是数组!!!
    # else:
    #     basePrice = tick.open
    
    # 最新价格，目前使用的最新价格，我们直接用买（卖）5的价格
    # 也就是我们目前使用滑点5的设置
    # 股票提供买卖5档数据, list[0]~list[4]分别对应买卖一档到五档
    curVal = tick.price
    curVal1_5 = [tick.quotes[0]['ask_p'], tick.quotes[1]['ask_p'], tick.quotes[2]['ask_p'], tick.quotes[3]['ask_p'], tick.quotes[4]['ask_p']] #卖1-5价格
    # 这里需要对值进行检测，有时候买卖5是空的，需要选择一个有效值
    curVal5 = 0
    for idx in range(0, context.strategy_info.slip_step):
        if (curVal1_5[context.strategy_info.slip_step - 1 - idx] != 0):
            curVal5 = curVal1_5[context.strategy_info.slip_step - 1 - idx]
            break

    if (curVal5 == 0):
        print(f"[{tick.symbol}][try buy]--this should not happen, all values are 0, return for tmp")
        return

    # 使用市价的话，不再使用滑点价格，而是使用涨停价格（跟卷商人员确认过）
    if context.strategy_info.order_type_buy.Market == 1:
        curVal5 = context.ids_buy_target_info_dict[tick.symbol].upper_limit

    # 掘金里的涨跌幅是需要自己手动计算的
    rate = (curVal - pre_close) / pre_close

    # 检测多次上涨后买入相关逻辑
    multi_up_buy_complete = check_multi_up_flag(context, tick, rate, buy_in_up_rate)

    now = datetime.datetime.strptime(str(context.now.date()) + str(context.now.hour) + ":" + str(context.now.minute), '%Y-%m-%d%H:%M')
    target_time_for_solo = datetime.datetime.strptime(str(context.now.date()) + context.ids[tick.symbol].buy_with_time, '%Y-%m-%d%H:%M')
    
    # 具体买入条件：
    # 0.先决条件，买的起一手（科技股需要200，会在下面的流程判断）
    # 1.上涨超过设定值（需要检查是否配合多次上涨）
    # 2.脚本配置强制买，无视其他条件
    # 3.配置文件，单个标的涨幅
    # 4.配置文件，达到时间买入
    # 5.配置文件，单个标的股数（BN100BN，不需要b标识）

    enoughMoney1Hand = leftCash > (curVal5 * 100)
    # 很奇怪，金字塔的python可以用and，但是在掘金准备就必须用&替换and，否则会报错
    # 其实不用把and换成&，主要是因为df的数据是一个数组，所以没法直接比较
    buyCondition1 = (rate > buy_in_up_rate) and (multi_up_buy_complete)
    buyCondition2 = True if context.ids[tick.symbol].force_buy_flag else False
    buyCondition3 = (rate > context.ids[tick.symbol].buy_with_rate) if (context.ids[tick.symbol].buy_with_rate > 0) else (rate < context.ids[tick.symbol].buy_with_rate)
    buyCondition4 = (now >= target_time_for_solo)
    buyCondition5 = (context.ids[tick.symbol].buy_with_num > 0)

    # 在合适的情况下输出剩余空间信息
    # if (leftCash > left_space) and (enoughMoney1Hand) and (tick.symbol == 'SZSE.300522'):
    #     print(f'{tick.symbol} 涨跌幅：{round(rate * 100.0, 3)}% 最新价格：{tick.price} 剩余空间：{left_space} leftcash：{leftCash}')  
    
    if enoughMoney1Hand and (buyCondition1 or buyCondition2 or buyCondition3 or buyCondition4 or buyCondition5):
        market_value = 0 if (not pos) else pos.amount
        print(f"---------->>>test{tick.symbol}")
        msg = f"\n-------->>开始尝试买入[{tick.symbol}:{name}]，当前持仓量:{curHolding} 市值:{round(market_value, 2)} 现金余额:{round(leftCash, 3)} 当前持仓品种数量:{curHoldTypeNum}"
        msg += f"\n总资金：{totalCash} 均分值：{round(avgBuyAmount, 2)} 买入股票总数：{context.buy_num} 前两者乘值：{round(avgBuyAmount * context.buy_num, 2)}"
        msg += f"\n昨收价格:{round(pre_close, 2)} 今开价格:{round(tick.open, 2)} 瞬间价格:{round(tick.price, 2)}"
        msg += f"\n买入时涨幅百分比:{round(rate * 100.0, 3)}% 是否为高预期{context.ids[tick.symbol].high_expected_flag}"
        msg += f"\n是否使用市价成交：{context.strategy_info.order_type_buy.Market}"

        if buyCondition1:
            msg += f"\n涨幅达标，进行买入"
        elif buyCondition2:
            msg += f"\n配置文件设置强制买入"
        elif buyCondition3:
            msg += f"\n配置文件，单只涨幅达标买入"
        elif buyCondition4:
            msg += f"\n配置文件，到指定时间买入"
        elif buyCondition5:
            msg += f"\n配置文件，买入指定的股数"

        log(msg)
        
        shouldBuyAmout = 0
        if (leftCash > left_space):
            # 目前仅剩一只票可以买的话，就直接把剩下的钱都买了？？
            # 这里出过bug，就是本来全仓都在一只票上，结果卖出的时候，买入脚本判断资金够了
            # 但是判断只剩一个仓位（也就是位置刷新不及时.....）
            # 这里应该再和资产总值对比一下，如果剩余资金基本等于资产总值，就说明出现这个问题了，这个时候就不应该全买
            #if ((totalBuyNum - curHoldTypeNum) == 1): # 错误版本，这种版本有碎股的话，就会有问题

            # 关闭最后一只全买的条件，bug很多，不好监测，因为品种够的时候很多都没有买够，不如直接使用剩余空间进行补齐就好
            if len(context.ids_buy) == 1 and False:
                msg = "只剩最后一个仓位，尝试买入所有余额------"
                print(msg)
                log(msg)
                # 这里的超标计算为：均分以后+均分部分的0.3，动态调整（总体说，就是可以超过自己份额的1/3，不能太多）
                # 对于2来说，就是0.5 + 0.5 * 0.3 = 0.65，应该算是比较合适的值了
                # 对于3来说，就是0.333 + 0.333 * 0.3 = 0.4329，也还算合适，应该是可以的
                allowRange = (1.0 / totalBuyNum) + (1.0 / totalBuyNum) * 0.5
                if ((leftCash / totalCash) < allowRange):
                    msg = f"剩余资金在正常范围:{round(leftCash / totalCash * 100, 2)}% 许可范围:{round(allowRange * 100, 2)}%，可以使用所有余额"
                    log(msg)
                    shouldBuyAmout = leftCash
                else:
                    msg = f"剩余资金超标:{round(leftCash / totalCash * 100, 2)}%  许可范围:{round(allowRange * 100, 2)}%，使用标准均分值 {avgBuyAmount} 购买"
                    log(msg)
                    shouldBuyAmout = left_space
            else:
                msg = f"使用剩余空间{round(left_space, 2)}购买，正常情况"
                log(msg)
                shouldBuyAmout = left_space
        else:
            msg = f"使用所有余额{leftCash}进行购买，剩余资金小于购买量的情况（需要注意）"
            log(msg)
            shouldBuyAmout = leftCash
        
        # 计算应该买入的数量：需要结合总股以及现金余额数进行处理（总股数需要手动设置正确）
        #print(f"tmp test...amount{shouldBuyAmout} val5{curVal5}")
        buyNum = shouldBuyAmout / curVal5
        buyNum = math.floor(buyNum)
        msg = f"原始买入预估数量：{buyNum}"
        log(msg)
        
        # 考虑特殊情况，买不起1手的话（均分价格下），需要具体分析情况
        # 目前使用的策略是，只要资金足够买一手，那么就买，不考虑占总资金的百分比
        if (buyNum < 100) and (enoughMoney1Hand):
            msg = "均价不够买一手，但是剩余资金足够"
            log(msg)
            buyNum = 100
            
        # 把买入数量化整，整除为基数，余数大于70且资金充足的情况下，基数可以尝试加1
        buyNumLessOneHand = 10
        buyBaseNum = math.floor(buyNum / 100)
        remainder = buyNum % 100
        if (not limitBuyAmountFlag) and (remainder >= buyNumLessOneHand) and (leftCash > curVal5 * (buyBaseNum + 1) * 100):
            buyBaseNum += 1

        if (context.strategy_info.buy_mode.buy_all_force == 1):
            buyBaseNum = context.ids_buy_target_info_dict[tick.symbol].fixed_buy_in_base_num

        # 科创股至少买200，检查如果是100的话，能买的起200就买
        tech_flag = ((tick.symbol.find('.688') != -1) or (tick.symbol.find('.689') != -1))
        if (buyBaseNum == 1) and tech_flag:
            if (leftCash > curVal5 * 200):
                buyBaseNum += 1
            else:
                # 买不起就直接返回
                log(f'科创股至少需要买入200股，目前剩余资金不足：{leftCash} 需要：{curVal5 * 200}')
                return
        
        msg = f"开始尝试买入数量:{buyBaseNum * 100} 预计花费:{round(buyBaseNum * 100 * curVal5, 3)}元 目前余额:{round(leftCash, 3)}元"
        msg += f"\n买入使用卖5价格：{curVal5}"
        log(msg)

        # 买入！！！！！！！！
        # 脚本设定了指定价格的话，则使用脚本的设定价格
        if context.ids[tick.symbol].buy_with_price != 0:
            curVal5 = context.ids[tick.symbol].buy_with_price
        # 指定买入量的话，则只买入设置的量
        if context.ids[tick.symbol].buy_with_num != 0:
            buyBaseNum = (int)(context.ids[tick.symbol].buy_with_num / 100)
        list_order = order_volume(symbol=tick.symbol, volume=buyBaseNum * 100, side=OrderSide_Buy, order_type=context.order_type_buy, position_effect=PositionEffect_Open, price=curVal5)
        #print(f"list order:{list_order}")
        
        # 记录order的client id，避免出现之前的重复购买
        # 只有当id在order status的回掉中，出现已成（不是部成）或者被拒绝的时候，才开放再次购买
        # 需要一定的数据格式，记录在context全局变量中，这样不会被擦除
        # 数据信息：{symbol:[list_order]}，直接把list_order一下装进去吧，也不用费事单独拆一些数据了
        context.client_order[tick.symbol] = list_order
        
        # 从ids_buy中消除已经购买过的记录（用于判断还有最后一只没买，防止碎股情况）
        # if tick.symbol in context.ids_buy:
        #     context.ids_buy.remove(tick.symbol)

def try_sell_strategyA(context, tick):
    # 获取当前持仓
    curHolding = 0
    # 这里的Side一定要标注正确，比如我是买入的脚本，里面有个都是使用的Buy类型
    # 验证了下，获取买入后的持仓都是Buy类型，不是我想象的sell就要获取sell类型，我估计期货才用这个
    pos = context.account().position(symbol = tick.symbol, side = OrderSide_Buy)
    if not pos:
        curHolding = 0
        return
        #print(f'{tick.symbol} cur holding: 0')
    else:
        curHolding = pos.available_now
        # print(f"{tick.symbol} 今持：{curHolding} 总持：{pos.volume} 可用：{pos.available_now}")

    # 更新vwap或者记录的买入价格到缓存，便于统计数据
    buy_price = pos.vwap
    # 下面的代码段有非常大的bug，本来是为了解决连续买入卖出时的成本不一致问题
    # 但是有个问题，就是这个更新的vwap，在我们卖出后，今天可能再次买入，买入的价格就更新了。。。。，但是实际我们统计的时候应该用上次记录的，这里完全就冲突了
    # 最后还会导致今日的统计值不正常，想清楚之前先不要使用这个了
    # if (tick.symbol in context.buy_pos_dict.keys()):
    #     buy_price = context.buy_pos_dict[tick.symbol] if context.buy_pos_dict[tick.symbol] > 0 else pos.vwap
    if (context.ids_virtual_sell_target_info_dict[tick.symbol].vwap == 0) and (buy_price > 0):
        context.ids_virtual_sell_target_info_dict[tick.symbol].vwap = buy_price
    context.ids_virtual_sell_target_info_dict[tick.symbol].hold = curHolding

    # 持仓浮动盈亏比例：amount持仓总额，fpnl浮动盈利值，vwap持仓均价
    #float_profit_rate = pos.fpnl / pos.amount # 这个应该是错误的，盈利是基于买入的成本价，而不是整体持仓市值（这个是对的，但是好像不太及时，算出来的涨跌幅，总是比最新价要少一点点）
    if (tick.price == 0):
        return

    # 这个在集合竞价的阶段最新价都是0，都是亏损100%。。。。，需要处理这个细节，技术支持建议用这个
    float_profit_rate = (tick.price - buy_price) / buy_price 
    context.ids_virtual_sell_target_info_dict[tick.symbol].fpr = float_profit_rate;
    # 使用这种方法计算涨幅，就不会遇到集合竞价时tick.price=0的情况，但是两种算法有点差异，技术建议是用上面
    #float_profit_rate = pos.fpnl / pos.amount 
    # print(f"-------->>>>>>tset 浮动盈利：{round(float_profit_rate * 100, 3)}% test val：{round(pos.fpnl / pos.amount * 100, 3)}%")

    # 如果client order还没有处理完，也返回
    if tick.symbol in context.client_order.keys():
        #print(f'{tick.symbol}订单没有处理完毕，直接返回')
        return

    if curHolding == 0:
        return

    leftCash = context.account().cash['available'] # 余额
    leftCash = float('%.2f' % leftCash)
    curVal1_5 = [tick.quotes[0]['bid_p'], tick.quotes[1]['bid_p'], tick.quotes[2]['bid_p'], tick.quotes[3]['bid_p'], tick.quotes[4]['bid_p']]
    curVal5 = 0 #买5价格
    for idx in range(0, context.strategy_info.slip_step):
        if (curVal1_5[context.strategy_info.slip_step - 1 - idx] != 0):
            curVal5 = curVal1_5[context.strategy_info.slip_step - 1 - idx]
            break
        
    if (curVal5 == 0):
        print(f"[{tick.symbol}][try sell]--this should not happen, all values are 0, return for tmp")
        return

    # 获取所有持仓信息时，side可以使用None，但是如果你只想获取买入的所有持仓，那也需要调整
    curHoldTypeNum = len(context.account().positions(symbol='', side=None))
    if context.ids_virtual_sell_target_info_dict[tick.symbol].pre_close == 0:
        info = get_instruments(symbols = tick.symbol, df = True)
        # empty情况一般就是ST的股票，直接先跳过不处理
        if info.empty:
            return
            
        # 最好不要直接使用df的值，很多奇怪的现象，比如下面的float相除，如果插入了df数据，结果是对的，但是小数点只有2位。。。。
        # 一定要先从数组里拿出来
        context.ids_virtual_sell_target_info_dict[tick.symbol].pre_close = info.pre_close[0]
        context.ids_virtual_sell_target_info_dict[tick.symbol].name = info.sec_name[0]
        
    pre_close = context.ids_virtual_sell_target_info_dict[tick.symbol].pre_close
    name = context.ids_virtual_sell_target_info_dict[tick.symbol].name

    #print(f"总资金{context.account().cash['nav']} 总市值{context.account().cash['market_value']} 总浮动盈亏{context.account().cash['fpnl']}")
    # 错误统计：总市值会受到已经卖出的标的干扰，比如卖出时时7%，但是后来到-7%了，这样计算整体的即使收益就有问题，所以我们必须在卖出后，要把卖出的票记录到缓存和文件中
    # cur_market_value = context.account().cash['market_value'] # 当前总市值
    # cur_market_value = float('%.2f' % cur_market_value)

    # 正确统计：通过缓存（记录）值，加上剩余没有卖出的总和才能得到正确值！！！！
    # 为了减轻计算负担，这里要判断下是否满意进入整体盈利和限时情况，有任意一个进入后就不再更新这里的市值计算了
    valid_tfpr_flag = True
    # 下面条件取消了context.tick_count_for_sell_ok的频率控制，有可能导致计算负担的加大？下面的print加入了频率控制，观察下AA的情况，再看下一步调整
    if (not context.sell_with_total_float_profit_flag) and (not context.sell_with_time_limit_flag) and (not context.sell_with_total_float_loss_flag):
        cur_market_value = 0
        handle_count = 0 # 用来调试总盈利计算错误问题，看是否执行完毕所有的目标
        for k,v in context.sell_pos_dict.items():
            mv = 0
            if (not v[1]) and (k in context.ids_virtual_sell_target_info_dict.keys()):
                mv = context.ids_virtual_sell_target_info_dict[k].price * v[0] #change mark
            else:
                mv = (v[0] * v[2])
            if mv <= 0:
                if k in context.ids_virtual_sell_target_info_dict.keys():
                    log(f"[sell] fatal potential error, mv[{mv}] should not be 0, [{k}] price[{context.ids_virtual_sell_target_info_dict[k].price}] hold[{v[0]}] sold_price[{v[2]}]")
                valid_tfpr_flag = False
                break
            cur_market_value += mv
            handle_count += 1

        # 现在策略AB应该是可以共用一套了，因为不管是否存在买入和卖出的混合，我们有了当天的文件缓存后，都可以计算正确的整体盈利了
        # 之前的话，因为没有文件缓存，所以逻辑上有点混乱，现在是很清晰的
        total_float_profit_rate = (cur_market_value - context.total_market_value_for_all_sell) / context.total_market_value_for_all_sell if context.total_market_value_for_all_sell != 0 else 0
        if cur_market_value == 0:
            print(f"Fatal error!! cur mv == 0, sell_pos_dict len:[{len(context.sell_pos_dict)}]")
            return
        # print(f"cur_mv[{cur_market_value}] total_mv[{context.total_market_value_for_all_sell}]")
        if valid_tfpr_flag and context.tick_count_for_sell_ok:
            print(f"总盈亏：{round(total_float_profit_rate * 100, 3)}%")
            context.tfpr = total_float_profit_rate
            # 检测一下异常，目前出现的非常低的百分比不知道怎么回事，需要排查下
            if (context.tfpr <= -0.05) or (context.tfpr >= 0.1):
                log(f"[sell][Fatal-Error] 出现异常总盈亏数据{round(total_float_profit_rate * 100, 3)}%, total_mv[{context.total_market_value_for_all_sell}] cur_mv[{cur_market_value}] sell_pos_dict_len[{len(context.sell_pos_dict)}] handle_len[{handle_count}]")

        # 更新和检测整体的追高情况（特定情况应该放弃追高卖出）
        if context.sell_all_chase_raise_flag:
            # 更新最高值
            if total_float_profit_rate > context.sell_all_chase_highest_record:
                context.sell_all_chase_highest_record = total_float_profit_rate
            # 检测最高值是否已经超过我们设定的卖出底线
            if context.sell_all_chase_highest_record > context.sell_all_lower_limit:
                # 超过底线后，有两个情况要卖出
                # 1. 再次低于底线值得时候直接卖出（保底），首要条件
                # 2. 从一个较高的值，比如0.99%回撤到了0.84，回撤超过15%也卖出，说明冲力不行
                if (not context.sell_with_total_float_profit_flag) and (total_float_profit_rate < context.sell_all_lower_limit):
                    context.sell_with_total_float_profit_flag = True
                    log(f"-------->已激活整体盈利卖出条件(追高回落超过底线)，目前设定的整体盈利为：{context.Sell_All_Increase_Rate * 100}%，设置的底线为：{context.sell_all_lower_limit}，当前整体盈利为：{round(context.tfpr * 100, 3)}%")
                    context.record_sell_time = context.now
                    context.record_sell_tfpr = context.tfpr
                elif (not context.sell_with_total_float_profit_flag) and ((total_float_profit_rate - context.sell_all_chase_highest_record) / context.sell_all_chase_highest_record < -0.12):
                    context.sell_with_total_float_profit_flag = True
                    log(f"-------->已激活整体盈利卖出条件(追高回落超过12%)，目前设定的整体盈利为：{context.Sell_All_Increase_Rate * 100}%，记录的最高值为：{round(context.sell_all_chase_highest_record, 3)}，当前整体盈利为：{round(context.tfpr * 100, 3)}%")
                    context.record_sell_time = context.now
                    context.record_sell_tfpr = context.tfpr

        # 更新记录最大的总浮动盈亏（用于在13点35分，也就是设定的全部卖出时段进行log记录）
        # if valid_tfpr_flag and (total_float_profit_rate > context.highest_total_float_profit_info[0]):
        #     context.highest_total_float_profit_info[0] = total_float_profit_rate
        #     context.highest_total_float_profit_info[1] = context.now
        # if valid_tfpr_flag and (total_float_profit_rate < context.lowest_total_float_profit_info[0]):
        #     context.lowest_total_float_profit_info[0] = total_float_profit_rate
        #     context.lowest_total_float_profit_info[1] = context.now

    # 大于整体盈利卖出条件后，直接激活卖出条件（不再重置false）
    # false只在init时有一次，后续只要激活就全部卖出（只激活一次即可）
    # 只激活一次的策略，有可能带来了滑点严重的问题？？因为激活的瞬间，可能整体盈利还在抖动，所以导致一直有0.2%左右的差值？？所以需要改为反复激活，也就是激活后，也要保证后续的每只股卖出时都达到了整体收益？？（需要验证）
    if (not context.sell_with_total_float_profit_flag) and (valid_tfpr_flag) and (context.tfpr > context.Sell_All_Increase_Rate):
        context.sell_with_total_float_profit_flag = True
        log(f"-------->已激活整体盈利卖出条件，目前设定的整体盈利为：{context.Sell_All_Increase_Rate * 100}%，当前整体盈利为：{round(context.tfpr * 100, 3)}%")
        context.record_sell_time = context.now
        context.record_sell_tfpr = context.tfpr

    # 整体止损再满足条件后，激活一次即可
    if (not context.sell_with_total_float_loss_flag) and (valid_tfpr_flag) and (context.tfpr < context.Sell_All_Loss_Rate):
        context.sell_with_total_float_loss_flag = True
        log(f"-------->已激活整体止损卖出条件，目前设定的整体止损为：{context.Sell_All_Loss_Rate * 100}%，当前整体止损为：{round(context.tfpr * 100, 3)}%")
        context.record_sell_time = context.now
        context.record_sell_tfpr = context.tfpr


    # TODO:这里还可以稍微优化下，过时限卖出的flag可以改为全局的，不过这个也不会有什么影响
    now = datetime.datetime.strptime(str(context.now.date()) + str(context.now.hour) + ":" + str(context.now.minute), '%Y-%m-%d%H:%M')
    target_time = datetime.datetime.strptime(str(context.now.date()) + sell_all_time, '%Y-%m-%d%H:%M')
    target_time_for_solo = datetime.datetime.strptime(str(context.now.date()) + context.ids[tick.symbol].sell_with_time, '%Y-%m-%d%H:%M')
    #change mark2
    if (not context.sell_with_time_limit_flag) and (now >= target_time):
        context.sell_with_time_limit_flag = True
        context.record_sell_time = context.now
        context.record_sell_tfpr = context.tfpr

    # 开始判断卖出的条件，一共4个
    # 1.涨幅达标，可以卖出
    # 2.达到13点35分，无论情况，直接全部卖出（要准备换第二天的标的了）
    # 3.强制止损，必须卖出
    # 4.整体盈利到达目标，全部卖出
    # 5.配置直接卖出单个（避免手动平仓）--ID后面加字符s
    # 6.整体止损
    # 7.配置直接清仓所有--fsa标记修改，详见配置文件中的说明
    # 8.配置单个标的卖出的涨幅比例
    # 9.配置单个标的的卖出时间
    # 10.配置单个标的卖出股数（使用方式SN100SN，不需要加s标识）

    sell_condition1 = float_profit_rate > context.Sell_Increase_Rate
    sell_condition2 = context.sell_with_time_limit_flag and False
    sell_condition3 = float_profit_rate < context.Sell_Loss_Limit
    sell_condition4 = context.sell_with_total_float_profit_flag
    # 重置整体盈利卖出标识（必须每只股都重新计算，保证贴合卖出线）
    context.sell_with_total_float_profit_flag = False
    sell_condition5 = context.ids[tick.symbol].force_sell_flag
    sell_condition6 = context.sell_with_total_float_loss_flag
    sell_condition7 = context.force_sell_all_flag
    sell_condition8 = (float_profit_rate > context.ids[tick.symbol].sell_with_rate) if (context.ids[tick.symbol].sell_with_rate > 0) else (float_profit_rate < context.ids[tick.symbol].sell_with_rate)
    sell_condition9 = (now >= target_time_for_solo)
    sell_condition10 = (context.ids[tick.symbol].sell_with_num > 0)

    # 开始判断条件，并尝试卖出
    if sell_condition1 or sell_condition2 or sell_condition3 or sell_condition4 or sell_condition5 or sell_condition6 or sell_condition7 or sell_condition8  or sell_condition9 or sell_condition10:
        msg = f"\n-------->>开始尝试卖出[{tick.symbol}:{name}]，当前持仓量:{curHolding} 现金余额:{round(leftCash, 3)} 当前持仓品种数量:{curHoldTypeNum}"
        msg += f"\n昨收价格:{round(pre_close, 2)} 今开价格:{round(tick.open, 2)} 瞬间价格:{round(tick.price, 2)} 成本价:{pos.vwap}"
        msg += f"\n卖出时盈亏百分比:{round(float_profit_rate * 100.0, 3)}% 是否为高预期{context.ids[tick.symbol].high_expected_flag}"
        msg += f"\n瞬间整体盈利：{round(context.tfpr * 100, 3)}%, Valid：{valid_tfpr_flag}"
        msg += f"\n是否使用市价成交：{context.strategy_info.order_type_sell.Market}"

        msg += f"\n卖出原因："
        if sell_condition1:
            msg += "盈利达标后卖出"
        elif sell_condition2:
            msg += "时间满足标准后卖出"
        elif sell_condition3:
            msg += "止损后卖出"
        elif sell_condition4:
            msg += f"整体盈利达标后卖出"
        elif sell_condition6:
            msg += f"整体止损后卖出"
        elif sell_condition5:
            msg += "配置文件标记强制卖出单个"
        elif sell_condition7:
            msg += "配置文件标记强制清仓所有"
        elif sell_condition8:
            msg += "配置文件单个涨幅达标"
        elif sell_condition9:
            msg += "配置文件指定时间卖出"
        elif sell_condition10:
            msg += "配置文件指定股数卖出"

        msg += f"\n卖出使用买5价格：{curVal5}"
        log(msg)

        # 卖出！！！！！！！！
        # 如果设置了脚本的指定卖出价格，则以指定的价格为准
        list_order = []
        # 判断是否有指定卖出数量，且挂单后，重置数量到0，避免反复卖出指定数量
        if context.ids[tick.symbol].sell_with_num != 0:
            curHolding = int(context.ids[tick.symbol].sell_with_num)
            # 将读取的卖出数量重置到0，否则会连续卖出，这样的话，除非再次刷新（且配置仍然存在），才会继续卖出
            context.ids[tick.symbol].sell_with_num = 0
        if context.ids[tick.symbol].sell_with_price != 0:
            list_order = order_volume(symbol=tick.symbol, volume=curHolding, side=OrderSide_Sell, order_type=OrderType_Limit, position_effect=PositionEffect_Close, price=context.ids[tick.symbol].sell_with_price)
        else:
            list_order = order_volume(symbol=tick.symbol, volume=curHolding, side=OrderSide_Sell, order_type=context.order_type_sell, position_effect=PositionEffect_Close, price=curVal5)
        #print(f"list order:{list_order}")
        
        # 记录order的client id，避免出现之前的重复购买
        # 只有当id在order status的回掉中，出现已成（不是部成）或者被拒绝的时候，才开放再次购买
        # 需要一定的数据格式，记录在context全局变量中，这样不会被擦除
        # 数据信息：{symbol:[list_order]}，直接把list_order一下装进去吧，也不用费事单独拆一些数据了
        context.client_order[tick.symbol] = list_order


def try_buy_strategyB(context, tick):
    t = time.time()

    # 如果client order还没有处理完，也返回
    if tick.symbol in context.client_order.keys():
        #print(f'{tick.symbol}订单没有处理完毕，直接返回')
        return

    # 获取当前持仓
    curHolding = 0
    # 这里的Side一定要标注正确，比如我是买入的脚本，里面有个都是使用的Buy类型
    pos = context.account().position(symbol = tick.symbol, side = side_type)
    if not pos:
        curHolding = 0
        #print(f'{tick.symbol} cur holding: 0')
    else:
        curHolding = pos.volume_today if (side_type == OrderSide_Buy) else pos.available_now
        #print(f"{tick.symbol} 今持：{curHolding} 总持：{pos.volume} 可用：{pos.available_now}")

    if tick.symbol not in context.ids_buy_target_info_dict.keys():
        return

    # 检测持仓取值是否出现问题（有小概率出现，部成的值已经记录，且大于这里取出的持仓），还是需要处理
    if curHolding < context.ids_buy_target_info_dict[tick.symbol].total_holding:
        #log(f"[Warning][{tick.symbol}]出现了仓位{curHolding}刷新不及时问题，已通过记录数据更新到{context.ids_buy_target_info_dict[tick.symbol].total_holding}")
        curHolding = context.ids_buy_target_info_dict[tick.symbol].total_holding
        #log(f"[Warning][{tick.symbol}]出现了仓位{curHolding}刷新不及时问题，已通过记录数据更新到{context.ids_buy_target_info_dict[tick.symbol].total_holding}")
        curHolding = context.ids_buy_target_info_dict[tick.symbol].total_holding

    # 股票提供买卖5档数据, list[0]~list[4]分别对应买卖一档到五档
    #print(f"买卖信息：{tick.quotes[0]['bid_p']} {tick.quotes[1]['bid_p']} {tick.quotes[2]['bid_p']} {tick.quotes[3]['bid_p']} {tick.quotes[4]['bid_p']}---- cur val{tick.price}")
    buy_in_down_rate = context.Buy_In_Fall_Rate
    buy_in_up_rate = context.Buy_In_Up_Rate
    useClose = (context.Use_Close == 1)
    # 这里和策略A不一样，数量是动态的
    totalBuyNum = context.buy_num
    # 获取所有持仓信息时，side可以使用None，但是如果你只想获取买入的所有持仓，那也需要调整
    curHoldTypeNum = len(context.account().positions(symbol='', side=None))
    # 品种数量达标后，还不能返回，因为有些票可能是部成，然后我又撤销了，这样会导致资金用不完
    # if (curHoldTypeNum >= totalBuyNum):
    #     return

    # 跳过集合竞价的不正常价格区间
    if (tick.price == 0):
        return
    
    # 检测设定买入股数的情况下，是否已经处理完毕需要返回（一般这种情况都是小股数，但是可能存在被撤单失败的情况，如果出现，则需要去check_unfinished_order函数调整条件）
    if (context.ids[tick.symbol].buy_with_num_need_handle) and (context.ids[tick.symbol].buy_with_num_handled_flag):
        return
    
    leftCash = context.account().cash['available'] # 余额
    leftCash = float('%.2f' % leftCash)
    totalCash = context.account().cash['nav'] # 总资金
    totalCash = float('%.2f' % totalCash)
    
    avgBuyAmount = 0
    limitBuyAmountFlag = False # 某些情况需要限制买入数量，比如设定了买入量的话，我们在下面就不要去加1的BaseNum了，不然会多用钱
    if context.strategy_info.buy_mode.buy_all == 1:
        avgBuyAmount = totalCash / totalBuyNum
    elif context.strategy_info.buy_mode.buy_one == 1:
        avgBuyAmount = context.ids[tick.symbol].buy_amount
        limitBuyAmountFlag = True
    elif context.strategy_info.buy_mode.buy_all_force == 1:
        if not check_buy_all_force_flag(context):
            # #print(f"还未拿到强制买入所有标的的有效标识，先返回")
            return
        avgBuyAmount = context.ids_buy_target_info_dict[tick.symbol].fixed_buy_in_base_num * 100.0 * tick.price


    # 持仓大于0，就不买入了，我们用的是今日买入量volume_today，不会出现判断问题，今天买过就不买了
    # 【MAYBE TODO】这里可能有待改进？？？因为会不会出现部成的情况，剩下的委托被我撤销？？需要观察
    # 如果要改进，那就需要判断当前持仓是否达到了均分的额度，没有的话，就还可以买入剩余额度，但是这样就会比较复杂，先观察吧    
    # 已出现上面提到的TODO情况，就是部成以后，撤销订单，就只买了一部分，这样钱会用不完，还需要判断该股买入数量是否达标
    buy_enough_flag = False
    vwap = 0.0 if (not pos) else pos.vwap
    left_space = avgBuyAmount - (vwap * curHolding)
    if ((left_space >= 0) and (left_space / (tick.price * 100.0) < 0.1)) or (left_space < 0):
        buy_enough_flag = True
    if (curHolding > 0) and (buy_enough_flag) and (context.ids[tick.symbol].buy_with_num == 0):
        return
    # 强制买入所有，持仓达标情况下，不进行任何补买动作
    elif (context.strategy_info.buy_mode.buy_all_force == 1) and ((curHolding / 100) == context.ids_buy_target_info_dict[tick.symbol].fixed_buy_in_base_num):
        return
    
    # 基础条件：
    # 和策略A不一样，B的话，直接买入，持仓>0前面判断过了，order在处理中也判断过了，使用下面的买入不需要任何条件了，直接买就ok
    buyCondition = True

    # 实盘附加条件：除了满足测试条件外，还需要满足下降百分比条件
    # dynainfo3：昨收，dynainfo4：今开，dynainfo7：最新
    if context.ids_buy_target_info_dict[tick.symbol].pre_close == 0:
        info = get_instruments(symbols = tick.symbol, df = True)
        # empty情况一般就是ST的股票，直接先跳过不处理
        if info.empty:
            print(f"get info null, this should not happen......")
            return
            
        # 最好不要直接使用df的值，很多奇怪的现象，比如下面的float相除，如果插入了df数据，结果是对的，但是小数点只有2位。。。。
        # 一定要先从数组里拿出来
        context.ids_buy_target_info_dict[tick.symbol].pre_close = info.pre_close[0]
        context.ids_buy_target_info_dict[tick.symbol].name = info.sec_name[0]
        context.ids_buy_target_info_dict[tick.symbol].upper_limit = info.upper_limit[0]
        
    pre_close = context.ids_buy_target_info_dict[tick.symbol].pre_close
    name = context.ids_buy_target_info_dict[tick.symbol].name

    if context.test_info == 3:
        print(f"buy time cost, pt2: {time.time() - t:.4f} s")

    # print(f"pre close {info.pre_close}")
    # print(f"test--------------[{tick.symbol} {info.empty}")
    # 下面的basePrice暂时不需要计算，是策略A根据跌幅买入的条件，先屏蔽
    #basePrice = info.pre_close if not info.empty else tick.open
    # if useClose:
    #     basePrice = info.pre_close if not info.empty else tick.open
    #     basePrice = float(basePrice[0]) if not info.empty else tick.open# 转换dataframe，df出来的数据都是数组!!!
    # else:
    #     basePrice = tick.open
    
    # 最新价格，目前使用的最新价格，我们直接用买（卖）5的价格
    # 也就是我们目前使用滑点5的设置
    # 股票提供买卖5档数据, list[0]~list[4]分别对应买卖一档到五档
    curVal = tick.price
    curVal1_5 = [tick.quotes[0]['ask_p'], tick.quotes[1]['ask_p'], tick.quotes[2]['ask_p'], tick.quotes[3]['ask_p'], tick.quotes[4]['ask_p']] #卖1-5价格
    # 这里需要对值进行检测，有时候买卖5是空的，需要选择一个有效值
    curVal5 = 0
    for idx in range(0, context.strategy_info.slip_step):
        if (curVal1_5[context.strategy_info.slip_step - 1 - idx] != 0):
            curVal5 = curVal1_5[context.strategy_info.slip_step - 1 - idx]
            break

    if (curVal5 == 0):
        print(f"[{tick.symbol}][try buy]--this should not happen, all values are 0, return for tmp")
        return

    # 使用市价的话，不再使用滑点价格，而是使用涨停价格（跟卷商人员确认过）
    if context.strategy_info.order_type_buy.Market == 1:
        curVal5 = context.ids_buy_target_info_dict[tick.symbol].upper_limit

    # 掘金里的涨跌幅是需要自己手动计算的
    rate = (curVal - pre_close) / pre_close

    # 检测多次上涨后买入相关逻辑
    multi_up_buy_complete = check_multi_up_flag(context, tick, rate, buy_in_up_rate)

    now = datetime.datetime.strptime(str(context.now.date()) + str(context.now.hour) + ":" + str(context.now.minute), '%Y-%m-%d%H:%M')
    target_time_for_solo = datetime.datetime.strptime(str(context.now.date()) + context.ids[tick.symbol].buy_with_time, '%Y-%m-%d%H:%M')
    
    # 具体买入条件：
    # 0.先觉条件，买的起一手（科技股需要200，会在下面的流程判断）
    # 1.上涨超过0.8%（策略B1特有条件）
    # 2.脚本配置强制买，无视其他条件
    # 3.配置文件，单个标的涨幅
    # 4.配置文件，达到时间买入
    # 5.配置文件，单个标的股数（BN100BN，不需要b标识）

    enoughMoney1Hand = leftCash > (curVal5 * 100)
    # 很奇怪，金字塔的python可以用and，但是在掘金准备就必须用&替换and，否则会报错
    # 其实不用把and换成&，主要是因为df的数据是一个数组，所以没法直接比较
    buyCondition1 = True
    buyCondition2 = True if context.ids[tick.symbol].force_buy_flag else False
    buyCondition3 = (rate > context.ids[tick.symbol].buy_with_rate) if (context.ids[tick.symbol].buy_with_rate > 0) else (rate < context.ids[tick.symbol].buy_with_rate)
    buyCondition4 = (now >= target_time_for_solo)
    buyCondition5 = (context.ids[tick.symbol].buy_with_num > 0)

    # 在合适的情况下输出剩余空间信息
    if (leftCash > left_space) and (enoughMoney1Hand):
        print(f'{tick.symbol} 涨跌幅：{round(rate * 100.0, 3)}% 最新价格：{tick.price} 剩余空间：{left_space} leftcash：{leftCash}')  

    if context.test_info == 3:
        print(f"buy time cost, pt3: {time.time() - t:.4f} s")
    
    if enoughMoney1Hand and (buyCondition1 or buyCondition2 or buyCondition3 or buyCondition4 or buyCondition5):
        market_value = 0 if (not pos) else pos.amount
        print(f"---------->>>test{tick.symbol}")
        msg = f"\n-------->>开始尝试买入[{tick.symbol}:{name}]，当前持仓量:{curHolding} 市值:{round(market_value, 2)} 现金余额:{round(leftCash, 3)} 当前持仓品种数量:{curHoldTypeNum}"
        msg += f"\n总资金：{totalCash} 均分值：{round(avgBuyAmount, 2)} 买入股票总数：{context.buy_num} 前两者乘值：{round(avgBuyAmount * context.buy_num, 2)}"
        msg += f"\n昨收价格:{round(pre_close, 2)} 今开价格:{round(tick.open, 2)} 瞬间价格:{round(tick.price, 2)}"
        msg += f"\n买入时涨幅百分比：{round(rate * 100.0, 3)}% 是否为高预期{context.ids[tick.symbol].high_expected_flag}"
        msg += f"\n是否使用市价成交：{context.strategy_info.order_type_buy.Market}"

        if buyCondition1:
            msg += f"\n涨幅达标，进行买入"
        elif buyCondition2:
            msg += f"\n配置文件设置强制买入"
        elif buyCondition3:
            msg += f"\n配置文件，单只涨幅达标买入"
        elif buyCondition4:
            msg += f"\n配置文件，到指定时间买入"
        elif buyCondition5:
            msg += f"\n配置文件，买入指定的股数"

        log(msg)
        
        shouldBuyAmout = 0
        if (leftCash > left_space):
            # 目前仅剩一只票可以买的话，就直接把剩下的钱都买了？？
            # 这里出过bug，就是本来全仓都在一只票上，结果卖出的时候，买入脚本判断资金够了
            # 但是判断只剩一个仓位（也就是位置刷新不及时.....）
            # 这里应该再和资产总值对比一下，如果剩余资金基本等于资产总值，就说明出现这个问题了，这个时候就不应该全买
            #if ((totalBuyNum - curHoldTypeNum) == 1): # 错误版本，这种版本有碎股的话，就会有问题

            # 关闭最后一只全买的条件，bug很多，不好监测，因为品种够的时候很多都没有买够，不如直接使用剩余空间进行补齐就好
            if len(context.ids_buy) == 1 and False:
                msg = "只剩最后一个仓位，尝试买入所有余额------"
                print(msg)
                log(msg)
                # 这里的超标计算为：均分以后+均分部分的0.3，动态调整（总体说，就是可以超过自己份额的1/3，不能太多）
                # 对于2来说，就是0.5 + 0.5 * 0.3 = 0.65，应该算是比较合适的值了
                # 对于3来说，就是0.333 + 0.333 * 0.3 = 0.4329，也还算合适，应该是可以的
                allowRange = (1.0 / totalBuyNum) + (1.0 / totalBuyNum) * 0.5
                if ((leftCash / totalCash) < allowRange):
                    msg = f"剩余资金在正常范围:{round(leftCash / totalCash * 100, 2)}% 许可范围:{round(allowRange * 100, 2)}%，可以使用所有余额"
                    log(msg)
                    shouldBuyAmout = leftCash
                else:
                    msg = f"剩余资金超标:{round(leftCash / totalCash * 100, 2)}%  许可范围:{round(allowRange * 100, 2)}%，使用标准均分值 {avgBuyAmount} 购买"
                    log(msg)
                    shouldBuyAmout = left_space
            else:
                msg = f"使用剩余空间{round(left_space, 2)}购买，正常情况"
                log(msg)
                shouldBuyAmout = left_space
        else:
            msg = f"使用所有余额{leftCash}进行购买，剩余资金小于购买量的情况（需要注意）"
            log(msg)
            shouldBuyAmout = leftCash
        
        # 计算应该买入的数量：需要结合总股以及现金余额数进行处理（总股数需要手动设置正确）
        #print(f"tmp test...amount{shouldBuyAmout} val5{curVal5}")
        buyNum = shouldBuyAmout / curVal5
        buyNum = math.floor(buyNum)
        msg = f"原始买入预估数量：{buyNum}"
        log(msg)
        
        # 考虑特殊情况，买不起1手的话（均分价格下），需要具体分析情况
        # 目前使用的策略是，只要资金足够买一手，那么就买，不考虑占总资金的百分比
        if (buyNum < 100) and (enoughMoney1Hand):
            msg = "均价不够买一手，但是剩余资金足够"
            log(msg)
            buyNum = 100
            
        # 把买入数量化整，整除为基数，余数大于70且资金充足的情况下，基数可以尝试加1
        buyNumLessOneHand = 10
        buyBaseNum = math.floor(buyNum / 100)
        remainder = buyNum % 100
        if (not limitBuyAmountFlag) and (remainder >= buyNumLessOneHand) and (leftCash > curVal5 * (buyBaseNum + 1) * 100):
            buyBaseNum += 1

        if (context.strategy_info.buy_mode.buy_all_force == 1):
            buyBaseNum = context.ids_buy_target_info_dict[tick.symbol].fixed_buy_in_base_num

        # 科创股至少买200，检查如果是100的话，能买的起200就买
        tech_flag = ((tick.symbol.find('.688') != -1) or (tick.symbol.find('.689') != -1))
        if (buyBaseNum == 1) and tech_flag:
            if (leftCash > curVal5 * 200):
                buyBaseNum += 1
            else:
                # 买不起就直接返回
                log(f'科创股至少需要买入200股，目前剩余资金不足：{leftCash} 需要：{curVal5 * 200}')
                return
        
        msg = f"开始尝试买入数量:{buyBaseNum * 100} 预计花费:{round(buyBaseNum * 100 * curVal5, 3)}元 目前余额:{round(leftCash, 3)}元"
        msg += f"\n买入使用卖5价格：{curVal5}"
        log(msg)

        # 买入！！！！！！！！
        # 脚本设定了指定价格的话，则使用脚本的设定价格
        if context.ids[tick.symbol].buy_with_price != 0:
            curVal5 = context.ids[tick.symbol].buy_with_price
        # 指定买入量的话，则只买入设置的量
        if context.ids[tick.symbol].buy_with_num != 0:
            buyBaseNum = (int)(context.ids[tick.symbol].buy_with_num / 100)
        list_order = order_volume(symbol=tick.symbol, volume=buyBaseNum * 100, side=OrderSide_Buy, order_type=context.order_type_buy, position_effect=PositionEffect_Open, price=curVal5)
        #print(f"list order:{list_order}")
        
        # 记录order的client id，避免出现之前的重复购买
        # 只有当id在order status的回掉中，出现已成（不是部成）或者被拒绝的时候，才开放再次购买
        # 需要一定的数据格式，记录在context全局变量中，这样不会被擦除
        # 数据信息：{symbol:[list_order]}，直接把list_order一下装进去吧，也不用费事单独拆一些数据了
        context.client_order[tick.symbol] = list_order
        
        # 从ids_buy中消除已经购买过的记录（用于判断还有最后一只没买，防止碎股情况）
        # if tick.symbol in context.ids_buy:
        #     context.ids_buy.remove(tick.symbol)

        if context.test_info == 3:
            print(f"buy time cost, pt4: {time.time() - t:.4f} s")

def try_sell_strategyB(context, tick):
    # 获取当前持仓
    t = time.time()
    curHolding = 0
    # 这里的Side一定要标注正确，比如我是买入的脚本，里面有个都是使用的Buy类型
    # 验证了下，获取买入后的持仓都是Buy类型，不是我想象的sell就要获取sell类型，我估计期货才用这个
    pos = context.account().position(symbol = tick.symbol, side = OrderSide_Buy)
    if not pos:
        curHolding = 0
        return
        #print(f'{tick.symbol} cur holding: 0')
    else:
        curHolding = pos.available_now
        # print(f"{tick.symbol} 今持：{curHolding} 总持：{pos.volume} 可用：{pos.available_now}")

    # 更新vwap或者记录的买入价格到缓存，便于统计数据
    buy_price = pos.vwap
    # 下面的代码段有非常大的bug，本来是为了解决连续买入卖出时的成本不一致问题
    # 但是有个问题，就是这个更新的vwap，在我们卖出后，今天可能再次买入，买入的价格就更新了。。。。，但是实际我们统计的时候应该用上次记录的，这里完全就冲突了
    # 最后还会导致今日的统计值不正常，想清楚之前先不要使用这个了
    # if (tick.symbol in context.buy_pos_dict.keys()):
    #     buy_price = context.buy_pos_dict[tick.symbol] if context.buy_pos_dict[tick.symbol] > 0 else pos.vwap
    if (context.ids_virtual_sell_target_info_dict[tick.symbol].vwap == 0) and (buy_price > 0):
        context.ids_virtual_sell_target_info_dict[tick.symbol].vwap = buy_price
    context.ids_virtual_sell_target_info_dict[tick.symbol].hold = curHolding

    # 持仓浮动盈亏比例：amount持仓总额，fpnl浮动盈利值，vwap持仓均价
    #float_profit_rate = pos.fpnl / pos.amount # 这个应该是错误的，盈利是基于买入的成本价，而不是整体持仓市值（这个是对的，但是好像不太及时，算出来的涨跌幅，总是比最新价要少一点点）
    if (tick.price == 0):
        return

    # 这个在集合竞价的阶段最新价都是0，都是亏损100%。。。。，需要处理这个细节，技术支持建议用这个
    float_profit_rate = (tick.price - buy_price) / buy_price 
    context.ids_virtual_sell_target_info_dict[tick.symbol].fpr = float_profit_rate;
    # 使用这种方法计算涨幅，就不会遇到集合竞价时tick.price=0的情况，但是两种算法有点差异，技术建议是用上面
    #float_profit_rate = pos.fpnl / pos.amount 
    # print(f"-------->>>>>>tset 浮动盈利：{round(float_profit_rate * 100, 3)}% test val：{round(pos.fpnl / pos.amount * 100, 3)}%")

    # 如果client order还没有处理完，也返回
    if tick.symbol in context.client_order.keys():
        #print(f'{tick.symbol}订单没有处理完毕，直接返回')
        return

    if curHolding == 0:
        return

    # if context.test_info == 2:
    #     print(f"sell time cost, pt1: {time.time() - t:.4f} s")

    leftCash = context.account().cash['available'] # 余额
    leftCash = float('%.2f' % leftCash)
    curVal1_5 = [tick.quotes[0]['bid_p'], tick.quotes[1]['bid_p'], tick.quotes[2]['bid_p'], tick.quotes[3]['bid_p'], tick.quotes[4]['bid_p']]
    curVal5 = 0 #买5价格
    for idx in range(0, context.strategy_info.slip_step):
        if (curVal1_5[context.strategy_info.slip_step - 1 - idx] != 0):
            curVal5 = curVal1_5[context.strategy_info.slip_step - 1 - idx]
            break
        
    if (curVal5 == 0):
        print(f"[{tick.symbol}][try sell]--this should not happen, all values are 0, return for tmp")
        return

    # 获取所有持仓信息时，side可以使用None，但是如果你只想获取买入的所有持仓，那也需要调整
    curHoldTypeNum = len(context.account().positions(symbol='', side=None))
    if context.ids_virtual_sell_target_info_dict[tick.symbol].pre_close == 0:
        info = get_instruments(symbols = tick.symbol, df = True)
        # empty情况一般就是ST的股票，直接先跳过不处理
        if info.empty:
            return
            
        # 最好不要直接使用df的值，很多奇怪的现象，比如下面的float相除，如果插入了df数据，结果是对的，但是小数点只有2位。。。。
        # 一定要先从数组里拿出来
        context.ids_virtual_sell_target_info_dict[tick.symbol].pre_close = info.pre_close[0]
        context.ids_virtual_sell_target_info_dict[tick.symbol].name = info.sec_name[0]
        
    pre_close = context.ids_virtual_sell_target_info_dict[tick.symbol].pre_close
    name = context.ids_virtual_sell_target_info_dict[tick.symbol].name

    # if context.test_info == 2:
    #     print(f"sell time cost, pt2: {time.time() - t:.4f} s")

    #print(f"总资金{context.account().cash['nav']} 总市值{context.account().cash['market_value']} 总浮动盈亏{context.account().cash['fpnl']}")
    # 错误统计：总市值会受到已经卖出的标的干扰，比如卖出时时7%，但是后来到-7%了，这样计算整体的即使收益就有问题，所以我们必须在卖出后，要把卖出的票记录到缓存和文件中
    # cur_market_value = context.account().cash['market_value'] # 当前总市值
    # cur_market_value = float('%.2f' % cur_market_value)

    # 正确统计：通过缓存（记录）值，加上剩余没有卖出的总和才能得到正确值！！！！
    # 为了减轻计算负担，这里要判断下是否满意进入整体盈利和限时情况，有任意一个进入后就不再更新这里的市值计算了
    valid_tfpr_flag = True
    # 下面条件取消了context.tick_count_for_sell_ok的频率控制，有可能导致计算负担的加大？下面的print加入了频率控制，观察下AA的情况，再看下一步调整
    if (not context.sell_with_total_float_profit_flag) and (not context.sell_with_time_limit_flag) and (not context.sell_with_total_float_loss_flag):
        
        cur_market_value = 0
        handle_count = 0 # 用来调试总盈利计算错误问题，看是否执行完毕所有的目标
        for k,v in context.sell_pos_dict.items():
            mv = 0
            if (not v[1]) and (k in context.ids_virtual_sell_target_info_dict.keys()):
                mv = context.ids_virtual_sell_target_info_dict[k].price * v[0] #change mark
            else:
                mv = (v[0] * v[2])
            if mv <= 0:
                if k in context.ids_virtual_sell_target_info_dict.keys():
                    log(f"[sell] fatal potential error, mv[{mv}] should not be 0, [{k}] price[{context.ids_virtual_sell_target_info_dict[k].price}] hold[{v[0]}] sold_price[{v[2]}]")
                valid_tfpr_flag = False
                break
            cur_market_value += mv
            handle_count += 1

        # 现在策略AB应该是可以共用一套了，因为不管是否存在买入和卖出的混合，我们有了当天的文件缓存后，都可以计算正确的整体盈利了
        # 之前的话，因为没有文件缓存，所以逻辑上有点混乱，现在是很清晰的
        total_float_profit_rate = (cur_market_value - context.total_market_value_for_all_sell) / context.total_market_value_for_all_sell if context.total_market_value_for_all_sell != 0 else 0
        if cur_market_value == 0:
            print(f"Fatal error!! cur mv == 0, sell_pos_dict len:[{len(context.sell_pos_dict)}]")
            return
        # print(f"cur_mv[{cur_market_value}] total_mv[{context.total_market_value_for_all_sell}]")
        if valid_tfpr_flag and context.tick_count_for_sell_ok:
            print(f"总盈亏：{round(total_float_profit_rate * 100, 3)}%")
            context.tfpr = total_float_profit_rate
            # 检测一下异常，目前出现的非常低的百分比不知道怎么回事，需要排查下
            if (context.tfpr <= -0.05) or (context.tfpr >= 0.1):
                log(f"[sell][Fatal-Error] 出现异常总盈亏数据{round(total_float_profit_rate * 100, 3)}%, total_mv[{context.total_market_value_for_all_sell}] cur_mv[{cur_market_value}] sell_pos_dict_len[{len(context.sell_pos_dict)}] handle_len[{handle_count}]")
        # 更新和检测整体的追高情况（特定情况应该放弃追高卖出）
        if context.sell_all_chase_raise_flag:
            # 更新最高值
            if total_float_profit_rate > context.sell_all_chase_highest_record:
                context.sell_all_chase_highest_record = total_float_profit_rate
            # 检测最高值是否已经超过我们设定的卖出底线
            if context.sell_all_chase_highest_record > context.sell_all_lower_limit:
                # 超过底线后，有两个情况要卖出
                # 1. 再次低于底线值得时候直接卖出（保底），首要条件
                # 2. 从一个较高的值，比如0.99%回撤到了0.84，回撤超过15%也卖出，说明冲力不行
                if (not context.sell_with_total_float_profit_flag) and (total_float_profit_rate < context.sell_all_lower_limit):
                    context.sell_with_total_float_profit_flag = True
                    log(f"-------->已激活整体盈利卖出条件(追高回落超过底线)，目前设定的整体盈利为：{context.Sell_All_Increase_Rate * 100}%，设置的底线为：{context.sell_all_lower_limit}，当前整体盈利为：{round(context.tfpr * 100, 3)}%")
                    context.record_sell_time = context.now
                    context.record_sell_tfpr = context.tfpr
                elif (not context.sell_with_total_float_profit_flag) and ((total_float_profit_rate - context.sell_all_chase_highest_record) / context.sell_all_chase_highest_record < -0.12):
                    context.sell_with_total_float_profit_flag = True
                    log(f"-------->已激活整体盈利卖出条件(追高回落超过12%)，目前设定的整体盈利为：{context.Sell_All_Increase_Rate * 100}%，记录的最高值为：{round(context.sell_all_chase_highest_record, 3)}，当前整体盈利为：{round(context.tfpr * 100, 3)}%")
                    context.record_sell_time = context.now
                    context.record_sell_tfpr = context.tfpr

        # 更新记录最大的总浮动盈亏（用于在13点35分，也就是设定的全部卖出时段进行log记录）
        # if valid_tfpr_flag and (total_float_profit_rate > context.highest_total_float_profit_info[0]):
        #     context.highest_total_float_profit_info[0] = total_float_profit_rate
        #     context.highest_total_float_profit_info[1] = context.now
        # if valid_tfpr_flag and (total_float_profit_rate < context.lowest_total_float_profit_info[0]):
        #     context.lowest_total_float_profit_info[0] = total_float_profit_rate
        #     context.lowest_total_float_profit_info[1] = context.now


    # if context.test_info == 2:
    #     print(f"sell time cost, pt3: {time.time() - t:.4f} s")
    # 大于整体盈利卖出条件后，直接激活卖出条件（不再重置false）
    # false只在init时有一次，后续只要激活就全部卖出（只激活一次即可）
    # 只激活一次的策略，有可能带来了滑点严重的问题？？因为激活的瞬间，可能整体盈利还在抖动，所以导致一直有0.2%左右的差值？？所以需要改为反复激活，也就是激活后，也要保证后续的每只股卖出时都达到了整体收益？？（需要验证）
    if (not context.sell_with_total_float_profit_flag) and (valid_tfpr_flag) and (context.tfpr > context.Sell_All_Increase_Rate):
        context.sell_with_total_float_profit_flag = True
        log(f"-------->已激活整体盈利卖出条件，目前设定的整体盈利为：{context.Sell_All_Increase_Rate * 100}%，当前整体盈利为：{round(context.tfpr * 100, 3)}%")
        context.record_sell_time = context.now
        context.record_sell_tfpr = context.tfpr

    # 整体止损再满足条件后，激活一次即可
    if (not context.sell_with_total_float_loss_flag) and (valid_tfpr_flag) and (context.tfpr < context.Sell_All_Loss_Rate):
        context.sell_with_total_float_loss_flag = True
        log(f"-------->已激活整体止损卖出条件，目前设定的整体止损为：{context.Sell_All_Loss_Rate * 100}%，当前整体止损为：{round(context.tfpr * 100, 3)}%")
        context.record_sell_time = context.now
        context.record_sell_tfpr = context.tfpr


    # TODO:这里还可以稍微优化下，过时限卖出的flag可以改为全局的，不过这个也不会有什么影响
    now = datetime.datetime.strptime(str(context.now.date()) + str(context.now.hour) + ":" + str(context.now.minute), '%Y-%m-%d%H:%M')
    target_time = datetime.datetime.strptime(str(context.now.date()) + sell_all_time, '%Y-%m-%d%H:%M')
    target_time_for_solo = datetime.datetime.strptime(str(context.now.date()) + context.ids[tick.symbol].sell_with_time, '%Y-%m-%d%H:%M')
    #change mark2
    if (not context.sell_with_time_limit_flag) and (now >= target_time):
        context.sell_with_time_limit_flag = True
        context.record_sell_time = context.now
        context.record_sell_tfpr = context.tfpr

    # 开始判断卖出的条件，一共4个
    # 1.涨幅达标，可以卖出
    # 2.达到13点35分，无论情况，直接全部卖出（要准备换第二天的标的了）
    # 3.强制止损，必须卖出
    # 4.整体盈利到达目标，全部卖出
    # 5.配置直接卖出单个（避免手动平仓）--ID后面加字符s
    # 6.整体止损
    # 7.配置直接清仓所有--fsa标记修改，详见配置文件中的说明
    # 8.配置单个标的卖出的涨幅比例
    # 9.配置单个标的的卖出时间
    # 10.配置单个标的卖出股数（使用方式SN100SN，不需要加s标识）

    sell_condition1 = float_profit_rate > context.Sell_Increase_Rate
    sell_condition2 = context.sell_with_time_limit_flag
    sell_condition3 = float_profit_rate < context.Sell_Loss_Limit
    sell_condition4 = context.sell_with_total_float_profit_flag
    # 重置整体盈利卖出标识（必须每只股都重新计算，保证贴合卖出线）
    context.sell_with_total_float_profit_flag = False
    sell_condition5 = context.ids[tick.symbol].force_sell_flag
    sell_condition6 = context.sell_with_total_float_loss_flag
    # 强制卖出所有，配置文件中配置fsa
    sell_condition7 = context.force_sell_all_flag
    # 配置文件支持的SR1SR，上涨超过1%卖出，也支持负数，负数的话是止损
    sell_condition8 = (float_profit_rate > context.ids[tick.symbol].sell_with_rate) if (context.ids[tick.symbol].sell_with_rate > 0) else (float_profit_rate < context.ids[tick.symbol].sell_with_rate)
    # 配置文件支持的限时卖出ST10:00ST
    sell_condition9 = (now >= target_time_for_solo)
    sell_condition10 = (context.ids[tick.symbol].sell_with_num > 0)

    if context.test_info == 2:
        print(f"sell time cost, pt4: {time.time() - t:.4f} s")

    # 开始判断条件，并尝试卖出
    if sell_condition1 or sell_condition2 or sell_condition3 or sell_condition4 or sell_condition5 or sell_condition6 or sell_condition7 or sell_condition8  or sell_condition9 or sell_condition10:
        msg = f"\n-------->>开始尝试卖出[{tick.symbol}:{name}]，当前持仓量:{curHolding} 现金余额:{round(leftCash, 3)} 当前持仓品种数量:{curHoldTypeNum}"
        msg += f"\n昨收价格:{round(pre_close, 2)} 今开价格:{round(tick.open, 2)} 瞬间价格:{round(tick.price, 2)} 成本价:{pos.vwap}"
        msg += f"\n卖出时盈亏百分比:{round(float_profit_rate * 100.0, 3)}% 是否为高预期{context.ids[tick.symbol].high_expected_flag}"
        msg += f"\n瞬间整体盈利：{round(context.tfpr * 100, 3)}%, Valid：{valid_tfpr_flag}"
        msg += f"\n是否使用市价成交：{context.strategy_info.order_type_sell.Market}"

        msg += f"\n卖出原因："
        if sell_condition1:
            msg += "盈利达标后卖出"
        elif sell_condition2:
            msg += "时间满足标准后卖出"
        elif sell_condition3:
            msg += "止损后卖出"
        elif sell_condition4:
            msg += f"整体盈利达标后卖出"
        elif sell_condition6:
            msg += f"整体止损后卖出"
        elif sell_condition5:
            msg += "配置文件标记强制卖出单个"
        elif sell_condition7:
            msg += "配置文件标记强制清仓所有"
        elif sell_condition8:
            msg += "配置文件单个涨幅达标"
        elif sell_condition9:
            msg += "配置文件指定时间卖出"
        elif sell_condition10:
            msg += "配置文件指定股数卖出"

        msg += f"\n卖出使用买5价格：{curVal5}"
        log(msg)

        # 卖出！！！！！！！！
        # 如果设置了脚本的指定卖出价格，则以指定的价格为准
        list_order = []
        # 判断是否有指定卖出数量，且挂单后，重置数量到0，避免反复卖出指定数量
        if context.ids[tick.symbol].sell_with_num != 0:
            curHolding = int(context.ids[tick.symbol].sell_with_num)
            # 将读取的卖出数量重置到0，否则会连续卖出，这样的话，除非再次刷新（且配置仍然存在），才会继续卖出
            context.ids[tick.symbol].sell_with_num = 0
        if context.ids[tick.symbol].sell_with_price != 0:
            list_order = order_volume(symbol=tick.symbol, volume=curHolding, side=OrderSide_Sell, order_type=OrderType_Limit, position_effect=PositionEffect_Close, price=context.ids[tick.symbol].sell_with_price)
        else:
            list_order = order_volume(symbol=tick.symbol, volume=curHolding, side=OrderSide_Sell, order_type=context.order_type_sell, position_effect=PositionEffect_Close, price=curVal5)
        #print(f"list order:{list_order}")
        
        # 记录order的client id，避免出现之前的重复购买
        # 只有当id在order status的回掉中，出现已成（不是部成）或者被拒绝的时候，才开放再次购买
        # 需要一定的数据格式，记录在context全局变量中，这样不会被擦除
        # 数据信息：{symbol:[list_order]}，直接把list_order一下装进去吧，也不用费事单独拆一些数据了
        context.client_order[tick.symbol] = list_order

        if context.test_info == 2:
            print(f"sell time cost, pt5: {time.time() - t:.4f} s")


def try_buy_strategyB1(context, tick):
    # 如果client order还没有处理完，也返回
    if tick.symbol in context.client_order.keys():
        #print(f'{tick.symbol}订单没有处理完毕，直接返回')
        return

    # 获取当前持仓
    curHolding = 0
    # 这里的Side一定要标注正确，比如我是买入的脚本，里面有个都是使用的Buy类型
    pos = context.account().position(symbol = tick.symbol, side = side_type)
    if not pos:
        curHolding = 0
        #print(f'{tick.symbol} cur holding: 0')
    else:
        curHolding = pos.volume_today if (side_type == OrderSide_Buy) else pos.available_now
        #print(f"{tick.symbol} 今持：{curHolding} 总持：{pos.volume} 可用：{pos.available_now}")

    if tick.symbol not in context.ids_buy_target_info_dict.keys():
        return

    # 检测持仓取值是否出现问题（有小概率出现，部成的值已经记录，且大于这里取出的持仓），还是需要处理
    if curHolding < context.ids_buy_target_info_dict[tick.symbol].total_holding:
        #log(f"[Warning][{tick.symbol}]出现了仓位{curHolding}刷新不及时问题，已通过记录数据更新到{context.ids_buy_target_info_dict[tick.symbol].total_holding}")
        curHolding = context.ids_buy_target_info_dict[tick.symbol].total_holding
        #log(f"[Warning][{tick.symbol}]出现了仓位{curHolding}刷新不及时问题，已通过记录数据更新到{context.ids_buy_target_info_dict[tick.symbol].total_holding}")
        curHolding = context.ids_buy_target_info_dict[tick.symbol].total_holding

    # 股票提供买卖5档数据, list[0]~list[4]分别对应买卖一档到五档
    #print(f"买卖信息：{tick.quotes[0]['bid_p']} {tick.quotes[1]['bid_p']} {tick.quotes[2]['bid_p']} {tick.quotes[3]['bid_p']} {tick.quotes[4]['bid_p']}---- cur val{tick.price}")
    buy_in_down_rate = context.Buy_In_Fall_Rate
    buy_in_up_rate = context.Buy_In_Up_Rate
    useClose = (context.Use_Close == 1)
    # 这里和策略A不一样，数量是动态的
    totalBuyNum = context.buy_num
    # 获取所有持仓信息时，side可以使用None，但是如果你只想获取买入的所有持仓，那也需要调整
    curHoldTypeNum = len(context.account().positions(symbol='', side=None))
    # 品种数量达标后，还不能返回，因为有些票可能是部成，然后我又撤销了，这样会导致资金用不完
    # if (curHoldTypeNum >= totalBuyNum):
    #     return

    if len(context.already_buy_in_keys) >= context.Buy_In_Limit_Num:
        return;

    # 跳过集合竞价的不正常价格区间
    if (tick.price == 0):
        return
    
    # 检测设定买入股数的情况下，是否已经处理完毕需要返回（一般这种情况都是小股数，但是可能存在被撤单失败的情况，如果出现，则需要去check_unfinished_order函数调整条件）
    if (context.ids[tick.symbol].buy_with_num_need_handle) and (context.ids[tick.symbol].buy_with_num_handled_flag):
        return
    
    leftCash = context.account().cash['available'] # 余额
    leftCash = float('%.2f' % leftCash)
    totalCash = context.account().cash['nav'] # 总资金
    totalCash = float('%.2f' % totalCash)
    
    avgBuyAmount = 0
    limitBuyAmountFlag = False # 某些情况需要限制买入数量，比如设定了买入量的话，我们在下面就不要去加1的BaseNum了，不然会多用钱
    if context.strategy_info.buy_mode.buy_all == 1:
        avgBuyAmount = totalCash / totalBuyNum
    elif context.strategy_info.buy_mode.buy_one == 1:
        avgBuyAmount = context.ids[tick.symbol].buy_amount
        limitBuyAmountFlag = True
    elif context.strategy_info.buy_mode.buy_all_force == 1:
        if not check_buy_all_force_flag(context):
            #print(f"还未拿到强制买入所有标的的有效标识，先返回")
            return
        avgBuyAmount = context.ids_buy_target_info_dict[tick.symbol].fixed_buy_in_base_num * 100.0 * tick.price


    # 持仓大于0，就不买入了，我们用的是今日买入量volume_today，不会出现判断问题，今天买过就不买了
    # 【MAYBE TODO】这里可能有待改进？？？因为会不会出现部成的情况，剩下的委托被我撤销？？需要观察
    # 如果要改进，那就需要判断当前持仓是否达到了均分的额度，没有的话，就还可以买入剩余额度，但是这样就会比较复杂，先观察吧    
    # 已出现上面提到的TODO情况，就是部成以后，撤销订单，就只买了一部分，这样钱会用不完，还需要判断该股买入数量是否达标
    buy_enough_flag = False
    vwap = 0.0 if (not pos) else pos.vwap
    left_space = avgBuyAmount - (vwap * curHolding)
    if ((left_space >= 0) and (left_space / (tick.price * 100.0) < 0.1)) or (left_space < 0):
        buy_enough_flag = True
    if (curHolding > 0) and (buy_enough_flag) and (context.ids[tick.symbol].buy_with_num == 0):
        return
    # 强制买入所有，持仓达标情况下，不进行任何补买动作
    elif (context.strategy_info.buy_mode.buy_all_force == 1) and ((curHolding / 100) == context.ids_buy_target_info_dict[tick.symbol].fixed_buy_in_base_num):
        return
    
    # 基础条件：
    # 和策略A不一样，B的话，直接买入，持仓>0前面判断过了，order在处理中也判断过了，使用下面的买入不需要任何条件了，直接买就ok
    buyCondition = True

    # 实盘附加条件：除了满足测试条件外，还需要满足下降百分比条件
    # dynainfo3：昨收，dynainfo4：今开，dynainfo7：最新
    if context.ids_buy_target_info_dict[tick.symbol].pre_close == 0:
        info = get_instruments(symbols = tick.symbol, df = True)
        # empty情况一般就是ST的股票，直接先跳过不处理
        if info.empty:
            print(f"get info null, this should not happen......")
            return
            
        # 最好不要直接使用df的值，很多奇怪的现象，比如下面的float相除，如果插入了df数据，结果是对的，但是小数点只有2位。。。。
        # 一定要先从数组里拿出来
        context.ids_buy_target_info_dict[tick.symbol].pre_close = info.pre_close[0]
        context.ids_buy_target_info_dict[tick.symbol].name = info.sec_name[0]
        context.ids_buy_target_info_dict[tick.symbol].upper_limit = info.upper_limit[0]
        
    pre_close = context.ids_buy_target_info_dict[tick.symbol].pre_close
    name = context.ids_buy_target_info_dict[tick.symbol].name

    # print(f"pre close {info.pre_close}")
    # print(f"test--------------[{tick.symbol} {info.empty}")
    # 下面的basePrice暂时不需要计算，是策略A根据跌幅买入的条件，先屏蔽
    #basePrice = info.pre_close if not info.empty else tick.open
    # if useClose:
    #     basePrice = info.pre_close if not info.empty else tick.open
    #     basePrice = float(basePrice[0]) if not info.empty else tick.open# 转换dataframe，df出来的数据都是数组!!!
    # else:
    #     basePrice = tick.open
    
    # 最新价格，目前使用的最新价格，我们直接用买（卖）5的价格
    # 也就是我们目前使用滑点5的设置
    # 股票提供买卖5档数据, list[0]~list[4]分别对应买卖一档到五档
    curVal = tick.price
    curVal1_5 = [tick.quotes[0]['ask_p'], tick.quotes[1]['ask_p'], tick.quotes[2]['ask_p'], tick.quotes[3]['ask_p'], tick.quotes[4]['ask_p']] #卖1-5价格
    # 这里需要对值进行检测，有时候买卖5是空的，需要选择一个有效值
    curVal5 = 0
    for idx in range(0, context.strategy_info.slip_step):
        if (curVal1_5[context.strategy_info.slip_step - 1 - idx] != 0):
            curVal5 = curVal1_5[context.strategy_info.slip_step - 1 - idx]
            break

    if (curVal5 == 0):
        print(f"[{tick.symbol}][try buy]--this should not happen, all values are 0, return for tmp")
        return

    # 使用市价的话，不再使用滑点价格，而是使用涨停价格（跟卷商人员确认过）
    if context.strategy_info.order_type_buy.Market == 1:
        curVal5 = context.ids_buy_target_info_dict[tick.symbol].upper_limit

    # 掘金里的涨跌幅是需要自己手动计算的
    rate = (curVal - pre_close) / pre_close

    # 检测多次上涨后买入相关逻辑
    multi_up_buy_complete = check_multi_up_flag(context, tick, rate, buy_in_up_rate)

    now = datetime.datetime.strptime(str(context.now.date()) + str(context.now.hour) + ":" + str(context.now.minute), '%Y-%m-%d%H:%M')
    target_time_for_solo = datetime.datetime.strptime(str(context.now.date()) + context.ids[tick.symbol].buy_with_time, '%Y-%m-%d%H:%M')
    
    # 具体买入条件：
    # 0.先觉条件，买的起一手（科技股需要200，会在下面的流程判断）
    # 1.上涨超过0.8%（策略B1特有条件）
    # 2.脚本配置强制买，无视其他条件
    # 3.配置文件，单个标的涨幅
    # 4.配置文件，达到时间买入
    # 5.配置文件，单个标的股数（BN100BN，不需要b标识）

    enoughMoney1Hand = leftCash > (curVal5 * 100)
    # 很奇怪，金字塔的python可以用and，但是在掘金准备就必须用&替换and，否则会报错
    # 其实不用把and换成&，主要是因为df的数据是一个数组，所以没法直接比较
    buyCondition1 = (rate > buy_in_up_rate)
    buyCondition2 = True if context.ids[tick.symbol].force_buy_flag else False
    buyCondition3 = (rate > context.ids[tick.symbol].buy_with_rate) if (context.ids[tick.symbol].buy_with_rate > 0) else (rate < context.ids[tick.symbol].buy_with_rate)
    buyCondition4 = (now >= target_time_for_solo)
    buyCondition5 = (context.ids[tick.symbol].buy_with_num > 0)

    # 在合适的情况下输出剩余空间信息
    if (leftCash > left_space) and (enoughMoney1Hand):
        print(f'{tick.symbol} 涨跌幅：{round(rate * 100.0, 3)}% 最新价格：{tick.price} 剩余空间：{left_space} leftcash：{leftCash}')  
    
    if enoughMoney1Hand and (buyCondition1 or buyCondition2 or buyCondition3 or buyCondition4 or buyCondition5):
        market_value = 0 if (not pos) else pos.amount
        print(f"---------->>>test{tick.symbol}")
        msg = f"\n-------->>开始尝试买入[{tick.symbol}:{name}]，当前持仓量:{curHolding} 市值:{round(market_value, 2)} 现金余额:{round(leftCash, 3)} 当前持仓品种数量:{curHoldTypeNum}"
        msg += f"\n总资金：{totalCash} 均分值：{round(avgBuyAmount, 2)} 买入股票总数：{context.buy_num} 前两者乘值：{round(avgBuyAmount * context.buy_num, 2)}"
        msg += f"\n昨收价格:{round(pre_close, 2)} 今开价格:{round(tick.open, 2)} 瞬间价格:{round(tick.price, 2)}"
        msg += f"\n买入时涨幅百分比:{round(rate * 100.0, 3)}% 是否为高预期{context.ids[tick.symbol].high_expected_flag}"
        msg += f"\n是否使用市价成交：{context.strategy_info.order_type_buy.Market}"

        if buyCondition1:
            msg += f"\n涨幅达标，进行买入"
        elif buyCondition2:
            msg += f"\n配置文件设置强制买入"
        elif buyCondition3:
            msg += f"\n配置文件，单只涨幅达标买入"
        elif buyCondition4:
            msg += f"\n配置文件，到指定时间买入"
        elif buyCondition5:
            msg += f"\n配置文件，买入指定的股数"

        log(msg)
        
        shouldBuyAmout = 0
        if (leftCash > left_space):
            # 目前仅剩一只票可以买的话，就直接把剩下的钱都买了？？
            # 这里出过bug，就是本来全仓都在一只票上，结果卖出的时候，买入脚本判断资金够了
            # 但是判断只剩一个仓位（也就是位置刷新不及时.....）
            # 这里应该再和资产总值对比一下，如果剩余资金基本等于资产总值，就说明出现这个问题了，这个时候就不应该全买
            #if ((totalBuyNum - curHoldTypeNum) == 1): # 错误版本，这种版本有碎股的话，就会有问题

            # 关闭最后一只全买的条件，bug很多，不好监测，因为品种够的时候很多都没有买够，不如直接使用剩余空间进行补齐就好
            if len(context.ids_buy) == 1 and False:
                msg = "只剩最后一个仓位，尝试买入所有余额------"
                print(msg)
                log(msg)
                # 这里的超标计算为：均分以后+均分部分的0.3，动态调整（总体说，就是可以超过自己份额的1/3，不能太多）
                # 对于2来说，就是0.5 + 0.5 * 0.3 = 0.65，应该算是比较合适的值了
                # 对于3来说，就是0.333 + 0.333 * 0.3 = 0.4329，也还算合适，应该是可以的
                allowRange = (1.0 / totalBuyNum) + (1.0 / totalBuyNum) * 0.5
                if ((leftCash / totalCash) < allowRange):
                    msg = f"剩余资金在正常范围:{round(leftCash / totalCash * 100, 2)}% 许可范围:{round(allowRange * 100, 2)}%，可以使用所有余额"
                    log(msg)
                    shouldBuyAmout = leftCash
                else:
                    msg = f"剩余资金超标:{round(leftCash / totalCash * 100, 2)}%  许可范围:{round(allowRange * 100, 2)}%，使用标准均分值 {avgBuyAmount} 购买"
                    log(msg)
                    shouldBuyAmout = left_space
            else:
                msg = f"使用剩余空间{round(left_space, 2)}购买，正常情况"
                log(msg)
                shouldBuyAmout = left_space
        else:
            msg = f"使用所有余额{leftCash}进行购买，剩余资金小于购买量的情况（需要注意）"
            log(msg)
            shouldBuyAmout = leftCash
        
        # 计算应该买入的数量：需要结合总股以及现金余额数进行处理（总股数需要手动设置正确）
        #print(f"tmp test...amount{shouldBuyAmout} val5{curVal5}")
        buyNum = shouldBuyAmout / curVal5
        buyNum = math.floor(buyNum)
        msg = f"原始买入预估数量：{buyNum}"
        log(msg)
        
        # 考虑特殊情况，买不起1手的话（均分价格下），需要具体分析情况
        # 目前使用的策略是，只要资金足够买一手，那么就买，不考虑占总资金的百分比
        if (buyNum < 100) and (enoughMoney1Hand):
            msg = "均价不够买一手，但是剩余资金足够"
            log(msg)
            buyNum = 100
            
        # 把买入数量化整，整除为基数，余数大于70且资金充足的情况下，基数可以尝试加1
        buyNumLessOneHand = 10
        buyBaseNum = math.floor(buyNum / 100)
        remainder = buyNum % 100
        if (not limitBuyAmountFlag) and (remainder >= buyNumLessOneHand) and (leftCash > curVal5 * (buyBaseNum + 1) * 100):
            buyBaseNum += 1

        if (context.strategy_info.buy_mode.buy_all_force == 1):
            buyBaseNum = context.ids_buy_target_info_dict[tick.symbol].fixed_buy_in_base_num

        # 科创股至少买200，检查如果是100的话，能买的起200就买
        tech_flag = ((tick.symbol.find('.688') != -1) or (tick.symbol.find('.689') != -1))
        if (buyBaseNum == 1) and tech_flag:
            if (leftCash > curVal5 * 200):
                buyBaseNum += 1
            else:
                # 买不起就直接返回
                log(f'科创股至少需要买入200股，目前剩余资金不足：{leftCash} 需要：{curVal5 * 200}')
                return
        
        msg = f"开始尝试买入数量:{buyBaseNum * 100} 预计花费:{round(buyBaseNum * 100 * curVal5, 3)}元 目前余额:{round(leftCash, 3)}元"
        msg += f"\n买入使用卖5价格：{curVal5}"
        log(msg)

        # 买入！！！！！！！！
        # 脚本设定了指定价格的话，则使用脚本的设定价格
        if context.ids[tick.symbol].buy_with_price != 0:
            curVal5 = context.ids[tick.symbol].buy_with_price
        # 指定买入量的话，则只买入设置的量
        if context.ids[tick.symbol].buy_with_num != 0:
            buyBaseNum = (int)(context.ids[tick.symbol].buy_with_num / 100)
        list_order = order_volume(symbol=tick.symbol, volume=buyBaseNum * 100, side=OrderSide_Buy, order_type=context.order_type_buy, position_effect=PositionEffect_Open, price=curVal5)
        #print(f"list order:{list_order}")
        
        # 记录order的client id，避免出现之前的重复购买
        # 只有当id在order status的回掉中，出现已成（不是部成）或者被拒绝的时候，才开放再次购买
        # 需要一定的数据格式，记录在context全局变量中，这样不会被擦除
        # 数据信息：{symbol:[list_order]}，直接把list_order一下装进去吧，也不用费事单独拆一些数据了
        context.client_order[tick.symbol] = list_order
        
        # 从ids_buy中消除已经购买过的记录（用于判断还有最后一只没买，防止碎股情况）
        # if tick.symbol in context.ids_buy:
        #     context.ids_buy.remove(tick.symbol)

def try_sell_strategyB1(context, tick):
    # 获取当前持仓
    curHolding = 0
    # 这里的Side一定要标注正确，比如我是买入的脚本，里面有个都是使用的Buy类型
    # 验证了下，获取买入后的持仓都是Buy类型，不是我想象的sell就要获取sell类型，我估计期货才用这个
    pos = context.account().position(symbol = tick.symbol, side = OrderSide_Buy)
    if not pos:
        curHolding = 0
        return
        #print(f'{tick.symbol} cur holding: 0')
    else:
        curHolding = pos.available_now
        # print(f"{tick.symbol} 今持：{curHolding} 总持：{pos.volume} 可用：{pos.available_now}")

    # 更新vwap或者记录的买入价格到缓存，便于统计数据
    buy_price = pos.vwap
    # 下面的代码段有非常大的bug，本来是为了解决连续买入卖出时的成本不一致问题
    # 但是有个问题，就是这个更新的vwap，在我们卖出后，今天可能再次买入，买入的价格就更新了。。。。，但是实际我们统计的时候应该用上次记录的，这里完全就冲突了
    # 最后还会导致今日的统计值不正常，想清楚之前先不要使用这个了
    # if (tick.symbol in context.buy_pos_dict.keys()):
    #     buy_price = context.buy_pos_dict[tick.symbol] if context.buy_pos_dict[tick.symbol] > 0 else pos.vwap
    if (context.ids_virtual_sell_target_info_dict[tick.symbol].vwap == 0) and (buy_price > 0):
        context.ids_virtual_sell_target_info_dict[tick.symbol].vwap = buy_price
    context.ids_virtual_sell_target_info_dict[tick.symbol].hold = curHolding

    # 持仓浮动盈亏比例：amount持仓总额，fpnl浮动盈利值，vwap持仓均价
    #float_profit_rate = pos.fpnl / pos.amount # 这个应该是错误的，盈利是基于买入的成本价，而不是整体持仓市值（这个是对的，但是好像不太及时，算出来的涨跌幅，总是比最新价要少一点点）
    if (tick.price == 0):
        return

    # 这个在集合竞价的阶段最新价都是0，都是亏损100%。。。。，需要处理这个细节，技术支持建议用这个
    float_profit_rate = (tick.price - buy_price) / buy_price 
    context.ids_virtual_sell_target_info_dict[tick.symbol].fpr = float_profit_rate;
    # 使用这种方法计算涨幅，就不会遇到集合竞价时tick.price=0的情况，但是两种算法有点差异，技术建议是用上面
    #float_profit_rate = pos.fpnl / pos.amount 
    # print(f"-------->>>>>>tset 浮动盈利：{round(float_profit_rate * 100, 3)}% test val：{round(pos.fpnl / pos.amount * 100, 3)}%")

    # 如果client order还没有处理完，也返回
    if tick.symbol in context.client_order.keys():
        #print(f'{tick.symbol}订单没有处理完毕，直接返回')
        return

    if curHolding == 0:
        return

    leftCash = context.account().cash['available'] # 余额
    leftCash = float('%.2f' % leftCash)
    curVal1_5 = [tick.quotes[0]['bid_p'], tick.quotes[1]['bid_p'], tick.quotes[2]['bid_p'], tick.quotes[3]['bid_p'], tick.quotes[4]['bid_p']]
    curVal5 = 0 #买5价格
    for idx in range(0, context.strategy_info.slip_step):
        if (curVal1_5[context.strategy_info.slip_step - 1 - idx] != 0):
            curVal5 = curVal1_5[context.strategy_info.slip_step - 1 - idx]
            break
        
    if (curVal5 == 0):
        print(f"[{tick.symbol}][try sell]--this should not happen, all values are 0, return for tmp")
        return

    # 获取所有持仓信息时，side可以使用None，但是如果你只想获取买入的所有持仓，那也需要调整
    curHoldTypeNum = len(context.account().positions(symbol='', side=None))
    if context.ids_virtual_sell_target_info_dict[tick.symbol].pre_close == 0:
        info = get_instruments(symbols = tick.symbol, df = True)
        # empty情况一般就是ST的股票，直接先跳过不处理
        if info.empty:
            return
            
        # 最好不要直接使用df的值，很多奇怪的现象，比如下面的float相除，如果插入了df数据，结果是对的，但是小数点只有2位。。。。
        # 一定要先从数组里拿出来
        context.ids_virtual_sell_target_info_dict[tick.symbol].pre_close = info.pre_close[0]
        context.ids_virtual_sell_target_info_dict[tick.symbol].name = info.sec_name[0]
        
    pre_close = context.ids_virtual_sell_target_info_dict[tick.symbol].pre_close
    name = context.ids_virtual_sell_target_info_dict[tick.symbol].name

    #print(f"总资金{context.account().cash['nav']} 总市值{context.account().cash['market_value']} 总浮动盈亏{context.account().cash['fpnl']}")
    # 错误统计：总市值会受到已经卖出的标的干扰，比如卖出时时7%，但是后来到-7%了，这样计算整体的即使收益就有问题，所以我们必须在卖出后，要把卖出的票记录到缓存和文件中
    # cur_market_value = context.account().cash['market_value'] # 当前总市值
    # cur_market_value = float('%.2f' % cur_market_value)

    # 正确统计：通过缓存（记录）值，加上剩余没有卖出的总和才能得到正确值！！！！
    # 为了减轻计算负担，这里要判断下是否满意进入整体盈利和限时情况，有任意一个进入后就不再更新这里的市值计算了
    valid_tfpr_flag = True
    # 下面条件取消了context.tick_count_for_sell_ok的频率控制，有可能导致计算负担的加大？下面的print加入了频率控制，观察下AA的情况，再看下一步调整
    if (not context.sell_with_total_float_profit_flag) and (not context.sell_with_time_limit_flag) and (not context.sell_with_total_float_loss_flag):
        cur_market_value = 0
        handle_count = 0 # 用来调试总盈利计算错误问题，看是否执行完毕所有的目标
        for k,v in context.sell_pos_dict.items():
            mv = 0
            if (not v[1]) and (k in context.ids_virtual_sell_target_info_dict.keys()):
                mv = context.ids_virtual_sell_target_info_dict[k].price * v[0] #change mark
            else:
                mv = (v[0] * v[2])
            if mv <= 0:
                if k in context.ids_virtual_sell_target_info_dict.keys():
                    log(f"[sell] fatal potential error, mv[{mv}] should not be 0, [{k}] price[{context.ids_virtual_sell_target_info_dict[k].price}] hold[{v[0]}] sold_price[{v[2]}]")
                valid_tfpr_flag = False
                break
            cur_market_value += mv
            handle_count += 1

        # 现在策略AB应该是可以共用一套了，因为不管是否存在买入和卖出的混合，我们有了当天的文件缓存后，都可以计算正确的整体盈利了
        # 之前的话，因为没有文件缓存，所以逻辑上有点混乱，现在是很清晰的
        total_float_profit_rate = (cur_market_value - context.total_market_value_for_all_sell) / context.total_market_value_for_all_sell if context.total_market_value_for_all_sell != 0 else 0
        if cur_market_value == 0:
            print(f"Fatal error!! cur mv == 0, sell_pos_dict len:[{len(context.sell_pos_dict)}]")
            return
        # print(f"cur_mv[{cur_market_value}] total_mv[{context.total_market_value_for_all_sell}]")
        if valid_tfpr_flag and context.tick_count_for_sell_ok:
            print(f"总盈亏：{round(total_float_profit_rate * 100, 3)}%")
            context.tfpr = total_float_profit_rate
            # 检测一下异常，目前出现的非常低的百分比不知道怎么回事，需要排查下
            if (context.tfpr <= -0.05) or (context.tfpr >= 0.1):
                log(f"[sell][Fatal-Error] 出现异常总盈亏数据{round(total_float_profit_rate * 100, 3)}%, total_mv[{context.total_market_value_for_all_sell}] cur_mv[{cur_market_value}] sell_pos_dict_len[{len(context.sell_pos_dict)}] handle_len[{handle_count}]")
        # 更新和检测整体的追高情况（特定情况应该放弃追高卖出）
        if context.sell_all_chase_raise_flag:
            # 更新最高值
            if total_float_profit_rate > context.sell_all_chase_highest_record:
                context.sell_all_chase_highest_record = total_float_profit_rate
            # 检测最高值是否已经超过我们设定的卖出底线
            if context.sell_all_chase_highest_record > context.sell_all_lower_limit:
                # 超过底线后，有两个情况要卖出
                # 1. 再次低于底线值得时候直接卖出（保底），首要条件
                # 2. 从一个较高的值，比如0.99%回撤到了0.84，回撤超过15%也卖出，说明冲力不行
                if (not context.sell_with_total_float_profit_flag) and (total_float_profit_rate < context.sell_all_lower_limit):
                    context.sell_with_total_float_profit_flag = True
                    log(f"-------->已激活整体盈利卖出条件(追高回落超过底线)，目前设定的整体盈利为：{context.Sell_All_Increase_Rate * 100}%，设置的底线为：{context.sell_all_lower_limit}，当前整体盈利为：{round(context.tfpr * 100, 3)}%")
                    context.record_sell_time = context.now
                    context.record_sell_tfpr = context.tfpr
                elif (not context.sell_with_total_float_profit_flag) and ((total_float_profit_rate - context.sell_all_chase_highest_record) / context.sell_all_chase_highest_record < -0.12):
                    context.sell_with_total_float_profit_flag = True
                    log(f"-------->已激活整体盈利卖出条件(追高回落超过12%)，目前设定的整体盈利为：{context.Sell_All_Increase_Rate * 100}%，记录的最高值为：{round(context.sell_all_chase_highest_record, 3)}，当前整体盈利为：{round(context.tfpr * 100, 3)}%")
                    context.record_sell_time = context.now
                    context.record_sell_tfpr = context.tfpr

        # 更新记录最大的总浮动盈亏（用于在13点35分，也就是设定的全部卖出时段进行log记录）
        # if valid_tfpr_flag and (total_float_profit_rate > context.highest_total_float_profit_info[0]):
        #     context.highest_total_float_profit_info[0] = total_float_profit_rate
        #     context.highest_total_float_profit_info[1] = context.now
        # if valid_tfpr_flag and (total_float_profit_rate < context.lowest_total_float_profit_info[0]):
        #     context.lowest_total_float_profit_info[0] = total_float_profit_rate
        #     context.lowest_total_float_profit_info[1] = context.now

    # 大于整体盈利卖出条件后，直接激活卖出条件（不再重置false）
    # false只在init时有一次，后续只要激活就全部卖出（只激活一次即可）
    # 只激活一次的策略，有可能带来了滑点严重的问题？？因为激活的瞬间，可能整体盈利还在抖动，所以导致一直有0.2%左右的差值？？所以需要改为反复激活，也就是激活后，也要保证后续的每只股卖出时都达到了整体收益？？（需要验证）
    if (not context.sell_with_total_float_profit_flag) and (valid_tfpr_flag) and (context.tfpr > context.Sell_All_Increase_Rate):
        context.sell_with_total_float_profit_flag = True
        log(f"-------->已激活整体盈利卖出条件，目前设定的整体盈利为：{context.Sell_All_Increase_Rate * 100}%，当前整体盈利为：{round(context.tfpr * 100, 3)}%")
        context.record_sell_time = context.now
        context.record_sell_tfpr = context.tfpr

    # 整体止损再满足条件后，激活一次即可
    if (not context.sell_with_total_float_loss_flag) and (valid_tfpr_flag) and (context.tfpr < context.Sell_All_Loss_Rate):
        context.sell_with_total_float_loss_flag = True
        log(f"-------->已激活整体止损卖出条件，目前设定的整体止损为：{context.Sell_All_Loss_Rate * 100}%，当前整体止损为：{round(context.tfpr * 100, 3)}%")
        context.record_sell_time = context.now
        context.record_sell_tfpr = context.tfpr


    # TODO:这里还可以稍微优化下，过时限卖出的flag可以改为全局的，不过这个也不会有什么影响
    now = datetime.datetime.strptime(str(context.now.date()) + str(context.now.hour) + ":" + str(context.now.minute), '%Y-%m-%d%H:%M')
    target_time = datetime.datetime.strptime(str(context.now.date()) + sell_all_time, '%Y-%m-%d%H:%M')
    target_time_for_solo = datetime.datetime.strptime(str(context.now.date()) + context.ids[tick.symbol].sell_with_time, '%Y-%m-%d%H:%M')
    #change mark2
    if (not context.sell_with_time_limit_flag) and (now >= target_time):
        context.sell_with_time_limit_flag = True
        context.record_sell_time = context.now
        context.record_sell_tfpr = context.tfpr

    # 开始判断卖出的条件，一共4个
    # 1.涨幅达标，可以卖出
    # 2.达到13点35分，无论情况，直接全部卖出（要准备换第二天的标的了）
    # 3.强制止损，必须卖出
    # 4.整体盈利到达目标，全部卖出
    # 5.配置直接卖出单个（避免手动平仓）--ID后面加字符s
    # 6.整体止损
    # 7.配置直接清仓所有--fsa标记修改，详见配置文件中的说明
    # 8.配置单个标的卖出的涨幅比例
    # 9.配置单个标的的卖出时间
    # 10.配置单个标的卖出股数（使用方式SN100SN，不需要加s标识）

    sell_condition1 = float_profit_rate > context.Sell_Increase_Rate
    sell_condition2 = context.sell_with_time_limit_flag and False
    sell_condition3 = float_profit_rate < context.Sell_Loss_Limit
    sell_condition4 = context.sell_with_total_float_profit_flag
    # 重置整体盈利卖出标识（必须每只股都重新计算，保证贴合卖出线）
    context.sell_with_total_float_profit_flag = False
    sell_condition5 = context.ids[tick.symbol].force_sell_flag
    sell_condition6 = context.sell_with_total_float_loss_flag
    sell_condition7 = context.force_sell_all_flag
    sell_condition8 = (float_profit_rate > context.ids[tick.symbol].sell_with_rate) if (context.ids[tick.symbol].sell_with_rate > 0) else (float_profit_rate < context.ids[tick.symbol].sell_with_rate)
    sell_condition9 = (now >= target_time_for_solo)
    sell_condition10 = (context.ids[tick.symbol].sell_with_num > 0)

    # 开始判断条件，并尝试卖出
    if sell_condition1 or sell_condition2 or sell_condition3 or sell_condition4 or sell_condition5 or sell_condition6 or sell_condition7 or sell_condition8  or sell_condition9 or sell_condition10:
        msg = f"\n-------->>开始尝试卖出[{tick.symbol}:{name}]，当前持仓量:{curHolding} 现金余额:{round(leftCash, 3)} 当前持仓品种数量:{curHoldTypeNum}"
        msg += f"\n昨收价格:{round(pre_close, 2)} 今开价格:{round(tick.open, 2)} 瞬间价格:{round(tick.price, 2)} 成本价:{pos.vwap}"
        msg += f"\n卖出时盈亏百分比:{round(float_profit_rate * 100.0, 3)}% 是否为高预期{context.ids[tick.symbol].high_expected_flag}"
        msg += f"\n瞬间整体盈利：{round(context.tfpr * 100, 3)}%, Valid：{valid_tfpr_flag}"
        msg += f"\n是否使用市价成交：{context.strategy_info.order_type_sell.Market}"

        msg += f"\n卖出原因："
        if sell_condition1:
            msg += "盈利达标后卖出"
        elif sell_condition2:
            msg += "时间满足标准后卖出"
        elif sell_condition3:
            msg += "止损后卖出"
        elif sell_condition4:
            msg += f"整体盈利达标后卖出"
        elif sell_condition6:
            msg += f"整体止损后卖出"
        elif sell_condition5:
            msg += "配置文件标记强制卖出单个"
        elif sell_condition7:
            msg += "配置文件标记强制清仓所有"
        elif sell_condition8:
            msg += "配置文件单个涨幅达标"
        elif sell_condition9:
            msg += "配置文件指定时间卖出"
        elif sell_condition10:
            msg += "配置文件指定股数卖出"

        msg += f"\n卖出使用买5价格：{curVal5}"
        log(msg)

        # 卖出！！！！！！！！
        # 如果设置了脚本的指定卖出价格，则以指定的价格为准
        list_order = []
        # 判断是否有指定卖出数量，且挂单后，重置数量到0，避免反复卖出指定数量
        if context.ids[tick.symbol].sell_with_num != 0:
            curHolding = int(context.ids[tick.symbol].sell_with_num)
            # 将读取的卖出数量重置到0，否则会连续卖出，这样的话，除非再次刷新（且配置仍然存在），才会继续卖出
            context.ids[tick.symbol].sell_with_num = 0
        if context.ids[tick.symbol].sell_with_price != 0:
            list_order = order_volume(symbol=tick.symbol, volume=curHolding, side=OrderSide_Sell, order_type=OrderType_Limit, position_effect=PositionEffect_Close, price=context.ids[tick.symbol].sell_with_price)
        else:
            list_order = order_volume(symbol=tick.symbol, volume=curHolding, side=OrderSide_Sell, order_type=context.order_type_sell, position_effect=PositionEffect_Close, price=curVal5)
        #print(f"list order:{list_order}")
        
        # 记录order的client id，避免出现之前的重复购买
        # 只有当id在order status的回掉中，出现已成（不是部成）或者被拒绝的时候，才开放再次购买
        # 需要一定的数据格式，记录在context全局变量中，这样不会被擦除
        # 数据信息：{symbol:[list_order]}，直接把list_order一下装进去吧，也不用费事单独拆一些数据了
        context.client_order[tick.symbol] = list_order


def on_bar(context, bars):
    print('---------on_bar---------')
    # print(bars)
    
def output_final_statistics(context):
    
    now = datetime.datetime.strptime(str(context.now.date()) + str(context.now.hour) + ":" + str(context.now.minute), '%Y-%m-%d%H:%M')
    target_time = datetime.datetime.strptime(str(context.now.date()) + "15:30", '%Y-%m-%d%H:%M')
    if (context.test_info) == 99 and (now >= target_time):
        log(f"调试盘终输出：highest_total_fpr:{context.statistics.highest_total_fpr} lowest_total_fpr:{context.statistics.lowest_total_fpr}")
    if (now >= target_time):

        # 在版本1中，输出所有标的当天最高和最低盈利情况
        for k,v in context.statistics.max_min_info_dict.items():
            log(f"[statistics][{k}]最高：[{round(v.max * 100, 3)}%]，最低：[{round(v.min * 100, 3)}%]")

        # 输出精确盈利（就是用(卖出后的mv - 卖出标的的成本mv) / 总成本mv，再减去0.13%的手续费，按理说应该是比较精确的）
        # 注意手续费的0.13%是针对交易额的，并不能固定去减这个值，除非是全部资金，那就可以直接减
        # 这样统计的话，就和总资金没有什么关系了
        # 注意两个结构体并没有什么关系（sell_pos_dict和ids_virtual_sell_info_dict）
        # 主要是因为之前保存文件的关系，没有统一结构体
        cur_mv = 0 # 当天卖出后的票的mv（有可能比持仓成本高或者低）
        vwap_mv = 0 # 当天卖出的票的成本mv（用于和cur_mv一起计算当天的盈利值）
        total_mv = 0 # 用于统计当天所有需要卖出的总mv（不是总资金，总资金一直在变化，不用它）
        for k,v in context.sell_pos_dict.items():
            if k not in context.ids_virtual_sell_target_info_dict.keys():
                continue
            if v[1]:
                cur_mv += (v[0] * v[2])
                vwap_mv += (v[0] * context.ids_virtual_sell_target_info_dict[k].vwap)

            # context.total_market_value_for_all_sell，用这个值也是可以的
            # 不过我看了，sell_pos_dict也是会存文件的，所以这样写也没有问题，不会因为中途关闭出问题
            total_mv += (v[0] * context.ids_virtual_sell_target_info_dict[k].vwap)

        accurate_float_profit = (cur_mv - (cur_mv * 0.0013) - vwap_mv) / (total_mv) if total_mv != 0 else 0
        log(f"\n[statistics][单卖可统计]今日最终精确整体盈利为：{round(accurate_float_profit * 100, 3)}%\n")

        log(f"[statistics]今日最高整体盈利为：{round(context.statistics.highest_total_fpr * 100, 3)}%，出现时间为：{context.statistics.highest_total_fpr_time}")
        context.statistics.highest_total_fpr = 2.0
    if (now >= target_time):
        log(f"[statistics]今日最低整体盈利为：{round(context.statistics.lowest_total_fpr * 100, 3)}%，出现时间为：{context.statistics.lowest_total_fpr_time}")
        context.statistics.lowest_total_fpr = -2.0

    # 版本2统计：止损止盈虚拟统计版本
    if (now >= target_time):
        log(f"[statistics][止]今日最高整体盈利为：{round(context.statistics.highest_total_fpr_limit_ver * 100, 3)}%，出现时间为：{context.statistics.highest_total_fpr_time_limit_ver}")
        context.statistics.highest_total_fpr_limit_ver = 2.0
    if (now >= target_time):
        log(f"[statistics][止]今日最低整体盈利为：{round(context.statistics.lowest_total_fpr_limit_ver * 100, 3)}%，出现时间为：{context.statistics.lowest_total_fpr_time_limit_ver}")
        context.statistics.lowest_total_fpr_limit_ver = -2.0

        log(f"平仓时间[{context.record_sell_time}] 平仓时的瞬间整体盈利[{round(context.record_sell_tfpr * 100, 3)}%]")

        market_value = context.account().cash['market_value'] # 市值，因为之前好像出现了统计错误，这里记录下收盘后的市值，有需要可以核算
        log(f"收盘后的持仓市值为：{market_value}")
        
        # 3点的时候重置整个sell相关的信息，主要是配置文件中的mv改到-1，这个核心值可以控制整个卖出流程
        context.total_market_value_for_all_sell = 0 # 只记录一次就ok
    over_write_mv(-1) # 这里重置为0问题不大，因为市值一般都是两位小数的float，比如1234.68，目前感觉是不会替换到有效id数据的
    over_write_force_sell_all_flag('') # 重置强制卖出标记，避免忘记后，第二天被直接全卖
    auto_generate_sell_list_with_ids_file(context)

def info_statistics(context, tick):
    # 数据统计中的总市值不能再用账号的总市值了，因为都卖完以后，就不会变化了，但我们其实是想监控标的在3点前的最高整体盈利（时间）
    # cur_market_value = context.account().cash['market_value'] # 当前总市值
    # cur_market_value = float('%.2f' % cur_market_value)

    if not context.get_all_sell_price_flag:
        return

    cur_market_value = 0
    cur_market_value_limit_ver = 0
    # 做数据统计时，我们都是使用的标的当前价格，不管标的是否已经卖出（这和sell中计算整体盈利是不一样的）
    # 这样我们才能正确统计它们一天的整体最高盈利是多少，出现在什么时间
    valid_tfpr_flag = True
    debug_count = 0
    for k,v in context.sell_pos_dict.items():
        # 应该跳过sell_pos_dict中持仓为0的情况（比如有时候出问题，手动粘贴sell列表，但是有些并没有成功买入）
        # 这时候再去取vwap的话，就是0，这样就无法正常统计了
        if v[0] == 0:
            continue

        # 一些崩溃或者无效的错误条件判断
        if (k not in context.ids_virtual_sell_target_info_dict.keys()):
            print(f"can not do the statistics, key not exsits [{k}]")
            valid_tfpr_flag = False
            break
        else:
            if (context.ids_virtual_sell_target_info_dict[k].vwap == 0) and (not v[1]):
                print(f"can not do the statistics, vwap invalid when not sold, [{k}]")
                valid_tfpr_flag = False
                break

        # 版本1为自由价格，无止损和止盈
        mv = context.ids_virtual_sell_target_info_dict[k].price * v[0]
        cur_market_value += mv
        if mv == 0:
            log(f"fatal potential error!!! mv should never be 0 here, key:[{k}] price[{context.ids_virtual_sell_target_info_dict[k].price}] holding[{v[0]}] vwap[{context.ids_virtual_sell_target_info_dict[k].vwap}]")
        debug_count += 1
        # 在版本1中（因为没有止损止盈）来更新各个标的的当天最高值和最低值情况
        # 之前有个错误，就是使用了context.ids_virtual_sell_target_info_dict[k].fpr缓存值，这样的话一旦卖出后就不能跟踪了，还是要及时计算
        fpr = (context.ids_virtual_sell_target_info_dict[k].price - context.ids_virtual_sell_target_info_dict[k].vwap) / context.ids_virtual_sell_target_info_dict[k].vwap if context.ids_virtual_sell_target_info_dict[k].vwap != 0 else 0
        if fpr > context.statistics.max_min_info_dict[k].max:
            context.statistics.max_min_info_dict[k].max = fpr
            context.statistics.max_min_info_dict[k].time = context.now
        if (fpr < context.statistics.max_min_info_dict[k].min) and (fpr > -0.25):
            context.statistics.max_min_info_dict[k].min = fpr
            context.statistics.max_min_info_dict[k].time = context.now

        # 版本2为止盈止损版
        mv_limit_ver = 0
        if not context.ids_virtual_sell_target_info_dict[k].sold_flag:
            fpr_limit_ver = (context.ids_virtual_sell_target_info_dict[k].price - context.ids_virtual_sell_target_info_dict[k].vwap) / context.ids_virtual_sell_target_info_dict[k].vwap if context.ids_virtual_sell_target_info_dict[k].vwap != 0 else 0

            price_limit_ver = context.ids_virtual_sell_target_info_dict[k].price
            mv_limit_ver = price_limit_ver * v[0]

            if (fpr_limit_ver > context.Sell_Increase_Rate) and (v[1]):
                price_limit_ver = v[2] # 要使用实际卖出的价格，用设置的百分比计算是不精确的，因为有些开盘就是-4%之类，直接超过了设置
                context.ids_virtual_sell_target_info_dict[k].sold_flag = True
                context.ids_virtual_sell_target_info_dict[k].sold_price = price_limit_ver
                context.ids_virtual_sell_target_info_dict[k].sold_mv = context.ids_virtual_sell_target_info_dict[k].sold_price * v[0]
                mv_limit_ver = context.ids_virtual_sell_target_info_dict[k].sold_mv
            elif (fpr_limit_ver < context.Sell_Loss_Limit) and (v[1]):
                price_limit_ver = v[2]
                context.ids_virtual_sell_target_info_dict[k].sold_flag = True
                context.ids_virtual_sell_target_info_dict[k].sold_price = price_limit_ver
                context.ids_virtual_sell_target_info_dict[k].sold_mv = context.ids_virtual_sell_target_info_dict[k].sold_price * v[0]
                mv_limit_ver = context.ids_virtual_sell_target_info_dict[k].sold_mv
        else:
            mv_limit_ver = context.ids_virtual_sell_target_info_dict[k].sold_mv

        cur_market_value_limit_ver += mv_limit_ver
    save_statistics_info(context)

        
    # 这里的日志输出也行分为版本1和2--------

    # 现在策略AB不能公用一套整体盈利的计算了，B这边要简单一些，就是用目前的总市值除记录的持仓市值就可以
    # B不存在今天没有卖掉的，不用分块考虑，即便有，占比也可以忽略，A的话就不行了，还要考虑去掉今天买入的部分
    # 版本1统计：不含止损止盈
    total_float_profit_rate = ((cur_market_value - context.total_market_value_for_all_sell) / context.total_market_value_for_all_sell) if context.total_market_value_for_all_sell != 0 else 0
    context.statistics.cur_fpr = total_float_profit_rate
    if valid_tfpr_flag and (total_float_profit_rate > context.statistics.highest_total_fpr):
        if (context.statistics.highest_total_fpr < 0.0065) and (total_float_profit_rate > 0.0065):
            log(f"[statistics]突破0.65--------")
        context.statistics.highest_total_fpr = total_float_profit_rate
        context.statistics.highest_total_fpr_time = context.now
        save_statistics_info(context)
        log(f"[statistics]最高:{round(context.statistics.highest_total_fpr * 100, 3)}%, {context.now}")
        #log(f"[debug]cur_mv[{cur_market_value}] total_mv[{context.total_market_value_for_all_sell}] sell_pos_dict_len[{len(context.sell_pos_dict)}] debug_count[{debug_count}]")
    if valid_tfpr_flag and (total_float_profit_rate < context.statistics.lowest_total_fpr):
        context.statistics.lowest_total_fpr = total_float_profit_rate
        context.statistics.lowest_total_fpr_time = context.now
        save_statistics_info(context)
        log(f"[statistics]最低:{round(context.statistics.lowest_total_fpr * 100, 3)}%, {context.now}")
        if context.statistics.lowest_total_fpr < -0.05:
            log(f"[debug]cur_mv[{cur_market_value}] total_mv[{context.total_market_value_for_all_sell}] sell_pos_dict_len[{len(context.sell_pos_dict)}] debug_count[{debug_count}]")

        # 在更新低值的时候，我们可以处理行情很好或者很不好时的特殊处理（测试）
        # 非常不好的情况，求保本，向坐标轴左侧包含
        if total_float_profit_rate < -0.01:
            # [Warning]内部的sell_all_chase_raise_flag不要提取到上层，否则会让一些不需要追高的策略开始追高逻辑的处理（之前改过出现了bug）
            if context.strategy_info.B == 1:
                context.Sell_All_Increase_Rate = 0.002
                context.sell_all_chase_raise_flag = False
            elif context.strategy_info.BA == 1:
                context.Sell_All_Increase_Rate = 0.002
                context.sell_all_chase_raise_flag = False
            # elif context.strategy_info.AA == 1:
            #     context.Sell_All_Increase_Rate = 0.002
            #     context.sell_all_chase_raise_flag = False
        # 非常好的情况，求高收益，向坐标轴右侧包含（注意下面也是右侧包含，所以要小心else的先后顺序）
        elif total_float_profit_rate > 0.003:
            if context.strategy_info.B == 1:
                context.Sell_All_Increase_Rate = 0.01
                context.sell_all_chase_raise_flag = True
            elif context.strategy_info.BA == 1:
                context.Sell_All_Increase_Rate = 0.01
                context.sell_all_chase_raise_flag = True
            # elif context.strategy_info.AA == 1:
            #     context.Sell_All_Increase_Rate = 0.01
            #     context.sell_all_chase_raise_flag = True
        # 比较好的情况，求高收益，向坐标轴右侧包含
        elif total_float_profit_rate > -0.0015:
            if context.strategy_info.B == 1:
                context.Sell_All_Increase_Rate = 0.0075
                context.sell_all_chase_raise_flag = True
            elif context.strategy_info.BA == 1:
                context.Sell_All_Increase_Rate = 0.0075
                context.sell_all_chase_raise_flag = True
            # elif context.strategy_info.AA == 1:
            #     context.Sell_All_Increase_Rate = 0.0075
            #     context.sell_all_chase_raise_flag = True
        # 一般情况，除开特殊情况外，值都应该保持在正常范围（后期根据数据再继续改进）
        else:
            if context.strategy_info.B == 1:
                context.Sell_All_Increase_Rate = 0.0066
                context.sell_all_chase_raise_flag = False
            elif context.strategy_info.BA == 1:
                context.Sell_All_Increase_Rate = 0.0066
                context.sell_all_chase_raise_flag = False
            # elif context.strategy_info.AA == 1:
            #     context.Sell_All_Increase_Rate = 0.0066
            #     context.sell_all_chase_raise_flag = False

    now = datetime.datetime.strptime(str(context.now.date()) + str(context.now.hour) + ":" + str(context.now.minute), '%Y-%m-%d%H:%M')
    target_time = datetime.datetime.strptime(str(context.now.date()) + "15:30", '%Y-%m-%d%H:%M')
    if (context.test_info) == 6 and (now >= target_time):
        log(f"调试盘终输出：highest_total_fpr:{context.statistics.highest_total_fpr} lowest_total_fpr:{context.statistics.lowest_total_fpr}")
    if (now >= target_time) and (context.statistics.highest_total_fpr < 1.0):

        # 在版本1中，输出所有标的当天最高和最低盈利情况
        for k,v in context.statistics.max_min_info_dict.items():
            log(f"[statistics][{k}]最高：[{round(v.max * 100, 3)}%]，最低：[{round(v.min * 100, 3)}%]")

        # 输出精确盈利（就是用(卖出后的mv - 卖出标的的成本mv) / 总成本mv，再减去0.13%的手续费，按理说应该是比较精确的）
        # 注意手续费的0.13%是针对交易额的，并不能固定去减这个值，除非是全部资金，那就可以直接减
        # 这样统计的话，就和总资金没有什么关系了
        # 注意两个结构体并没有什么关系（sell_pos_dict和ids_virtual_sell_info_dict）
        # 主要是因为之前保存文件的关系，没有统一结构体
        cur_mv = 0 # 当天卖出后的票的mv（有可能比持仓成本高或者低）
        vwap_mv = 0 # 当天卖出的票的成本mv（用于和cur_mv一起计算当天的盈利值）
        total_mv = 0 # 用于统计当天所有需要卖出的总mv（不是总资金，总资金一直在变化，不用它）
        for k,v in context.sell_pos_dict.items():
            if k not in context.ids_virtual_sell_target_info_dict.keys():
                continue
            if v[1]:
                cur_mv += (v[0] * v[2])
                vwap_mv += (v[0] * context.ids_virtual_sell_target_info_dict[k].vwap)

            # context.total_market_value_for_all_sell，用这个值也是可以的
            # 不过我看了，sell_pos_dict也是会存文件的，所以这样写也没有问题，不会因为中途关闭出问题
            total_mv += (v[0] * context.ids_virtual_sell_target_info_dict[k].vwap)

        accurate_float_profit = (cur_mv - (cur_mv * 0.0013) - vwap_mv) / (total_mv) if total_mv != 0 else 0
        log(f"\n[statistics][单卖可统计]今日最终精确整体盈利为：{round(accurate_float_profit * 100, 3)}%\n")

        log(f"[statistics]今日最高整体盈利为：{round(context.statistics.highest_total_fpr * 100, 3)}%，出现时间为：{context.statistics.highest_total_fpr_time}")
        context.statistics.highest_total_fpr = 2.0
    if (now >= target_time) and (context.statistics.lowest_total_fpr >= -1.0):
        log(f"[statistics]今日最低整体盈利为：{round(context.statistics.lowest_total_fpr * 100, 3)}%，出现时间为：{context.statistics.lowest_total_fpr_time}")
        context.statistics.lowest_total_fpr = -2.0

    # 版本2统计：止损止盈虚拟统计版本
    total_float_profit_rate_limit_ver = ((cur_market_value_limit_ver - context.total_market_value_for_all_sell) / context.total_market_value_for_all_sell) if context.total_market_value_for_all_sell != 0 else 0
    context.statistics.cur_fpr_limit_ver = total_float_profit_rate_limit_ver
    if valid_tfpr_flag and (total_float_profit_rate_limit_ver > context.statistics.highest_total_fpr_limit_ver):
        if (context.statistics.highest_total_fpr_limit_ver < 0.0065) and (total_float_profit_rate_limit_ver > 0.0065):
            log(f"[statistics][止]突破0.65--------")
        context.statistics.highest_total_fpr_limit_ver = total_float_profit_rate_limit_ver
        context.statistics.highest_total_fpr_time_limit_ver = context.now
        save_statistics_info(context)
        print(f"[statistics][止]最高:{round(context.statistics.highest_total_fpr_limit_ver * 100, 3)}%, {context.now}")
    if valid_tfpr_flag and (total_float_profit_rate_limit_ver < context.statistics.lowest_total_fpr_limit_ver):
        context.statistics.lowest_total_fpr_limit_ver = total_float_profit_rate_limit_ver
        context.statistics.lowest_total_fpr_time_limit_ver = context.now
        save_statistics_info(context)
        print(f"[statistics][止]最低:{round(context.statistics.lowest_total_fpr_limit_ver * 100, 3)}%, {context.now}")

    if (now >= target_time) and (context.statistics.highest_total_fpr_limit_ver <= 1.0):
        log(f"[statistics][止]今日最高整体盈利为：{round(context.statistics.highest_total_fpr_limit_ver * 100, 3)}%，出现时间为：{context.statistics.highest_total_fpr_time_limit_ver}")
        context.statistics.highest_total_fpr_limit_ver = 2.0
    if (now >= target_time) and (context.statistics.lowest_total_fpr_limit_ver >= -1.0):
        log(f"[statistics][止]今日最低整体盈利为：{round(context.statistics.lowest_total_fpr_limit_ver * 100, 3)}%，出现时间为：{context.statistics.lowest_total_fpr_time_limit_ver}")
        context.statistics.lowest_total_fpr_limit_ver = -2.0

        log(f"平仓时间[{context.record_sell_time}] 平仓时的瞬间整体盈利[{round(context.record_sell_tfpr * 100, 3)}%]")

        market_value = context.account().cash['market_value'] # 市值，因为之前好像出现了统计错误，这里记录下收盘后的市值，有需要可以核算
        log(f"收盘后的持仓市值为：{market_value}")
        
        # 3点的时候重置整个sell相关的信息，主要是配置文件中的mv改到-1，这个核心值可以控制整个卖出流程
        context.total_market_value_for_all_sell = 0 # 只记录一次就ok
        over_write_mv(-1) # 这里重置为0问题不大，因为市值一般都是两位小数的float，比如1234.68，目前感觉是不会替换到有效id数据的
        over_write_force_sell_all_flag('') # 重置强制卖出标记，避免忘记后，第二天被直接全卖
        auto_generate_sell_list_with_ids_file(context)

def on_tick(context, tick):
    context.tick_count_for_statistics += 1
    if context.test_info == 1:
        print(f'---------on_tick({tick.symbol})---------')
    # #print(tick)
    # info = get_instruments(symbols = tick.symbol, df = True)
    # msg = f"\n-------->>开始尝试卖出[{info.sec_id[0]}:{info.sec_name[0]}]"
    # print(msg)
    # return
    
    t = time.time()

    if context.ids[tick.symbol].buy_flag == 1:
        if (tick.price > 0) and (tick.symbol in context.ids_buy_target_info_dict.keys()):
            context.ids_buy_target_info_dict[tick.symbol].price = tick.price
            context.ids_buy_target_info_dict[tick.symbol].first_record_flag = True
        # else:
        #     print(f"potential [buy]price error, == 0, [{tick.symbol}]")
    if context.ids[tick.symbol].buy_flag == 0:
        # 为什么这里判断大于0，因为这个订阅很扯，9点30之前有些票会给你发价格0过来，3点以后有些之前有效的票，也会发0给你，所以必须判断
        if tick.price > 0:
            context.ids_virtual_sell_target_info_dict[tick.symbol].price = tick.price
            context.ids_virtual_sell_target_info_dict[tick.symbol].first_record_flag = True
        # else:
        #     print(f"potential [sell]price error, == 0, [{tick.symbol}]")

        if context.ids_virtual_sell_target_info_dict[tick.symbol].vwap == 0:
            pos = context.account().position(symbol = tick.symbol, side = OrderSide_Buy)
            if pos and pos.vwap > 0:
                context.ids_virtual_sell_target_info_dict[tick.symbol].vwap = pos.vwap

    # 根据设置的tick handle frequence来跳过tick的处理
    context.ids[tick.symbol].tick_cur_count += 1
    if context.ids[tick.symbol].tick_cur_count < context.ids[tick.symbol].tick_handle_frequence:
        return
    else:
        context.ids[tick.symbol].tick_cur_count = 0

    # 检测是否已经记录所有的buy或者sell的price，这样后续流程就不用再浪费性能检测了，该过程激活一次就ok了（要注意refresh中重置flag，因为刷新可能ids变更）
    if (not context.get_all_buy_price_flag):
        record_all = True
        for k,v in context.ids_buy_target_info_dict.items():
            if v.price == 0:
                record_all = False
                break
        if record_all:
            context.get_all_buy_price_flag = True

    invalid_sell_symbol = ""
    if (not context.get_all_sell_price_flag):
        record_all = True
        for k,v in context.ids_virtual_sell_target_info_dict.items():
            # 这里用过first_record_flag比较，但是不行，验证发现price第一次记录了也很可能是0，原因不明
            # 使用还是必须要用price，否则就会出现之前刚刚开盘统计数据最低就到-4，-5，甚至更低，就是因为好几只票，明明有价格，但是第一次进来给的0
            if v.price == 0:
                invalid_sell_symbol = k
                record_all = False
                break
        if record_all:
            context.get_all_sell_price_flag = True

    # 检测tick_count_for_statistics是否在收盘后出现了，次数累加不够的情况？？
    if (context.test_info) == 6:
        log(f"目前tick_count_for_statistics:{context.tick_count_for_statistics} len of ids:{len(context.ids)}")

    # 更新缓存价格，在外面更新，里面return的条件太多了，这样更新的价格，statistics也可以用
    if context.tick_count_for_statistics >= len(context.ids):
        # 检测未结委托，超时的话，无论原因都应该撤单重新操作
        check_unfinished_orders(context, tick)
        
        # 调试信息：有时候会偶尔出现不输出盘终总结的情况
        if (context.test_info) == 6:
            now = datetime.datetime.strptime(str(context.now.date()) + str(context.now.hour) + ":" + str(context.now.minute), '%Y-%m-%d%H:%M')
            target_time = datetime.datetime.strptime(str(context.now.date()) + "15:30", '%Y-%m-%d%H:%M')
            if now >= target_time:
                log(f"已到盘终总结输出测试点01，且时间满足")
            else:
                log(f"已到盘终总结输出测试点01，但时间为满足条件")


        info_statistics(context, tick)
        context.tick_count_for_statistics = 0
        if invalid_sell_symbol != "":
            print(f"卖出列表中存在无法获取price的情况[{invalid_sell_symbol}]，等待一段时间（30s）后仍然无法获取到的，需要从配置列表中删除，删除后手动重置配置文件中的mv到-1，然后再刷新")
        if context.test_info == 1:
            print(f"trade logic cost time with count limit------: {time.time() - t:.4f} s")
        # print(f"trade logic cost time with count limit------: {time.time() - t:.4f} s")

    now = datetime.datetime.strptime(str(context.now.date()) + str(context.now.hour) + ":" + str(context.now.minute), '%Y-%m-%d%H:%M')
    target_time = datetime.datetime.strptime(str(context.now.date()) + context.start_operation_time, '%Y-%m-%d%H:%M')
    if (now < target_time):
        # 没有到9点30，先不要开始操作（目前原因，是我统计剩余ids_buy长度，有些股我看了竞价就可以买，但是不会成功，会被我超时取消掉）
        # 现在先简单处理，9点30前都不操作，后面有需要再调整
        print(f"not reach the begin time [{context.start_operation_time}]......")
        return

    if context.get_all_buy_price_flag:
        context.tick_count_for_buy += 1
        if (context.tick_count_for_buy > (len(context.ids) * context.tick_count_limit_rate_for_buy)):
            context.tick_count_for_buy_ok = True
        else:
            context.tick_count_for_buy_ok = False
    if context.get_all_sell_price_flag:
        context.tick_count_for_sell += 1
        if (context.tick_count_for_sell > (len(context.ids) * context.tick_count_limit_rate_for_sell)):
            context.tick_count_for_sell_ok = True
        else:
            context.tick_count_for_sell_ok = False

    # 根据不同策略尝试买卖--------
    # 策略A（存在滚动买入和卖出，以及买入和卖出的单独条件设置）
    if (context.strategy_info.A == 1) or (context.strategy_info.A1 == 1):
        if (context.ids[tick.symbol].buy_flag == 1) and (context.get_all_buy_price_flag):            
            try_buy_strategyA(context, tick)
        if (context.ids[tick.symbol].buy_flag == 0) and (context.get_all_sell_price_flag):            
            try_sell_strategyA(context, tick)
    # 策略B（对冲整体买卖策略，不存在单只处理）
    elif (context.strategy_info.B == 1) or (context.strategy_info.BA == 1) or (context.strategy_info.AA == 1):
        if (context.ids[tick.symbol].buy_flag == 1) and (context.get_all_buy_price_flag):
            try_buy_strategyB(context, tick)
        if (context.ids[tick.symbol].buy_flag == 0) and (context.get_all_sell_price_flag):
            try_sell_strategyB(context, tick)
    # 策略B改版1（存在滚动买入和卖出，存在单只操作）
    elif context.strategy_info.B1 == 1:
        if (context.ids[tick.symbol].buy_flag == 1) and (context.get_all_buy_price_flag):
            try_buy_strategyB1(context, tick)
        if (context.ids[tick.symbol].buy_flag == 0) and (context.get_all_sell_price_flag):
            try_sell_strategyB1(context, tick)
    else:
        print(f"[error] enter trade strategy failed, this should never happen")

    if context.get_all_buy_price_flag:
        if (context.tick_count_for_buy > (len(context.ids) * context.tick_count_limit_rate_for_buy)):
            context.tick_count_for_buy = 0
    if context.get_all_sell_price_flag:
        if (context.tick_count_for_sell > (len(context.ids) * context.tick_count_limit_rate_for_sell)):
            context.tick_count_for_sell = 0 # 重置tick count

    if context.test_info == 1:
        print(f"trade logic cost time: {time.time() - t:.4f} s")

    #info = get_instruments(symbols = tick.symbol, df = True)
    # id就是不带前缀（XXSE.）的6位代码
    #print(f"代码{info.symbol} 名称{info.sec_name} id{info.sec_id}")

    # ！！！下面是典型的错误代码，tick已经是订阅后激活的了（是回调函数，订阅以后都有回调），tick的信息中有我所有订阅的股票，不应该在这里循环自己去调用
    # 每只股票会有单独的tick被触发（订阅后）
    '''
    for id in context.ids:
        try_buy(context, tick)
    '''

# 检测委托超时函数--------
def check_unfinished_orders(context, tick):
    unfinished_orders = get_unfinished_orders()

    for order in unfinished_orders:
        # 没有设置脚本的指定买入或者卖出价格的时候，我们才自动取消订单，否则就挂着（这种情况需要人工取消订单）
        if (context.ids[order.symbol].sell_with_price == 0 and context.ids[order.symbol].buy_with_price == 0) and ((context.now - order.created_at).seconds > order_overtime):
            if order.symbol in context.ids_virtual_sell_target_info_dict.keys():
                log(f"{order.symbol}:{context.ids_virtual_sell_target_info_dict[order.symbol].name} 委托已经超时！！开始取消订单--------")
            elif order.symbol in context.ids_buy_target_info_dict.keys():
                log(f"{order.symbol}:{context.ids_buy_target_info_dict[order.symbol].name} 委托已经超时！！开始取消订单--------")
            else:
                log(f"{order.symbol} 委托已经超时！！开始取消订单--------")

            # 取消委托订单
            order_cancel(order)

            # 撤单后，删除本地记录订单，以便继续操作
            # 不能再这里删除记录，因为取消成功后，会在order里面接收到canceled的信息，那时候再删除才是对的
            # if order.symbol in context.client_order.keys():
            #     del context.client_order[order.symbol]

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
    if order.symbol in context.ids_virtual_sell_target_info_dict.keys():
        name = context.ids_virtual_sell_target_info_dict[order.symbol].name
    elif order.symbol in context.ids_buy_target_info_dict.keys():
        name = context.ids_buy_target_info_dict[order.symbol].name


    if order.ord_rej_reason != 0:
        log(f"{order.symbol}:{name} 委托已被拒绝！具体原因如下：{order.ord_rej_reason_detail}")
        # 被拒绝后，可以消除订单的记录
        if order.symbol in context.client_order.keys():
            del context.client_order[order.symbol]

    # 订单全部成交的话（status == 3），可以消除订单记录
    if order.status == OrderStatus_Filled:
        log(f'{order.symbol}:{name} 所有委托订单已成，成交均价为：{round(order.filled_vwap, 3)}，已成量：{order.filled_volume}')
        if order.symbol in context.client_order.keys():
            del context.client_order[order.symbol]

        #print(f"-------------------test order side:{order.side}")
        # 更新买卖方向的相关信息
        if order.side == OrderSide_Sell:
            update_sell_position_info(context, order.symbol, True, order.filled_vwap)
        elif order.side == OrderSide_Buy:
            update_buy_info(context, order.symbol, order.filled_vwap)
            context.ids[order.symbol].already_buy_in_flag = True
            # 通过记录买入列表，来达到限制购买数量的目的（重启脚本后无效：未保存到文件）
            # 根据不保存文件还好点，不然临时要增加就不太好操作？？
            if order.symbol not in context.already_buy_in_keys:
                context.already_buy_in_keys.append(order.symbol)

            # 更新已买入的仓位数量：为了解决pos中取出的仓位小几率刷新不及时的问题
            # 全部成交的情况下，不需要用到partial的值，直接加这里的值就可以
            context.ids_buy_target_info_dict[order.symbol].total_holding += order.filled_volume
            context.ids_buy_target_info_dict[order.symbol].partial_holding = 0
            log(f"{order.symbol}:{name}目前总持仓更新为：{context.ids_buy_target_info_dict[order.symbol].total_holding}")
            
            # 只买入一次，这里重置buy_with_num为0，防止连续买入指定数量（除非后续刷新，且配置仍然存在）
            if (context.ids[order.symbol].buy_with_num != 0):
                context.ids[order.symbol].buy_with_num = 0
                context.ids[order.symbol].buy_with_num_handled_flag = True
            

    # [MAYBE TODO]订单部分成交的话（status == 2），暂不消除订单记录--------
    # 目前的观察结果：这种部成的委托，最后都进入了全部完成中，可以暂时不管（但是不能排除有极个别其他情况，继续观察）
    if order.status == OrderStatus_PartiallyFilled:
        log(f'{order.symbol}:{name} 订单部分完成~~~~~~成交均价为：{round(order.filled_vwap, 3)}，已成量：{order.filled_volume}')

        if order.side == OrderSide_Buy:
            context.ids[order.symbol].already_buy_in_flag = True
            if order.symbol not in context.already_buy_in_keys:
                context.already_buy_in_keys.append(order.symbol)

            # 更新已买入的仓位数量：为了解决pos中取出的仓位小几率刷新不及时的问题
            # 部成的情况下，不能直接记录到总数，我们只需要一直更新（注意这里不是加总）部成值即可，直到撤销订单激活的时候，才加总
            context.ids_buy_target_info_dict[order.symbol].partial_holding = order.filled_volume

    # 订单已撤销的话（status == 5），可以消除订单记录
    if order.status == OrderStatus_Canceled:
        log(f'{order.symbol}:{name} 订单已撤销')
        if order.symbol in context.client_order.keys():
            del context.client_order[order.symbol]

        # 撤销订单的时候，应该把已经完成的partial加总到总持仓里面，并重置partial到0（避免下次撤销时，并没有partial完成的情况下，依然有非0值）
        if (order.side == OrderSide_Buy) and (order.symbol in context.ids_buy_target_info_dict.keys()):
            context.ids_buy_target_info_dict[order.symbol].total_holding += context.ids_buy_target_info_dict[order.symbol].partial_holding 
            context.ids_buy_target_info_dict[order.symbol].partial_holding = 0
            log(f"{order.symbol}:{name}目前总持仓更新为：{context.ids_buy_target_info_dict[order.symbol].total_holding}")

    # 订单已过期的话（status == 12），可以消除订单记录
    if order.status == OrderStatus_Expired:
        log(f'{order.symbol}:{name} 订单已过期')
        if order.symbol in context.client_order.keys():
            del context.client_order[order.symbol]

# 委托执行回报事件
# 响应委托被执行事件，委托成交或者撤单拒绝后被触发。
# 注意：
# 1、交易账户重连后，会重新推送一遍交易账户登录成功后查询回来的所有执行回报
# 2、撤单拒绝后，会推送撤单拒绝执行回报，可以根据exec_id区分
def on_execution_report(context, execrpt):
    print('--------on_execution_report')
    #print(execrpt)

# 交易账户状态更新事件
# 响应交易账户状态更新事件，交易账户状态变化时被触发。
# 交易账户状态对象，仅响应 已连接，已登录，已断开 和 错误 事件
def on_account_status(context, account):
    #print('--------on_account_status')
    #print(account)
    
    if (account['status']['state'] != 3):
        log(f'账号连接异常！！！目前没有任何处理')

    if (account['status']['error']['code'] != 0):
        log(f"发生账号错误：{account['status']['error']['code']}！！！目前没有任何处理")

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
        '''
    run(strategy_id='1457c400-f485-11ed-a1a9-005056bc063c',
        filename='main.py',
        #mode=MODE_BACKTEST,
        mode=MODE_LIVE,
        token='4f0478a8560615e1a0049e2e2565955620b3ec02',
        backtest_start_time='2020-11-01 08:00:00',
        backtest_end_time='2020-11-10 16:00:00',
        backtest_adjust=ADJUST_PREV,
        backtest_initial_cash=10000000,
        backtest_commission_ratio=0.0001,
        backtest_slippage_ratio=0.0001)
