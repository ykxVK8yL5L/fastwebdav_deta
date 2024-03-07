import json, requests
import time
import datetime
from fastapi import HTTPException
import re
import math
import hashlib
from cachelib import SimpleCache
import os
import sys
import configparser
import base64
sys.path.append(os.path.abspath('../'))
from schemas.schemas import *
from webdav4.client import Client
from urllib.parse import urlparse

class WebDAV():
    '''
    WebDAV:WebDAV
    '''
    def __init__(self,provider='',url='',username='',password=''):
        #注意provider必填
        '''
        :param provider: 模型实例名称
        :param url: webdav地址
        :param username: 登陆用户名
        :param password: 登陆密码
        '''
        # 创建配置文件对象
        self.provider = provider
        self.url = url
        self.username = username
        self.password = password
        self.cache = SimpleCache()
        # 防止请求过于频繁，用于请求间隔时间
        self.sleep_time = 0.005
        # 缓存结果时间默认10分钟
        self.cache_time = 600
        auth_token = base64.b64encode(f"{self.username}:{self.password}".encode('utf-8')).decode('utf-8')
        self.headers = {
            "user-agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.93 Safari/537.36",
            "Authorization": 'Basic '+ auth_token
        }
        self.client = Client(self.url, auth=(self.username, self.password),verify=False)

        parsed_url = urlparse(self.url)
        self.netloc = parsed_url.netloc
        self.hostname = parsed_url.hostname
        self.path = parsed_url.path
        self.scheme = parsed_url.scheme


    # 文件列表方法 返回DavFile列表 请求内容为ListRequest，默认根目录ID为root
    def list_files(self, list_req:ListRequest):
        # 计算请求路径 
        path_str = list_req.path_str
        if list_req.parent_file_id=='root':
            path_str="/"
        else:
            start_index=list_req.path_str.find('/',1)
            path_str=list_req.path_str[start_index:]
        
        file_list = self.cache.get(f"{self.provider}-{self.username}-files-{path_str}")
        # 如果缓存中没有结果，则重新请求并缓存结果
        if not file_list:
            file_list = []
            files = self.client.ls(path_str,detail=True)
            for file in files:
                kind = 0
                filesize = 0
                download_url = None
                now = datetime.datetime.now()
                # 格式化时间为字符串
                formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
                if file['display_name'] is None:
                    file['display_name']=os.path.basename(file['name'])

                if file['modified'] is not None:
                    #dt = datetime.strptime(file['modified'], '%Y-%m-%dT%H:%M:%SZ')
                    dt = file['modified']
                    formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                if file['etag'] is None:
                    file['etag'] = base64.b64encode(f"{file['display_name']}:{file['href']}".encode('utf-8')).decode('utf-8')

                if  file['type']!='directory':
                    kind = 1
                    filesize = file['content_length']
                    #download_url = self.scheme+"://"+self.netloc+file['href']
                    #要直接播放所以目前采用用户名:密码@服务器的方式，极不安全有好的解决方案再改吧
                    download_url = self.scheme+"://"+self.username+":"+self.password+"@"+self.netloc+file['href']

                playe_headers = json.dumps(self.headers)
                dav_file = DavFile(id=file['etag'].replace('"',''),provider=self.provider,parent_id=list_req.parent_file_id,kind= kind,name=file['display_name'],size=str(filesize),create_time=formatted_time,download_url=download_url,play_headers=playe_headers) 
                file_list.append(dav_file)
            file_list=sorted(file_list, key = lambda x: (-x.kind,x.create_time),reverse=True)
            self.cache.set(f"{self.provider}-{self.username}-files-{path_str}", file_list, timeout=self.cache_time)
        return file_list

    # 文件下载地址 返回下载地址
    def get_url(self,dav_file:DavFile):
        #这个url已经在列表页面得到，不需要再请求保留添加过期注释供参考
        #设置三小时后过期
        # current_timestamp_sec = round(time.time())
        # expires_timestamp_sec = current_timestamp_sec+10800
        # download_url = result['data']
        # download_expires_url = ""
        # if '?' in download_url:
        #     download_expires_url=f"{download_url}&x-oss-expires={expires_timestamp_sec}"
        # else:
        #     download_expires_url=f"{download_url}?x-oss-expires={expires_timestamp_sec}"
        return ""

    # 删除文件
    def remove_file(self,remove_file_req:RemoveFileRequest):
        folderId = remove_file_req.dav_file.parent_id
        path_str = remove_file_req.remove_path
        if folderId=='root':
            folderId='0'
        removed_file_path=path_str[path_str.find('/',1):]
        self.client.remove(removed_file_path)
        parent_dir=os.path.dirname(removed_file_path)
        self.cache.delete(f"{self.provider}-{self.username}-files-{parent_dir}")
        return remove_file_req.dav_file


    # 创建文件夹
    def create_folder(self,create_folder_req:CreateFolderRequest):
        now = datetime.datetime.now()
        # 格式化时间为字符串
        formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
        folderId = create_folder_req.parent_id
        path_str = create_folder_req.path_str
        if folderId=='root':
            folderId='0'
        created_parent_dir=path_str[path_str.find('/',1):]
        if path_str.find('/',1)==-1:
            created_parent_dir="/"
        created_folder = created_parent_dir+"/"+create_folder_req.name
        self.client.mkdir(created_folder)
        self.cache.delete(f"{self.username}-files-{created_parent_dir}")
        etag = base64.b64encode(f"{create_folder_req.name}:{created_folder}".encode('utf-8')).decode('utf-8')
        dav_file = DavFile(id=etag,parent_id=create_folder_req.parent_id,provider=create_folder_req.parend_file.provider,kind=0,name=create_folder_req.name,size='0',create_time=formatted_time)
        return dav_file

    # 移动文件
    def move_file(self,move_file_req:MoveFileRequest):
        folderId = move_file_req.dav_file.parent_id
        if folderId=='root':
            folderId='0'
        # from_path = move_file_req.from_path.split('/', 2)[-1]
        # to_path = move_file_req.to_path.split('/', 2)[-1]
        from_path=move_file_req.from_path[move_file_req.from_path.find('/',1):]
        to_path=move_file_req.to_path[move_file_req.to_path.find('/',1):]
        self.client.move(from_path,to_path)
        from_dir=os.path.dirname(from_path)
        to_dir=os.path.dirname(to_path)
        self.cache.delete(f"{self.provider}-{self.username}-files-{from_dir}")
        self.cache.delete(f"{self.provider}-{self.username}-files-{to_dir}")
        return move_file_req.dav_file
    
