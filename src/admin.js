'use strict';

const fs=require('node:fs');
const path=require('node:path');
const ROOT=path.resolve(__dirname,'..');
const {execFile,spawn}=require('node:child_process');
const {promisify}=require('node:util');
const {moscow,now}=require('./db');
const {mailingContent}=require('./emojis');
const exec=promisify(execFile);
const button=(text,data)=>({text,callback_data:data});
const inline=rows=>({inline_keyboard:rows});
const keyboard=rows=>({keyboard:rows.map(row=>row.map(text=>({text}))),resize_keyboard:true});
const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const integer=text=>/^\d+$/.test(text||'') && Number.isSafeInteger(Number(text)) && Number(text)>0?Number(text):null;
const newer=(a,b)=>{
  if (!/^\d+\.\d+\.\d+(?:-[\w.-]+)?$/.test(a || '') || !/^\d+\.\d+\.\d+(?:-[\w.-]+)?$/.test(b || '')) return false;
  const x=a.split('-')[0].split('.').map(Number),y=b.split('-')[0].split('.').map(Number);
  for(let i=0;i<3;i++) if(x[i]!==y[i]) return x[i]>y[i];
  return a!==b && b.includes('-') && !a.includes('-');
};

function parseMoscowTime(text){
 const m=/^(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})$/.exec(text.trim());
 if(!m)return null;
 const [,day,month,year,hour,minute]=m;
 const value=Date.parse(`${year}-${month}-${day}T${hour}:${minute}:00+03:00`);
 if(!Number.isFinite(value))return null;
 const local=new Date(value+3*3600000).toISOString().slice(0,16);
 return local===`${year}-${month}-${day}T${hour}:${minute}`?value:null;
}
const scheduleLabel=time=>new Date(time).toLocaleString('ru-RU',{timeZone:'Europe/Moscow',dateStyle:'short',timeStyle:'short'})+' МСК';
class Admin {
  constructor(bot) {this.bot=bot;this.store=bot.store;this.config=bot.config;this.checking=false;this.restarting=false;this.broadcasting=false;}
  isAdmin(id) {return id===this.config.adminId;}
  isStaff(id) {return this.isAdmin(id) || this.store.moderator(id);}
  keyboard(id) {
    const rows=[[button('🚫 Банлист','admin_action_bans'),button('🔎 Найти бан','ban_search')],[button('👤 Посмотреть анкету','admin_action_view'),button('🚫 Заблокировать','admin_action_ban')]];
    if(this.isAdmin(id))rows.unshift(
      [button('📊 Статистика','admin_action_stats'),button('🗑 Удалить анкету','admin_action_delete_profile')],
      [button('❤️ Шаблон поддержки','admin_support_template')],
      [button(this.config.miniApp?.enabled?'🌐 Выключить Mini App':'🌐 Включить Mini App',this.config.miniApp?.enabled?'admin_miniapp_off':'admin_miniapp_on')],
      [button('📢 Рассылка','admin_action_broadcast'),button('🔄 Автосообщение','admin_action_auto')],
      [button('🕒 Запланированные рассылки','admin_schedule_list')],
      [button('👥 Модераторы','admin_action_staff'),button('➕ Добавить','admin_action_add_staff'),button('➖ Удалить','admin_action_remove_staff')],
      [button('🆕 Обновления','admin_check_version'),button('♻️ Рестарт dvbot','admin_restart')]
    );
    if(this.config.miniApp?.enabled)rows.unshift([{text:'🛡 Админ-приложение',web_app:{url:new URL('/koiutyrtkljkhjghf',this.config.miniApp.url).href}}]);
    return inline(rows);
  }
  requestProfileDeletion(id,target){
    if(!this.isAdmin(id) || this.isAdmin(target) || !this.store.user(target))return null;
    const token=this.bot.requestProfileDeletion(target);this.bot.setState(id,'admin_confirm_delete_profile',{target,token});return token;
  }
  confirmProfileDeletion(id,target,token){
    const state=this.bot.state(id);
    if(!this.isAdmin(id) || this.isAdmin(target) || state.step!=='admin_confirm_delete_profile' || state.data.target!==target || state.data.token!==token)return false;
    const deleted=this.bot.confirmProfileDeletion(target,token);if(deleted)this.bot.reset(id);return deleted;
  }
  supportTemplate() {return 'Бот абсолютно бесплатный ❤️\n\nЧтобы поддержать разработчика, подпишитесь на канал с его проектами. А если хотите следить за новостями этого бота — на канал проекта. Спасибо за поддержку!';}
  async applyBan(staffId,target,seconds,reason,comment,hide=false,deleteMessages=false){
    if(!this.isStaff(staffId) || this.isAdmin(target))throw new Error('Недостаточно прав.');
    this.store.ban(target,seconds,reason,hide,deleteMessages);
    const notes=this.bot.runtime.banComments || (this.bot.runtime.banComments={});notes[target]={staffId,comment,at:moscow()};this.bot.persist();
    const ban=this.store.get('SELECT until_ts FROM bans WHERE user_id=?',target);
    const duration=ban.until_ts?new Date(ban.until_ts*1000).toLocaleString('ru-RU',{timeZone:'Europe/Moscow'}):'навсегда';
    const result=await this.bot.send(target,`🚫 Вам выдан бан.\nСрок: ${duration}\nПричина: ${reason}\n\nКомментарий администрации:\n${comment}\n\nВы можете смотреть анкеты и редактировать свою. Лайки, сообщения и жалобы недоступны до окончания бана.`);
    return {delivered:!!result?.ok};
  }
  deleteReport(id,reportId) {
    if(!this.isStaff(id))throw new Error('Недостаточно прав.');
    const result=this.store.run('DELETE FROM reports WHERE id=?',reportId);
    if(!result.changes)return false;
    delete this.bot.runtime.reportReplies?.[reportId];this.bot.persist();return true;
  }
  async replyReport(id,reportId,text) {
    if(!this.isStaff(id))throw new Error('Недостаточно прав.');
    const report=this.store.get('SELECT * FROM reports WHERE id=?',reportId);
    if(!report)throw new Error('Жалоба не найдена.');
    if(typeof text!=='string' || !text.trim() || text.length>3500)throw new Error('Введите ответ от 1 до 3500 символов.');
    const replies=this.bot.runtime.reportReplies || (this.bot.runtime.reportReplies={});
    const answer={text:text.trim(),staffId:id,at:moscow()};replies[reportId]=answer;this.bot.persist();
    const response=await this.bot.send(report.reporter_id,'Пришел ответ по вашей жалобе',inline([[button('Открыть',`report_answer_${reportId}`)]]));
    return {delivered:!!response?.ok};
  }
  actionKeyboard() {return inline([[button('❌ Отменить','admin_cancel'),button('⬅️ В админ-меню','admin_home')]]);}
  doneKeyboard() {return inline([[button('⬅️ В админ-меню','admin_home')]]);}
  stats(detailed=true) {
    const colleges=this.bot.colleges;
    const counts=this.store.all('SELECT u.college,COUNT(*) AS total,SUM(CASE WHEN b.user_id IS NULL THEN 1 ELSE 0 END) AS available FROM users u LEFT JOIN blocked_users b ON b.user_id=u.user_id GROUP BY u.college');
    const today=moscow().slice(0,10)+' 00:00:00';
    let result='📊 Статистика по колледжам:\n\n'+colleges.map(c=>`${c}: ${counts.find(x=>x.college===c)?.available || 0}/ ${counts.find(x=>x.college===c)?.total || 0} чел.`).join('\n');
    result+=`\n\nВсего пользователей: ${this.store.count('SELECT COUNT(*) FROM users')}\nЗарегистрировано сегодня: ${this.store.count('SELECT COUNT(*) FROM users WHERE datetime(created_at)>=datetime(?)',today)}`;
    if (!detailed) return result;
    const week=moscow(new Date(Date.now()-7*86400000)),month=moscow(new Date(Date.now()-30*86400000));
    for (const [label,start] of [['Сегодня',today],['За неделю',week],['За месяц',month]]) {
      result+=`\n${label}: регистраций ${this.store.count('SELECT COUNT(*) FROM users WHERE datetime(created_at)>=datetime(?)',start)}, сообщений ${this.store.count('SELECT COUNT(*) FROM messages WHERE datetime(created_at)>=datetime(?)',start)}`;
    }
    let active=0;
    for (let day=1;day<=7;day++) {
      const start=moscow(new Date(Date.now()-day*86400000)).slice(0,10)+' 00:00:00';
      const end=moscow(new Date(Date.now()-(day-1)*86400000)).slice(0,10)+' 00:00:00';
      active+=this.store.count(`SELECT COUNT(DISTINCT user_id) FROM (
        SELECT sender_id AS user_id FROM messages WHERE created_at>=? AND created_at<? UNION
        SELECT receiver_id FROM messages WHERE created_at>=? AND created_at<? UNION
        SELECT user_id FROM likes WHERE created_at>=? AND created_at<? UNION
        SELECT user_id FROM users WHERE created_at>=? AND created_at<?)`,start,end,start,end,start,end,start,end);
    }
    return result+`\n\n❤️ Лайков: ${this.store.count('SELECT COUNT(*) FROM likes')}\n💖 Взаимных симпатий: ${this.store.count('SELECT COUNT(*) FROM matches')}\n🚫 Активных банов: ${this.store.count('SELECT COUNT(*) FROM bans WHERE until_ts=0 OR until_ts>?',now())}\nЗаблокировали бота: ${this.store.count('SELECT COUNT(*) FROM blocked_users')}\nСреднее число активных за день: ${(active/7).toFixed(1)}\nВерсия: ${require('../package.json').version}\nUptime: ${Math.floor(process.uptime()/60)} мин.`;
  }
  async bans(chat,all=false,page=0) {
    const rows=this.store.all(`SELECT * FROM bans ${all?'':'WHERE until_ts=0 OR until_ts>?'} ORDER BY created_at DESC LIMIT 15 OFFSET ?`,...(all?[]:[now()]),page*15);
    const buttons=rows.map(b=>[button(`${b.user_id} · ${b.reason || 'Не указана'}`,`ban_view_${b.user_id}`)]);
    buttons.push([button('⬅️ В админ-меню','admin_home')]);
    buttons.push([button('🔄 Обновить','banlist_refresh'),button('Все баны','ban_show_all')],[button('🔎 Поиск по ID','ban_search')]);
    const nav=[];if(page>0)nav.push(button('⬅️',`ban_page_${Number(all)}_${page-1}`));if(rows.length===15)nav.push(button('➡️',`ban_page_${Number(all)}_${page+1}`));if(nav.length)buttons.push(nav);
    return this.bot.send(chat,rows.length?'🚫 Список банов:':'Активных банов нет.',inline(buttons));
  }
  async banDetails(chat,target) {
    const ban=this.store.get('SELECT * FROM bans WHERE user_id=?',target);
    if (!ban) return this.bot.send(chat,'✅ Поиск завершён. Бан не найден.',this.doneKeyboard());
    return this.bot.send(chat,`🚫 ${target}\nПричина: ${ban.reason}\nДо: ${ban.until_ts?new Date(ban.until_ts*1000).toLocaleString('ru-RU',{timeZone:'Europe/Moscow'}):'навсегда'}\nАнкета скрыта: ${ban.delete_profile?'да':'нет'}\nСообщения удалены: ${ban.delete_messages?'да':'нет'}`,inline([[button('Разбанить',`ban_unban_${target}`),button('Анкета',`view_${target}`)],[button('⬅️ Список','banlist_refresh')]]));
  }
  async beginBan(id,chat,target) {
    if (this.isAdmin(target) || target===id) return this.bot.send(chat,'Нельзя заблокировать администратора или себя.');
    this.bot.setState(id,'admin_ban',{target});
    return this.bot.send(chat,`Причина бана пользователя ${target}:`,inline([[button('Своя причина','ban_reason_custom')],[button('📢 Реклама','ban_reason_ad')],[button('🔗 Ссылки','ban_reason_links')],[button('🔞 Порнография','ban_reason_porn')]]));
  }
  async broadcast(chat,text,route,appTitle,entities=[],job=null) {
    if (this.broadcasting) return this.bot.send(chat,'Рассылка уже выполняется.');
    this.broadcasting=true;let {success=0,failed=0,skipped=0,blocked=0,uncertain=0}=job?.counts || {};
    if(job?.pending){uncertain++;delete job.pending;}
    const checkpoint=()=>{if(job){job.counts={success,failed,skipped,blocked,uncertain};delete job.pending;this.bot.persist();}};
    try {
      await this.bot.send(chat,'📢 Рассылка запущена.');
      const recipients=job?(job.recipients || (job.recipients=this.store.recipients(true).map(u=>u.user_id))):this.store.recipients(true).map(u=>u.user_id);
      for(let index=job?.cursor || 0;index<recipients.length;index++) {
        const user={user_id:recipients[index]};
        if (this.bot.stopping) break;
        if(job){job.cursor=index+1;job.pending=user.user_id;this.bot.persist();}
        if(this.store.banned(user.user_id) || this.store.mailingDisabled(user.user_id)){skipped++;checkpoint();continue;}
        const result=await this.bot.sendMailing(user.user_id,text,route,false,appTitle,entities);
        if(result?.ok)success++;else{
          failed++;
          if(result?.error_code===403 && /blocked by the user/i.test(result.description || ''))blocked++;
        }
        checkpoint();
        await sleep(70);
      }
      if(!this.bot.stopping)await this.bot.send(chat,`📢 Рассылка завершена\n✅ Отправлено: ${success}\n❌ Ошибок: ${failed}\n🚫 Заблокировали бота: ${blocked}\n⏭ Пропущено: ${skipped}${uncertain?`\n⚠️ Статус не подтверждён после перезапуска: ${uncertain}`:''}`);
      if(job){if(!this.bot.stopping)this.bot.runtime.scheduledBroadcasts=this.scheduled().filter(j=>j.id!==job.id);this.bot.persist();}
    } finally {this.broadcasting=false;}
  }
  scheduled(){return this.bot.runtime.scheduledBroadcasts || (this.bot.runtime.scheduledBroadcasts=[]);}
  async scheduledList(chat){
    const jobs=this.scheduled();
    await this.bot.send(chat,jobs.length?'Запланированные рассылки (московское время):':'Запланированных рассылок нет.',this.doneKeyboard());
    for(const job of jobs)await this.bot.send(chat,`${scheduleLabel(job.at)}${job.started?' — отправляется':''}\n${job.text}`,job.started?undefined:inline([[button('📢 Отправить сейчас',`admin_schedule_send_${job.id}`)],[button('❌ Отменить рассылку',`admin_schedule_delete_${job.id}`)]]));
  }
  async runScheduled(){
    if(this.broadcasting || this.bot.stopping)return;
    const job=this.scheduled().filter(j=>j.at<=Date.now()).sort((a,b)=>a.at-b.at)[0];
    if(!job)return;
    job.started=true;this.bot.persist();
    await this.broadcast(job.chat,job.text,job.route,job.appTitle,job.entities,job);
  }
  async message(message) {
    const id=message.from.id,chat=message.chat.id,text=message.text || '';
    if(!this.isStaff(id))return false;
    if(text==='/cancel' || text==='⬅️ Отмена' || /^\/start(?:\s|$)/.test(text))return false;
    const [command,...args]=text.trim().split(/\s+/);const target=integer(args[0]);
    if(command==='/admin') {this.bot.reset(id);await this.bot.send(chat,'Панель администратора:',this.keyboard(id));return true;}
    if(command==='/help') {await this.bot.send(chat,'/admin — меню\n/view ID — анкета\n/ban ID — бан\n/unban ID — снять бан\n/banlist — баны\n/cancel — отмена'+(this.isAdmin(id)?'\n/stats — статистика\n/broadcast ТЕКСТ — рассылка\n/auto ТЕКСТ — реклама\n/add_moderator ID\n/remove_moderator ID\n/list_staff\n/version — проверить GitHub\n/restart — перезапустить dvbot':''));return true;}
    if(command==='/view') {if(!target)await this.bot.send(chat,'Использование: /view ID');else await this.bot.showProfile(chat,this.store.user(target),{viewer:id});return true;}
    if(command==='/ban') {if(!target)await this.bot.send(chat,'Использование: /ban ID');else await this.beginBan(id,chat,target);return true;}
    if(command==='/unban') {if(!target)await this.bot.send(chat,'Использование: /unban ID');else{this.store.unban(target);await this.bot.send(chat,`✅ ${target} разбанен.`);}return true;}
    if(command==='/banlist' || text==='🚫 Банлист' || text==='⚙️ Управление банами') {await this.bans(chat);return true;}
    const state=this.bot.state(id);
    if(state.step==='admin_report_reply'){if(!text.trim() || text.length>3500){await this.bot.send(chat,'Введите ответ до 3500 символов.',this.actionKeyboard());return true;}const result=await this.replyReport(id,state.data.reportId,text);this.bot.reset(id);await this.bot.send(chat,result.delivered?'✅ Ответ отправлен.':'Ответ сохранён. Уведомление не доставлено.',this.doneKeyboard());return true;}
    if(state.step==='admin_ban_reason' || state.step==='admin_ban_comment'){
      if(!text.trim() || text.length>1000){await this.bot.send(chat,'Введите текст до 1000 символов.',this.actionKeyboard());return true;}
      const ban={...state.data};
      if(state.step==='admin_ban_reason'){ban.reason=text.trim();this.bot.setState(id,'admin_ban',ban);await this.bot.send(chat,'Срок бана:',inline([[button('1 день','ban_duration_1d'),button('7 дней','ban_duration_7d')],[button('30 дней','ban_duration_30d'),button('Навсегда','ban_duration_forever')]]));}
      else{ban.comment=text.trim();this.bot.setState(id,'admin_ban',ban);await this.bot.send(chat,'Скрыть анкету на срок бана?',inline([[button('Да','ban_delete_profile_yes'),button('Нет','ban_delete_profile_no')]]));}return true;
    }
    if(state.step==='admin_broadcast_time'){
      if(!this.isAdmin(id))return false;
      const at=parseMoscowTime(text);
      if(!at || at<=Date.now()){await this.bot.send(chat,'Введите будущую дату и время по Москве: ДД.ММ.ГГГГ ЧЧ:ММ, например 12.10.2026 18:30.',this.actionKeyboard());return true;}
      this.bot.setState(id,'admin_confirm_broadcast',{...state.data,at});await this.broadcastPreview(chat,this.bot.state(id).data);return true;
    }
    if(state.step==='admin_broadcast_title'){if(!text.trim() || Array.from(text.trim()).length>64){await this.bot.send(chat,'Введите название кнопки от 1 до 64 символов.',this.actionKeyboard());return true;}this.bot.setState(id,'admin_confirm_broadcast',{...state.data,appTitle:text.trim()});await this.broadcastPreview(chat,this.bot.state(id).data);return true;}
    if(state.step==='admin_input_delete_profile'){
      if(!this.isAdmin(id))return false;
      const targetId=integer(text.trim()),token=targetId && this.requestProfileDeletion(id,targetId);
      if(!token){await this.bot.send(chat,'Введите ID существующей анкеты. Анкета администратора защищена.',this.actionKeyboard());return true;}
      const user=this.store.user(targetId);await this.bot.send(chat,`Удалить анкету «${user.name}» (ID: ${targetId})?\nФото, видео, лайки и симпатии будут удалены. Переписка, жалобы и баны сохранятся.`,inline([[button('Нет, оставить','admin_cancel')],[button('Да, удалить анкету',`admin_delete_profile_confirm_${token}`)]]));return true;
    }
    const inputId=integer(command);
    if(['admin_input_view','admin_input_ban','admin_input_add_staff','admin_input_remove_staff'].includes(state.step)) {
      if(!inputId){await this.bot.send(chat,'Нужен числовой ID пользователя. Отправьте ID или завершите действие кнопкой ниже.',this.actionKeyboard());return true;}
      const action=state.step.slice(12);this.bot.reset(id);
      return this.message({...message,text:{view:'/view',ban:'/ban',add_staff:'/add_moderator',remove_staff:'/remove_moderator'}[action]+' '+inputId});
    }
    if(state.step==='admin_ban_search') {if(!inputId)await this.bot.send(chat,'Нужен числовой ID пользователя. Отправьте ID или завершите поиск кнопкой ниже.',this.actionKeyboard());else{this.bot.reset(id);await this.banDetails(chat,inputId);}return true;}
    if(!this.isAdmin(id))return false;
    if(command==='/add_moderator' || command==='/remove_moderator') {
      if(!target)await this.bot.send(chat,`Использование: ${command} ID`);
      else{if(command==='/add_moderator')this.store.run("INSERT OR REPLACE INTO staff(user_id,role) VALUES(?,'moderator')",target);else this.store.run("DELETE FROM staff WHERE user_id=? AND role='moderator'",target);await this.bot.send(chat,'✅ Сохранено.');}
      return true;
    }
    if(command==='/list_staff') {await this.bot.send(chat,`Администратор: ${this.config.adminId}\nМодераторы: ${this.store.all("SELECT user_id FROM staff WHERE role='moderator'").map(u=>u.user_id).join(', ')||'нет'}`);return true;}
    if(command==='/stats' || text==='📊 Статистика') {await this.bot.send(chat,this.stats());return true;}
    if(command==='/version' || text==='🆕 Проверить обновления') {await this.updateVersion(chat);return true;}
    if(command==='/restart' || text==='♻️ Перезапустить dvbot') {await this.bot.send(chat,'Перезапустить процесс PM2 dvbot?',inline([[button('♻️ Перезапустить dvbot','admin_restart')],[button('Отмена','admin_cancel')]]));return true;}
    if(command==='/photo') {await this.bot.send(chat,'Фото сохранены на прежних местах. Автоматическая выгрузка и замена путей отключены.');return true;}
    const action=command==='/broadcast' || text==='📢 Рассылка'?'broadcast':command==='/auto' || text==='🔄 Установить автосообщение'?'auto':null;
    if(action){if(action==='broadcast' && this.broadcasting){await this.bot.send(chat,'Рассылка уже выполняется. Дождитесь завершения.');return true;}const body=command.startsWith('/')?text.slice(command.length).trim():'';this.bot.setState(id,`admin_${action}`,{});if(body)return this.preview(id,chat,action,body,(message.entities || []).map(e=>({...e,offset:e.offset-text.indexOf(body)}))); if(action==='auto')await this.bot.send(chat,`Текущее автосообщение:\n\n${this.store.autoMessage() || this.supportTemplate()}`,{inline_keyboard:[this.bot.mailingKeyboard().inline_keyboard[0]]});await this.bot.send(chat,action==='auto'?'Введите новый текст автосообщения или отмените действие:':'Введите текст рассылки. Премиум-эмодзи можно вставить из Telegram или через <tg-emoji emoji-id="ID">🩷</tg-emoji>. Затем можно выбрать время по Москве и отправить тест себе.',this.actionKeyboard());return true;}
    if(state.step==='admin_broadcast' || state.step==='admin_auto') {return this.preview(id,chat,state.step.slice(6),text,message.entities);}
    if(state.step==='admin_confirm_broadcast' || state.step==='admin_confirm_auto') {await this.bot.send(chat,'Нажмите кнопку подтверждения или /cancel.');return true;}
    return false;
  }
  async preview(id,chat,action,text,entities=[]) {
    if(!text.trim() || text.length>3500){await this.bot.send(chat,'Введите текст от 1 до 3500 символов.');return true;}
    this.bot.setState(id,`admin_confirm_${action}`,action==='broadcast'?mailingContent(text,entities):{text});
    if(action==='broadcast')await this.broadcastPreview(chat,this.bot.state(id).data);else await this.bot.send(chat,`Предпросмотр:\n\n${text}`,inline([[button('✅ Подтвердить',`admin_confirm_${action}`)],[button('❌ Отменить','admin_cancel')]]));return true;
  }
  async broadcastPreview(chat,draft){
    const labels={discover:'Анкеты',likes:'Симпатии',chats:'Диалоги',me:'Моя анкета'};
    const rows=[[button('🧪 Отправить себе','admin_broadcast_test')]];
    if(this.config.miniApp?.enabled)rows.push([button('Добавить / изменить кнопку Mini App','admin_broadcast_app')]);
    rows.push([button('📢 Отправить сейчас','admin_broadcast_now')],[button('🕒 Время по Москве','admin_broadcast_time')]);
    if(draft.at)rows.push([button('✅ Запланировать','admin_confirm_broadcast')]);
    rows.push([button('❌ Отменить','admin_cancel')]);
    return this.bot.api.call('sendMessage',{chat_id:chat,text:`Предпросмотр:\n\n${draft.text}\n\nОтправка: ${draft.at?scheduleLabel(draft.at):'сейчас'}\nКнопка Mini App: ${labels[draft.route] || 'не добавлена'}${draft.route?'\nНазвание: '+(draft.appTitle || '🌐 Открыть мини-приложение'):''}`,entities:(draft.entities || []).map(e=>({...e,offset:e.offset+'Предпросмотр:\n\n'.length})),reply_markup:inline(rows)});
  }
  async callback(query) {
    const id=query.from.id,chat=query.message?.chat.id,data=query.data || '';
    if(!/^(?:admin_|ban_)/.test(data) && data!=='banlist_refresh')return false;
    const staffActions=new Set(['admin_action_bans','admin_action_view','admin_action_ban','admin_home','admin_cancel','admin_report_reply']);
    const adminOnly=data.startsWith('admin_') && !data.startsWith('admin_ban_') && !staffActions.has(data) && !/^admin_report_(?:reply|delete|delete_confirm)_\d+$/.test(data);
    if(!chat || query.message.chat.type!=='private' || (adminOnly?!this.isAdmin(id):!this.isStaff(id))){await this.bot.answer(query,'Недостаточно прав');return true;}
    await this.bot.answer(query);
    if(['admin_miniapp_on','admin_miniapp_off'].includes(data)){try{await this.bot.toggleMiniApp(data==='admin_miniapp_on');await this.bot.send(chat,this.config.miniApp.enabled?'Mini App включено.':'Mini App выключено.',this.keyboard(id));}catch(error){await this.bot.send(chat,'Не удалось изменить настройку: '+error.message);}return true;}
    const deletion=data.match(/^admin_report_(delete|delete_confirm)_(\d+)$/);
    if(deletion){const reportId=Number(deletion[2]);if(!this.store.get('SELECT 1 FROM reports WHERE id=?',reportId)){await this.bot.send(chat,'Жалоба уже удалена или не найдена.',this.doneKeyboard());return true;}
      if(deletion[1]==='delete'){await this.bot.send(chat,`Удалить жалобу #${reportId} вместе с ответом администрации?`,inline([[button('Удалить',`admin_report_delete_confirm_${reportId}`)],[button('Отмена','admin_cancel')]]));return true;}
      this.deleteReport(id,reportId);this.bot.reset(id);await this.bot.send(chat,'✅ Жалоба удалена.',this.doneKeyboard());return true;
    }
    const reply=data.match(/^admin_report_reply_(\d+)$/);if(reply){const reportId=Number(reply[1]);if(!this.store.get('SELECT 1 FROM reports WHERE id=?',reportId)){await this.bot.send(chat,'Жалоба не найдена.');return true;}this.bot.setState(id,'admin_report_reply',{reportId});await this.bot.send(chat,'Введите ответ автору жалобы:',this.actionKeyboard());return true;}
    if(data==='admin_support_template'){this.store.setAutoMessage(this.supportTemplate());await this.bot.send(chat,'✅ Шаблон автосообщения установлен.',this.doneKeyboard());return true;}
    if(data==='admin_home'){this.bot.reset(id);await this.bot.send(chat,'Панель администратора:',this.keyboard(id));return true;}
    if(data.startsWith('admin_action_') || ['banlist_refresh','ban_show_all','ban_search','ban_management'].includes(data) || /^ban_(?:view|page)_/.test(data))this.bot.reset(id);
    if(data.startsWith('admin_action_')) {
      const action=data.slice(13);
      if(['view','ban','add_staff','remove_staff','delete_profile'].includes(action)) {this.bot.setState(id,'admin_input_'+action);await this.bot.send(chat,'Введите ID пользователя или отмените действие:',this.actionKeyboard());return true;}
      const text={bans:'/banlist',stats:'/stats',broadcast:'/broadcast',auto:'/auto',staff:'/list_staff'}[action];
      if(text)await this.message({from:query.from,chat:query.message.chat,text});return true;
    }
    if(/^admin_delete_profile_confirm_[a-f0-9]{24}$/.test(data)){
      const state=this.bot.state(id),target=state.data.target,deleted=this.confirmProfileDeletion(id,target,data.slice('admin_delete_profile_confirm_'.length));
      await this.bot.send(chat,deleted?`✅ Анкета пользователя ${target} удалена.`:'Подтверждение устарело. Повторите удаление.',this.doneKeyboard());return true;
    }
    if(data==='admin_schedule_list'){await this.scheduledList(chat);return true;}
    if(/^admin_schedule_send_/.test(data)){
      const jobId=data.slice('admin_schedule_send_'.length),job=this.scheduled().find(j=>j.id===jobId);
      if(!job || job.started){await this.bot.send(chat,'Рассылка уже отправляется или отсутствует.');return true;}
      if(this.broadcasting){await this.bot.send(chat,'Другая рассылка уже выполняется. Дождитесь завершения.');return true;}
      job.at=Date.now();job.started=true;this.bot.persist();
      this.bot.launch(()=>this.broadcast(job.chat,job.text,job.route,job.appTitle,job.entities,job));
      await this.bot.api.call('editMessageReplyMarkup',{chat_id:chat,message_id:query.message.message_id,reply_markup:inline([])});return true;
    }
    if(/^admin_schedule_delete_/.test(data)){
      const jobId=data.slice('admin_schedule_delete_'.length),job=this.scheduled().find(j=>j.id===jobId);
      if(!job || job.started){await this.bot.send(chat,'Рассылка уже отправляется или отсутствует.');return true;}
      this.bot.runtime.scheduledBroadcasts=this.scheduled().filter(j=>j.id!==jobId);this.bot.persist();await this.bot.send(chat,'✅ Запланированная рассылка отменена.',this.doneKeyboard());return true;
    }
    if(data.startsWith('admin_broadcast_')){
      const state=this.bot.state(id);if(state.step!=='admin_confirm_broadcast' || !state.data.text){await this.bot.send(chat,'Черновик устарел. Создайте новую рассылку.');return true;}
      if(data==='admin_broadcast_time'){this.bot.setState(id,'admin_broadcast_time',state.data);await this.bot.send(chat,'Введите дату и время отправки по Москве: ДД.ММ.ГГГГ ЧЧ:ММ, например 12.10.2026 18:30.',this.actionKeyboard());return true;}
      if(data==='admin_broadcast_now'){if(this.broadcasting){await this.bot.send(chat,'Рассылка уже выполняется. Дождитесь завершения.');return true;}this.bot.reset(id);this.bot.launch(()=>this.broadcast(chat,state.data.text,state.data.route,state.data.appTitle,state.data.entities));return true;}
      if(data==='admin_broadcast_test'){const result=await this.bot.sendMailing(chat,state.data.text,state.data.route,false,state.data.appTitle,state.data.entities);await this.bot.send(chat,result?.ok?'✅ Тест отправлен только вам.':'❌ Не удалось отправить тест.');await this.broadcastPreview(chat,state.data);return true;}
      if(data==='admin_broadcast_app'){await this.bot.send(chat,'Куда ведёт кнопка Mini App?',inline([[button('Анкеты','admin_broadcast_route_discover'),button('Симпатии','admin_broadcast_route_likes')],[button('Диалоги','admin_broadcast_route_chats'),button('Моя анкета','admin_broadcast_route_me')],[button('Без кнопки','admin_broadcast_route_none')],[button('Отмена','admin_cancel')]]));return true;}
      const route=data.slice('admin_broadcast_route_'.length);if(data.startsWith('admin_broadcast_route_') && ['discover','likes','chats','me','none'].includes(route)){if(route!=='none' && !this.config.miniApp?.enabled){await this.bot.send(chat,'Mini App отключено.');return true;}if(route==='none'){this.bot.setState(id,state.step,{...state.data,route:null,appTitle:null});await this.broadcastPreview(chat,this.bot.state(id).data);}else{this.bot.setState(id,'admin_broadcast_title',{...state.data,route});await this.bot.send(chat,'Введите название кнопки Mini App (до 64 символов):',this.actionKeyboard());}}return true;
    }
    if(data==='admin_restart'){await this.restart(chat);return true;}
    if(data==='admin_cancel'){this.bot.reset(id);await this.bot.send(chat,'Отменено.',this.keyboard(id));return true;}
    if(data==='admin_update_version'){await this.updateVersion(chat);return true;}
    if(data==='admin_check_version'){await this.checkVersion(chat,true);return true;}
    if(data==='admin_confirm_broadcast' || data==='admin_confirm_auto'){
      const state=this.bot.state(id);if(state.step!==data || !state.data.text){await this.bot.send(chat,'Подтверждение устарело.');return true;}
      if(data.endsWith('_broadcast') && state.data.at){
        if(state.data.at<=Date.now()){await this.bot.send(chat,'Время уже прошло. Укажите новое время или выберите «Сейчас».');return true;}
        this.scheduled().push({...state.data,id:require('node:crypto').randomUUID(),chat});this.bot.reset(id);
        await this.bot.send(chat,`✅ Рассылка запланирована на ${scheduleLabel(state.data.at)}.`,this.doneKeyboard());return true;
      }
      this.bot.reset(id);
      if(data.endsWith('_broadcast'))this.bot.launch(()=>this.broadcast(chat,state.data.text,state.data.route,state.data.appTitle,state.data.entities));
      else{this.store.setAutoMessage(state.data.text);await this.bot.send(chat,'✅ Автосообщение сохранено.',this.keyboard(id));}
      return true;
    }
    const target=data.match(/^(admin_ban|ban_view|ban_unban)_(\d+)$/);
    if(target){const uid=Number(target[2]);if(target[1]==='admin_ban')await this.beginBan(id,chat,uid);else if(target[1]==='ban_view')await this.banDetails(chat,uid);else{this.store.unban(uid);await this.bot.send(chat,'✅ Бан снят. Действие завершено.',this.doneKeyboard());}return true;}
    if(data==='banlist_refresh' || data==='ban_management'){await this.bans(chat);return true;}
    if(data==='ban_show_all'){await this.bans(chat,true);return true;}
    if(data==='ban_search'){this.bot.setState(id,'admin_ban_search');await this.bot.send(chat,'Введите ID пользователя или отмените действие:',this.actionKeyboard());return true;}
    const page=data.match(/^ban_page_([01])_(\d+)$/);if(page){await this.bans(chat,page[1]==='1',Number(page[2]));return true;}
    const state=this.bot.state(id),ban={...state.data};
    if(state.step!=='admin_ban' || !ban.target){await this.bot.send(chat,'Сначала выберите пользователя: /ban ID');return true;}
    if(data==='ban_reason_custom'){this.bot.setState(id,'admin_ban_reason',ban);await this.bot.send(chat,'Введите причину бана:',this.actionKeyboard());return true;}
    if(data.startsWith('ban_reason_')) {
      const reason={ban_reason_ad:'Реклама',ban_reason_links:'Ссылки',ban_reason_porn:'Порнография'}[data];if(!reason)return true;
      ban.reason=reason;this.bot.setState(id,'admin_ban',ban);
      await this.bot.send(chat,'Срок бана:',inline(['1d','3d','7d','30d','3m','forever'].map((duration,i)=>[button(['1 день','3 дня','7 дней','30 дней','3 месяца','Навсегда'][i],'ban_duration_'+duration)])));
    } else if(data.startsWith('ban_duration_')) {
      const durations={'1d':86400,'3d':259200,'7d':604800,'30d':2592000,'3m':7776000,forever:0};const key=data.slice(13);
      if(!ban.reason || !(key in durations))return true;
      ban.seconds=durations[key];this.bot.setState(id,'admin_ban_comment',ban);
      await this.bot.send(chat,'Введите комментарий, который получит пользователь:',this.actionKeyboard());
    } else if(data==='ban_delete_profile_yes' || data==='ban_delete_profile_no') {
      if(ban.seconds===undefined)return true;ban.hide=data.endsWith('_yes');this.bot.setState(id,'admin_ban',ban);
      await this.bot.send(chat,'Удалить переписку пользователя?',inline([[button('Да, удалить','ban_delete_messages_yes')],[button('Нет, сохранить','ban_delete_messages_no')]]));
    } else if(data==='ban_delete_messages_yes' || data==='ban_delete_messages_no') {
      if(ban.hide===undefined || this.isAdmin(ban.target))return true;
      const notification=await this.applyBan(id,ban.target,ban.seconds,ban.reason,ban.comment || ban.reason,ban.hide,data.endsWith('_yes'));this.bot.reset(id);await this.bot.send(chat,`✅ Пользователь ${ban.target} заблокирован. ${notification.delivered?'Уведомление отправлено.':'Уведомление не доставлено.'} Действие завершено.`,this.doneKeyboard());
    }
    return true;
  }
  async restart(chat) {
    if(this.restarting)return this.bot.send(chat,'Перезапуск уже выполняется.');
    if(this.broadcasting)return this.bot.send(chat,'Дождитесь завершения рассылки перед перезапуском.');
    this.restarting=true;
    try {
      // Без shell, пользователь не может подставить имя процесса или команду.
      await exec('pm2',['describe','dvbot'],{cwd:ROOT,timeout:10000,maxBuffer:65536});
      const reply=await this.bot.send(chat,'♻️ Перезапускаю PM2 dvbot.');if(!reply?.ok){this.restarting=false;return;}
      this.bot.runtime.restartRequested=chat;this.bot.persist();
      const fd=fs.openSync(path.join(ROOT,'.dvbot-restart.log'),'a',0o600);
      const child=spawn('pm2',['restart','dvbot'],{cwd:ROOT,detached:true,stdio:['ignore',fd,fd],shell:false});
      child.once('error',()=>{this.restarting=false;delete this.bot.runtime.restartRequested;this.bot.persist();this.bot.send(chat,'Не удалось запустить PM2.').catch(()=>{});});
      child.once('exit',code=>{if(code && !this.bot.stopping){this.restarting=false;delete this.bot.runtime.restartRequested;this.bot.persist();this.bot.send(chat,'PM2 не смог перезапустить dvbot. Проверьте журнал.').catch(()=>{});}});
      child.unref();fs.closeSync(fd);
    } catch(error) {this.restarting=false;await this.bot.send(chat,'Процесс PM2 dvbot не найден или PM2 недоступен. Запустите: pm2 start ecosystem.config.cjs');}
  }
  async remoteVersion() {
    const gh=this.config.github;
    if(!gh || !/^[\w.-]+\/[\w.-]+$/.test(gh.repository) || !/^[\w./-]+$/.test(gh.branch) || gh.branch.startsWith('-'))throw new Error('Проверьте github.repository и github.branch в config.json.');
    const response=await fetch(`https://raw.githubusercontent.com/${gh.repository}/${encodeURIComponent(gh.branch)}/package.json`,{signal:AbortSignal.timeout(15000),headers:{'User-Agent':'dvbot'}});
    if(response.status===404)throw new Error('JavaScript-релиз ещё не опубликован: в ветке нет package.json.');
    if(!response.ok)throw new Error(`GitHub HTTP ${response.status}.`);
    const pkg=await response.json();if(pkg.main!=='src/main.js' || typeof pkg.version!=='string')throw new Error('Несовместимый формат релиза.');
    return {version:pkg.version,key:pkg.version};
  }

