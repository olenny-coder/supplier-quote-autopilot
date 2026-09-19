# SEO and discoverability playbook

This is a practical, specific plan for getting Supplier Quote Autopilot found by the people
it is for — facilities managers, building owners and SME procurement teams searching for RFQ
software — and an honest account of what search engine optimisation can and cannot do for a
repository.

Everything here is meant to be pasted or copied. Nothing here requires access to a marketing
tool, an analytics account, or money.

---

## 0. Read this part first: the honest limits

**GitHub is not Google, and a README is not a landing page.**

- **GitHub search weights the description and topics far more than README prose.** A
  repository with a precise description and twenty relevant topics will out-rank one with a
  beautiful README and no topics, for searches like *rfq software* or *facilities management
  procurement*. Fill those two fields in before you tweak a single sentence of prose.
- **Keyword stuffing actively hurts.** A README that repeats "RFQ software Singapore
  procurement" eleven times reads as spam to a human deciding whether to trust your code,
  and the human is the one who stars, forks and deploys it. GitHub's crawler is not the
  audience; a facilities manager who landed here from a search result is.
- **Google will mostly find you through long-tail phrases, if at all.** Nobody outranks
  established vendors for "procurement software". Somebody may well find you searching
  "open source RFQ tool for minor works Singapore" or "supplier quote comparison
  spreadsheet alternative". Those are the queries worth writing for.
- **The strongest signal is other people linking to you.** A post in a facilities
  management community, an answer on a forum, a mention in a newsletter — one real mention
  beats any amount of on-page tuning. Do not spam for them.
- **Most of your traffic will not come from search at all** for the first year. It will come
  from wherever you announce it, and from GitHub's own "similar repositories" and topic
  pages. Optimise for the person who arrives from those and needs to understand in twenty
  seconds whether this fits their problem.
- **Do not fabricate claims to rank.** "The #1 procurement platform" in a repository whose
  own README documents an MVP boundary list is a credibility loss, and the README is the
  one thing a technical evaluator will actually read.

The rest of this document is what to actually do.

---

## 1. Suggested GitHub repository description

GitHub's description field (the one under the repository name, next to the ⚙ button) is
**350 characters**. This field is indexed by GitHub search and is usually the only text a
searcher sees in a result list, so it does the heaviest lifting of anything on this page.

Pick one. The first is the recommended default.

### Option A — recommended (292 characters)

```
Open-source RFQ software for facilities management and building services procurement: tokenized supplier quote forms with no supplier login, automated follow-up, and landed/works-cost comparison with SGD and GST defaults. FastAPI + React + PostgreSQL. Deploys free on Neon, Render and Vercel.
```

Why this one: it leads with the two phrases people actually type (*RFQ software*, *facilities
management*), states the single most differentiating mechanic in the first line (tokenized
supplier forms, no supplier login), names the comparison behaviour that separates it from a
spreadsheet, mentions the market defaults that make it findable locally, and ends with the
stack and the free tier for the developer who is evaluating rather than buying.

### Option B — short (140 characters)

```
Open-source RFQ and quote comparison for building maintenance and minor works. Tokenized supplier forms, automated follow-up, SGD/GST aware.
```

Use this if you prefer something a human reads in one glance. It gives up the stack and the
deployment story, so it is weaker for GitHub search and for developer traffic.

### Option C — long (345 characters)

```
Supplier Quote Autopilot is open-source RFQ software for facilities management and building services procurement. Invite suppliers by tokenized link (no account needed), chase non-responders automatically, and compare quotes on landed/works cost with SGD and GST handling. FastAPI, React 19, PostgreSQL. Free-tier deploy on Neon, Render, Vercel.
```

Use this if you want the product name indexed too. It repeats the project name, which the
repository name already contains, so it wastes a few characters — and on GitHub the name is
already bolded above the description in every result.

**Do not** put a URL, an emoji, or "🚀" in this field. It is plain text, it is truncated
without warning at 350 characters, and it is indexed.

---

## 2. Topics to paste

