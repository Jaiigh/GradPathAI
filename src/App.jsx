import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from './api.js';
import { BlockerCard, GoalCard, PlanCard, StopCard, goalText } from './cards.jsx';

const OPERATOR = new URLSearchParams(window.location.search).has('operator');
const ROUNDS = [['รอบ 1 (Group 4)', ['T01', 'T05', 'T09', 'T13', 'T17']], ['รอบ 2 (Group 7)', ['T03', 'T07', 'T11', 'T16', 'T19']]];
const STEP_TH = {
  think: 'กำลังคิด', audit: 'ตรวจสถานะหน่วยกิต', retrieve_courses: 'ค้นข้อมูลรายวิชา', propose_goal: 'สรุปเป้าหมาย',
  solve_plan: 'จัดแผนด้วย solver', validate_plan: 'ตรวจแผนกับกฎหลักสูตร', submit_final: 'ตรวจขั้นสุดท้าย (final gate)',
  ask_user: 'เตรียมคำถาม', reply: 'เตรียมคำตอบ'
};
const GRADES = ['A', 'B+', 'B', 'C+', 'C', 'D+', 'D', 'F', 'S', 'U', 'W'];

const sessionFromHash = () => new URLSearchParams(window.location.hash.slice(1)).get('s');

function Topbar({ view, health, onNew }) {
  const ready = health?.warm?.model;
  return <header className="topbar">
    <a className="brand" href={OPERATOR ? '?operator' : '.'}>GRADPATH<span>•</span></a>
    <div className="privacy"><span className={`dot ${ready ? 'ok' : ready === false ? 'bad' : ''}`} />
      {ready ? 'ระบบพร้อม' : ready === false ? 'โมเดลไม่พร้อม' : 'กำลังเตรียมโมเดล'} <i>·</i> ทำงานบนเครื่องนี้เท่านั้น <i>·</i> ข้อมูลนิสิตจำลอง</div>
    {view && <span className="who">{view.persona_label}{view.task_id ? ` · ${view.task_id}` : ''}</span>}
    {view && <button className="new-session" onClick={onNew}>เริ่ม session ใหม่</button>}
  </header>;
}

function Start({ onStart, error }) {
  const [personas, setPersonas] = useState([]);
  const [tasks, setTasks] = useState([]);
  useEffect(() => {
    api.personas().then(setPersonas).catch(() => {});
    if (OPERATOR) api.tasks().then(setTasks).catch(() => {});
  }, []);
  const byId = useMemo(() => Object.fromEntries(tasks.map(t => [t.id, t])), [tasks]);
  const taskButton = (t) => t && <button key={t.id} className="task" onClick={() => onStart({ task_id: t.id })}>
    <b>{t.id}</b><span>{t.uat} · {t.type}</span><small>{t.persona} · {t.lang.toUpperCase()}{t.fault ? ` · fault ${t.fault}` : ''}{t.overlay ? ' · overlay' : ''}</small>
  </button>;
  return <main className="start">
    <section>
      <p className="eyebrow">GradPath · วิศวกรรมคอมพิวเตอร์ หลักสูตร 2566</p>
      <h1>วางแผนการเรียนที่เหลือจนจบปี 4</h1>
      <p className="lead">GradPath ถามสิ่งที่ยังไม่ชัด จัดแผนทุกเทอมด้วย solver และแสดงเฉพาะแผนที่ผ่านการตรวจขั้นสุดท้าย ข้อมูลในรอบนี้เป็นนิสิตจำลอง ไม่ใช่การรับรองการจบการศึกษา</p>
      {error && <p className="error">{error}</p>}
    </section>
    {OPERATOR && <section>
      <h2 className="section-title">ผู้ดูแล: เลือก Task</h2>
      {ROUNDS.map(([label, ids]) => <div key={label} className="task-group"><p className="eyebrow">{label}</p>
        <div className="task-grid">{ids.map(id => taskButton(byId[id]))}</div></div>)}
      <div className="task-group"><p className="eyebrow">ทุก task</p>
        <div className="task-grid">{tasks.map(taskButton)}</div></div>
    </section>}
    <section>
      <h2 className="section-title">{OPERATOR ? 'โหมดสาธิต: เลือกนิสิตจำลอง' : 'เลือกนิสิตจำลอง'}</h2>
      <div className="task-grid">{personas.map(p => <button key={p.name} className="task" onClick={() => onStart({ persona: p.name })}>
        <b>{p.label}</b><span>เทอมถัดไป {p.next_term}</span><small>จบปี 4 ภาค {p.end_of_year4}</small>
      </button>)}</div>
    </section>
  </main>;
}

