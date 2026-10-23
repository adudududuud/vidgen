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
let poller=null;
const stateKey='video-saas-last-job';
function showError(text){error.textContent=text;error.hidden=false;}
function clearError(){error.textContent='';error.hidden=true;}
async function jsonResponse(res){let data={};try{data=await res.json();}catch{}if(!res.ok){let msg=data.detail||`请求失败（${res.status}）`;if(Array.isArray(msg))msg='请检查输入的链接与授权确认';throw Error(msg);}return data;}
function showTask(jobId,token){box.hidden=false;box.scrollIntoView({behavior:'smooth',block:'center'});fileLink.hidden=true;refreshTask(jobId,token);clearInterval(poller);poller=setInterval(()=>refreshTask(jobId,token),1800);}
async function refreshTask(jobId,token){try{const j=await jsonResponse(await fetch(`/api/jobs/${encodeURIComponent(jobId)}`,{headers:{'X-Job-Token':token},cache:'no-store'}));const labels={queued:'排队中',running:'正在处理',done:'处理完成',error:'处理失败'};status.textContent=labels[j.status]||j.status;label.textContent=j.status==='done'?'视频已经准备好了':j.status==='error'?'任务未完成':'正在为您处理视频';percent.textContent=`${j.progress}%`;fill.style.width=`${j.progress}%`;caption.textContent=j.status==='running'?'正在获取并整理素材…':labels[j.status]||'等待处理';if(j.status==='done'){message.textContent='文件可在限定时间内下载，请及时保存。';fileLink.hidden=false;fileLink.href=`/api/files/${encodeURIComponent(jobId)}?token=${encodeURIComponent(token)}`;fileLink.setAttribute('download',j.filename||'video');clearInterval(poller);submit.disabled=false;}if(j.status==='error'){message.textContent=j.error||'处理失败，请稍后再试';fileLink.hidden=true;clearInterval(poller);submit.disabled=false;}}catch(e){clearInterval(poller);message.textContent=e.message;submit.disabled=false;}}
form.addEventListener('submit',async e=>{e.preventDefault();clearError();submit.disabled=true;submit.textContent='正在提交…';try{const data=await jsonResponse(await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:document.getElementById('video-url').value.trim(),confirmed_rights:document.getElementById('rights').checked})}));sessionStorage.setItem(stateKey,JSON.stringify(data));showTask(data.job_id,data.access_token);}catch(e){showError(e.message);submit.disabled=false;}finally{submit.textContent='开始处理 →';}});
try{const last=JSON.parse(sessionStorage.getItem(stateKey)||'null');if(last?.job_id&&last?.access_token)showTask(last.job_id,last.access_token);}catch{}
(async()=>{try{const data=await jsonResponse(await fetch('/api/config'));document.getElementById('limit-info').textContent=`每日免费额度：${data.daily_limit} 次 · 文件上限 ${data.max_mb} MB`;if(data.adsense_enabled){const area=document.getElementById('ads-area');area.hidden=false;const script=document.createElement('script');script.async=true;script.crossOrigin='anonymous';script.src=`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${encodeURIComponent(data.adsense_client)}`;document.head.appendChild(script);const ins=document.createElement('ins');ins.className='adsbygoogle';ins.style.display='block';ins.dataset.adClient=data.adsense_client;ins.dataset.adSlot=data.adsense_slot;ins.dataset.adFormat='auto';ins.dataset.fullWidthResponsive='true';document.getElementById('ad-slot').appendChild(ins);script.onload=()=>{(window.adsbygoogle=window.adsbygoogle||[]).push({});};}}catch{}})();
