'use strict';

const { DatabaseSync } = require('node:sqlite');
const fs = require('node:fs');
const path = require('node:path');
const { randomBytes } = require('node:crypto');

const now = () => Math.floor(Date.now() / 1000);
const moscow = (date = new Date()) => new Date(date.getTime() + 10800000).toISOString().slice(0, 19).replace('T', ' ');
const timestamp = value => value ? Date.parse(/(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : value.replace(' ', 'T') + '+03:00') : 0;

class Store {
  constructor(filename, { create = false, readonly = false } = {}) {
    const exists = filename === ':memory:' ? false : fs.existsSync(filename);
    if (!exists && !create) throw new Error(`База ${filename} не найдена. Проверьте database в config.json; существующие базы не создаются заново.`);
    if (!exists && filename !== ':memory:') fs.mkdirSync(path.dirname(filename), { recursive: true });
    this.db = new DatabaseSync(filename, { readOnly: readonly });
    this.db.exec('PRAGMA busy_timeout=5000');
    if (!exists && create) this.db.exec(Store.schema);
    // Существующая база: никаких миграций, смены journal_mode или очистки данных.
    for (const [table, columns] of Object.entries(Store.required)) {
      const present = new Set(this.all(`PRAGMA table_info(${table})`).map(c => c.name));
      const missing = columns.filter(c => !present.has(c));
      if (missing.length) {
        this.db.close();
        throw new Error(`Несовместимая схема ${table}: отсутствуют ${missing.join(', ')}. База оставлена без изменений.`);
      }
    }
  }
  all(sql, ...params) { return this.db.prepare(sql).all(...params); }
  get(sql, ...params) { return this.db.prepare(sql).get(...params); }
  run(sql, ...params) { return this.db.prepare(sql).run(...params); }
  count(sql, ...params) { return Number(Object.values(this.get(sql, ...params) || { count: 0 })[0]); }
  transaction(fn) {
    this.db.exec('BEGIN IMMEDIATE');
    try { const result = fn(); this.db.exec('COMMIT'); return result; }
    catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }
  close() { this.db.close(); }
  user(id) { return this.get('SELECT * FROM users WHERE user_id=?', id); }
  byToken(token) { return this.get('SELECT * FROM users WHERE profile_token=?', token); }
  token(id) {
    const user = this.user(id);
    if (!user) return null;
    if (user.profile_token) return user.profile_token;
    let token;
    do { token = randomBytes(16).toString('base64url'); } while (this.byToken(token));
    this.run('UPDATE users SET profile_token=? WHERE user_id=?', token, id);
    return token;
  }
  register(id, data, username) {
    return this.transaction(() => {
      const fields = [data.college, data.name, data.age, data.photos.join(','), username || null, data.bio || '', data.gender || null, data.video || null];
      if (this.user(id)) this.run('UPDATE users SET college=?, name=?, age=?, photos=?, username=?, bio=?, gender=?, video=? WHERE user_id=?', ...fields, id);
      else this.run('INSERT INTO users(college,name,age,photos,username,bio,gender,video,user_id,created_at,profile_token) VALUES(?,?,?,?,?,?,?,?,?,?,?)', ...fields, id, moscow(), randomBytes(16).toString('base64url'));
      return this.user(id);
    });
  }
  deleteProfile(id){
    return this.transaction(()=>{
      if(!this.user(id))return false;
      for(const [table,left,right]of [['likes','user_id','liked_user_id'],['matches','user1_id','user2_id'],['dislikes','user_id','disliked_user_id'],['viewed_profiles','user_id','viewed_user_id']])this.run(`DELETE FROM ${table} WHERE ${left}=? OR ${right}=?`,id,id);
      this.run('DELETE FROM profile_boosts WHERE user_id=?',id);
      this.run('DELETE FROM web_auth_codes WHERE user_id=?',id);
      this.run('DELETE FROM users WHERE user_id=?',id);
      return true;
    });
  }
  update(id, field, value) {
    const allowed = new Set(['college','name','age','photos','username','bio','view_scope','is_hidden','gender','video','hide_from_top','mailing_disabled_until','boosted_at']);
    if (!allowed.has(field)) throw new Error('Недопустимое поле анкеты');
    this.run(`UPDATE users SET ${field}=? WHERE user_id=?`, value, id);
  }
  moderator(id) { return !!this.get("SELECT 1 FROM staff WHERE user_id=? AND role='moderator'", id); }
  banned(id) {
    const ban = this.get('SELECT * FROM bans WHERE user_id=?', id);
    if (!ban) return false;
    if (ban.until_ts === 0 || ban.until_ts > now()) return true;
    this.unban(id);
    return false;
  }
  unban(id) {
    this.transaction(() => {
      const ban = this.get('SELECT * FROM bans WHERE user_id=?', id);
      if (ban?.delete_profile) this.update(id, 'is_hidden', 0);
      this.run('DELETE FROM bans WHERE user_id=?', id);
    });
  }
  ban(id, seconds, reason, hide, deleteMessages) {
    this.transaction(() => {
      this.run('INSERT OR REPLACE INTO bans(user_id,until_ts,reason,delete_profile,delete_messages) VALUES(?,?,?,?,?)', id, seconds ? now() + seconds : 0, reason, Number(hide), Number(deleteMessages));
      if (hide) this.update(id, 'is_hidden', 1);
      if (deleteMessages) this.run('DELETE FROM messages WHERE sender_id=? OR receiver_id=?', id, id);
    });
  }
  cleanupExpiredBans() {
    for (const ban of this.all('SELECT user_id FROM bans WHERE until_ts>0 AND until_ts<=?', now())) this.unban(ban.user_id);
  }
  profile(id) {
    const requester = this.user(id);
    if (!requester) return null;
    this.cleanupExpiredBans();
    const base = `SELECT u.* FROM users u WHERE u.user_id!=? AND COALESCE(u.is_hidden,0)=0
      AND NOT EXISTS(SELECT 1 FROM bans b WHERE b.user_id=u.user_id AND (b.until_ts=0 OR b.until_ts>?))`;
    const rejected = ` AND NOT EXISTS(SELECT 1 FROM likes l WHERE l.user_id=? AND l.liked_user_id=u.user_id)
      AND NOT EXISTS(SELECT 1 FROM dislikes d WHERE d.user_id=? AND d.disliked_user_id=u.user_id)`;
    const fresh = ` AND NOT EXISTS(SELECT 1 FROM viewed_profiles v WHERE v.user_id=? AND v.viewed_user_id=u.user_id)`;
    const params = [id, now(), id, id, id];
    const same = requester.view_scope !== 'all';
    let user = same ? this.get(base + rejected + fresh + ' AND u.college=? ORDER BY RANDOM() LIMIT 1', ...params, requester.college) : undefined;
    user ||= this.get(base + rejected + fresh + ' ORDER BY RANDOM() LIMIT 1', ...params);
    if (user) this.run('INSERT OR IGNORE INTO viewed_profiles(user_id,viewed_user_id) VALUES(?,?)', id, user.user_id);
    return user;
  }
  like(id, target) {
    if (id === target || !this.user(id) || !this.user(target) || this.banned(id) || this.banned(target)) return { added: false, matched: false };
    return this.transaction(() => {
      const added = Number(this.run('INSERT OR IGNORE INTO likes(user_id,liked_user_id) VALUES(?,?)', id, target).changes) > 0;
      let matched = false;
      if (this.get('SELECT 1 FROM likes WHERE user_id=? AND liked_user_id=?', target, id)) {
        matched = Number(this.run('INSERT OR IGNORE INTO matches(user1_id,user2_id) VALUES(?,?)', Math.min(id,target), Math.max(id,target)).changes) > 0;
      }
      return { added, matched };
    });
  }
  mutual(id, target) { return !!this.get('SELECT 1 FROM matches WHERE user1_id=? AND user2_id=?', Math.min(id,target), Math.max(id,target)); }
  boost(id) {
    const elapsed = Date.now() - timestamp(this.user(id)?.boosted_at);
    if (elapsed < 86400000) return Math.ceil((86400000-elapsed)/3600000);
    this.transaction(() => {
      this.update(id,'boosted_at',moscow());
      this.run('INSERT INTO profile_boosts(user_id) VALUES(?)', id);
    });
    return 0;
  }
  history(id, target, limit=50, offset=0) {
    return this.all(`SELECT * FROM messages WHERE (sender_id=? AND receiver_id=?) OR (sender_id=? AND receiver_id=?) ORDER BY id DESC LIMIT ? OFFSET ?`, id,target,target,id,limit,offset).reverse();
  }
  conversations(id, offset=0) {
    return this.all(`SELECT m.*,u.name,CASE WHEN m.sender_id=? THEN m.receiver_id ELSE m.sender_id END AS other_id FROM messages m
      LEFT JOIN users u ON u.user_id=CASE WHEN m.sender_id=? THEN m.receiver_id ELSE m.sender_id END
      WHERE m.id IN (SELECT MAX(id) FROM messages WHERE sender_id=? OR receiver_id=? GROUP BY CASE WHEN sender_id=? THEN receiver_id ELSE sender_id END)
      ORDER BY m.id DESC LIMIT 15 OFFSET ?`, id,id,id,id,id,offset);
  }
  saveMessage(sender, receiver, message) {
    const last = this.history(sender,receiver,1)[0];
    const result = this.run('INSERT INTO messages(sender_id,receiver_id,message,voice_file_id,photo_file_id,video_file_id,sticker_file_id,animation_file_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)', sender,receiver,message.text || '',message.voice || null,message.photo || null,message.video || null,message.sticker || null,message.animation || null,moscow());
    return { id: Number(result.lastInsertRowid), notify: !last || last.sender_id === receiver };
  }
  unanswered(id) {
    return this.count(`SELECT COUNT(*) FROM messages m WHERE m.receiver_id=? AND m.id=(SELECT MAX(n.id) FROM messages n WHERE (n.sender_id=m.sender_id AND n.receiver_id=?) OR (n.sender_id=? AND n.receiver_id=m.sender_id))`,id,id,id);
  }
  report(id,target,reason,messageId=null) { this.run('INSERT INTO reports(reporter_id,target_user_id,reason,message_id) VALUES(?,?,?,?)', id,target,reason,messageId); }
  autoMessage() { return this.get('SELECT message FROM auto_messages WHERE is_active=1 ORDER BY id DESC LIMIT 1')?.message; }
  setAutoMessage(text) {
    this.transaction(() => { this.run('UPDATE auto_messages SET is_active=0'); this.run('INSERT INTO auto_messages(message) VALUES(?)',text); });
  }
  mailingDisabled(id) { return timestamp(this.user(id)?.mailing_disabled_until)>Date.now(); }
  recipients(includeBlocked=false) {
    return this.all(`SELECT user_id FROM users WHERE NOT EXISTS(SELECT 1 FROM bans b WHERE b.user_id=users.user_id AND (b.until_ts=0 OR b.until_ts>?)) AND (? OR NOT EXISTS(SELECT 1 FROM blocked_users b WHERE b.user_id=users.user_id))`,now(),Number(includeBlocked)).filter(u=>!this.mailingDisabled(u.user_id));
  }
  profileStats(id) {
    return `❤️ Получено лайков: ${this.count('SELECT COUNT(*) FROM likes WHERE liked_user_id=?',id)}\n👀 Просмотров: ${this.count('SELECT COUNT(*) FROM viewed_profiles WHERE viewed_user_id=?',id)}\n❤️ Отправлено лайков: ${this.count('SELECT COUNT(*) FROM likes WHERE user_id=?',id)}\n💖 Взаимных симпатий: ${this.count('SELECT COUNT(*) FROM matches WHERE user1_id=? OR user2_id=?',id,id)}`;
  }
}

Store.required = {
  users: ['user_id','college','name','age','photos','username','bio','created_at','view_scope','is_hidden','profile_token','boosted_at','gender','video','hide_from_top','mailing_disabled_until'],
  messages: ['id','sender_id','receiver_id','message','voice_file_id','photo_file_id','video_file_id','sticker_file_id','animation_file_id','created_at'],
  staff:['user_id','role'], bans:['user_id','until_ts','reason','delete_profile','delete_messages','created_at'],
  likes:['user_id','liked_user_id'], matches:['user1_id','user2_id'], dislikes:['user_id','disliked_user_id'],
  viewed_profiles:['user_id','viewed_user_id'], reports:['reporter_id','target_user_id','reason','message_id'],
  profile_boosts:['user_id'], blocked_users:['user_id'], auto_messages:['id','message','is_active'], web_auth_codes:['user_id','code','expires_at','used']
};

Store.schema = "CREATE TABLE IF NOT EXISTS users\n                        (id INTEGER PRIMARY KEY AUTOINCREMENT,\n                        user_id INTEGER UNIQUE,\n                        college TEXT,\n                        name TEXT,\n                        age INTEGER,\n                        photos TEXT,\n                        username TEXT,\n                        bio TEXT,\n                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);\nCREATE TABLE IF NOT EXISTS messages\n                        (id INTEGER PRIMARY KEY AUTOINCREMENT,\n                        sender_id INTEGER,\n                        receiver_id INTEGER,\n                        message TEXT,\n                        voice_file_id TEXT,\n                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);\nCREATE TABLE IF NOT EXISTS auto_messages\n                        (id INTEGER PRIMARY KEY AUTOINCREMENT,\n                        message TEXT,\n                        is_active INTEGER DEFAULT 1,\n                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);\nALTER TABLE users ADD COLUMN view_scope TEXT DEFAULT 'college';\nALTER TABLE users ADD COLUMN is_hidden INTEGER DEFAULT 0;\nALTER TABLE users ADD COLUMN profile_token TEXT;\nALTER TABLE users ADD COLUMN boosted_at TIMESTAMP;\nALTER TABLE users ADD COLUMN gender TEXT;\nALTER TABLE users ADD COLUMN video TEXT;\nALTER TABLE users ADD COLUMN hide_from_top INTEGER DEFAULT 0;\nALTER TABLE users ADD COLUMN mailing_disabled_until TIMESTAMP;\nALTER TABLE messages ADD COLUMN photo_file_id TEXT;\nALTER TABLE messages ADD COLUMN video_file_id TEXT;\nALTER TABLE messages ADD COLUMN sticker_file_id TEXT;\nALTER TABLE messages ADD COLUMN animation_file_id TEXT;\nCREATE TABLE IF NOT EXISTS viewed_profiles\n                        (id INTEGER PRIMARY KEY AUTOINCREMENT,\n                        user_id INTEGER,\n                        viewed_user_id INTEGER,\n                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n                        UNIQUE(user_id, viewed_user_id));\nCREATE TABLE IF NOT EXISTS likes\n                        (id INTEGER PRIMARY KEY AUTOINCREMENT,\n                        user_id INTEGER,\n                        liked_user_id INTEGER,\n                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n                        UNIQUE(user_id, liked_user_id));\nCREATE TABLE IF NOT EXISTS matches\n                        (id INTEGER PRIMARY KEY AUTOINCREMENT,\n                        user1_id INTEGER,\n                        user2_id INTEGER,\n                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n                        UNIQUE(user1_id, user2_id));\nCREATE TABLE IF NOT EXISTS bans\n                        (id INTEGER PRIMARY KEY AUTOINCREMENT,\n                        user_id INTEGER UNIQUE,\n                        until_ts INTEGER,\n                        reason TEXT,\n                        delete_profile INTEGER DEFAULT 0,\n                        delete_messages INTEGER DEFAULT 0,\n                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);\nCREATE TABLE IF NOT EXISTS reports\n                        (id INTEGER PRIMARY KEY AUTOINCREMENT,\n                        reporter_id INTEGER,\n                        target_user_id INTEGER,\n                        reason TEXT,\n                        message_id INTEGER,\n                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);\nCREATE TABLE IF NOT EXISTS dislikes\n                        (id INTEGER PRIMARY KEY AUTOINCREMENT,\n                        user_id INTEGER,\n                        disliked_user_id INTEGER,\n                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,\n                        UNIQUE(user_id, disliked_user_id));\nCREATE TABLE IF NOT EXISTS profile_boosts\n                        (id INTEGER PRIMARY KEY AUTOINCREMENT,\n                        user_id INTEGER,\n                        boosted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);\nCREATE TABLE IF NOT EXISTS blocked_users\n                        (id INTEGER PRIMARY KEY AUTOINCREMENT,\n                        user_id INTEGER UNIQUE,\n                        detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);\nCREATE TABLE IF NOT EXISTS web_auth_codes\n                        (id INTEGER PRIMARY KEY AUTOINCREMENT,\n                        user_id INTEGER,\n                        code TEXT UNIQUE,\n                        expires_at TIMESTAMP,\n                        used INTEGER DEFAULT 0,\n                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);\nCREATE TABLE IF NOT EXISTS staff\n                        (id INTEGER PRIMARY KEY AUTOINCREMENT,\n                        user_id INTEGER UNIQUE,\n                        role TEXT NOT NULL,\n                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);";

module.exports = { Store, moscow, timestamp, now };


