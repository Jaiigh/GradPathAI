import { useRef, useState } from 'react';

const sampleTranscript = {
  name: 'Sample transcript.pdf',
  courses: 13,
  creditsTaken: 39,
  creditsApplied: 39,
  creditsRemaining: 24,
  cumulativeGpa: '3.48',
  status: 'Verified',
  records: [
    ['CSC-101', 'Computing Fundamentals', 'A', '3'],
    ['MAT-120', 'Discrete Mathematics', 'B+', '3'],
    ['WRT-101', 'Academic Writing', 'A−', '3'],
    ['DES-110', 'Design Thinking', 'A', '3']
  ]
};

function Message({ role = 'assistant', children, time }) {
  return <div className={`message ${role}`}>
    {role === 'assistant' && <div className="avatar" aria-hidden="true">G</div>}
    <div>
      <div className="bubble">{children}</div>
      {time && <p className="message-time">{time}</p>}
    </div>
  </div>;
}

function UploadIcon() {
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V3m0 0 4 4m-4-4L8 7M5 14v5h14v-5" /></svg>;
}

function App() {
  const fileInput = useRef(null);
  const [transcript, setTranscript] = useState(null);
  const [messages, setMessages] = useState([{ role: 'assistant', content: 'Hi — I’m GradPath. Upload your transcript and I’ll turn what you’ve already completed into a clear next step.', time: 'NOW' }]);
  const [input, setInput] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [summaryOpen, setSummaryOpen] = useState(false);

  const addTranscript = (file) => {
    if (!file) return;
    const details = { ...sampleTranscript, name: file.name || sampleTranscript.name };
    setTranscript(details);
    setMessages(current => [...current,
      { role: 'user', content: `I uploaded ${details.name}.` },
      { role: 'assistant', content: 'I’ve read the transcript locally and found a consistent academic record. Here is the credit summary before we plan anything further.', summary: true, time: 'JUST NOW' }
    ]);
    setSummaryOpen(true);
  };

  const useSample = () => addTranscript({ name: 'Sample transcript.pdf' });
  const sendMessage = (event) => {
    event.preventDefault();
    const text = input.trim();
    if (!text) return;
    setMessages(current => [...current,
      { role: 'user', content: text },
      { role: 'assistant', content: 'That’s helpful. I’ll treat it as a preference, not a requirement. What completion date and maximum credits per term feel realistic for you?' }
    ]);
    setInput('');
  };

  const confirmSummary = () => {
    setSummaryOpen(false);
    setMessages(current => [...current, { role: 'assistant', content: 'Great — your records are now confirmed for this session. Tell me what you want to study next, or ask me to build a two-term path.' }]);
  };

  return <div className="app-shell">
    <header className="topbar">
      <a className="brand" href="#top">GRADPATH<span>•</span></a>
      <div className="privacy"><span className="privacy-dot" />PRIVATE SESSION <i>·</i> TRANSCRIPT STAYS ON YOUR DEVICE</div>
      <button className="new-session" onClick={() => window.location.reload()}>New session</button>
    </header>

    <main id="top" className="layout">
      <aside className="transcript-panel" aria-labelledby="records-heading">
        <div className="panel-heading">
          <div><p className="eyebrow">Step 01</p><h1 id="records-heading">Your records</h1></div>
          <span className={`state-pill ${transcript ? 'ready' : ''}`}>{transcript ? 'READY' : 'WAITING'}</span>
        </div>

        {!transcript ? <>
          <p className="panel-copy">Start with the most complete transcript you have. GradPath uses it only in this browser session to establish your academic starting point.</p>
          <button
            className={`dropzone ${isDragging ? 'dragging' : ''}`}
            onClick={() => fileInput.current?.click()}
            onDragOver={(event) => { event.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={(event) => { event.preventDefault(); setIsDragging(false); addTranscript(event.dataTransfer.files[0]); }}
          >
            <span className="upload-icon"><UploadIcon /></span>
            <strong>Drop transcript here</strong>
            <span>or choose a PDF, CSV, or text file</span>
          </button>
          <input ref={fileInput} className="visually-hidden" type="file" accept=".pdf,.csv,.txt" onChange={(event) => addTranscript(event.target.files[0])} />
          <button className="sample-link" onClick={useSample}>Use a sample transcript instead <span>→</span></button>
          <p className="secure-note"><span>⌁</span> No academic data is sent to a server in this prototype.</p>
        </> : <>
          <div className="uploaded-file"><div className="file-mark">PDF</div><div><strong>{transcript.name}</strong><span>Local file · {transcript.courses} courses detected</span></div><button aria-label="Replace transcript" onClick={() => setTranscript(null)}>×</button></div>
          <section className="left-summary" aria-label="Transcript summary">
            <p className="eyebrow">Academic snapshot</p>
            <div className="large-credit"><strong>{transcript.creditsTaken}</strong><span>credits<br />taken</span></div>
            <div className="mini-stats"><div><span>Applied</span><strong>{transcript.creditsApplied}</strong></div><div><span>Remaining</span><strong>{transcript.creditsRemaining}</strong></div><div><span>GPA</span><strong>{transcript.cumulativeGpa}</strong></div></div>
          </section>
          <div className="record-list"><p className="eyebrow">Extracted records</p>{transcript.records.map(([id, name, grade, credits]) => <div className="record" key={id}><div><strong>{id}</strong><span>{name}</span></div><span>{grade} · {credits} cr</span></div>)}</div>
          <button className="replace-link" onClick={() => setTranscript(null)}>Replace transcript</button>
        </>}
      </aside>

      <section className="chat-panel" aria-labelledby="chat-heading">
        <div className="chat-heading"><div><p className="eyebrow">Planning conversation</p><h2 id="chat-heading">Let’s map your next move.</h2></div><div className="online"><span />GradPath is ready</div></div>
        <div className="chat-scroll" aria-live="polite">
          <div className="conversation-label">TODAY</div>
          {messages.map((message, index) => <Message key={`${message.content}-${index}`} role={message.role} time={message.time}>
            <p>{message.content}</p>
            {message.summary && transcript && <CreditSummary transcript={transcript} open={summaryOpen} onConfirm={confirmSummary} />}
          </Message>)}
        </div>
        <form className="composer" onSubmit={sendMessage}>
          <label className="visually-hidden" htmlFor="message">Message GradPath</label>
          <input id="message" value={input} onChange={(event) => setInput(event.target.value)} placeholder={transcript ? 'Tell GradPath about your goal…' : 'Upload a transcript to begin…'} disabled={!transcript} />
          <button type="submit" disabled={!transcript || !input.trim()} aria-label="Send message">↑</button>
        </form>
        <p className="composer-note">GradPath is advisory. Verify plans with your academic advisor.</p>
      </section>
    </main>
  </div>;
}

function CreditSummary({ transcript, open, onConfirm }) {
  return <section className="credit-summary">
    <div className="summary-title"><div><span className="summary-check">✓</span><strong>Transcript summary</strong></div><span className="match">RECORDS MATCH</span></div>
    <div className="credit-figures"><div><span>Credits taken</span><strong>{transcript.creditsTaken}</strong><small>across {transcript.courses} courses</small></div><div><span>Credits left</span><strong>{transcript.creditsRemaining}</strong><small>to complete this sample program</small></div></div>
    <div className="progress-track"><span style={{ width: `${(transcript.creditsApplied / (transcript.creditsApplied + transcript.creditsRemaining)) * 100}%` }} /></div>
    <p><b>{transcript.creditsApplied} of {transcript.creditsApplied + transcript.creditsRemaining} credits</b> are accounted for. Your foundational computing and mathematics prerequisites are complete.</p>
    {open && <button className="confirm-button" onClick={onConfirm}>These records look right <span>→</span></button>}
  </section>;
}

export default App;
