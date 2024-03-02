from pydantic import BaseModel,Field,Extra
from typing import Set, Union,Optional

class PostRequest(BaseModel):
    class Config:
        extra = Extra.allow

class DavFile(BaseModel):
    '''
    文件模型提供数据给webdav
    '''
    file_id: str = Field(title="文件ID",description="文件ID，如果是0和root需要注意",alias='id') 
    parent_id: str = Field(title="上级目录的ID",description="上级目录的ID,默认根目录为root需要特殊处理")
    provider: str = Field(title="模型实例的name",description="模型实例的name,通常不用管")
    kind: int = Field(title="文件类型",description="文件类型0为文件夹，1为文件") 
    name: str = Field(title="文件名称",description="文件名称") 
    oriname: Optional[str] = Field(None,title="文件原始名称",description="文件原始名称，加密情况下使用") 
    size: str = Field(title="文件大小",description="文件大小，注意返回需要为字符串")  
    create_time:str = Field(title="文件创建时间",description="文件创建时间，需要格式化为年-月-日 时-分-秒的格式，一定要一致否则webdav会报错")
    sha1: Optional[str] = Field(None,title="文件sha1",description="文件sha1，可选")  
    download_url: Optional[str] = Field(None,title="文件下载链接",description="文件下载链接，有些可以在列表页算出来的就不需要请求了，可以添加?x-oss-expires=时间戳 来控制过期时间，如果rust的缓存时间先到以缓存时间为准")  #
    play_headers: Optional[str] = Field(None,title="播放文件的header信息",description="播放文件的header信息")  #
    password: Optional[str] = Field(None,title="目录加密密码",description="目录加密密码")  #
    class Config:
        title = "DavFile:Webdav文件模型"

class ListRequest(BaseModel):
    '''
    文件列表请求字段，从webdav那里接收过来
    '''
    path_str:str = Field(title="请求的文件路径",description="求的文件路径，一般没用")  
    parent_file_id:str = Field(title="请求的目录ID",description="请求的文件上级目录ID") 
    class Config:
        title = "ListRequest:文件列表请求字段"

class InitUploadRequest(BaseModel):
    '''
    初始化文件上传请求字段，从webdav那里接收过来
    '''
    provider:str = Field(title="上传文件的provider",description="上传文件的provider，一般不用管，需要在相应的model里进行上传处理")  
    name:str = Field(title="上传文件的名称",description="上传文件的名称") 
    parent_file_id:str =  Field(title="上传文件的上级目录ID",description="上传文件的上级目录ID，不允许上传到根目录")  
    sha1:str =  Field(title="上传文件的sha1值",description="上传文件的sah1信息，需要在header里指定，有些不需要可不管：例子:curl -T '文件名' 'http://127.0.0.1:9867/test/'  --header 'OC-Checksum:sha1:文件名的sha1'")  
    size:int =  Field(title="上传文件的大小",description="上传文件的大小") 
    class Config:
        title = "InitUploadRequest:初始化文件上传请求字段" 

class InitResponseData(BaseModel):
    '''
    初始化文件上传响应数据
    '''
    uploader:str = Field(title="上传文件的地址",description="通常分片上传会返回一个上传地址，如果没有返回API的上传地址即可")
    fileName:str = Field(title="上传文件的名称",description="上传文件的名称") 
    fileSize:int = Field(title="上传文件的大小",description="上传文件的大小") 
    chunkSize:int = Field(title="分片上传用来分隔文件的大小",description="分片上传用来分隔文件的大小") 
    fileSha1:str = Field(title="上传文件的Sha1",description="上传文件的Sha1") 
    class Config:
        title = "InitResponseData:初始化文件上传响应数据"   

class InitUploadResponse(BaseModel):
    '''
    初始化文件上传响应信息,会最终反馈给webdav,其中code目前webdav那里只处理了200的响应，其它一律输出message
    '''
    code:int = Field(title="上传响应的状态码",description="目前webdav没有做过多状态处理，只有200成功，如果要显示信息在message里设置")
    message:str = Field(title="上传响应的信息提示",description="一般是错误提示，如果状态码不是200才显示") 
    extra:Optional[str] = Field(None,title="传递一些额外参数",description="传递一些额外参数，处理不同服务器需要的信息最好是base64加密字符串") 
    data:Union[InitResponseData, None] = Field(title="上传响应的数据",description="上传响应的数据") 
    class Config:
        title = "InitUploadResponse:初始化文件上传响应信息"


class OssArgs(BaseModel):
    '''
    OssArgs也不太清楚是啥，就是把上传请求获得到的信息缓存起来给其它函数调用，需要根据需求来不断完善，先这样
    '''
    uploader:str = Field(title="分片上传网址",description="分片上传网址") 
    sha1:str = Field(title="文件sha1做上传ID用",description="文件sha1做上传ID用") 
    chunkSize:int = Field(title="文件分片大小",description="文件分片大小") 
    extra_init:Optional[str] = Field(None,title="初始化后的一些额外信息",description="初始化后的一些额外信息") 
    extra_last:Optional[str] = Field(None,title="上次上传后的一些额外信息",description="上次上传后的一些额外信息") 
    class Config:
        title = "OssArgs:上传响应信息缓存"


