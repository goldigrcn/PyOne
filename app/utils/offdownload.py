#-*- coding=utf-8 -*-
from header import *
from upload import *

def download_and_upload(url,remote_dir,user,gid=None):
    p,status=get_aria2()
    down_path=os.path.join(config_dir,'upload')
    #重新下载
    if gid is not None:
        task=down_db.find_one({'gid':gid})
        if task is None:
            return False
        if task['up_status']!='100.0%':
            new_value={}
            new_value['up_status']=u'待机'
            new_value['status']=1
            down_db.update_many({'gid':gid},{'$set':new_value})
    else:
        if not url.lower().startswith('http') and not url.lower().startswith('magnet'):
            item={}
            item['name']='仅支持http(s)和磁力链接(magnet)'
            item['idx']=0
            item['gid']=''
            item['localpath']=''
            item['downloadUrl']=url
            item['selected']='true'
            item['selectable']='false'
            item['user']=user
            item['remote_dir']=remote_dir
            item['uploadUrl']=''
            item['size']=0
            item['down_status']='-'
            item['up_status']='-'
            item['status']=-1
            down_db.insert_one(item)
            return
        cur_order=down_db.count()
        option={"dir":down_path,"split":"16","max-connection-per-server":"8","seed-ratio":"0.1","bt-save-metadata":"false","bt-max-peers":"200","header":["User-Agent:Transmission/2.77"]}
        item={}
        r=p.addUri(url,option)
        gid=json.loads(r)[0]["result"]
        item['gid']=gid
        a=json.loads(p.tellStatus(gid))[0]["result"]
        if 'magnet:?xt=' in url:
            name=re.findall('magnet:\?xt=urn:btih:(.{,40})',url)[0].lower()+'.torrent'
            localpath=os.path.join(down_path,name)
        else:
            name=a['files'][0]['path'].replace(down_path+'/','').replace(down_path,'').replace(down_path[:-1],'')
            localpath=a['files'][0]['path']
        item['name']=name
        item['idx']=0
        item['localpath']=localpath
        item['downloadUrl']=url
        item['selected']='true'
        item['selectable']='false'
        item['user']=user
        item['remote_dir']=remote_dir
        item['uploadUrl']=''
        item['size']=a['totalLength']
        # item['size']=humanize.naturalsize(a['totalLength'], gnu=True)
        item['down_status']=u'{}%'.format(round(float(a['completedLength'])/(float(a['totalLength'])+0.1)*100,0))
        item['up_status']=u'待机'
        item['status']=1
        down_db.insert_one(item)
    while 1:
        a=json.loads(p.tellStatus(gid))[0]["result"]
        if a.get('followedBy'):
            old_status={}
            old_status['status']=0
            old_status['down_status']='100.0%'
            old_status['up_status']=u'磁力文件，无需上传'
            down_db.find_one_and_update({'gid':gid},{'$set':old_status})
            magnet=re.findall('magnet:\?xt=urn:btih:(.{,40})',down_db.find_one({'gid':gid})['downloadUrl'])[0].lower()+'.torrent'
            old_path=os.path.join(down_path,magnet)
            try:
                os.remove(old_path)
            except:
                print("删除种子文件失败")
            gid=a.get('followedBy')[0]
            aa=json.loads(p.tellStatus(gid))[0]["result"]
            for idx,file in enumerate(aa['files']):
                new_item={}
                new_item['gid']=gid
                new_item['idx']=idx
                new_item['name']=file['path'].replace(down_path+'/','').replace(down_path,'').replace(down_path[:-1],'')
                new_item['localpath']=file['path']
                new_item['downloadUrl']=aa['infoHash']
                new_item['selected']='true'
                new_item['selectable']='true'
                new_item['user']=user
                new_item['remote_dir']=remote_dir
                new_item['uploadUrl']=''
                new_item['size']=file['length']
                # new_item['size']=humanize.naturalsize(file['length'], gnu=True)
                new_item['down_status']=u'{}%'.format(round(float(file['completedLength'])/(float(file['length'])+0.1)*100,0))
                new_item['up_status']=u'待机'
                new_item['status']=1
                down_db.insert_one(new_item)
            a=json.loads(p.tellStatus(gid))[0]["result"]
        total=len(a['files'])
        complete=0
        for idx,file in enumerate(a['files']):
            t=down_db.find_one({'gid':gid,'idx':idx})
            if t['down_status']=='100.0%':
                if t['up_status']=='待机':
                    new_value['up_status']=u'准备上传'
                    down_db.find_one_and_update({'gid':gid,'idx':idx},{'$set':new_value})
                    upload_status(gid,idx,remote_dir,user)
                elif t['up_status']=='上传成功！':
                    complete+=1
                else:
                    continue
            if t['selected']=='false':
                complete+=1
                continue
            name=file['path'].replace(down_path+'/','').replace(down_path,'').replace(down_path[:-1],'')
            new_value={'down_status':u'{}%'.format(round(float(file['completedLength'])/(float(file['length'])+0.1)*100,0))}
            new_value['name']=name
            new_value['size']=file['length']
            # new_value['size']=humanize.naturalsize(file['length'], gnu=True)
            new_value['localpath']=file['path']
            if a['status']=='complete' or (file['completedLength']==file['length'] and int(file['length'])!=0):
                new_value['up_status']=u'准备上传'
                down_db.find_one_and_update({'gid':gid,'idx':idx},{'$set':new_value})
                upload_status(gid,idx,remote_dir,user)
                complete+=1
            elif a['status']=='active' or a['status']=='waiting':
                time.sleep(1)
                down_db.find_one_and_update({'gid':gid,'idx':idx},{'$set':new_value})
            elif a['status']=='paused':
                new_value['down_status']=u'暂停下载'
                down_db.find_one_and_update({'gid':gid,'idx':idx},{'$set':new_value})
            else:
                print('下载出错')
                new_value['down_status']=u'下载出错'
                new_value['status']=-1
                down_db.find_one_and_update({'gid':gid,'idx':idx},{'$set':new_value})
                complete+=1
        # time.sleep(2)
        if complete==total:
            print('{} complete'.format(gid))
            break