function RecordsPanel({ view, busy, onConfirm }) {
  const [choices, setChoices] = useState({});
  const st = view.student;
  const byTerm = useMemo(() => {
    const out = {};
    view.records.forEach(r => { (out[r.term] ||= []).push(r); });
    return Object.entries(out);
  }, [view.records]);
  const unresolved = view.records.flatMap(r => r.unresolved.map(u => ({ ...u, record: r })));
  const ready = unresolved.every(u => choices[`${u.record.index}.${u.field}`]);
  const confirm = () => onConfirm(unresolved.map(u => ({ record_index: u.record.index, field: u.field, value: choices[`${u.record.index}.${u.field}`] })));
  const a = view.audit;
  return <aside className="records">
    <div className="panel-heading">
      <div><p className="eyebrow">ขั้นที่ 1</p><h2>ระเบียนการเรียน</h2></div>
      <span className={`pill ${st.confirmed ? 'ok' : unresolved.length ? 'warn' : ''}`}>{st.confirmed ? `ยืนยันแล้ว · v${st.record_version}` : unresolved.length ? 'ต้องตรวจข้อมูล' : 'รอยืนยัน'}</span>
    </div>
    <p className="muted">ปีเข้า {st.entry_year} · เทอมถัดไป {st.next_term} · ปลายปี 4 คือ {st.end_of_year4}</p>
    {a && <div className="summary">
      <div className="big"><strong>{a.earned_credits}</strong><span>หน่วยกิตที่ได้แล้ว<br />จาก 138</span></div>
      <div className="mini"><span>ยังต้องเรียน <b>{a.credits_to_graduate}</b></span><span>เทอมที่เหลือ <b>{a.terms_left.filter(t => !t.endsWith('/S')).length}</b></span>
        {a.must_retake.length > 0 && <span className="warn-text">ต้องเรียนซ้ำ <b>{a.must_retake.join(', ')}</b></span>}</div>
    </div>}
    {unresolved.length > 0 && !st.confirmed && <div className="need-info">
      <p className="eyebrow">NEED_INFO · ข้อมูลที่ระบบยืนยันไม่ได้</p>
      {unresolved.map(u => {
        const key = `${u.record.index}.${u.field}`;
        const options = u.field === 'grade' ? GRADES : u.candidates;
        return <div key={key} className="fix">
          <p>{u.field === 'grade' ? 'เกรด' : 'รหัสวิชา'}ของ “{u.record.evidence || u.record.course_id}” ({u.record.term}): {u.reason}</p>
          <div className="choices">{options.map(o => <button key={o} className={choices[key] === o ? 'chosen' : ''} disabled={busy} onClick={() => setChoices({ ...choices, [key]: o })}>{o}</button>)}</div>
          {u.candidates.length > 0 && u.field === 'grade' && <small>ค่าที่อ่านได้ใกล้เคียง: {u.candidates.join(' หรือ ')}</small>}
        </div>;
      })}
    </div>}
    {!st.confirmed && <button className="primary wide" disabled={busy || !ready} onClick={confirm}>ข้อมูลถูกต้อง ยืนยันระเบียน →</button>}
    {view.goal && <div className="goal-now"><p className="eyebrow">เป้าหมายปัจจุบัน · v{view.goal.goal_version}</p>
      <p>{goalText(view.goal)}</p></div>}
    {a && Object.keys(a.category_deficits).length > 0 && <div className="deficits"><p className="eyebrow">หมวดที่ยังขาด (หน่วยกิต)</p>
      <ul>{Object.entries(a.category_deficits).map(([k, v]) => <li key={k}><span>{a.category_names[k] || k}</span><b>{v}</b></li>)}</ul></div>}
    <div className="record-list"><p className="eyebrow">รายวิชาที่เรียนแล้ว</p>
      {byTerm.map(([term, rs]) => <div key={term} className="term-records"><p className="term-name">{term}</p>
        {rs.map(r => <div key={r.index} className={`record ${r.unresolved.length && !st.confirmed ? 'flag' : ''}`}>
          <div><strong>{r.course_id}</strong><span>{r.name_th || r.evidence}</span></div>
          <span>{r.grade ?? '?'} · {r.credits ?? '?'} นก.</span>
        </div>)}
      </div>)}
    </div>
  </aside>;
}

