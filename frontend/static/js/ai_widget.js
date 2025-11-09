(function(){
  if (window.__assistantWidgetLoaded) return; window.__assistantWidgetLoaded = true;
  function el(tag, cls){ const e=document.createElement(tag); if(cls) e.className=cls; return e; }
  function escapeHtml(s){ return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
  function renderBotText(text){ const t=(text||'').trim(); const lines=t.split(/\r?\n/); const out=[]; for(const ln of lines){ const l=ln.trim(); if(!l) continue; if(/^(-|•)\s+/.test(l)){ out.push('<li>'+escapeHtml(l.replace(/^(-|•)\s+/,''))+'</li>'); } else { out.push('<p>'+escapeHtml(l)+'</p>'); } } if(out.some(x=>x.startsWith('<li'))){ return '<ul>'+out.join('')+'</ul>'; } return out.join(''); }

  const root = el('div','assistant-widget');
  const fab = el('button','assistant-fab');
  fab.setAttribute('aria-label','Open AI Assistant');
  fab.innerHTML = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 3C7.03 3 3 6.58 3 11c0 2.06.94 3.93 2.5 5.37V21l3.37-1.83C9.9 19.72 10.93 20 12 20c4.97 0 9-3.58 9-8s-4.03-9-9-9z" fill="currentColor"/></svg>';
  const badge = el('div','assistant-badge'); badge.style.display='none'; fab.appendChild(badge);
  const panel = el('div','assistant-panel');
  const header = el('div','assistant-header');
  const title = el('div','assistant-title'); title.textContent='AI Assistant';
  const close = el('button','assistant-close'); close.setAttribute('aria-label','Close'); close.innerHTML='×';
  header.appendChild(title); header.appendChild(close);
  const body = el('div','assistant-body');
  const inputWrap = el('div','assistant-input');
  const input = document.createElement('input'); input.type='text'; input.placeholder='Ask about your garden...';
  const send = document.createElement('button'); send.textContent='Send';
  inputWrap.appendChild(input); inputWrap.appendChild(send);
  panel.appendChild(header); panel.appendChild(body); panel.appendChild(inputWrap);
  root.appendChild(fab); root.appendChild(panel);
  const link = document.createElement('link'); link.rel='stylesheet'; link.href=(window.__assistantCssPath||'/static/ai_widget.css');
  document.head.appendChild(link);
  document.body.appendChild(root);

  let open=false, busy=false; function toggle(){ open=!open; panel.style.display=open?'flex':'none'; if(open){ loadHistory(); updateBadge(0); } }
  fab.addEventListener('click', toggle); close.addEventListener('click', toggle);

  function appendMsg(role, text){ const m=el('div','assistant-msg '+(role==='user'?'assistant-user':'assistant-bot')); if(role==='assistant'){ m.innerHTML=renderBotText(text); } else { m.textContent=text; } body.appendChild(m); body.scrollTop=body.scrollHeight; }

  async function loadHistory(){ try{ const r=await fetch('/api/ai/chat'); const list=await r.json(); body.innerHTML=''; (list||[]).forEach(m=> appendMsg(m.role, m.message)); }catch(e){ /* ignore */ } }

  async function sendMsg(){ if(busy) return; const text=(input.value||'').trim(); if(!text) return; busy=true; input.value=''; appendMsg('user', text); try{ const r=await fetch('/api/ai/respond',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})}); const res=await r.json(); appendMsg('assistant', (res && (res.assistant||res.error)) || ''); }catch(e){ appendMsg('assistant','Sorry, something went wrong.'); } finally{ busy=false; } }
  send.addEventListener('click', sendMsg); input.addEventListener('keydown', e=>{ if(e.key==='Enter'){ e.preventDefault(); sendMsg(); }});

  function renderPendingList(items){
    const wrap = el('div','assistant-msg assistant-bot');
    const list = document.createElement('div'); list.className='assistant-pending';
    const title = document.createElement('div'); title.className='assistant-pending-title'; title.textContent='Pending tasks'; list.appendChild(title);
    items.forEach(it=>{
      const row = document.createElement('div'); row.className='assistant-pending-item';
      const txt = document.createElement('div'); txt.className='assistant-pending-text'; txt.textContent = it.message || it.task || '';
      const btn = document.createElement('button'); btn.className='assistant-done-btn'; btn.textContent='Mark Done';
      btn.addEventListener('click', async ()=>{
        btn.disabled = true;
        try{
          await fetch('/api/assistant/pending/complete',{method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({schedule_id: it.schedule_id, day: it.day, task: it.task})});
          row.classList.add('done'); btn.textContent='✓ Done'; updateBadge(Math.max(0, (Number(badge.textContent)||1)-1));
        }catch(e){ btn.disabled=false; }
      });
      row.appendChild(txt); row.appendChild(btn); list.appendChild(row);
    });
    wrap.appendChild(list); body.appendChild(wrap); body.scrollTop=body.scrollHeight;
  }

  async function checkPending(){ try{ const r=await fetch('/api/assistant/pending'); const d=await r.json(); const c = (d && d.count)|0; updateBadge(c); if(open && d && Array.isArray(d.items) && d.items.length){ renderPendingList(d.items.slice(0,5)); }
  }catch(e){ /* ignore */ } }
  function updateBadge(n){ if(n>0){ badge.textContent = String(n); badge.style.display='block'; } else { badge.style.display='none'; } }

  // Initial fetches
  loadHistory(); checkPending();
  // Poll pending every 60s
  setInterval(checkPending, 60000);
})();
