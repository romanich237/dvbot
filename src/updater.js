'use strict';
const fs=require('node:fs');const os=require('node:os');const path=require('node:path');
const entries=['src','public','package.json','package-lock.json','ecosystem.config.cjs','README.md'];
function validateSource(source){
 const pkg=JSON.parse(fs.readFileSync(path.join(source,'package.json'),'utf8'));
 if(pkg.main!=='src/main.js' || !pkg.scripts?.check || !fs.existsSync(path.join(source,'src/main.js')))throw new Error('Репозиторий не содержит совместимую JavaScript-сборку dvbot.');
 function check(file){const stat=fs.lstatSync(file);if(stat.isSymbolicLink())throw new Error('Символические ссылки в обновлении не поддерживаются.');if(stat.isDirectory())for(const name of fs.readdirSync(file))check(path.join(file,name));else if(!stat.isFile())throw new Error('Недопустимый файл в обновлении.');}
 for(const name of entries){const file=path.join(source,name);if(fs.existsSync(file))check(file);}
 return pkg;
}
async function installUpdate(root,github,command){
 if(!/^[\w.-]+\/[\w.-]+$/.test(github.repository) || !/^[\w./-]+$/.test(github.branch) || github.branch.startsWith('-'))throw new Error('Неверный репозиторий или ветка.');
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'dvbot-update-')),source=path.join(temp,'source'),backup=path.join(temp,'backup');
 const env={...process.env,GIT_TERMINAL_PROMPT:'0'};let replaced=false;
 try{
  await command('git',['-c','credential.interactive=false','clone','--depth','1','--single-branch','--branch',github.branch,`https://github.com/${github.repository}.git`,source],{env,timeout:120000});
  const pkg=validateSource(source);
  await command('npm',['ci','--no-audit','--no-fund'],{cwd:source,timeout:300000});
  await command('npm',['run','check'],{cwd:source});
  fs.mkdirSync(backup);
  for(const name of entries)if(fs.existsSync(path.join(root,name)))fs.cpSync(path.join(root,name),path.join(backup,name),{recursive:true});
  replaced=true;
  for(const name of entries){const target=path.join(root,name);fs.rmSync(target,{recursive:true,force:true});if(fs.existsSync(path.join(source,name)))fs.cpSync(path.join(source,name),target,{recursive:true});}
  await command('npm',['ci','--no-audit','--no-fund'],{timeout:300000});
  await command('npm',['run','check']);
  return pkg.version;
 }catch(error){
  if(replaced){for(const name of entries){fs.rmSync(path.join(root,name),{recursive:true,force:true});if(fs.existsSync(path.join(backup,name)))fs.cpSync(path.join(backup,name),path.join(root,name),{recursive:true});}await command('npm',['ci','--no-audit','--no-fund'],{timeout:300000}).catch(()=>{});}
  throw error;
 }finally{fs.rmSync(temp,{recursive:true,force:true});}
}
module.exports={installUpdate,validateSource};