Repository page → **About** → ⚙ → **Topics**. GitHub allows up to 20; use all 20.

```
rfq
request-for-quotation
procurement
facilities-management
building-maintenance
quote-comparison
supplier-management
fastapi
react
postgresql
neon
render
vercel
groq
llm
openai-compatible
sgd
gst
singapore
minor-works
```

Notes on the order, which matters more than it looks:

- **The first eight are the ones a buyer searches.** `rfq`, `request-for-quotation`,
  `procurement`, `facilities-management`, `building-maintenance`, `quote-comparison`,
  `supplier-management` are the phrases a facilities or procurement person types. These
  should be present even if they cost you a technology topic.
- **The next seven are developer-facing.** A developer evaluating a FastAPI or React
  implementation searches `fastapi` and `react`; a developer looking for something to deploy
  cheaply searches `neon`, `render`, `vercel`. These bring contributors as well as users.
- **The last four are market-specific.** `sgd`, `gst`, `singapore` and `minor-works` are
  low-volume and high-intent: someone searching `gst` inside a procurement context is
  almost certainly in the market this project was built for. They also cost you almost
  nothing to hold.

If you would rather add `electrical`, `plumbing`, `hvac`, `tailwindcss`, `docker` or
`alembic`, drop from the bottom up — `minor-works` first, then `singapore`. `tailwindcss`
and `docker` in particular are crowded with noise: thousands of repositories carry them and
almost nobody browses by them.

**The description and the topics are the two fields that matter most.** If you do nothing
else from this document, do these.

---

## 3. Keyword map

Where each phrase belongs, and where it does not. "README H1" means the single `#` heading
at the top of the root README — it is the strongest on-page signal GitHub has, and it should
carry the primary phrases in a single readable sentence rather than a list.

### Primary — must appear in the README H1 (or the first paragraph) *and* the description

| Phrase | Where it is used | Notes |
| --- | --- | --- |
| RFQ software | README H1, description, first paragraph, topics (`rfq`) | The head term. One exact use in the H1 and one in the opening paragraph is enough. |
| request for quotation | README H1, first paragraph, topics (`request-for-quotation`) | Spelled out at least once — this is the phrase a buyer types, `rfq` is the acronym they may also type. |
| quote comparison | README H1, first paragraph, feature headings, description, topics (`quote-comparison`) | The differentiating capability. |
| facilities management procurement | README H1, first paragraph, description, topics (`facilities-management`, `procurement`) | The vertical. |
| supplier management | First paragraph, feature heading, topics (`supplier-management`) | Also the phrase someone types when replacing a spreadsheet of contractors. |

### Secondary — must appear naturally in prose and in the feature list

| Phrase | Where it is used | Notes |
| --- | --- | --- |
| building maintenance tendering | First paragraph, potential blog post or announcement | A real buying phrase, low competition. |
| minor works | First paragraph, feature list, topics (`minor-works`), both issue templates | The specificity that makes this project findable at all. |
| automated supplier follow-up | Feature group heading, first paragraph | Describe it as *follow-up*, not "email automation" — the latter attracts a different, wrong audience. |
| landed cost / works cost | Comparison feature section, guardrails | Buyers who know this term are buyers who have been burned by headline-price comparison. |
| RFQ template / three-quote process | FAQ and roadmap — **describe honestly** | Do not claim a template library that does not exist. Refer to the required-field contract instead. |
| supplier quote form | Feature heading, description | The mechanic that needs no supplier account. |
| SGD, GST | First paragraph, FAQ ("Can I use it outside Singapore?"), configuration table, topics | Defaults, not requirements — say so, or non-Singapore buyers bounce. |

### Long-tail — write these into headings and FAQ questions verbatim

These are the queries with realistic intent and low competition. Each one maps to a heading
or an FAQ question that already exists in the README, which is not an accident: question-shaped
headings are how a README gets found by a person typing a question.

