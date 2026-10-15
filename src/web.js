'use strict';

const http=require('node:http');
const fs=require('node:fs');
const path=require('node:path');
const ROOT=path.resolve(__dirname,'..');
const {createHmac,timingSafeEqual,randomBytes,createHash}=require('node:crypto');
const {Readable}=require('node:stream');
const {pipeline}=require('node:stream/promises');
const {moscow,now}=require('./db');
const {compressPhoto}=require('./photos');

class HttpError extends Error {constructor(status,message){super(message);this.status=status;}}
const fail=(status,message)=>{throw new HttpError(status,message);};
const integer=(value,max=Number.MAX_SAFE_INTEGER)=>/^\d+$/.test(String(value)) && Number.isSafeInteger(Number(value)) && Number(value)>0 && Number(value)<=max?Number(value):fail(400,'Неверный идентификатор.');
const page=value=>value===null?0:Math.min(1000,integer(Number(value)+1)-1);
const hmac=(key,value)=>createHmac('sha256',key).update(value).digest();
const equal=(a,b)=>a.length===b.length && timingSafeEqual(a,b);
let sharp;try{sharp=require('sharp');}catch{}
const photoRefs=user=>(user.photos || '').split(',').map(ref=>ref.trim()).filter(Boolean);

function validateInitData(raw,token,maxAge=3600,clock=now()) {
  if(typeof raw!=='string' || raw.length>16384)fail(401,'Откройте приложение через Telegram.');
  const params=new URLSearchParams(raw),seen=new Set();
  for(const key of params.keys()){if(seen.has(key))fail(401,'Неверные данные Telegram.');seen.add(key);}
  const hash=params.get('hash');if(!/^[a-f0-9]{64}$/i.test(hash || ''))fail(401,'Неверная подпись Telegram.');
  params.delete('hash');
  const data=[...params.entries()].sort(([a],[b])=>a<b?-1:a>b?1:0).map(([k,v])=>`${k}=${v}`).join('\n');
  if(!equal(hmac(hmac('WebAppData',token),data),Buffer.from(hash,'hex')))fail(401,'Неверная подпись Telegram.');
  const authDate=Number(params.get('auth_date'));
  if(!Number.isSafeInteger(authDate) || authDate>clock+30 || clock-authDate>maxAge)fail(401,'Вход устарел. Закройте и откройте приложение заново.');
  let user;try{user=JSON.parse(params.get('user'));}catch{fail(401,'Не удалось определить пользователя Telegram.');}
  if(!Number.isSafeInteger(user?.id) || user.id<=0 || user.is_bot)fail(401,'Неверный пользователь Telegram.');
  return user;
}

