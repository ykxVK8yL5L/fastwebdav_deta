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
from deta import Deta

class AliYunDrive():
    '''
    AliYunDrive:阿里云网盘
    '''
    def __init__(self,provider='',refreshToken=''):
        # 创建配置文件对象 注provider必填 参数对照alist
        '''
        :param provider: 模型实例名称
        :param refreshToken: 刷新令牌
        '''
        deta = Deta()
        self.driver = deta.Drive("AliYunDrive")
        self.config = {}
        self.configFileName = provider+".txt"
        self.provider = provider
        self.refreshToken = refreshToken
        self.accessToken = ""
        self.driveId = ""
        self.cache = SimpleCache()
        # 防止请求过于频繁，用于请求间隔时间
        self.sleep_time = 0.005
        # 缓存结果时间默认10分钟
        self.cache_time = 600
        self.url_cache_time = 600
        self.headers = {
            "user-agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.93 Safari/537.36",
            "content-type":"application/json;charset=UTF-8",
            "Origin":"https://www.aliyundrive.com",
            "Referer":"https://www.aliyundrive.com",
        }


        try:
            response=self.driver.get(self.configFileName)
            self.config = json.loads(response.read())
        except:
            # 如果配置文件不存在，创建一个空的配置文件
            self.driver.put(self.configFileName, data=json.dumps({}))        
            self.refresh_token()          
                
        if 'refresh_token' in self.config:
            self.refreshToken = self.config['refresh_token']
            self.accessToken = self.config['access_token']
            self.headers['Authorization']='Bearer '+self.accessToken
        else:
            self.refresh_token()

        if 'drive_id' in self.config:
            self.driveId = self.config['drive_id']
        else:
            self.get_drive_id()

  
    # 文件列表方法 返回DavFile列表 请求内容为ListRequest，默认根目录ID为root
    def list_files(self, list_req:ListRequest):
        folderId=list_req.parent_file_id
        if folderId=='root':
            folderId=""
        file_list = self.cache.get(f"aliyundrive-{self.provider}-files-{folderId}")

        path_str = list_req.path_str
        if list_req.parent_file_id=='root':
            path_str="/"
        else:
            start_index=list_req.path_str.find('/',1)
            path_str=list_req.path_str[start_index:]

        # 如果缓存中没有结果，则重新请求并缓存结果
        if not file_list:
            file_list = []
            loop_index=1
            sha1 = None
            maker=''
            while True:
                parent_file_id=""
                if folderId == "":
                    parent_file_id="root"
                else:
                    parent_file_id=folderId
                url="https://openapi.aliyundrive.com/adrive/v1.0/openFile/list"
                list_req=json.dumps({
                    "drive_id":self.driveId,
                    "parent_file_id":parent_file_id,
                    "limit": 200,
                    "fields": "*",
                    "order_by": "updated_at",
                    "order_direction": "DESC",
                    "maker":maker
                })
                try:
                    response = requests.post(url, data=list_req,verify=False,headers=self.headers, timeout=100)
                    # 如果请求失败，则抛出异常
                    response.raise_for_status()
                except requests.exceptions.RequestException as e:
                    print(e)
                    self.refresh_token()
                    response = requests.post(url, data=list_req,verify=False,headers=self.headers, timeout=100)
                if response.status_code == 200:
                    result = json.loads(response.text)
                    for file in result['items']:
                        kind = '1'
                        filesize = 0
                        download_url = None
                        if file['type']=="folder":
                            kind = '0'
                        else:
                            sha1 = file['content_hash']
                            download_url=file['url']
                        #2023-06-12T06:37:57.138Z
                        dt = datetime.strptime(file['created_at'], '%Y-%m-%dT%H:%M:%S.%fZ')
                        ts_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                        dav_file = DavFile(id=file['file_id'],provider=self.provider,parent_id=file['parent_file_id'],kind=kind,name=file['name'],size=str(file['size']),create_time=ts_str,sha1=sha1,download_url=download_url) 
                        file_list.append(dav_file)
                    # 暂时不知道maker是啥
                    if 'maker' not in result or len(result['maker'])<2:
                        break
                    else:
                        maker = result['maker']
                    loop_index+=1
                    time.sleep(self.sleep_time)
                else:
                    print("无法获取文件列表")
                    break
            self.cache.set(f"aliyundrive-{self.provider}-files-{folderId}", file_list, timeout=self.cache_time)
        return file_list

    # 文件下载地址 返回下载地址
    def get_url(self,dav_file:DavFile):
        # 在列表页已经获得无需再次请求
        # download_url = self.cache.get(f"onedrive-{self.provider}-files-{dav_file.file_id}-url")
        # # 如果缓存中没有结果，则重新请求并缓存结果
        # if download_url:
        #     return download_url
        # url="{}/v1.0/me/drive/items/{}?select=id,@microsoft.graph.downloadUrl".format(self.driveHost["Api"], dav_file.file_id)
        # try:
        #     response = requests.get(url, verify=False, headers=self.headers, timeout=100)
        #     # 如果请求失败，则抛出异常
        #     response.raise_for_status()
        # except requests.exceptions.RequestException as e:
        #     print(e)
        #     self.refresh_token()            
        #     response = requests.get(url, verify=False,headers=self.headers, timeout=100)
        # result = json.loads(response.text)
        # download_url = result['@microsoft.graph.downloadUrl']
        #设置三小时后过期,这个本身带的有oss参数
        # current_timestamp_sec = round(time.time())
        # expires_timestamp_sec = current_timestamp_sec+10800
        # download_expires_url = ""
        # if '?' in download_url:
        #     download_expires_url=f"{download_url}&x-oss-expires={expires_timestamp_sec}"
        # else:
        #     download_expires_url=f"{download_url}?x-oss-expires={expires_timestamp_sec}"
        #self.cache.set(f"aliyundrive-{self.provider}-files-{dav_file.file_id}-url", download_expires_url, timeout=self.url_cache_time)
        download_expires_url=""
        return download_expires_url

    # 以下都是辅助方法
    def refresh_token(self) -> str:
        loop_index = 1
        access_token = ''
        refresh_token = ''
        while True:
            url ="https://aliyundrive-oauth.messense.me/oauth/access_token"
            d = json.dumps({
                "grant_type":"refresh_token",
                "refresh_token": self.refreshToken,
            })
            r = requests.post(url, verify=False, data=d)
            result = json.loads(r.text)
            if 'access_token' not in result:
                refresh_token = 'error'
                access_token = 'error'
            else:
                refresh_token = result['refresh_token']
                access_token = result['access_token']
                break
            if loop_index>2:
                break
            loop_index+=1

        if access_token == 'error':
            print("无法获取token请稍后再试")
        else:
            self.config['refresh_token']=refresh_token
            self.config['access_token']=access_token
            self.driver.put(self.configFileName, data=json.dumps(self.config))
            self.accessToken = access_token
            self.headers['Authorization']='Bearer '+self.accessToken
    

    def get_drive_id(self) -> str:
        loop_index = 1
        drive_id = ""
        while True:
            url ="https://openapi.aliyundrive.com/adrive/v1.0/user/getDriveInfo"
            r = requests.post(url, headers=self.headers,verify=False)
            result = json.loads(r.text)
            if 'default_drive_id' not in result:
                drive_id = 'error'
            else:
                drive_id = result['default_drive_id']
                break
            if loop_index>2:
                break
            loop_index+=1

        if drive_id == 'error':
            print("无法获取drive_id请稍后再试")
        else:
            self.config['drive_id'] = drive_id
            self.driver.put(self.configFileName, data=json.dumps(self.config))
            self.driveId = drive_id

