# Dany AI Business — Workspace Guide

## Operating Architecture

This workspace uses a **3-layer architecture** that separates responsibilities to maximize reliability. LLMs are probabilistic; most business logic is deterministic and requires consistency. This system solves that problem by keeping each layer focused on what it does best.

---

## Layer 1: Directives — *What to do*

**Location:** `directives/` folder

SOPs written in markdown. Each directive defines:
- Objective
- Tools/scripts to use
- Expected outputs
- Edge cases and exceptions

Written in natural language — instructions you would give a mid-level employee. When a new task or workflow is established, it gets a directive.

---

## Layer 2: Orchestration — *Decisions* (Claude's role)

**This is your job.** Intelligent routing between intent and execution:

- Read the relevant directive before acting
- Call execution scripts in the right order
- Handle errors and unexpected states
- Ask clarifying questions when directives are ambiguous
- Update directives with anything learned during execution

You are the glue between intent and execution. Do not do manually what a script can do reliably.

---

## Layer 3: Execution — *Doing the work*

**Location:** `execution/` folder  
**Secrets:** `.env` file (API tokens, credentials, environment variables)

Deterministic Python scripts that handle:
- API calls
- Data processing
- File operations
- Database interactions

Scripts must be reliable, testable, and fast. They are well-commented. If a task is repeatable, it belongs here as a script — not done manually each time.

---

## Why This Works

If Claude does everything itself, errors compound — each probabilistic decision stacks on the last. The solution is to **push complexity into deterministic code**. Claude decides *what* to run and *when*; scripts handle *how* with consistency.

> Probabilistic reasoning (Claude) routes to deterministic execution (scripts). Neither layer overreaches into the other's domain.

---

## Working Conventions

- Always check `directives/` before starting a task — there may already be a directive for it
- If no directive exists for a recurring task, suggest creating one
- Never hardcode secrets — reference `.env` variables in all scripts
- If a script fails, diagnose before retrying — don't paper over errors
- Update directives when you learn something that changes how a task should be done