class MiniApp {
  constructor(bot) {
    this.bot=bot;this.store=bot.store;this.config=bot.config.miniApp;
    this.origin=new URL(this.config.url).origin;
    if(!this.origin.startsWith('https://'))throw new Error('Mini App требует HTTPS URL.');
    this.sessionKey=hmac('dvbot-miniapp-session',bot.config.token);
    this.avatarJobs=new Map();this.mediaCache=new Map();this.limits=new Map();this.uploading=new Set();
    this.server=http.createServer((req,res)=>this.handle(req,res));
    this.server.requestTimeout=60000;this.server.headersTimeout=10000;
    this.server.maxHeadersCount=50;
  }
  async start(){
    if(!['127.0.0.1','::1'].includes(this.config.host))throw new Error('Mini App должен слушать только localhost за nginx.');
    const port=integer(this.config.port,65535);
    await new Promise((resolve,reject)=>{this.server.once('error',reject);this.server.listen(port,this.config.host,resolve);});
    console.log(`Mini App: ${this.config.url} → ${this.config.host}:${port}`);
  }
  stop(){
    if(this.closing)return this.closing;
    this.closing=new Promise(resolve=>{
      const timeout=setTimeout(()=>this.server.closeAllConnections(),5000);timeout.unref();
      this.server.close(()=>{clearTimeout(timeout);resolve();});
      this.server.closeIdleConnections();
    });
    return this.closing;
  }
  json(res,status,data){res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});res.end(JSON.stringify(data));}
  async body(req,limit=16384,raw=false){
    const chunks=[];let size=0;
    for await(const chunk of req){size+=chunk.length;if(size>limit)fail(413,'Файл или запрос слишком большой.');chunks.push(chunk);}
    const buffer=Buffer.concat(chunks);if(raw)return buffer;
    try{return JSON.parse(buffer.toString('utf8'));}catch{fail(400,'Неверный JSON.');}
  }
  session(req){
    const bearer=req.headers.authorization?.match(/^Bearer ([\w.-]+)$/)?.[1];
    const value=bearer || (req.headers.cookie || '').split(';').map(s=>s.trim()).find(s=>s.startsWith('dv_session='))?.slice(11);
    if(!value || value.length>2048)return null;
    const [payload,signature,...extra]=value.split('.');if(extra.length || !signature)return null;
    if(!equal(hmac(this.sessionKey,payload),Buffer.from(signature,'base64url')))return null;
    try{const session=JSON.parse(Buffer.from(payload,'base64url'));if(!Number.isSafeInteger(session.id) || session.id<=0 || typeof session.csrf!=='string' || !Number.isSafeInteger(session.exp) || session.exp<now())return null;return session;}catch{return null;}
  }
  setSession(res,user){
    const session={id:user.id,username:user.username || null,firstName:user.first_name || '',csrf:randomBytes(24).toString('base64url'),exp:now()+Math.min(24,Math.max(1,this.config.sessionHours||12))*3600};
    const payload=Buffer.from(JSON.stringify(session)).toString('base64url');
    res.setHeader('Set-Cookie',`dv_session=${payload}.${hmac(this.sessionKey,payload).toString('base64url')}; Path=/; HttpOnly; Secure; SameSite=None; Partitioned; Max-Age=${session.exp-now()}`);
    return session;
  }
  authenticate(req){const session=this.session(req);if(!session)fail(401,'Войдите через Telegram.');return session;}
  csrf(req,session){
    if(req.headers.origin!==this.origin)fail(403,'Неверный источник запроса.');
    if(!equal(Buffer.from(req.headers['x-csrf-token'] || ''),Buffer.from(session.csrf)))fail(403,'Обновите страницу и повторите действие.');
  }
  rate(key,limit=600){
    const at=Date.now();const entry=this.limits.get(key);
    if(!entry || at-entry.start>60000)this.limits.set(key,{start:at,count:1});else if(++entry.count>limit)fail(429,'Слишком много запросов. Подождите минуту.');
    if(this.limits.size>10000)for(const [k,v]of this.limits)if(at-v.start>60000)this.limits.delete(k);
  }
  profile(user,viewer){
    if(!user)return null;
    const own=user.user_id===viewer;
    const photos=photoRefs(user).map((ref,index)=>({url:this.mediaUrl(`/api/media/profile/${user.user_id}/${index}`,viewer),...(own?{ref}:{})}));
    const result={id:user.user_id,name:user.name,age:user.age,college:user.college,bio:user.bio || '',photos,avatar:photos.length?this.mediaUrl(`/api/media/profile/${user.user_id}/avatar`,viewer):null,video:user.video?this.mediaUrl(`/api/media/profile/${user.user_id}/video`,viewer):null};
    const requester=this.store.user(viewer);if(requester && requester.college!==user.college)result.distance=this.bot.distance(requester.college,user.college);
    if(own)Object.assign(result,{viewScope:user.view_scope || 'college',hidden:!!user.is_hidden,hideFromTop:!!user.hide_from_top,videoRef:user.video || null,mailing:!this.store.mailingDisabled(viewer)});
    return result;
  }
  sessionResult(session){
    const colleges=this.bot.colleges;
    const payload=Buffer.from(JSON.stringify(session)).toString('base64url');
    return {user:{id:session.id,firstName:session.firstName,isBanned:this.store.banned(session.id),isStaff:this.bot.admin.isStaff(session.id),isAdmin:this.bot.admin.isAdmin(session.id)},profile:this.profile(this.store.user(session.id),session.id),csrf:session.csrf,sessionToken:payload+'.'+hmac(this.sessionKey,payload).toString('base64url'),colleges,botUsername:this.bot.config.botUsername};
  }
  needProfile(id){if(!this.store.user(id))fail(409,'Сначала создайте анкету.');}
  accessible(target,viewer,{conversation=false}={}){
    const user=this.store.user(target);if(!user)fail(404,'Анкета не найдена.');
    if(target!==viewer && !this.bot.admin.isStaff(viewer)){
      if(this.store.banned(target))fail(404,'Анкета недоступна.');
      if(user.is_hidden && !(conversation && this.store.history(viewer,target,1).length))fail(404,'Анкета скрыта.');
    }
    return user;
  }
  serializeMessage(message,viewer){
    const result={id:message.id,mine:message.sender_id===viewer,text:message.message || '',at:message.created_at,media:[]};
    for(const type of ['photo','video','voice','sticker','animation'])if(message[`${type}_file_id`])result.media.push({type,url:this.mediaUrl(`/api/media/message/${message.id}/${type}`,viewer)});
    const replyId=this.bot.runtime.miniAppReplies?.[message.id];
    if(replyId){
      const original=this.store.get('SELECT * FROM messages WHERE id=? AND ((sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?))',replyId,message.sender_id,message.receiver_id,message.receiver_id,message.sender_id);
      if(original)result.reply={id:original.id,name:this.store.user(original.sender_id)?.name || 'Пользователь',text:(original.message || 'Медиа').slice(0,200)};
    }
    return result;
  }
  mediaUrl(resource,viewer){
    const payload=Buffer.from(JSON.stringify({id:viewer,path:resource,exp:now()+3600})).toString('base64url');
    return resource+'?access='+payload+'.'+hmac(hmac(this.sessionKey,'media'),payload).toString('base64url');
  }
  mediaSession(url){
    if(!/^\/api\/media\/(profile|message)\/\d+\/[\w]+$/.test(url.pathname))return null;
    const value=url.searchParams.get('access');if(!value || value.length>2048)return null;
    const [payload,signature,...extra]=value.split('.');if(extra.length || !signature || !equal(hmac(hmac(this.sessionKey,'media'),payload),Buffer.from(signature,'base64url')))return null;
    try{const data=JSON.parse(Buffer.from(payload,'base64url'));if(!Number.isSafeInteger(data.id) || data.id<=0 || data.path!==url.pathname || data.exp<now())return null;return {id:data.id};}catch{return null;}
  }
  rememberUpload(id,type,ref){
    const uploads=this.bot.runtime.miniAppUploads || (this.bot.runtime.miniAppUploads={});
    uploads[id]=[...(uploads[id] || []).filter(u=>u.at>Date.now()-7*86400000),{type,ref,at:Date.now()}].slice(-40);
    this.bot.persist();
  }
  ownsUpload(id,type,ref){return (this.bot.runtime.miniAppUploads?.[id] || []).some(u=>u.type===type && u.ref===ref);}
  async updateProfile(session,body){
    const {spam}=require('./main'),colleges=this.bot.colleges,id=session.id,existing=this.store.user(id);
    const editing=!!existing;
    const name=body.name??existing?.name,age=body.age??existing?.age,college=body.college??existing?.college,bio=body.bio??existing?.bio??'';
    if(typeof name!=='string' || !/^[А-Яа-яЁё\s-]{2,60}$/.test(name.trim()))fail(400,'Имя: 2–60 символов, русские буквы.');
    if(!Number.isInteger(age) || age<14 || age>30)fail(400,'Возраст должен быть от 14 до 30 лет.');
    if(!colleges.includes(college))fail(400,'Выберите корпус из списка.');
    if(typeof bio!=='string' || bio.length>500 || spam(bio))fail(400,'Описание: до 500 символов и не более одной ссылки.');
    if(!editing && body.student!==true)fail(400,'Подтвердите, что вы студент сообщества.');
    if(body.mailing!==undefined)fail(403,'Отписка доступна только в полученной рассылке.');
    const oldPhotos=photoRefs(existing || {});
    const photos=body.photos??oldPhotos;
    if(!Array.isArray(photos) || photos.length<1 || photos.length>3 || photos.some(p=>typeof p!=='string' || (!oldPhotos.includes(p) && !this.ownsUpload(id,'photo',p))))fail(400,'Загрузите от 1 до 3 своих фотографий.');
    const video=body.video===undefined?existing?.video:body.video;
    if(video && video!==existing?.video && !this.ownsUpload(id,'video',video))fail(400,'Загрузите своё видео.');
    if(body.viewScope!==undefined && !['college','all'].includes(body.viewScope))fail(400,'Неверная область поиска.');
    for(const key of ['hidden','hideFromTop','mailing'])if(body[key]!==undefined && typeof body[key]!=='boolean')fail(400,'Неверные настройки.');
    this.store.transaction(()=>{
      // Оставляем дополнительные столбцы и строки существующей схемы на месте.
      const values=[name.trim(),age,college,bio,photos.join(','),video || null];
      if(editing)this.store.run('UPDATE users SET name=?,age=?,college=?,bio=?,photos=?,video=? WHERE user_id=?',...values,id);
      else this.store.run('INSERT INTO users(name,age,college,bio,photos,video,user_id,username,created_at,profile_token) VALUES(?,?,?,?,?,?,?,?,?,?)',...values,id,session.username,moscow(),randomBytes(16).toString('base64url'));
      if(!editing)this.bot.restoreProfilePreferences(id);
      if(body.viewScope!==undefined)this.store.update(id,'view_scope',body.viewScope);
      if(body.hidden!==undefined)this.store.update(id,'is_hidden',Number(body.hidden));
      if(body.hideFromTop!==undefined)this.store.update(id,'hide_from_top',Number(body.hideFromTop));

    });
    return this.profile(this.store.user(id),id);
  }
  async upload(req,session,url){
    this.rate('upload:'+session.id,30);if(this.uploading.has(session.id))fail(429,'Дождитесь завершения загрузки.');
    const type=url.searchParams.get('type');const methods={photo:'sendPhoto',video:'sendVideo',voice:'sendVoice'};
    if(!methods[type])fail(400,'Неподдерживаемый тип медиа.');
    const mime=(req.headers['content-type'] || '').split(';')[0];
    if(type==='photo' && !['image/jpeg','image/png','image/webp'].includes(mime))fail(400,'Фото должно быть JPEG, PNG или WebP.');
    if(type==='video' && !['video/mp4','video/webm','video/quicktime'].includes(mime))fail(400,'Отправьте видео MP4, WebM или MOV.');
    if(type==='voice' && !['audio/ogg','audio/webm','audio/mp4','audio/mpeg','audio/wav'].includes(mime))fail(400,'Неподдерживаемый аудиофайл.');
    this.uploading.add(session.id);
    try{
      let buffer=await this.body(req,20*1024*1024,true);if(!buffer.length)fail(400,'Файл пуст.');
      let name=String(req.headers['x-file-name'] || 'upload').replace(/[^\w.-]/g,'_').slice(0,100);
      if(type==='photo'){try{const result=await compressPhoto(buffer,this.bot.config.photoCompression);buffer=result.buffer;if(result.compressed)name='photo.jpg';}catch{fail(400,'Не удалось обработать фото. Отправьте JPEG, PNG или WebP до 20 МБ и 40 мегапикселей.');}}
      const response=await this.bot.api.call(methods[type],{chat_id:session.id,disable_notification:true},{[type]:{buffer,name}});
      if(!response?.ok)fail(502,'Не удалось загрузить файл в Telegram. Сначала нажмите /start в боте.');
      const ref=type==='photo'?response.result.photo?.at(-1)?.file_id:response.result[type]?.file_id;
      if(!ref)fail(502,'Telegram не вернул файл.');
      this.rememberUpload(session.id,type,ref);
      if(response.result.message_id)await this.bot.api.call('deleteMessage',{chat_id:session.id,message_id:response.result.message_id});
      return {ref,type};
    } finally {this.uploading.delete(session.id);}
  }
  async react(id,target,action){
    if(id===target)fail(400,'Это ваша анкета.');this.accessible(target,id);
    if(action==='dislike'){this.store.run('INSERT OR IGNORE INTO dislikes(user_id,disliked_user_id) VALUES(?,?)',id,target);return {matched:false};}
    if(action!=='like')fail(400,'Неверное действие.');
    const result=this.store.like(id,target);
    if(result.added)this.bot.launch(async()=>{
      await this.bot.showProfile(target,this.store.user(id),{viewer:target,captionPrefix:result.matched?'💖 Взаимная симпатия!\n\n':'💖 Твоя анкета понравилась!\n\n'});
      if(result.matched)await this.bot.send(id,'💖 У вас взаимная симпатия!',this.bot.profileKeyboard(target));
    });
    return result;
  }
  async sendMessage(id,target,body){
    if(id===target)fail(400,'Нельзя написать самому себе.');this.accessible(target,id,{conversation:true});
    const text=body.text || '',media=body.media;
    if(typeof text!=='string' || text.length>3500 || (!text.trim() && !media))fail(400,'Отправьте текст до 3500 символов или медиа.');
    if(typeof body.clientId!=='string' || !/^[\w-]{16,80}$/.test(body.clientId))fail(400,'Неверный идентификатор отправки.');
    if(media && (!['photo','video','voice'].includes(media.type) || typeof media.ref!=='string' || !this.ownsUpload(id,media.type,media.ref)))fail(403,'Файл не принадлежит вам.');
    const pending=this.bot.runtime.miniAppSent || (this.bot.runtime.miniAppSent={});
    const replyTo=body.replyTo==null?null:integer(body.replyTo);
    if(replyTo && !this.store.get('SELECT 1 FROM messages WHERE id=? AND ((sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?))',replyTo,id,target,target,id))fail(403,'Можно ответить только на сообщение этого диалога.');
    const key=id+':'+body.clientId;const digest=createHash('sha256').update(JSON.stringify({target,text,media,...(replyTo?{replyTo}:{})})).digest('hex');
    if(pending[key]){if(pending[key].digest!==digest)fail(409,'Этот запрос уже использован.');const old=this.store.get('SELECT * FROM messages WHERE id=? AND sender_id=? AND receiver_id=?',pending[key].id,id,target);if(!old)fail(410,'Сообщение удалено.');return this.serializeMessage(old,id);}
    const content={text:text.trim() || {photo:'📷 Фото',video:'🎥 Видео',voice:'🎤 Голосовое сообщение'}[media.type],...(media?{[media.type]:media.ref}:{})};
    const saved=this.store.saveMessage(id,target,content);
    if(replyTo){const replies=this.bot.runtime.miniAppReplies || (this.bot.runtime.miniAppReplies={});replies[saved.id]=replyTo;}
    pending[key]={id:saved.id,digest,at:Date.now()};
    const keys=Object.keys(pending);if(keys.length>2000)for(const key of keys.slice(0,keys.length-2000))delete pending[key];
    this.bot.persist();
    this.bot.launch(async()=>{
      const markup=this.bot.messageKeyboard(id,saved.id),sender=this.store.user(id)?.name || 'Пользователь',delivered=`💬 ${sender}\n${content.text}`;
      if(saved.notify)await this.bot.send(target,`📩 Сообщение от ${sender}.`,markup);
      if(media)await this.bot.media(target,media.type,media.ref,delivered,markup);else await this.bot.send(target,delivered,markup);
    });
    return this.serializeMessage(this.store.get('SELECT * FROM messages WHERE id=?',saved.id),id);
  }
  async resolveFile(ref){
    const local=this.bot.localPhoto(ref);if(local)return {local};
    if(!/^[\w-]{8,512}$/.test(ref))fail(404,'Медиа недоступно.');
    const cache=this.mediaCache.get(ref);if(cache && cache.exp>Date.now())return cache;
    const result=await this.bot.api.call('getFile',{file_id:ref});
    const file=result?.result?.file_path;
    if(!result?.ok || typeof file!=='string' || file.includes('..') || !/^[\w/.-]+$/.test(file))fail(404,'Telegram не отдал файл.');
    const info={file,exp:Date.now()+3000000};if(this.mediaCache.size>=200)this.mediaCache.delete(this.mediaCache.keys().next().value);this.mediaCache.set(ref,info);return info;
  }
  async streamAvatar(req,res,ref){
    if(!sharp)return this.streamFile(req,res,ref);
    const directory=path.join(path.dirname(this.bot.runtimePath),'avatar-cache');
    const filename=path.join(directory,createHash('sha256').update(ref).digest('hex')+'.webp');
    if(!fs.existsSync(filename)){
      if(!this.avatarJobs.has(filename))this.avatarJobs.set(filename,(async()=>{
        const info=await this.resolveFile(ref);let input=info.local;
        if(!input){const response=await fetch(`https://api.telegram.org/file/bot${this.bot.config.token}/${info.file}`,{signal:AbortSignal.timeout(30000)});if(!response.ok)fail(502,'Не удалось получить фото.');const chunks=[];let size=0;for await(const chunk of response.body){size+=chunk.length;if(size>20*1024*1024)fail(413,'Фото слишком большое.');chunks.push(chunk);}input=Buffer.concat(chunks);}
        const buffer=await sharp(input).rotate().resize(160,160,{fit:'cover',withoutEnlargement:true}).webp({quality:72}).toBuffer();
        fs.mkdirSync(directory,{recursive:true});fs.writeFileSync(filename,buffer);
      })().finally(()=>this.avatarJobs.delete(filename)));
      await this.avatarJobs.get(filename);
    }
    res.setHeader('Content-Type','image/webp');res.setHeader('Cache-Control','private, max-age=3600');
    await pipeline(fs.createReadStream(filename),res);
  }
  async streamFile(req,res,ref){
    const info=await this.resolveFile(ref);
    const types={'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.webp':'image/webp','.gif':'image/gif','.mp4':'video/mp4','.webm':'video/webm','.ogg':'audio/ogg','.oga':'audio/ogg','.mp3':'audio/mpeg','.m4a':'audio/mp4','.mov':'video/quicktime'};
    const mime=types[path.extname(info.local || info.file).toLowerCase()];if(!mime)fail(415,'Этот стикер можно посмотреть в Telegram.');
    const range=req.headers.range;if(range && !/^bytes=\d*-\d*$/.test(range))fail(416,'Неверный диапазон.');
    res.setHeader('Content-Type',mime);res.setHeader('Cache-Control','private, max-age=300');res.setHeader('Accept-Ranges','bytes');
    if(info.local){
      const size=fs.statSync(info.local).size;let start=0,end=size-1;
      if(range){const [,a,b]=/^bytes=(\d*)-(\d*)$/.exec(range);if(!a && !b)fail(416,'Неверный диапазон.');if(a){start=Number(a);end=b?Math.min(Number(b),end):end;}else start=Math.max(0,size-Number(b));if(start>end || start>=size){res.setHeader('Content-Range',`bytes */${size}`);fail(416,'Неверный диапазон.');}res.statusCode=206;res.setHeader('Content-Range',`bytes ${start}-${end}/${size}`);}
      res.setHeader('Content-Length',end-start+1);await pipeline(fs.createReadStream(info.local,{start,end}),res);return;
    }
    const controller=new AbortController();res.once('close',()=>controller.abort());
    const upstream=await fetch(`https://api.telegram.org/file/bot${this.bot.config.token}/${info.file}`,{headers:range?{Range:range}:{},signal:AbortSignal.any([controller.signal,AbortSignal.timeout(45000)])});
    if(!upstream.ok){if(upstream.status===416)fail(416,'Неверный диапазон.');fail(502,'Не удалось получить медиа из Telegram.');}
    res.statusCode=upstream.status;
    for(const header of ['content-length','content-range'])if(upstream.headers.has(header))res.setHeader(header,upstream.headers.get(header));
    await pipeline(Readable.fromWeb(upstream.body),res);
  }
  async handle(req,res){
    res.setHeader('Permissions-Policy','camera=(), microphone=(self), geolocation=()');res.setHeader('Cross-Origin-Resource-Policy','same-origin');
    res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Referrer-Policy','no-referrer');
    res.setHeader('Content-Security-Policy',"default-src 'self'; script-src 'self' https://telegram.org; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors https://web.telegram.org https://*.telegram.org; base-uri 'none'; form-action 'self'; object-src 'none'");
    try{
      const url=new URL(req.url,'http://localhost');
      if(!['GET','POST','PATCH','DELETE'].includes(req.method))fail(405,'Метод не поддерживается.');
      if(url.pathname==='/api/public-config' && req.method==='GET')return this.json(res,200,{branding:this.bot.config.branding,botUsername:this.bot.config.botUsername,supportLinks:this.bot.config.supportLinks || []});
      if(url.pathname==='/health' && req.method==='GET')return this.json(res,200,{ok:true,version:require('../package.json').version});
      const staticFiles={'/koiutyrtkljkhjghf':'index.html','/koiutyrtkljkhjghf/':'index.html','/reports':'index.html','/likes':'index.html','/likes/':'index.html','/discover':'index.html','/me':'index.html','/chats':'index.html','/':'index.html','/logo.svg':'logo.svg','/app.js':'app.js','/style.css':'style.css'};
      if(/^\/(?:chats|reports)\/\d+\/?$/.test(url.pathname))staticFiles[url.pathname]='index.html';
      if(staticFiles[url.pathname] && req.method==='GET'){
        const name=staticFiles[url.pathname];res.setHeader('Content-Type',name.endsWith('.svg')?'image/svg+xml':name.endsWith('.html')?'text/html; charset=utf-8':name.endsWith('.js')?'application/javascript; charset=utf-8':'text/css; charset=utf-8');res.setHeader('Cache-Control','no-cache');let content=fs.readFileSync(path.join(ROOT,'public',name));if(name==='index.html'){const escape=v=>String(v || '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));content=content.toString().replaceAll('{{DESCRIPTION}}',escape(this.bot.config.branding?.description || '')).replaceAll('{{TITLE}}',escape(this.bot.config.branding?.title || 'Знакомства')).replaceAll('{{ORG}}',escape(this.bot.config.branding?.organization || '')).replaceAll('{{BOT}}',escape(this.bot.config.botUsername)).replaceAll('{{URL}}',escape(this.config.url));}return res.end(content);
      }
      if(!url.pathname.startsWith('/api/'))fail(404,'Страница не найдена.');
      const peer=req.socket.remoteAddress+':'+(req.headers['x-real-ip'] || '');this.rate('ip:'+peer,1800);
      if(url.pathname==='/api/auth' && req.method==='POST'){
        if(req.headers.origin!==this.origin)fail(403,'Неверный источник запроса.');this.rate('auth:'+peer,60);
        const body=await this.body(req);const user=validateInitData(body.initData,this.bot.config.token,this.config.initDataMaxAgeSeconds);

        const session=this.setSession(res,user);return this.json(res,200,this.sessionResult(session));
      }
      const session=req.method==='GET'?this.mediaSession(url) || this.authenticate(req):this.authenticate(req),id=session.id;this.rate('user:'+id);
      if(this.store.banned(id) && !this.bot.admin.isAdmin(id)){const allowed=(req.method==='GET' && (['/api/session','/api/me','/api/discover'].includes(url.pathname) || /^\/api\/(?:profiles\/\d+$|media\/profile\/)/.test(url.pathname))) || (req.method==='PATCH' && url.pathname==='/api/me') || (req.method==='POST' && url.pathname==='/api/upload');if(!allowed)fail(403,'Во время бана доступны только просмотр анкет и редактирование своей.');}
      if(req.method!=='GET')this.csrf(req,session);
      if(url.pathname==='/api/session' && req.method==='GET')return this.json(res,200,this.sessionResult(session));
      if(url.pathname==='/api/upload' && req.method==='POST')return this.json(res,200,await this.upload(req,session,url));
      if(url.pathname==='/api/me' && req.method==='PATCH')return this.json(res,200,{profile:await this.updateProfile(session,await this.body(req))});
      if(url.pathname==='/api/me' && req.method==='GET')return this.json(res,200,{profile:this.profile(this.store.user(id),id),stats:this.store.user(id)?this.store.profileStats(id):null});
      if(url.pathname.startsWith('/api/admin/')){
        if(!this.bot.admin.isStaff(id))fail(403,'Доступ только для администрации.');
        this.rate('admin:'+id,300);
        if(url.pathname==='/api/admin/overview' && req.method==='GET')return this.json(res,200,{stats:this.bot.admin.stats(),template:this.bot.admin.supportTemplate(),autoMessage:this.store.autoMessage() || this.bot.admin.supportTemplate(),isAdmin:this.bot.admin.isAdmin(id)});
        if(url.pathname==='/api/admin/reports' && req.method==='GET'){
          const offset=page(url.searchParams.get('page'))*20;
          const rows=this.store.all('SELECT r.*,u.name AS reporter_name,t.name AS target_name FROM reports r LEFT JOIN users u ON u.user_id=r.reporter_id LEFT JOIN users t ON t.user_id=r.target_user_id ORDER BY r.id DESC LIMIT 21 OFFSET ?',offset);
          return this.json(res,200,{reports:rows.slice(0,20).map(r=>({...r,answer:this.bot.runtime.reportReplies?.[r.id] || null})),hasMore:rows.length>20});
        }
        if(url.pathname==='/api/admin/bans' && req.method==='GET')return this.json(res,200,{bans:this.store.all('SELECT user_id,reason,until_ts FROM bans WHERE until_ts=0 OR until_ts>? ORDER BY id DESC LIMIT 100',now())});
        const banRoute=url.pathname.match(/^\/api\/admin\/users\/(\d+)\/(ban|unban)$/);
        if(banRoute && req.method==='POST'){
          const target=integer(banRoute[1]);if(this.bot.admin.isAdmin(target))fail(403,'Нельзя заблокировать администратора.');if(!this.store.user(target))fail(404,'Пользователь не найден.');
          const body=await this.body(req);if(banRoute[2]==='unban')this.store.unban(target);else{if(typeof body.reason!=='string' || !body.reason.trim() || body.reason.length>500 || typeof body.comment!=='string' || !body.comment.trim() || body.comment.length>1000 || ![0,86400,259200,604800,2592000,7776000].includes(body.seconds))fail(400,'Укажите причину и срок бана.');const result=await this.bot.admin.applyBan(id,target,body.seconds,body.reason.trim(),body.comment.trim());return this.json(res,200,{ok:true,...result});}
          return this.json(res,200,{ok:true});
        }
        const profileDeletion=url.pathname.match(/^\/api\/admin\/users\/(\d+)\/(delete-request|profile)$/);
        if(profileDeletion){
          if(!this.bot.admin.isAdmin(id))fail(403,'Доступ только для администратора.');
          const target=integer(profileDeletion[1]);
          if(profileDeletion[2]==='delete-request' && req.method==='POST'){
            const confirmation=this.bot.admin.requestProfileDeletion(id,target);if(!confirmation)fail(404,'Анкета не найдена или защищена.');const user=this.store.user(target);return this.json(res,200,{confirmation,user:{id:target,name:user.name}});
          }
          if(profileDeletion[2]==='profile' && req.method==='DELETE'){
            const body=await this.body(req);if(!this.bot.admin.confirmProfileDeletion(id,target,body.confirmation))fail(409,'Подтверждение устарело. Повторите удаление.');return this.json(res,200,{ok:true});
          }
        }
        const deletion=url.pathname.match(/^\/api\/admin\/reports\/(\d+)$/);
        if(deletion && req.method==='DELETE'){if(!this.bot.admin.deleteReport(id,integer(deletion[1])))fail(404,'Жалоба не найдена.');return this.json(res,200,{ok:true});}
        const reply=url.pathname.match(/^\/api\/admin\/reports\/(\d+)\/reply$/);
        if(reply && req.method==='POST'){this.rate('reportReply:'+id,60);const reportId=integer(reply[1]);if(!this.store.get('SELECT 1 FROM reports WHERE id=?',reportId))fail(404,'Жалоба не найдена.');const {text}=await this.body(req);if(typeof text!=='string' || !text.trim() || text.length>3500)fail(400,'Введите ответ до 3500 символов.');return this.json(res,200,await this.bot.admin.replyReport(id,reportId,text));}
        if(url.pathname==='/api/admin/support-template' && req.method==='POST'){if(!this.bot.admin.isAdmin(id))fail(403,'Доступ только для администратора.');this.store.setAutoMessage(this.bot.admin.supportTemplate());return this.json(res,200,{ok:true});}
        fail(404,'Действие не найдено.');
      }
      const reportRoute=url.pathname.match(/^\/api\/reports\/(\d+)$/);
      if(reportRoute && req.method==='GET'){const report=this.store.get('SELECT * FROM reports WHERE id=? AND reporter_id=?',integer(reportRoute[1]),id);if(!report)fail(404,'Жалоба недоступна.');return this.json(res,200,{report:{id:report.id,reason:report.reason,answer:this.bot.runtime.reportReplies?.[report.id] || null}});}
      if(!this.bot.admin.isStaff(id))this.needProfile(id);
      if(url.pathname==='/api/discover' && req.method==='GET')return this.json(res,200,{profile:this.profile(this.store.profile(id),id)});
      if(url.pathname==='/api/matches' && req.method==='GET'){
        const users=this.store.all('SELECT u.* FROM users u JOIN matches m ON (u.user_id=m.user1_id OR u.user_id=m.user2_id) WHERE (m.user1_id=? OR m.user2_id=?) AND u.user_id!=? AND COALESCE(u.is_hidden,0)=0 AND NOT EXISTS(SELECT 1 FROM bans b WHERE b.user_id=u.user_id AND (b.until_ts=0 OR b.until_ts>?)) ORDER BY m.id DESC LIMIT 50',id,id,id,now());return this.json(res,200,{profiles:users.map(u=>this.profile(u,id))});
      }
      if(url.pathname==='/api/likes' && req.method==='GET'){
        const offset=page(url.searchParams.get('page'))*30;
        const users=this.store.all(`SELECT u.* FROM users u JOIN likes l ON l.user_id=u.user_id WHERE l.liked_user_id=? AND COALESCE(u.is_hidden,0)=0 AND NOT EXISTS(SELECT 1 FROM bans b WHERE b.user_id=u.user_id AND (b.until_ts=0 OR b.until_ts>?)) ORDER BY l.id DESC LIMIT 31 OFFSET ?`,id,now(),offset);
        return this.json(res,200,{profiles:users.slice(0,30).map(u=>({...this.profile(u,id),mutual:this.store.mutual(id,u.user_id)})),hasMore:users.length>30,mutualCount:this.store.count('SELECT COUNT(*) FROM matches WHERE user1_id=? OR user2_id=?',id,id)});
      }
      if(url.pathname==='/api/chats' && req.method==='GET'){
        const read=this.bot.runtime.miniAppRead?.[id] || {};
        const chats=this.store.conversations(id,page(url.searchParams.get('page'))*15).map(m=>{
          const other=this.store.user(m.other_id);return {id:m.other_id,name:m.name || 'Пользователь',preview:m.message || 'Медиа',at:m.created_at,avatar:other?.photos?this.mediaUrl(`/api/media/profile/${m.other_id}/avatar`,id):null,unread:this.store.count('SELECT COUNT(*) FROM messages WHERE sender_id=? AND receiver_id=? AND id>?',m.other_id,id,read[m.other_id] || 0)};
        });return this.json(res,200,{chats,hasMore:chats.length===15});
      }
      const profileRoute=url.pathname.match(/^\/api\/profiles\/(\d+)(?:\/(like|dislike|report))?$/);
      if(profileRoute){
        const target=integer(profileRoute[1]),action=profileRoute[2];
        if(!action && req.method==='GET')return this.json(res,200,{profile:this.profile(this.accessible(target,id,{conversation:true}),id)});
        if(['like','dislike'].includes(action) && req.method==='POST')return this.json(res,200,await this.react(id,target,action));
        if(action==='report' && req.method==='POST'){
          const body=await this.body(req);const reason=body.reason;this.accessible(target,id,{conversation:true});
          if(typeof reason!=='string' || !reason.trim() || reason.length>2000)fail(400,'Введите причину жалобы до 2000 символов.');
          this.rate('report:'+id,5);this.store.report(id,target,reason);const reportId=this.store.get('SELECT last_insert_rowid() AS id').id;this.bot.launch(()=>this.bot.send(this.bot.config.adminId,`🚩 Жалоба из Mini App\nОт: ${id}\nНа: ${target}\n${reason}`,{inline_keyboard:[[{text:'Анкета',callback_data:`view_${target}`},{text:'Заблокировать',callback_data:`admin_ban_${target}`}],[{text:'Ответить по жалобе',callback_data:`admin_report_reply_${reportId}`},{text:'Удалить жалобу',callback_data:`admin_report_delete_${reportId}`}]]}));return this.json(res,200,{ok:true});
        }
      }
      const chatRoute=url.pathname.match(/^\/api\/chats\/(\d+)\/(messages|read)$/);
      if(chatRoute){
        const target=integer(chatRoute[1]);
        if(chatRoute[2]==='messages' && req.method==='GET'){
          // Данные всегда ограничены собственной парой собеседников, независимо от URL.
          const before=url.searchParams.get('before'),after=url.searchParams.get('after');
          const params=[id,target,target,id];let condition='';if(before){condition+=' AND id<?';params.push(integer(before));}if(after){condition+=' AND id>?';params.push(integer(after));}
          const list=this.store.all(`SELECT * FROM messages WHERE ((sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?))${condition} ORDER BY id ${after?'ASC':'DESC'} LIMIT 30`,...params);
          if(!after)list.reverse();return this.json(res,200,{messages:list.map(m=>this.serializeMessage(m,id)),hasMore:list.length===30});
        }
        if(chatRoute[2]==='messages' && req.method==='POST'){this.rate('send:'+id,120);return this.json(res,201,{message:await this.sendMessage(id,target,await this.body(req))});}
        if(chatRoute[2]==='read' && req.method==='POST'){
          const body=await this.body(req),through=integer(body.through);
          if(!this.store.get('SELECT 1 FROM messages WHERE id=? AND ((sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?))',through,id,target,target,id))fail(403,'Сообщение недоступно.');
          const read=this.bot.runtime.miniAppRead || (this.bot.runtime.miniAppRead={});const chats=read[id] || (read[id]={});chats[target]=Math.max(chats[target] || 0,through);this.bot.persist();return this.json(res,200,{ok:true});
        }
      }
      const mediaRoute=url.pathname.match(/^\/api\/media\/(profile|message)\/(\d+)\/([\w]+)$/);
      if(mediaRoute && req.method==='GET'){
        const target=integer(mediaRoute[2]);let ref;
        if(mediaRoute[1]==='profile'){const user=this.accessible(target,id,{conversation:true});ref=mediaRoute[3]==='video'?user.video:photoRefs(user)[mediaRoute[3]==='avatar'?0:Number(mediaRoute[3])];}
        else{const message=this.store.get('SELECT * FROM messages WHERE id=? AND (sender_id=? OR receiver_id=?)',target,id,id);if(!message)fail(404,'Медиа недоступно.');if(!['photo','video','voice','sticker','animation'].includes(mediaRoute[3]))fail(404,'Медиа недоступно.');ref=message[mediaRoute[3]+'_file_id'];}
        if(!ref)fail(404,'Медиа не найдено.');if(mediaRoute[1]==='profile' && mediaRoute[3]==='avatar')await this.streamAvatar(req,res,ref);else await this.streamFile(req,res,ref);return;
      }
      fail(404,'Неизвестный запрос.');
    } catch(error){
      if(res.headersSent){res.destroy();return;}
      if(!error.status)console.error('Mini App:',error.name);
      this.json(res,error.status || 500,{error:error.status?error.message:'Не удалось выполнить запрос. Попробуйте ещё раз.'});
    }
  }
}

module.exports={MiniApp,validateInitData,HttpError};




