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

class PikPak():
    '''
    PikPak:10T网盘
    '''
    def __init__(self,provider='',username='',password=''):
        # 创建配置文件对象 注意provider必填
        '''
        :param provider: 模型实例名称
        :param username: 用户名
        :param password: 密码
        '''
        deta = Deta()
        self.driver = deta.Drive("PikPak")
        self.config = {}
        self.configFileName = username+".txt"
        self.provider = provider
        self.username = username
        self.password = password
        self.token = ''
        self.cache = SimpleCache()
        # 防止请求过于频繁，用于请求间隔时间
        self.sleep_time = 0.005
        # 缓存结果时间默认10分钟
        self.cache_time = 600
        self.headers = {
            "user-agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.93 Safari/537.36",
            "content-type":"application/json;charset=UTF-8",
        }
        
        try:
            response=self.driver.get(self.configFileName)
            self.config = json.loads(response.read())
        except:
            # 如果配置文件不存在，创建一个空的配置文件
            self.driver.put(self.configFileName, data=json.dumps({}))
                
        if  'token' in self.config:
            self.token = self.config['token']
            self.headers['Authorization']='Bearer '+self.token
        else:
            self.refresh_token()
  


    # 文件列表方法 返回DavFile列表 请求内容为ListRequest，默认根目录ID为root
    def list_files(self, list_req:ListRequest):
        folderId=list_req.parent_file_id
        if folderId=='root':
            folderId=''
        file_list = self.cache.get(f"{self.username}-files-{folderId}")
        # 如果缓存中没有结果，则重新请求并缓存结果
        if not file_list:
            file_list = []
            loop_index=1
            sha1 = None
            page_token=''
            while True:
                rdata = json.dumps({'parent_id': folderId,'page_token': page_token})
                url = 'https://api-drive.mypikpak.com/drive/v1/files?thumbnail_size=SIZE_LARGE&with_audit=true&parent_id='+folderId+'&page_token='+page_token+'&filters=%7B%22phase%22:%7B%22eq%22:%22PHASE_TYPE_COMPLETE%22%7D,%22trashed%22:%7B%22eq%22:false%7D%7D'
                self.headers['referer'] = "https://api-drive.mypikpak.com/drive/v1/files"
                try:
                    response = requests.get(url, verify=False,data=rdata, headers=self.headers, timeout=100)
                    # 如果请求失败，则抛出异常
                    response.raise_for_status()
                except requests.exceptions.RequestException as e:
                    self.refresh_token()
                    response = requests.get(url, verify=False,data=rdata, headers=self.headers, timeout=100)

                if response.status_code == 200:
                    result = json.loads(response.text)
                    for file in result['files']:
                        kind = '1'
                        if file['kind']=='drive#folder':
                            kind = '0'
                        else:
                            sha1 = file['hash']
                        
                        if len(file['parent_id'])==0:
                            file['parent_id']="root"
                        #2021-11-30T09:12:48.820+08:00
                        dt = datetime.fromisoformat(file['created_time'])
                        ts_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                        dav_file = DavFile(id=file['id'],provider=self.provider,parent_id=file['parent_id'],kind= kind,name=file['name'],size=str(file['size']),create_time=ts_str,sha1=sha1) 
                        file_list.append(dav_file)
                    if result['next_page_token'] is None or len(result['next_page_token'])<2:
                        break
                    else:
                        page_token = result['next_page_token']
                    loop_index+=1
                    time.sleep(self.sleep_time)
                else:
                    print("无法获取文件列表")
                    break
            self.cache.set(f"{self.username}-files-{folderId}", file_list, timeout=self.cache_time)
        return file_list

    # 文件下载地址 返回下载地址
    def get_url(self,dav_file:DavFile):
        self.headers['referer'] = "https://api-drive.mypikpak.com/drive/v1/files"
        if dav_file.file_id == '/':
            url = 'https://api-drive.mypikpak.com/drive/v1/files'
        else:
            url = 'https://api-drive.mypikpak.com/drive/v1/files/'+dav_file.file_id
        try:
            response = requests.get(url, verify=False, headers=self.headers, timeout=100)
            # 如果请求失败，则抛出异常
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.refresh_token()            
            response = requests.get(url, verify=False,headers=self.headers, timeout=100)

        result = json.loads(response.text)
        if result['medias'][0]['link']['url'] is None:
            download_url = result['web_content_link']
        else:
            download_url = result['medias'][0]['link']['url']
        #这个不能设置过期时间，否则会报403
        return download_url

    # 以下都是辅助方法
    def refresh_token(self) -> str:
        loop_index = 1
        token = ''
        while True:
            url = "https://user.mypikpak.com/v1/auth/signin"
            username = self.username
            password = self.password
            d = json.dumps({
            "captcha_token": "",
            "client_id": "YNxT9w7GMdWvEOKa",
            "client_secret": "dbw2OtmVEeuUvIptb1Coyg",
            "username": username,
            "password": password
            })
            r = requests.post(url, verify=False, data=d)
            result = json.loads(r.text)
            if 'access_token' not in result:
                token = 'error'
            else:
                token = result['access_token']
                break
            if loop_index>2:
                break
            loop_index+=1

        if token == 'error':
            print("无法获取token请稍后再试")
        else:
            self.token = self.config['token'] = token;
            self.driver.put(self.configFileName, data=json.dumps(self.config))
            self.headers['Authorization']='Bearer '+self.token
    
   
    
        
