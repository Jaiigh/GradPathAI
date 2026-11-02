// Conversation cards: goal (first goal or a change), plan, blocker, stop. Every plan shown is the stored
// candidate that passed the final gate; the UI only renders it.
const FLAG_TH = {
  offering_unverified: 'ภาคที่เปิดสอนยังไม่ยืนยัน',
  prereqs_unverified: 'วิชาบังคับก่อนยังไม่ยืนยัน'
};
const FIELD_TH = {
  horizon_end: 'เทอมสุดท้ายของแผน', default_cap: 'เพดานหน่วยกิตต่อภาคปกติ', caps: 'เพดานรายเทอม',
  allow_summer: 'ภาคฤดูร้อน', must_take: 'วิชาที่ต้องลง', avoid: 'วิชาที่ไม่ลง'
};

const termLabel = (t) => {
  const [y, s] = t.split('/');
  return s === 'S' ? `ภาคฤดูร้อน ${y}` : `ภาค ${s}/${y}`;
};

export function goalText(g) {
  const caps = Object.entries(g.caps || {}).map(([t, c]) => `${t}: ${c}`).join(', ');
  return [`จบภาค ${g.horizon_end}`, `เพดาน ${g.default_cap || 22} หน่วยกิต${caps ? ` (${caps})` : ''}`,
    g.allow_summer ? 'ใช้ภาคฤดูร้อน' : 'ไม่ใช้ภาคฤดูร้อน', g.must_take?.length ? `ต้องลง ${g.must_take.join(', ')}` : null,
    g.avoid?.length ? `ไม่ลง ${g.avoid.join(', ')}` : null, g.interests?.length ? `สนใจ ${g.interests.join(', ')}` : null]
    .filter(Boolean).join(' · ');
}

function Status({ status }) {
  if (status === 'pending') return null;
  const text = { approved: 'อนุมัติแล้ว', declined: 'ไม่อนุมัติ', superseded: 'ถูกแทนด้วยข้อเสนอใหม่' }[status];
  return <span className={`card-status ${status}`}>{text}</span>;
}

function showValue(field, value, names) {
  if (field === 'allow_summer') return value ? 'ใช้' : 'ไม่ใช้';
  if (field === 'default_cap') return value ? `${value} หน่วยกิต` : '22 หน่วยกิต (สูงสุดตามระเบียบ)';
  if (field === 'caps') return Object.keys(value || {}).length ? Object.entries(value).map(([t, c]) => `${t}: ${c}`).join(', ') : '-';
  if (field === 'must_take' || field === 'avoid') return value?.length ? value.map(c => `${c} ${names?.[c] || ''}`).join(', ') : '-';
  return value || '-';
}

export function GoalCard({ card, student, busy, onDecide }) {
  const g = card.data.goal;
  const changed = new Set(card.data.changes.map(c => c.field));
  const initial = card.data.initial;
  const rows = [
    ['horizon_end', g.horizon_end === student.end_of_year4 ? `${g.horizon_end} (ปลายปี 4)` : g.horizon_end],
    ['default_cap', showValue('default_cap', g.default_cap)],
    ['caps', showValue('caps', g.caps)],
    ['allow_summer', showValue('allow_summer', g.allow_summer)],
    ['must_take', showValue('must_take', g.must_take, card.data.course_names)],
    ['avoid', showValue('avoid', g.avoid, card.data.course_names)]
  ];
  return <section className="card goal-card">
    <header>
      <div><p className="eyebrow">{initial ? 'ยืนยันเป้าหมาย' : `ขออนุมัติเปลี่ยนเป้าหมาย (v${card.data.from_version} → v${card.data.from_version + 1})`}</p>
        <strong>{initial ? 'ตรวจเป้าหมายก่อนวางแผน' : 'การเปลี่ยนเงื่อนไขสำคัญต้องได้รับอนุมัติจากคุณ'}</strong></div>
      <Status status={card.status} />
    </header>
    <dl className="goal-grid">
      {rows.map(([f, v]) => <div key={f} className={!initial && changed.has(f) ? 'changed' : ''}>
        <dt>{FIELD_TH[f]}</dt>
        <dd>{!initial && changed.has(f)
          ? <><s>{showValue(f, card.data.changes.find(c => c.field === f).from, card.data.course_names)}</s> → {v}</>
          : v}</dd>
      </div>)}
      <div><dt>ความสนใจ</dt><dd>{g.interests?.length ? g.interests.join(', ') : '-'}</dd></div>
    </dl>
    {card.data.ignored?.length > 0 && <p className="note warn">ไม่นำไปใช้: {card.data.ignored.map(i => `${i.field} = ${i.value}`).join(', ')} เกินเพดานตามระเบียบ (สูงสุด {card.data.ignored[0].max} หน่วยกิต) ต้องได้รับอนุมัติจากคณบดี GradPath จึงไม่ตั้งค่านี้</p>}
    {card.status === 'pending' && <div className="actions">
      <button className="primary" disabled={busy} onClick={() => onDecide(true)}>อนุมัติเป้าหมายนี้</button>
      <button className="ghost" disabled={busy} onClick={() => onDecide(false)}>ไม่อนุมัติ</button>
    </div>}
  </section>;
}