| Long-tail phrase | Where it already appears |
| --- | --- |
| free RFQ software for small business | FAQ: *Is it free?* |
| RFQ software without supplier login / do suppliers need an account | FAQ: *Do suppliers need an account?* |
| open source quote comparison tool | README H1, §4 comparison table |
| how to chase suppliers for quotes automatically | §3 Follow-up automation, FAQ: *Does it send email?* |
| compare contractor quotes on total cost not unit price | §3 Comparison and scoring, §6 guardrails |
| RFQ tool for GST and SGD with tax handling | FAQ: *Can I use it outside Singapore?*, §9 |
| self-hosted procurement tool free tier | §8 deployment, FAQ: *Is it free?* |
| can software award a contract automatically | FAQ: *Can it award a supplier automatically?* (the answer is no, by design) |
| supplier quote form mobile no app | §5 tour of the screens |
| quote comparison spreadsheet alternative | §4 comparison table, first column |

### Where the phrases do **not** go

- **Not in code comments.** Search engines do not index your Python comments for product
  queries, and a maintainer reading `comparison/score.py` wants to know why the weighting is
  what it is, not what a marketing phrase is. The one exception is `backend/app/features/rfq/taxonomy.py`,
  whose module docstring legitimately explains the goods-versus-services difference — that
  is documentation, not optimisation.
- **Not in the issue templates as keyword filler.** The templates here ask for a failing
  command and its output, because that is what makes a report actionable. They mention the
  product areas by name (RFQ management, supplier invitations, comparison and scoring)
  because those are the categories a reporter has to pick from — that is a real function, and
  it happens to include the useful nouns.
- **Not in `.env.example` or `docs/API.md`** beyond what the variable or endpoint actually
  does. Those files are read by operators mid-incident.
- **Not as repeated exact phrases.** If a phrase appears in the H1, do not repeat it
  verbatim in the next three paragraphs. Use the natural variant (`request for quotation`
  once, then "the RFQ", "the quote round", "the tender").

---

## 4. What to write for announcements

Three audiences, three different posts. The facilities-management audience is **not on
Hacker News** — a facilities manager reads a trade forum, a LinkedIn group for MCST council
members, or a newsletter. Posting the same text to all three places is the fastest way to
look like spam in all three.

Two rules for all of them:

1. **Lead with the problem, not the product name.** Nobody searches for your project; lots
   of people are annoyed by chasing contractors by email.
2. **Say what it does not do.** It makes the post credible and it pre-empts the comment that
   would otherwise derail the thread.

### Hacker News (Show HN)

Title format that works: `Show HN: <what it is> (<what is technically interesting>)`. Do not
call it a startup, and do not ask for upvotes.

