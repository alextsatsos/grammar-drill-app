import { useState, useEffect } from 'react'

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

// ---------------------------------------------------------------------------
// Keep the sentence count inside the 1–20 range the backend enforces. We CLAMP
// rather than block: an out-of-range or empty entry settles to the nearest
// valid value instead of throwing an error at the user. Used on blur (to tidy
// the field once they're done typing) and again at send time (so the request
// is always in range even if they hit Enter without leaving the field).
// ---------------------------------------------------------------------------
const COUNT_MIN = 1
const COUNT_MAX = 20
function clampCount(value) {
  const n = Math.round(Number(value))
  if (!Number.isFinite(n)) return COUNT_MIN
  return Math.min(COUNT_MAX, Math.max(COUNT_MIN, n))
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
  // WHICH WAIT IS ON. The app had no loading flag — screens were derived purely
  // from `sentences` / `feedback` length, so during a fetch the user sat on a
  // frozen screen. This single value records which request is in flight so the
  // UI can show a waiting state. It does NOT change any fetch logic; the two
  // handlers just set it at the start and clear it in a `finally`.
  //   'idle'       — nothing pending
  //   'generating' — /generate is running (skeleton screen)
  //   'grading'    — /feedback is running (reviewing overlay, next piece)
  // ---------------------------------------------------------------------------
  const [phase, setPhase] = useState('idle')

  // ---------------------------------------------------------------------------
  // ACTION 1: Generate sentences
  //
  // `async` lets us use `await` inside. `await` pauses this function (without
  // freezing the browser) until the network request comes back.
  // ---------------------------------------------------------------------------
  async function handleGenerate() {
    // Mark the generate wait as on, so the render shows the skeleton screen
    // instead of leaving the user on a frozen selection form. The `finally`
    // clears it whether the request succeeds or throws, so we never get stuck
    // on the skeleton. The fetch itself is unchanged.
    setPhase('generating')
    try {
      // fetch(url, options) sends the HTTP request. We build a POST with a JSON
      // body whose keys match your GenerateRequest model exactly: concept,
      // count, hsk_level.
      const response = await fetch(`${API}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }, // "the body is JSON"
        body: JSON.stringify({
          concept: concept,
          // clampCount keeps this in 1–20 even if they hit Enter without
          // blurring the field. The backend caps it too, independently — this
          // is just so a valid request goes out.
          count: clampCount(count),
          // hsk_level is optional. If the box is empty we send null, which your
          // backend treats as "omitted / use natural vocabulary".
          hsk_level: hskLevel === '' ? null : Number(hskLevel),
        }),
      })

      // response.json() reads the body and parses it from JSON text into a real
      // JS object. It's also async, so we await it. `data` is { sentences: [...] }.
      const data = await response.json()

      // Save the returned sentences into state -> triggers a re-render -> the
      // list below appears.
      setSentences(data.sentences)

      // Reset the answer boxes to one empty string per sentence, same length as
      // the sentences array. Array(n).fill('') makes ['', '', ''] for 3 sentences.
      setTranslations(Array(data.sentences.length).fill(''))

      // Clear any feedback from a previous round.
      setFeedback([])
    } finally {
      setPhase('idle')
    }
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
    // Mark the grading wait as on. Unlike generate, the answers stay on screen
    // throughout — the render below lays a quiet ink wash over them and swaps
    // the button for a "Reviewing…" note. The `finally` clears the flag whether
    // grading succeeds or throws. The fetch itself is unchanged.
    setPhase('grading')
    try {
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
    } finally {
      setPhase('idle')
    }
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

  // While /generate is running, `sentences` is still empty, so without this the
  // user would sit on the selection form. isGenerating takes precedence in the
  // render below and shows the skeleton instead. We mirror the chosen count (in
  // range) so the ghosted rows roughly match what's coming.
  const isGenerating = phase === 'generating'
  const skeletonCount = clampCount(count)

  // While /feedback is running, `feedback` is still empty, so the render would
  // otherwise fall through to the input screen. isGrading takes precedence over
  // that fallback and shows a results-shaped skeleton instead — one ghost block
  // per submitted sentence — so the wait clearly reads as "working," matching
  // the generate-step skeleton.
  const isGrading = phase === 'grading'

  // "New practice": drop the drill data so we fall back to the SELECTION screen.
  // Only resets the per-round data; the user's concept/level choices are kept
  // so the form comes back pre-filled. Touches no fetch logic.
  function handleNewPractice() {
    setSentences([])
    setTranslations([])
    setFeedback([])
  }

  // ---------------------------------------------------------------------------
  // Enter = the primary action of whichever screen is showing. One window-level
  // keydown handler covers all three screens — including results, which has no
  // field to attach to — and calls the SAME functions the buttons do, so no
  // submit logic is duplicated. Tab still moves between fields. Only a plain,
  // non-repeating Enter counts; when a button already has focus we bail out so
  // its native click isn't doubled. No dependency array: the effect re-binds
  // each render so the handler always sees current state.
  // ---------------------------------------------------------------------------
  useEffect(() => {
    function onEnter(e) {
      if (e.key !== 'Enter' || e.repeat) return
      if (e.shiftKey || e.ctrlKey || e.metaKey || e.altKey) return
      if (document.activeElement && document.activeElement.tagName === 'BUTTON') return
      // A request is already in flight — don't let Enter fire a duplicate.
      if (phase !== 'idle') return
      e.preventDefault()
      if (onSelectionScreen) handleGenerate()
      else if (onResultsScreen) handleNewPractice()
      else handleGetFeedback()
    }
    window.addEventListener('keydown', onEnter)
    return () => window.removeEventListener('keydown', onEnter)
  })

  return (
    <>
      {/* Decorative ink-painting side panels. position:fixed, so they drop out
          of the centered flow and never move or overlap the content band;
          aria-hidden + pointer-events:none keep them out of the reading and
          click paths. They fade into the cream before reaching the band. */}
      <div className="plum-panel left" aria-hidden="true"></div>
      <div className="plum-panel right" aria-hidden="true"></div>

      <div className="scroll-wrap">
        <div className="paper">
        {isGenerating ? (
          // ---------- LOADING: generating sentences (skeleton) ----------
          // Ghosted rows standing in for the prompts + answer fields that are
          // coming, so the wait shows the user WHAT and WHERE. One row per
          // sentence they asked for. The bars are decorative (aria-hidden); the
          // heading carries the meaning for screen readers. The shimmer lives
          // only in a prefers-reduced-motion:no-preference block in the CSS, so
          // reduced-motion users get these same bars, held still.
          <>
            <p className="screen-title" role="status">
              Generating your sentences…
            </p>
            {Array.from({ length: skeletonCount }).map((_, i) => (
              <div className="row skel-row" key={i} aria-hidden="true">
                <div className="skel-line skel-prompt"></div>
                <div className="skel-line skel-field"></div>
              </div>
            ))}
          </>
        ) : onSelectionScreen ? (
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
                  max="20"
                  value={count}
                  onChange={(e) => setCount(e.target.value)}
                  // Settle the field into range once they finish typing. We
                  // don't clamp on every keystroke — that would fight the user
                  // mid-edit (e.g. clearing the box to retype). Clamp on blur
                  // and again at send time instead.
                  onBlur={() => setCount(clampCount(count))}
                />
              </div>
              <span className="hint">1–20 sentences</span>
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
            </div>
            <hr className="d" />

            {/* One block per sentence. The PASS/FAIL chip is the star, locked
                to a consistent left column so the verdicts scan straight down. */}
            {feedback.map((item, index) => (
              <div className="block" key={index}>
                <img
                  className={`seal ${item.concept_pass ? 'pass' : 'fail'}`}
                  src={item.concept_pass ? '/seal-pass.PNG' : '/seal-fail.PNG'}
                  alt={item.concept_pass ? 'Pass' : 'Fail'}
                />
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
        ) : isGrading ? (
          // ---------- LOADING: grading (results-shaped skeleton) ----------
          // Ghosted results blocks — one per submitted sentence — standing in
          // for the verdict seal and the prompt / answer / correction lines that
          // are coming. This REPLACES the input view, the same way the real
          // results do, so the transition reads inputs → results-shaped ghosts
          // → results. It reuses the exact .skel-line class the generate
          // skeleton uses, so the shimmer and the prefers-reduced-motion
          // handling are identical — the two waits look like one family. The
          // bars are decorative (aria-hidden); the heading carries the meaning
          // for screen readers.
          <>
            <p className="screen-title" role="status">
              Marking your translations…
            </p>
            {sentences.map((_, i) => (
              // Same .block grid as a real feedback block (seal column + content),
              // so the ghost sits exactly where the verdict will.
              <div className="block skel-block" key={i} aria-hidden="true">
                <div className="skel-line skel-seal"></div>
                <div>
                  <div className="skel-line skel-prompt"></div>
                  <div className="skel-line skel-answer"></div>
                  <div className="skel-line skel-correct"></div>
                </div>
              </div>
            ))}
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
      </div>
    </>
  )
}

export default App
