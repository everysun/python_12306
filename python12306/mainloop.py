import datetime
import random
import time

from global_data.session import LOGIN_SESSION
from logic.login.checkuser import OnlineChecker, OnlineCheckerTool
from logic.login.login import NormalLogin
from logic.query.query import Query
from config import Config
from logic.submit.fastsubmit import FastSubmitDcOrder
from logic.submit.submit import NormalSubmitDcOrder
from utils.send_email import send_email
from utils.log import Log
from utils.data_loader import LocalSimpleCache


class Schedule(object):
    retry_login_time = Config.basic_config.retry_login_time
    login_status = False
    order_id = ''

    def login(self):
        count = 0
        while self.retry_login_time > count:
            l = NormalLogin()
            Log.v("正在为您登录")
            status, msg = l.login()
            if not status:
                count += 1
                Log.v("登录失败, 重试{0}次".format(count))
                continue
            else:
                Log.v("登录成功")
                break
        if not self.retry_login_time <= count:
            Log.v("重试次数已经超过设置")
            return False
        return True

    def online_checker(self):
        # 两分钟检测一次
        flag =  OnlineCheckerTool.should_check_online(datetime.datetime.now())
        if flag:
            status, msg = OnlineCheckerTool.checker()
            OnlineCheckerTool.update_check_time()
            if not status:
                Log.v("用户登录失效, 正在为您重试登录")
                l = self.login()
                if not l:
                    return False, "重试登录失败"
            else:
                return status, msg
        else:
            status, msg = True, "用户状态检测:未到检测时间"
        return status, msg

    def run(self):
        self.login()
        if not Config.auto_code_enable:
            Log.v("未开启自动打码功能, 不检测用户登录状态")
        Log.v("正在查询车次余票信息")
        count = 0
        while True:
            if Config.auto_code_enable:
                status, msg = self.online_checker()
                Log.v(msg)
            count += 1
            n = datetime.datetime.now()
            q = Query()
            data = q.filter()
            if not data:
                Log.v("满足条件的车次暂无余票,正在重新查询")
            for v in data:
                print("\t\t\t当前座位席别 {}".format(v[0].name))
                q.pretty_output(v[1])
            delta_time = datetime.datetime.now() - n
            try:
                delta = Config.basic_config.query_left_ticket_time - 1 + random.random()
            except AttributeError:
                delta = 4 + random.random()
            time.sleep(delta)
            Log.v("查询第 {0} 次, 当次查询时间间隔为 {1} 秒, 查询请求处理时间 {2} 秒".format(
                count, delta, delta_time.total_seconds()))
            for v in data:
                if Config.basic_config.fast_submit:
                    submit = FastSubmitDcOrder(v[1], v[0])
                else:
                    submit = NormalSubmitDcOrder(v[1], v[0])
                f = submit.run()
                if not f:
                    continue
                else:
                    self.order_id = submit.order_id
                    break
            if self.order_id:
                break

        Log.v("抢票成功，如果有配置邮箱，稍后会收到邮件通知")
        # 抢票成功发邮件信息
        send_email(2, **{"order_no": self.order_id})

if __name__ == "__main__":
    instance = Schedule()
    instance.run()
