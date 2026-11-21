"use strict";
const $ = (s) => document.querySelector(s);
const labels = {video:"Видео", image:"Изображения", mixed:"Видео и фото", strategy:"Стратегия и обучение"};
const aiLabels = {generation:"AI-генерация", partial:"AI частично", none:"Без AI", unset:"AI не размечен"};
const statuses = {applied:"Отклик отправлен", closed:"Заказ закрыт", reserve:"В резерве", skip:"Низкий приоритет"};
const icons = {
  video:'<rect x="2" y="4" width="15" height="16" rx="2"/><path d="m17 10 5-3v10l-5-3z"/>',
  image:'<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="1.5"/><path d="m3 17 5-5 4 4 3-4 6 6"/>',
  mixed:'<rect x="3" y="5" width="16" height="15" rx="2"/><path d="m9 9 5 3-5 3zM7 2h14"/>',
  strategy:'<path d="M3 7h9l3 3h6v9H3zM7 3h9l3 4"/>'
};
let projects = [], kind = "all", ai = "all", loaded = false, warning = false, fetching = false, lastFocus = null;
let reviewUntil = 0;
const dialog = $("#detail");
function elem(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = text;
  return node;
}
function chip(p) {
  const type = Object.hasOwn(icons,p.kind) ? p.kind : "mixed";
  const tag = elem("span","tag "+type);
  const icon = document.createElementNS("http://www.w3.org/2000/svg","svg");
  icon.setAttribute("viewBox","0 0 24 24"); icon.setAttribute("class","ico"); icon.setAttribute("aria-hidden","true");
  icon.innerHTML = icons[type];
  tag.append(icon,labels[type]); return tag;
}
function aiRole(p) {return ["generation","partial","none"].includes(p.aiRole) ? p.aiRole : "unset";}
function tags(p) {
  const box = elem("span","tags"), role = aiRole(p);
  const mark = elem("span","tag ai-"+role,aiLabels[role]);
  if (p.aiNote) mark.title = p.aiNote;
  box.append(chip(p),mark); return box;
}
function kindMatches(p) {
  return kind==="all" || p.kind===kind || (p.kind==="mixed" && (kind==="video" || kind==="image"));
}
function score(p) {
  const el = elem("span","score");
  if (Number.isFinite(p.score)) {
    el.append(elem("b","",p.score+" / 100"));
    el.title = "Соответствие по шести критериям подборки";
    el.setAttribute("aria-label","Оценка соответствия "+p.score+" из 100");
  }
  return el;
}
function stamp(value) {
  return new Intl.DateTimeFormat("ru-RU",{timeZone:"Europe/Kyiv",day:"numeric",month:"short",hour:"2-digit",minute:"2-digit"}).format(new Date(value));
}
function payment(p) {return p.payment === "hourly" ? "Почасовая оплата" : "Фиксированная оплата";}
const marketLabels = {open:"Подача доступна", closed:"Заказ закрыт", unavailable:"Подача недоступна", unknown:"Требует проверки", applied:"Отклик отправлен"};
const terminalStates = new Set(["CLOSED", "FILLED", "CANCELLED", "CANCELED", "EXPIRED", "COMPLETED"]);
function market(p) {
  const a = p.availability;
  if (p.status === "applied" || a?.applied === true) return "applied";
  if (!a?.state) return "unknown";
  if (terminalStates.has(a.state)) return "closed";
  if (p.status === "closed" && new Date(p.statusChecked || p.checked) > new Date(a.at)) return "closed";
  if (a.canApply === false) return "unavailable";
  return a.state === "ACTIVE" && a.canApply === true ? "open" : "unknown";
}
function recommended(p) {
  return !!p.applicationPlan && market(p) === "open" && Date.now() < reviewUntil;
}
function marketText(p) {
  const a=p.availability;
  let text=marketLabels[market(p)];
  if (a?.state && market(p)==="applied") text += a.state==="ACTIVE" ? " · Заказ активен" : terminalStates.has(a.state) ? " · Заказ закрыт" : " · " + a.state;
  if (a?.at) text += " · " + stamp(a.at);
  if (Number.isInteger(a?.cost) && market(p)==="open") text += " · " + a.cost + " Connects";
  return text;
}
function addPlan(container, plan) {
  container.append(section("Почему стоит откликнуться",[plan.reason]), section("Что хочет клиент",[plan.brief]));
  const offer=section("Предложение по оплате и срокам",[plan.pricing]);
  container.append(offer);
  const letter=section("Cover Letter",[plan.letter]);
  letter.classList.add("application-copy");
  const copy=elem("button","plain","Скопировать Cover Letter");
  copy.type="button"; copy.addEventListener("click",async()=>{
    try{await navigator.clipboard.writeText(plan.letter);copy.textContent="Скопировано";}catch{copy.textContent="Выделите текст выше";}
  });letter.append(copy);container.append(letter);
  if(plan.answers?.length)container.append(section("Ответы для формы",plan.answers));
  if(plan.sample)container.append(section("Что приложить",[plan.sample]));
  container.append(section("Демо для этого клиента",[plan.demo,plan.check]));
  const refs=section("Региональные референсы",[]);
  for(const ref of plan.refs||[]){const line=elem("p","",ref.use+" ");const a=elem("a","plain",ref.name);a.href=ref.url;a.target="_blank";a.rel="noopener noreferrer";line.append(a);refs.append(line);}
  container.append(refs);
}
function buildCard(p) {
  const card = elem("article","card"), head = elem("div","mt"), h = elem("h3");
  head.append(tags(p),score(p));
  const button = elem("button","",p.title); button.type="button"; button.setAttribute("aria-haspopup","dialog");
  button.addEventListener("click",()=>{lastFocus=button; location.hash="project-"+p.id;});
  h.append(button);
  const meta = elem("p","meta",[p.client,p.country].filter(Boolean).join(" · "));
  const bottom = elem("div","cardbottom"), budget = elem("div","budget");
  budget.append(elem("strong","",p.budget),elem("small","",payment(p)));
  const go = elem("span","go","↗"); go.setAttribute("aria-hidden","true"); bottom.append(budget,go);
  card.append(head,h,meta);
  card.append(elem("p","audit-status",marketText(p)));
  if (recommended(p)) card.append(elem("span","st","Приоритет " + p.applicationPlan.rank + " · ближайшие 12 ч"));
  else if (["reserve","skip"].includes(p.status) && market(p)==="unknown") card.append(elem("span","st",statuses[p.status]));
  if(p.originalDescription?.quality === "excerpt") card.append(elem("p","carddate","Сохранён фрагмент описания клиента"));
  else if(p.reviewLevel === "search_excerpt" && !p.applicationPlan) card.append(elem("p","carddate","Условия заказа проверены только по поисковой выдаче"));
  card.append(elem("p","excerpt",p.description),elem("p","carddate","Бриф сохранён "+stamp(p.checked)+(Date.now()-new Date(p.checked).getTime()>48*3600000?" · Архив":"")),bottom);
  const practice = elem("a","practice-link","Разбор и идея демо →"); practice.href="./practice.html?project="+p.id; card.append(practice);
  return card;
}
function ageMatches(p, value) {
  if(value==="all")return true;
  const pub=value.startsWith("published-");
  const date=pub?p.publishedAt:((p.availability?.state && p.availability.at)||p.checked);
  if(!date)return false;
  return (value==="archive" || value==="published-old") === (Date.now()-Date.parse(date)>48*3600000);
}
function matches(p,q) {
  const choice=$("#availability").value;
  if (choice && !(choice==="priority" ? recommended(p) : choice==="closed" ? market(p)==="closed" || terminalStates.has(p.availability?.state) : market(p)===choice)) return false;
  const haystack=[marketText(p),p.title,p.original,p.client,p.country,p.description,p.about,p.tasks.join(" "),p.status && statuses[p.status]].filter(Boolean).join(" ").toLocaleLowerCase("ru");
  return kindMatches(p)
    && (ai==="all" || aiRole(p)===ai)
    && ageMatches(p,$("#age").value)
    && (!$("#pay").value || p.payment===$("#pay").value)
    && q.split(/\s+/).filter(Boolean).every(w=>haystack.includes(w));
}
function render() {
  const filtered=projects.filter(p=>matches(p,$("#query").value.trim().toLocaleLowerCase("ru")));
  filtered.sort(compareProjects);
  $("#grid").replaceChildren(...filtered.map(buildCard));
  $("#total").textContent=projects.length;
  const base={all:"Любая",...aiLabels,unset:"Не размечено"}, inKind=projects.filter(kindMatches);
  for(const b of document.querySelectorAll("button[data-ai]")) {
    const n=b.dataset.ai==="all" ? inKind.length : inKind.filter(p=>aiRole(p)===b.dataset.ai).length;
    b.textContent=base[b.dataset.ai]+" · "+n;
    if(b.dataset.ai==="unset") b.hidden=!projects.some(p=>aiRole(p)==="unset");
  }
  $("#result").textContent="Показано проектов: "+filtered.length+" из "+projects.length;
  $("#empty").hidden=!!filtered.length;
  $("#reset").hidden=!projects.length;
  $("#empty-title").textContent=projects.length?"Совпадений нет":warning?"Не удалось загрузить подборку":"Архив пока пуст";
  $("#empty-body").textContent=projects.length?"Попробуйте другое слово или сбросьте фильтры.":warning?"Обновите страницу, когда локальный сервер будет доступен.":"Здесь появятся проекты из следующей подборки Upwork.";
}
function section(title,paragraphs,cls="") {
  const el=elem("section","detailsection "+cls);
  el.append(elem("h3","",title));
  for (const text of paragraphs.filter(Boolean)) el.append(elem("p","",text));
  return el;
}
function showDetail(p) {
  const head=elem("div","mt"), title=elem("h2","",p.title);
  head.append(tags(p),score(p)); title.id="detail-title";
  const facts=elem("div","facts");
  for(const fact of [p.budget, payment(p),marketText(p)]) {
    if(fact) facts.append(elem("span","",fact));
  }
  const brief=section("Что нужно сделать",[p.description]);
  const list=elem("ul");
  for(const task of p.tasks) list.append(elem("li","",task));
  brief.append(list);
  const customer=section("О клиенте на дату сохранения брифа",[[p.client,p.country].filter(Boolean).join(" · "),p.about,p.history,p.activity]);
  const unknownBudget = p.payment === "hourly" && p.paidScopeConfirmed !== true;
  const pay=section("Условия и риски на дату сохранения брифа",[unknownBudget?"Общий бюджет не подтверждён. "+p.budget+".":null,p.risk]);
  const questions=section("Что уточнить у клиента",[p.question],"question");
  const aiPart=section("Роль AI в заказе",[aiLabels[aiRole(p)]+(p.aiNote?" · "+p.aiNote:"")]);
  const dates=elem("p","original","Данные сохранены на "+stamp(p.checked)+" по Киеву"+(p.published?" · Опубликовано "+p.published+" по Киеву":""));
  const inside=$("#inside");
  inside.replaceChildren(head,title,elem("p","original",p.original),facts,dates,originalBrief(p),brief,aiPart,customer,pay,questions);
  const a=p.availability;
  if(a?.state){
    const activity=[["Наймов",a.hires],["Интервью",a.interviews],["Офферов",a.offers],["Приглашений",a.invites]].filter(([,v])=>v!=null).map(([k,v])=>k+" "+v);
    inside.append(section("Проверка на Upwork",[marketText(p),activity.join(" · ")]));
  } else if(a?.at){inside.append(section("Проверка на Upwork",[(a.error==="PERMISSION" ? "У этого аккаунта нет доступа к карточке. Это не подтверждает закрытие." : a.error==="UPSTREAM" ? "Upwork вернул ошибку при чтении. Это не подтверждает закрытие." : "Upwork не вернул подтверждённый статус.")+" Проверено "+stamp(a.at)]));}
  if(p.reviewNote && !p.applicationPlan) inside.append(section("Решение на ближайшие 12 часов",[p.reviewNote]));
  if (p.applicationPlan) {
    inside.append(section("Подготовка отклика",["План составлен на период до "+stamp(reviewUntil)+" по Киеву."]));
    const jump=elem("button","plain","К Cover Letter, цене и демо ↓");jump.type="button";facts.after(jump);
    addPlan(inside,p.applicationPlan);jump.addEventListener("click",()=>inside.querySelector(".application-copy").scrollIntoView({block:"start"}));
  }
  const practiceLink=elem("a","solid","Разбор и план практики →");practiceLink.href="./practice.html?project="+p.id;inside.append(practiceLink);
  $("#source").href=p.url;
  if (!dialog.open) {dialog.showModal(); $("#close").focus();}
  dialog.scrollTop=0;
}
function syncHash() {
  const id=location.hash.match(/^#project-(\d+)$/)?.[1];
  const p=projects.find(p=>p.id===id);
  if (p) {showDetail(p);return;}
  if(id && loaded) history.replaceState(null,"",location.pathname+location.search);
  if(dialog.open) dialog.close();
}
function closeDetail() {
  history.replaceState(null,"",location.pathname+location.search);
  if(dialog.open) dialog.close();
}
function sortKey(p) {
  if(recommended(p)) return 0;
  return {open:1,unknown:2,applied:3,unavailable:4,closed:5}[market(p)];
}
function compareProjects(a,b) {
  const mode=$("#order").value;
  const byScore=(Number.isFinite(b.score)?b.score:-1)-(Number.isFinite(a.score)?a.score:-1);
  const byTime=(b.availability?.at||"").localeCompare(a.availability?.at||"");
  const seen=p=>Date.parse(p.publishedAt||p.firstSeen||p.checked)||0;
  if(mode==="new")return (seen(b)-seen(a))||byScore;
  if(mode==="check")return byTime||byScore;
  if(mode==="score")return byScore||byTime;
  if(mode==="cost"){
    const cost=p=>market(p)==="open" && Number.isInteger(p.availability?.cost)?p.availability.cost:Infinity;
    return (cost(a)-cost(b))||byScore||byTime;
  }
  return sortKey(a)-sortKey(b) || (recommended(a)&&recommended(b)?a.applicationPlan.rank-b.applicationPlan.rank:0) || byScore || byTime;
}
async function refresh() {
  if(fetching) return;
  fetching=true;
  try {
    const r=await fetch("./api/projects.json",{cache:"no-store"});
    if(!r.ok) throw new Error("catalog");
    const data=await r.json();
    projects=data.projects; reviewUntil=Date.parse(data.reviewUntil)||0;
    warning=false; loaded=true;
    $("#sync").textContent=(data.updated?"Обновлено "+stamp(data.updated)+" · Киев":"Ожидается подборка")+(data.incomplete?" · Часть данных недоступна":"");
    if(data.reviewStarted) $("#sync").textContent="Статусы Upwork · "+projects.filter(p=>p.availability?.state).length+" из "+projects.length+" подтверждено";
    const summary=$("#review-summary"), rb=data.reviewBudget;summary.replaceChildren();summary.hidden=!rb;
    if(rb){const fresh=Date.now()<reviewUntil;summary.append(elem("strong","",fresh?"Очередь на 12 часов":"Последняя очередь откликов"),elem("p","", "До "+stamp(reviewUntil)+" по Киеву · "+rb.count+" заявок · "+rb.required+" Connects · баланс при проверке "+rb.balance+" · к покупке "+rb.buy+" (без буста)."));if(fresh){const priority=elem("a","plain","Открыть очередь");priority.href="./?availability=priority#catalog";summary.append(priority);}if(data.reviewReport){const l=elem("a","plain","Полный отчёт");l.href="./reports/"+encodeURIComponent(data.reviewReport);summary.append(l);}}
    render();
    if(!dialog.open || !projects.some(p=>"#project-"+p.id===location.hash)) syncHash();
  } catch {
    warning=true;
    projects=[]; loaded=true;
    $("#sync").textContent="Не удалось загрузить каталог";
    render(); syncHash();
  } finally {fetching=false;}
}
function selectKind(value) {
  kind = ["video", "image", "strategy"].includes(value) ? value : "all";
  for(const tab of document.querySelectorAll("button[data-kind]")) {
    tab.setAttribute("aria-pressed", String(tab.dataset.kind === kind));
  }
}
function selectAi(value) {
  ai = ["generation", "partial", "none", "unset"].includes(value) ? value : "all";
  for(const tab of document.querySelectorAll("button[data-ai]")) {
    tab.setAttribute("aria-pressed", String(tab.dataset.ai === ai));
  }
}
function openFromFinder() {
  const destination = new URL($("#file-open").href);
  destination.search = location.search;
  destination.hash = location.hash;
  $("#file-open").href = destination.href;
  $("#file-entry").hidden = false;
  $(".toolbar").hidden = true;
  $("#total").hidden = true;

  // Top-level navigation keeps the API on its own origin. The link also
  // works in browsers that block requests from local files to loopback.
  const probe = new Image();
  probe.onload = () => location.replace(destination.href);
  probe.src = new URL("mark.svg", destination).href;
}

function startCatalog() {
  const params=new URLSearchParams(location.search);
  selectKind(params.get("type"));
  selectAi(params.get("ai"));
  for(const b of document.querySelectorAll("button[data-ai]")) b.addEventListener("click",()=>{
    selectAi(b.dataset.ai);
    const url = new URL(location.href);
    if (ai === "all") url.searchParams.delete("ai");
    else url.searchParams.set("ai", ai);
    history.replaceState(null, "", url.pathname + url.search + url.hash);
    render();
  });
  for(const id of ["availability","order"]){
    const select=$("#"+id);
    if([...select.options].some(o=>o.value===params.get(id))) select.value=params.get(id);
    select.addEventListener("change",()=>{const u=new URL(location.href);u.searchParams.set(id,select.value);history.replaceState(null,"",u);render();});
  }
  for(const b of document.querySelectorAll("button[data-kind]")) b.addEventListener("click",()=>{
    selectKind(b.dataset.kind);
    const url = new URL(location.href);
    if (kind === "all") url.searchParams.delete("type");
    else url.searchParams.set("type", kind);
    history.replaceState(null, "", url.pathname + url.search + url.hash);
    render();
  });
  $("#query").addEventListener("input",render); $("#pay").addEventListener("change",render); $("#age").addEventListener("change",render);
  $("#reset").addEventListener("click",()=>{$("#query").value="";$("#pay").value="";$("#age").value="all";$("#availability").value="";$("#order").value="new";const u=new URL(location.href);u.searchParams.delete("availability");u.searchParams.delete("order");history.replaceState(null,"",u);document.querySelector("[data-ai=all]").click();document.querySelector("[data-kind=all]").click();});
  $("#close").addEventListener("click",closeDetail); $("#back").addEventListener("click",closeDetail);
  dialog.addEventListener("cancel",e=>{e.preventDefault();closeDetail();});
  dialog.addEventListener("click",e=>{
    const r=dialog.getBoundingClientRect();
    if(e.target===dialog && (e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)) closeDetail();
  });
  dialog.addEventListener("close",()=>{if(lastFocus?.isConnected) lastFocus.focus();});
  window.addEventListener("hashchange",syncHash);
  document.addEventListener("visibilitychange",()=>{if(!document.hidden)refresh();});
  refresh(); setInterval(refresh,60000);
}

if (location.protocol === "file:") {
  openFromFinder();
} else {
  startCatalog();
}
