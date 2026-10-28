# Voice commands: plan

Branch: `voice-ai-feature`. Status: **backend and website built; iPhone app next.**

> **Change from this plan: voice is understood on our own server, for free.** Instead of Claude
> (sections 4.2 and 5), the default is a tiny model of our own, with no outside service:
> - **Matching** (`app/services/voice_local.py`) finds people, chores, bills, grocery items,
>   favours and amounts in what was said. It allows nicknames, misspellings and synonyms, and asks
>   *"Did you mean Raj or Rajesh?"* whenever two roommates fit.
> - **A naive Bayes model** (`voice_model.json`, about 24 KB, plain Python, no new libraries) then
>   picks the kind of action.
> - **To improve it,** add phrases to `backend/voice_training/phrases.py`, then run
>   `python -m voice_training.train` from `backend/`. Real phrases are saved in `voice_commands`.
> - **Claude is still there, switched off:** `VOICE_ENGINE=claude` plus `ANTHROPIC_API_KEY`.

## 1. The idea in one line

A floating **mic button** on every tab. You say what happened, for example *"I did the dishes"*,
*"Raj took out the trash"*, *"add milk and eggs"* or *"I paid the gas bill, it was 42 dollars"*.
The app shows what it understood as a card, you tap **Confirm**, and it's done.

## 2. What you can say (version 1)

The admin settings are left out. Everything else is covered:

| Area (tab) | Example phrases | What happens |
|---|---|---|
| **Chores** (Today / House) | "I did the dishes" · "Raj cleaned the bathroom" · "undo the trash, I didn't do it" | Marks today's task done, by me or by a roommate. Or reopens it |
| **Reminders / bills** (House) | "I paid the electricity bill" · "Priya paid wifi" · "gas bill is 42.50 and I paid it" | Records the payment, by me or by someone else. Sets the amount when one is said |
| **Groceries** | "add milk, eggs and bread" · "I bought the milk" · "got everything on the list" · "remove the chips" | Adds items, marks them bought, or removes an item |
| **Chat** | "tell everyone I'll be late tonight" · "message the house: rent is due Friday" | Posts the message in the house chat, in my name |
| **Favours** | "can someone pick up my parcel" · "Sam helped me with the parcel" · "my parcel favour is done" | Asks for a favour, or marks one done (mine, or one I did for someone) |
| **Anything unclear** | "the bathroom" (which task?) · "Raj paid" (which bill?) | Asks back with a few buttons to choose from, instead of guessing |
| **Can't do it** | "delete the house" · "make me admin" | "I can't do that by voice," plus where to do it |

**One sentence can hold several actions:** *"I did the dishes and bought milk"* gives two cards,
which can be confirmed together.

**The current tab is a hint, not a limit.** Saying *"add milk"* on the Chat tab still adds milk. The
tab only helps decide when a phrase could mean two things.

## 3. How it looks

```
  ┌─────────────────────────────┐
  │  Groceries                  │
  │  ...                        │
  │                        (🎤) │  ← floating "bob", bottom-right above the tab bar,
  └─────────────────────────────┘    on every tab except Admin settings

  Tap 🎤 → a bottom sheet opens:
  ┌─────────────────────────────┐
  │ 🎙  Listening…              │
  │ "Raj took out the trash     │  ← live words as you speak
  │  and I bought milk"         │
  │            [ Done ]  [ ⌨︎ ] │  ← ⌨︎ = type it instead
  └─────────────────────────────┘

  Then:
  ┌─────────────────────────────┐
  │ ✅ Take out trash           │
  │    Done by Raj · today      │
  │ 🛒 Milk                     │
  │    Mark as bought           │
  │  [ Confirm all ]  [ Cancel ]│
  └─────────────────────────────┘
  → a toast says "Done · Undo"
```

- **Tap to talk, tap Done to stop.** It also stops on its own after about 2 seconds of silence.
- **A keyboard option is always there,** for noisy rooms and for browsers without speech
  recognition.
