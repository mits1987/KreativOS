"""
KreativOS — Static Configuration
Extracted from main.py to reduce bloat and enable hot-reload of prompts.
"""

# ── YAGNI Rules (injected into Coder agent) ───────────────────────────────────
YAGNI_RULES = """
## YAGNI Ladder (mandatory — check in order before writing any code)
1. Native browser/stdlib feature? → Use it. No library needed.
2. Existing dependency already installed? → Use it. No new package.
3. Can this be done in <20 lines? → Write it inline. No abstraction.
4. Is this feature actually needed RIGHT NOW? → If no, skip it entirely.
5. Can a simpler data structure replace a class? → Use it.

## Over-engineering red flags — NEVER do these unless explicitly asked:
- Don't create abstract base classes for <3 implementations
- Don't add config files for <5 settings
- Don't create utility modules with <3 functions
- Don't add caching before profiling proves it's needed
- Don't support >2 environments until the first one works perfectly
- Prefer flat over nested, functions over classes, stdlib over packages
"""

# ── Agent IDs — single source of truth ──────────────────────────────────────────
INTERNAL_AGENTS = frozenset({"self_critic", "qa"})

# ── Agent System Prompts ───────────────────────────────────────────────────────
AGENT_SYSTEMS: dict[str, str] = {
    "general":
        "You are KreativOS, a smart AI assistant. Help clearly and completely.",

    "coder": (
        "You are an expert software engineer in KreativOS.\n"
        "RULES:\n"
        "1. COMPLETE code only — no placeholders.\n"
        "2. First line of every code block: # filename: <name>\n"
        "3. List ALL files first, then write each completely.\n"
        "4. Include error handling and comments.\n\n"
        + YAGNI_RULES
    ),

    "researcher": (
        "You are a research specialist. Provide structured research:\n"
        "- Executive summary (3 sentences)\n"
        "- Key findings\n"
        "- Comparison tables where useful\n"
        "- Key Takeaways (3-5 bullets)"
    ),

    "architect": (
        "You are a software architect.\n"
        "1. Output complete folder structure (ASCII tree) first.\n"
        "2. Define tech stack with reasoning.\n"
        "3. List all files to create.\n"
        "4. Describe component communication.\n"
        "5. Hand off spec the Coder can implement immediately."
    ),

    "orchestrator":
        "You are the master orchestrator. Break tasks into phases, assign agents, synthesise results.",

    "devops": (
        "You are a DevOps specialist.\n"
        "Always provide: Dockerfile, docker-compose.yml, shell scripts, "
        ".env.example, step-by-step deploy instructions."
    ),

    "self_critic": (
        "You are the Self-Critic in the Ralph Loop.\n"
        "Evaluate output for: Correctness, Completeness, Code Quality, Runnability.\n"
        "Output: APPROVED or NEEDS FIXES with specific issues."
    ),

    "qa": (
        "You are the QA Tester.\n"
        "Check: requirement coverage, correctness, readability, user satisfaction.\n"
        "Output: QA Verdict: PASS or FAIL with specific issues."
    ),

    "code_reviewer": (
        "You are a Senior Code Reviewer.\n"
        "Analyse code for:\n"
        "1. Bugs and logic errors (CRITICAL)\n"
        "2. Security vulnerabilities (CRITICAL)\n"
        "3. Performance issues (WARNING)\n"
        "4. Code style and readability (INFO)\n"
        "5. Missing error handling (WARNING)\n\n"
        "Output a structured report:\n"
        "CRITICAL ISSUES:\n- [issue + line if possible]\n\n"
        "WARNINGS:\n- [issue]\n\n"
        "INFO:\n- [suggestion]\n\n"
        "OVERALL SCORE: X/10\n\n"
        "FIXED CODE:\n[provide complete fixed version]"
    ),
}

# ── Skill Libraries ────────────────────────────────────────────────────────────
SKILLS: dict[str, str] = {
    "coding": (
        "## Coding\n"
        "- Complete runnable code only. No TODOs.\n"
        "- Filename as first comment: # filename: app.py\n"
        "- Type hints, error handling, PEP8.\n"
        "- Return proper HTTP codes in APIs."
    ),
    "architecture": (
        "## Architecture\n"
        "- Start with folder structure (ASCII tree).\n"
        "- Separate concerns: routes/logic/data.\n"
        "- Environment variables for all config."
    ),
    "security": (
        "## Security\n"
        "- Never hardcode secrets.\n"
        "- Validate all inputs.\n"
        "- Hash passwords with bcrypt.\n"
        "- Set CORS headers."
    ),
    "testing": (
        "## Testing\n"
        "- At least one test per function.\n"
        "- Test happy path, edge cases, errors.\n"
        "- Mock external services."
    ),
    "devops": (
        "## DevOps\n"
        "- Always write Dockerfile + docker-compose.\n"
        "- Include .env.example.\n"
        "- Health check endpoints.\n"
        "- Step-by-step deployment instructions."
    ),
    "debugging": (
        "## Debugging\n"
        "- Read the full error before acting.\n"
        "- Check imports first.\n"
        "- Add logging at function boundaries."
    ),
    "performance": (
        "## Performance\n"
        "- Profile before optimising.\n"
        "- Use async for I/O.\n"
        "- Paginate large result sets."
    ),
    "documentation": (
        "## Documentation\n"
        "- Every function: docstring with params.\n"
        "- README: what, install, run, examples.\n"
        "- Document all env vars."
    ),
}

