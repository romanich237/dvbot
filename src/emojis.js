'use strict';
const ids={'❤️':'5357523891289894888','💌':'5357147682219536262','🚩':'5355142739946156240'};
function premiumParams(params){
 const rows=params.reply_markup?.inline_keyboard;
 if(!rows?.some(row=>row.some(b=>/^next_\d+$/.test(b.callback_data || ''))))return params;
 return {...params,reply_markup:{...params.reply_markup,inline_keyboard:rows.map(row=>row.map(b=>ids[b.text] && /^(?:like|write|report)_\d+$/.test(b.callback_data || '')?{...b,text:'\u200b',icon_custom_emoji_id:ids[b.text]}:{...b}))}};
}
function mailingContent(text,entities=[]){
 const tags=/<tg-emoji\s+emoji-id=["'](\d+)["']>([^<>]+)<\/tg-emoji>/g;
 let output='',last=0,custom=[];
 for(const match of text.matchAll(tags)){
  output+=text.slice(last,match.index);
  custom.push({type:'custom_emoji',offset:output.length,length:match[2].length,custom_emoji_id:match[1]});
  output+=match[2];last=match.index+match[0].length;
 }
 if(last){output+=text.slice(last);return {text:output,entities:custom};}
 return {text,entities:entities.filter(e=>e.type==='custom_emoji' && /^\d+$/.test(e.custom_emoji_id || '') && Number.isInteger(e.offset) && e.offset>=0 && e.length>0 && e.offset+e.length<=text.length).map(e=>({...e}))};
}
module.exports={premiumParams,mailingContent};