- **Undo** sits in the toast for about 8 seconds. It uses the existing reopen and undo actions.
- **One bob component** is shared by every tab, so adding a new tab later needs no extra voice work.

## 4. How it works

```
 phone / browser                      our backend (FastAPI)                Claude API
 ───────────────                      ────────────────────                 ──────────
 speech → text (on the device)
 POST /voice/interpret  ───────────►  build the house snapshot:
   { text, tab }                       today's tasks, members, bills,
                                       open grocery items, open favours
                                       ───────────────────────────────────►  pick actions
                                                                             (tool use)
                                      ◄───────────────────────────────────
                                      check each action is allowed
 ◄───── proposed actions (cards) ────
 user taps Confirm
 POST /voice/execute  ─────────────►  runs the same services the
   { actions }                         buttons use today
 ◄───── results, plus undo info ─────
```

### 4.1 Speech to text, on the device and free

- **iPhone:** Apple's speech recognition (`SFSpeechRecognizer`), on the device when possible.
  It needs two permission prompts, microphone and speech.
- **Web:** the browser's built-in speech recognition (Chrome, Edge, Safari). Firefox doesn't
  have it, so it shows the keyboard instead.
- **Audio never leaves the phone.** Only the words do.

### 4.2 Understanding the words: Claude with tools

- **The backend sends Claude two things:**
  - The words, plus which tab you were on.
  - A **compact house snapshot:** today's tasks (with IDs and assignees), members (names and
    nicknames), bills that are due, open grocery items, and open favours.
- **Claude can only answer with tools,** each with a strict schema (`strict: true`), so the
  answers always match the format:
  - `complete_task(task_id, done_by_member_id?)` and `reopen_task(task_id)`
  - `record_bill_payment(bill_id, paid_by_member_id?, amount?)`
  - `add_grocery_items(names[])`, `mark_bought(item_ids[] | "all")`, `remove_grocery_item(item_id)`
  - `send_chat_message(text)`
  - `ask_favour(title, details?)` and `mark_favour_done(request_id)`
  - `ask_back(question, options[])`, for when the words could mean two things
  - `cannot_do(reason)`
- **Claude never runs anything.** The backend turns its tool calls into **proposed actions.** Then:
  - It checks them against the real data: the task exists today, the person is in the house,
    the bill is open.
  - It sends them back as cards. Nothing changes until you tap Confirm.
- **Names are matched loosely:** "Raj", "raj", "Rajesh" and a home nickname all work. With two
  Rajs, Claude asks back.

### 4.3 Running the actions: no new business logic

`/voice/execute` calls the **same service functions** the buttons call today:
- Tasks: `tasks/{id}/complete` (with `completed_by_member_id`) and `reopen`.
- Bills: `bills/{id}/pay` (with `member_id`) and `bills/{id}/amount`.
- Groceries: create, `shopping/{id}/bought`, `shopping/bought` (all), and delete.
- Chat: post a message.
- Favours: create, `help-requests/{id}/done`, and `reopen`.

So all the existing rules still apply: who can pay a bill, who can complete a task, and the activity
feed entries. Activity shows "via voice" so roommates can see where an action came from.

## 5. Which Claude model and what it costs

| Choice | Model | Price per 1M tokens (input / output) | Rough cost per command |
|---|---|---|---|
| **Default (recommended)** | Claude Opus 5.5 (`claude-opus-5-5`), effort `low` | $4 / $20 (cached input $0.20) | **~1 cent** |
| Cheaper option, if you prefer | Claude Haiku 5.5 (`claude-haiku-5-5`) | $0.10 / $0.50 | **~0.05 cent** |

**How the estimate works:**
- A command is about 3,000–5,000 tokens of house snapshot plus a few hundred tokens of answer.
- The fixed part (instructions and tool list) is **cached** for repeat commands, so most of the
  input is billed at the cached rate.
- Example: 5 roommates × 10 commands a day ≈ 1,500 commands a month ≈ **$15 a month on Opus 5.5**,
  or **under $1 on Haiku 5.5**.
