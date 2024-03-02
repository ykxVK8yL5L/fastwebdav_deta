import json, requests
import time
import re
import math
from cachelib import SimpleCache
from fastapi import Request,HTTPException
import os
import sys
sys.path.append(os.path.abspath('../'))
from schemas.schemas import *
import hashlib
from urllib.parse import urlparse
from deta import Deta

TMP_FILE_API="https://tmp-api.vx-cdn.com/api_v2/file"
TMP_TOKEN_API="https://tmp-api.vx-cdn.com/api_v2/token"

class TmpLink():
    '''
    TmpLink:https://tmp.link钛盘，临时网盘
    '''
    def __init__(self,provider='',token=''):
        #注意provider必填
        '''
        :param provider: 模型实例名称
        :param token: 登陆token可在cli上传处获得
        '''
        deta = Deta()
        self.driver = deta.Drive("TmpLink")
        self.config = {}
        self.configFileName = provider+".txt"
        self.provider = provider
        self.token = token
        self.uid = ''
        self.cache = SimpleCache()
        # 防止请求过于频繁，用于请求间隔时间1秒
        self.sleep_time = 1
        # 缓存结果时间默认10分钟
        self.cache_time = 600
        # 分片大小
        self.slice_size = 33554432
        self.headers = {
            'authority': 'tmp-api.vx-cdn.com',
            'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': 'https://tmp.link',
            'referer': 'https://tmp.link/?tmpui_page=/app&listview=workspace',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
            'Cookie': f"PHPSESSID={self.token}",
        }
        
        try:
            response=self.driver.get(self.configFileName)
            self.config = json.loads(response.read())
        except:
            # 如果配置文件不存在，创建一个空的配置文件
            self.driver.put(self.configFileName, data=json.dumps({}))
          
        if 'token' in self.config:
            self.token = self.config['token']
            self.uid = self.config['uid']
        else:
            self.set_user()



    # 文件列表方法 返回DavFile列表 请求内容为ListRequest,默认根目录ID为root
    def list_files(self, list_req:ListRequest):
        folderId=list_req.parent_file_id
        file_list = self.cache.get(f"{self.token}-files-{folderId}")
        # 如果缓存中没有结果，则重新请求并缓存结果
        if not file_list:
            file_list = []
            fileinfo=self.getFileInfo()
            list_range=math.ceil(int(fileinfo['nums'])/50)
            for x in range(0, list_range):
                payload = {
                    'action': 'workspace_filelist_page',
                    'page': x,
                    'token': self.token,
                    'sort_type':'',
                    'sort_by':'',
                    'photo':0,
                    'search':'',
                }
                response = requests.post(TMP_FILE_API, verify=False,headers=self.headers, data=payload)
                result = json.loads(response.text)
                for file in result['data']:
                    dav_file = DavFile(id=file['ukey'],provider=self.provider,parent_id='root',kind= 1,name=file['fname'],size=file['fsize'],create_time=file['ctime']) 
                    file_list.append(dav_file)
                time.sleep(self.sleep_time)
            self.cache.set(f"{self.token}-files-{folderId}", file_list, timeout=self.cache_time)
        return file_list

    # 文件下载地址 返回下载地址
    def get_url(self,dav_file:DavFile):
        token = self.getToken()
        data = {
            'action': 'download_req',
            'ukey': dav_file.file_id,
            'token': self.token,
            'captcha': token,
        }
        response = requests.post(TMP_FILE_API,verify=False, headers=self.headers, data=data)
        result = json.loads(response.text)
        #设置三小时后过期
        current_timestamp_sec = round(time.time())
        expires_timestamp_sec = current_timestamp_sec+10800
        download_url = result['data']
        download_expires_url = ""
        if '?' in download_url:
            download_expires_url=f"{download_url}&x-oss-expires={expires_timestamp_sec}"
        else:
            download_expires_url=f"{download_url}?x-oss-expires={expires_timestamp_sec}"
        return download_expires_url
    
    # 初始化文件上传，如果不需要的话根据需要自己构造返回的InitUploadResponse
    def init_upload(self,init_file:InitUploadRequest):
        # 第一次请求创建文件，貌似没啥用只是提交一下
        prepare_data = {
            "sha1":0,
            "filename": init_file.name,
            "filesize": init_file.size,
            "model": "2",
            "mr_id": "0",
            "skip_upload": "0",
            "action": "prepare_v4",
            "token": self.token,
        }
        prepare_response = requests.post(TMP_FILE_API,verify=False, headers=self.headers, data=prepare_data)
        print(prepare_response.text)
        # 每次得到操作的验证码
        captcha = self.getToken()
        # 开始上传请求，这个是最主要操作，获取到上传的utoken 
        # 返回示例:
        # {
        #     "data": {
        #         "utoken": "xxxxxxxxxx",
        #         "uploader": "https:\/\/tmp-hd4.vx-cdn.com",
        #         "src": "42.224.203.231"
        #     },
        #     "status": 1,
        #     "debug": []
        # }
        upload_request_data = {
            "action":"upload_request_select2",
            "token": self.token,
            "filesize": init_file.size,
            "captcha": captcha,
        }
        upload_request_response = requests.post(TMP_FILE_API,verify=False, headers=self.headers, data=upload_request_data)
        result = json.loads(upload_request_response.text)
        print(upload_request_response.text)
        if result['status']!=1:
            raise HTTPException(status_code=400, detail="初始化请求失败")
        init_data = InitResponseData(uploader=result['data']['uploader'],fileName=init_file.name,fileSize=init_file.size,fileSha1=init_file.sha1,chunkSize=self.slice_size)
        response = InitUploadResponse(code=200,message="文件已经上传",data=init_data,extra=result['data']['utoken'])
        return response

    # 文件分片上传
    def upload_chunk(self,slice_req:SliceUploadRequest,filedata:bytes):
        parsed_url = urlparse(slice_req.oss_args.uploader)
        host = parsed_url.hostname
        prepare_headers = {
            "authority": host,
            "Host": host,
            "accept": "application/json, text/javascript, /; q=0.01",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://tmp.link",
            "referer": "https://tmp.link/",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "macOS",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
        }
        upload_url = slice_req.oss_args.uploader+"/app/upload_slice"
        # 获取准备信息 返回示例
        # {"status":3,"data":{"next":0,"total":2,"wait":2,"uploading":0,"success":0}}
        # uptoken为sha1加密：uid+file.name+file.size 但是目前官方网站有Bug
        sha1_str = str(self.uid)+slice_req.dav_file.name+slice_req.dav_file.size
        # 创建sha1对象
        sha1 = hashlib.sha1()
        # 更新字符串
        sha1.update(sha1_str.encode('utf-8'))
        # 获取加密后的字符串
        uptoken = sha1.hexdigest()
        prepare_data = {
            'token': self.token,
            'uptoken': uptoken,
            'action': 'prepare',
            'sha1': 0,
            'filename': slice_req.dav_file.name,
            'filesize': slice_req.dav_file.size,
            'slice_size': self.slice_size,
            'utoken': slice_req.oss_args.extra_init,
            'mr_id': 0,
            'model': 2,
        }
        prepare_response = requests.post(upload_url,verify=False, headers=prepare_headers, data=prepare_data)
        prepare_info = json.loads(prepare_response.text)
        if prepare_info['status']!=3:
            raise HTTPException(status_code=400, detail="无法获取分片信息")
        # 获取操作验证码
        captcha = self.getToken()
        # 上传操作 返回示例
        options_headers =  {
            'Host': host,
            'Accept': '*/*',
            'Access-Control-Request-Method': 'POST',
            'Origin': 'https://tmp.link',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://tmp.link/?tmpui_page=/app&listview=workspace',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }
        payload = {}
        options_response = requests.options(upload_url,verify=False,headers=options_headers,data=payload)
        # {"status":5,"data":"upload slice success"}
        upload_data = {
            'uptoken': uptoken,
            "sha1": 0,
            "index": prepare_info['data']['next'],
            "action": "upload_slice",
            "slice_size": slice_req.oss_args.chunkSize,
            "captcha":captcha,
        }
        upload_headers = {
            "Host": host,
            'Accept': '*/*',
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "content-type": "application/octet-stream",
            "origin": "https://tmp.link",
            "referer": "https://tmp.link/?tmpui_page=/app&listview=workspac",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "macOS",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
        }
        #upload_headers['content-type'] = 'multipart/form-data'
        files = {'filedata': ('slice', filedata,'application/octet-stream')}
        # if result['status']!=5:
        #     raise HTTPException(status_code=400, detail="分片上传失败")
        code = 200
        data = ''
        status = 0
        loop_index = 1
        while True:
            upload_response = requests.post(upload_url,verify=False, data=upload_data,files=files)
            result = json.loads(upload_response.text)
            print(f"第{loop_index}次上传尝试")
            print(upload_response.text)
            if loop_index >5:
                break
            if result['status'] == 5:
                code = 200
                data = result['data']
                status = result['status']
                break
            loop_index+=1
            time.sleep(self.sleep_time)

        upload_data = FileUploadInfo(fileName=slice_req.dav_file.name,fileSize=slice_req.dav_file.size,fileHash=slice_req.dav_file.sha1,chunkIndex=slice_req.current_chunk,chunkSize=slice_req.oss_args.chunkSize,uploadState=status)
        response = SliceUploadResponse(code=code,message=data, data=upload_data)
        return response
    
    # 分片上传完成后的处理
    def complete_upload(self,complete_req:CompleteUploadRequest):
        parsed_url = urlparse(complete_req.oss_args.uploader)
        host = parsed_url.hostname
        sha1_str = str(self.uid)+complete_req.dav_file.name+complete_req.dav_file.size
        sha1 = hashlib.sha1()
        sha1.update(sha1_str.encode('utf-8'))
        uptoken = sha1.hexdigest()
        complete_headers = {
            "authority": host,
            "Host": host,
            "accept": "application/json, text/javascript, /; q=0.01",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://tmp.link",
            "referer": "https://tmp.link/",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "macOS",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
        }
        complete_url = complete_req.oss_args.uploader+"/app/upload_slice"
        complete_data = {
            'token': self.token,
            'uptoken': uptoken,
            'action': 'prepare',
            'sha1': 0,
            'filename': complete_req.dav_file.name,
            'filesize': complete_req.dav_file.size,
            'slice_size': self.slice_size,
            'utoken': complete_req.oss_args.extra_init,
            'mr_id': 0,
            'model': 2,
        }
        complete_response = requests.post(complete_url,verify=False, headers=complete_headers, data=complete_data)
        complete_info = json.loads(complete_response.text)
        if complete_info['status']!=8:
            raise HTTPException(status_code=400, detail="无法获取分片信息")
        code = 400
        if complete_info['status']==8:
            code = 200
        response = CompleteUploadResponse(status=code,data=complete_info['data'])
        return response


    # 以下都是辅助方法
    def getToken(self):
        # 返回操作的验证码，示例
        # {
        #     "data": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        #     "status": 1,
        #     "debug": []
        # }
        payload = {
            'action': 'challenge',
            'token': self.token,
        }
        response = requests.post(TMP_TOKEN_API,verify=False, headers=self.headers, data=payload)
        result = json.loads(response.text)
        return result['data']

    def getFileInfo(self):
        data = {
            'action': 'total',
            'token': self.token,
        }
        response = requests.post(TMP_FILE_API,verify=False, headers=self.headers, data=data)
        result = json.loads(response.text)
        return result['data']
    
    def set_user(self) -> str:
    	# 响应示例
  #   	{
		#     "data": {
		#         "uid": "xxxxxxxxx",
		#         "lang": "cn",
		#         "storage": 0,
		#         "storage_used": 100000000,
		#         "private_storage_used": 0,
		#         "acv": "1",
		#         "acv_dq": "0",
		#         "group": {
		#             "level": 1,
		#             "storage": 0,
		#             "highspeed": true,
		#             "blue": true
		#         },
		#         "join": "2023-04-01",
		#         "total_files": "56",
		#         "total_filesize": "10000000000",
		#         "total_upload": "10000000000",
		#         "pf_confirm_delete": 0,
		#         "pf_bulk_copy": 0,
		#         "pf_mybg_light": 0,
		#         "pf_mybg_dark": 0,
		#         "pf_mybg_light_key": 0,
		#         "pf_mybg_dark_key": 0,
		#         "highspeed": true,
		#         "blue": true,
		#         "sponsor": false,
		#         "sponsor_time": "0000-00-00"
		#     },
		#     "status": 1,
		#     "debug": []
		# }
        loop_index = 1
        token = ''
        uid = ''
        while True:
            payload = {
                'action': 'get_detail',
                'token': self.token,
            }
            response = requests.post("https://tmp-api.vx-cdn.com/api_v2/user",verify=False, headers=self.headers, data=payload)
            result = json.loads(response.text)
            if 'uid' not in result['data']:
                print(f"第{loop_index}次无法获取uid")
                uid = 'error'
            else:
                uid = result['data']['uid']
                break 
            if loop_index>2:
                break
            loop_index+=1

        if uid == 'error':
            print("无法获取token请稍后再试")
        else:
            self.config['token'] = self.token
            self.config['uid'] = uid
            self.driver.put(self.configFileName, data=json.dumps(self.config))
            self.token = self.token
            self.uid = uid


