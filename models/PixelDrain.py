import json, requests
import time
import datetime
import re
import math
import hashlib
import base64
from cachelib import SimpleCache
from fastapi import HTTPException
import os
import sys
sys.path.append(os.path.abspath('../'))
from schemas.schemas import *


class PixelDrain():
    '''
    https://pixeldrain.com/
    '''
    def __init__(self,provider='',token=''):
        # 注意provider必填
        '''
        :param provider: 模型实例名称
        :param token: API token【官方叫api_key】可在https://pixeldrain.com/user/api_keys获得
        '''
        # 创建配置文件对象
        self.provider = provider
        self.token = token
        self.cache = SimpleCache()
        # 防止请求过于频繁，用于请求间隔时间
        self.sleep_time = 0.005
        # 缓存结果时间默认10分钟
        self.cache_time = 600
        auth_token = base64.b64encode(f"ttt:{self.token}".encode('utf-8')).decode('utf-8')
        self.headers = {
            "user-agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.93 Safari/537.36",
            "content-type":"application/json;charset=UTF-8",
            "Authorization": f"Basic {auth_token}"
        }
       
    # 文件列表方法 返回DavFile列表 请求内容为ListRequest，默认根目录ID为root
    def list_files(self, list_req:ListRequest):
        folderId=list_req.parent_file_id
        if folderId=='root':
            folderId=0
        file_list = self.cache.get(f"PixelDrain-{self.token}-{folderId}")
        auth_token = base64.b64encode(f"ttt:{self.token}".encode('utf-8')).decode('utf-8')
        # 如果缓存中没有结果，则重新请求并缓存结果
        if not file_list:
            file_list = []
            url = "https://pixeldrain.com/api/user/files"
            try:
                response = requests.get(url, verify=False, headers=self.headers, timeout=100)
                # 如果请求失败，则抛出异常
            except requests.exceptions.RequestException as e:
                print("无法获取文件信息")
            result = json.loads(response.text)
            for file in result['files']:
                # 格式化时间为字符串
                dt = datetime.datetime.strptime(file['date_upload'], '%Y-%m-%dT%H:%M:%S.%fZ')
                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                download_url = "https://pixeldrain.com/api/file/"+file['id']
                dav_file = DavFile(id=file['id'],provider=self.provider,parent_id=0,kind=1,name=file['name'],size=str(file['size']),create_time=formatted_time,download_url=download_url) 
                file_list.append(dav_file)

            self.cache.set(f"PixelDrain-{self.token}-{folderId}", file_list, timeout=self.cache_time)
        return file_list

    # 文件下载地址 返回下载地址
    def get_url(self,dav_file:DavFile):
        #这个url已经在列表页面得到，不需要再请求
        # url = f"https://uploady.io/embed-{dav_file.file_id}.html"
        # try:
        #     response = requests.get(url, verify=False, headers=self.headers, timeout=100)
        #     # 如果请求失败，则抛出异常
        # except requests.exceptions.RequestException as e:
        #     raise HTTPException(status_code=400, detail="无法打开文件播放页面")
        # parten="src: \"(.*)\""
        # download_url = re.findall(parten, response.text)[0]
        # #设置三小时后过期
        # current_timestamp_sec = round(time.time())
        # expires_timestamp_sec = current_timestamp_sec+10800
        # if '?' in download_url:
        #     download_url=f"{download_url}&x-oss-expires={expires_timestamp_sec}"
        # else:
        #     download_url=f"{download_url}?x-oss-expires={expires_timestamp_sec}"     

        return ""


    # 辅助方法
    def pluck(self,lst, key):
        return [x.get(key) for x in lst]
