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
  pill.textContent=status==="running"?"RUNNING":status==="failed"?"FAILED":status==="completed"?"COMPLETE":"READY";
  pill.className="pill "+(status==="running"?"live":status==="failed"?"review":"live");
}

function renderOpportunities(items){
  const list=document.getElementById("opportunity-list");
  if(!items || !items.length){
    list.innerHTML='<div class="panel" style="padding:20px"><p class="muted">No opportunities yet. Run Overseer to generate the first evidence-based queue.</p></div>';
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

function renderChannelProfiles(profiles){
  const box=document.getElementById("channel-profiles");
  if(!box) return;

  if(!profiles || !profiles.length){
    box.innerHTML="";
    return;
  }

  box.innerHTML=profiles.map(p=>`
    <div class="channel-profile">
      <strong>${escapeHtml(p.title || "Untitled channel")}</strong>
      <span>${Number(p.subscriber_count||0).toLocaleString()} subscribers · ${Number(p.video_count||0).toLocaleString()} videos</span>
    </div>`).join("");
}

function renderResearchTerritory(territory){
  const box=document.getElementById("research-territory");
  if(!box) return;

  if(!territory){
    box.innerHTML=`
      <div class="territory-empty">
        <span class="field-label">Research territory</span>
        <strong>Waiting for reference-channel evidence</strong>
        <p class="muted small">After a run, Overseer will show the territory it inferred, its confidence, and the evidence used.</p>
      </div>`;
    return;
  }

  const subTerritories=(territory.sub_territories||[]).map(item=>
    `<span class="territory-tag">${escapeHtml(item)}</span>`
  ).join("");

  const evidence=(territory.evidence||[]).map(item=>
    `<li>${escapeHtml(item)}</li>`
  ).join("");

  box.innerHTML=`
    <div class="territory-head">
      <div>
        <span class="field-label">Research territory</span>
        <h3>${escapeHtml(territory.label || "Reference-channel territory")}</h3>
      </div>
      <span class="confidence ${escapeHtml(territory.confidence||"unrated")}">${escapeHtml(String(territory.confidence||"unrated").toUpperCase())} CONFIDENCE</span>
    </div>
    ${subTerritories ? `<div class="territory-tags">${subTerritories}</div>` : ""}
    ${territory.audience ? `<p class="territory-audience"><strong>Observed audience:</strong> ${escapeHtml(territory.audience)}</p>` : ""}
    ${evidence ? `<div class="territory-evidence"><span class="field-label">Evidence used</span><ul>${evidence}</ul></div>` : ""}
  `;
}

function render(state){
  document.getElementById("sources-count").textContent=state.research_count ?? 0;
  document.getElementById("opportunity-count").textContent=state.opportunity_count ?? 0;
  document.getElementById("signals-count").textContent=state.research_count ? "Active" : "—";
  document.getElementById("run-cost").textContent="API";
  document.getElementById("run-time").textContent=state.completed_at
    ? new Date(state.completed_at).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"})
    : "Not started";

  renderChannelProfiles(state.channel_profiles||[]);
  renderResearchTerritory(state.research_territory);
  setStageState(state.completed_steps||[],state.current_step,state.status);
  renderOpportunities(state.opportunities||[]);

  const territory=state.research_territory?.label;
  document.getElementById("run-title").textContent=state.status==="running"
    ? "Studying reference channels and inferring territory"
    : state.status==="failed"
      ? "Research run needs attention"
      : territory
        ? `Research territory: ${territory}`
        : "Ready for a research run";

  if(state.status==="failed" && state.errors?.length) {
    showToast(state.errors[state.errors.length-1]);
  }
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

function selectedChannels(){
  const input=document.getElementById("channels-input");
  if(!input) return [];
  return input.value.split(/\r?\n/).map(v=>v.trim()).filter(Boolean);
}

async function runAgent(){
  const channels=selectedChannels();

  if(!channels.length){
    showToast("Add at least one reference YouTube channel");
    return;
  }

  try{
    const response=await fetch("/api/run",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({
        mode:"channel_intelligence",
        channels
      })
    });

    const data=await response.json();
    if(!response.ok) throw new Error(data.message||"Could not start Overseer");

    showToast("Studying reference channels…");
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

document.addEventListener("DOMContentLoaded", () => {
  const button = document.getElementById("run-agent");
  if(button) button.addEventListener("click", runAgent);
  refresh();
  setInterval(refresh,2000);
});
