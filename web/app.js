const stageNames=["research","intelligence","opportunity","strategy","script","production"];

function showToast(message){
  const t=document.getElementById("toast");
  t.textContent=message;
  t.className="show";
  setTimeout(()=>t.className="",2600);
}

function setStageState(completed,current,status){
  document.querySelectorAll("[data-stage]").forEach(el=>{
    const name=el.dataset.stage;
    el.classList.remove("done","active");
    if(completed.includes(name)) {
      el.classList.add("done");
      el.querySelector("b").textContent="✓";
    } else {
      const index=stageNames.indexOf(name);
      el.querySelector("b").textContent=String(index+1).padStart(2,"0");
    }
    if(name===current) el.classList.add("active");
  });
  const pill=document.getElementById("run-pill");
  pill.textContent=status==="running"?"RUNNING":status==="failed"?"FAILED":"READY";
  pill.className="pill "+(status==="running"?"live":status==="failed"?"review":"live");
}

function renderOpportunities(items){
  const list=document.getElementById("opportunity-list");
  if(!items || !items.length){
    list.innerHTML='<div class="panel" style="padding:20px"><p class="muted">No opportunities yet. Run Overseer to generate the first queue.</p></div>';
    return;
  }
  list.innerHTML=items.slice(0,8).map((item,index)=>`
    <article class="opportunity ${index===0?"featured":""}">
      <div class="score">${item.score}</div>
      <div class="opp-main">
        <div class="tags"><span>${item.score>=80?"HIGH PRIORITY":"RESEARCH SIGNAL"}</span><span>RELATIVE SCORE</span></div>
        <h3>${escapeHtml(item.topic)}</h3>
        <p>${escapeHtml(item.angle)}</p>
        <div class="evidence"><span>Demand ${item.demand}</span><span>Audience ${item.audience_fit}</span><span>Gap ${item.competition_gap}</span><span>Intent ${item.business_intent}</span></div>
      </div>
      <button class="icon-btn" onclick="approveIdea(this)">→</button>
    </article>`).join("");
}

function escapeHtml(value){
  return String(value).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[c]));
}

function render(state){
  document.getElementById("sources-count").textContent=state.research_count ?? 0;
  document.getElementById("opportunity-count").textContent=state.opportunity_count ?? 0;
  document.getElementById("run-time").textContent=state.completed_at?"Completed":"Not started";
  document.getElementById("run-title").textContent=state.status==="running"?"Overseer is working":"Ready for a run";
  document.getElementById("run-cost").textContent="API";
  setStageState(state.completed_steps||[],state.current_step,state.status);
  renderOpportunities(state.opportunities||[]);
  if(state.errors?.length) showToast(state.errors[0]);
}

async function refresh(){
  try{
    const response=await fetch("/api/status",{cache:"no-store"});
    if(!response.ok) throw new Error("Status request failed");
    render(await response.json());
  }catch(error){
    document.getElementById("runtime-status").innerHTML="<i></i> Local runtime offline";
  }
}

async function runAgent(){
  try{
    const response=await fetch("/api/run",{method:"POST"});
    const data=await response.json();
    if(!response.ok) throw new Error(data.message||"Could not start Overseer");
    showToast("Overseer run started");
    await refresh();
  }catch(error){
    showToast(error.message);
  }
}

function approveIdea(btn){
  btn.textContent="✓";
  btn.style.background="var(--accent)";
  btn.style.color="#111";
  showToast("Opportunity marked for review");
}

function approveVideo(){
  showToast("Human approval recorded — publishing remains gated");
}

refresh();
setInterval(refresh,2000);
