import time

import settings
import log
from functions import get_location, mysql_exec_sql
from message.send import sendmsg

logger = log.Logger("webhook").logger
PLAY_LIST = []


def report_to_discord(event):
    # Create message
    message = None
    message_flag = True

    # System
    logger.info('事件类型：' + event.category)
    if event.category == 'system':
        if event.action == 'webhooktest':
            message = '【Emby】Test'
    # Playback
    elif event.category == 'playback':
        ignore_list = eval(settings.get("webhook.webhook_ignore"))
        if event.user_name in ignore_list or \
                event.device_name in ignore_list or \
                (event.user_name + ':' + event.device_name) in ignore_list:
            logger.info('忽略的用户或设备，不通知：' + event.user_name + ':' + event.device_name)
            message_flag = False
        list_id = event.user_name + event.item_name + event.ip + event.device_name + event.client
        if event.action == 'start':
            message = '【Emby】用户 {} 开始播放 {}'.format(event.user_name, event.item_name)
            if list_id not in PLAY_LIST:
                PLAY_LIST.append(list_id)
        elif event.action == 'stop':
            if list_id in PLAY_LIST:
                message = '【Emby】用户 {} 停止播放 {}'.format(event.user_name, event.item_name)
                PLAY_LIST.remove(list_id)
            else:
                message_flag = False
                logger.info('重复Stop通知，丢弃：' + list_id)
    elif event.category == 'user':
        if event.action == 'login':
            if event.status.upper() == 'F':
                message = '【Emby】用户 {} 登录 {} 失败！'.format(event.user_name, event.server_name)
            else:
                message = '【Emby】用户 {} 登录了 {}'.format(event.user_name, event.server_name)
    else:
        message_flag = False

    if not message:
        message_flag = False

    if message_flag:
        address = get_location(event.ip)
        desp = ""
        if event.category == 'playback':
            desp = '设备：' + event.device_name \
                   + '\n\n客户端：' + event.client \
                   + '\n\nIP地址：' + event.ip \
                   + '\n\n位置：' + address \
                   + '\n\n时间：' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
        elif event.category == 'user':
            if event.action == 'login':
                desp = '设备：' + event.device_name \
                   + '\n\nIP地址：' + event.ip \
                   + '\n\n位置：' + address \
                   + '\n\n时间：' + time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
        # Report Message
        sendmsg(message, desp)

        # 登记数据库
        sql = ""
        if event.category == 'playback':
            sql = "INSERT INTO emby_playback_log \
                   (USER, DEVICE, CLIENT, IP, ADDRESS, TIME, MEDIA, OP) \
                   VALUES ('%s', '%s', '%s', '%s', '%s',now(), '%s', '%s')" % \
                  (event.user_name, event.device_name, event.client, event.ip, address, event.item_name, event.action)
        elif event.category == 'user':
            if event.action == 'login':
                sql = "INSERT INTO emby_playback_log \
                                   (USER, DEVICE, CLIENT, IP, ADDRESS, TIME, MEDIA, OP) \
                                   VALUES ('%s', '%s', '', '%s', '%s',now(), '', '%s')" % \
                      (event.user_name, event.device_name, event.ip, address, event.action)
        if sql:
            if mysql_exec_sql(sql):
                logger.info("数据库登记成功！")
            else:
                logger.info("数据库登记失败：" + sql)