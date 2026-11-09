import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from './api.js';
import { BlockerCard, GoalCard, NextSteps, PlanCard, StopCard, goalText } from './cards.jsx';

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
      {ready ? 'โมเดลพร้อม' : ready === false ? 'โมเดลไม่พร้อม · ยังอัปโหลดได้' : 'กำลังเตรียมโมเดล · ยังอัปโหลดได้'} <i>·</i> ทำงานบนเครื่องนี้เท่านั้น
      {view?.student.source_kind === 'persona' && <><i>·</i> ข้อมูลนิสิตจำลอง</>}</div>
    {view && <span className="who">{view.persona_label}{view.task_id ? ` · ${view.task_id}` : ''}</span>}
    {view && <button className="new-session" onClick={onNew}>เริ่ม session ใหม่</button>}
  </header>;
}

function UploadReport({ onUploaded, sessionId, disabled = false }) {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const submit = async (e) => {
    e.preventDefault();
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { setError('ไฟล์ต้องมีขนาดไม่เกิน 10 MB'); return; }
    setUploading(true); setError('');
    try { onUploaded(await api.upload(file, sessionId)); }
    catch (err) { setError(err.message); }
    finally { setUploading(false); }
  };
  return <form className="upload-report" onSubmit={submit} aria-busy={uploading}>
    <label className="upload-label">{sessionId ? 'เลือก grade report ฉบับใหม่' : 'อัปโหลด CR60 / Grade report'}
      <input type="file" accept="application/pdf,.pdf" disabled={disabled || uploading}
        onChange={e => { setFile(e.target.files?.[0] || null); setError(''); }} />
    </label>
    <p className="muted">PDF ต้นฉบับที่เลือกข้อความได้ · สูงสุด 10 MB / 20 หน้า · ยังไม่รองรับภาพสแกน</p>
    {sessionId && <p className="note">รายงานใหม่จะแทนที่ประวัติเดิมทั้งฉบับ ต้องตรวจข้อมูลและเป้าหมายอีกครั้ง แผนเดิมจะถูกระบุว่าไม่ใช่แผนปัจจุบัน</p>}
    <button className="primary" disabled={!file || disabled || uploading}>
      {uploading ? 'กำลังอ่านรายวิชาทุกหน้า…' : sessionId ? 'แทนที่รายงานและตรวจข้อมูล' : 'อ่านรายงานผลการเรียน →'}
    </button>
    {error && <p className="error" role="alert">{error}</p>}
    <p className="note">ไฟล์และประวัติการเรียนเก็บบนเครื่องนี้ ไม่ส่ง PDF ให้โมเดลหรือบริการภายนอก</p>
  </form>;
}

