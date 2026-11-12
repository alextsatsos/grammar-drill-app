import { useState } from 'react'

// The base URL of your FastAPI backend. Everything POSTs here.
const API = 'http://localhost:8000'

// ---------------------------------------------------------------------------
// DISPLAY-ONLY helper. `other_errors` is free text; when a sentence has no
// other mistakes the grader writes a short "no errors" sentence rather than an
// empty string (see the backend schema). This decides whether the quiet
// "Also:" line is worth showing. It only affects RENDERING — it never changes
// the grading, the data, or the /feedback call.
// ---------------------------------------------------------------------------
function hasOtherError(text) {
  if (!text) return false
  const t = text.trim().toLowerCase()
  if (t === '') return false
  // Common "nothing else wrong" phrasings the grader produces.
  const noError =
    /^(no( other)? (errors?|mistakes?|issues?)|none\b|n\/a|nothing (else )?(wrong|to (fix|correct)))/.test(
      t
    ) || /\bno other (errors?|mistakes?|issues?)\b/.test(t)
  return !noError
}

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
  // ---------------------------------------------------------------------------
  // RENDER
  //
  // The app is two screens sharing the same paper scroll. Which one shows is
  // decided by state that already exists: before /generate returns anything we
  // show the SELECTION screen; once `sentences` has items we show the INPUT
  // screen. No new state — this is the same JSX, just gated and restyled.
  // ---------------------------------------------------------------------------
  const onSelectionScreen = sentences.length === 0
  const onResultsScreen = feedback.length > 0

  // "New practice": drop the drill data so we fall back to the SELECTION screen.
  // Only resets the per-round data; the user's concept/level choices are kept
  // so the form comes back pre-filled. Touches no fetch logic.
  function handleNewPractice() {
    setSentences([])
    setTranslations([])
    setFeedback([])
  }

  return (
    <div className="scroll-wrap">
      <div className="dowel top"></div>
      <div className="paper">
        {onSelectionScreen ? (
          // ---------- SCREEN 1: selection / setup ----------
          <>
            <div className="title">
              <span className="cn">你好学生</span>
              <span className="en">Welcome Student</span>
            </div>

            <div className="row">
              <label className="label">
                What grammar concept do you want to work on?
              </label>
              <div className="field">
                <input
                  className="inp"
                  type="text"
                  placeholder="e.g. 了 for completed actions"
                  value={concept}
                  // Every keystroke fires onChange; e.target.value is the box's
                  // text. We push it into state so `concept` always mirrors the
                  // screen.
                  onChange={(e) => setConcept(e.target.value)}
                />
              </div>
            </div>

            <div className="row">
              <label className="label">
                How many sentences would you like to practice?
              </label>
              <div className="field">
                <input
                  className="inp"
                  type="number"
                  min="1"
                  max="10"
                  value={count}
                  onChange={(e) => setCount(e.target.value)}
                />
              </div>
            </div>

            <div className="row">
              <label className="label">Vocabulary level</label>
              <div className="sel">
                <select
                  value={hskLevel}
                  onChange={(e) => setHskLevel(e.target.value)}
                >
                  <option value="">Any level</option>
                  <option value="1">HSK 1</option>
                  <option value="2">HSK 2</option>
                  <option value="3">HSK 3</option>
                  <option value="4">HSK 4</option>
                  <option value="5">HSK 5</option>
                  <option value="6">HSK 6</option>
                </select>
                <span className="chev">▼</span>
              </div>
            </div>

            <button className="btn" onClick={handleGenerate}>
              Begin practice
            </button>
          </>
        ) : onResultsScreen ? (
          // ---------- SCREEN 3: results (REPLACES the input view) ----------
          <>
            {/* Teacher's remark + ONE positive, concept-oriented score. */}
            <div className="remark">
              <span className="cn">做得好，学生</span>
              <span className="score">
                Concept {concept} — you got{' '}
                <b>{feedback.filter((f) => f.concept_pass).length}</b> of{' '}
                {feedback.length} correct
              </span>
              <span className="seal" aria-hidden="true">
                評
              </span>
            </div>
            <hr className="d" />

            {/* One block per sentence. The PASS/FAIL chip is the star, locked
                to a consistent left column so the verdicts scan straight down. */}
            {feedback.map((item, index) => (
              <div className="block" key={index}>
                <div
                  className={`chip ${item.concept_pass ? 'pass' : 'fail'}`}
                  aria-label={item.concept_pass ? 'Pass' : 'Fail'}
                >
                  {item.concept_pass ? '✓' : '✕'}
                </div>
                <div>
                  <p className="prompt">{sentences[index]}</p>
                  <p className="ln">
                    <span className="l">You wrote</span>
                    {translations[index]}
                  </p>
                  {/* Corrected line only when something was actually wrong. */}
                  {item.corrected_translation ? (
                    <p className="ln">
                      <span className="l">Correct</span>
                      {item.corrected_translation}
                    </p>
                  ) : null}

                  {/* Concept FAIL: the concept's own note is the explanation —
                      warmer, plain, part of the star verdict (not "other"). */}
                  {!item.concept_pass && item.concept_note ? (
                    <p className="cnote">{item.concept_note}</p>
                  ) : null}

                  {/* OTHER feedback: subordinate + conditional. Shown only when
                      there is a real other slip, and kept quiet. */}
                  {hasOtherError(item.other_errors) ? (
                    <p className="other">
                      <span className="k">Also:</span> {item.other_errors}
                    </p>
                  ) : null}
                </div>
              </div>
            ))}

            {/* Primary action, normal flow at the bottom (not pinned). */}
            <button className="btn" onClick={handleNewPractice}>
              New practice
            </button>
          </>
        ) : (
          // ---------- SCREEN 2: sentence input ----------
          <>
            <p className="screen-title">Please translate the sentences</p>

            {/* sentences.map(...) turns each sentence into a prompt+input pair.
                `key` lets React track list items across re-renders; index is
                fine for this static list. */}
            {sentences.map((sentence, index) => (
              <div className="row" key={index}>
                <p className="prompt">{sentence}</p>
                <div className="field">
                  <input
                    className="inp"
                    type="text"
                    placeholder="write your translation…"
                    value={translations[index] || ''}
                    onChange={(e) =>
                      handleTranslationChange(index, e.target.value)
                    }
                  />
                </div>
              </div>
            ))}

            <button className="btn" onClick={handleGetFeedback}>
              Check my translations
            </button>
          </>
        )}
      </div>
      <div className="dowel bottom"></div>
    </div>
  )
}

export default App
