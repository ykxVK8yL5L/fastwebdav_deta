import json, requests
import time
import datetime
import re
import math
import hashlib
from cachelib import SimpleCache
from fastapi import HTTPException
import os
import sys
sys.path.append(os.path.abspath('../'))
from schemas.schemas import *


class Filebin():
    '''
    https://filebin.net/:临时网盘6天有效
    '''
    def __init__(self,provider='',bin=''):
        #注provider必填
        '''
        :param provider: 模型实例名称
        :param bin: bin名称 请你查看主页
        '''
        # 创建配置文件对象
        self.provider = provider
        self.bin = bin
        self.cache = SimpleCache()
        # 防止请求过于频繁，用于请求间隔时间
        self.sleep_time = 0.005
        # 缓存结果时间默认10分钟
        self.cache_time = 600
        self.headers = {
            "user-agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.93 Safari/537.36",
            "content-type":"application/json;charset=UTF-8",
            "accept":"application/json",
        }
    # 文件列表方法 返回DavFile列表 请求内容为ListRequest，默认根目录ID为root
    def list_files(self, list_req:ListRequest):
        folderId=list_req.parent_file_id
        if folderId=='root':
            folderId='root'
        file_list = self.cache.get(f"Filebin-{self.bin}")
        # 如果缓存中没有结果，则重新请求并缓存结果
        if not file_list:
            file_list = []
            url = f"https://filebin.net/{self.bin}"
            try:
                response = requests.get(url, verify=False, headers=self.headers, timeout=100)
                # 如果请求失败，则抛出异常
            except requests.exceptions.RequestException as e:
                print("无法获取文件信息")
            result = json.loads(response.text)
            for child in result['files']:
                file=child
                kind = 1
                filesize = 0
                # 格式化时间为字符串
                dt = datetime.datetime.strptime(file['created_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                filesize = file['bytes']
                download_url = "https://filebin.net/"+self.bin+'/'+file['filename']
                #设置三小时后过期
                # current_timestamp_sec = round(time.time())
                # expires_timestamp_sec = current_timestamp_sec+10800
                # if '?' in download_url:
                #     download_url=f"{download_url}&x-oss-expires={expires_timestamp_sec}"
                # else:
                #     download_url=f"{download_url}?x-oss-expires={expires_timestamp_sec}"                    
                dav_file = DavFile(id=file['filename'],provider=self.provider,parent_id='root',kind= kind,name=file['filename'],size=str(filesize),create_time=formatted_time,download_url=download_url) 
                file_list.append(dav_file)
            self.cache.set(f"Filebin-{self.bin}", file_list, timeout=self.cache_time)
        return file_list

    # 文件下载地址 返回下载地址
    def get_url(self,dav_file:DavFile):
        #这个url已经在列表页面得到，不需要再请求
        return ""

    # 辅助方法
    def pluck(self,lst, key):
        return [x.get(key) for x in lst]