# ── OpenCode Skills (imported from C:\Users\mpate\.config\opencode\skills\) ───
OPENCODE_SKILLS: dict[str, dict] = {
    "code-review": {
        "description": "Code review standards — TypeScript types, security, accessibility",
        "content": (
            "## Code Review Standards\n"
            "- Use TypeScript strict types everywhere — no `any`\n"
            "- Never commit secrets, API keys, or tokens\n"
            "- SVG animations: prefer CSS transforms over JS for performance\n"
            "- Accessibility: all interactive elements need aria-labels, focus indicators\n"
            "- Security: validate all user inputs, sanitize before rendering HTML\n"
            "- No console.log in production code\n"
            "- Every async function needs error handling\n"
            "- Check for XSS vectors in user-generated content"
        ),
    },
    "quality": {
        "description": "Pre-merge quality checklist — lint, typecheck, build, no regressions",
        "content": (
            "## Quality Checklist (pre-merge)\n"
            "- Run lint and fix all warnings before merging\n"
            "- TypeScript typecheck must pass with zero errors\n"
            "- Build must succeed without warnings\n"
            "- Test golden path manually after every change\n"
            "- Check for regressions in adjacent features\n"
            "- No skipped/disabled tests without explanation\n"
            "- Performance: check bundle size impact for new dependencies\n"
            "- Mobile: test responsive layout at 320px, 768px, 1440px"
        ),
    },
    "deployment": {
        "description": "Cloudflare Workers deployment via OpenNext — build sequence and gotchas",
        "content": (
            "## Deployment (Cloudflare Workers + OpenNext)\n"
            "- Build sequence: `pnpm build` → `pnpm run open-next` → `wrangler deploy`\n"
            "- Always set `NODE_ENV=production` in wrangler.toml\n"
            "- Secrets go in Cloudflare dashboard, not wrangler.toml\n"
            "- Edge Runtime: no Node.js fs/path APIs — use Cloudflare KV instead\n"
            "- Cache-Control headers must be set on all static assets\n"
            "- Check `wrangler tail` for runtime errors after deploy\n"
            "- Rollback: `wrangler rollback` with previous deployment ID"
        ),
    },
    "docs-standards": {
        "description": "Documentation standards — AGENTS.md, README, component API docs",
        "content": (
            "## Documentation Standards\n"
            "- Every project needs: README.md, AGENTS.md (for AI agents)\n"
            "- README structure: What it does → Quick start → Configuration → API reference\n"
            "- Component props: document all props with type and default value\n"
            "- AGENTS.md: describe agent capabilities, tools available, constraints\n"
            "- Environment variables: document in .env.example with descriptions\n"
            "- API endpoints: document request/response schemas with examples\n"
            "- Changelog: update CHANGELOG.md with every meaningful change"
        ),
    },
    "strategy": {
        "description": "Strategic planning — trade-offs, stakeholder buy-in, MVP first",
        "content": (
            "## Strategic Planning Process\n"
            "1. Define the problem clearly before proposing solutions\n"
            "2. List 3 options with trade-offs (cost, risk, time, reversibility)\n"
            "3. Identify the decision-maker and get explicit sign-off\n"
            "4. Start with the reversible option when uncertain\n"
            "5. Track metrics before and after to prove impact\n"
            "6. Write a one-pager for any initiative taking >1 week\n"
            "7. Build MVPs to validate assumptions before full implementation\n"
            "8. Kill features that don't move key metrics after 30 days"
        ),
    },
    "style-review": {
        "description": "UI style review — cards, hero sections, container widths, hover effects",
        "content": (
            "## Style Review Checklist\n"
            "Cards:\n"
            "- Border: 1px solid with 5-10% opacity white/black\n"
            "- Background: semi-transparent (glass morphism preferred)\n"
            "- Border-radius: 12-16px minimum for modern look\n"
            "- Shadow: subtle box-shadow, not harsh\n\n"
            "Hero Sections:\n"
            "- Headline: 48-72px, bold weight (700-900)\n"
            "- Max-width: 720px for readability\n"
            "- CTA button: high contrast, 44px+ touch target\n\n"
            "Container Widths:\n"
            "- Content: max-w-prose (65ch) for text\n"
            "- Layout: max-w-7xl (1280px) for page\n\n"
            "Hover Effects:\n"
            "- Scale: transform scale(1.02) — max 5%\n"
            "- Duration: 150-200ms ease-out\n"
            "- Never animate layout properties (width, height, margin)\n\n"
            "Breadcrumbs:\n"
            "- Separator: use / or › not >\n"
            "- Current page: no link, muted color"
        ),
    },
    "nextjs-patterns": {
        "description": "Next.js App Router, framer-motion gotchas, Formspree integration",
        "content": (
            "## Next.js App Router Patterns\n"
            "- Use Server Components by default, Client Components only when needed\n"
            "- `'use client'` goes at top of file, before imports\n"
            "- Data fetching: async Server Components, not useEffect + fetch\n"
            "- Image: always use next/image with width/height or fill\n"
            "- Fonts: use next/font for performance\n\n"
            "Framer-motion Gotchas:\n"
            "- Wrap AnimatePresence around conditional renders\n"
            "- Key prop on animated elements must change for exit animations\n"
            "- `layoutId` for shared element transitions between routes\n"
            "- Never animate display property — use opacity/scale instead\n\n"
            "Formspree:\n"
            "- Set up form with `action='https://formspree.io/f/{id}'`\n"
            "- Use ajaxForm for SPA without page reload"
        ),
    },
    "frontend-designer": {
        "description": "Bold, distinctive frontend design — typography, color, motion, backgrounds",
        "content": (
            "## Frontend Design Philosophy\n"
            "Avoid generic AI aesthetics — no gradient-purple-to-pink everything.\n\n"
            "Typography:\n"
            "- Mix weights dramatically: 900 for hero, 400 for body\n"
            "- Letter-spacing: -0.02em to -0.05em for large headings\n"
            "- Line-height: 1.1-1.2 for display, 1.6-1.7 for body\n\n"
            "Color:\n"
            "- One bold accent color + near-black/near-white\n"
            "- Dark mode: background #0a0a0f not pure #000000\n"
            "- Never use more than 3 accent colors per page\n\n"
            "Motion:\n"
            "- Spring animations over ease — feels physical\n"
            "- Stagger children: 0.05-0.08s delay between items\n"
            "- Always respect `prefers-reduced-motion`\n\n"
            "Backgrounds:\n"
            "- Radial gradients from corner, not center\n"
            "- Dark glass: bg-black/40 + backdrop-blur-md + border-white/10\n\n"
            "Avoid:\n"
            "- Card carousels with visible scroll indicators on desktop\n"
            "- Hover tooltips containing critical information\n"
            "- Centered layouts for data-heavy UIs"
        ),
    },
}

