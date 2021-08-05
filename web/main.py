import os

from flask import Flask, request, json, render_template

import settings
from functions import system_exec_command
from rmt.qbittorrent import login_qbittorrent
from scheduler.autoremove_torrents import run_autoremovetorrents
from scheduler.hot_trailer import run_hottrailers
from scheduler.icloudpd import run_icloudpd
from scheduler.pt_signin import run_ptsignin
from scheduler.qb_transfer import run_qbtransfer
from scheduler.smzdm_signin import run_smzdmsignin
from scheduler.unicom_signin import run_unicomsignin
from web.emby.discord import report_to_discord
from web.emby.emby_event import EmbyEvent

import log
from message.send import sendmsg


def create_app():
    app = Flask(__name__)
    app.config['JSON_AS_ASCII'] = False
    logger = log.Logger("webhook").logger

    # Emby消息通知
    @app.route('/emby', methods=['POST', 'GET'])
    def emby():
        if request.method == 'POST':
            request_json = json.loads(request.form.get('data', {}))
        else:
            server_name = request.args.get("server_name")
            user_name = request.args.get("user_name")
            device_name = request.args.get("device_name")
            ip = request.args.get("ip")
            flag = request.args.get("flag")
            request_json = {"Event": "user.login",
                            "User": {"user_name": user_name, "device_name": device_name, "device_ip": ip},
                            "Server": {"server_name": server_name},
                            "Status": flag
                            }
        logger.debug("输入报文：" + str(request_json))
        event = EmbyEvent(request_json)
        report_to_discord(event)
        return 'Success'

    # 主页面
    @app.route('/', methods=['POST', 'GET'])
    def main():
        # 读取qBittorrent列表
        qbt = login_qbittorrent()
        torrents = qbt.torrents_info()
        trans_qbpath = settings.get("rmt.rmt_qbpath")
        trans_containerpath = settings.get("rmt.rmt_containerpath")
        path_list = []
        hash_list = []
        for torrent in torrents:
            logger.info(torrent.name + "：" + torrent.state)
            if torrent.state == "uploading" or torrent.state == "stalledUP":
                true_path = torrent.content_path.replace(str(trans_qbpath), str(trans_containerpath))
                path_list.append(true_path)
                hash_list.append(torrent.name + "|" + torrent.hash)
        qbt.auth_log_out()
        # 读取配置文件
        cfg = open(settings.get_config_path(), mode="r", encoding="utf8")
        config_str = cfg.read()
        cfg.close()
        # 读取定时服务配置
        tim_autoremovetorrents = settings.get("scheduler.autoremovetorrents_interval")
        tim_qbtransfer = settings.get("scheduler.qbtransfer_interval")
        tim_icloudpd = settings.get("scheduler.icloudpd_interval")
        tim_hottrailers = settings.get("scheduler.hottrailer_cron")
        tim_ptsignin = settings.get("scheduler.ptsignin_cron")
        tim_smzdmsignin = settings.get("scheduler.smzdmsignin_cron")
        tim_unicomsignin = settings.get("scheduler.unicomsignin_cron")

        return render_template("main.html",
                               page="rmt",
                               rmt_paths=path_list,
                               rmt_hashs=hash_list,
                               config_str=config_str,
                               tim_autoremovetorrents=tim_autoremovetorrents,
                               tim_qbtransfer=tim_qbtransfer,
                               tim_icloudpd=tim_icloudpd,
                               tim_hottrailers=tim_hottrailers,
                               tim_ptsignin=tim_ptsignin,
                               tim_smzdmsignin=tim_smzdmsignin,
                               tim_unicomsignin=tim_unicomsignin
                               )

    # 事件响应
    @app.route('/do', methods=['POST'])
    def do():
        cmd = request.form.get("cmd")
        data = json.loads(request.form.get("data"))
        if cmd:
            if cmd == "rmt":
                p_name = data["name"]
                p_path = data["path"]
                p_hash = data["hash"]
                cmdstr = "bash /nas-tools/bin/rmt.sh" + " \"" + p_name + "\" \"" + p_path + "\" \"" + p_hash + "\""
                logger.info("执行命令：" + cmdstr)
                std_err, std_out = system_exec_command(cmdstr, 1800)
                # 读取qBittorrent列表
                qbt = login_qbittorrent()
                torrents = qbt.torrents_info()
                trans_qbpath = settings.get("rmt.rmt_qbpath")
                trans_containerpath = settings.get("rmt.rmt_containerpath")
                path_list = []
                hash_list = []
                for torrent in torrents:
                    logger.info(torrent.name + "：" + torrent.state)
                    if torrent.state == "uploading" or torrent.state == "stalledUP":
                        true_path = torrent.content_path.replace(str(trans_qbpath), str(trans_containerpath))
                        path_list.append(true_path)
                        hash_list.append(torrent.name + "|" + torrent.hash)
                qbt.auth_log_out()
                return {"rmt_stderr": std_err, "rmt_stdout": std_out, "rmt_paths": path_list, "rmt_hashs": hash_list}

            if cmd == "msg":
                title = data["title"]
                text = data["text"]
                retcode, retmsg = "", ""
                if title or text:
                    retcode, retmsg = sendmsg(title, text)
                return {"msg_code": retcode, "msg_msg": retmsg}

            if cmd == "set":
                editer_str = data["editer_str"]
                if editer_str:
                    cfg = open(settings.get_config_path(), mode="w", encoding="utf8")
                    cfg.write(editer_str)
                    cfg.flush()
                    cfg.close()
                # 重新读取配置文件
                cfg = open(settings.get_config_path(), mode="r", encoding="utf8")
                config_str = cfg.read()
                cfg.close()
                return {"config_str": config_str}

            if cmd == "sch":
                sch_item = data["item"]
                if sch_item == "sch_btn_autoremovetorrents":
                    run_autoremovetorrents()
                if sch_item == "sch_btn_qbtransfer":
                    run_qbtransfer()
                if sch_item == "sch_btn_icloudpd":
                    run_icloudpd()
                if sch_item == "sch_btn_hottrailers":
                    run_hottrailers()
                if sch_item == "sch_btn_ptsignin":
                    run_ptsignin()
                if sch_item == "sch_btn_smzdmsignin":
                    run_smzdmsignin()
                if sch_item == "sch_btn_unicomsignin":
                    run_unicomsignin()
                return {"retmsg": "执行完成！", "item": sch_item}

    return app