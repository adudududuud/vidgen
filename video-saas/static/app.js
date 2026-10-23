const form=document.getElementById('download-form');
const error=document.getElementById('form-error');
const submit=document.getElementById('submit-btn');
const box=document.getElementById('task-box');
const label=document.getElementById('task-label');
const status=document.getElementById('task-status');
const caption=document.getElementById('progress-caption');
const percent=document.getElementById('progress-percent');
const fill=document.getElementById('progress-fill');
const message=document.getElementById('task-message');
const fileLink=document.getElementById('download-file');
const cancelButton=document.getElementById('cancel-task');
const retryButton=document.getElementById('retry-task');
let poller=null;
let activeJob=null;
const stateKey='video-saas-last-job';
function showError(text){error.textContent=text;error.hidden=false;}
function clearError(){error.textContent='';error.hidden=true;}
async function jsonResponse(res){let data={};try{data=await res.json();}catch{}if(!res.ok){let msg=data.detail||`请求失败（${res.status}）`;if(Array.isArray(msg))msg='请检查输入的链接与授权确认';throw Error(msg);}return data;}
function showTask(jobId,token){clearInterval(poller);activeJob={job_id:jobId,access_token:token};box.hidden=false;box.scrollIntoView({behavior:'smooth',block:'center'});fileLink.hidden=true;cancelButton.hidden=true;retryButton.hidden=true;refreshTask(jobId,token);poller=setInterval(()=>refreshTask(jobId,token),1800);}
async function refreshTask(jobId,token){try{const j=await jsonResponse(await fetch(`/api/jobs/${encodeURIComponent(jobId)}`,{headers:{'X-Job-Token':token},cache:'no-store'}));const labels={queued:'排队中',running:'正在处理',done:'处理完成',error:'处理失败',cancelled:'已取消'};status.textContent=j.cancel_requested&&j.status==='running'?'正在取消':(labels[j.status]||j.status);label.textContent=j.status==='done'?'视频已经准备好了':j.status==='error'?'任务未完成':j.status==='cancelled'?'任务已取消':'正在为您处理视频';percent.textContent=`${j.progress}%`;fill.style.width=`${j.progress}%`;caption.textContent=j.status==='running'?(j.cancel_requested?'正在停止下载器…':'正在获取并整理素材…'):(labels[j.status]||'等待处理');cancelButton.hidden=!(j.status==='queued'||j.status==='running');cancelButton.disabled=Boolean(j.cancel_requested);retryButton.hidden=!(j.status==='error'||j.status==='cancelled');if(j.status==='done'){message.textContent='文件可在限定时间内下载，请及时保存。';fileLink.hidden=false;fileLink.href=`/api/files/${encodeURIComponent(jobId)}?token=${encodeURIComponent(token)}`;fileLink.setAttribute('download',j.filename||'video');clearInterval(poller);submit.disabled=false;}else if(j.status==='error'){message.textContent=j.error||'处理失败，请稍后再试';fileLink.hidden=true;clearInterval(poller);submit.disabled=false;}else if(j.status==='cancelled'){message.textContent='任务已取消。你可以重新提交或点击“重试任务”。';fileLink.hidden=true;clearInterval(poller);submit.disabled=false;}else if(j.cancel_requested){message.textContent='已收到取消请求，正在等待下载器停止。';}else{message.textContent='任务运行中。可以取消任务，或等待处理完成。';}}catch(e){clearInterval(poller);message.textContent=e.message;submit.disabled=false;}}
form.addEventListener('submit',async e=>{e.preventDefault();clearError();submit.disabled=true;submit.textContent='正在提交…';try{const data=await jsonResponse(await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:document.getElementById('video-url').value.trim(),confirmed_rights:document.getElementById('rights').checked})}));sessionStorage.setItem(stateKey,JSON.stringify(data));showTask(data.job_id,data.access_token);}catch(e){showError(e.message);submit.disabled=false;}finally{submit.textContent='开始处理 →';}});
cancelButton.addEventListener('click',async()=>{if(!activeJob)return;cancelButton.disabled=true;try{const result=await jsonResponse(await fetch(`/api/jobs/${encodeURIComponent(activeJob.job_id)}/cancel`,{method:'POST',headers:{'X-Job-Token':activeJob.access_token}}));message.textContent=result.message||'已请求取消任务';await refreshTask(activeJob.job_id,activeJob.access_token);}catch(e){message.textContent=e.message;cancelButton.disabled=false;}});
retryButton.addEventListener('click',async()=>{if(!activeJob)return;retryButton.disabled=true;try{const data=await jsonResponse(await fetch(`/api/jobs/${encodeURIComponent(activeJob.job_id)}/retry`,{method:'POST',headers:{'Content-Type':'application/json','X-Job-Token':activeJob.access_token},body:JSON.stringify({confirmed_rights:document.getElementById('rights').checked})}));sessionStorage.setItem(stateKey,JSON.stringify(data));showTask(data.job_id,data.access_token);}catch(e){message.textContent=e.message;}finally{retryButton.disabled=false;}});
try{const last=JSON.parse(sessionStorage.getItem(stateKey)||'null');if(last?.job_id&&last?.access_token)showTask(last.job_id,last.access_token);}catch{}
(async()=>{try{const data=await jsonResponse(await fetch('/api/config'));document.getElementById('limit-info').textContent=`每日免费额度：${data.daily_limit} 次 · 文件上限 ${data.max_mb} MB`;if(data.adsense_enabled){const area=document.getElementById('ads-area');area.hidden=false;const script=document.createElement('script');script.async=true;script.crossOrigin='anonymous';script.src=`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${encodeURIComponent(data.adsense_client)}`;document.head.appendChild(script);const ins=document.createElement('ins');ins.className='adsbygoogle';ins.style.display='block';ins.dataset.adClient=data.adsense_client;ins.dataset.adSlot=data.adsense_slot;ins.dataset.adFormat='auto';ins.dataset.fullWidthResponsive='true';document.getElementById('ad-slot').appendChild(ins);script.onload=()=>{(window.adsbygoogle=window.adsbygoogle||[]).push({});};}}catch{}})();


