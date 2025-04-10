#!/usr/bin/env python
# -*- coding: utf-8 -*-

import apiproxy
from apiproxy.common import utils

# 尝试获取ttwid，如果失败则使用空字符串
try:
    ttwid = utils.getttwid()
except Exception as e:
    print(f"获取ttwid失败，将使用空值: {str(e)}")
    ttwid = ""

douyin_headers = {
    'User-Agent': apiproxy.ua,
    'referer': 'https://www.douyin.com/',
    'accept-encoding': None,
    'Cookie': f"msToken={utils.generate_random_str(107)}; ttwid={ttwid}; odin_tt=324fb4ea4a89c0c05827e18a1ed9cf9bf8a17f7705fcc793fec935b637867e2a5a9b8168c885554d029919117a18ba69; passport_csrf_token=f61602fc63757ae0e4fd9d6bdcee4810;"
}
