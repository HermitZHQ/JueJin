# coding=utf-8
from __future__ import print_function, absolute_import
from gm.api import *
import socket

def on_tick(context):
    pass


# 策略中必须有init方法
def init(context):
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
    run(strategy_id='c6304d41-0534-11ef-b80b-00ff2b50aff6',
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


def start_tcp_server(server_ip, server_port):
    # 创建一个socket对象
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # 绑定IP地址和端口号
    server_socket.bind((server_ip, server_port))

    # 开始监听连接
    server_socket.listen(1)

    print(f"Server is listening on {server_ip}:{server_port}...")

    while True:
        # 接受新的连接
        client_socket, client_address = server_socket.accept()
        print(f"New connection from: {client_address}")

        try:
            # 接收客户端发送的数据
            data = client_socket.recv(1024)
            if data:
                # 发送响应到客户端
                client_socket.sendall(data)  # 或者发送其他自定义的响应
                print(f"Received from client: {data.decode()}")
                print(f"Sent back to client: {data.decode()}")
            else:
                print("No data received from client.")

        except ConnectionResetError:
            print("Client disconnected unexpectedly.")

        finally:
            # 关闭客户端socket连接
            client_socket.close()

# 服务器IP地址和端口号
server_ip = "0.0.0.0"
server_port = 12345

# 开始运行TCP服务器
start_tcp_server(server_ip, server_port)