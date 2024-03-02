import json, requests
import time
from datetime import datetime
import re
import math
import hashlib
from cachelib import SimpleCache
from fastapi import HTTPException
import os
import sys
sys.path.append(os.path.abspath('../'))
from schemas.schemas import *


class StreamTape():
    '''
    https://streamtape.com - Streamtape
    '''
    def __init__(self,provider='',login='',key=''):
        #注意provider必填
        '''
        :param provider: 模型实例名称
        :param login: API login 可在https://streamtape.com/accpanel#accsettings获得 API/FTP Username
        :param key: API key 可在https://streamtape.com/accpanel#accsettings API/FTP Credentials获得
        '''
        # 创建配置文件对象
        self.provider = provider
        self.login = login
        self.key = key
        self.cache = SimpleCache()
        # 防止请求过于频繁，用于请求间隔时间
        self.sleep_time = 0.005
        # 缓存结果时间默认10分钟
        self.cache_time = 600
        self.headers = {
            "user-agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/27.0.1453.93 Safari/537.36",
            "content-type":"application/json;charset=UTF-8",
        }
       
    # 文件列表方法 返回DavFile列表 请求内容为ListRequest，默认根目录ID为root
    def list_files(self, list_req:ListRequest):
        folderId=list_req.parent_file_id
        folder_query = '&folder='+folderId
        if folderId=='root':
            folder_query=''
        file_list = self.cache.get(f"streamtape-{self.login}-{folderId}")
        # 如果缓存中没有结果，则重新请求并缓存结果
        if not file_list:
            file_list = []
            url = f"https://api.streamtape.com/file/listfolder?login={self.login}&key={self.key}{folder_query}"
            try:
                response = requests.get(url, verify=False, headers=self.headers, timeout=100)
                # 如果请求失败，则抛出异常
            except requests.exceptions.RequestException as e:
                print("无法获取文件信息")
            result = json.loads(response.text)
            if result['msg']!='OK':
                raise HTTPException(status_code=400, detail="无法获取文件列表")
            for child in result['result']['folders']:
                file=child
                filesize = 0
                # 格式化时间为字符串
                now = datetime.now()
                # 格式化时间为字符串
                formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
                dav_file = DavFile(id=file['id'],provider=self.provider,parent_id=folderId,kind= 0,name=file['name'],size=str(filesize),create_time=formatted_time) 
                file_list.append(dav_file)
            for file in result['result']['files']:
                filesize = file['size']
                # 格式化时间为字符串
                dt = datetime.fromtimestamp(file['created_at'])
                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                dav_file = DavFile(id=file['linkid'],provider=self.provider,parent_id=folderId,kind=1,name=file['name'],size=str(filesize),create_time=formatted_time) 
                file_list.append(dav_file)
            self.cache.set(f"streamtape-{self.login}-{folderId}", file_list, timeout=self.cache_time)
        return file_list

    # 文件下载地址 返回下载地址
    def get_url(self,dav_file:DavFile):
        #这个url已经在列表页面得到，不需要再请求
        download_url = self.cache.get(f"streamtape-{self.login}-{dav_file.file_id}-url")
        # 如果缓存中没有结果，则重新请求并缓存结果
        if download_url:
            return download_url
        ticket_url = f"https://api.streamtape.com/file/dlticket?file={dav_file.file_id}&login={self.login}&key={self.key}"
        try:
            ticket_response = requests.get(ticket_url, verify=False, headers=self.headers, timeout=100)
            # 如果请求失败，则抛出异常
        except requests.exceptions.RequestException as e:
            print("无法获取文件信息")
        ticket_result = json.loads(ticket_response.text)
        if ticket_result['msg']!='OK':
            raise HTTPException(status_code=400, detail="无法获取下载的ticket")
        time.sleep(ticket_result['result']['wait_time'])
        download_url = f"https://api.streamtape.com/file/dl?file={dav_file.file_id}&ticket={ticket_result['result']['ticket']}"
        try:
            download_response = requests.get(download_url, verify=False, headers=self.headers, timeout=100)
            # 如果请求失败，则抛出异常
        except requests.exceptions.RequestException as e:
            print("无法获取文件下载信息")
        download_result = json.loads(download_response.text)
        if download_result['msg']!='OK':
            raise HTTPException(status_code=400, detail="无法获取下载地址")
        download_url = download_result['result']['url']
        #设置三小时后过期
        current_timestamp_sec = round(time.time())
        expires_timestamp_sec = current_timestamp_sec+10800
        if '?' in download_url:
            download_url=f"{download_url}&x-oss-expires={expires_timestamp_sec}"
        else:
            download_url=f"{download_url}?x-oss-expires={expires_timestamp_sec}"
        self.cache.set(f"streamtape-{self.login}-{dav_file.file_id}-url", download_url, timeout=self.cache_time)
        return download_url


    def create_folder(self,create_folder_req:CreateFolderRequest):
        now = datetime.datetime.now()
        # 格式化时间为字符串
        formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
        folderId = create_folder_req.parent_id
        folder_query = '&pid='+folderId
        if folderId=='root':
            folder_query=''
        create_url = f"https://api.streamtape.com/file/createfolder?login={self.login}&key={self.key}&name={create_folder_req.dav_file.name}&pid={folder_query}"
        response = requests.get(create_url,verify=False, headers=self.headers, timeout=100)
        result = json.loads(response.text)
        if result['msg']!='OK':
            raise HTTPException(status_code=400, detail="无法创建文件夹")
        if result['code']==200:
            self.cache.delete(f"streamtape-{self.login}-{folderId}")
            dav_file = DavFile(id=result['result']['folderid'],parent_id=create_folder_req.parent_id,provider=create_folder_req.parend_file.provider,kind=0,name=create_folder_req.name,size='0',create_time=formatted_time)
            return dav_file
        else:
            raise HTTPException(status_code=400, detail="无法创建文件夹")



    def remove_file(self,remove_file_req:RemoveFileRequest):
        dav_file = remove_file_req.dav_file
        folderId = dav_file.parent_id
        remove_url = f"https://api.streamtape.com/file/delete?login={self.login}&key={self.key}&file={dav_file.file_id}"
        if dav_file.kind==0:
            remove_url = f"https://api.streamtape.com/file/deletefolder?login={self.login}&key={self.key}&folder={dav_file.file_id}"
        print(remove_url)
        response = requests.get(remove_url, verify=False, headers=self.headers, timeout=100)
        result = json.loads(response.text)
        print(result)
        if result['msg']!='OK':
            raise HTTPException(status_code=400, detail="无法删除文件")
        if result['status']==200:
            self.cache.delete(f"streamtape-{self.login}-{folderId}")
            return dav_file
        else:
            raise HTTPException(status_code=400, detail="无法删除文件")



    # 辅助方法
    def pluck(self,lst, key):
        return [x.get(key) for x in lst]
