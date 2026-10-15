'use strict';
let sharp;
try{sharp=require('sharp');}catch{}
const MAX_INPUT=20*1024*1024;
function settings(config={}){
  return {enabled:config.enabled!==false,maxWidth:Number.isInteger(config.maxWidth)?Math.min(4096,Math.max(320,config.maxWidth)):1600,maxHeight:Number.isInteger(config.maxHeight)?Math.min(4096,Math.max(320,config.maxHeight)):1600,quality:Number.isInteger(config.quality)?Math.min(95,Math.max(40,config.quality)):80};
}
async function compressPhoto(buffer,config){
  const options=settings(config);
  if(!options.enabled || !sharp)return {buffer,compressed:false};
  if(!buffer.length || buffer.length>MAX_INPUT)throw new Error('Фото должно быть не больше 20 МБ.');
  const image=sharp(buffer,{limitInputPixels:40000000,failOn:'error'});
  const metadata=await image.metadata();
  if(!['jpeg','png','webp'].includes(metadata.format))throw new Error('Фото должно быть JPEG, PNG или WebP.');
  const resize=metadata.width>options.maxWidth || metadata.height>options.maxHeight;
  const output=await image.rotate().resize(options.maxWidth,options.maxHeight,{fit:'inside',withoutEnlargement:true}).flatten({background:'#ffffff'}).jpeg({quality:options.quality,mozjpeg:true}).toBuffer();
  if(!resize && output.length>=buffer.length)return {buffer,compressed:false};
  return {buffer:output,compressed:true};
}
async function readPhoto(response){
  if(!response.ok)throw new Error('Не удалось получить фото.');
  const chunks=[];let size=0;
  for await(const chunk of response.body){size+=chunk.length;if(size>MAX_INPUT)throw new Error('Фото больше 20 МБ.');chunks.push(chunk);}
  return Buffer.concat(chunks);
}
module.exports={compressPhoto,readPhoto,available:!!sharp};