> **Show HN: Supplier Quote Autopilot – open-source RFQ tool with tokenized supplier forms**
>
> I run quote rounds for building maintenance work, which means emailing a specification to
> five contractors, getting three replies, and then reading them out of a spreadsheet to work
> out which one is actually cheapest once you add the callout charge and GST.
>
> This is my attempt to fix that. A buyer creates an RFQ, each invited supplier gets a unique
> tokenized link (no account, no app — it's a mobile-first web form), and a scheduler chases
> the non-responders. Quotes are normalised by currency, rate basis and terms before anything
> is ranked, and scored on price, response time, mobilisation time, accreditations, payment
> terms, minimum callout, validity, defect liability and risk with weights you set.
>
> The part I'd most like feedback on is the guardrails, because they're the design decisions
> rather than the code:
>
> - A quote that can't be normalised is never silently dropped from a comparison. It shows up
>   with a reason. Omitting a supplier is the expensive failure.
> - A supplier who is waiting on the buyer for a spec is escalated, not chased. Chasing them
>   asks for something they've said they can't give.
> - Nothing is auto-awarded. One endpoint awards, and it needs an authenticated buyer and a
>   written reason.
> - Complete quotes always outrank incomplete ones, regardless of score.
>
> Stack is FastAPI + SQLAlchemy + React 19 + PostgreSQL. The domain logic (parser, follow-up
> policy, costing and scoring) lives in two packages that do no I/O at all, so the engine is
> testable without a database or a network, and every LLM call site has a deterministic
> fallback — it runs with no API key. 424 tests, all offline on SQLite; there's a separate
> test that compiles the schema and queries against the PostgreSQL dialect, because the one
> bug class that hurt was "green on SQLite, broken on Postgres".
>
> Free-tier deploy: Neon + Render + Vercel. MIT.
>
> Known limits, so nobody wastes time: single-tenant (one buyer account, no roles), one scope
> per RFQ (no line items), static dated FX table rather than a live feed, and the rate limiter
> is in-process so it's correct for one instance only.
>
> Repo: <link>

Post it once. If it does not land, do not repost it — answer questions on the thread and
move on to the audience-specific posts below, which are where the actual users are.

### Reddit

Pick **one** subreddit where the problem is real — a facilities management, property
management, or small-business operations community — and read its self-promotion rules
first. Many require you to be an established participant. If the rules forbid promotion,
participate for a few weeks first, or post it as a comment where someone asks exactly this
question rather than as a new thread.

> **Title:** I built a free tool for running three-quote rounds on building maintenance work — would this be useful, or am I solving a problem nobody has?
>
> Bit of context: I kept running into the same mess on minor works quotes. Send a spec to
> five contractors, get three replies after a chase, then try to compare a lump sum against
> an hourly rate against a per-visit rate, one of which has a callout charge and one of which
> doesn't, and all of which expire on different dates.
>
> So I built this. It's open source and free to run:
>
> - You create the RFQ once — scope, site, access notes, deadline, and the fields a quote
>   must contain to count as complete.
> - Each contractor gets their own link. No signup, no login, works on a phone. They fill it
>   in and get a reference number.
> - You can see who opened the form and didn't submit, which is usually the useful signal.
> - It chases the ones who haven't replied, and it emails *you* if a contractor is waiting on
>   you rather than on them.
> - The comparison adds up the callout charge and GST, converts currencies, and scores each
>   quote. It suggests a winner and tells you why. You still approve it yourself and write
>   down the reason.
>
> I'm not selling anything and there's no paid tier. What I'd genuinely like to know: does
> this match how you actually run quotes, or do you do something different that this doesn't
> handle? The thing I'm least sure about is whether the "required fields" idea is useful or
> just extra setup before you can send anything.
>
> <link>

That last paragraph is the point of the post. A thread of people telling you what your model
gets wrong is worth more than a hundred stars.

### LinkedIn

LinkedIn rewards a plain, first-person post with a specific problem and no hashtag soup. Two
to four short paragraphs, one link at the end. Do not tag companies or people who have not
agreed to it.

> Most minor works quotes are decided in a spreadsheet, and the spreadsheet only ever
> compares the headline number.
>
> That number is rarely the cost. A lump sum quote with no callout charge is not comparable to
> an hourly rate with a four-hour minimum and a $120 attendance fee. Neither is comparable to
> a quote in another currency, on payment terms that differ by 60 days, or with a validity date
> that expires next month. And the contractor who was never chased is not cheaper — they just
> never answered.
>
> I've spent the last while building an open-source tool for exactly this: Supplier Quote
> Autopilot. A buyer creates a request for quotation, each invited supplier gets their own
> private link with no account to create, the ones who go quiet get chased automatically with
> the buyer approving each reminder, and the comparison adds callout charges and GST,
> normalises the rate bases, and scores each supplier on price, response time, terms, validity,
> defect liability period, accreditation and risk.
>
> The design decision I care most about: it never awards on its own. It recommends, with a
> written rationale, and a human approves and records why. In procurement that is not a
> limitation, it is the point.
>
> It's MIT-licensed, runs on free-tier hosting (Neon + Render + Vercel), and works with no AI
> key configured at all. Requirements are Python 3.13 and Node 22 if you want to run it
> yourself; there is a one-command Windows launcher and a Docker Compose file.
>
> If you run three-quote processes for maintenance or minor works, I'd value your view on
> where this doesn't fit your reality. <link>

**Do not** post the same text on all three on the same day. Space them, and reply to every
comment in the first 24 hours — on every one of these platforms the replies are what get the
post seen, not the post itself.

---

## 5. Post-push checklist

Tick these off after the repository is public. The first two are worth more than the rest
combined.

**Settings (do these first)**

- [ ] Repository **description** pasted from §1 (Option A unless you have a reason).
- [ ] All 20 **topics** pasted from §2, in the order given.
- [ ] **Website** field set, if there is a demo instance or a landing page — leave it empty
      rather than pointing at a Render URL that will be asleep.
- [ ] **Social preview image** uploaded (repository → Settings → General → Social preview).
      Without one, every share renders as a grey box. 1280×640 is the safe size.
- [ ] **About** sidebar shows the description, topics, license and the MIT badge.

**Content**

- [ ] README renders correctly on GitHub: headings, the ASCII architecture diagram, and every
      table. Check the badges load and none of them is a 404.
- [ ] Every relative link in the README resolves on the GitHub blob view — `LICENSE`,
      `NOTICE`, `.env.example`, `docs/API.md`, `docs/SEO.md`, `GITHUB_SETUP.md`,
      `CONTRIBUTING.md`, `INTEGRATION_PLAN.md`, the three sub-READMEs, `render.yaml` and
      `docker-compose.yml`. `INTEGRATION_PLAN.md` is committed at the repository root for
      exactly this reason: GitHub cannot follow a relative link out of a repository root, so
      it was copied in rather than linked from the build workspace.
- [ ] Every internal anchor link in the table of contents jumps to the right heading.
- [ ] The README's claims are still true: re-run the test count and update the badge if it
      changed.
- [ ] `LICENSE` shows on the repository page as **MIT** (GitHub detects it from the filename
      and content).

**Discoverability**

- [ ] CI is green on `main`, so the Actions tab is not the first thing a visitor sees.
- [ ] If you want the build badge, add it once the first workflow run has completed, using
      your own `owner/repo`:
      `[![CI](https://github.com/OWNER/REPO/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci-cd.yml)`
- [ ] Search GitHub for `rfq`, `request-for-quotation` and `facilities-management` and confirm
      the repository appears in the topic list within a day or two. If it does not, the
      topics were not saved.
- [ ] Google Search Console or a plain `site:github.com/OWNER/REPO` check, once, purely to
      confirm indexing. Do not obsess over it.
- [ ] **Announce it in one place that is actually full of the intended audience** — a
      facilities management forum, an MCST/property managers group, a local SME operations
      community. One real mention in a real community outperforms every other item on this
      checklist.
- [ ] Reply to every comment and issue in the first week.

**Deliberately not on this list**

- Buying ads, keyword-stuffing the README, mass-posting the same announcement to a dozen
  subreddits, creating fake accounts to star the repository, or adding a "SEO" section to the
  README. Each of them is either useless or actively harmful to a project whose entire
  credibility rests on an honest README and a documented list of its own limitations.

---

## 6. After launch: what to publish

The most durable search traffic for a repository comes from writing up the problems, not the
product. Each of these is a real thing this codebase has an answer to, so nobody has to
invent content:

- *"Why a complete quote should always outrank a cheaper incomplete one"* — an ordering rule,
  not a score penalty, and the reasoning is in this README's guardrails section.
- *"Green on SQLite, broken on PostgreSQL: the `IS true` on an integer column bug"* — a
  concrete post-mortem with a reproduction and a CI guard, described in §9 of
  `INTEGRATION_PLAN.md`.
- *"Converting a per-unit price in the wrong direction is a 10⁶ error"* — a short piece on why
  deriving unit conversion from physical sizes beats a hand-written factor table.
- *"Never chase a supplier who is waiting on you"* — the follow-up decision order, and why
  step 3 comes before steps 4 and 5.
- *"Running a procurement tool with no AI key"* — what the deterministic fallbacks actually
  do, and why every LLM call site needs one.

Post these wherever the first announcement worked. Technical post-mortems travel further than
product announcements in almost every developer community, and they are honest by
construction, which is the property that makes people trust the repository they link to.
