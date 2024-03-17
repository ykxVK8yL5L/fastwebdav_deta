import json, requests
import time
from datetime import datetime
import re
import math
import hashlib
from cachelib import SimpleCache
import os
import sys
import urllib.parse


sys.path.append(os.path.abspath('../'))
from schemas.schemas import *
from deta import Deta

class Cloudreve():
    '''
    Cloudreve:Cloudreve
    '''
    def __init__(self,provider='',url='',username='',password=''):
        # 创建配置文件对象 注provider必填 
        '''
        :param provider: 模型实例名称
        :param url: Cloudreve的网址，没有开启登陆验证码的才可以成功
        :param username: 登陆用户名
        :param password: 登陆密码
        '''
        if url.endswith("/"):
            url = url[:-1]
        deta = Deta()
        self.driver = deta.Drive("Cloudreve")
        self.config = {}
        self.configFileName = provider+".txt"
        self.provider = provider
        self.url = url
        self.username = username
        self.password = password
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
            "Origin":self.url,
            "Referer":self.url,
        }

        try:
            response=self.driver.get(self.configFileName)
            self.config = json.loads(response.read())
        except:
            # 如果配置文件不存在，创建一个空的配置文件
            self.driver.put(self.configFileName, data=json.dumps({}))        
            self.refresh_token()          
                
        if 'refresh_token' in self.config:
            self.accessToken = self.config['access_token']
        else:
            self.refresh_token()



  
    # 文件列表方法 返回DavFile列表 请求内容为ListRequest，默认根目录ID为root
    def list_files(self, list_req:ListRequest):
        folderId=list_req.parent_file_id
        if folderId=='root':
            folderId=""
        file_list = self.cache.get(f"cloudreve-{self.provider}-files-{folderId}")

        path_str = list_req.path_str
        if list_req.parent_file_id=='root':
            path_str="/"
        else:
            start_index=list_req.path_str.find('/',1)
            path_str=list_req.path_str[start_index:]
            if path_str.endswith("/"):
                path_str = path_str[:-1]
            
        path_str = urllib.parse.quote_plus(path_str)
        headers =self.get_headers()
        
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
                url=f"{self.url}/api/v3/directory"+path_str
                print(url)
                try:
                    response = requests.get(url,verify=False,headers=headers, timeout=100)
                    # 如果请求失败，则抛出异常
                    response.raise_for_status()
                except requests.exceptions.RequestException as e:
                    print(e)
                    self.refresh_token()
                    headers =self.get_headers()
                    response = requests.get(url,verify=False,headers=headers, timeout=100)
                result = json.loads(response.text)
                if result['code'] == 401:
                    self.refresh_token()
                    headers =self.get_headers()
                    response = requests.get(url,verify=False,headers=headers, timeout=100)

                if response.status_code == 200:
                    result = json.loads(response.text)
                    for file in result['data']['objects']:
                        kind = '1'
                        filesize = 0
                        download_url = None
                        if file['type']=="dir":
                            kind = '0'
                        else:
                            filesize = file['size']
                        #2023-06-12T06:37:57.138Z
                        # dt = datetime.strptime(file['date'], '%Y-%m-%dT%H:%M:%S.%fZ')
                        date_obj = datetime.strptime(file['date'], "%Y-%m-%dT%H:%M:%S%z")
                        ts_str = date_obj.strftime('%Y-%m-%d %H:%M:%S')
                        dav_file = DavFile(id=file['id'],provider=self.provider,parent_id=parent_file_id,kind=kind,name=file['name'],size=str(filesize),create_time=ts_str,sha1=sha1,download_url=download_url) 
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
            self.cache.set(f"cloudreve-{self.provider}-files-{folderId}", file_list, timeout=self.cache_time)
        return file_list

    # 文件下载地址 返回下载地址
    def get_url(self,dav_file:DavFile):
        # 在列表页已经获得无需再次请求
        download_url = self.cache.get(f"cloudreve-{self.provider}-files-{dav_file.file_id}-url")
        # # 如果缓存中没有结果，则重新请求并缓存结果
        if download_url:
            return download_url
        requrl="{}/api/v3/file/source".format(self.url, dav_file.file_id)
        headers =self.get_headers()
        try:
            payload = "{\"items\":[\""+dav_file.file_id+"\"]}"
            response = requests.post(requrl,data=payload, verify=False, headers=headers, timeout=100)
            # 如果请求失败，则抛出异常
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(e)
            self.refresh_token()            
            response = requests.post(requrl,data=payload,verify=False,headers=headers, timeout=100)
        result = json.loads(response.text)
        download_url = result['data'][0]['url']
        #设置三小时后过期,这个本身带的有oss参数
        current_timestamp_sec = round(time.time())
        expires_timestamp_sec = current_timestamp_sec+10800
        download_expires_url = ""
        if '?' in download_url:
            download_expires_url=f"{download_url}&x-oss-expires={expires_timestamp_sec}"
        else:
            download_expires_url=f"{download_url}?x-oss-expires={expires_timestamp_sec}"
        self.cache.set(f"cloudreve-{self.provider}-files-{dav_file.file_id}-url", download_expires_url, timeout=self.url_cache_time)
        return download_expires_url

    # 以下都是辅助方法
    def refresh_token(self) -> str:
        loop_index = 1
        access_token = ''
        while True:
            url = self.url
            if url.endswith("/"):
                url = url[:-1]
            session_url = url+"/api/v3/user/session"
            payload = "{\"userName\":\""+self.username+"\",\"Password\":\""+self.password+"\",\"captchaCode\":\"\"}"
            headers = {
                'sec-ch-ua': '"Not.A/Brand";v="8", "Chromium";v="114", "Google Chrome";v="114"',
                'Accept': 'application/json, text/plain, */*',
                'Content-Type': 'application/json;charset=UTF-8',
                'Referer': url+'/login',
                'sec-ch-ua-mobile': '?0',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
            }
            response = requests.request("POST", session_url, headers=headers, data=payload,verify=False)
            cookiedict = requests.utils.dict_from_cookiejar(response.cookies)
            access_token=cookiedict["cloudreve-session"]
            result = json.loads(response.text)
            if result['code'] == 0:
                break
            if loop_index>=3:
                break
            loop_index = loop_index+1

        if access_token == 'error':
            print("无法获取token请稍后再试")
        else:
            self.config['access_token']=access_token
            self.driver.put(self.configFileName, data=json.dumps(self.config))
            self.accessToken = access_token
            
    def get_headers(self):
        cookie_cloudreve=self.accessToken
        base_url= self.url
        parsed_url = urllib.parse.urlparse(base_url)
        host = parsed_url.netloc 
        headers = {
            'authority': host,
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'content-type': 'application/json;charset=UTF-8',
            'cookie': 'cloudreve-session='+cookie_cloudreve,
            'origin': base_url,
            'referer': base_url+'/home?path=%2F',
            'sec-ch-ua': '"Chromium";v="116", "Not)A;Brand";v="24", "Google Chrome";v="116"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36'
        }
        return headers


