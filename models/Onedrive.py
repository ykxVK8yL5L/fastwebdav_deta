import json, requests
import time
from datetime import datetime
import re
import math
import hashlib
from cachelib import SimpleCache
import os
import sys
import configparser
sys.path.append(os.path.abspath('../'))
from schemas.schemas import *
from deta import Deta

class Onedrive():
    '''
    Onedrive:Onedrive网盘
    '''
    def __init__(self,provider='',region='',rootPath='',clientID='',clientSecret='',redirectUri='',refreshToken=''):
        # 创建配置文件对象 参数对照alist 注意provider必填
        '''
        :param provider: 模型实例名称
        :param region: 地区
        :param rootPath: 根文件夹路径
        :param clientID: 客户端ID
        :param clientSecret: 客户端密钥
        :param redirectUri: 重定向 Uri
        :param refreshToken: 刷新令牌
        '''
        onedriveHostMap = {
            "global": {
                "Oauth": "https://login.microsoftonline.com",
                "Api": "https://graph.microsoft.com",
            },
            "cn": {
                "Oauth": "https://login.chinacloudapi.cn",
                "Api": "https://microsoftgraph.chinacloudapi.cn",
            },
            "us": {
                "Oauth": "https://login.microsoftonline.us",
                "Api": "https://graph.microsoft.us",
            },
            "de": {
                "Oauth": "https://login.microsoftonline.de",
                "Api": "https://graph.microsoft.de",
            },
        }
        deta = Deta()
        self.driver = deta.Drive("Onedrive")
        self.config = {}
        self.configFileName = provider+".txt"
        self.provider = provider
        self.region = region
        self.rootPath = rootPath
        self.clientID = clientID
        self.clientSecret = clientSecret
        self.redirectUri = redirectUri
        self.refreshToken = refreshToken
        self.accessToken = ""
        self.driveHost=onedriveHostMap[self.region]
        self.cache = SimpleCache()
        # 防止请求过于频繁，用于请求间隔时间
        self.sleep_time = 0.005
        # 缓存结果时间默认10分钟
        self.cache_time = 600
        self.url_cache_time = 600
        self.headers = {
            "user-agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.93 Safari/537.36",
            "content-type":"application/json;charset=UTF-8",
        }
       
        try:
            response=self.driver.get(self.configFileName)
            self.config = json.loads(response.read())
            self.refreshToken = self.config['refresh_token']
            self.accessToken = self.config['access_token']
            self.headers['Authorization']='Bearer '+self.accessToken
        except:
            # 如果配置文件不存在，创建一个空的配置文件
            self.driver.put(self.configFileName, data=json.dumps({}))        
            self.refresh_token()   
                
                
  
    # 文件列表方法 返回DavFile列表 请求内容为ListRequest，默认根目录ID为root
    def list_files(self, list_req:ListRequest):
        folderId=list_req.parent_file_id
        if folderId=='root':
            folderId=""
        file_list = self.cache.get(f"onedrive-{self.provider}-files-{folderId}")

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
            nextLink=''
            while True:
                api_url=""
                if folderId == "":
                    api_url="{}/v1.0/me/drive/root".format(self.driveHost["Api"])
                else:
                    api_url="{}/v1.0/me/drive/root:{}:".format(self.driveHost["Api"], path_str)
                if len(nextLink)>20:
                    api_url=nextLink
                url = api_url + "/children?$top=5000&$expand=thumbnails($select=medium)&$select=id,name,size,folder,lastModifiedDateTime,content.downloadUrl,file,parentReference"
                try:
                    response = requests.get(url, verify=False,headers=self.headers, timeout=100)
                    # 如果请求失败，则抛出异常
                    response.raise_for_status()
                except requests.exceptions.RequestException as e:
                    print(e)
                    self.refresh_token()
                    response = requests.get(url, verify=False,headers=self.headers, timeout=100)
                if response.status_code == 200:
                    result = json.loads(response.text)
                    for file in result['value']:
                        kind = '1'
                        if 'file' not in file:
                            kind = '0'
                        else:
                            sha1 = file['file']['hashes']['quickXorHash']
                        
                        if file['parentReference']['path']=='/drive/root:':
                            file['parent_id']="root"
                        else:
                            file['parent_id']=file['parentReference']['id']
                        #2023-08-30T00:03:00Z
                        dt = datetime.strptime(file['lastModifiedDateTime'], '%Y-%m-%dT%H:%M:%SZ')
                        ts_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                        dav_file = DavFile(id=file['id'],provider=self.provider,parent_id=file['parent_id'],kind=kind,name=file['name'],size=str(file['size']),create_time=ts_str,sha1=sha1) 
                        file_list.append(dav_file)
                    if '@odata.nextLink' not in result or len(result['@odata.nextLink'])<2:
                        break
                    else:
                        nextLink = result['@odata.nextLink']
                    loop_index+=1
                    time.sleep(self.sleep_time)
                else:
                    print("无法获取文件列表")
                    break
            self.cache.set(f"onedrive-{self.provider}-files-{folderId}", file_list, timeout=self.cache_time)
        return file_list

    # 文件下载地址 返回下载地址
    def get_url(self,dav_file:DavFile):
        download_url = self.cache.get(f"onedrive-{self.provider}-files-{dav_file.file_id}-url")
        # 如果缓存中没有结果，则重新请求并缓存结果
        if download_url:
            return download_url

        url="{}/v1.0/me/drive/items/{}?select=id,@microsoft.graph.downloadUrl".format(self.driveHost["Api"], dav_file.file_id)
        try:
            response = requests.get(url, verify=False, headers=self.headers, timeout=100)
            # 如果请求失败，则抛出异常
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(e)
            self.refresh_token()            
            response = requests.get(url, verify=False,headers=self.headers, timeout=100)
        result = json.loads(response.text)
        download_url = result['@microsoft.graph.downloadUrl']
        #设置三小时后过期
        current_timestamp_sec = round(time.time())
        expires_timestamp_sec = current_timestamp_sec+10800
        download_expires_url = ""
        if '?' in download_url:
            download_expires_url=f"{download_url}&x-oss-expires={expires_timestamp_sec}"
        else:
            download_expires_url=f"{download_url}?x-oss-expires={expires_timestamp_sec}"
        self.cache.set(f"onedrive-{self.provider}-files-{dav_file.file_id}-url", download_expires_url, timeout=self.url_cache_time)
        return download_expires_url

    # 以下都是辅助方法
    def refresh_token(self) -> str:
        loop_index = 1
        access_token = ''
        refresh_token = ''
        while True:
            url = self.driveHost["Oauth"]+ "/common/oauth2/v2.0/token"
            d = {
                "grant_type":    "refresh_token",
                "client_id":     self.clientID,
                "client_secret": self.clientSecret,
                "redirect_uri":  self.redirectUri,
                "refresh_token": self.refreshToken,
            }
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
    
   