def upload_status(gid,idx,remote_dir,user):
    item=down_db.find_one({'gid':gid,'idx':idx})
    localpath=item['localpath']
    if not remote_dir.endswith('/'):
        remote_dir=remote_dir+'/'
    remote_path=os.path.join(remote_dir,item['name'])
    if not os.path.exists(localpath) and down_db.find_one({'_id':item['_id']})['status']!=0:
        new_value={}
        new_value['up_status']=u'本地文件不存在。检查：{}'.format(localpath)
        new_value['status']=-1
        down_db.find_one_and_update({'_id':item['_id']},{'$set':new_value})
        return
    _upload_session=Upload_for_server(localpath,remote_path,user)
    while 1:
        try:
            new_value={}
            data=_upload_session.next()
            msg=data['status']
            """
            partition upload success
            The request has been throttled!
            partition upload fail! retry
            partition upload fail!
            file exists
            create upload session fail
            """
            if 'partition upload success' in msg:
                new_value['up_status']=msg
                new_value['uploadUrl']=data.get('uploadUrl')
                new_value['status']=1
            elif 'The request has been throttled' in msg:
                new_value['up_status']='api受限！智能等待30分钟'
                new_value['status']=0
            elif 'partition upload fail! retry' in msg:
                new_value['up_status']='上传失败，等待重试'
                new_value['status']=1
            elif 'partition upload fail' in msg:
                new_value['up_status']='上传失败，已经超过重试次数'
                new_value['status']=-1
                down_db.find_one_and_update({'_id':item['_id']},{'$set':new_value})
                break
            elif 'file exists' in msg:
                new_value['up_status']='远程文件已存在'
                new_value['status']=-1
                down_db.find_one_and_update({'_id':item['_id']},{'$set':new_value})
                break
            elif 'create upload session fail' in msg:
                new_value['up_status']='创建实例失败！'
                new_value['status']=-1
                down_db.find_one_and_update({'_id':item['_id']},{'$set':new_value})
                break
            else:
                new_value['up_status']='上传成功！'
                new_value['status']=0
                down_db.find_one_and_update({'_id':item['_id']},{'$set':new_value})
                time.sleep(2)
                os.remove(localpath)
                break
            down_db.find_one_and_update({'_id':item['_id']},{'$set':new_value})
        except Exception as e:
            print(e)
            break
        time.sleep(2)


