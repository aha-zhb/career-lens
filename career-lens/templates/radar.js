/* Locally rendered chart, no libraries, fetching, or scoring. */
document.querySelectorAll('.radar-panel').forEach(panel=>{
  const data=JSON.parse(panel.querySelector('.radar-data').textContent);
  const svg=panel.querySelector('.career-radar'),plot=panel.querySelector('.radar-plot');
  const detail=document.getElementById('radar-detail'),buttons=[...panel.querySelectorAll('button[data-axis]')];
  let selected=data.default_axis,lastWidth=0;
  const ns='http://www.w3.org/2000/svg';
  function element(tag,attrs,text){const e=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));if(text!==undefined)e.textContent=text;svg.append(e);return e;}
  function draw(){
    const w=Math.max(240,plot.clientWidth),r=Math.min(142,(w-116)/2),h=2*r+140,cx=w/2,cy=h/2,n=data.axes.length;
    svg.setAttribute('viewBox',`0 0 ${w} ${h}`);svg.setAttribute('height',h);svg.replaceChildren();
    element('title',{},data.title);element('desc',{},data.description);
    const point=(i,v,extra=0)=>{const a=-Math.PI/2+i*2*Math.PI/n;return[cx+Math.cos(a)*(r*v/5+extra),cy+Math.sin(a)*(r*v/5+extra)];};
    const pairs=values=>values.map((v,i)=>point(i,v).join(',')).join(' ');
    for(let k=1;k<=5;k++)element('polygon',{points:pairs(Array(n).fill(k)),class:'radar-grid'});
    data.axes.forEach((a,i)=>{const p=point(i,5);element('line',{x1:cx,y1:cy,x2:p[0],y2:p[1],class:'radar-grid'});});
    const ticks=r<60?[1,3,5]:[1,2,3,4,5];ticks.forEach(k=>element('text',{x:cx+8,y:cy-r*k/5+4,class:'radar-tick'},String(k)));
    element('polygon',{points:pairs(data.axes.map(a=>a.required_level)),class:'radar-target'});
    const values=data.axes.map(a=>a.personal_level);
    if(values.every(v=>v!==null))element('polygon',{points:pairs(values),class:'radar-personal'});
    else data.axes.forEach((a,i)=>{const next=(i+1)%n;if(a.personal_level!==null&&values[next]!==null){const p=point(i,a.personal_level),q=point(next,values[next]);element('line',{x1:p[0],y1:p[1],x2:q[0],y2:q[1],class:'radar-personal radar-segment','data-from':a.id,'data-to':data.axes[next].id});}});
    const active=data.axes.findIndex(a=>a.id===selected),axis=data.axes[active];
    if(axis.personal_level!==null&&axis.personal_level!==axis.required_level){const t=point(active,axis.required_level),p=point(active,axis.personal_level);element('line',{x1:t[0],y1:t[1],x2:p[0],y2:p[1],class:'radar-gap-line'});}
    data.axes.forEach((a,i)=>{
      const p=point(i,a.required_level);element('circle',{cx:p[0],cy:p[1],r:4,class:'radar-target-point','data-axis':a.id});
      if(a.personal_level!==null){const q=point(i,a.personal_level);element('rect',{x:q[0]-4,y:q[1]-4,width:8,height:8,class:'radar-personal-point','data-axis':a.id});}
      const l=point(i,5,n===3?36:26),angle=-Math.PI/2+i*2*Math.PI/n,c=Math.cos(angle);
      let anchor=Math.abs(c)<.05?'middle':c>0?'start':'end';
      const measure=document.createElement('canvas').getContext('2d');
      measure.font=`14px ${getComputedStyle(svg).fontFamily}`;
      const labelWidth=Math.max(...a.label_lines.map(line=>measure.measureText(line).width),a.personal_level===null?42:0);
      if((anchor==='start'&&l[0]+labelWidth>w-4)||(anchor==='end'&&l[0]-labelWidth<4))anchor='middle';
      if(anchor==='middle')l[0]=Math.max(labelWidth/2+4,Math.min(w-labelWidth/2-4,l[0]));
      const y=l[1]+(Math.sin(angle)<-.95?-9:Math.sin(angle)>.95?16:0);
      const text=element('text',{x:l[0],y,'text-anchor':anchor,class:'radar-label','data-axis':a.id});
      a.label_lines.forEach((line,j)=>{const t=document.createElementNS(ns,'tspan');t.setAttribute('x',l[0]);t.setAttribute('dy',j?15:0);t.textContent=line;text.append(t);});
      if(a.personal_level===null)element('text',{x:l[0],y:y+15*a.label_lines.length,'text-anchor':anchor,class:'radar-missing','data-axis':a.id},a.status==='experience_gap'?'缺经历':'需讲清');
    });
    buttons.forEach(b=>b.setAttribute('aria-pressed',b.dataset.axis===selected?'true':'false'));
    document.querySelectorAll('[data-axis-card]').forEach(card=>card.dataset.selected=card.dataset.axisCard===selected?'true':'false');
  }
  function select(id){
    const a=data.axes.find(a=>a.id===id);if(!a)return;selected=id;draw();
    detail.querySelector('h2').textContent=a.label;
    if(detail.classList.contains('axis-explanation')){
      detail.querySelector('.axis-requirement').textContent=a.explanation.requirement;
      detail.querySelector('.axis-experience').textContent=a.explanation.experience;
      detail.querySelector('.axis-difference').textContent=a.explanation.difference;
      detail.querySelector('.radar-audit-link').setAttribute('href',`#radar-axis-${a.id}`);
      return;
    }
    detail.querySelector('.required-value').textContent=`${a.required_level} · ${a.anchors[a.required_level-1]}`;
    detail.querySelector('.personal-value').textContent=a.personal_level===null?(a.status==='experience_gap'?'缺少该阶段的完整经历':'需要展开项目说明'):`${a.personal_level} · ${a.anchors[a.personal_level-1]}`;
    detail.querySelector('.required-reason').textContent=a.required_reason;
    detail.querySelector('.personal-reason').textContent=a.personal_reason;
    detail.querySelector('.radar-gap').textContent=a.gap_note;
    detail.querySelector('.radar-audit-link').setAttribute('href',`#radar-axis-${a.id}`);
  }
  buttons.forEach(b=>b.addEventListener('click',()=>select(b.dataset.axis)));
  svg.addEventListener('click',event=>{const mark=event.target.closest('[data-axis]');if(mark)select(mark.dataset.axis);});
  new ResizeObserver(()=>{if(plot.clientWidth!==lastWidth){lastWidth=plot.clientWidth;draw();}}).observe(plot);draw();
});
