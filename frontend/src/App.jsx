import { useState } from 'react'

// The base URL of your FastAPI backend. Everything POSTs here.
const API = 'http://localhost:8000'

function App() {
  // ---------------------------------------------------------------------------
  // STATE
  //
  // useState(initialValue) gives you back a PAIR: [currentValue, setterFn].
  // - The first item is the value React remembers between renders.
  // - The second is the ONLY correct way to change it. Calling the setter tells
  //   React "this data changed, re-run App() and repaint the parts that use it."
  // Never mutate the value directly (e.g. sentences.push(...)) — React won't
  // notice and the screen won't update. Always call the setter with a new value.
  // ---------------------------------------------------------------------------

  // The three inputs at the top of the form.
  const [concept, setConcept] = useState('')      // text, e.g. "把-construction"
  const [count, setCount] = useState(3)           // number of sentences to make
  const [hskLevel, setHskLevel] = useState('')    // optional; '' means "omit it"

  // The English sentences the backend returns from /generate.
  // Starts as an empty array; becomes ["He ate...", "She will..."] after fetch.
  const [sentences, setSentences] = useState([])

  // The Chinese translations YOU type. This is an array kept in the same order
  // as `sentences`: translations[0] is your answer to sentences[0], and so on.
  const [translations, setTranslations] = useState([])

  // The two-score feedback the backend returns from /feedback.
  // Each item looks like { concept_pass, concept_note, other_errors,
  // corrected_translation } — the exact shape from your FeedbackItem model.
  const [feedback, setFeedback] = useState([])

  // ---------------------------------------------------------------------------
  // ACTION 1: Generate sentences
  //
  // `async` lets us use `await` inside. `await` pauses this function (without
  // freezing the browser) until the network request comes back.
  // ---------------------------------------------------------------------------
  async function handleGenerate() {
    // fetch(url, options) sends the HTTP request. We build a POST with a JSON
    // body whose keys match your GenerateRequest model exactly: concept, count,
    // hsk_level.
    const response = await fetch(`${API}/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }, // "the body is JSON"
      body: JSON.stringify({
        concept: concept,
        count: Number(count), // inputs give strings; your model wants an int
        // hsk_level is optional. If the box is empty we send null, which your
        // backend treats as "omitted / use natural vocabulary".
        hsk_level: hskLevel === '' ? null : Number(hskLevel),
      }),
    })

    // response.json() reads the body and parses it from JSON text into a real
    // JS object. It's also async, so we await it. `data` is { sentences: [...] }.
    const data = await response.json()

    // Save the returned sentences into state -> triggers a re-render -> the list
    // below appears.
    setSentences(data.sentences)

    // Reset the answer boxes to one empty string per sentence, same length as
    // the sentences array. Array(n).fill('') makes ['', '', ''] for 3 sentences.
    setTranslations(Array(data.sentences.length).fill(''))

    // Clear any feedback from a previous round.
    setFeedback([])
  }

  // ---------------------------------------------------------------------------
  // Update ONE translation box without disturbing the others.
  //
  // React state must be replaced, not mutated, so we make a COPY of the array,
  // change the one slot, then set the copy. [...translations] is a shallow copy.
  // ---------------------------------------------------------------------------
  function handleTranslationChange(index, value) {
    const next = [...translations]
    next[index] = value
    setTranslations(next)
  }

  // ---------------------------------------------------------------------------
  // ACTION 2: Get feedback
  //
  // Sends the concept, the sentences, and your translations back together so the
  // backend can grade each pair. Body keys match your FeedbackRequest model.
  // ---------------------------------------------------------------------------
  async function handleGetFeedback() {
    const response = await fetch(`${API}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        concept: concept,
        sentences: sentences,
        translations: translations,
      }),
    })

    const data = await response.json() // { feedback: [ {...}, {...} ] }
    setFeedback(data.feedback)
  }

  // ---------------------------------------------------------------------------
  // RENDER
  //
  // This returns the HTML (JSX). React re-runs App() and re-renders this every
  // time a setter changes state. {curly braces} drop JS values into the markup.
  // ---------------------------------------------------------------------------
  return (
    <div>
      <h1>Grammar Drill</h1>

      {/* --- The input form --- */}
      <div>
        <label>
          Concept:{' '}
          <input
            type="text"
            value={concept}
            // Every keystroke fires onChange; e.target.value is the box's text.
            // We push it into state so `concept` always mirrors what's on screen.
            onChange={(e) => setConcept(e.target.value)}
          />
        </label>
      </div>

      <div>
        <label>
          Count:{' '}
          <input
            type="number"
            value={count}
            onChange={(e) => setCount(e.target.value)}
          />
        </label>
      </div>

      <div>
        <label>
          HSK level (optional):{' '}
          <input
            type="number"
            value={hskLevel}
            onChange={(e) => setHskLevel(e.target.value)}
          />
        </label>
      </div>

      <button onClick={handleGenerate}>Generate</button>

      {/* --- The sentences + translation boxes --- */}
      {/* sentences.map(...) turns each sentence into an <li>. `key` lets React
          track list items across re-renders; index is fine for a static list. */}
      <ul>
        {sentences.map((sentence, index) => (
          <li key={index}>
            <div>{sentence}</div>
            <input
              type="text"
              placeholder="Your Chinese translation"
              value={translations[index] || ''}
              onChange={(e) => handleTranslationChange(index, e.target.value)}
            />
          </li>
        ))}
      </ul>

      {/* Only show the Feedback button once there are sentences to grade. */}
      {sentences.length > 0 && (
        <button onClick={handleGetFeedback}>Get Feedback</button>
      )}

      {/* --- The feedback, one block per sentence --- */}
      <ul>
        {feedback.map((item, index) => (
          <li key={index}>
            {/* concept_pass is a boolean; show it as PASS or FAIL text. */}
            <div>
              Concept: {item.concept_pass ? 'PASS' : 'FAIL'} — {item.concept_note}
            </div>
            <div>Other: {item.other_errors}</div>
            <div>Corrected: {item.corrected_translation}</div>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default App
