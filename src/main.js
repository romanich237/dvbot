'use strict';

const fs = require('node:fs');
const path = require('node:path');
const ROOT=path.resolve(__dirname,'..');
const { randomInt, randomBytes } = require('node:crypto');
const { Store, moscow } = require('./db');
const { Admin } = require('./admin');
const {premiumParams}=require('./emojis');
const {compressPhoto,readPhoto,available:photoCompressionAvailable}=require('./photos');

const defaults = require('../config.json');
const colleges = defaults.campuses.map(c=>c.name);
const coordinates = Object.fromEntries(defaults.campuses.map(c=>[c.name,c.coordinates]));
const button = (text, data) => ({ text, callback_data: data });
const inline = rows => ({ inline_keyboard: rows });
const keyboard = rows => ({ keyboard: rows.map(row=>row.map(text=>({ text }))), resize_keyboard:true });
const removeKeyboard = { remove_keyboard: true };
const menu = keyboard([['Смотреть анкеты','Лайкнувшие'],['Моя анкета 👤','✉️ Мои сообщения'],['📊 Статистика профиля']]);
const editMenu = keyboard([['Изменить имя','Изменить возраст'],['Изменить колледж','Изменить описание'],['Изменить фото','Изменить видео'],['⬅️ Отмена']]);

