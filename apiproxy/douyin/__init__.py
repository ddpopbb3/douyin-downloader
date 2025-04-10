#!/usr/bin/env python
# -*- coding: utf-8 -*-

import apiproxy
import logging
import random
import time
import uuid
import platform
import hashlib
from apiproxy.common import utils

# 创建logger实例
logger = logging.getLogger("douyin_downloader")

# 尝试获取ttwid，如果失败则使用空字符串，增加重试机制
def get_ttwid_with_retry(max_retries=5):  # 增加重试次数
    for attempt in range(max_retries):
        try:
            logger.info(f"尝试获取ttwid (尝试 {attempt+1}/{max_retries})")
            ttwid = utils.getttwid()
            if ttwid:
                logger.info("成功获取ttwid")
                return ttwid
            else:
                logger.warning("获取到空的ttwid，将重试")
        except Exception as e:
            logger.warning(f"获取ttwid失败: {str(e)}")
        
        # 如果不是最后一次尝试，则等待后重试
        if attempt < max_retries - 1:
            wait_time = random.uniform(2.0, 5.0) * (attempt + 1)  # 增加等待时间
            logger.info(f"等待 {wait_time:.1f} 秒后重试...")
            time.sleep(wait_time)
    
    logger.error("所有尝试获取ttwid均失败，将使用空值")
    return ""

# 生成随机设备ID
def generate_device_id():
    return str(uuid.uuid4()).replace('-', '')[:21]

# 生成随机的session ID
def generate_session_id():
    return hashlib.md5(str(time.time() + random.random()).encode()).hexdigest()

# 获取ttwid
ttwid = get_ttwid_with_retry()

# 生成随机的Cookie值
msToken = utils.generate_random_str(107)
did = generate_device_id()
session_id = generate_session_id()

# 生成随机的odin_tt和passport_csrf_token
odin_tt = hashlib.md5((did + str(time.time())).encode()).hexdigest() + hashlib.sha1((did + str(random.random())).encode()).hexdigest()[:20]
passport_csrf_token = hashlib.md5(str(time.time() + random.random()).encode()).hexdigest()[:32]

# 构建更完整的Cookie
cookie_str = (
    f"msToken={msToken}; "
    f"ttwid={ttwid}; "
    f"odin_tt={odin_tt}; "
    f"passport_csrf_token={passport_csrf_token}; "
    f"sessionid={session_id}; "
    f"passport_auth_status=1; "
    f"d_ticket=1; "
    f"sid_tt=1; "
    f"uid_tt=1; "
    f"sid_ucp_v1=1; "
    f"ssid_ucp_v1=1; "
    f"install_id={random.randint(1000000000, 9999999999)}; "
    f"ttreq={utils.generate_random_str(32)}"
)

# 构建增强的请求头
douyin_headers = {
    'User-Agent': apiproxy.ua,
    'Referer': 'https://www.douyin.com/',
    'Accept-Encoding': 'gzip, deflate, br',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
    'Cookie': cookie_str,
    'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': f'"{platform.system()}"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'Origin': 'https://www.douyin.com',
    'Pragma': 'no-cache',
    'Cache-Control': 'no-cache'
}

# 记录初始化信息
logger.info(f"初始化抖音请求头: ttwid长度={len(ttwid)}, msToken长度={len(msToken)}, did={did[:8]}...")
logger.info(f"User-Agent: {apiproxy.ua}")