function Course({ item }) {
  if (item.slot) return <li className="slot">
    <span className="code">ช่องวิชา</span>
    <span className="name">{item.category_th}<small>{item.category_en} · เลือกวิชาเองภายหลัง</small></span>
    <span className="cr">{item.credits}</span>
  </li>;
  return <li>
    <span className="code">{item.course_id}</span>
    <span className="name">{item.name_th}<small>{item.name_en} · {item.category_th}</small>
      {item.flags.length > 0 && <span className="flags">{item.flags.map(f => <em key={f}>{FLAG_TH[f] || f}</em>)}</span>}
    </span>
    <span className="cr">{item.credits}</span>
  </li>;
}

export function PlanCard({ item }) {
  const p = item.data.plan;
  return <section className="card plan-card">
    <header>
      <div><p className="eyebrow">แผนการเรียนจนจบปี 4</p><strong><span className="tick">✓</span> ผ่านการตรวจขั้นสุดท้าย (final gate)</strong></div>
      <span className="meta">plan {p.plan_id} · goal v{p.goal_version} · record v{p.record_version}</span>
    </header>
    {item.text && <p className="explain">{item.text}</p>}
    <div className="terms">
      {p.terms.map(t => <div key={t.term} className={`term ${t.kind}`}>
        <div className="term-head"><strong>{termLabel(t.term)}</strong><span>{t.credits}/{t.cap} หน่วยกิต</span></div>
        {t.items.length ? <ul>{t.items.map((it, i) => <Course key={i} item={it} />)}</ul> : <p className="empty">ไม่ลงเรียน</p>}
      </div>)}
    </div>
    <footer>
      <span>หน่วยกิตรวมเมื่อจบแผน <b>{p.total_credits}</b> / 138</span>
      {p.warnings.length > 0 && <span className="note">ป้าย “ยังไม่ยืนยัน” หมายถึงข้อมูลภาคที่เปิดสอนหรือวิชาบังคับก่อนอนุมานจากแผนการศึกษา ไม่ใช่ข้อมูลทางการ ควรตรวจกับภาควิชาก่อนลงทะเบียน</span>}
    </footer>
  </section>;
}

function altText(a) {
  if (a.kind === 'raise_caps') return `เพิ่มเพดาน: ${Object.entries(a.caps).map(([t, c]) => `${t} เป็น ${c} หน่วยกิต`).join(', ')}`;
  if (a.kind === 'allow_summer') return 'เปิดให้ใช้ภาคฤดูร้อน';
  if (a.kind === 'extend_horizon') return `ขยายเวลาจบถึง ${a.horizon_end}`;
  return a.kind;
}

export function BlockerCard({ card, item, busy, onChoose, onDecline }) {
  const b = card.data;
  return <section className="card blocker-card">
    <header>
      <div><p className="eyebrow">Evidenced blocker</p><strong>เป้าหมายนี้จัดแผนไม่ได้ตามกฎหลักสูตร</strong></div>
      <Status status={card.status} />
    </header>
    {item.text && <p className="explain">{item.text}</p>}
    <p className="note">เงื่อนไขปัจจุบัน (goal v{b.goal_version}): {b.goal ? goalText(b.goal) : b.goal_summary}</p>
    <p className="note">solver ตรวจแล้วว่าทางเลือกต่อไปนี้ทำให้จัดแผนได้ การเลือกทางใดทางหนึ่งเป็นการเปลี่ยนเป้าหมายและต้องได้รับอนุมัติจากคุณ</p>
    <ul className="alts">
      {b.alternatives.map(a => <li key={a.kind}>
        <span>{altText(a)}</span>
        {card.status === 'pending' && <button className="primary small" disabled={busy} onClick={() => onChoose(a.kind)}>อนุมัติทางเลือกนี้</button>}
      </li>)}
      {b.alternatives.length === 0 && <li>ไม่พบทางเลือกที่ทำให้จัดแผนได้</li>}
    </ul>
    {card.status === 'pending' && <div className="actions"><button className="ghost" disabled={busy} onClick={onDecline}>คงเป้าหมายเดิม</button></div>}
  </section>;
}

export function StopCard({ item }) {
  return <section className="card stop-card">
    <header><div><p className="eyebrow">STOP_UNVERIFIED</p><strong>ยังยืนยันแผนไม่ได้</strong></div></header>
    <p>{item.text}</p>
  </section>;
}