const photoMenu = keyboard([['Да, это все фото'],['Нет, хочу добавить еще']]);
const sleep = ms => new Promise(resolve=>setTimeout(resolve,ms));
const spam = text => (text.match(/https?:\/\/\S+|www\.\S+|(?<!\/)t\.me\/\S+|@[a-zA-Z0-9_]+/gi)||[]).length>1;
const escapeXml = text => String(text).replace(/[<>&"']/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&apos;'}[c]));

class Telegram {
  constructor(token) { this.token=token; this.abort=new AbortController(); }
  async call(method, params={}, files={}) {
    const plainParams={...params,...(params.entities?{entities:params.entities.filter(e=>e.type!=='custom_emoji')}:{})};params=premiumParams(params);
    let usedPlain=false;
    for (let attempt=0; attempt<2; attempt++) {
      let body; const hasFiles=Object.keys(files).length>0;
      if (hasFiles) {
        body=new FormData();
        for (const [key,value] of Object.entries(params)) if (value!==undefined && value!==null) body.set(key,typeof value==='object'?JSON.stringify(value):String(value));
        for (const [key,file] of Object.entries(files)) body.set(key,new Blob([file.buffer || fs.readFileSync(file)]),file.name || path.basename(file));
      } else body=JSON.stringify(params);
      try {
        const response=await fetch(`https://api.telegram.org/bot${this.token}/${method}`,{
          method:'POST',headers:hasFiles?{}:{'Content-Type':'application/json'},body,
          signal:AbortSignal.any([this.abort.signal,AbortSignal.timeout(method==='getUpdates'?65000:30000)])
        });
        const data=await response.json();
        if(data.error_code===400 && !usedPlain && /custom.?emoji|emoji.*(?:invalid|not allowed|premium)/i.test(data.description || '')){params=plainParams;usedPlain=true;attempt--;continue;}
        if (data.error_code===429 && attempt===0) { await sleep(Math.min(data.parameters?.retry_after || 1,60)*1000); continue; }
        if (!data.ok && !/message is not modified/.test(data.description || '')) console.error(`Telegram ${method}: ${data.error_code} ${data.description || ''}`);
        return data;
      } catch (error) {
        // Не повторяем отправку при сетевом обрыве: Telegram мог уже принять сообщение.
        if (!this.abort.signal.aborted) console.error(`Telegram ${method}: ${error.name}`);
        return { ok:false, networkError:true };
      }
    }
  }
  stop() { this.abort.abort(); }
}

class DatingBot {
  constructor(config, { store, api, runtimePath=path.join(ROOT,'.dvbot-runtime.json') }={}) {
    this.config=config;
    this.colleges=(config.campuses || defaults.campuses).map(c=>c.name);
    this.coordinates=Object.fromEntries((config.campuses || defaults.campuses).map(c=>[c.name,c.coordinates]));
    this.collegeMenu=keyboard(this.colleges.map(c=>[c]));
    this.store=store || new Store(path.resolve(ROOT,config.database),{create:config.createDatabase===true});
    this.api=api || new Telegram(config.token);
    this.runtimePath=runtimePath;
    this.runtime={ offset:0, states:{}, versionNotifications:{} };
    if (fs.existsSync(runtimePath)) this.runtime={...this.runtime,...JSON.parse(fs.readFileSync(runtimePath,'utf8'))};
    this.admin=new Admin(this);
    this.adViews=new Map();
    this.stopping=false;
    this.background=new Set();
  }
  persist() {
    const tmp=this.runtimePath+'.tmp';
    fs.writeFileSync(tmp,JSON.stringify(this.runtime),{mode:0o600});
    fs.renameSync(tmp,this.runtimePath);
  }
  state(id) { return this.runtime.states[id] || { step:this.store.user(id)?'registered':'start',data:{} }; }
  setState(id,step,data={}) { this.runtime.states[id]={step,data}; this.persist(); }
  reset(id) { delete this.runtime.states[id];if(this.runtime.profileDeletions)delete this.runtime.profileDeletions[id]; this.persist(); }
  async send(chat,text,markup) {
    // Telegram ограничивает длину сообщения. Делим по символам, не теряя конец истории.
    const chunks=Array.from(String(text).matchAll(/[\s\S]{1,3800}/gu),m=>m[0]);
    let result;
    for (let i=0;i<chunks.length;i++) result=await this.api.call('sendMessage',{chat_id:chat,text:chunks[i],...(i===chunks.length-1 && markup?{reply_markup:markup}:{})});
    return result;
  }
  async answer(query,text='') { return this.api.call('answerCallbackQuery',{callback_query_id:query.id,text}); }
  launch(task) {
    const promise=Promise.resolve().then(task).catch(e=>console.error('Фоновая задача:',e.message)).finally(()=>this.background.delete(promise));
    this.background.add(promise);
  }
  requestProfileDeletion(id){
    if(!this.store.user(id))return null;
    const requests=this.runtime.profileDeletions || (this.runtime.profileDeletions={});
    const request={token:randomBytes(12).toString('hex'),profileToken:this.store.token(id),expires:Date.now()+300000};requests[id]=request;this.persist();return request.token;
  }
  restoreProfilePreferences(id){
    const preferences=this.runtime.deletedProfilePreferences?.[id];
    if(preferences)this.store.update(id,'mailing_disabled_until',preferences.mailingDisabledUntil);
  }
  confirmProfileDeletion(id,token){
    const request=this.runtime.profileDeletions?.[id],user=this.store.user(id);
    if(!user || !request || request.token!==token || request.expires<Date.now() || request.profileToken!==user.profile_token)return false;
    const preferences=this.runtime.deletedProfilePreferences || (this.runtime.deletedProfilePreferences={});
    preferences[id]={mailingDisabledUntil:user.mailing_disabled_until || null};this.persist();
    if(!this.store.deleteProfile(id))return false;
    this.reset(id);this.adViews.delete(id);return true;
  }
  ownKeyboard(user) {
    return inline([[button('✏️ Редактировать','edit_profile'),button('⚙️ Настройки','settings')],[button('🚀 Поднять анкету','boost_profile'),button(user.is_hidden?'🟢 Включить анкету':'🔴 Отключить анкету','toggle_visibility')]]);
  }
  reactions(id) {
    return inline([[button('❤️',`like_${id}`),button('💌',`write_${id}`),button('🚩',`report_${id}`)],[button('➡️ Следующая',`next_${id}`),button('👎 Не интересно',`dislike_${id}`)]]);
  }
  profileKeyboard(id,allow=true) {
    const token=this.store.token(id);
    const rows=[[{text:'👤 Профиль',url:`https://t.me/${this.config.botUsername}?start=profile_${token}`}]];
    if (allow) rows.push([button('✍️ Через бота',`write_${id}`)]);
    rows.push([button('👀 Посмотреть анкету',`view_${id}`)]);
    return inline(rows);
  }
  localPhoto(ref) {
    if (/^(?:https?:\/\/)/i.test(ref)) return null;
    const normalized=ref.replaceAll('\\','/');
    const directory=path.resolve(ROOT,this.config.photoDirectory);
    const candidates=[path.resolve(ROOT,normalized)];
    if(normalized.includes('/') || /\.(?:jpe?g|png|webp)$/i.test(normalized))candidates.push(path.join(directory,path.basename(normalized)));
    return candidates.find(file=>file.startsWith(directory+path.sep) && fs.existsSync(file) && fs.statSync(file).isFile()) || null;
  }

  async preparePhoto(ref){
    if(this.config.photoCompression?.enabled===false || !photoCompressionAvailable)return ref;
    const filename=require('node:crypto').createHash('sha256').update(ref).digest('hex')+'.jpg';
    const directory=path.resolve(ROOT,this.config.photoDirectory);
    const relative=path.join(this.config.photoDirectory,filename),destination=path.join(directory,filename);
    if(fs.existsSync(destination))return relative;
    this.photoJobs ||= new Map();if(this.photoJobs.has(ref))return this.photoJobs.get(ref);
    const job=(async()=>{
      try{
        const result=await this.api.call('getFile',{file_id:ref});const remote=result?.result?.file_path;
        if(!result?.ok || typeof remote!=='string' || remote.includes('..') || !/^[\w/.-]+$/.test(remote))return ref;
        const response=await fetch(`https://api.telegram.org/file/bot${this.config.token}/${remote}`,{signal:AbortSignal.timeout(30000)});
        const input=await readPhoto(response),photo=await compressPhoto(input,this.config.photoCompression);
        if(!photo.compressed)return ref;
        fs.mkdirSync(directory,{recursive:true});fs.writeFileSync(destination+'.tmp',photo.buffer,{mode:0o600});fs.renameSync(destination+'.tmp',destination);
        return relative;
      }catch{console.error('Сжатие фото недоступно; используем фото Telegram.');return ref;}
    })().finally(()=>this.photoJobs.delete(ref));this.photoJobs.set(ref,job);return job;
  }
  async media(chat,type,ref,caption,markup) {
    const method={photo:'sendPhoto',video:'sendVideo',voice:'sendVoice',sticker:'sendSticker',animation:'sendAnimation'}[type];
    const local=type==='photo'?this.localPhoto(ref):null;
    return this.api.call(method,{chat_id:chat,[type]:local?undefined:ref,...(caption && type!=='sticker'?{caption:caption.slice(0,1000)}:{}),...(markup?{reply_markup:markup}:{})},local?{photo:local}:{});
  }
  distance(a,b) {
    const x=this.coordinates[a],y=this.coordinates[b]; if (!x || !y) return null;
    const rad=n=>n*Math.PI/180;
    const h=Math.sin(rad(y[0]-x[0])/2)**2+Math.cos(rad(x[0]))*Math.cos(rad(y[0]))*Math.sin(rad(y[1]-x[1])/2)**2;
    return Math.round(6371*2*Math.atan2(Math.sqrt(h),Math.sqrt(1-h)));
  }
  async showProfile(chat,user,{viewer,link=false,own=false,recommendation=false,captionPrefix=''}={}) {
    if (!user) return this.send(chat,'Анкета не найдена.');
    if (!own && (user.is_hidden || this.store.banned(user.user_id)) && !this.admin.isStaff(viewer)) return this.send(chat,'Анкета недоступна.');
    const allow=!link || this.store.mutual(viewer,user.user_id);
    let caption=`${captionPrefix}Имя: ${link && !allow?'Пользователь':user.name}\nВозраст: ${user.age}\nКолледж: ${user.college}`;
    const current=this.store.user(viewer);
    if (recommendation && current?.view_scope==='all' && current.college!==user.college) {
      const km=this.distance(current.college,user.college); if (km!==null) caption+=`\nРасстояние: ~${km} км`;
    }
    if (user.bio) caption+=`\nО себе: ${user.bio}`;
    const markup=own?this.ownKeyboard(user):recommendation?this.reactions(user.user_id):this.profileKeyboard(user.user_id,allow);
    const photos=(user.photos || '').split(',').map(p=>p.trim()).filter(Boolean).slice(0,10);
    const items=photos.map(ref=>({type:'photo',ref}));
    if(user.video)items.push({type:'video',ref:user.video});
    if(items.length===1){
      const result=await this.media(chat,items[0].type,items[0].ref,caption,markup);
      if(!result?.ok)await this.send(chat,caption,markup);
    }else if(items.length>1){
      const files={};
      const media=items.slice(0,10).map(({type,ref},i)=>{
        const local=type==='photo'?this.localPhoto(ref):null;if(local)files[`media${i}`]=local;
        return {type,media:local?`attach://media${i}`:ref,...(i===0?{caption:caption.slice(0,1000)}:{})};
      });
      const result=await this.api.call('sendMediaGroup',{chat_id:chat,media},files);
      await this.send(chat,result?.ok?'Выбери действие:':caption,markup);
    }else await this.send(chat,caption,markup);
  }

  async profiles(id,chat) {
    const user=this.store.profile(id);
    if (!user) return this.send(chat,'Анкет не найдено 😔\nПриглашай друзей!',inline([[{text:'📢 Поделиться ссылкой',url:`https://t.me/share/url?url=${encodeURIComponent('https://t.me/'+this.config.botUsername)}`}]]));
    await this.showProfile(chat,user,{viewer:id,recommendation:true});
    const count=(this.adViews.get(id)||0)+1; this.adViews.set(id,count);
    const ad=this.store.autoMessage() || this.admin.supportTemplate();
    if (ad && !this.store.mailingDisabled(id) && count%this.config.adEveryViews===0) await this.sendMailing(chat,`📢 ${ad}`);
  }
  async settings(id,chat) {
    const user=this.store.user(id); if (!user) return;
    await this.send(chat,'⚙️ Настройки анкеты:',inline([
      [button(`${user.view_scope!=='all'?'✅ ':''}Мой колледж`,'set_view_scope_college'),button(`${user.view_scope==='all'?'✅ ':''}Все колледжи`,'set_view_scope_all')],
      [button(user.hide_from_top?'✅ Показать в топе':'❌ Скрыть из топа','toggle_hide_from_top')],
      [button(user.is_hidden?'🟢 Включить анкету':'🔴 Отключить анкету','toggle_visibility')]
    ]));
  }
  async chats(id,chat,page=0) {
    const list=this.store.conversations(id,page*15);
    if (!list.length) return this.send(chat,'У тебя пока нет сообщений 💬');
    const rows=list.map(c=>[button(`💬 ${c.name||'Пользователь'} · ${(c.message||'Медиа').slice(0,25)}`,`open_chat_${c.other_id}`)]);
    const nav=[]; if (page>0) nav.push(button('⬅️',`chats_page_${page-1}`));
    if (list.length===15) nav.push(button('➡️',`chats_page_${page+1}`));
    if (nav.length) rows.push(nav);
    return this.send(chat,`💬 Мои чаты\nНеотвеченных: ${this.store.unanswered(id)}`,inline(rows));
  }
  async chat(id,chat,target,page=0) {
    const other=this.store.user(target); const name=other?.name || 'Пользователь';
    const messages=this.store.history(id,target,20,page*20);
    const rows=[[button('✍️ Написать',`write_${target}`)],[button('⬅️ К чатам','back_to_chats')]];
    const nav=[]; if (messages.length===20) nav.push(button('Более ранние',`history_${target}_${page+1}`));
    if (page>0) nav.push(button('Новые',`history_${target}_${page-1}`));
    if (nav.length) rows.push(nav);
    const markup=inline(rows);
    const text=`💬 Чат с ${name}\n\n`+messages.map(m=>`${m.sender_id===id?'➡️':'⬅️'} ${m.message || 'Медиа'} [${m.created_at}]`).join('\n');
    let rendered=false;
    // Как и в оригинале, графическая история опциональна. Изображение в памяти, photo/ не меняется.
    try {
      const sharp=require('sharp');
      const lines=[];
      for (const m of messages) {
        const chars=Array.from(`${m.sender_id===id?'Ты':name}: ${m.message || 'Медиа'} (${m.created_at})`);
        while (chars.length) lines.push(chars.splice(0,65).join(''));
      }
      const height=100+lines.length*26;
      const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="900" height="${height}"><rect width="900" height="${height}" fill="#edf3f8"/><text x="30" y="40" font-family="DejaVu Sans" font-size="24">${escapeXml('Чат с '+name)}</text>${lines.map((line,i)=>`<text x="30" y="${85+i*26}" font-family="DejaVu Sans" font-size="18">${escapeXml(line)}</text>`).join('')}</svg>`;
      const buffer=await sharp(Buffer.from(svg)).png().toBuffer();
      rendered=(await this.api.call('sendPhoto',{chat_id:chat,caption:`💬 Чат с ${name}`,reply_markup:markup},{photo:{buffer,name:'chat.png'}}))?.ok;
    } catch (error) { if (error.code!=='MODULE_NOT_FOUND') console.error('Изображение чата:',error.message); }
    if (!rendered) await this.send(chat,messages.length?text:`💬 Чат с ${name}\nПока нет сообщений.`,markup);
    for (const m of messages) for (const type of ['voice','photo','video','sticker','animation']) if (m[`${type}_file_id`]) {
      await this.media(chat,type,m[`${type}_file_id`],`${m.sender_id===id?'От тебя':'От '+name} · ${m.created_at}`);
      await sleep(100);
    }
  }
  async write(id,chat,target,message) {
    if (!this.store.user(target) || target===id || this.store.banned(target)) return this.send(chat,'Получатель недоступен.');
    const content={text:message.text || message.caption || ''};
    for (const type of ['voice','video','sticker','animation']) if (message[type]) content[type]=message[type].file_id;
    if (message.photo) content.photo=await this.preparePhoto(message.photo.at(-1).file_id);
    if (!content.text && !Object.keys(content).some(k=>k!=='text')) return this.send(chat,'Отправь текст, фото, видео, голосовое, стикер или GIF.');
    if (content.text.length>3500) return this.send(chat,'Максимальная длина сообщения — 3500 символов.');
    if (!content.text) content.text={voice:'🎤 Голосовое сообщение',photo:'📷 Фото',video:'🎥 Видео',sticker:'🎭 Стикер',animation:'🎬 GIF'}[Object.keys(content).find(k=>k!=='text')];
    const saved=this.store.saveMessage(id,target,content);
    const markup=this.messageKeyboard(id,saved.id),sender=this.store.user(id)?.name || 'Пользователь';
    if (saved.notify) await this.send(target,`📩 Сообщение от ${sender}.\nНеотвеченных чатов: ${this.store.unanswered(target)}`,markup);
    const type=Object.keys(content).find(k=>k!=='text');
    const delivered=`💬 ${sender}\n${content.text}`;
    const response=type?await this.media(target,type,content[type],delivered,markup):await this.send(target,delivered,markup);
    this.reset(id);
    await this.send(chat,response?.ok?'✅ Сообщение отправлено!':'Сообщение сохранено в чате. Уведомить получателя не удалось.',menu);
  }
  async finish(id,chat,username,data) {
    this.store.register(id,data,username);this.restoreProfilePreferences(id); this.reset(id);
    await this.send(chat,'✅ Анкета готова!',menu);
    await this.showProfile(chat,this.store.user(id),{viewer:id,own:true});
  }
  async registration(id,chat,message,state) {
    const text=message.text || ''; const {step,data}=state; const editing=step.startsWith('edit_'); const field=editing?step.slice(5):step;
    const change=(next,updated=data)=>this.setState(id,next,updated);
    const done=async(field,value)=>{this.store.update(id,field,value);this.reset(id);await this.send(chat,'✅ Сохранено.',menu);await this.showProfile(chat,this.store.user(id),{viewer:id,own:true});};
    if (field==='start') {
      if (text==='Да') { change('college',{}); await this.send(chat,'Выбери свой колледж:',this.collegeMenu); }
      else await this.send(chat,text==='Нет'?'Бот предназначен для участников сообщества.':'Ты участник сообщества?',keyboard([['Да','Нет']]));
    } else if (field==='college') {
      if (!this.colleges.includes(text)) return this.send(chat,'Выбери колледж из списка:',this.collegeMenu);
      if (editing) return done('college',text);
      change('name',{...data,college:text}); await this.send(chat,'Введи своё имя:',removeKeyboard);
    } else if (field==='name') {
      if (!/^[А-Яа-яЁё\s-]{2,60}$/.test(text)) return this.send(chat,'Введи имя русскими буквами (2–60 символов).');
      if (editing) return done('name',text);
      change('age',{...data,name:text}); await this.send(chat,'Введи возраст:');
    } else if (field==='age') {
      if (!/^\d+$/.test(text) || Number(text)<14 || Number(text)>30) return this.send(chat,'Введи возраст от 14 до 30 лет.');
      if (editing) return done('age',Number(text));
      change('photos',{...data,age:Number(text),photos:[]}); await this.send(chat,'Загрузи первую фотографию:',removeKeyboard);
    } else if (field==='photos') {
      const photos=[...(data.photos || [])];
      if (message.photo && photos.length<3) photos.push(await this.preparePhoto(message.photo.at(-1).file_id));
      const complete=photos.length>=3 || text==='Да, это все фото';
      if (complete && photos.length) {
        if (editing) return done('photos',photos.join(','));
        change('bio',{...data,photos}); await this.send(chat,'Напиши краткое описание о себе (до 500 символов):',removeKeyboard);
      } else { change(step,{...data,photos}); await this.send(chat,`Сохранено фото: ${photos.length}/3. Загрузи фото или подтверди завершение.`,photoMenu); }
    } else if (field==='bio') {
      if (!text || text.length>500 || spam(text)) return this.send(chat,'Описание: 1–500 символов, не более одной ссылки или @username.');
      if (editing) return done('bio',text);
      change('video',{...data,bio:text}); await this.send(chat,'Добавь видео или нажми «Пропустить»:',keyboard([['Пропустить']]));
    } else if (field==='video') {
      if (!message.video && text!=='Пропустить') return this.send(chat,'Отправь видео или нажми «Пропустить».');
      if (editing) return done('video',message.video?.file_id || null);
      await this.finish(id,chat,message.from.username,{...data,video:message.video?.file_id || null});
    } else return false;
    return true;
  }
  paymentValid(payment,id) {
    return payment.currency==='XTR' && payment.total_amount===this.config.mailingDisableStars && payment.invoice_payload===`disable_mailing_${id}` && !!this.store.user(id);
  }
  async processMessage(message) {
    const id=message.from?.id,chat=message.chat.id,text=message.text || '';
    if (!id || message.chat.type!=='private') return;
    this.store.run('DELETE FROM blocked_users WHERE user_id=?',id);
    if(this.store.banned(id) && !this.admin.isAdmin(id)){const step=this.state(id).step;const allowed=['Смотреть анкеты','Моя анкета 👤','🌐 Мини-приложение','/app','/web','/cancel','⬅️ Отмена'].includes(text) || /^\/start(?:\s|$)/.test(text) || step==='edit_menu' || /^edit_/.test(step);if(!allowed){this.reset(id);return this.send(chat,'Во время бана доступны только просмотр анкет и редактирование своей.',menu);}}
    if (message.successful_payment) {
      const payment=message.successful_payment;
      if (!this.paymentValid(payment,id)) return;
      // Telegram update_id хранится отдельно от пользовательской БД.
      const charge=payment.telegram_payment_charge_id;
      const paid=this.runtime.payments || (this.runtime.payments={});
      if (paid[charge]) return;
      const until=moscow(new Date(Date.now()+this.config.mailingDisableMonths*30*86400000));
      this.store.update(id,'mailing_disabled_until',until); paid[charge]=true; this.persist();
      return this.send(chat,`✅ Рассылка отключена до ${until}.`);
    }
    // Навигация и команды не являются содержимым жалобы, переписки или формы.
    const command=/^\/[a-zA-Z0-9_]+(?:@[a-zA-Z0-9_]+)?(?:\s|$)/.test(text);
    const navigation=menu.keyboard.flat().some(item=>item.text===text) || text==='🌐 Мини-приложение';
    if(command || navigation)this.reset(id);
    if (await this.admin.message(message)) return;
    if(command && !['/start','/cancel','/app','/matches','/web'].includes(text.split(/\s+/)[0]))return;
    if (text==='/cancel' || text==='⬅️ Отмена') { this.reset(id); return this.send(chat,'Действие отменено.',menu); }
    if (/^\/start(?:\s|$)/.test(text)) {
      this.reset(id);
      const token=text.split(/\s+/)[1];
      if (token?.startsWith('profile_')) return this.showProfile(chat,this.store.byToken(token.slice(8)),{viewer:id,link:true});
      if (this.store.user(id)) return this.send(chat,'Добро пожаловать!',menu);
      this.setState(id,'start',{}); return this.send(chat,'Привет! Ты участник сообщества?',keyboard([['Да','Нет']]));
    }
    if(text==='/app' || text==='🌐 Мини-приложение') return this.send(chat,'Анкеты и диалоги в мини-приложении:',this.appKeyboard());
    const state=this.state(id);
    if (/^(?:start|college|name|age|photos|bio|video|edit_(?:college|name|age|photos|bio|video))$/.test(state.step)) return this.registration(id,chat,message,state);
    if (!this.store.user(id)) return this.send(chat,'Сначала создай анкету: /start');
    if (state.step==='write' || state.step==='reply') return this.write(id,chat,state.data.target,message);
    if (state.step==='report') {
      if (!text || text.length>2000) return this.send(chat,'Опиши причину жалобы (до 2000 символов).');
      this.store.report(id,state.data.target,text,state.data.messageId);
      const reportId=this.store.get('SELECT last_insert_rowid() AS id').id;
      const original=state.data.messageId?this.store.get('SELECT message FROM messages WHERE id=?',state.data.messageId):null;
      await this.send(this.config.adminId,`🚩 Жалоба\nОт: ${id}\nНа: ${state.data.target}\n${text}${original?'\nСообщение: '+original.message:''}`,inline([[button('Анкета',`view_${state.data.target}`),button('Заблокировать',`admin_ban_${state.data.target}`)],[button('Ответить по жалобе',`admin_report_reply_${reportId}`),button('Удалить жалобу',`admin_report_delete_${reportId}`)]]));
      this.reset(id); return this.send(chat,'Спасибо! Жалоба отправлена администратору.',menu);
    }
    if (state.step==='edit_menu') {
      const fields={'Изменить имя':'name','Изменить возраст':'age','Изменить колледж':'college','Изменить описание':'bio','Изменить фото':'photos','Изменить видео':'video'};
      const field=fields[text]; if (!field) return this.send(chat,'Выбери поле:',editMenu);
      this.setState(id,'edit_'+field,field==='photos'?{photos:[]}:{});
      return this.send(chat,'Отправь новое значение:',field==='college'?this.collegeMenu:field==='video'?keyboard([['Пропустить']]):removeKeyboard);
    }
    if (text==='Смотреть анкеты') return this.profiles(id,chat);
    if (text==='Моя анкета 👤') return this.showProfile(chat,this.store.user(id),{viewer:id,own:true});
    if (text==='✉️ Мои сообщения') return this.config.miniApp?.enabled?this.send(chat,'✉️ Мои диалоги',this.appKeyboard('chats')):this.chats(id,chat);
    if (text==='📊 Статистика профиля') return this.send(chat,this.store.profileStats(id));
    if (text==='Лайкнувшие' || text==='/matches') {
      const count=this.store.count('SELECT COUNT(*) FROM matches WHERE user1_id=? OR user2_id=?',id,id);
      return this.send(chat,`💖 Взаимных симпатий: ${count}`,count>0?this.appKeyboard('likes','Посмотреть симпатии'):undefined);
    }

    if (text==='/web') {
      let code; do {code=String(randomInt(1000000)).padStart(6,'0');} while(this.store.get('SELECT 1 FROM web_auth_codes WHERE code=?',code));
      this.store.transaction(()=>{
        this.store.run('DELETE FROM web_auth_codes WHERE user_id=? AND used=0',id);
        this.store.run('INSERT INTO web_auth_codes(user_id,code,expires_at) VALUES(?,?,?)',id,code,moscow(new Date(Date.now()+600000)));
      });
      return this.send(chat,`🔐 Код для входа на сайт: ${code}\nДействителен 10 минут.`);
    }
    return this.send(chat,'Выбери действие:',menu);
  }
  async callback(query) {
    const id=query.from.id,chat=query.message?.chat.id,data=query.data || '';
    if (!chat || query.message.chat.type!=='private') return this.answer(query);
    if (await this.admin.callback(query)) return;
    const reportAnswer=data.match(/^report_answer_(\d+)$/);
    if(reportAnswer){await this.answer(query);const report=this.store.get('SELECT * FROM reports WHERE id=? AND reporter_id=?',Number(reportAnswer[1]),id);const answer=report && this.runtime.reportReplies?.[report.id];return this.send(chat,answer?`Ответ по вашей жалобе #${report.id}\n\n${answer.text}`:'Ответ недоступен.');}
    if(this.store.banned(id) && !this.admin.isAdmin(id) && !/^(?:(?:next|view)_\d+|edit_profile|settings|toggle_visibility|toggle_hide_from_top|set_view_scope_(?:all|college)|mailing_(?:off|on|menu))$/.test(data))return this.answer(query,'Во время бана можно только смотреть и редактировать анкеты');
    if (!this.store.user(id)) return this.answer(query,'Сначала создай анкету: /start');
    const match=data.match(/^(like|next|view|dislike|write|send_msg|cancel_msg|open_chat)_(\d+)$/);
    await this.answer(query);
    if (match) {
      const action=match[1],target=Number(match[2]);
      if (action==='next') return this.profiles(id,chat);
      if (action==='cancel_msg') { this.reset(id); return this.send(chat,'Отменено.',menu); }
      if (action==='open_chat') return this.chat(id,chat,target);
      const user=this.store.user(target);
      if (!user || this.store.banned(target)) return this.send(chat,'Анкета недоступна.');
      if (action==='view') return this.showProfile(chat,user,{viewer:id});
      if (action==='write' || action==='send_msg') {this.setState(id,'write',{target});return this.send(chat,'Введи сообщение или отправь медиа. Для отмены: /cancel');}
      if (action==='dislike') this.store.run('INSERT OR IGNORE INTO dislikes(user_id,disliked_user_id) VALUES(?,?)',id,target);
      if (action==='like') {
        const result=this.store.like(id,target);
        if (result.added) await this.showProfile(target,this.store.user(id),{viewer:target,captionPrefix:'💖 Твоя анкета понравилась!\n\n'});
        if (result.matched) {
          await this.showProfile(id,user,{viewer:id,captionPrefix:'💖 У вас взаимная симпатия!\n\n'});
          await this.send(target,'💖 У вас взаимная симпатия!',this.profileKeyboard(id));
        }
      }
      return this.profiles(id,chat);
    }
    if (data==='edit_profile') {this.setState(id,'edit_menu');return this.send(chat,'Что хочешь изменить?',editMenu);}
    if (data==='settings') return this.settings(id,chat);
    if (data==='toggle_visibility' || data==='toggle_hide_from_top') {
      const field=data==='toggle_visibility'?'is_hidden':'hide_from_top'; this.store.update(id,field,this.store.user(id)[field]?0:1); return this.settings(id,chat);
    }
    if (data==='set_view_scope_college' || data==='set_view_scope_all') {this.store.update(id,'view_scope',data.endsWith('_all')?'all':'college');return this.settings(id,chat);}
    if (data==='boost_profile') {const hours=this.store.boost(id);return this.send(chat,hours?`Повторное поднятие через ${hours} ч.`:'🚀 Анкета поднята!');}
    if (data==='back_to_chats') return this.chats(id,chat);
    const page=data.match(/^chats_page_(\d+)$/); if (page) return this.chats(id,chat,Number(page[1]));
    const history=data.match(/^history_(\d+)_(\d+)$/); if (history) return this.chat(id,chat,Number(history[1]),Number(history[2]));
    const report=data.match(/^report_(\d+)$/);
    if (report) {this.setState(id,'report',{target:Number(report[1])});return this.send(chat,'Опиши причину жалобы:');}
    const reply=data.match(/^(reply_msg|report_msg)_(\d+)_(\d+)$/);
    if (reply) {
      const target=Number(reply[2]),messageId=Number(reply[3]);
      const message=this.store.get('SELECT * FROM messages WHERE id=? AND sender_id=? AND receiver_id=?',messageId,target,id);
      if (!message) return this.send(chat,'Сообщение недоступно.');
      this.setState(id,reply[1]==='reply_msg'?'reply':'report',{target,messageId});return this.send(chat,reply[1]==='reply_msg'?'Введи ответ:':'Опиши причину жалобы:');
    }
    if(['disable_mailing','mailing_menu','mailing_off','mailing_on'].includes(data)) {
      if(!(this.runtime.mailingReceipts?.[id] || []).includes(query.message.message_id))return this.send(chat,'Отказаться от рассылки можно через кнопку в полученном сообщении рассылки.');
      if(data==='mailing_off')this.store.update(id,'mailing_disabled_until','9999-12-31 23:59:59');
      if(data==='mailing_on')this.store.update(id,'mailing_disabled_until',null);
      return this.mailingMenu(id,chat);
    }
  }
  rememberMailing(chat,result){
    if(!result?.ok || !result.result?.message_id)return;
    const receipts=this.runtime.mailingReceipts || (this.runtime.mailingReceipts={});
    receipts[chat]=[...(receipts[chat] || []),result.result.message_id].slice(-500);this.persist();
  }
  async sendMailing(chat,text,route,includeChannels=true,appTitle,entities=[]){
    const markup=this.mailingKeyboard();if(!includeChannels && (this.config.supportLinks || []).length)markup.inline_keyboard.shift();if(route && this.config.miniApp?.enabled)markup.inline_keyboard.unshift(...this.appKeyboard(route,appTitle).inline_keyboard);
    const result=entities.length?await this.api.call('sendMessage',{chat_id:chat,text,entities,reply_markup:markup}):await this.send(chat,text,markup);this.rememberMailing(chat,result);
    if(result?.ok)this.store.run('DELETE FROM blocked_users WHERE user_id=?',chat);
    else if(result?.error_code===403 && /blocked by the user/i.test(result.description || ''))this.store.run('INSERT OR IGNORE INTO blocked_users(user_id) VALUES(?)',chat);
    return result;
  }
  mailingKeyboard(){return inline([(this.config.supportLinks || []).map(({text,url})=>({text,url})),[button('🔕 Отказаться от рассылки','mailing_off')]].filter(row=>row.length));}
  async mailingMenu(id,chat){
    if(!this.store.user(id))return this.send(chat,'Сначала создайте анкету через /start.');
    const disabled=this.store.mailingDisabled(id);
    const result=await this.send(chat,disabled?'🔕 Вы отписаны от рассылки. Рекламные сообщения отключены.':'📢 Вы подписаны на рассылку. От неё можно бесплатно отказаться.',inline([[button(disabled?'🔔 Подписаться снова':'🔕 Выйти из рассылки',disabled?'mailing_on':'mailing_off')]]));
    this.rememberMailing(chat,result);
    if(result?.ok)this.store.run('DELETE FROM blocked_users WHERE user_id=?',chat);
    else if(result?.error_code===403 && /blocked by the user/i.test(result.description || ''))this.store.run('INSERT OR IGNORE INTO blocked_users(user_id) VALUES(?)',chat);
    return result;
  }
  async processUpdate(update) {
    if (update.pre_checkout_query) {
      const query=update.pre_checkout_query; const valid=this.paymentValid(query,query.from.id);
      await this.api.call('answerPreCheckoutQuery',{pre_checkout_query_id:query.id,ok:valid,...(!valid?{error_message:'Неизвестный товар или неверная сумма.'}:{})});
    } else if (update.callback_query) await this.callback(update.callback_query);
    else if (update.message) await this.processMessage(update.message);
  }
  async configureMiniApp(enabled) {
    if(enabled && !this.web){
      const {MiniApp}=require('./web');const web=new MiniApp(this);
      await web.start();this.web=web;
    }
    if(!enabled && this.web){await this.web.stop();this.web=null;}
    await this.api.call('setChatMenuButton',{menu_button:enabled?{type:'web_app',text:'Открыть',web_app:{url:this.config.miniApp.url}}:{type:'default'}});
    const commands=[{command:'start',description:'Главное меню'},...(enabled?[{command:'app',description:'Открыть мини-приложение'}]:[]),{command:'cancel',description:'Отменить действие'}];
    await this.api.call('setMyCommands',{commands});
    for(const staff of [{user_id:this.config.adminId},...this.store.all("SELECT user_id FROM staff WHERE role='moderator'")])await this.api.call('setMyCommands',{scope:{type:'chat',chat_id:staff.user_id},commands:[...commands,{command:'admin',description:'Панель администратора'}]});
  }
  async toggleMiniApp(enabled) {
    if(this.miniAppChanging)throw new Error('Настройка уже изменяется.');
    this.miniAppChanging=true;const previous=this.config.miniApp.enabled;
    try{
      await this.configureMiniApp(enabled);
      const configPath=path.join(ROOT,'config.json');
      const saved=JSON.parse(fs.readFileSync(configPath,'utf8'));saved.miniApp.enabled=enabled;
      fs.writeFileSync(configPath+'.tmp',JSON.stringify(saved,null,2)+'\n',{mode:0o600});
      fs.renameSync(configPath+'.tmp',configPath);this.config.miniApp.enabled=enabled;
    }catch(error){await this.configureMiniApp(previous).catch(()=>{});throw error;}
    finally{this.miniAppChanging=false;}
  }
  async run() {
    const me=await this.api.call('getMe'); if (!me?.ok) throw new Error('Не удалось авторизовать Telegram-бота. Проверьте token.');
    if(!me.result?.username)throw new Error('Telegram не вернул username бота.');
    this.config.botUsername=me.result.username;
    if(!this.runtime.descriptionInitialized)this.runtime.descriptionInitialized={};
    const botId=String(me.result.id);
    if(!this.runtime.descriptionInitialized[botId]){
      const result=await this.api.call('setMyDescription',{description:'Бот создан при помощи https://github.com/romanich237/dvbot'});
      if(result?.ok){this.runtime.descriptionInitialized[botId]=true;this.persist();}
      else console.error('Не удалось установить начальное описание бота; повторим при следующем запуске.');
    }
    const deleted=await this.api.call('deleteWebhook',{drop_pending_updates:false}); if (!deleted?.ok) throw new Error('Не удалось отключить webhook для long polling.');
    await this.configureMiniApp(this.config.miniApp?.enabled===true);
    console.log(`dvbot v${require('../package.json').version} запущен · администратор ${this.config.adminId}`);
    this.admin.start();
    let statsTime=0;
    while (!this.stopping) {
      const updates=await this.api.call('getUpdates',{offset:this.runtime.offset,timeout:40,allowed_updates:['message','callback_query','pre_checkout_query']});
      if (!updates?.ok) {if(updates?.error_code===409) throw new Error('Уже запущен другой экземпляр бота. Остановите старый процесс.');if(!this.stopping)await sleep(3000);continue;}
      for (const update of updates.result || []) {
        if (this.stopping) break;
        try {await this.processUpdate(update);} catch(error) {
          console.error(`Ошибка update ${update.update_id}: ${error.message}`);
          const chat=update.message?.chat.id || update.callback_query?.message?.chat.id;
          if (chat) await this.send(chat,'Не удалось выполнить действие. Попробуй ещё раз.');
        }
        this.runtime.offset=update.update_id+1; this.persist();
      }
      if (!this.stopping && this.config.statsChannelId && Date.now()-statsTime>this.config.statsIntervalSeconds*1000) {
        statsTime=Date.now(); this.launch(()=>this.api.call('editMessageText',{chat_id:this.config.statsChannelId,message_id:this.config.statsMessageId,text:this.admin.stats(false)}));
      }
    }
    await Promise.allSettled([...this.background]);
  }
  appKeyboard(route,text='🌐 Открыть мини-приложение') {
    return this.config.miniApp?.enabled?{inline_keyboard:[[{text,web_app:{url:route?new URL('/'+route,this.config.miniApp.url).href:this.config.miniApp.url}}]]}:undefined;
  }
  messageKeyboard(sender,messageId) {
    const rows=[];
    if(this.config.miniApp?.enabled){const url=new URL(this.config.miniApp.url);url.hash='';url.searchParams.set('chat',sender);rows.push([{text:'🌐 Ответить в Mini App',web_app:{url:url.href}}]);}
    rows.push([button('💬 Ответить в боте',`reply_msg_${sender}_${messageId}`)],[button('🚩 Пожаловаться',`report_msg_${sender}_${messageId}`)]);
    return inline(rows);
  }
  async stop() {this.stopping=true;this.admin.stop();this.web?.stop();this.api.stop();this.persist();}
}

function loadConfig() {
  const config=JSON.parse(fs.readFileSync(path.join(ROOT,'config.json'),'utf8'));
  if (!/^\d+:[\w-]+$/.test(config.token || '')) throw new Error('Укажите token в config.json.');
  if (!Number.isSafeInteger(config.adminId) || config.adminId<=0) throw new Error('Неверный adminId.');
  if (config.pm2Process!=='dvbot') throw new Error('pm2Process должен быть dvbot.');
  if (!Array.isArray(config.campuses) || !config.campuses.length || config.campuses.some(c=>!c.name || Buffer.byteLength(c.name)>50 || (c.coordinates!==null && (!Array.isArray(c.coordinates) || c.coordinates.length!==2 || !c.coordinates.every(Number.isFinite) || Math.abs(c.coordinates[0])>90 || Math.abs(c.coordinates[1])>180))) || new Set(config.campuses.map(c=>c.name)).size!==config.campuses.length) throw new Error('Проверьте campuses в config.json: уникальные названия до 50 байт и coordinates: null либо [широта, долгота].');
  if (!config.database || !config.photoDirectory || !(config.adEveryViews>0)) throw new Error('Неверные настройки базы, фото или рекламы.');
  return config;
}

if (require.main===module) {
  let bot;
  try {bot=new DatingBot(loadConfig());} catch(error) {console.error(error.message);process.exit(1);}
  for (const signal of ['SIGINT','SIGTERM']) process.once(signal,()=>bot.stop());
  bot.run().catch(error=>{console.error(error.message);process.exitCode=1;}).finally(async()=>{bot.admin.stop();await bot.web?.stop();bot.store.close();});
}

module.exports={DatingBot,Telegram,colleges,coordinates,button,inline,keyboard,menu,sleep,spam};