  async updateCommand(command,args,options={}) {
    return exec(command,args,{cwd:ROOT,timeout:120000,maxBuffer:1048576,...options});
  }
  async updateVersion(chat) {
    if(!this.isAdmin(chat))return;
    if(this.updating || this.checking || this.restarting)return this.bot.send(chat,'Проверка или обновление уже выполняется.');
    this.updating=true;
    let stage='Проверка версии GitHub';
    try {
      const local=require('../package.json').version,remote=await this.remoteVersion();
      if(!newer(remote.version,local))return await this.bot.send(chat,`✅ Установлена актуальная версия: v${local}.`);
      await this.bot.send(chat,`🔄 Обновляю бота: v${local} → v${remote.version}…`);
      stage='Загрузка и проверка публичного релиза';
      const {installUpdate}=require('./updater');
      const installed=await installUpdate(ROOT,this.config.github,(...args)=>this.updateCommand(...args));
      await this.bot.send(chat,`✅ Код обновлён до v${installed}. Перезапускаю dvbot.`);
      stage='Перезапуск';
      await this.restart(chat);
    } catch(error) {
      let detail=String(error.stderr || error.stdout || error.message || 'Неизвестная ошибка');
      for(const secret of [this.config.token,this.config.github?.token,this.config.github?.token && Buffer.from('x-access-token:'+this.config.github.token).toString('base64')])if(secret)detail=detail.split(secret).join('[скрыто]');
      detail=detail.replace(/https?:\/\/[^\s/@]+:[^\s/@]+@/g,'https://[скрыто]@').replace(/(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]+/g,'[скрыто]').replace(/Authorization:[^\r\n]*/gi,'Authorization: [скрыто]');
      await this.bot.send(chat,`❌ Обновление не завершено.\nЭтап: ${stage}\n\n${detail.slice(-2500)}\n\nБот не перезапущен.`);
    } finally {this.updating=false;}
  }
  async checkVersion(chat=this.config.adminId,manual=false) {
    if(this.checking || this.updating){if(manual)await this.bot.send(chat,'Проверка уже выполняется.');return;}
    this.checking=true;
    try {
      const remote=await this.remoteVersion(),local=require('../package.json').version;
      if(!newer(remote.version,local)){if(manual)await this.bot.send(chat,`Установлена v${local}. Новых версий нет.`);return;}
      if(!manual && this.config.github.autoUpdate===true){this.checking=false;await this.updateVersion(chat);return;}
      const key=`${this.config.adminId}:${remote.version}`;
      const notified=this.bot.runtime.versionNotifications;
      if(notified[key] && !manual)return;
      const text=`🆕 В GitHub доступна новая версия dvbot\nУстановлена: v${local}\nНовая: v${remote.version}\n\nНажмите «Установить обновление».`;
      const markup=inline([[{text:'Посмотреть изменения',url:`https://github.com/${this.config.github.repository}/commits/${encodeURIComponent(this.config.github.branch)}`}],[button('⬇️ Установить обновление','admin_update_version')]]);
      const previous=this.bot.runtime.versionNotice;
      let result;
      if(previous?.admin===this.config.adminId)result=await this.bot.api.call('editMessageText',{chat_id:this.config.adminId,message_id:previous.messageId,text,reply_markup:markup});
      if(result?.description?.includes('message is not modified'))result={ok:true,result:{message_id:previous.messageId}};
      if(!result?.ok)result=await this.bot.send(this.config.adminId,text,markup);
      if(result?.ok){notified[key]=true;this.bot.runtime.versionNotice={admin:this.config.adminId,messageId:result.result.message_id};this.bot.persist();}
    } catch(error) {
      // stderr git может содержать адрес с credentials, поэтому не выводим его.
      const message=error.message;
      if(manual)await this.bot.send(chat,message);
      else if(this.lastVersionError!==message){console.error(message);this.lastVersionError=message;}
    } finally {this.checking=false;}
  }
  start() {
    if(this.bot.runtime.restartRequested){
      const chat=this.bot.runtime.restartRequested;delete this.bot.runtime.restartRequested;this.bot.persist();
      if(chat===this.config.adminId)this.bot.launch(()=>this.bot.send(chat,`✅ dvbot перезапущен. Версия: v${require('../package.json').version}`));
    }
    this.bot.launch(()=>this.runScheduled());
    this.scheduleTimer=setInterval(()=>this.bot.launch(()=>this.runScheduled()),15000);this.scheduleTimer.unref();
    if(!this.config.github?.repository)return;
    this.bot.launch(()=>this.checkVersion());
    this.timer=setInterval(()=>this.bot.launch(()=>this.checkVersion()),Math.max(60,this.config.github?.checkIntervalSeconds || 60)*1000);
    this.timer.unref();
  }
  stop() {clearInterval(this.timer);clearInterval(this.scheduleTimer);}
}

module.exports={Admin,newer,parseMoscowTime};



