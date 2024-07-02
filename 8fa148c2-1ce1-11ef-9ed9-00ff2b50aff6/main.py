# coding=utf-8
from __future__ import print_function, absolute_import
from gm.api import *

import time
import datetime
import math

# 策略中必须有init方法
def init(context):
    context.count = 0
    context.update_time = 0
    subscribe(symbols='SHSE.000001', frequency='tick', count=1, unsubscribe_previous=True)
    pass

def on_tick(context, tick):
    if context.update_time == 0:
        context.update_time = time.time()
        
    context.count += 1
    
    print(f"目前更新次数:[{context.count}] 初始化总计耗时:[{time.time() - context.update_time:.4f}]s 平均每次耗时:[{(time.time() - context.update_time) / context.count:.4f}]")

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
    run(strategy_id='8fa148c2-1ce1-11ef-9ed9-00ff2b50aff6',
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