function Busy({ view }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 500); return () => clearInterval(t); }, []);
  const last = view.progress?.[view.progress.length - 1];
  const since = view.turn_started ? Math.max(0, Math.round(now / 1000 - view.turn_started)) : null;
  return <div className="busy"><span className="spinner" />{last ? STEP_TH[last.step] || last.step : 'กำลังทำงาน'}…{since !== null && <small>{since} วินาที</small>}</div>;
}

function Chat({ view, busy, act }) {
  const [input, setInput] = useState('');
  const scroller = useRef(null);
  const cards = useMemo(() => Object.fromEntries(view.cards.map(c => [c.card_id, c])), [view.cards]);
  useEffect(() => { scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: 'smooth' }); }, [view.items.length, busy]);
  const send = (e) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput('');
    act(() => api.message(view.session_id, text));
  };
  const render = (it) => {
    if (it.kind === 'goal_card') return <GoalCard card={cards[it.data.card_id]} student={view.student} busy={busy}
      onDecide={(ok) => act(() => api.goal(view.session_id, it.data.card_id, ok))} />;
    if (it.kind === 'plan') return <PlanCard item={it} />;
    if (it.kind === 'blocker_card') return <BlockerCard card={cards[it.data.card_id]} item={it} busy={busy}
      onChoose={(kind) => act(() => api.blocker(view.session_id, it.data.card_id, kind))}
      onDecline={() => act(() => api.blocker(view.session_id, it.data.card_id, null, true))} />;
    if (it.kind === 'stop') return <StopCard item={it} />;
    if (it.kind === 'event') return null;
    return <p>{it.text}</p>;
  };
  return <section className="chat">
    <div className="chat-heading"><div><p className="eyebrow">ขั้นที่ 2 · คุยกับ GradPath</p><h2>บอกเป้าหมายของคุณ</h2></div></div>
    <div className="chat-scroll" ref={scroller} aria-live="polite">
      <div className="message agent"><div className="avatar">G</div><div className="bubble"><p>สวัสดีครับ ผม GradPath ตรวจระเบียนทางซ้ายแล้วกดยืนยัน จากนั้นบอกเป้าหมาย เช่น อยากเน้นด้านไหน อยากจบเมื่อไร หรือไม่อยากลงเกินกี่หน่วยกิตต่อเทอม</p></div></div>
      {view.items.map(it => it.kind === 'event'
        ? <div key={it.seq} className="event">{it.text}</div>
        : <div key={it.seq} className={`message ${it.role === 'student' ? 'student' : 'agent'} ${it.kind}`}>
          {it.role !== 'student' && <div className="avatar">{it.role === 'system' ? '!' : 'G'}</div>}
          <div className={`bubble ${['goal_card', 'plan', 'blocker_card', 'stop'].includes(it.kind) ? 'wide' : ''}`}>
            {it.kind === 'question' && <span className="tag">คำถามจากระบบ</span>}
            {it.kind === 'need_info' && <span className="tag warn">NEED_INFO</span>}
            {it.kind === 'decline' && <span className="tag">ปฏิเสธคำขอ</span>}
            {render(it)}
          </div>
        </div>)}
      {busy && <Busy view={view} />}
    </div>
    {view.error && <p className="error">{view.error}</p>}
    <form className="composer" onSubmit={send}>
      <input value={input} onChange={(e) => setInput(e.target.value)} disabled={busy}
        placeholder={view.student.confirmed ? 'พิมพ์เป้าหมายหรือคำตอบของคุณ…' : 'ยืนยันระเบียนทางซ้ายก่อน หรือพิมพ์เป้าหมายไว้ได้เลย…'} />
      <button type="submit" disabled={busy || !input.trim()} aria-label="ส่งข้อความ">↑</button>
    </form>
    <p className="composer-note">GradPath เป็นเครื่องมือช่วยวางแผน ตรวจกับอาจารย์ที่ปรึกษาก่อนลงทะเบียนจริง</p>
  </section>;
}