def get_tasks(status):
    tasks=down_db.find({'status':status})
    #获取所有的gid
    gids=[]
    for t in tasks:
        gids.append((t['gid'],t['name'].split('/')[0]))
    gids=list(set(gids))
    ##根据gid获取列表
    result=[]
    for gid,title in gids:
        info={}
        info['gid']=gid
        info['down_status']='' #"选择下载","选择不下载","*%","暂停下载","开始下载","-","下载出错"
        info['title']=title
        info['files']=[]
        total_size=0
        complete=0
        for file in down_db.find({'gid':gid}):
            file_info={}
            total_size+=int(file['size'])
            try:
                complete+=int(file['size'])*float(file['down_status'].replace('%',''))/100
            except Exception as e:
                complete+=0
            file_info['idx']=file['idx']
            file_info['name']=file['name'].replace(title+'/','')
            file_info['size']=humanize.naturalsize(file['size'], gnu=True)
            file_info['down_status']=file['down_status']
            file_info['up_status']=file['up_status']
            file_info['selectable']=file['selectable']
            file_info['selected']=file['selected']
            file_info['status']=file['status']
            if file['down_status'] not in ["选择下载","选择不下载"]:
                if file['down_status'] in ["暂停下载","下载出错"]:
                    info['down_status']='暂停下载'
            info['files'].append(file_info)
        info['size']=humanize.naturalsize(total_size, gnu=True)
        d=round(float(complete)/(float(total_size)+0.1)*100,0)
        info['down_percent']=u'{}% / '.format(d)
        result.append(info)
    return result

def Aria2Method(action,**kwargs):
    p,status=get_aria2()
    if not status:
        return {'status':False,'msg':p}
    if action in ['pause']:
        for gid in kwargs['gids']:
            p.forcePause(gid)
    if action in ['unpause']:
        for gid in kwargs['gids']:
            p.unpause(gid)
    elif action in ['remove']:
        for gid in kwargs['gids']:
            gid,idx=gid.split('#')
            p.forceRemove(gid)
    elif action in ['removeAll']:
        for gid in kwargs['gids']:
            p.forceRemove(gid)
    elif action=='restart':
        for gid in kwargs['gids']:
            p.unpause(gid)
    elif action=='selected':
        retdata={}
        selected_dict={}
        status_dict={}
        #选择下载的gid&idx放进字典
        for gid in kwargs['gids']:
            gid,idx=gid.split('#')
            idx=int(idx)
            # p.pause(gid)
            r=json.loads(p.tellStatus(gid))[0]['result']['status']
            status_dict[gid]=r
            if r=='active':
                p.forcePause(gid)
            selected_dict.setdefault(gid,[]).append(idx+1)
        #之前本就选择下载的gid&idx放进字典
        for gid in selected_dict.keys():
            tasks=down_db.find({'gid':gid,'selected':'true'})
            for t in tasks:
                selected_dict[gid].append(t['idx']+1)
        #重新处理可下载文件
        result=[]
        for gid,idxs in selected_dict.items():
            idxs=[str(i) for i in idxs]
            info={'gid':gid}
            option={"select-file":','.join(idxs)}
            r=p.changeOption(gid,option)
            if status_dict[gid]=='active':
                p.unpause(gid)
            res=json.loads(r)[0]['result']
            info['msg']=res
            result.append(info)
            for idx in idxs:
                new_value={'selected':'true','down_status':'选择下载','status':1}
                down_db.find_one_and_update({'gid':gid,'idx':int(idx)-1},{'$set':new_value})
        retdata['result']=result
        return retdata
    elif action=='unselected':
        retdata={}
        selected_dict={}
        status_dict={}
        #先创建围表
        for gid in kwargs['gids']:
            gid,idx=gid.split('#')
            nums=down_db.find({'gid':gid}).count()
            if nums<=1:
                result=[{'gid':gid,'msg':'当前磁力只有一个文件，无法选择'}]
                retdata['result']=result
                return retdata
            idx=int(idx)
            # p.pause(gid)
            r=json.loads(p.tellStatus(gid))[0]['result']['status']
            status_dict[gid]=r
            if r=='active':
                p.forcePause(gid)
            new_value={'selected':'false','down_status':'选择不下载','status':2}
            down_db.find_one_and_update({'gid':gid,'idx':idx},{'$set':new_value})
            selected_dict.setdefault(gid,[])
        #之前本就选择下载的gid&idx放进字典
        for gid in selected_dict.keys():
            tasks=down_db.find({'gid':gid,'selected':'true'})
            for t in tasks:
                selected_dict[gid].append(int(t['idx']+1))
        #选择不下载的gid&idx从字典移除
        for gid in kwargs['gids']:
            gid,idx=gid.split('#')
            idx=int(idx)
            # selected_dict[gid].pop(selected_dict[gid].index(idx+1))
        #重新处理可下载文件
        result=[]
        for gid,idxs in selected_dict.items():
            idxs=[str(i) for i in idxs]
            info={'gid':gid}
            option={"select-file":','.join(idxs)}
            r=p.changeOption(gid,option)
            if status_dict[gid]=='active':
                p.unpause(gid)
            res=json.loads(r)[0]['result']
            info['msg']=res
            result.append(info)
        retdata['result']=result
        return retdata




