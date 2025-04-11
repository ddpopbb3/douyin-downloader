#!/usr/bin/env python
# -*- coding: utf-8 -*-


import re
import requests
import json
import time
import copy
import random
# from tenacity import retry, stop_after_attempt, wait_exponential
from typing import Tuple, Optional
from requests.exceptions import RequestException
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.console import Console

from apiproxy.douyin import douyin_headers
from apiproxy.douyin.urls import Urls
from apiproxy.douyin.result import Result
from apiproxy.douyin.database import DataBase
from apiproxy.common import utils
import logging

# 创建全局console实例
console = Console()

# 创建logger实例
logger = logging.getLogger("douyin_downloader")

class Douyin(object):

    def __init__(self, database=False):
        self.urls = Urls()
        self.result = Result()
        self.database = database
        if database:
            self.db = DataBase()
        # 用于设置重复请求某个接口的最大时间
        self.timeout = 10
        self.console = Console()  # 也可以在实例中创建console

    # 从分享链接中提取网址
    def getShareLink(self, string):
        # findall() 查找匹配正则表达式的字符串
        return re.findall('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', string)[0]

    # 得到 作品id 或者 用户id
    # 传入 url 支持 https://www.iesdouyin.com 与 https://v.douyin.com
    def getKey(self, url: str) -> Tuple[Optional[str], Optional[str]]:
        """获取资源标识
        Args:
            url: 抖音分享链接或网页URL
        Returns:
            (资源类型, 资源ID)
        """
        key = None
        key_type = None

        try:
            r = requests.get(url=url, headers=douyin_headers)
        except Exception as e:
            print('[  错误  ]:输入链接有误！\r')
            return key_type, key

        # 抖音把图集更新为note
        # 作品 第一步解析出来的链接是share/video/{aweme_id}
        # https://www.iesdouyin.com/share/video/7037827546599263488/?region=CN&mid=6939809470193126152&u_code=j8a5173b&did=MS4wLjABAAAA1DICF9-A9M_CiGqAJZdsnig5TInVeIyPdc2QQdGrq58xUgD2w6BqCHovtqdIDs2i&iid=MS4wLjABAAAAomGWi4n2T0H9Ab9x96cUZoJXaILk4qXOJlJMZFiK6b_aJbuHkjN_f0mBzfy91DX1&with_sec_did=1&titleType=title&schema_type=37&from_ssr=1&utm_source=copy&utm_campaign=client_share&utm_medium=android&app=aweme
        # 用户 第一步解析出来的链接是share/user/{sec_uid}
        # https://www.iesdouyin.com/share/user/MS4wLjABAAAA06y3Ctu8QmuefqvUSU7vr0c_ZQnCqB0eaglgkelLTek?did=MS4wLjABAAAA1DICF9-A9M_CiGqAJZdsnig5TInVeIyPdc2QQdGrq58xUgD2w6BqCHovtqdIDs2i&iid=MS4wLjABAAAAomGWi4n2T0H9Ab9x96cUZoJXaILk4qXOJlJMZFiK6b_aJbuHkjN_f0mBzfy91DX1&with_sec_did=1&sec_uid=MS4wLjABAAAA06y3Ctu8QmuefqvUSU7vr0c_ZQnCqB0eaglgkelLTek&from_ssr=1&u_code=j8a5173b&timestamp=1674540164&ecom_share_track_params=%7B%22is_ec_shopping%22%3A%221%22%2C%22secuid%22%3A%22MS4wLjABAAAA-jD2lukp--I21BF8VQsmYUqJDbj3FmU-kGQTHl2y1Cw%22%2C%22enter_from%22%3A%22others_homepage%22%2C%22share_previous_page%22%3A%22others_homepage%22%7D&utm_source=copy&utm_campaign=client_share&utm_medium=android&app=aweme
        # 合集
        # https://www.douyin.com/collection/7093490319085307918
        urlstr = str(r.request.path_url)

        if "/user/" in urlstr:
            # 获取用户 sec_uid
            if '?' in r.request.path_url:
                for one in re.finditer(r'user\/([\d\D]*)([?])', str(r.request.path_url)):
                    key = one.group(1)
            else:
                for one in re.finditer(r'user\/([\d\D]*)', str(r.request.path_url)):
                    key = one.group(1)
            key_type = "user"
        elif "/video/" in urlstr:
            # 获取作品 aweme_id
            key = re.findall('video/(\d+)?', urlstr)[0]
            key_type = "aweme"
        elif "/note/" in urlstr:
            # 获取note aweme_id
            key = re.findall('note/(\d+)?', urlstr)[0]
            key_type = "aweme"
        elif "/mix/detail/" in urlstr:
            # 获取合集 id
            key = re.findall('/mix/detail/(\d+)?', urlstr)[0]
            key_type = "mix"
        elif "/collection/" in urlstr:
            # 获取合集 id
            key = re.findall('/collection/(\d+)?', urlstr)[0]
            key_type = "mix"
        elif "/music/" in urlstr:
            # 获取原声 id
            key = re.findall('music/(\d+)?', urlstr)[0]
            key_type = "music"
        elif "/webcast/reflow/" in urlstr:
            key1 = re.findall('reflow/(\d+)?', urlstr)[0]
            url = self.urls.LIVE2 + utils.getXbogus(
                f'live_id=1&room_id={key1}&app_id=1128')
            res = requests.get(url, headers=douyin_headers)
            resjson = json.loads(res.text)
            key = resjson['data']['room']['owner']['web_rid']
            key_type = "live"
        elif "live.douyin.com" in r.url:
            key = r.url.replace('https://live.douyin.com/', '')
            key_type = "live"

        if key is None or key_type is None:
            print('[  错误  ]:输入链接有误！无法获取 id\r')
            return key_type, key

        return key_type, key

    # 暂时注释掉装饰器
    # @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def getAwemeInfo(self, aweme_id: str) -> dict:
        """获取作品信息（带重试机制）"""
        retries = 10  # 增加重试次数
        for attempt in range(retries):
            try:
                logger.info(f'[  提示  ]:正在请求的作品 id = {aweme_id} (尝试 {attempt+1}/{retries})')
                if aweme_id is None:
                    return {}

                # 增加随机延迟，避免请求过于规律被限制
                jitter = random.uniform(2.0, 5.0) * (1 + (attempt * 0.3))  # 随着重试次数增加延迟
                time.sleep(jitter)  # 请求前随机延迟

                # 构建请求URL，尝试不同的参数组合
                query_params = [
                    f'aweme_id={aweme_id}&device_platform=webapp&aid=6383',
                    f'aweme_id={aweme_id}&device_platform=webapp&version_code=170400&version_name=17.4.0&aid=6383',
                    f'aweme_id={aweme_id}&device_platform=webapp&aid=6383&version_name=23.5.0'
                ]
                
                # 选择一个参数组合
                param_index = attempt % len(query_params)
                jx_url = self.urls.POST_DETAIL + utils.getXbogus(query_params[param_index])
                
                # 更新请求头，添加更多浏览器特征
                headers = copy.deepcopy(douyin_headers)
                headers['Accept'] = 'application/json, text/plain, */*'
                headers['Accept-Language'] = 'zh-CN,zh;q=0.9,en;q=0.8'
                headers['sec-ch-ua'] = '"Not_A Brand";v="8", "Chromium";v="120"'
                headers['Referer'] = f'https://www.douyin.com/user/{sec_uid}'
                headers['Origin'] = 'https://www.douyin.com'
                headers['Accept-Encoding'] = 'gzip, deflate, br'
                headers['Connection'] = 'keep-alive'
                headers['Pragma'] = 'no-cache'
                headers['Cache-Control'] = 'no-cache'
                headers['sec-fetch-dest'] = 'empty'
                headers['sec-fetch-mode'] = 'cors'
                headers['sec-fetch-site'] = 'same-origin'
                
                # 生成新的随机Cookie值
                new_msToken = utils.generate_random_str(107)
                new_odin_tt = utils.generate_random_str(64)
                new_passport_csrf_token = utils.generate_random_str(32)
                new_sessionid = utils.generate_random_str(32)
                new_ttreq = utils.generate_random_str(32)
                new_install_id = str(random.randint(1000000000, 9999999999))
                
                # 构建更完整的Cookie
                cookie_str = (
                    f"msToken={new_msToken}; "
                    f"odin_tt={new_odin_tt}; "
                    f"passport_csrf_token={new_passport_csrf_token}; "
                    f"sessionid={new_sessionid}; "
                    f"ttreq={new_ttreq}; "
                    f"install_id={new_install_id}; "
                    f"passport_auth_status=1; "
                    f"d_ticket=1; "
                    f"sid_tt=1; "
                    f"uid_tt=1; "
                    f"sid_ucp_v1=1; "
                    f"ssid_ucp_v1=1"
                )
                
                # 设置新的Cookie
                headers['Cookie'] = cookie_str
                headers['Cookie'] += f"{headers.get('Cookie', '')};"
                headers['Cookie'] += f"msToken={new_msToken};"
                headers['Cookie'] += f"odin_tt={new_odin_tt};"
                headers['Cookie'] += f"passport_csrf_token={new_passport_csrf_token};"
                headers['Cookie'] += f"sessionid={new_sessionid};"
                
                # 尝试使用不同的User-Agent
                user_agents = [
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
                    'Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
                ]
                
                # 每次尝试使用不同的User-Agent
                headers['User-Agent'] = user_agents[attempt % len(user_agents)]
                
                # 如果是移动设备UA，相应地修改其他头信息
                if 'iPhone' in headers['User-Agent'] or 'iPad' in headers['User-Agent']:
                    headers['sec-ch-ua-mobile'] = '?1'
                    headers['sec-ch-ua-platform'] = '"iOS"'
                
                # 使用session保持连接
                session = requests.Session()
                
                try:
                    # 增加超时参数和错误处理，随着重试次数增加超时时间
                    timeout = 20 + (attempt * 5)
                    
                    # 添加请求前的日志
                    logger.info(f"请求URL: {jx_url[:100]}...")
                    logger.info(f"使用User-Agent: {headers['User-Agent'][:50]}...")
                    
                    # 发送请求
                    response = session.get(url=jx_url, headers=headers, timeout=timeout)
                    
                    # 检查HTTP状态码
                    if response.status_code != 200:
                        logger.warning(f"HTTP请求失败: 状态码 {response.status_code}")
                        raise RequestException(f"HTTP状态码: {response.status_code}")
                    
                    # 检查响应内容是否为空
                    if not response.text or response.text.isspace():
                        logger.warning("收到空响应")
                        raise ValueError("空响应")
                    
                    # 检查响应是否为二进制或加密数据
                    if res.text and len(res.text) > 0 and not res.text.strip().startswith('{'):
                        logger.warning("收到非JSON格式响应，可能是加密数据")
                        # 保存原始响应以便调试
                        with open(f"debug_user_{sec_uid}_cursor_{max_cursor}.txt", "wb") as f:
                            f.write(res.content)
                        logger.info(f"已保存原始响应到debug_user_{sec_uid}_cursor_{max_cursor}.txt")
                        raise ValueError("非JSON格式响应")
                    
                    # 记录响应长度
                    logger.info(f"收到响应，长度: {len(response.text)} 字节")
                    
                    # 尝试解析JSON
                    try:
                        datadict = json.loads(response.text)
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON解析失败: {str(e)}")
                        logger.debug(f"响应内容前100个字符: {response.text[:100]}")
                        raise
                    
                    # 验证API返回状态
                    if datadict is None:
                        logger.warning("API返回空数据")
                        raise ValueError("API返回空数据")
                        
                    if datadict.get("status_code") != 0:
                        status_msg = datadict.get("status_msg", "未知错误")
                        logger.warning(f"API返回错误: {status_msg}")
                        
                        # 如果是限流或需要登录的错误，增加等待时间
                        if "频繁" in status_msg or "登录" in status_msg or "拦截" in status_msg:
                            logger.warning("检测到限流或需要登录，增加等待时间")
                            time.sleep(random.uniform(10.0, 20.0))
                            
                        raise ValueError(f"API错误: {status_msg}")
                    
                    # 验证是否包含必要的数据
                    if 'aweme_detail' not in datadict:
                        logger.warning("API响应中缺少aweme_detail字段")
                        raise KeyError("缺少aweme_detail字段")
                    
                    # 清空self.awemeDict
                    self.result.clearDict(self.result.awemeDict)
                    
                    # 判断作品类型
                    awemeType = 0  # 默认为视频
                    if datadict['aweme_detail'].get("images") is not None:
                        awemeType = 1  # 图集
                    
                    # 转换成我们自己的格式
                    try:
                        self.result.dataConvert(awemeType, self.result.awemeDict, datadict['aweme_detail'])
                        logger.info(f"成功获取作品信息: ID={aweme_id}")
                        return self.result.awemeDict
                    except Exception as e:
                        logger.error(f"数据转换失败: {str(e)}")
                        # 保存原始数据以便调试
                        with open(f"debug_aweme_{aweme_id}.json", "w", encoding="utf-8") as f:
                            json.dump(datadict, f, ensure_ascii=False, indent=2)
                        logger.info(f"已保存原始数据到debug_aweme_{aweme_id}.json")
                        raise
                    
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    # 特定错误处理
                    logger.warning(f"处理响应时出错: {str(e)}")
                    # 不立即返回，继续外层重试
                except RequestException as e:
                    # 网络请求错误
                    logger.warning(f"网络请求失败: {str(e)}")
                    # 不立即返回，继续外层重试
                except Exception as e:
                    # 其他未预期的错误
                    logger.warning(f"未预期的错误: {str(e)}")
                    # 不立即返回，继续外层重试
                
            except Exception as e:
                # 外层异常捕获
                logger.error(f"获取作品信息失败 (尝试 {attempt+1}/{retries}): {str(e)}")
            
            # 指数退避等待，但添加随机性
            base_wait_time = min(45, 8 * (2 ** min(attempt, 3)))  # 基础等待时间，但限制最大值
            jitter = random.uniform(0.8, 1.5)  # 添加随机波动
            wait_time = base_wait_time * jitter
            logger.warning(f"等待{wait_time:.1f}秒后重试...")
            time.sleep(wait_time)
                
        logger.error(f"已达到最大重试次数({retries}次)，无法获取作品信息")
        return {}

    # 传入 url 支持 https://www.iesdouyin.com 与 https://v.douyin.com
    # mode : post | like 模式选择 like为用户点赞 post为用户发布
    def getUserInfo(self, sec_uid, mode="post", count=35, number=0, increase=False, start_time="", end_time=""):
        """获取用户信息
        Args:
            sec_uid: 用户ID
            mode: 模式(post:发布/like:点赞)
            count: 每页数量
            number: 限制下载数量(0表示无限制)
            increase: 是否增量更新
            start_time: 开始时间，格式：YYYY-MM-DD
            end_time: 结束时间，格式：YYYY-MM-DD
        """
        if sec_uid is None:
            return None

        # 处理时间范围
        if end_time == "now":
            end_time = time.strftime("%Y-%m-%d")
        
        if not start_time:
            start_time = "1970-01-01"
        if not end_time:
            end_time = "2099-12-31"

        self.console.print(f"[cyan]🕒 时间范围: {start_time} 至 {end_time}[/]")
        
        max_cursor = 0
        awemeList = []
        total_fetched = 0
        filtered_count = 0
        max_retries = 10  # 增加最大重试次数
        max_pages = 15    # 最大页数限制，防止无限循环
        current_page = 0  # 当前页数计数
        consecutive_failures = 0  # 连续失败计数
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=self.console,
            transient=True
        ) as progress:
            fetch_task = progress.add_task(
                f"[cyan]📥 正在获取{mode}作品列表...", 
                total=None  # 总数未知，使用无限进度条
            )
            
            while True and current_page < max_pages:
                current_page += 1
                retry_count = 0
                success = False
                
                # 如果连续失败次数过多，提前退出
                if consecutive_failures >= 3:
                    self.console.print(f"[yellow]⚠️ 连续{consecutive_failures}次请求失败，停止获取更多作品[/]")
                    break
                
                while retry_count < max_retries and not success:
                    try:
                        # 构建请求URL，尝试不同的参数组合
                        if mode == "post":
                            # 为post模式准备多种参数组合
                            query_params = [
                                f'sec_user_id={sec_uid}&count={count}&max_cursor={max_cursor}&device_platform=webapp&aid=6383&version_code=170400&version_name=17.4.0',
                                f'sec_user_id={sec_uid}&count={count}&max_cursor={max_cursor}&device_platform=webapp&aid=6383',
                                f'sec_user_id={sec_uid}&count={count}&max_cursor={max_cursor}&device_platform=webapp&version_code=170400&version_name=17.4.0',
                                # 添加更多参数组合
                                f'sec_user_id={sec_uid}&count={count}&max_cursor={max_cursor}&device_platform=webcast&aid=6383',
                                f'sec_user_id={sec_uid}&count={count}&max_cursor={max_cursor}&device_platform=webapp&aid=6383&version_name=23.5.0',
                                f'sec_user_id={sec_uid}&count={count}&max_cursor={max_cursor}&device_platform=webapp&aid=6383&version_name=23.5.0&channel=douyin_web',
                                f'sec_user_id={sec_uid}&count={count}&max_cursor={max_cursor}&device_platform=webapp&aid=6383&channel=channel_pc_web',
                                f'sec_user_id={sec_uid}&count={count}&max_cursor={max_cursor}&device_platform=webapp&aid=6383&cookie_enabled=true&platform=PC&downlink=10'
                            ]
                            param_index = retry_count % len(query_params)
                            url = self.urls.USER_POST + utils.getXbogus(query_params[param_index])
                        elif mode == "like":
                            query_params = [
                                f'sec_user_id={sec_uid}&count={count}&max_cursor={max_cursor}&device_platform=webapp&aid=6383',
                                f'sec_user_id={sec_uid}&count={count}&max_cursor={max_cursor}&device_platform=webapp&aid=6383&version_code=170400'
                            ]
                            param_index = retry_count % len(query_params)
                            url = self.urls.USER_FAVORITE_A + utils.getXbogus(query_params[param_index])
                        else:
                            self.console.print("[red]❌ 模式选择错误，仅支持post、like[/]")
                            return None

                        # 添加随机延迟，避免请求过于规律被限制
                        jitter = random.uniform(1.5, 3.0) * (retry_count + 1)
                        if retry_count > 0:
                            logger.info(f"第{retry_count+1}次重试，等待{jitter:.1f}秒...")
                            time.sleep(jitter)

                        # 使用session保持连接
                        session = requests.Session()
                        
                        # 更新请求头，添加更多浏览器特征
                        headers = copy.deepcopy(douyin_headers)
                        headers['Accept'] = 'application/json, text/plain, */*'
                        headers['Accept-Language'] = 'zh-CN,zh;q=0.9,en;q=0.8'
                        headers['sec-ch-ua'] = '"Not_A Brand";v="8", "Chromium";v="120"'
                        headers['Referer'] = 'https://www.douyin.com/'
                        headers['Origin'] = 'https://www.douyin.com'
                        
                        # 生成新的随机Cookie值
                        new_msToken = utils.generate_random_str(107)
                        new_odin_tt = utils.generate_random_str(64)
                        new_passport_csrf_token = utils.generate_random_str(32)
                        new_sessionid = utils.generate_random_str(32)
                        
                        # 构建更完整的Cookie
                        headers['Cookie'] = f"{headers.get('Cookie', '')};"
                        headers['Cookie'] += f"msToken={new_msToken};"
                        headers['Cookie'] += f"odin_tt={new_odin_tt};"
                        headers['Cookie'] += f"passport_csrf_token={new_passport_csrf_token};"
                        headers['Cookie'] += f"sessionid={new_sessionid};"
                        
                        # 为post模式添加更多请求头参数
                        if mode == "post":
                            headers['x-secsdk-csrf-token'] = utils.generate_random_str(32)
                            headers['x-tt-trace-id'] = utils.generate_random_str(32)
                            headers['x-tt-params'] = utils.generate_random_str(128)
                        
                        # 使用不同的User-Agent
                        user_agents = [
                            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
                            'Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
                        ]
                        
                        # 每次尝试使用不同的User-Agent
                        headers['User-Agent'] = user_agents[retry_count % len(user_agents)]
                        
                        # 如果是移动设备UA，相应地修改其他头信息
                        if 'iPhone' in headers['User-Agent'] or 'iPad' in headers['User-Agent']:
                            headers['sec-ch-ua-mobile'] = '?1'
                            headers['sec-ch-ua-platform'] = '"iOS"'
                        else:
                            headers['sec-ch-ua-mobile'] = '?0'
                            headers['sec-ch-ua-platform'] = '"macOS"'
                        
                        # 增加超时参数，随着重试次数增加超时时间
                        timeout = 20 + (retry_count * 5)
                        
                        # 添加请求前的日志
                        logger.info(f"请求URL: {url[:100]}...")
                        logger.info(f"使用User-Agent: {headers['User-Agent'][:50]}...")
                        
                        # 发送请求
                        res = session.get(url=url, headers=headers, timeout=timeout)
                        
                        # 检查HTTP状态码
                        if res.status_code != 200:
                            logger.warning(f"HTTP请求失败: 状态码 {res.status_code}")
                            raise RequestException(f"HTTP状态码: {res.status_code}")
                        
                        # 检查响应内容是否为空
                        if not res.text or res.text.isspace():
                            logger.warning("收到空响应")
                            raise ValueError("空响应")
                        
                        # 检查响应是否为二进制或加密数据
                        if res.text and len(res.text) > 0 and not res.text.strip().startswith('{'):
                            logger.warning("收到非JSON格式响应，可能是加密数据")
                            # 保存原始响应以便调试
                            with open(f"debug_user_{sec_uid}_cursor_{max_cursor}.txt", "wb") as f:
                                f.write(res.content)
                            logger.info(f"已保存原始响应到debug_user_{sec_uid}_cursor_{max_cursor}.txt")
                            raise ValueError("非JSON格式响应")
                        
                        # 尝试解析JSON
                        try:
                            datadict = json.loads(res.text)
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON解析失败: {str(e)}")
                            # 保存原始响应以便调试
                            debug_file = f"debug_user_{sec_uid}_cursor_{max_cursor}.txt"
                            with open(debug_file, "wb") as f:
                                f.write(res.content)
                            logger.info(f"已保存原始响应到{debug_file}")
                            raise
                        
                        # 处理返回数据
                        if not datadict:
                            logger.warning("API返回空数据")
                            raise ValueError("API返回空数据")
                            
                        if datadict.get("status_code") != 0:
                            status_msg = datadict.get('status_msg', '未知错误')
                            logger.warning(f"API返回错误: {status_msg}")
                            
                            # 针对post模式的特殊处理
                            if mode == "post" and ("请求太频繁" in str(status_msg) or "拦截" in str(status_msg)):
                                logger.warning("检测到请求频率限制，增加等待时间")
                                time.sleep(random.uniform(5.0, 10.0) * (retry_count + 1))
                            elif mode == "post" and ("登录" in str(status_msg) or "授权" in str(status_msg)):
                                logger.warning("可能需要更新Cookie")
                            
                            raise ValueError(f"API错误: {status_msg}")
                        
                        # 检查是否包含必要的数据
                        if "aweme_list" not in datadict or not isinstance(datadict["aweme_list"], list):
                            logger.warning("API响应中缺少aweme_list字段或格式不正确")
                            raise KeyError("缺少有效的aweme_list字段")
                            
                        # 如果执行到这里，说明请求成功
                        success = True
                        has_more = datadict.get('has_more', False)
                        max_cursor = datadict.get('max_cursor', 0)
                        
                        # 记录成功获取的数据信息
                        logger.info(f"成功获取数据: 模式={mode}, 用户ID={sec_uid}, 游标={max_cursor}, 作品数量={len(datadict['aweme_list'])}, 是否有更多={has_more}")
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON解析失败: {str(e)}")
                        logger.debug(f"响应内容前100个字符: {res.text[:100] if hasattr(res, 'text') else '无响应内容'}")
                        
                        # 保存原始响应以便调试
                        debug_file = f"debug_user_{sec_uid}_cursor_{max_cursor}.txt"
                        try:
                            with open(debug_file, "w", encoding="utf-8") as f:
                                f.write(res.text[:2000] if hasattr(res, 'text') else '无响应内容')  # 只保存前2000个字符避免文件过大
                            logger.info(f"已保存原始响应到{debug_file}")
                        except Exception as debug_err:
                            logger.warning(f"保存调试文件失败: {str(debug_err)}")
                        
                        # 尝试使用备用URL和参数组合，特别是针对post模式
                        if mode == "post" and retry_count < max_retries - 1:
                            try:
                                logger.info("尝试使用备用URL和参数组合")
                                backup_urls = [
                                    f"https://www.douyin.com/aweme/v1/web/aweme/post/?sec_user_id={sec_uid}&count={count}&max_cursor={max_cursor}&device_platform=webapp&aid=6383&version_code=170400&version_name=17.4.0",
                                    f"https://www.douyin.com/aweme/v1/web/aweme/post/?sec_user_id={sec_uid}&count={count}&max_cursor={max_cursor}&device_platform=webapp&aid=6383",
                                    f"https://www.douyin.com/aweme/v1/web/aweme/post/?sec_user_id={sec_uid}&count={count}&max_cursor={max_cursor}&device_platform=webcast&aid=6383",
                                    f"https://www.douyin.com/aweme/v1/web/aweme/post/?sec_user_id={sec_uid}&count={count}&max_cursor={max_cursor}&device_platform=webapp&aid=6383&version_name=23.5.0",
                                    f"https://www.douyin.com/aweme/v1/web/aweme/post/?sec_user_id={sec_uid}&count={count}&max_cursor={max_cursor}&device_platform=webapp&aid=6383&version_name=23.5.0&channel=douyin_web"
                                ]
                                
                                for i, backup_url in enumerate(backup_urls):
                                    try:
                                        logger.info(f"尝试备用URL {i+1}/{len(backup_urls)}")
                                        # 添加X-Bogus参数
                                        query_part = backup_url.split('?')[1]
                                        backup_url_with_xbogus = backup_url + "&" + utils.getXbogus(query_part).split('?')[1]
                                        
                                        # 修改User-Agent
                                        backup_headers = copy.deepcopy(headers)
                                        backup_headers['User-Agent'] = user_agents[i % len(user_agents)]
                                        
                                        # 添加随机延迟，增加延迟时间以避免频率限制
                                        time.sleep(random.uniform(3.0, 5.0) * (i + 1))
                                        
                                        # 增加请求头多样性
                                        backup_headers['Accept-Encoding'] = 'gzip, deflate, br'
                                        backup_headers['Connection'] = 'keep-alive'
                                        backup_headers['Pragma'] = 'no-cache'
                                        backup_headers['Cache-Control'] = 'no-cache'
                                        
                                        # 发送请求，增加重试次数
                                        temp_response = session.get(url=backup_url_with_xbogus, headers=backup_headers, timeout=timeout + (i * 5))
                                        if temp_response.status_code == 200 and temp_response.text and not temp_response.text.isspace():
                                            try:
                                                temp_data = json.loads(temp_response.text)
                                                if temp_data and temp_data.get("status_code") == 0 and "aweme_list" in temp_data:
                                                    logger.info(f"备用URL {i+1} 请求成功")
                                                    datadict = temp_data
                                                    success = True
                                                    break
                                            except json.JSONDecodeError:
                                                pass
                                    except Exception as e:
                                        logger.warning(f"备用URL {i+1} 请求失败: {str(e)}")
                            except Exception as e:
                                logger.warning(f"备用URL处理失败: {str(e)}")
                        
                        retry_count += 1
                    except (RequestException, ValueError) as e:
                        logger.error(f"请求失败: {str(e)}")
                        retry_count += 1
                    except Exception as e:
                        logger.error(f"未预期的错误: {str(e)}")
                        retry_count += 1
                
                # 如果所有重试都失败了
                if not success:
                    consecutive_failures += 1  # 增加连续失败计数
                    self.console.print(f"[red]❌ 网络请求失败: 已重试{max_retries}次[/]")
                    
                    # 如果是第一页就失败，直接退出
                    if current_page == 1 and len(awemeList) == 0:
                        break
                        
                    # 尝试跳过当前游标，继续获取下一页
                    if datadict and "max_cursor" in datadict:
                        max_cursor = datadict["max_cursor"]
                        logger.info(f"尝试跳过当前游标 {max_cursor}，继续获取下一页")
                        continue
                    else:
                        # 如果无法获取下一页游标，尝试增加当前游标值
                        max_cursor += count * 10000  # 大致估算下一页游标
                        logger.info(f"无法获取下一页游标，尝试使用估算值: {max_cursor}")
                        continue
                    
                # 请求成功，处理数据
                try:
                    current_count = len(datadict["aweme_list"])
                    total_fetched += current_count
                    
                    # 更新进度显示
                    progress.update(
                        fetch_task, 
                        description=f"[cyan]📥 已获取: {total_fetched}个作品"
                    )

                    # 在处理作品时添加时间过滤
                    for aweme in datadict["aweme_list"]:
                        create_time = time.strftime(
                            "%Y-%m-%d", 
                            time.localtime(int(aweme.get("create_time", 0)))
                        )
                        
                        # 时间过滤
                        if not (start_time <= create_time <= end_time):
                            filtered_count += 1
                            continue

                        # 数量限制检查
                        if number > 0 and len(awemeList) >= number:
                            self.console.print(f"[green]✅ 已达到限制数量: {number}[/]")
                            return awemeList
                            
                        # 增量更新检查
                        if self.database:
                            if mode == "post":
                                if self.db.get_user_post(sec_uid=sec_uid, aweme_id=aweme['aweme_id']):
                                    if increase and aweme['is_top'] == 0:
                                        self.console.print("[green]✅ 增量更新完成[/]")
                                        return awemeList
                                else:
                                    self.db.insert_user_post(sec_uid=sec_uid, aweme_id=aweme['aweme_id'], data=aweme)
                            elif mode == "like":
                                if self.db.get_user_like(sec_uid=sec_uid, aweme_id=aweme['aweme_id']):
                                    if increase and aweme['is_top'] == 0:
                                        self.console.print("[green]✅ 增量更新完成[/]")
                                        return awemeList
                            else:
                                self.console.print("[red]❌ 模式选择错误，仅支持post、like[/]")
                                return None

                        # 转换数据格式
                        aweme_data = self._convert_aweme_data(aweme)
                        if aweme_data:
                            awemeList.append(aweme_data)

                    # 检查是否还有更多数据
                    if not datadict["has_more"]:
                        self.console.print(f"[green]✅ 已获取全部作品: {total_fetched}个[/]")
                        break
                    
                    # 更新游标
                    max_cursor = datadict["max_cursor"]
                    
                except Exception as e:
                    consecutive_failures += 1  # 增加连续失败计数
                    self.console.print(f"[red]❌ 获取作品列表出错: {str(e)}[/]")
                    break

        return awemeList

    def _convert_aweme_data(self, aweme):
        """转换作品数据格式"""
        try:
            self.result.clearDict(self.result.awemeDict)
            aweme_type = 1 if aweme.get("images") else 0
            self.result.dataConvert(aweme_type, self.result.awemeDict, aweme)
            return copy.deepcopy(self.result.awemeDict)
        except Exception as e:
            logger.error(f"数据转换错误: {str(e)}")
            return None

    def getLiveInfo(self, web_rid: str):
        print('[  提示  ]:正在请求的直播间 id = %s\r\n' % web_rid)

        start = time.time()  # 开始时间
        while True:
            # 接口不稳定, 有时服务器不返回数据, 需要重新获取
            try:
                live_api = self.urls.LIVE + utils.getXbogus(
                    f'aid=6383&device_platform=web&web_rid={web_rid}')

                response = requests.get(live_api, headers=douyin_headers)
                live_json = json.loads(response.text)
                if live_json != {} and live_json['status_code'] == 0:
                    break
            except Exception as e:
                end = time.time()  # 结束时间
                if end - start > self.timeout:
                    print("[  提示  ]:重复请求该接口" + str(self.timeout) + "s, 仍然未获取到数据")
                    return {}

        # 清空字典
        self.result.clearDict(self.result.liveDict)

        # 类型
        self.result.liveDict["awemeType"] = 2
        # 是否在播
        self.result.liveDict["status"] = live_json['data']['data'][0]['status']

        if self.result.liveDict["status"] == 4:
            print('[   📺   ]:当前直播已结束，正在退出')
            return self.result.liveDict

        # 直播标题
        self.result.liveDict["title"] = live_json['data']['data'][0]['title']

        # 直播cover
        self.result.liveDict["cover"] = live_json['data']['data'][0]['cover']['url_list'][0]

        # 头像
        self.result.liveDict["avatar"] = live_json['data']['data'][0]['owner']['avatar_thumb']['url_list'][0].replace(
            "100x100", "1080x1080")

        # 观看人数
        self.result.liveDict["user_count"] = live_json['data']['data'][0]['user_count_str']

        # 昵称
        self.result.liveDict["nickname"] = live_json['data']['data'][0]['owner']['nickname']

        # sec_uid
        self.result.liveDict["sec_uid"] = live_json['data']['data'][0]['owner']['sec_uid']

        # 直播间观看状态
        self.result.liveDict["display_long"] = live_json['data']['data'][0]['room_view_stats']['display_long']

        # 推流
        self.result.liveDict["flv_pull_url"] = live_json['data']['data'][0]['stream_url']['flv_pull_url']

        try:
            # 分区
            self.result.liveDict["partition"] = live_json['data']['partition_road_map']['partition']['title']
            self.result.liveDict["sub_partition"] = \
                live_json['data']['partition_road_map']['sub_partition']['partition']['title']
        except Exception as e:
            self.result.liveDict["partition"] = '无'
            self.result.liveDict["sub_partition"] = '无'

        info = '[   💻   ]:直播间：%s  当前%s  主播：%s 分区：%s-%s\r' % (
            self.result.liveDict["title"], self.result.liveDict["display_long"], self.result.liveDict["nickname"],
            self.result.liveDict["partition"], self.result.liveDict["sub_partition"])
        print(info)

        flv = []
        print('[   🎦   ]:直播间清晰度')
        for i, f in enumerate(self.result.liveDict["flv_pull_url"].keys()):
            print('[   %s   ]: %s' % (i, f))
            flv.append(f)

        rate = int(input('[   🎬   ]输入数字选择推流清晰度：'))

        self.result.liveDict["flv_pull_url0"] = self.result.liveDict["flv_pull_url"][flv[rate]]

        # 显示清晰度列表
        print('[   %s   ]:%s' % (flv[rate], self.result.liveDict["flv_pull_url"][flv[rate]]))
        print('[   📺   ]:复制链接使用下载工具下载')
        return self.result.liveDict

    def getMixInfo(self, mix_id, count=35, number=0, increase=False, sec_uid="", start_time="", end_time=""):
        """获取合集信息"""
        if mix_id is None:
            return None

        # 处理时间范围
        if end_time == "now":
            end_time = time.strftime("%Y-%m-%d")
        
        if not start_time:
            start_time = "1970-01-01"
        if not end_time:
            end_time = "2099-12-31"

        self.console.print(f"[cyan]🕒 时间范围: {start_time} 至 {end_time}[/]")

        cursor = 0
        awemeList = []
        total_fetched = 0
        filtered_count = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=self.console,
            transient=True
        ) as progress:
            fetch_task = progress.add_task(
                "[cyan]📥 正在获取合集作品...",
                total=None
            )

            max_retries = 5  # 最大重试次数
            
            while True:  # 外层循环
                retry_count = 0
                success = False
                
                while retry_count < max_retries and not success:
                    try:
                        url = self.urls.USER_MIX + utils.getXbogus(
                            f'mix_id={mix_id}&cursor={cursor}&count={count}&device_platform=webapp&aid=6383')

                        # 添加随机延迟，避免请求过于规律被限制
                        jitter = random.uniform(0.5, 2.0) * (retry_count + 1)
                        if retry_count > 0:
                            logger.info(f"第{retry_count+1}次重试，等待{jitter:.1f}秒...")
                            time.sleep(jitter)
                        
                        # 使用session保持连接
                        session = requests.Session()
                        # 更新请求头，添加更多浏览器特征
                        headers = copy.deepcopy(douyin_headers)
                        headers['Accept'] = 'application/json, text/plain, */*'
                        headers['Accept-Language'] = 'zh-CN,zh;q=0.9,en;q=0.8'
                        headers['sec-ch-ua'] = '"Not_A Brand";v="8", "Chromium";v="120"'
                        headers['sec-ch-ua-mobile'] = '?0'
                        headers['sec-ch-ua-platform'] = '"macOS"'
                        headers['Referer'] = 'https://www.douyin.com/'
                        headers['Origin'] = 'https://www.douyin.com'
                        
                        # 生成新的随机Cookie值
                        new_msToken = utils.generate_random_str(107)
                        headers['Cookie'] = f"{headers.get('Cookie', '')};msToken={new_msToken};"
                        
                        # 尝试使用不同的User-Agent
                        if retry_count > 0 and retry_count % 2 == 0:
                            headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                        
                        # 增加超时参数，随着重试次数增加超时时间
                        timeout = 15 + (retry_count * 5)
                        res = session.get(url=url, headers=headers, timeout=timeout)
                        
                        # 检查HTTP状态码
                        if res.status_code != 200:
                            logger.warning(f"HTTP请求失败: 状态码 {res.status_code}")
                            raise RequestException(f"HTTP状态码: {res.status_code}")
                        
                        # 检查响应内容是否为空
                        if not res.text or res.text.isspace():
                            logger.warning("收到空响应")
                            raise ValueError("空响应")
                        
                        # 检查响应是否为二进制或加密数据
                        if res.text and len(res.text) > 0 and not res.text.strip().startswith('{'):
                            logger.warning("收到非JSON格式响应，可能是加密数据")
                            # 保存原始响应以便调试
                            with open(f"debug_user_{sec_uid}_cursor_{max_cursor}.txt", "wb") as f:
                                f.write(res.content)
                            logger.info(f"已保存原始响应到debug_user_{sec_uid}_cursor_{max_cursor}.txt")
                            raise ValueError("非JSON格式响应")
                        
                        # 尝试解析JSON
                        try:
                            datadict = json.loads(res.text)
                        except json.JSONDecodeError as e:
                            logger.error(f"JSON解析失败: {str(e)}")
                            # 保存原始响应以便调试
                            debug_file = f"debug_user_{sec_uid}_cursor_{max_cursor}.txt"
                            with open(debug_file, "wb") as f:
                                f.write(res.content)
                            logger.info(f"已保存原始响应到{debug_file}")
                            raise
                        
                        if not datadict:
                            logger.warning("获取到空数据字典")
                            raise ValueError("空数据字典")
                            
                        # 检查API返回状态
                        if datadict.get("status_code") != 0:
                            status_msg = datadict.get('status_msg', '未知错误')
                            logger.warning(f"API返回错误: {status_msg}")
                            raise ValueError(f"API错误: {status_msg}")
                            
                        # 如果执行到这里，说明请求成功
                        success = True
                        has_more = datadict.get('has_more', False)
                        max_cursor = datadict.get('max_cursor', 0)
                        
                        # 记录成功获取的数据信息
                        logger.info(f"成功获取数据: 模式={mode}, 用户ID={sec_uid}, 游标={max_cursor}, 作品数量={len(datadict['aweme_list'])}, 是否有更多={has_more}")
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON解析失败: {str(e)}")
                        logger.debug(f"响应内容前100个字符: {res.text[:100] if hasattr(res, 'text') else '无响应内容'}")
                        
                        # 保存原始响应以便调试
                        debug_file = f"debug_user_{sec_uid}_cursor_{max_cursor}.txt"
                        try:
                            with open(debug_file, "w", encoding="utf-8") as f:
                                f.write(res.text[:2000] if hasattr(res, 'text') else '无响应内容')  # 只保存前2000个字符避免文件过大
                            logger.info(f"已保存原始响应到{debug_file}")
                        except Exception as debug_err:
                            logger.warning(f"保存调试文件失败: {str(debug_err)}")
                        
                        # 尝试使用备用URL和参数组合，特别是针对post模式
                        if mode == "post" and retry_count < max_retries - 1:
                            try:
                                logger.info("尝试使用备用URL和参数组合")
                                backup_urls = [
                                    f"https://www.douyin.com/aweme/v1/web/aweme/post/?sec_user_id={sec_uid}&count={count}&max_cursor={max_cursor}&device_platform=webapp&aid=6383&version_code=170400&version_name=17.4.0",
                                    f"https://www.douyin.com/aweme/v1/web/aweme/post/?sec_user_id={sec_uid}&count={count}&max_cursor={max_cursor}&device_platform=webapp&aid=6383",
                                    f"https://www.douyin.com/aweme/v1/web/aweme/post/?sec_user_id={sec_uid}&count={count}&max_cursor={max_cursor}&device_platform=webcast&aid=6383",
                                    f"https://www.douyin.com/aweme/v1/web/aweme/post/?sec_user_id={sec_uid}&count={count}&max_cursor={max_cursor}&device_platform=webapp&aid=6383&version_name=23.5.0",
                                    f"https://www.douyin.com/aweme/v1/web/aweme/post/?sec_user_id={sec_uid}&count={count}&max_cursor={max_cursor}&device_platform=webapp&aid=6383&version_name=23.5.0&channel=douyin_web"
                                ]
                                
                                for i, backup_url in enumerate(backup_urls):
                                    try:
                                        logger.info(f"尝试备用URL {i+1}/{len(backup_urls)}")
                                        # 添加X-Bogus参数
                                        query_part = backup_url.split('?')[1]
                                        backup_url_with_xbogus = backup_url + "&" + utils.getXbogus(query_part).split('?')[1]
                                        
                                        # 修改User-Agent
                                        backup_headers = copy.deepcopy(headers)
                                        backup_headers['User-Agent'] = user_agents[i % len(user_agents)]
                                        
                                        # 添加随机延迟，增加延迟时间以避免频率限制
                                        time.sleep(random.uniform(3.0, 5.0) * (i + 1))
                                        
                                        # 增加请求头多样性
                                        backup_headers['Accept-Encoding'] = 'gzip, deflate, br'
                                        backup_headers['Connection'] = 'keep-alive'
                                        backup_headers['Pragma'] = 'no-cache'
                                        backup_headers['Cache-Control'] = 'no-cache'
                                        
                                        # 发送请求，增加重试次数
                                        temp_response = session.get(url=backup_url_with_xbogus, headers=backup_headers, timeout=timeout + (i * 5))
                                        if temp_response.status_code == 200 and temp_response.text and not temp_response.text.isspace():
                                            try:
                                                temp_data = json.loads(temp_response.text)
                                                if temp_data and temp_data.get("status_code") == 0 and "aweme_list" in temp_data:
                                                    logger.info(f"备用URL {i+1} 请求成功")
                                                    datadict = temp_data
                                                    success = True
                                                    break
                                            except json.JSONDecodeError:
                                                pass
                                    except Exception as e:
                                        logger.warning(f"备用URL {i+1} 请求失败: {str(e)}")
                            except Exception as e:
                                logger.warning(f"备用URL处理失败: {str(e)}")
                        
                        retry_count += 1
                    except (RequestException, ValueError) as e:
                        logger.error(f"请求失败: {str(e)}")
                        retry_count += 1
                    except Exception as e:
                        logger.error(f"未预期的错误: {str(e)}")
                        retry_count += 1
                
                # 如果所有重试都失败了
                if not success:
                    self.console.print(f"[red]❌ 网络请求失败: 已重试{max_retries}次[/]")
                    break
                
                try:
                    for aweme in datadict["aweme_list"]:
                        create_time = time.strftime(
                            "%Y-%m-%d",
                            time.localtime(int(aweme.get("create_time", 0)))
                        )

                        # 时间过滤
                        if not (start_time <= create_time <= end_time):
                            filtered_count += 1
                            continue

                        # 数量限制检查
                        if number > 0 and len(awemeList) >= number:
                            return awemeList  # 使用return替代break

                        # 增量更新检查
                        if self.database:
                            if self.db.get_mix(sec_uid=sec_uid, mix_id=mix_id, aweme_id=aweme['aweme_id']):
                                if increase and aweme['is_top'] == 0:
                                    return awemeList  # 使用return替代break
                            else:
                                self.db.insert_mix(sec_uid=sec_uid, mix_id=mix_id, aweme_id=aweme['aweme_id'], data=aweme)

                        # 转换数据
                        aweme_data = self._convert_aweme_data(aweme)
                        if aweme_data:
                            awemeList.append(aweme_data)

                    # 检查是否还有更多数据
                    if not datadict.get("has_more"):
                        self.console.print(f"[green]✅ 已获取全部作品[/]")
                        break

                    # 更新游标
                    cursor = datadict.get("cursor", 0)
                    total_fetched += len(datadict["aweme_list"])
                    progress.update(fetch_task, description=f"[cyan]📥 已获取: {total_fetched}个作品")

                except Exception as e:
                    self.console.print(f"[red]❌ 获取作品列表出错: {str(e)}[/]")
                    break

        if filtered_count > 0:
            self.console.print(f"[yellow]⚠️  已过滤 {filtered_count} 个不在时间范围内的作品[/]")

        return awemeList

    def getUserAllMixInfo(self, sec_uid, count=35, number=0):
        print('[  提示  ]:正在请求的用户 id = %s\r\n' % sec_uid)
        if sec_uid is None:
            return None
        if number <= 0:
            numflag = False
        else:
            numflag = True

        cursor = 0
        mixIdNameDict = {}

        print("[  提示  ]:正在获取主页下所有合集 id 数据请稍后...\r")
        print("[  提示  ]:会进行多次请求，等待时间较长...\r\n")
        times = 0
        while True:
            times = times + 1
            print("[  提示  ]:正在对 [合集列表] 进行第 " + str(times) + " 次请求...\r")

            start = time.time()  # 开始时间
            while True:
                # 接口不稳定, 有时服务器不返回数据, 需要重新获取
                try:
                    url = self.urls.USER_MIX_LIST + utils.getXbogus(
                        f'sec_user_id={sec_uid}&count={count}&cursor={cursor}&device_platform=webapp&aid=6383')

                    res = requests.get(url=url, headers=douyin_headers)
                    datadict = json.loads(res.text)
                    print('[  提示  ]:本次请求返回 ' + str(len(datadict["mix_infos"])) + ' 条数据\r')

                    if datadict is not None and datadict["status_code"] == 0:
                        break
                except Exception as e:
                    end = time.time()  # 结束时间
                    if end - start > self.timeout:
                        print("[  提示  ]:重复请求该接口" + str(self.timeout) + "s, 仍然未获取到数据")
                        return mixIdNameDict


            for mix in datadict["mix_infos"]:
                mixIdNameDict[mix["mix_id"]] = mix["mix_name"]
                if numflag:
                    number -= 1
                    if number == 0:
                        break
            if numflag and number == 0:
                print("\r\n[  提示  ]:[合集列表] 下指定数量合集数据获取完成...\r\n")
                break

            # 更新 max_cursor
            cursor = datadict["cursor"]

            # 退出条件
            if datadict["has_more"] == 0 or datadict["has_more"] == False:
                print("[  提示  ]:[合集列表] 下所有合集 id 数据获取完成...\r\n")
                break
            else:
                print("\r\n[  提示  ]:[合集列表] 第 " + str(times) + " 次请求成功...\r\n")

        return mixIdNameDict

    def getMusicInfo(self, music_id: str, count=35, number=0, increase=False):
        print('[  提示  ]:正在请求的音乐集合 id = %s\r\n' % music_id)
        if music_id is None:
            return None
        if number <= 0:
            numflag = False
        else:
            numflag = True

        cursor = 0
        awemeList = []
        increaseflag = False
        numberis0 = False

        print("[  提示  ]:正在获取音乐集合下的所有作品数据请稍后...\r")
        print("[  提示  ]:会进行多次请求，等待时间较长...\r\n")
        times = 0
        while True:
            times = times + 1
            print("[  提示  ]:正在对 [音乐集合] 进行第 " + str(times) + " 次请求...\r")

            start = time.time()  # 开始时间
            while True:
                # 接口不稳定, 有时服务器不返回数据, 需要重新获取
                try:
                    url = self.urls.MUSIC + utils.getXbogus(
                        f'music_id={music_id}&cursor={cursor}&count={count}&device_platform=webapp&aid=6383')

                    res = requests.get(url=url, headers=douyin_headers)
                    datadict = json.loads(res.text)
                    print('[  提示  ]:本次请求返回 ' + str(len(datadict["aweme_list"])) + ' 条数据\r')

                    if datadict is not None and datadict["status_code"] == 0:
                        break
                except Exception as e:
                    end = time.time()  # 结束时间
                    if end - start > self.timeout:
                        print("[  提示  ]:重复请求该接口" + str(self.timeout) + "s, 仍然未获取到数据")
                        return awemeList


            for aweme in datadict["aweme_list"]:
                if self.database:
                    # 退出条件
                    if increase is False and numflag and numberis0:
                        break
                    if increase and numflag and numberis0 and increaseflag:
                        break
                    # 增量更新, 找到非置顶的最新的作品发布时间
                    if self.db.get_music(music_id=music_id, aweme_id=aweme['aweme_id']) is not None:
                        if increase and aweme['is_top'] == 0:
                            increaseflag = True
                    else:
                        self.db.insert_music(music_id=music_id, aweme_id=aweme['aweme_id'], data=aweme)

                    # 退出条件
                    if increase and numflag is False and increaseflag:
                        break
                    if increase and numflag and numberis0 and increaseflag:
                        break
                else:
                    if numflag and numberis0:
                        break

                if numflag:
                    number -= 1
                    if number == 0:
                        numberis0 = True

                # 清空self.awemeDict
                self.result.clearDict(self.result.awemeDict)

                # 默认为视频
                awemeType = 0
                try:
                    if aweme["images"] is not None:
                        awemeType = 1
                except Exception as e:
                    print("[  警告  ]:接口中未找到 images\r")

                # 转换成我们自己的格式
                self.result.dataConvert(awemeType, self.result.awemeDict, aweme)

                if self.result.awemeDict is not None and self.result.awemeDict != {}:
                    awemeList.append(copy.deepcopy(self.result.awemeDict))

            if self.database:
                if increase and numflag is False and increaseflag:
                    print("\r\n[  提示  ]: [音乐集合] 下作品增量更新数据获取完成...\r\n")
                    break
                elif increase is False and numflag and numberis0:
                    print("\r\n[  提示  ]: [音乐集合] 下指定数量作品数据获取完成...\r\n")
                    break
                elif increase and numflag and numberis0 and increaseflag:
                    print("\r\n[  提示  ]: [音乐集合] 下指定数量作品数据获取完成, 增量更新数据获取完成...\r\n")
                    break
            else:
                if numflag and numberis0:
                    print("\r\n[  提示  ]: [音乐集合] 下指定数量作品数据获取完成...\r\n")
                    break

            # 更新 cursor
            cursor = datadict["cursor"]

            # 退出条件
            if datadict["has_more"] == 0 or datadict["has_more"] == False:
                print("\r\n[  提示  ]:[音乐集合] 下所有作品数据获取完成...\r\n")
                break
            else:
                print("\r\n[  提示  ]:[音乐集合] 第 " + str(times) + " 次请求成功...\r\n")

        return awemeList

    def getUserDetailInfo(self, sec_uid):
        if sec_uid is None:
            return None

        datadict = {}
        start = time.time()  # 开始时间
        while True:
            # 接口不稳定, 有时服务器不返回数据, 需要重新获取
            try:
                url = self.urls.USER_DETAIL + utils.getXbogus(
                        f'sec_user_id={sec_uid}&device_platform=webapp&aid=6383')

                res = requests.get(url=url, headers=douyin_headers)
                datadict = json.loads(res.text)

                if datadict is not None and datadict["status_code"] == 0:
                    return datadict
            except Exception as e:
                end = time.time()  # 结束时间
                if end - start > self.timeout:
                    print("[  提示  ]:重复请求该接口" + str(self.timeout) + "s, 仍然未获取到数据")
                    return datadict


if __name__ == "__main__":
    pass