class SliceUploadRequest(BaseModel):
    '''
    分片上传请求
    '''
    dav_file:Union[DavFile, None] = Field(title="分片的文件信息",description="分片的文件信息",alias='file') 
    oss_args:Union[OssArgs, None] = Field(title="分片的缓存信息",description="分片的缓存信息")
    upload_id:str = Field(title="上传ID",description="上传ID，应该是oss_args的sha1") 
    current_chunk:int = Field(title="当前上传的index",description="当前上传的index,注意从1开始") 
    class Config:
        title = "SliceUploadRequest:分片上传请求"


class FileUploadInfo(BaseModel):
    '''
    分片上传响应数据
    '''
    fileName:str = Field(title="文件名",description="文件名")
    fileSize:int = Field(title="文件大小",description="文件大小") 
    fileHash:str = Field(title="文件sha1",description="文件sha1")
    chunkIndex:int = Field(title="上传索引",description="上传索引，相当于上传请求的current_chunk，但不同服务响应不同，可能需要特殊处理") 
    chunkSize:int = Field(title="分片大小",description="分片大小")
    uploadState:int = Field(title="上传状态",description="上传状态") 
    class Config:
        title = "FileUploadInfo:分片上传响应数据"


class SliceUploadResponse(BaseModel):
    '''
    分片上传响应
    '''
    code:int = Field(title="分片上传响应的状态码",description="目前webdav没有做过多状态处理，只有200成功，如果要显示信息在message里设置")
    message:str = Field(title="分片上传响应的信息提示",description="一般是错误提示，如果状态码不是200才显示") 
    extra:Optional[str] = Field(None,title="传递一些额外参数",description="传递一些额外参数，处理不同服务器需要的信息最好是base64加密字符串") 
    data:Union[FileUploadInfo, None] = Field(title="分片上传响应的数据",description="分片上传响应的数据") 
    class Config:
        title = "SliceUploadResponse:分片上传响应"


class CompleteUploadRequest(BaseModel):
    '''
    最后完成上传的请求
    '''
    dav_file:Union[DavFile, None] = Field(title="分片的文件信息",description="分片的文件信息",alias='file') 
    oss_args:Union[OssArgs, None] = Field(title="分片的缓存信息",description="分片的缓存信息")
    upload_id:str = Field(title="上传ID",description="上传ID，应该是oss_args的sha1") 
    upload_tags:str = Field(title="上传tag",description="上传tag,一般没用") 
    class Config:
        title = "CompleteUploadRequest:完成上传的请求"


class CompleteUploadResponse(BaseModel):
    '''
    完成上传响应
    '''
    status:int = Field(title="上传响应的状态码",description="目前webdav没有做过多状态处理，只有200成功，如果要显示信息在data里设置")
    data:str = Field(title="上传响应的信息提示",description="一般是错误提示，如果状态码不是200才显示") 
    class Config:
        title = "CompleteUploadResponse:完成上传响应"


class CreateFolderRequest(BaseModel):
    '''
    创建文件夹请求
    '''
    name:str = Field(title="新文件夹名称",description="新文件夹名称")
    parent_id:str = Field(title="上级目录ID",description="上级目录ID,不允许在根目录创建") 
    path_str:str = Field(title="上级目录路径",description="上级目录路径,不允许在根目录创建") 
    parend_file:Union[DavFile, None] =Field(title="上级目录文件信息",description="上级目录文件信息") 
    class Config:
        title = "CreateFolderRequest:创建文件夹请求"

class RemoveFileRequest(BaseModel):
    '''
    删除文件请求
    '''
    dav_file:Union[DavFile, None] =Field(title="删除文件信息",description="删除文件信息",alias='file') 
    remove_path:str = Field(title="删除文件路径",description="删除文件路径,不允许在根目录操作") 
    class Config:
        title = "RemoveFileRequest:删除文件请求"

class RenameFileRequest(BaseModel):
    '''
    重命名请求
    '''
    dav_file:Union[DavFile, None] =Field(title="重命名文件信息",description="重命名文件信息",alias='file') 
    new_name:str = Field(title="新文件名称",description="新文件名称")
    from_path:str = Field(title="原路径",description="原路径",alias='from')
    to_path:str = Field(title="新路径",description="新路径",alias='to')
    class Config:
        title = "RenameFileRequest:重命名请求"

class MoveFileRequest(BaseModel):
    '''
    移动文件请求
    '''
    dav_file:Union[DavFile, None] =Field(title="移动文件信息",description="移动文件信息",alias='file') 
    new_parent_id:str = Field(title="新文件目录ID",description="新文件目录ID")
    from_path:str = Field(title="原路径",description="原路径",alias='from')
    to_path:str = Field(title="新路径",description="新路径",alias='to')
    class Config:
        title = "MoveFileRequest:移动文件请求"

class CopyFileRequest(BaseModel):
    '''
    复制文件请求
    '''
    dav_file:Union[DavFile, None] =Field(title="复制文件信息",description=" 复制文件信息",alias='file') 
    new_parent_id:str = Field(title="复制到目录ID",description="复制到目录ID")
    class Config:
        title = "CopyFileRequest:复制文件请求"