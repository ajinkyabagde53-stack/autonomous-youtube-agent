function showToast(message){const t=document.getElementById('toast');t.textContent=message;t.className='show';setTimeout(()=>t.className='',2200)}
function runAgent(){showToast('Agent run queued — cloud orchestration starting')}
function approveIdea(btn){btn.textContent='✓';btn.style.background='var(--accent)';btn.style.color='#111';showToast('Opportunity moved to strategy queue')}
function approveVideo(){showToast('Human approval recorded — publishing remains gated')}
