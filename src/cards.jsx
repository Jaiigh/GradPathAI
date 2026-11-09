// Conversation cards: goal (first goal or a change), plan, blocker, stop. Every plan shown is the stored
// candidate that passed the final gate; the UI only renders it.
const FLAG_TH = {
  fixed_year3_summer: 'บังคับซัมเมอร์ปี 3 เท่านั้น · เปลี่ยนเทอมไม่ได้',
  offering_unverified: 'ภาคที่เปิดสอนยังไม่ยืนยัน',
  prereqs_unverified: 'วิชาบังคับก่อนยังไม่ยืนยัน'
};
const REASON_TH = {
  retake: () => 'เรียนซ้ำ (เคยไม่ผ่าน)', must_take: () => 'คุณระบุให้ลง', required: () => 'วิชาบังคับ',
  interest: (item, interests) => `ตรงความสนใจ${interests?.length ? `: ${interests.join(', ')}` : ''}`,
  category: (item) => `นับในหมวด ${item.category_th}`
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

function Course({ item, interests }) {
  if (item.slot) return <li className="slot">
    <span className="code">ช่องวิชา</span>
    <span className="name">{item.category_th}<small>{item.category_en} · เลือกวิชาเองภายหลัง</small></span>
    <span className="cr">{item.credits}</span>
  </li>;
  return <li>
    <span className="code">{item.course_id}</span>
    <span className="name">{item.name_th}<small>{item.name_en} · {item.category_th}</small>
      {item.reasons?.length > 0 && <span className="reasons">{item.reasons.map(r => <em key={r} className={r}>{REASON_TH[r]?.(item, interests) || r}</em>)}</span>}
      {item.flags.length > 0 && <span className="flags">{item.flags.map(f => <em key={f}>{FLAG_TH[f] || f}</em>)}</span>}
    </span>
    <span className="cr">{item.credits}</span>
  </li>;
}

export function PlanCard({ item }) {
  const p = item.data.plan;
  return <section className="card plan-card">
    <header>
      <div><p className="eyebrow">แผนการเรียนตามเป้าหมาย</p><strong>{item.data.stale ? 'แผนเก่า · ระเบียนหรือกฎหลักสูตรเปลี่ยนแล้ว' : <><span className="tick">✓</span> ผ่านการตรวจขั้นสุดท้าย (final gate)</>}</strong></div>
      <span className="meta">plan {p.plan_id} · goal v{p.goal_version} · record v{p.record_version}</span>
    </header>
    {item.text && <p className="explain">{item.text}</p>}
    <div className="terms">
      {p.terms.map(t => <div key={t.term} className={`term ${t.kind}`}>
        <div className="term-head"><strong>{termLabel(t.term)}</strong><span>{t.credits}/{t.cap} หน่วยกิต</span></div>
        {t.items.length ? <ul>{t.items.map((it, i) => <Course key={i} item={it} interests={p.interests} />)}</ul> : <p className="empty">ไม่ลงเรียน</p>}
      </div>)}
    </div>
    {p.categories?.length > 0 && <details className="cat-table" open>
      <summary>ยอดหน่วยกิตรายหมวด ก่อนและหลังแผน</summary>
      <table><thead><tr><th>หมวด</th><th>ขั้นต่ำ</th><th>ก่อนแผน</th><th>หลังแผน</th></tr></thead>
        <tbody>{p.categories.map(c => <tr key={c.id} className={c.after >= c.min ? 'met' : 'short'}>
          <td>{c.name_th}</td><td>{c.min}</td><td>{c.before}</td><td>{c.after} {c.after >= c.min ? '✓' : ''}</td>
        </tr>)}</tbody></table>
      <p className="note">แต่ละวิชานับได้เพียงหมวดเดียว ยอด “หลังแผน” คือการจัดสรรที่ตัวตรวจแผน (validator) ใช้</p>
    </details>}
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
    {b.alternatives.length > 0 ? <table className="alt-table">
      <thead><tr><th>ทางเลือก</th><th>เทอมสุดท้าย</th><th>เพดานหน่วยกิต</th><th>ภาคฤดูร้อน</th><th></th></tr></thead>
      <tbody>
        <tr className="current"><td>เป้าหมายเดิม (จัดแผนไม่ได้)</td><td>{b.goal?.horizon_end}</td><td>{b.goal?.default_cap || 22}</td><td>{b.goal?.allow_summer ? 'ใช้' : 'ไม่ใช้'}</td><td /></tr>
        {b.alternatives.map(a => <tr key={a.kind}>
          <td>{altText(a)}</td>
          <td className={a.kind === 'extend_horizon' ? 'diff' : ''}>{a.kind === 'extend_horizon' ? a.horizon_end : b.goal?.horizon_end}</td>
          <td className={a.kind === 'raise_caps' ? 'diff' : ''}>{a.kind === 'raise_caps' ? Object.entries(a.caps).map(([t, c]) => `${t}: ${c}`).join(', ') : (b.goal?.default_cap || 22)}</td>
          <td className={a.kind === 'allow_summer' ? 'diff' : ''}>{a.kind === 'allow_summer' || b.goal?.allow_summer ? 'ใช้' : 'ไม่ใช้'}</td>
          <td>{card.status === 'pending' && <button className="primary small" disabled={busy} onClick={() => onChoose(a.kind)}>อนุมัติทางเลือกนี้</button>}</td>
        </tr>)}
      </tbody></table> : <ul className="alts"><li>ไม่พบทางเลือกที่ทำให้จัดแผนได้</li></ul>}
    {card.status === 'pending' && <div className="actions"><button className="ghost" disabled={busy} onClick={onDecline}>คงเป้าหมายเดิม</button></div>}
  </section>;
}

export function StopCard({ item, canRetry, busy, operator, onRetry }) {
  return <section className="card stop-card">
    <header><div><p className="eyebrow">STOP_UNVERIFIED</p><strong>ยังยืนยันแผนไม่ได้</strong></div></header>
    <p>{item.text}</p>
    {canRetry && <div className="actions">
      <button className="primary" disabled={busy} onClick={() => onRetry(false)}>ลองใหม่จากจุดเดิม</button>
      {operator && <button className="ghost" disabled={busy} onClick={() => onRetry(true)}>ผู้ดูแล: ปิด fault แล้วลองใหม่</button>}
      <span className="note">ใช้ระเบียนและเป้าหมายเดิม ไม่ต้องพิมพ์ใหม่</span>
    </div>}
  </section>;
}

export function NextSteps({ item, active, busy, onDefer }) {
  return <section className="card next-steps">
    <header><div><p className="eyebrow">NEED_INFO · ทำอะไรต่อได้</p><strong>{item.data.missing?.length ? `ข้อมูลของ ${item.data.missing.join(', ')} ยังไม่พอสำหรับวางแผน` : 'ยังขาดข้อมูลสำหรับวางแผน'}</strong></div></header>
    {item.text.split('\n').map((line, i) => <p key={i}>{line}</p>)}
    {active && item.data.can_defer && <div className="actions">
      <button className="primary" disabled={busy} onClick={onDefer}>วางแผนส่วนที่เหลือไปก่อน</button>
    </div>}
  </section>;
}
