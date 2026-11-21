"use strict";
const $=s=>document.querySelector(s);
function el(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
function link(text,href,cls=""){const n=el("a",cls,text);n.href=href;return n;}
function section(title,texts,tag="p"){const s=el("section","reportsection");s.append(el("h3","",title));const w=tag==="li"?el("ul"):s;if(w!==s)s.append(w);for(const t of texts)w.append(el(tag,"",t));return s;}
function stamp(s){return new Intl.DateTimeFormat("ru-RU",{timeZone:"Europe/Kyiv",dateStyle:"medium",timeStyle:"short"}).format(new Date(s));}
let cards=[],briefs=new Map(),list=[];
function openReport(id,scroll=true){
 const c=cards.find(x=>x.id===id),p=briefs.get(id),box=$("#practice-report");
 if(!c){box.hidden=true;return;}
 const actions=el("div","reportactions");actions.append(link("← Карточка в каталоге","./#project-"+c.id,"plain"));const source=link("Оригинал на Upwork ↗",c.url,"plain");source.target="_blank";source.rel="noopener noreferrer";actions.append(source);
 box.replaceChildren(actions,el("p","eyebrow",p?.group||"Разбор ещё не подготовлен"),el("h2","",c.title),el("p","subtle",`${c.client}${c.country?" · "+c.country:""} · Данные на ${stamp(c.checked)} по Киеву`));
 box.append(originalBrief(c),section("Краткое описание задачи",[c.description,...c.tasks],"li"));
 box.append(section("Зачем это клиенту",[c.about,c.history,c.activity].filter(Boolean)));
 const unknownBudget = c.payment === "hourly" && c.paidScopeConfirmed !== true;
 box.append(section("Условия и неопределённость",[c.budget+(unknownBudget?" · Общий бюджет не подтверждён":""),c.risk,c.question]));
 if(c.applicationPlan){const a=c.applicationPlan;const next=section("Новая демка именно для этого отклика",[a.brief,a.demo,a.check]);next.classList.add("demobox");for(const r of a.refs){const line=el("p","",r.use+" ");const l=link(r.name,r.url,"plain");l.target="_blank";l.rel="noopener noreferrer";line.append(l);next.append(line);}next.append(link("Открыть цену и Cover Letter →","./#project-"+c.id,"plain"));box.append(next);}
 if(p){
  const demo=section("Предлагаемое демо для практики",[p.demo,p.scopeNote]);demo.classList.add("demobox");box.append(demo);
  const badges=el("div","practicebadges");badges.append(el("span","",p.difficulty+" сложность демо"),el("span","",p.hours+" часов активной практики — ориентир"));box.append(badges);
  box.append(el("p","subtle","Оценка времени не включает ожидание генераций и освоение незнакомых инструментов. Это не срок выполнения полного заказа."));
  const storyboard=el("section","reportsection");storyboard.append(el("h3","","Последовательность кадров или материалов"));const ol=el("ol","storyboard");p.storyboard.forEach((t,i)=>{const li=el("li");li.append(el("span","frame-no",String(i+1).padStart(2,"0")),el("p","",t));ol.append(li);});storyboard.append(ol);box.append(storyboard);
  box.append(section("Как выполнить",p.workflow,"li"),section("Проверка готовности",p.checks,"li"),section("Что положить в кейс",p.caseStudy,"li"),section("Как честно представить работу",[p.presentation]));
  const plan=el("button","solid","Скопировать учебный план");plan.type="button";plan.addEventListener("click",async()=>{const text=[c.title,"\nИсходная задача",c.description,...c.tasks,"\nМоё учебное демо",p.demo,"\nПоследовательность",...p.storyboard,"\nПроверка",...p.checks,p.presentation].join("\n");try{await navigator.clipboard.writeText(text);plan.textContent="План скопирован";}catch{plan.textContent="Выделите текст плана для копирования";}});box.append(plan);
 } else box.append(el("p","","Карточка сохранена. Индивидуальный разбор для неё ещё не добавлен."));
 box.hidden=false;if(scroll){box.scrollIntoView({behavior:"smooth",block:"start"});box.focus({preventScroll:true});}
}
function choose(id){const u=new URL(location.href);u.searchParams.set("project",id);history.pushState(null,"",u.pathname+u.search);openReport(id);}
function render(){const q=$("#practice-query").value.trim().toLocaleLowerCase("ru"),g=$("#practice-group").value,l=$("#practice-level").value;
 const selected=list.filter(({c,p})=>(!g||p?.group===g)&&(!l||p?.difficulty===l)&&[c.title,c.client,c.description,p?.demo,p?.group].join(" ").toLocaleLowerCase("ru").includes(q));
 $("#practice-results").textContent=`Показано ${selected.length} из ${list.length}`;$("#practice-grid").replaceChildren(...selected.map(({c,p})=>{const a=el("article","practicecard");a.append(el("p","eyebrow",p?.group||"Новый проект"));const title=link(c.title,"./practice.html?project="+c.id);title.addEventListener("click",e=>{if(!e.metaKey&&!e.ctrlKey){e.preventDefault();choose(c.id);}});const h=el("h3");h.append(title);a.append(h,el("p","",p?.demo||c.description),el("p","subtle",p?`${p.difficulty} · ${p.hours} ч практики`:"Разбор ожидается"));return a;}));if(!selected.length)$("#practice-grid").append(el("p","","По этим фильтрам проектов нет."));}
function overview(){
 const sorted=[...briefs.values()].filter(p=>cards.some(c=>c.id===p.id));$("#stat-all").textContent=cards.length;$("#stat-video").textContent=cards.filter(c=>c.kind!=="image").length;$("#stat-practice").textContent=sorted.length;$("#stat-early").textContent=sorted.filter(p=>p.difficulty==="Начальная").length;$("#practice-count").textContent=cards.length;
 const groups={};sorted.forEach(p=>groups[p.group]=(groups[p.group]||0)+1);const entries=Object.entries(groups).sort((a,b)=>b[1]-a[1]);
 for(const [name,count]of entries){const row=el("div","marketrow");row.append(el("span","",name),el("b","",count));const meter=document.createElement("meter");meter.min=0;meter.max=cards.length;meter.value=count;meter.setAttribute("aria-label",`${name}: ${count} из ${cards.length}`);row.append(meter);$("#market-bars").append(row);const opt=el("option","",name);opt.value=name;$("#practice-group").append(opt);}
 const signals=[
  ["Узнаваемость товара и героя",/сохран|неизмен|узнаваем|стабиль|одинаков|точн/i,"В кейсе полезно показать исходник, результат и крупное сравнение деталей."],
  ["Варианты и поток производства",/вариант|парт|недел|месяц|серия|серии|поток/i,"Покажи одну базовую концепцию и несколько управляемых вариаций, затем учти время и стоимость."],
  ["Звук, речь и монтаж",/голос|озвуч|субтитр|звук|монтаж|смонтир/i,"Сильного кадра недостаточно: демонстрируй законченный короткий фрагмент со звуком и читаемым текстом."]
 ];for(const [title,re,meaning]of signals){const n=cards.filter(c=>re.test([c.description,...c.tasks].join(" "))).length;const s=el("div","signal");s.append(el("h3","",title),el("p","",meaning),el("small","",`${n} из ${cards.length} описаний содержат соответствующие требования или их формулировки.`));$("#signals").append(s);}
 $("#signals").append(el("p","subtle","Тематические счётчики основаны на формулировках сохранённых описаний и пересекаются. Они не измеряют долю рынка."));
 for(const id of ["2119203335814999173","2118951201390294996","2118401767399857908","2119220665053756505","2118626076449939188"]){const c=cards.find(c=>c.id===id);if(c)$("#starter-links").append(link(c.title+" ↗","./practice.html?project="+id));}
 $("#overview").hidden=false;
}
async function start(){try{const [a,b,c]=await Promise.all([fetch('./api/projects.json',{cache:'no-store'}),fetch('./api/practice.json',{cache:'no-store'}),fetch('./api/reports.json',{cache:'no-store'})]);if(!a.ok||!b.ok||!c.ok)throw Error();const [data,practice,reports]=await Promise.all([a.json(),b.json(),c.json()]);cards=data.projects;briefs=new Map(practice.projects.map(p=>[p.id,p]));list=cards.map(c=>({c,p:briefs.get(c.id)}));overview();render();for(const r of reports.reports)$("#report-links").append(link(r.label,"./reports/"+encodeURIComponent(r.name),"reportlink"));$("#load-status").textContent="Здесь собраны учебные разборы. Актуальность подачи и подготовленные отклики указаны в карточках каталога.";openReport(new URLSearchParams(location.search).get('project'));}catch{$("#load-status").textContent="Не удалось загрузить архив. Обновите страницу или повторите позже.";}}
for(const id of ['practice-query','practice-group','practice-level'])$('#'+id).addEventListener(id==='practice-query'?'input':'change',render);
window.addEventListener('popstate',()=>openReport(new URLSearchParams(location.search).get('project')));start();