function Start({ onStart, onUploaded, error }) {
  const [personas, setPersonas] = useState([]);
  const [tasks, setTasks] = useState([]);
  useEffect(() => {
    if (OPERATOR) api.personas().then(setPersonas).catch(() => {});
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
      <p className="lead">เริ่มจากรายงานผลการเรียนของคุณ ตรวจรายวิชาทุกเทอมและยืนยันข้อมูล แล้วบอกเป้าหมายเพื่อจัดแผนที่ผ่านการตรวจตามข้อมูลหลักสูตร</p>
      {error && <p className="error">{error}</p>}
    </section>
    <UploadReport onUploaded={onUploaded} />
    {OPERATOR && <section>
      <h2 className="section-title">ผู้ดูแล: เลือก Task</h2>
      {ROUNDS.map(([label, ids]) => <div key={label} className="task-group"><p className="eyebrow">{label}</p>
        <div className="task-grid">{ids.map(id => taskButton(byId[id]))}</div></div>)}
      <div className="task-group"><p className="eyebrow">ทุก task</p>
        <div className="task-grid">{tasks.map(taskButton)}</div></div>
    </section>}
    {OPERATOR && <section>
      <h2 className="section-title">{OPERATOR ? 'โหมดสาธิต: เลือกนิสิตจำลอง' : 'เลือกนิสิตจำลอง'}</h2>
      <div className="task-grid">{personas.map(p => <button key={p.name} className="task" onClick={() => onStart({ persona: p.name })}>
        <b>{p.label}</b><span>เทอมถัดไป {p.next_term}</span><small>จบปี 4 ภาค {p.end_of_year4}</small>
      </button>)}</div>
    </section>}
  </main>;
}

function RecordsPanel({ view, busy, onConfirm, onUploaded, onInternship }) {
  const [choices, setChoices] = useState({});
  const st = view.student;
  const [internshipChecked, setInternshipChecked] = useState(view.internship?.attested || false);
  useEffect(() => setInternshipChecked(view.internship?.attested || false), [view.internship?.attested]);
  const [entryYear, setEntryYear] = useState(String(st.entry_year));
  const [nextTerm, setNextTerm] = useState(st.next_term);
  const [profileConfirmed, setProfileConfirmed] = useState(false);
  const report = view.report;
  const categoryNames = Object.fromEntries((view.categories || []).map(c => [c.id, c.name]));
  const byTerm = useMemo(() => {
    const out = {};
    view.records.forEach(r => { (out[r.term] ||= []).push(r); });
    return Object.entries(out);
  }, [view.records]);
  const unresolved = view.records.flatMap(r => r.unresolved.map(u => ({ ...u, record: r })));
  const ready = unresolved.every(u => choices[`${u.record.index}.${u.field}`]) &&
    (!report || (profileConfirmed && /^\d{4}\/[12S]$/.test(nextTerm) && Number(entryYear) >= 2566));
  const confirm = () => onConfirm(unresolved.map(u => ({ record_index: u.record.index, field: u.field, value: choices[`${u.record.index}.${u.field}`] })),
    report ? { entry_year: Number(entryYear), next_term: nextTerm, confirmed: profileConfirmed } : undefined);
  const a = view.audit;
  return <aside className="records">
    <div className="panel-heading">
      <div><p className="eyebrow">ขั้นที่ 1</p><h2>ระเบียนการเรียน</h2></div>
      <span className={`pill ${st.confirmed ? 'ok' : unresolved.length ? 'warn' : ''}`}>{st.confirmed ? `ยืนยันแล้ว · v${st.record_version}` : unresolved.length ? 'ต้องตรวจข้อมูล' : 'รอยืนยัน'}</span>
    </div>
    <p className="muted">ปีเข้า {st.entry_year} · เทอมถัดไป {st.next_term} · ปลายปี 4 คือ {st.end_of_year4}</p>
    {report && <div className="report-summary">
      <p><strong>{report.reported_earned} หน่วยกิตตามรายงาน</strong> · GPAX {report.gpax.toFixed(2)}</p>
      <p className="muted">อ่าน {view.records.length} รายการ · {report.terms.length} เทอม · {report.pages} หน้า<br />รายงาน ณ {report.as_of || '-'} · ผลการเรียนถึง {report.last_term}</p>
      <a href={`/api/sessions/${view.session_id}/report`} target="_blank" rel="noreferrer">เปิด PDF ต้นฉบับ ↗</a>
      <p className="note">หน่วยกิตที่ได้ตามรายงานยังไม่เท่ากับหน่วยกิตที่จัดเข้าหมวดเพื่อจบการศึกษา ต้องยืนยันหมวดวิชาที่ระบบยังไม่ทราบก่อน</p>
      {report.reconciliation_errors.length > 0
        ? <div className="error" role="alert"><strong>ยอดหน่วยกิตยังไม่ตรงกับรายงาน</strong><ul>{report.reconciliation_errors.map(e => <li key={e}>{e}</li>)}</ul><p>ตรวจเกรดที่ไม่ชัดเจนหรืออัปโหลดรายงานที่ครบทุกหน้า</p></div>
        : <p className="reconciled">✓ ยอดหน่วยกิตรายเทอมและสะสมตรงกับ PDF</p>}
    </div>}
    {report && !st.confirmed && <div className="profile-review">
      <label>ปีที่เข้าศึกษา (พ.ศ.)<input type="number" min="2566" value={entryYear} disabled={busy} onChange={e => setEntryYear(e.target.value)} /></label>
      <label>เริ่มวางแผนเทอมใด (เช่น 2569/1)<input value={nextTerm} disabled={busy} onChange={e => setNextTerm(e.target.value.trim())} /></label>
      <p className="note">วันที่ออกรายงานไม่ใช่เทอมล่าสุด ระบบเสนอเทอมถัดจากผลการเรียนที่อ่านได้ หากมีผลการเรียนใหม่กว่านี้ให้อัปโหลดฉบับล่าสุด วิชาที่ยังไม่ออกเกรดจะไม่นับว่าผ่านแล้ว</p>
      <label className="confirm-profile"><input type="checkbox" checked={profileConfirmed} disabled={busy} onChange={e => setProfileConfirmed(e.target.checked)} />ฉันใช้หลักสูตร CP 2566 และตรวจแล้วว่าประวัติผลการเรียนครบก่อนเทอมที่เลือก</label>
    </div>}
    {view.internship && <div className="profile-review">
      <strong>การฝึกงานทางวิศวกรรม · 2100301</strong>
      <p>{view.internship.message}</p>
      {view.internship.reported ? <p>✓ พบผลผ่านในรายงานแล้ว ไม่ต้องยืนยันซ้ำ</p> : <>
        <label className="confirm-profile"><input type="checkbox" checked={internshipChecked} disabled={busy} onChange={e => setInternshipChecked(e.target.checked)} />ฉันลงทะเบียนวิชา 2100301 และผ่านการฝึกงานแล้ว</label>
        <p className="note">ข้อมูลนี้เป็นการยืนยันของคุณ แยกจาก CR60 ไม่แก้ยอดหน่วยกิตหรือ GPAX ใน PDF หากยังไม่ผ่านให้เว้นช่องนี้ไว้</p>
        <button disabled={busy || internshipChecked === view.internship.attested} onClick={() => onInternship(internshipChecked)}>บันทึกสถานะฝึกงาน</button>
        {view.internship.attested && <p>✓ คุณยืนยันว่าผ่านแล้ว · นับเพิ่ม {view.internship.supplemental_credits} หน่วยกิตตามแผนหลักสูตร โดยไม่นับซ้ำกับ PDF</p>}
      </>}
    </div>}
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
        const fieldName = { grade: 'เกรด', course_id: 'รหัสวิชา', category: 'หมวดวิชา', credits: 'หน่วยกิต' }[u.field] || u.field;
        return <div key={key} className="fix">
          <p><strong>{u.record.course_id} {u.record.title || u.record.name_th}</strong><br />{fieldName} · {u.record.term}{u.record.page ? ` · หน้า ${u.record.page}` : ''}: {u.field === 'category' ? 'รายงานไม่ได้ระบุหมวดวิชา กรุณาเลือกตามข้อมูลรายวิชาที่คุณยืนยันแล้ว หากยังไม่แน่ใจให้เว้นไว้ก่อน' : u.reason}</p>
          {u.field === 'category'
            ? <label className="category-choice">หมวดของ {u.record.course_id}<select aria-label={`หมวดของ ${u.record.course_id}`} value={choices[key] || ''} disabled={busy} onChange={e => setChoices({ ...choices, [key]: e.target.value })}>
                <option value="">ยังไม่ทราบ / เลือกหมวดที่ยืนยันแล้ว</option>
                {options.map(o => <option key={o} value={o}>{categoryNames[o] || o}</option>)}
              </select></label>
            : <div className="choices">{options.map(o => <button key={o} className={choices[key] === o ? 'chosen' : ''} disabled={busy} onClick={() => setChoices({ ...choices, [key]: o })}>{o}</button>)}</div>}
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
          <div><strong>{r.course_id}</strong><span>{r.title || r.name_th || r.evidence}</span>
            {r.page && <a className="evidence-link" href={`/api/sessions/${view.session_id}/report#page=${r.page}`} target="_blank" rel="noreferrer">ต้นฉบับ หน้า {r.page}</a>}
            <span className="record-category">{r.category_names?.length
              ? `${r.category_names.length > 1 ? 'นับได้ใน' : 'หมวด'}: ${r.category_names.join(' / ')}${r.category_names.length > 1 ? ' (นับเพียงหมวดเดียว)' : ''}`
              : 'หมวด: ยังไม่ยืนยัน'}</span>
          </div>
          <span>{r.grade ?? '?'} · {r.credits ?? '?'} นก.</span>
        </div>)}
      </div>)}
    </div>
    {report && <details className="replace-report"><summary>อัปโหลดรายงานฉบับใหม่</summary><UploadReport sessionId={view.session_id} onUploaded={onUploaded} disabled={busy} /></details>}
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
    const last = it.seq === view.items[view.items.length - 1]?.seq;
    if (it.kind === 'stop') return <StopCard item={it} busy={busy} operator={OPERATOR}
      canRetry={last && view.outcome === 'STOP_UNVERIFIED' && it.data.retry}
      onRetry={(clear) => act(() => api.retry(view.session_id, clear))} />;
    if (it.kind === 'next_steps') return <NextSteps item={it} busy={busy} active={last && view.outcome === 'NEED_INFO'}
      onDefer={() => act(() => api.defer(view.session_id))} />;
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
          <div className={`bubble ${['goal_card', 'plan', 'blocker_card', 'stop', 'next_steps'].includes(it.kind) ? 'wide' : ''}`}>
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
    let active = true;
    const restore = () => {
      const id = sessionFromHash();
      if (!id) { setView(null); return; }
      api.get(id, OPERATOR).then(v => {
        if (active && sessionFromHash() === id) setView(v);
      }).catch(() => { if (active && sessionFromHash() === id) window.location.hash = ''; });
    };
    restore();
    window.addEventListener('hashchange', restore);
    return () => { active = false; window.removeEventListener('hashchange', restore); };
  }, []);

  const refresh = useCallback(() => sessionId && api.get(sessionId, OPERATOR).then(v => {
    if (sessionFromHash() === sessionId) setView(v);
  }).catch(() => {}), [sessionId]);
  useEffect(() => {
    if (!view?.busy) return;
    const t = setInterval(refresh, 600);
    return () => clearInterval(t);
  }, [view?.busy, refresh]);

  const act = async (fn) => {
    setPending(true);
    try {
      const next = await fn();
      if (sessionFromHash() === sessionId) setView(next);
    } catch (e) { if (sessionFromHash() === sessionId) setView(v => v && ({ ...v, error: e.message })); }
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
  const uploaded = (v) => { window.location.hash = `s=${v.session_id}`; setView(v); setError(null); };
  const reset = () => { window.location.hash = ''; setView(null); };
  const busy = pending || !!view?.busy;

  return <div className="app-shell">
    <Topbar view={view} health={health} onNew={reset} />
    {!view ? <Start onStart={start} onUploaded={uploaded} error={error} /> : <main className="layout">
      <RecordsPanel key={`${view.session_id}:${view.student.record_version}`} view={view} busy={busy} onUploaded={uploaded}
        onInternship={completed => act(() => api.internship(view.session_id, completed))}
        onConfirm={(resolve, profile) => act(() => api.record(view.session_id, resolve, true, profile))} />
      <Chat view={view} busy={busy} act={act} />
      <OperatorPanel view={view} />
    </main>}
  </div>;
}
