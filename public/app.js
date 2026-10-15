'use strict';

const $=selector=>document.querySelector(selector);
const el=(tag,className,text)=>{const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node;};
const svg=name=>{const node=document.createElementNS('http://www.w3.org/2000/svg','svg'),use=document.createElementNS('http://www.w3.org/2000/svg','use');use.setAttribute('href','#i-'+name);node.append(use);return node;};
const icon=(name,label,handler,className='')=>{const b=el('button','icon-button '+className);b.type='button';b.setAttribute('aria-label',label);b.title=label;b.append(svg(name));b.onclick=handler;return b;};
const button=(text,handler,className='secondary')=>{const b=el('button',className,text);b.type='button';b.onclick=handler;return b;};
const state={session:null,sessionToken:sessionStorage.getItem('dv-session'),csrf:null,profile:null,colleges:[],route:'',chats:[],chatPage:0,chatId:null,messages:[],pending:null,reply:null,drafts:new Map(),chatBusy:false,requestId:0,discover:null};
const tg=window.Telegram?.WebApp;
let toastTimer;
function toast(text){$('#toast').textContent=text;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,4000);}
async function api(url,{method='GET',body,raw=false,headers={}}={}){
  const options={method,credentials:'same-origin',headers:{...headers}};
  if(state.sessionToken)options.headers.Authorization='Bearer '+state.sessionToken;
  if(method!=='GET')options.headers['X-CSRF-Token']=state.csrf || '';
  if(body!==undefined){options.body=raw?body:JSON.stringify(body);if(!raw)options.headers['Content-Type']='application/json';}
  const response=await fetch(url,options);let data;try{data=await response.json();}catch{throw new Error('Сервер временно недоступен.');}
  if(!response.ok){const error=new Error(data.error || 'Не удалось выполнить запрос.');error.status=response.status;if(response.status===401 && url!=='/api/auth')showLogin(data.error);throw error;}
  return data;
}
const busy=node=>{node.replaceChildren(el('div','busy'));node.firstChild.append(el('span','spinner'));};
function empty(node,title,text,action){const box=el('div','empty');box.append(svg('heart'),el('h2','',title),el('p','',text));if(action)box.append(action);node.replaceChildren(box);}
function image(src,alt,className=''){
  const img=el('img',className);img.alt=alt;img.loading='lazy';img.decoding='async';img.addEventListener('load',()=>{img.hidden=false;});img.addEventListener('error',()=>{img.hidden=true;});img.src=src;return img;
}
function avatar(src,name,className=''){
  const node=el('span','avatar'+(className?' '+className:''));
  node.append(el('span','avatar-fallback',(name || 'Пользователь').trim().slice(0,1).toUpperCase()));
  if(src){const photo=image(src,name || 'Фото профиля');photo.loading='eager';node.append(photo);}
  return node;
}
function profileCard(profile){
  const card=el('article','profile-card'),portrait=el('div','portrait');
  const fallback=el('div','fallback');fallback.append(svg('user'),el('span','','Фото недоступно'));portrait.append(fallback);
  const photos=profile.photos || [];let index=0;let photo;
  if(photos.length){photo=image(photos[0].url,'Фото '+profile.name);photo.loading='eager';portrait.append(photo);}
  portrait.append(el('div','portrait-gradient'));
  const info=el('div','portrait-info'),location=el('p');location.append(svg('pin'),document.createTextNode(profile.college));info.append(el('h2','',`${profile.name}, ${profile.age}`),location);portrait.append(info);
  if(photos.length>1){
    const counter=el('span','photo-counter',`1 / ${photos.length}`);portrait.append(counter);
    const change=offset=>{index=(index+offset+photos.length)%photos.length;photo.hidden=false;photo.src=photos[index].url;counter.textContent=`${index+1} / ${photos.length}`;};
    portrait.append(icon('back','Предыдущее фото',()=>change(-1),'photo-arrow prev'),icon('next','Следующее фото',()=>change(1),'photo-arrow next'));
    let start;portrait.addEventListener('touchstart',event=>{start=event.touches[0].clientX;},{passive:true});portrait.addEventListener('touchend',event=>{if(start!==undefined){const diff=event.changedTouches[0].clientX-start;if(Math.abs(diff)>50)change(diff<0?1:-1);start=undefined;}},{passive:true});
  }
  const body=el('div','profile-body');if(profile.bio)body.append(el('p','profile-bio',profile.bio));
  const meta=el('div','profile-meta');meta.append(el('span','',profile.distance!==undefined?`Примерно ${profile.distance} км от твоего корпуса`:'Из твоего корпуса'),button('Пожаловаться',()=>report(profile.id),'text-button compact'));if(state.session?.isBanned)for(const b of meta.querySelectorAll('button'))b.remove();body.append(meta);
  if(profile.video){const video=el('video','video-preview');video.src=profile.video;video.controls=true;video.preload='none';body.append(video);}
  card.append(portrait,body);return card;
}
function modal(content){$('#modal-content').replaceChildren(content);if(!$('#modal').open)$('#modal').showModal();}
function closeModal(){$('#modal').close();$('#modal-content').replaceChildren();}
async function report(id){
  const form=el('form','profile-form');form.append(el('h2','','Пожаловаться'));
  const label=el('label','','Что случилось?'),text=el('textarea');text.required=true;text.maxLength=2000;label.append(text);form.append(label);
  const submit=el('button','primary','Отправить жалобу');submit.type='submit';form.append(submit);form.onsubmit=async event=>{event.preventDefault();submit.disabled=true;try{await api(`/api/profiles/${id}/report`,{method:'POST',body:{reason:text.value}});closeModal();toast('Жалоба отправлена администратору.');}catch(e){toast(e.message);}finally{submit.disabled=false;}};modal(form);
}
async function discover(){
  const node=$('#discover-content');busy(node);const request=++state.requestId;
  try{
    const data=await api('/api/discover');if(request!==state.requestId)return;state.discover=data.profile;
    if(!data.profile)return empty(node,'Пока никого нет','Попробуй другой корпус или зайди чуть позже.',button('Искать снова',discover));
    const card=profileCard(data.profile),actions=el('div','profile-actions');
    const react=async action=>{for(const b of actions.querySelectorAll('button'))b.disabled=true;try{const result=await api(`/api/profiles/${data.profile.id}/${action}`,{method:'POST',body:{}});tg?.HapticFeedback?.notificationOccurred(result.matched?'success':'warning');if(result.matched)toast('Взаимная симпатия! Можно начать диалог.');await discover();}catch(e){toast(e.message);for(const b of actions.querySelectorAll('button'))b.disabled=false;}};
    actions.append(icon('close','Пропустить',()=>react('dislike')),icon('heart','Нравится',()=>react('like'),'like'),icon('chat','Написать',()=>openChat(data.profile.id)));
    const labels=el('div','action-labels');for(const text of ['Пропустить','Нравится','Написать'])labels.append(el('span','',text));
    if(state.session?.isBanned){actions.replaceChildren(icon('close','Пропустить',discover));labels.replaceChildren(el('span','','Пропустить'));}const controls=el('div','discover-controls');controls.append(actions,labels);node.replaceChildren(card,controls);
  }catch(e){empty(node,'Не удалось загрузить анкеты',e.message,button('Повторить',discover));}
}
function showMatches(){go('likes');}
async function loadLikes(page=0){
  const node=$('#likes-content');busy(node);
  try{
    const data=await api('/api/likes?page='+page);node.replaceChildren(el('p','',`💖 Взаимных симпатий: ${data.mutualCount}`));
    const grid=el('div','match-grid');node.append(grid);
    if(!data.profiles.length)empty(grid,'Пока нет лайков','Здесь появятся люди, которым понравилась твоя анкета.');
    for(const profile of data.profiles){const b=button('',()=>showPerson(profile.id));b.append(avatar(profile.avatar,profile.name),el('strong','',`${profile.name}, ${profile.age}`),el('span','muted',profile.mutual?'💖 Взаимная симпатия':profile.college));grid.append(b);}
    const pages=el('div','form-actions');if(page>0)pages.append(button('← Назад',()=>loadLikes(page-1)));if(data.hasMore)pages.append(button('Далее →',()=>loadLikes(page+1)));node.append(pages);
  }catch(e){empty(node,'Не удалось загрузить лайки',e.message,button('Повторить',()=>loadLikes(page)));}
}
async function showPerson(id){
  const container=el('div');modal(container);busy(container);
  try{const {profile}=await api('/api/profiles/'+id);const actions=el('div','person-actions');actions.append(button('❤️ Нравится',async()=>{try{const result=await api(`/api/profiles/${id}/like`,{method:'POST',body:{}});toast(result.matched?'Взаимная симпатия!':'Лайк отправлен.');if(state.route==='likes')await loadLikes();}catch(e){toast(e.message);}},'primary'),button('Написать',()=>{closeModal();openChat(id);},'secondary'));if(state.session?.isBanned)actions.replaceChildren();container.replaceChildren(profileCard(profile),actions);}catch(e){empty(container,'Анкета недоступна',e.message);}
}
function supportLinks(){const row=el('div','form-actions');for(const [text,url] of (window.publicConfig?.supportLinks || []).map(x=>[x.text,x.url])){const link=el('a','secondary',text);link.href=url;link.target='_blank';link.rel='noopener noreferrer';row.append(link);}return row;}
async function adminPage(page=0){
  const node=$('#admin-content');busy(node);
  try{
    const [overview,data]=await Promise.all([api('/api/admin/overview'),api('/api/admin/reports?page='+page)]);node.replaceChildren();
    const tabs=el('div','form-actions');tabs.append(button('Жалобы',()=>adminPage(0),'primary'),button('Статистика',()=>{const box=el('div','admin-stats');box.append(el('h2','','Статистика'),el('p','',overview.stats));modal(box);}));
    tabs.append(button('Баны',async()=>{try{const {bans}=await api('/api/admin/bans');const box=el('div');box.append(el('h2','','Активные баны'));if(!bans.length)box.append(el('p','','Активных банов нет.'));for(const ban of bans){const row=el('article','report-card');row.append(el('strong','',String(ban.user_id)),el('p','',ban.reason),button('Снять бан',async()=>{try{await api(`/api/admin/users/${ban.user_id}/unban`,{method:'POST',body:{}});row.remove();toast('Бан снят.');}catch(e){toast(e.message);}}));box.append(row);}modal(box);}catch(e){toast(e.message);}}));
    if(overview.isAdmin)tabs.append(button('Автосообщение',async()=>{let current;try{current=await api('/api/admin/overview');}catch(e){toast(e.message);return;}const box=el('div','admin-stats');box.append(el('h2','','Текущее автосообщение'),el('p','report-text',current.autoMessage),supportLinks(),button('Установить шаблон',async()=>{try{await api('/api/admin/support-template',{method:'POST',body:{}});closeModal();toast('Шаблон установлен.');}catch(e){toast(e.message);}},'primary'));modal(box);}));
    if(overview.isAdmin)tabs.append(button('Удалить анкету',()=>{const form=el('form','profile-form');form.append(el('h2','','Удалить анкету по ID'));const input=el('input');input.type='text';input.inputMode='numeric';input.pattern='[0-9]+';input.required=true;input.placeholder='ID пользователя';input.setAttribute('aria-label','ID пользователя');const submit=el('button','primary','Найти анкету');submit.type='submit';form.append(input,submit);form.onsubmit=event=>{event.preventDefault();const id=Number(input.value);if(!Number.isSafeInteger(id) || id<=0)return toast('Введите числовой ID пользователя.');confirmDeleteProfile(id);};modal(form);input.focus();}));
    node.append(tabs,el('h2','admin-subtitle','Жалобы'));
    if(!data.reports.length){const blank=el('div');empty(blank,'Жалоб нет','Новые обращения появятся здесь.');node.append(blank);}
    for(const report of data.reports){const card=el('article','report-card');card.append(el('h3','',`Жалоба #${report.id}`),el('p','muted',`От: ${report.reporter_name || 'Пользователь'} (ID: ${report.reporter_id}) · На: ${report.target_name || 'Пользователь'} (ID: ${report.target_user_id})`),el('p','report-text',report.reason));
      if(report.answer){const answer=el('div','report-answer');answer.append(el('strong','','Ответ администрации'),el('p','',report.answer.text));card.append(answer);}
      const actions=el('div','form-actions');actions.append(button('Анкета',()=>showPerson(report.target_user_id)),button('Заблокировать',()=>banForm(report.target_user_id)),button(report.answer?'Дополнить ответ':'Ответить',()=>{const form=el('form','profile-form');form.append(el('h2','',`Ответ по жалобе #${report.id}`));const field=el('textarea');field.required=true;field.maxLength=3500;field.placeholder='Ответ пользователю';form.append(field);const submit=el('button','primary','Отправить ответ');submit.type='submit';form.append(submit);form.onsubmit=async event=>{event.preventDefault();submit.disabled=true;try{const result=await api(`/api/admin/reports/${report.id}/reply`,{method:'POST',body:{text:field.value}});closeModal();toast(result.delivered?'Ответ отправлен.':'Ответ сохранён, уведомление не доставлено.');await adminPage(page);}catch(e){toast(e.message);}finally{submit.disabled=false;}};modal(form);},'primary'));actions.append(button('Удалить жалобу',async()=>{if(!confirm(`Удалить жалобу #${report.id} вместе с ответом администрации?`))return;try{await api(`/api/admin/reports/${report.id}`,{method:'DELETE'});toast('Жалоба удалена.');await adminPage(page);}catch(e){toast(e.message);}},'text-button'));if(overview.isAdmin)actions.append(button('Удалить анкету',()=>confirmDeleteProfile(report.target_user_id),'text-button danger-text'));card.append(actions);node.append(card);}
    const pages=el('div','form-actions');if(page>0)pages.append(button('← Назад',()=>adminPage(page-1)));if(data.hasMore)pages.append(button('Далее →',()=>adminPage(page+1)));node.append(pages);
  }catch(e){empty(node,'Админ-раздел недоступен',e.message);}
}
function banForm(id){
  const form=el('form','profile-form');form.append(el('h2','',`Блокировка пользователя ${id}`),el('p','muted','Анкета и переписка сохранятся.'));
  const reason=el('textarea');reason.required=true;reason.maxLength=500;reason.placeholder='Причина блокировки';const duration=el('select');for(const [value,label]of [[86400,'1 день'],[604800,'7 дней'],[2592000,'30 дней'],[0,'Навсегда']]){const option=el('option','',label);option.value=value;duration.append(option);}const comment=el('textarea');comment.required=true;comment.maxLength=1000;comment.placeholder='Комментарий пользователю (придёт отдельным уведомлением)';form.append(reason,duration,comment);
  const submit=el('button','primary','Подтвердить блокировку');submit.type='submit';form.append(submit);form.onsubmit=async event=>{event.preventDefault();submit.disabled=true;try{const result=await api(`/api/admin/users/${id}/ban`,{method:'POST',body:{reason:reason.value,seconds:Number(duration.value),comment:comment.value}});closeModal();toast(result.delivered?'Бан выдан, уведомление отправлено.':'Бан выдан, уведомление не доставлено.');}catch(e){toast(e.message);}finally{submit.disabled=false;}};modal(form);
}
async function reportPage(id){
  const node=$('#reports-content');busy(node);
  if(!id)return empty(node,'Выберите жалобу','Откройте ответ через уведомление бота.');
  try{const {report}=await api('/api/reports/'+id);const card=el('article','report-card');card.append(el('h2','',`Жалоба #${report.id}`),el('p','report-text',report.reason),el('h3','','Ответ администрации'),el('p','report-text',report.answer?.text || 'Ответ пока не поступил.'));node.replaceChildren(card);}catch(e){empty(node,'Ответ недоступен',e.message);}
}
function route(){
  if(location.pathname.replace(/\/+$/,'')==='/koiutyrtkljkhjghf')return 'admin';
  const hash=location.hash.replace(/^#/,'');if(/^(discover|likes|me|reports(?:\/\d+)?|chats(?:\/\d+)?)$/.test(hash))return hash;
  const pathname=location.pathname.replace(/^\/+|\/+$/g,'');if(/^(discover|likes|me|reports(?:\/\d+)?|chats(?:\/\d+)?)$/.test(pathname))return pathname;
  const chat=new URLSearchParams(location.search).get('chat');if(/^[1-9]\d{0,15}$/.test(chat || '') && Number.isSafeInteger(Number(chat)))return 'chats/'+chat;
  return sessionStorage.getItem('dv-route') || 'discover';
}
function go(value){history.pushState(null,'','/'+(value==='admin'?'koiutyrtkljkhjghf':value));renderRoute();}
function openChat(id){go('chats/'+id);}
function saveRoute(value){state.route=value;sessionStorage.setItem('dv-route',value);for(const nav of document.querySelectorAll('[data-nav]'))nav.classList.toggle('active',nav.dataset.nav===value.split('/')[0]);}
async function renderRoute(){
  if(!state.session)return;
  if(state.chatId){const input=$('#message-input');if(input)state.drafts.set(state.chatId,{text:input.value,reply:state.reply});}
  let value=route();if(!/^(discover|likes|me|admin|reports(?:\/\d+)?|chats(?:\/\d+)?)$/.test(value))value='discover';
  if(!state.profile && !value.startsWith('reports') && value!=='admin')value='me';
  if(value==='admin' && !state.session.isStaff){toast('Доступ только для администрации.');value='discover';}
  saveRoute(value);for(const name of ['discover','likes','chats','me','admin','reports'])$('#'+name+'-view').hidden=name!==value.split('/')[0];
  document.body.classList.toggle('chat-active',value.startsWith('chats/'));
  tg?.BackButton?.hide();state.chatId=null;state.messages=[];state.pending=null;state.reply=null;
  if(value==='discover'){
    $('#scope').value=state.profile.viewScope;await discover();
  }else if(value==='admin')await adminPage();
  else if(value.startsWith('reports'))await reportPage(value.split('/')[1]);
  else if(value==='likes')await loadLikes();
  else if(value==='me')await myProfile();
  else{
    const id=value.split('/')[1];$('#chats-view').classList.toggle('chat-open',!!id);state.chatPage=0;await loadChats();
    if(id){state.chatId=Number(id);tg?.BackButton?.show();await loadConversation(state.chatId);}else $('#conversation').replaceChildren(makeEmptyChat());
  }
}
function makeEmptyChat(){const node=el('div','empty');node.append(svg('chat'),el('h2','','Начните разговор'),el('p','','Выберите диалог или напишите человеку из анкеты.'));return node;}
function dateLabel(value){const date=new Date(value.replace(' ','T')+'+03:00');return Number.isNaN(date.getTime())?value:new Intl.DateTimeFormat('ru-RU',{day:'numeric',month:'long',timeZone:'Europe/Moscow'}).format(date);}
function time(value){const date=new Date(value.replace(' ','T')+'+03:00');return Number.isNaN(date.getTime())?'':new Intl.DateTimeFormat('ru-RU',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Moscow'}).format(date);}
function renderChats(){
  const node=$('#chat-list'),search=$('#chat-search').value.toLowerCase();node.replaceChildren();
  const chats=state.chats.filter(c=>c.name.toLowerCase().includes(search));
  if(!chats.length){empty(node,'Пока нет диалогов',search?'Попробуй другое имя.':'Напиши человеку, который тебе понравился.');return;}
  let unread=0;
  for(const chat of chats){const row=button('',()=>openChat(chat.id),'chat-row'+(state.chatId===chat.id?' active':''));
    const photo=avatar(chat.avatar,chat.name);
    const summary=el('span','chat-summary');summary.append(el('strong','',chat.name),el('p','',chat.preview));const side=el('span','chat-time',time(chat.at));if(chat.unread){side.append(el('b','unread',chat.unread));unread+=chat.unread;}row.append(photo,summary,side);node.append(row);
  }
  $('#unread-badge').hidden=!unread;$('#unread-badge').textContent=unread;
}
async function loadChats(append=false){
  if(append)state.chatPage++;
  try{const data=await api('/api/chats?page='+state.chatPage);state.chats=append?[...state.chats,...data.chats]:data.chats;$('#more-chats').hidden=!data.hasMore;renderChats();}catch(e){toast(e.message);}
}
function messageNode(message){
  const node=el('article','message'+(message.mine?' mine':''));node.dataset.id=message.id;
  if(message.reply){const quote=button('',()=>{const target=$(`[data-id="${message.reply.id}"]`);if(target){target.scrollIntoView({block:'center',behavior:'smooth'});target.classList.add('message-highlight');setTimeout(()=>target.classList.remove('message-highlight'),1200);}else toast('Исходное сообщение находится выше в переписке.');},'message-quote');quote.append(el('strong','',message.reply.name),el('span','',message.reply.text));node.append(quote);}
  for(const media of message.media){let item;
    if(media.type==='photo' || media.type==='sticker'){item=image(media.url,media.type==='photo'?'Фото в сообщении':'Стикер',media.type==='sticker'?'sticker':'');}
    else if(media.type==='voice'){item=el('audio');item.controls=true;item.src=media.url;item.preload='none';}
    else{item=el('video');item.controls=true;item.src=media.url;item.preload='none';item.playsInline=true;if(media.type==='animation'){item.loop=true;item.muted=true;}}
    item.addEventListener('error',()=>{if(media.type==='sticker'){item.hidden=true;const note=el('small','','Анимированный стикер — в Telegram');node.append(note);}});node.append(item);
  }
  if(message.text)node.append(el('p','',message.text));const t=el('time','',time(message.at));t.dateTime=message.at;
  const footer=el('div','message-footer');footer.append(button('Ответить',()=>chooseReply(message),'text-button reply-button'),t);node.append(footer);return node;
}
function chooseReply(message){
  if(state.sending)return;
  state.reply={id:message.id,name:message.mine?'Вы':$('#conversation-name')?.textContent || 'Собеседник',text:message.text || 'Медиа'};
  const input=$('#message-input');if(input){delete input.dataset.clientId;if(state.pending?.media)state.pending.clientId=crypto.randomUUID();renderReply();input.focus({preventScroll:true});}
}
function renderReply(){
  const node=$('#reply-strip');if(!node)return;node.hidden=!state.reply;node.replaceChildren();
  if(state.reply){const text=el('div');text.append(el('strong','',`Ответ: ${state.reply.name}`),el('span','',state.reply.text));node.append(text,icon('close','Отменить ответ',()=>{state.reply=null;const input=$('#message-input');if(input)delete input.dataset.clientId;if(state.pending?.media)state.pending.clientId=crypto.randomUUID();renderReply();}));}
}
function renderMessages({scroll=false,preserve=false}={}){
  const node=$('#message-list');if(!node)return;const oldHeight=node.scrollHeight,oldTop=node.scrollTop;
  const children=[];let day='';
  if(state.messages.length>=30)children.push(button('Более ранние сообщения',loadEarlier,'text-button compact'));
  for(const message of state.messages){const next=message.at.slice(0,10);if(next!==day){children.push(el('div','day-label',dateLabel(message.at)));day=next;}children.push(messageNode(message));}
  node.replaceChildren(...children);if(!state.messages.length)node.append(el('div','empty','Сообщений пока нет. Напиши первым!'));
  if(scroll)node.scrollTop=node.scrollHeight;else if(preserve)node.scrollTop=oldTop+node.scrollHeight-oldHeight;
}
async function markRead(){
  if(!state.messages.length || !state.chatId)return;const through=state.messages.at(-1).id;
  try{await api(`/api/chats/${state.chatId}/read`,{method:'POST',body:{through}});const c=state.chats.find(c=>c.id===state.chatId);if(c)c.unread=0;renderChats();}catch(e){if(e.status!==401)console.debug('Read status unavailable');}
}
async function loadConversation(id){
  const container=$('#conversation');busy(container);state.chatBusy=true;
  try{
    const [person,data]=await Promise.all([api('/api/profiles/'+id).catch(()=>({profile:{id,name:'Пользователь',college:'Анкета недоступна',photos:[]}})),api(`/api/chats/${id}/messages`)]);
    if(state.chatId!==id)return;const profile=person.profile;
    const header=el('header','conversation-header'),photo=avatar(profile.avatar || profile.photos[0]?.url,profile.name);
    const name=el('div','conversation-person'),title=el('h2','',profile.name);title.id='conversation-name';name.append(title,el('p','',profile.college));header.append(icon('back','К диалогам',()=>go('chats'),'mobile-back'),photo,name,button('Анкета',()=>showPerson(id),'secondary view-person'));
    const messages=el('div','messages');messages.id='message-list';const attachment=el('div','attachment-strip');attachment.id='attachment-strip';attachment.hidden=true;
    const replyStrip=el('div','reply-strip');replyStrip.id='reply-strip';replyStrip.hidden=true;
    const composer=el('form','composer'),input=el('textarea');input.id='message-input';input.rows=1;input.maxLength=3500;input.placeholder='Написать сообщение…';input.setAttribute('aria-label','Сообщение');input.value=state.drafts.get(id)?.text || '';state.reply=state.drafts.get(id)?.reply || null;
    const file=el('input');file.type='file';file.accept='image/jpeg,image/png,image/webp,video/mp4,video/webm,video/quicktime,audio/*';file.hidden=true;
    file.onchange=()=>attach(file.files[0]);
    const send=icon('send','Отправить сообщение',()=>{} ,'send');send.type='submit';send.id='send-message';
    composer.append(icon('clip','Прикрепить медиа',()=>file.click()),input,send,file);composer.onsubmit=sendMessage;
    input.onkeydown=event=>{if(event.key==='Enter' && !event.shiftKey && !event.isComposing && matchMedia('(hover:hover) and (pointer:fine)').matches){event.preventDefault();composer.requestSubmit();}};
    input.oninput=()=>{delete input.dataset.clientId;if(state.pending?.media)state.pending.clientId=crypto.randomUUID();input.style.height='auto';input.style.height=Math.min(input.scrollHeight,130)+'px';};
    container.replaceChildren(header,messages,replyStrip,attachment,composer);renderReply();state.messages=data.messages;renderMessages({scroll:true});await markRead();
  }catch(e){empty(container,'Не удалось открыть диалог',e.message,button('Повторить',()=>loadConversation(id)));}finally{state.chatBusy=false;}
}
async function loadEarlier(){
  if(state.chatBusy || !state.messages.length)return;state.chatBusy=true;
  try{const data=await api(`/api/chats/${state.chatId}/messages?before=${state.messages[0].id}`);if(!data.messages.length)return toast('Это начало диалога.');state.messages=[...data.messages,...state.messages];renderMessages({preserve:true});}catch(e){toast(e.message);}finally{state.chatBusy=false;}
}
async function pollMessages(){
  const id=state.chatId;if(!id || state.chatBusy || document.hidden || !state.route.startsWith('chats/'))return;state.chatBusy=true;
  try{const latest=state.messages.at(-1)?.id;const data=await api(`/api/chats/${id}/messages${latest?'?after='+latest:''}`);if(state.chatId!==id)return;
    if(data.messages.length){const node=$('#message-list'),nearBottom=node && node.scrollHeight-node.scrollTop-node.clientHeight<100;const known=new Set(state.messages.map(m=>m.id));const fresh=data.messages.filter(m=>!known.has(m.id));for(const message of fresh)state.messages.push(message);
      // Добавляем новые узлы: воспроизведение старых медиа и позиция чтения сохраняются.
      if(!known.size)renderMessages({scroll:true});else for(const message of fresh)node?.append(messageNode(message));
      if(nearBottom && node)node.scrollTop=node.scrollHeight;await markRead();
    }
  }catch(e){if(e.status===401)return;}finally{state.chatBusy=false;}
}
async function attach(file){
  if(!file)return;if(state.pending?.loading || state.sending)return;const id=state.chatId;
  const type=file.type.startsWith('image/')?'photo':file.type.startsWith('video/')?'video':file.type.startsWith('audio/')?'voice':null;
  if(!type)return toast('Выбери фото, видео или аудио.');
  state.pending={loading:true};renderAttachment('Загружаем '+file.name);
  try{const media=await upload(file,type);if(state.chatId!==id)return;state.pending={media,name:file.name,clientId:crypto.randomUUID()};renderAttachment(file.name);}catch(e){state.pending=null;renderAttachment();toast(e.message);}
}
function renderAttachment(name){const node=$('#attachment-strip');if(!node)return;node.hidden=!name;node.replaceChildren();if(name)node.append(el('span','',name),button('Убрать',()=>{state.pending=null;renderAttachment();},'text-button compact'));}
async function sendMessage(event){
  event.preventDefault();const input=$('#message-input'),send=$('#send-message'),text=input.value.trim(),id=state.chatId;
  if(state.pending?.loading)return toast('Дождись загрузки медиа.');if(!text && !state.pending?.media)return;
  if(state.sending)return;state.sending=true;send.disabled=true;const payload={text,clientId:state.pending?.clientId || input.dataset.clientId || crypto.randomUUID(),...(state.pending?.media?{media:state.pending.media}:{}),...(state.reply?{replyTo:state.reply.id}:{})};input.dataset.clientId=payload.clientId;
  try{const data=await api(`/api/chats/${id}/messages`,{method:'POST',body:payload});if(state.chatId!==id){if(state.drafts.get(id)?.text.trim()===text)state.drafts.delete(id);return;}
    if(!state.messages.some(m=>m.id===data.message.id))state.messages.push(data.message);if(input.value.trim()===text){input.value='';input.style.height='auto';}delete input.dataset.clientId;state.pending=null;state.reply=null;state.drafts.delete(id);renderReply();renderAttachment();renderMessages({scroll:true});await markRead();await loadChats();tg?.HapticFeedback?.impactOccurred('light');
  }catch(e){toast(e.message);}finally{state.sending=false;if(send.isConnected)send.disabled=false;}
}
async function upload(file,type){
  const limit=type==='photo'?10:20;if(file.size>limit*1024*1024)throw new Error(`Максимальный размер ${limit} МБ.`);
  return api('/api/upload?type='+type,{method:'POST',body:file,raw:true,headers:{'Content-Type':file.type,'X-File-Name':encodeURIComponent(file.name)}});
}
async function saveSettings(patch){
  const result=await api('/api/me',{method:'PATCH',body:patch});state.profile=result.profile;return result.profile;
}
function setting(title,description,checked,onchange){const row=el('label','setting'),text=el('span','',title),input=el('input');input.type='checkbox';input.checked=checked;if(description)text.append(el('small','',description));row.append(text,input);input.onchange=async()=>{input.disabled=true;try{await onchange(input.checked);toast('Настройки сохранены.');}catch(e){input.checked=!input.checked;toast(e.message);}finally{input.disabled=false;}};return row;}
async function myProfile(){
  const node=$('#me-content');busy(node);
  try{
    const data=await api('/api/me');state.profile=data.profile;
    if(!state.profile)return node.replaceChildren(profileForm(null));
    const profile=state.profile,content=el('div','own-profile'),summary=el('div','own-summary');
    summary.append(avatar(profile.avatar || profile.photos[0]?.url,profile.name,'own-avatar'));
    const intro=el('div');intro.append(el('h2','',`${profile.name}, ${profile.age}`),el('p','',profile.college),button('Редактировать анкету',()=>node.replaceChildren(profileForm(profile)),'secondary'));summary.append(intro);content.append(summary);
    if(profile.bio)content.append(el('p','profile-bio',profile.bio));
    const stats=el('div','stats');for(const line of (data.stats||'').split('\n')){const parts=line.split(':');const item=el('div','stat',parts[0]);item.prepend(el('strong','',parts[1]?.trim() || '0'));stats.append(item);}content.append(stats);
    const settings=el('div','settings');settings.append(
      setting('Анкета видна','Можно отключить, сохранив все данные.',!profile.hidden,value=>saveSettings({hidden:!value})),
      setting('Показывать в топе','Управляет видимостью в рейтинге.',!profile.hideFromTop,value=>saveSettings({hideFromTop:!value}))
    );settings.append(themeSetting());content.append(settings,button('Посмотреть мою анкету',()=>{modal(profileCard(profile));},'text-button'));node.replaceChildren(content);
  }catch(e){empty(node,'Не удалось открыть профиль',e.message,button('Повторить',myProfile));}
}
async function confirmDeleteProfile(id){
  try{
    const {confirmation,user}=await api(`/api/admin/users/${id}/delete-request`,{method:'POST',body:{}}),content=el('div');
    content.append(el('h2','',`Удалить анкету ${user.name} (ID: ${user.id})?`),el('p','','Фото, видео, лайки и симпатии будут удалены. Переписка сохранится. Восстановить анкету нельзя, но можно создать новую.'));
    const actions=el('div','form-actions'),cancel=button('Нет, оставить',closeModal,'secondary'),confirm=button('Да, удалить анкету',async()=>{
      confirm.disabled=true;cancel.disabled=true;
      try{await api(`/api/admin/users/${id}/profile`,{method:'DELETE',body:{confirmation}});closeModal();await adminPage();toast(`Анкета пользователя ${id} удалена.`);}
      catch(e){toast(e.message);confirm.disabled=false;cancel.disabled=false;}
    },'primary danger-button');actions.append(cancel,confirm);content.append(actions);modal(content);cancel.focus();
  }catch(e){toast(e.message);}
}
function profileForm(existing){
  const form=el('form','profile-form');form.append(el('h2','',existing?'Редактировать анкету':'Создай свою анкету'),el('p','muted',existing?'Изменения появятся и в боте.':'Познакомься с людьми из своего корпуса.'));
  const field=(title,type,value,attributes={})=>{const label=el('label','',title),input=el(type==='textarea'?'textarea':'input');if(type!=='textarea')input.type=type;input.value=value??'';Object.assign(input,attributes);label.append(input);return {label,input};};
  const name=field('Имя','text',existing?.name || '',{required:true,minLength:2,maxLength:60}),age=field('Возраст','number',existing?.age || '',{required:true,min:14,max:30});
  const row=el('div','form-row');row.append(name.label,age.label);form.append(row);
  const collegeLabel=el('label','','Корпус'),college=el('select');for(const c of state.colleges){const option=el('option','',c);option.value=c;college.append(option);}college.value=existing?.college || state.colleges[0];collegeLabel.append(college);form.append(collegeLabel);
  const bio=field('О себе','textarea',existing?.bio || '',{maxLength:500});bio.input.placeholder='Что любишь и кого хочешь встретить';form.append(bio.label);
  let photos=(existing?.photos || []).map(p=>({...p})),video=existing?.videoRef || null,uploading=false;
  const label=el('label','','Фотографии · от 1 до 3'),editor=el('div','photo-editor'),file=el('input');file.type='file';file.accept='image/jpeg,image/png,image/webp';file.hidden=true;label.append(editor,file);form.append(label);
  const render=()=>{editor.replaceChildren();for(let i=0;i<photos.length;i++){const slot=el('div','photo-slot');slot.append(image(photos[i].url,'Моё фото '+(i+1)),button('×',()=>{photos.splice(i,1);render();},''));editor.append(slot);}if(photos.length<3)editor.append(button(uploading?'…':'+',()=>file.click(),'photo-add'));};render();
  file.onchange=async()=>{if(uploading || !file.files[0])return;uploading=true;render();const selected=file.files[0];try{const result=await upload(selected,'photo');photos.push({ref:result.ref,url:URL.createObjectURL(selected)});toast('Фото загружено.');}catch(e){toast(e.message);}finally{uploading=false;render();file.value='';}};
  const videoLabel=el('label','','Видео · необязательно'),videoInput=el('input');videoInput.type='file';videoInput.accept='video/mp4,video/webm,video/quicktime';videoLabel.append(videoInput);form.append(videoLabel);
  const videoStatus=el('small','',video?'Видео уже добавлено':'');form.append(videoStatus,button('Убрать видео',()=>{video=null;videoInput.value='';videoStatus.textContent='Видео будет убрано после сохранения.';},'text-button compact'));
  videoInput.onchange=async()=>{if(!videoInput.files[0])return;uploading=true;videoStatus.textContent='Загружаем видео…';try{const result=await upload(videoInput.files[0],'video');video=result.ref;videoStatus.textContent='Видео загружено.';}catch(e){videoStatus.textContent=e.message;}finally{uploading=false;}};
  let student;
  if(!existing){const check=el('label','check-label');student=el('input');student.type='checkbox';student.required=true;check.append(student,document.createTextNode('Я участник сообщества.'));form.append(check);}
  const error=el('p','error-note'),actions=el('div','form-actions'),submit=el('button','primary',existing?'Сохранить изменения':'Создать анкету');submit.type='submit';actions.append(submit);if(existing)actions.append(button('Отмена',myProfile,'secondary'));form.append(error,actions);
  form.onsubmit=async event=>{event.preventDefault();if(uploading)return toast('Дождись завершения загрузки.');if(!photos.length){error.textContent='Добавь хотя бы одну фотографию.';return;}submit.disabled=true;error.textContent='';
    try{const data=await api('/api/me',{method:'PATCH',body:{name:name.input.value,age:Number(age.input.value),college:college.value,bio:bio.input.value,photos:photos.map(p=>p.ref),video,student:student?.checked}});state.profile=data.profile;toast('Анкета сохранена.');if(existing)await myProfile();else go('discover');for(const p of photos)if(p.url.startsWith('blob:'))URL.revokeObjectURL(p.url);}catch(e){error.textContent=e.message;}finally{submit.disabled=false;}
  };return form;
}
function showLogin(message){state.session=null;state.sessionToken=null;sessionStorage.removeItem('dv-session');$('#app').hidden=true;$('#loading').hidden=true;$('#login').hidden=false;$('#login-status').hidden=!message;if(message)$('#login-message').textContent=message;}
async function bootstrap(){
  const telegramLogin=!!tg?.initData;$('#loading').hidden=!telegramLogin;$('#login').hidden=telegramLogin;
  try{
    let data;
    if(tg?.initData)data=await api('/api/auth',{method:'POST',body:{initData:tg.initData}});else{try{data=await api('/api/session');}catch(e){if(e.status===401){showLogin();return;}throw e;}}
    state.session=data.user;$('#admin-nav').hidden=!data.user.isStaff;state.sessionToken=data.sessionToken;sessionStorage.setItem('dv-session',data.sessionToken);state.csrf=data.csrf;state.profile=data.profile;state.colleges=data.colleges;$('#bot-link').href='https://t.me/'+data.botUsername;
    $('#loading').hidden=true;$('#login').hidden=true;$('#app').hidden=false;await renderRoute();
  }catch(e){showLogin(e.message);}
}
$('#retry-login').onclick=bootstrap;$('#modal-close').onclick=closeModal;$('#modal').addEventListener('click',event=>{if(event.target===$('#modal'))closeModal();});
$('#matches-button').onclick=showMatches;$('#chat-search').oninput=renderChats;$('#more-chats').onclick=()=>loadChats(true);
$('#scope').onchange=async event=>{event.target.disabled=true;try{await saveSettings({viewScope:event.target.value});await discover();}catch(e){toast(e.message);event.target.value=state.profile.viewScope;}finally{event.target.disabled=false;}};
window.addEventListener('hashchange',renderRoute);
window.addEventListener('popstate',renderRoute);
for(const link of document.querySelectorAll('.navigation a'))link.addEventListener('click',event=>{if(event.button!==0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)return;event.preventDefault();go(link.getAttribute('href').slice(1));});
tg?.ready();tg?.expand();tg?.BackButton?.onClick(()=>go('chats'));
let themeChoice='light';try{const saved=localStorage.getItem('dv-theme');if(['light','dark'].includes(saved))themeChoice=saved;}catch{}
function themeSetting(){const row=el('label','setting'),text=el('span','','Тема'),select=el('select');select.setAttribute('aria-label','Тема приложения');for(const [value,label]of [['light','Бело-розовая'],['dark','Чёрная']]){const option=el('option','',label);option.value=value;select.append(option);}select.value=themeChoice;select.onchange=()=>{themeChoice=select.value;try{localStorage.setItem('dv-theme',themeChoice);}catch{}theme();};row.append(text,select);return row;}
function theme(){
 const dark=themeChoice==='dark';
 const palette=dark?{'--bg':'#111014','--surface':'#201c22','--ink':'#fff3fa','--muted':'#b8a5b1','--line':'#40303c','--green':'#ef85b5','--green-soft':'#3b2030','--on-accent':'#250c19'}:{'--bg':'#fff7fb','--surface':'#ffffff','--ink':'#35212d','--muted':'#806675','--line':'#efd9e5','--green':'#c52b73','--green-soft':'#fde7f1','--on-accent':'#ffffff'};
 const toggle=$('#public-theme-toggle');toggle.textContent=dark?'Светлая тема':'Чёрная тема';toggle.setAttribute('aria-label',dark?'Включить светлую тему':'Включить чёрную тему');
 document.documentElement.style.colorScheme=dark?'dark':'light';
 for(const [key,value]of Object.entries(palette))document.documentElement.style.setProperty(key,value);
 document.querySelector('meta[name="theme-color"]')?.setAttribute('content',palette['--bg']);
 try{tg?.setHeaderColor(palette['--bg']);tg?.setBackgroundColor(palette['--bg']);tg?.setBottomBarColor?.(palette['--bg']);}catch{}
}
theme();tg?.onEvent('themeChanged',theme);
$('#public-theme-toggle').onclick=()=>{themeChoice=themeChoice==='dark'?'light':'dark';try{localStorage.setItem('dv-theme',themeChoice);}catch{}theme();};
function viewport(){
  const visual=window.visualViewport,height=Math.min(tg?.viewportHeight || window.innerHeight,visual?.height || window.innerHeight);
  document.documentElement.style.setProperty('--app-height',Math.round(height)+'px');document.documentElement.style.setProperty('--viewport-top',(visual?.offsetTop || 0)+'px');
  const node=$('#message-list');if(node && document.activeElement===$('#message-input'))node.scrollTop=node.scrollHeight;
}
viewport();tg?.onEvent('viewportChanged',viewport);window.addEventListener('resize',viewport);window.visualViewport?.addEventListener('resize',viewport);window.visualViewport?.addEventListener('scroll',viewport);
setInterval(()=>pollMessages(),2500);setInterval(()=>{if(state.session && state.profile && !document.hidden && state.route.startsWith('chats') && state.chatPage===0)loadChats();},8000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)pollMessages();});
bootstrap();





fetch('/api/public-config').then(r=>r.json()).then(c=>{window.publicConfig=c;document.title=c.branding?.title || 'Знакомства';}).catch(()=>{});
