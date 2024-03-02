import json, requests
import time
from datetime import datetime
import re
import math
import hashlib
from cachelib import SimpleCache
import os
import sys
sys.path.append(os.path.abspath('../'))
from schemas.schemas import *
import base64
import urllib
import random
import string

class CaiYunDrive():
    '''
    移动139云盘:又叫彩云网盘,这里用的是个人云
    '''
    def __init__(self,provider='',authToken='',folder_id=''):
        # 创建配置文件对象 注provider必填 参数对照alist
        '''
        :param provider: 模型实例名称
        :param authToken: Authorization
        :param folder_id: 根文件夹ID
        '''
        self.config = {}
        self.configFileName = provider+".txt"
        self.provider = provider
        self.refreshToken = authToken
        self.account = ""
        self.folder_id = folder_id
        self.accessToken = ""
        self.driveId = ""
        self.cache = SimpleCache()
        self.api_base = "https://yun.139.com"
        # 防止请求过于频繁，用于请求间隔时间
        self.sleep_time = 1
        # 缓存结果时间默认10分钟
        self.cache_time = 600
        self.url_cache_time = 600
        self.headers = {
            "user-agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.93 Safari/537.36",
            "content-type":"application/json;charset=UTF-8",
            "Origin":"https://www.aliyundrive.com",
            "Referer":"https://www.aliyundrive.com",
        }
        if len(self.folder_id)==0:
            self.folder_id = "root"
        
        decode = base64.b64decode(self.refreshToken)
        decode_str = decode.decode('utf-8')
        splits = decode_str.split(":")
        if len(splits) < 2:
            raise ValueError("认证字符串不正确,无法获取账号信息")

        self.account = splits[1]


  
    # 文件列表方法 返回DavFile列表 请求内容为ListRequest，默认根目录ID为root
    def list_files(self, list_req:ListRequest):
        folderId=list_req.parent_file_id
        if folderId=='root':
            folderId=""
        file_list = self.cache.get(f"caiyundrive-{self.provider}-files-{folderId}")

        path_str = list_req.path_str
        if list_req.parent_file_id=='root':
            path_str="/"
        else:
            start_index=list_req.path_str.find('/',1)
            path_str=list_req.path_str[start_index:]

        # 如果缓存中没有结果，则重新请求并缓存结果
        if not file_list:
            file_list = []
            sha1 = None
            start = 0
            limit = 100
            while True:
                parent_file_id=""
                if folderId == "":
                    parent_file_id=self.folder_id
                else:
                    parent_file_id=folderId
                url=f"{self.api_base}/orchestration/personalCloud/catalog/v1.0/getDisk"
                list_req=json.dumps({
                    "catalogID":       parent_file_id,
                    "sortDirection":   1,
                    "startNumber":     start + 1,
                    "endNumber":       start + limit,
                    "filterType":      0,
                    "catalogSortType": 0,
                    "contentSortType": 0,
                    "commonAccountInfo":{
                        "account":self.account,
                        "accountType": 1,
                    },
                })
                headers = self.requestHeader(list_req)
                try:
                    response = requests.post(url, data=list_req,verify=False,headers=headers, timeout=100)
                    # 如果请求失败，则抛出异常
                    response.raise_for_status()
                except requests.exceptions.RequestException as e:
                    print(e)
                    #response = requests.post(url, data=list_req,verify=False,headers=headers, timeout=100)
                
                if response.status_code == 200:
                    result = json.loads(response.text)
                    if result['data']['getDiskResult']['contentList']:
                        for file in result['data']['getDiskResult']['contentList']:
                            kind = '1'
                            download_url = None
                            sha1 = file['digest']
                            date_time = datetime.strptime(file['updateTime'], "%Y%m%d%H%M%S")
                            ts_str = date_time.strftime("%Y-%m-%d %H:%M:%S")
                            dav_file = DavFile(id=file['contentID'],provider=self.provider,parent_id=file['parentCatalogId'],kind=kind,name=file['contentName'],size=str(file['contentSize']),create_time=ts_str,sha1=sha1,download_url=download_url) 
                            file_list.append(dav_file)
                    
                    if result['data']['getDiskResult']['catalogList']:
                        for file in result['data']['getDiskResult']['catalogList']:
                            kind = '0'
                            download_url = None
                            sha1 = file['path']
                            date_time = datetime.strptime(file['updateTime'], "%Y%m%d%H%M%S")
                            ts_str = date_time.strftime("%Y-%m-%d %H:%M:%S")
                            dav_file = DavFile(id=file['catalogID'],provider=self.provider,parent_id=file['parentCatalogId'],kind=kind,name=file['catalogName'],size=str(0),create_time=ts_str,sha1=sha1,download_url=download_url) 
                            file_list.append(dav_file)
                    
                    if start+limit >= result['data']['getDiskResult']['nodeCount']:
                        break
                    else:
                        start += limit
                    time.sleep(self.sleep_time)
                else:
                    print("无法获取文件列表")
                    break
            self.cache.set(f"caiyundrive-{self.provider}-files-{folderId}", file_list, timeout=self.cache_time)
        return file_list

    # 文件下载地址 返回下载地址
    def get_url(self,dav_file:DavFile):
        download_url = self.cache.get(f"caiyun-{self.provider}-files-{dav_file.file_id}-url")
        # 如果缓存中没有结果，则重新请求并缓存结果
        if download_url:
            return download_url
        url=f"{self.api_base}/orchestration/personalCloud/uploadAndDownload/v1.0/downloadRequest"
        url_req=json.dumps({
            "appName":   "",
            "contentID": dav_file.file_id,
            "commonAccountInfo": {
                "account": self.account,
                "accountType": 1,
            },
        })
        headers = self.requestHeader(url_req)
        try:
            response = requests.post(url, verify=False, data=url_req, headers=headers, timeout=100)
            # 如果请求失败，则抛出异常
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(e)
            #response = requests.get(url, verify=False,headers=self.headers, timeout=100)
        result = json.loads(response.text)
        download_url = result['data']['downloadURL']
        current_timestamp_sec = round(time.time())
        expires_timestamp_sec = current_timestamp_sec+10800
        download_expires_url = ""
        if '?' in download_url:
            download_expires_url=f"{download_url}&x-oss-expires={expires_timestamp_sec}"
        else:
            download_expires_url=f"{download_url}?x-oss-expires={expires_timestamp_sec}"
        self.cache.set(f"caiyundrive-{self.provider}-files-{dav_file.file_id}-url", download_expires_url, timeout=self.url_cache_time)
        return download_expires_url
        
    def requestHeader(self,payload):
        current_time = datetime.now()
        formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S")
        key = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        sign = Yun139Sign(formatted_time, key,payload)
        headers = {
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'mcloud-route': '001',
            'x-yun-module-type': '100',
            'x-yun-app-channel': '10000034',
            'Authorization': 'Basic '+self.refreshToken,
            'x-huawei-channelSrc': '10000034',
            "x-DeviceInfo":"||9|6.6.0|chrome|95.0.4638.69|uwIy75obnsRPIwlJSd7D9GhUvFwG96ce||macos 10.15.2||zh-CN|||",
            'caller': 'web',
            'x-yun-channel-source': '10000034',
            'x-inner-ntwk': '2',
            'sec-ch-ua-platform': '"macOS"',
            'CMS-DEVICE': 'default',
            'mcloud-client': '10701',
            'mcloud-channel': '1000101',
            'mcloud-sign': formatted_time + "," + key + "," + sign,
            'x-m4c-src': '10002',
            'INNER-HCY-ROUTER-HTTPS': '1',
            'mcloud-version': '7.13.1',
            'Content-Type': 'application/json;charset=UTF-8',
            'x-SvcType': '1',
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'x-yun-api-version': 'v1',
            'sec-ch-ua-mobile': '?0',
            'Referer': 'https://yun.139.com/w/',
            'x-yun-svc-type': '1',
            'x-m4c-caller': 'PC'
        }   
        return headers

def Yun139Sign(timestamp, key, data):
    #去除多余空格
    data = data.strip()
    data = urllib.parse.quote(data)
    c = list(data)
    c.sort()
    json = ''.join(c)
    s1 = hashlib.md5(base64.b64encode(json.encode('utf-8'))).hexdigest()
    s2 = hashlib.md5((timestamp + ":" + key).encode('utf-8')).hexdigest()
    return hashlib.md5((s1 + s2).encode('utf-8')).hexdigest().upper()