def DBMethod(action,**kwargs):
    retdata={}
    if action in ['pause','unpause','pauseAll','unpauseAll']:
        result=[]
        for gid in kwargs['gids']:
            info={'gid':gid}
            task=down_db.find_one({'gid':gid})
            if task['down_status']=='100.0%':
                info['msg']='文件下载完成！无法更改上传状态'
            elif task['down_status']=='下载出错':
                info['msg']='失败任务只能重启'
            else:
                new_value={}
                if action in ['pauseAll','pause']:
                    new_value['down_status']='暂停下载'
                else:
                    new_value['down_status']='开始下载'
                down_db.update_many({'gid':gid},{'$set':new_value})
                info['msg']='更改状态成功'
            result.append(info)
    elif action in ['remove']:
        result=[]
        for gid in kwargs['gids']:
            gid,idx=gid.split('#')
            info={'gid':gid,'idx':int(idx)}
            task=down_db.find_one({'gid':gid,'idx':int(idx)})
            if task['down_status']=='100.0%' and 'partition upload success' in task['up_status']:
                info['msg']='正在上传的任务，无法更改状态'
            else:
                down_db.remove(info)
                info['msg']='删除任务成功'
            try:
                os.remove(task['localpath'])
            except:
                print('未能成功删除本地文件')
                info['msg']='删除任务成功。但是未能成功删除本地文件'
            result.append(info)
    elif action in ['removeAll']:
        result=[]
        for gid in kwargs['gids']:
            info={'gid':gid}
            task=down_db.find_one({'gid':gid})
            if task['down_status']=='100.0%' and 'partition upload success' in task['up_status']:
                info['msg']='正在上传的任务，无法更改状态'
            else:
                down_db.delete_many(info)
                info['msg']='删除任务成功'
            try:
                os.delete_many(task['localpath'])
            except:
                print('未能成功删除本地文件')
                info['msg']='删除任务成功。但是未能成功删除本地文件'
            result.append(info)
    elif action=='restart':
        result=[]
        for gid in kwargs['gids']:
            info={'gid':gid}
            new_value={'status':1}
            down_db.update_many({'gid':gid},{'$set':new_value})
            info['msg']='更改状态成功'
            it=down_db.find_one({'gid':gid})
            user=it['user']
            remote_dir=it['remote_dir']
            cmd=u'python {} download_and_upload "{}" "{}" {} {}'.format(os.path.join(config_dir,'function.py'),1,remote_dir,user,gid)
            print cmd
            subprocess.Popen(cmd,shell=True)
            result.append(info)
    elif action in ['unselected','selected']:
        return None
    retdata['result']=result
    return retdata