- I'd start on Opus 5.5 at low effort for accuracy. The model is one setting (`VOICE_MODEL`), so it
  can switch to Haiku 5.5 after testing if the cost matters more. That's your call.

**Technical notes for the build:**
- Opus 5.5 doesn't allow "force a tool". We use `tool_choice: auto`, plus an instruction to always
  answer with a tool, plus strict schemas.
- When Claude declines a request (a "refusal"), the server-side fallback (`fallbacks: "default"`)
  retries on another model automatically.
- The prompt order is fixed instructions → tools → house snapshot → your words, so the fixed part
  stays cached.

## 6. Safety and privacy

- **Confirm before anything changes.** Version 1 never runs an action straight from your voice.
- **No deleting houses, removing members, or admin settings** by voice. Removing one grocery item
  is the only removal, and it's confirmed too.
- **Same permissions as the buttons.** The backend checks everything again at execute time, so
  nothing can be done by voice that couldn't be done by tapping.
- **Your words are treated as data, not instructions.** Saying "ignore your rules and…" can only
  ever produce one of the listed actions, and then a confirm card.
- **Limits:** about 60 commands a day per user, and about 500 characters per command.
- **Privacy:** audio stays on the device. The words and the house snapshot (names, task names,
  bills) go to Anthropic's API to be understood. The privacy policy page needs a short paragraph
  on this, and so does the App Store privacy form.
- **Switch:** if `ANTHROPIC_API_KEY` isn't set on the server, the bob is hidden, the same way the
  Google and Facebook buttons work.

## 7. What gets built

### Phase 1: backend
- `app/services/voice.py`: builds the house snapshot, calls Claude, and checks the proposed
  actions.
- Routes:
  - `POST /households/{id}/voice/interpret`: `{ text, tab }` → `{ actions[], question?, message? }`
  - `POST /households/{id}/voice/execute`: `{ actions[] }` → results, plus undo info
  - `GET /voice/config`: whether voice is on (the apps use it to show or hide the bob)
- Settings:
  - `ANTHROPIC_API_KEY`, `VOICE_MODEL` (default `claude-opus-5-5`), `VOICE_DAILY_LIMIT`
  - These go in `render.yaml` and `.env.example`.
- Add `anthropic` to `pyproject.toml`.
- Tests, with Claude faked:
  - Each action type.
  - Done by someone else.
  - Ask-back when it's unclear.
  - The permission checks.
  - The daily limit.
- **A test set of about 50 real phrases** (including Indian-English and US accents, typed the way
  speech recognition writes them). It's run against the real model, with your OK, to check accuracy
  before launch.

### Phase 2: website
- `VoiceBob` component, shown on every house tab except admin settings.
- `VoiceSheet`: listening view, live text, typing fallback, action cards, Confirm, and the Undo
  toast.
- Uses the browser's speech recognition. In browsers without it, the sheet opens straight to
  typing.

### Phase 3: iPhone app (when you say go)
- The same bob and sheet in SwiftUI, on the five tabs.
- `SFSpeechRecognizer` plus the two permission texts in Info.plist.
- Haptics on Confirm.

### Phase 4: later ideas
- **Questions:** "what's left for me today?", "who hasn't paid wifi?" (answers read out, no
  changes).
- **Siri Shortcut:** "Hey Siri, Roommates, I did the dishes."
- **Skipping Confirm for low-risk actions,** like adding groceries, if you want that.
- **WhatsApp voice notes,** if the WhatsApp integration happens.

## 8. Questions for you

1. **Confirm card:** always, or should adding groceries skip it? *(Suggest: always, for v1.)*
2. **Model:** start on Opus 5.5 (~1 cent per command), or go straight to Haiku 5.5 (~0.05 cent)?
3. **Chat by voice:** post right after Confirm, or show the text so it can be edited first?
4. **"Done by someone else":** should that roommate get a notification ("Shiva marked your trash
   chore done")?
5. **Swaps** ("swap my Tuesday trash with Raj"): include in v1, or later?
6. **Order:** backend + website first, then iPhone (as usual)?