async function loadAccountJobs(){
  const section=document.getElementById('account-jobs');
  const list=document.getElementById('account-jobs-list');
  if(section.hidden)return;
  try{
    const data=await jsonResponse(await fetch('/api/me/jobs?limit=30',{cache:'no-store'}));
    list.replaceChildren();
    if(!data.jobs.length){const empty=document.createElement('p');empty.className='muted';empty.textContent='登录后提交的任务会显示在这里。';list.appendChild(empty);return;}
    const labels={queued:'排队中',running:'处理中',done:'已完成',error:'失败',cancelled:'已取消'};
    for(const job of data.jobs){
      const card=document.createElement('article');card.className='account-job';
      const info=document.createElement('div');info.className='account-job-info';
      const heading=document.createElement('strong');heading.textContent=`${labels[job.status]||job.status} · ${job.progress}%`;info.appendChild(heading);
      const source=document.createElement('a');source.href=job.source_url;source.target='_blank';source.rel='noopener noreferrer';source.textContent=job.source_url;source.className='account-job-source';info.appendChild(source);
      const date=document.createElement('small');date.textContent=new Date(job.created_at*1000).toLocaleString('zh-CN');info.appendChild(date);
      if(job.error){const err=document.createElement('small');err.textContent=job.error;err.className='account-job-error';info.appendChild(err);}
      card.appendChild(info);const actions=document.createElement('div');actions.className='account-job-actions';
      if(job.status==='queued'||job.status==='running'){
        const cancel=document.createElement('button');cancel.className='small-button';cancel.textContent=job.cancel_requested?'正在取消…':'取消';cancel.disabled=Boolean(job.cancel_requested);
        cancel.addEventListener('click',async()=>{try{await jsonResponse(await fetch(`/api/jobs/${encodeURIComponent(job.id)}/cancel`,{method:'POST'}));await loadAccountJobs();if(activeJob?.job_id===job.id)await refreshTask(job.id,activeJob.access_token);}catch(e){alert(e.message);}});actions.appendChild(cancel);
      }
      if(job.status==='error'||job.status==='cancelled'){
        const retry=document.createElement('button');retry.className='small-button';retry.textContent='重试';
        retry.addEventListener('click',async()=>{if(!confirm('请确认你拥有该视频的下载权利或已取得授权。继续重试？'))return;try{const result=await jsonResponse(await fetch(`/api/jobs/${encodeURIComponent(job.id)}/retry`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmed_rights:true})}));sessionStorage.setItem(stateKey,JSON.stringify(result));showTask(result.job_id,result.access_token);await loadAccountJobs();}catch(e){alert(e.message);}});actions.appendChild(retry);
      }
      if(job.status==='done'){
        const download=document.createElement('a');download.className='small-button';download.href=`/api/files/${encodeURIComponent(job.id)}`;download.textContent='下载';actions.appendChild(download);
      }
      card.appendChild(actions);list.appendChild(card);
    }
  }catch(e){list.textContent=e.message;}
}

async function refreshAccountUI(){
  try{
    const me=await jsonResponse(await fetch('/api/me',{cache:'no-store'}));
    const login=document.getElementById('google-login');const statusTag=document.getElementById('account-status');const logout=document.getElementById('google-logout');const section=document.getElementById('account-jobs');
    login.hidden=!me.google_oauth_enabled||me.authenticated;
    statusTag.hidden=!me.authenticated;statusTag.textContent=me.authenticated?(me.user.name||me.user.email):'';
    logout.hidden=!me.authenticated;section.hidden=!me.authenticated;
    if(me.authenticated)await loadAccountJobs();
  }catch{}
}
document.getElementById('google-logout').addEventListener('click',async()=>{await fetch('/api/me/logout',{method:'POST'});await refreshAccountUI();});
document.getElementById('refresh-account-jobs').addEventListener('click',loadAccountJobs);
refreshAccountUI();