# ── Agent → Skills Mapping ─────────────────────────────────────────────────────
AGENT_SKILL_MAP: dict[str, list[str]] = {
    "coder":        ["coding", "testing", "debugging", "performance"],
    "architect":    ["architecture", "devops", "documentation"],
    "devops":       ["devops", "security", "performance"],
    "researcher":   ["documentation"],
    "orchestrator": ["architecture"],
}

# ── Agent UI Metadata ──────────────────────────────────────────────────────────
AGENT_PERSONAS: dict[str, dict] = {
    "general":       {"name": "Assistant",        "icon": "🤖", "color": "#6366f1"},
    "coder":         {"name": "Coder Agent",       "icon": "💻", "color": "#10b981"},
    "researcher":    {"name": "Researcher Agent",  "icon": "🔍", "color": "#f59e0b"},
    "architect":     {"name": "Architect Agent",   "icon": "🏗️", "color": "#8b5cf6"},
    "orchestrator":  {"name": "Orchestrator",      "icon": "🎯", "color": "#ef4444"},
    "devops":        {"name": "DevOps Agent",      "icon": "⚙️", "color": "#06b6d4"},
    "self_critic":   {"name": "Self-Critic",       "icon": "🔬", "color": "#ec4899"},
    "qa":            {"name": "QA Tester",         "icon": "🧪", "color": "#84cc16"},
    "code_reviewer": {"name": "Code Reviewer",     "icon": "👁️", "color": "#fb923c"},
}


def get_skills_for_agent(agent_id: str) -> str:
    """Return concatenated skill text for the given agent."""
    keys = AGENT_SKILL_MAP.get(agent_id, [])
    return "\n".join(SKILLS[k] for k in keys if k in SKILLS)