function OperatorPanel({ view }) {
  const [open, setOpen] = useState(false);
  const op = view.operator;
  if (!op) return null;
  const r = op.run_record;
  return <div className={`operator ${open ? 'open' : ''}`}>
    <button onClick={() => setOpen(!open)}>ผู้ดูแล {open ? '▾' : '▸'}</button>
    {open && <div className="op-body">
      <p><a href={`./#s=${view.session_id}`} target="_blank" rel="noreferrer">เปิดมุมมองผู้ทดสอบของ session นี้</a></p>
      <p>task {view.task_id || '-'} · fault {op.fault || '-'} · overlay {op.overlay ? 'yes' : 'no'} · state {view.state}</p>
      <p>build {r.git_commit} · {r.model}@{r.digest} · Ollama {r.ollama_version} · {r.gpu}</p>
      <p>snapshot {r.snapshot_id} {r.snapshot_hash} · test set {r.test_set_sha256?.slice(0, 12)}</p>
      <table><thead><tr><th>turn</th><th>outcome</th><th>s</th><th>llm</th><th>tools</th><th>rev</th></tr></thead>
        <tbody>{op.turns.map(t => <tr key={t.turn}><td>{t.turn}</td><td>{t.outcome}</td><td>{t.ended ? (t.ended - t.started).toFixed(1) : '…'}</td><td>{t.llm_calls}</td><td title={t.tools.join(', ')}>{t.tool_calls}</td><td>{t.revisions}</td></tr>)}</tbody></table>
      <p className="mono">{op.trace}</p>
    </div>}
  </div>;
}

export default function App() {
  const [view, setView] = useState(null);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);
  const [pending, setPending] = useState(false);
  const sessionId = view?.session_id;

  useEffect(() => {
    const poll = () => api.health().then(setHealth).catch(() => setHealth({ warm: { model: false } }));
    poll();
    const t = setInterval(poll, 5000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const id = sessionFromHash();
    if (id) api.get(id, OPERATOR).then(setView).catch(() => { window.location.hash = ''; });
  }, []);

  const refresh = useCallback(() => sessionId && api.get(sessionId, OPERATOR).then(setView), [sessionId]);
  useEffect(() => {
    if (!view?.busy) return;
    const t = setInterval(refresh, 600);
    return () => clearInterval(t);
  }, [view?.busy, refresh]);

  const act = async (fn) => {
    setPending(true);
    try { setView(await fn()); } catch (e) { setView(v => ({ ...v, error: e.message })); }
    finally { setPending(false); refresh(); }
  };
  const start = async (body) => {
    setError(null);
    try {
      const v = await api.create(body);
      window.location.hash = `s=${v.session_id}`;
      setView(OPERATOR ? v : { ...v, operator: undefined });
    } catch (e) { setError(e.message); }
  };
  const reset = () => { window.location.hash = ''; setView(null); };
  const busy = pending || !!view?.busy;

  return <div className="app-shell">
    <Topbar view={view} health={health} onNew={reset} />
    {!view ? <Start onStart={start} error={error} /> : <main className="layout">
      <RecordsPanel key={view.session_id} view={view} busy={busy} onConfirm={(resolve) => act(() => api.record(view.session_id, resolve, true))} />
      <Chat view={view} busy={busy} act={act} />
      <OperatorPanel view={view} />
    </main>}
  </div>;
}
