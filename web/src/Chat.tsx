import { useEffect, useRef, useState } from 'react';
import { Bot, Minus, Send, Square } from 'lucide-react';
import { usePresentationCue } from './presentation/bridge';

type Row = Record<string, any>;
async function request(path: string, init?: RequestInit) {
  const response = await fetch(path, { headers: {'Content-Type':'application/json'}, ...init });
  const data = await response.json();
  if (!response.ok) throw Object.assign(new Error(data.error || `HTTP ${response.status}`), {status:response.status});
  return data;
}
const storage = {
  get(key: string) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key: string, value: string) { try { localStorage.setItem(key,value); } catch { /* recovery endpoint still works */ } },
};
function merge(old: Row[], incoming: Row[]) {
  return [...new Map([...old,...incoming].map(e=>[e.event_id,e])).values()].sort((a,b)=>a.seq-b.seq);
}

export function Chat() {
  const [open,setOpen]=useState(false), [id,setId]=useState<string>(), [message,setMessage]=useState('');
  const presentationCue = usePresentationCue();
  useEffect(() => {
    if (presentationCue) setOpen(!!presentationCue.chat);
    if (typeof presentationCue?.chatPrompt === 'string' && presentationCue.chatPrompt.length <= 4000) setMessage(presentationCue.chatPrompt);
  }, [presentationCue]);
  const [messages,setMessages]=useState<Row[]>([]), [events,setEvents]=useState<Row[]>([]);
  const [status,setStatus]=useState('reconnecting'), [canSend,setCanSend]=useState(false);
  const [error,setError]=useState(''), [actionError,setActionError]=useState(''), [constraints,setConstraints]=useState('');
  const [chats,setChats]=useState<Row[]>([]), [history,setHistory]=useState<number|null>(null);
  const [nextChats,setNextChats]=useState<string|null>(null), [references,setReferences]=useState<string[]>([]);
  const [action,setAction]=useState('auto'), [specification,setSpecification]=useState(''), [contractVersion,setContractVersion]=useState<string>();
  const cursor=useRef<number|undefined>(undefined), instance=useRef(''), initialized=useRef(false);
  const generation=useRef(0), mutation=useRef(false), constraintsDirty=useRef(false);
  const retry=useRef<Row|null>(null);
  const attach=(chatId?: string) => {
    generation.current++; cursor.current=undefined; constraintsDirty.current=false;
    setId(chatId); setMessages([]); setEvents([]); setReferences([]); setConstraints(''); setHistory(null);
    setCanSend(false); setStatus('reconnecting'); setError(''); setActionError('');
    if(instance.current) storage.set(`ev-chat:${instance.current}`,chatId || '');
  };
  const apply=(data: Row) => {
    cursor.current=data.cursor;
    setMessages(old=>merge(data.reset?[]:old,data.messages || []));
    setEvents(old=>merge(data.reset?[]:old,data.events || []).filter(e=>e.seq>(data.events_floor || 0)));
    if(data.reset) setHistory(data.history_before);
    setReferences(data.references || []);
    if(!constraintsDirty.current) setConstraints(data.constraints || '');
    setCanSend(data.can_send);
    setStatus(data.cancel_requested && !data.can_send?'cancelling':data.status);
    setError(data.error || '');
    storage.set(`ev-chat:${instance.current}`,data.chat_id);
  };
  useEffect(()=> {
    const listener=(event: Event)=> {setMessage((event as CustomEvent<string>).detail);setOpen(true);};
    window.addEventListener('strategy-chat',listener);
    return ()=>window.removeEventListener('strategy-chat',listener);
  },[]);
  useEffect(()=> {
    let disposed=false, timer: ReturnType<typeof setTimeout>, controller: AbortController|undefined, failures=0;
    const poll=async()=> {
      const version=generation.current;
      if(mutation.current) { timer=setTimeout(poll,300); return; }
      controller=new AbortController();
      // A hung HTTP request must not prevent recovery forever.
      const timeout=setTimeout(()=>controller?.abort(),10000);
      try {
        if(!initialized.current || !id) {
          const current=await request('/api/chat/current',{signal:controller.signal});
          if(disposed || version!==generation.current) return;
          const contract=await request('/api/agent-contract',{signal:controller.signal});
          if(disposed || version!==generation.current) return;
          setContractVersion(contract.version);
          instance.current=current.instance_id; setChats(current.chats); setNextChats(current.next_cursor);
          const saved=initialized.current?null:storage.get(`ev-chat:${current.instance_id}`);
          const pending=storage.get(`ev-chat-pending:${current.instance_id}`);
          initialized.current=true;
          let recovered: string|undefined;
          if(pending) {
            try { recovered=(await request(`/api/chat/requests/${pending}`,{signal:controller.signal})).chat_id; }
            catch(e: any) { if(e.status!==404) throw e; }
            if(disposed || version!==generation.current) return;
            storage.set(`ev-chat-pending:${current.instance_id}`,'');
          }
          const target=current.active_chat_id || recovered || saved;
          if(target && target!==id) { attach(target); return; }
          setCanSend(current.can_send); setStatus('ready'); setError('');
        } else {
          const data=await request(`/api/chat/${id}${cursor.current===undefined?'':`?after=${cursor.current}`}`,{signal:controller.signal});
          if(disposed || version!==generation.current) return;
          if(data.active_chat_id && data.active_chat_id!==id) { attach(data.active_chat_id); return; }
          apply(data);
        }
        failures=0;
      } catch(e: any) {
        if(disposed || version!==generation.current) return;
        if(e.status===404 && id) {attach(); return;}
        setCanSend(false); setStatus('reconnecting'); setError('Connection lost. Reconnecting to check whether work is still running.'); failures++;
      } finally {
        clearTimeout(timeout);
        if(!disposed) timer=setTimeout(poll,Math.min(10000,1200*2**failures));
      }
    };
    void poll();
    return ()=> {disposed=true;clearTimeout(timer);controller?.abort();};
  },[id]);
  const send=async()=> {
    if(!canSend || mutation.current || !message.trim()) return;
    mutation.current=true; generation.current++; setCanSend(false);setStatus('sending');setError('');setActionError('');
    const body={message,chat_id:id,constraints,requested_action:action,specification_id:action==='implement'?specification:undefined,contract_version:contractVersion};
    if(!retry.current || JSON.stringify(retry.current.body)!==JSON.stringify(body)) retry.current={body,request_id:`request-${crypto.randomUUID()}`};
    const payload={...body,request_id:retry.current!.request_id};
    storage.set(`ev-chat-pending:${instance.current}`,payload.request_id);
    try {
      const data=await request('/api/chat',{method:'POST',body:JSON.stringify(payload),signal:AbortSignal.timeout(15000)});
      if(data.chat_id!==id) attach(data.chat_id);
      apply(data);setMessage('');setAction('auto');setSpecification('');retry.current=null;
      storage.set(`ev-chat-pending:${instance.current}`,'');
    } catch(e: any) {
      // A lost POST response may hide an accepted turn. Never blindly replay it.
      try {
        const accepted=await request(`/api/chat/requests/${payload.request_id}`,{signal:AbortSignal.timeout(10000)});
        if(accepted.chat_id!==id) attach(accepted.chat_id);
        apply(accepted);setMessage('');setAction('auto');setSpecification('');retry.current=null;
        storage.set(`ev-chat-pending:${instance.current}`,'');
      } catch {
        setStatus('reconnecting');setActionError(e.message);
      }
    } finally { mutation.current=false; }
  };
  const cancel=async()=> {
    if(!id || mutation.current) return;
    mutation.current=true;generation.current++;setStatus('cancelling');setCanSend(false);setActionError('');
    try { apply(await request(`/api/chat/${id}/cancel`,{method:'POST',body:'{}',signal:AbortSignal.timeout(10000)})); }
    catch(e: any) {setActionError(`Cancellation could not be confirmed: ${e.message}`);setStatus('reconnecting');}
    finally {mutation.current=false;}
  };
  const loadHistory=async()=> {
    const version=generation.current;
    try {const data=await request(`/api/chat/${id}/history?before=${history}`);
      if(version!==generation.current) return;
      setMessages(old=>merge(data.messages,old));setHistory(data.history_before);
    } catch(e: any) {setError(e.message);}
  };
  const loadChats=async(more=false)=> {
    try {const data=await request(`/api/chat/current${more && nextChats?`?before=${nextChats}`:''}`);
      setChats(old=>more?[...old,...data.chats]:data.chats);setNextChats(data.next_cursor);
    } catch(e: any) {setError(e.message);}
  };
  const answered=new Set(messages.filter(m=>m.role==='assistant').map(m=>m.turn_id));
  const latest=new Map<string,Row>();
  for(const event of events) {
    const item=event.item || {};
    if(item.type==='agent_message' && (answered.has(event.turn_id) || event.type!=='item.completed')) continue;
    latest.set(item.id?`${event.turn_id}:${item.id}`:event.event_id,event);
  }
  const feed=[...messages,...latest.values()].sort((a,b)=>a.seq-b.seq);
  if(!open) return <button className="chat-launch" onClick={()=>setOpen(true)}><Bot size={19}/> {'Codex CLI chat'}</button>;
  return <aside className="chat" aria-label="Experiment assistant">
    <div className="chat-head"><Bot/><div><b>{'Codex experiment assistant'}</b><small role="status">{status==='completed'||status==='ready'?'Ready to send':status}</small></div>
      {!canSend && id && <button title="Cancel chat response" aria-label="Cancel chat response" onClick={()=>void cancel()}><Square size={14}/></button>}
      <button title="Minimize chat" aria-label="Minimize chat" onClick={()=>setOpen(false)}><Minus size={16}/></button>
    </div>
    <div className="chat-controls">
      <button disabled={!canSend} onClick={()=>attach()}>{'New conversation'}</button>
      <select aria-label="Open conversation" value={id || ''} disabled={!canSend} onFocus={()=>void loadChats()} onChange={e=>attach(e.target.value || undefined)}>
        <option value="">{'Open conversation…'}</option>
        {id && !chats.some(c=>c.chat_id===id) && <option value={id}>{id}</option>}
        {chats.map(c=><option key={c.chat_id} value={c.chat_id}>{c.started_at?new Date(c.started_at*1000).toLocaleString():c.chat_id} · {c.status}</option>)}
      </select>
      {nextChats && <button onClick={()=>void loadChats(true)}>{'More conversations'}</button>}
    </div>
    <div className="chat-controls"><select aria-label="Chat workflow" disabled={!canSend} value={action} onChange={e=>setAction(e.target.value)}>
      <option value="auto">{'Focus from my message'}</option><option value="explain">{'Explain / plan only'}</option><option value="algorithm">{'Develop algorithm'}</option><option value="scenario">{'Create scenario'}</option><option value="run">{'Run experiment'}</option><option value="compare">{'Compare results'}</option><option value="diagnose">{'Diagnose failure'}</option><option value="training">{'Train RL policy'}</option><option value="benchmark">{'Benchmark algorithms'}</option><option value="implement">{'Implement saved strategy'}</option>
    </select>{action==='implement' && <input aria-label="Saved specification ID" placeholder="strategy-..." value={specification} onChange={e=>setSpecification(e.target.value)}/>}</div>
    {action==='implement' && <small className="chat-notes">{'Sending this request enables workspace edits and tests for the saved specification.'}</small>}
    <div className="feed" aria-live="polite">
      {history!==null && <button onClick={()=>void loadHistory()}>{'Load earlier messages'}</button>}
      {!feed.length && <p>{'Draft an experiment, inspect a stopped run, or compare evidence.'}</p>}
      {feed.map(e=> {
        const item=e.item || {}, tool=item.type==='mcp_tool_call';
        const diagnostic=!e.role && item.type!=='agent_message';
        return <div key={e.event_id} className={`event ${e.role || 'tool'}`} data-turn={e.turn_id}>
          <small>{e.role || (tool?`${item.tool} · ${item.status || e.type}`:item.type==='agent_message'?'assistant':e.type)}</small>
          {diagnostic?<details><summary>{tool?'Tool activity':'Diagnostic event'}</summary><pre>{e.preview || JSON.stringify(item.id?item:e,null,2)}</pre></details>:<p>{e.content || item.text || e.preview}</p>}
          {e.full_url && <a href={e.full_url} target="_blank" rel="noreferrer">{'Open full evidence'}</a>}
        </div>;
      })}
      {(actionError || error) && <p role="alert">{actionError || error}</p>}
    </div>
    {references.filter(r=>r.startsWith('run-')).length>0 && <details className="chat-notes"><summary>{'Referenced runs'}</summary>{references.filter(r=>r.startsWith('run-')).map(r=><div key={r}><a href={`/api/runs/${r}`} target="_blank" rel="noreferrer">{r}</a></div>)}</details>}
    <details className="chat-notes"><summary>{'Constraints to keep across turns'}</summary><textarea aria-label="Pinned constraints" maxLength={4000} value={constraints} onChange={e=>{constraintsDirty.current=true;setConstraints(e.target.value);}}/><small>{'Saved verbatim with your next message. Edit or clear these when assumptions change.'}</small></details>
    {id && <a className="chat-notes" href={`/api/chat/${id}/outputs`} target="_blank" rel="noreferrer">{'All saved tool evidence'}</a>}
    <small className="chat-notes">{'Cancel stops this response. Started experiments continue; cancel them in Runs.'}</small>
    <div className="composer"><textarea aria-label="Message to Codex" maxLength={20000} placeholder={'Ask about experiments or paste a STRATEGY command…'} value={message} onChange={e=>setMessage(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();void send();}}}/><button aria-label="Send message" disabled={!canSend||!message.trim()} onClick={()=>void send()}><Send size={17}/></button></div>
  </aside>;
}
