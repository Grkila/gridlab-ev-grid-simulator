"""Bounded chat transport and exact evidence references; no generated memory."""
import hashlib
import json
import re
import uuid
from mvgrid.novi_sad.playground.service import read_json, write_json


class ChatRecords:
    EVENT_BYTES = 12_000
    EVENTS_BYTES = 256_000
    REFERENCES = re.compile(r'\b(?:exp|run|strategy|job)-[a-z0-9-]{1,80}\b')

    @property
    def instance_id(self):
        return hashlib.sha256(str(self.service.root).encode()).hexdigest()[:20]

    def _normalize(self, record):
        if 'sequence' not in record:
            record['sequence'] = 0
            for entry in record['messages'] + record['events']:
                record['sequence'] += 1
                entry.update(seq=record['sequence'], event_id=f"legacy-{record['sequence']}", turn_id='legacy')
        if record.get('transport_version') != 1:
            events=record['events']; record['events']=[]
            for event in events: self._event(record,event)
            record['transport_version']=1
        return record

    def _append(self, record, collection, entry):
        record['sequence'] = record.get('sequence', 0) + 1
        entry.update(seq=record['sequence'], event_id='entry-'+uuid.uuid4().hex,
                     turn_id=record.get('turn_id', 'legacy'))
        record[collection].append(entry)

    def current(self, before=None, limit=20):
        with self.lock:
            if not isinstance(limit, int) or not 1 <= limit <= 100:
                raise ValueError('limit must be between 1 and 100')
            paths = sorted((self.service.root/'chats').glob('*.json'), reverse=True)
            if before: paths = [p for p in paths if p.stem < before]
            rows=[]
            for path in paths[:limit]:
                r=self.get(path.stem)
                rows.append({k:r.get(k) for k in ('chat_id','status','started_at')})
            return dict(instance_id=self.instance_id, active_chat_id=next(iter(self.active), None),
                        can_send=not self.active, chats=rows,
                        next_cursor=paths[limit-1].stem if len(paths)>limit else None)

    def snapshot(self, chat_id, after=None):
        with self.lock:
            r=self.get(chat_id)
            if after is not None and (not isinstance(after,int) or after < 0):
                raise ValueError('after must be a nonnegative sequence')
            reset=after is None or after < r.get('events_floor',0) or after > r['sequence']
            lower=-1 if reset else after
            messages=[m for m in r['messages'] if m['seq']>lower]
            if len(messages)>100:
                reset=True;lower=-1;messages=r['messages'][-100:]
            elif reset: messages=messages[-100:]
            return {k:v for k,v in r.items() if k not in ('messages','events','build_request','pending_status')} | dict(
                messages=[self._message_preview(chat_id,m) for m in messages],
                events=[e for e in r['events'] if e['seq']>lower], reset=reset,
                cursor=r['sequence'], can_send=not self.active,
                active_chat_id=next(iter(self.active),None),
                history_before=messages[0]['seq'] if reset and messages and any(m['seq']<messages[0]['seq'] for m in r['messages']) else None)

    def _message_preview(self, chat_id, message):
        if len(message.get('content','').encode()) <= self.EVENT_BYTES: return message
        return message | dict(content=message['content'][:3000]+'\n[Full message available below]',
                              full_url=f"/api/chat/{chat_id}/messages/{message['event_id']}")

    def history(self, chat_id, before):
        r=self.get(chat_id)
        messages=[m for m in r['messages'] if m['seq']<before][-100:]
        return dict(messages=[self._message_preview(chat_id,m) for m in messages],
                    history_before=messages[0]['seq'] if messages and any(m['seq']<messages[0]['seq'] for m in r['messages']) else None)

    def output(self, chat_id, output_id):
        folder=self.service._path('chat-outputs',chat_id)
        name=self.service._path('chat-outputs',output_id).name
        return read_json(folder/name)

    def outputs(self, chat_id, after=None):
        files=sorted(self.service._path('chat-outputs',chat_id).glob('output-*'))
        if after: files=[p for p in files if p.name>after]
        return dict(outputs=[dict(output_id=p.name,url=f'/api/chat/{chat_id}/outputs/{p.name}') for p in files[:50]],
                    next_cursor=files[49].name if len(files)>50 else None)

    def _event(self, record, event):
        encoded=json.dumps(event,ensure_ascii=False)
        refs=record.setdefault('references',[])
        for ref in self.REFERENCES.findall(encoded):
            if ref not in refs: refs.append(ref)
        record['references']=refs[-80:]
        item=event.get('item',{})
        archive=len(encoded.encode())>self.EVENT_BYTES or (item.get('type')=='mcp_tool_call' and event.get('type')=='item.completed')
        if archive:
            output_id='output-'+uuid.uuid4().hex
            write_json(self.service._path('chat-outputs',record['chat_id'])/output_id,event)
            url=f"/api/chat/{record['chat_id']}/outputs/{output_id}"
            if len(encoded.encode())>self.EVENT_BYTES:
                event=dict(type=event.get('type','event'), item={k:item[k] for k in ('id','type','tool','server','status') if k in item}, preview=encoded[:2000], full_url=url)
            else: event=event | dict(full_url=url)
        self._append(record,'events',event)
        sizes=[len(json.dumps(e).encode()) for e in record['events']]
        total=sum(sizes)+2*len(sizes)+2
        while len(record['events'])>500 or total>self.EVENTS_BYTES:
            total-=sizes.pop(0)+2
            record['events_floor']=record['events'].pop(0)['seq']

    def context(self, record):
        selected=[]; size=0
        for m in reversed(record['messages']):
            text=m['role'].upper()+': '+m['content']
            if selected and size+len(text)>40_000: break
            selected.append(text); size+=len(text)
            if len(selected)>=20: break
        omitted=len(record['messages'])-len(selected)
        return (f"Referenced IDs (retrieve current evidence with MCP): {json.dumps(record.get('references',[]))}\n"
                f"User-pinned constraints, verbatim: {json.dumps(record.get('constraints',''))}\n"
                f"Earlier messages omitted: {omitted}. Do not infer missing constraints or results; retrieve evidence or ask.\n"
                +'\n\n'.join(reversed(selected)))
