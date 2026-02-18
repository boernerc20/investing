# Project-Specific Claude Optimization

## Model Strategy for This Project

Default agent model preferences:
- Exploration/Research: **haiku**
- Implementation: **sonnet**
- Complex reasoning: **opus** (use sparingly)

## Project-Specific Rules

### Agent Team Configuration

For this project's workflows, optimize as follows:

```
# Research phase - always use Haiku
Task(subagent_type="Explore", model="haiku", prompt="...")

# Implementation - use Sonnet (or Haiku for simple tasks)
Task(subagent_type="general-purpose", model="sonnet", prompt="...")

# Critical decisions only - Opus
Task(subagent_type="Plan", model="opus", prompt="...")
```

### Message Conservation

1. Batch file operations - read multiple files in parallel
2. Use direct Grep/Glob instead of agents for known patterns
3. Combine related tasks in single requests

### Token Conservation

1. Read files with offset/limit when possible
2. Use grep with head_limit to avoid huge outputs
3. Avoid reading build artifacts / dependencies

## Project File Patterns to Avoid

Add patterns for files that shouldn't be read unnecessarily:
- `node_modules/**`
- `build/**`
- `dist/**`
- `*.min.js`
- `package-lock.json` (unless specifically needed)

## Cost-Aware Workflow

For typical tasks in this project:

**Feature Development:**
1. Haiku: Research existing patterns
2. Direct tools: Read specific files
3. Sonnet: Implement changes
4. Direct tools: Verify changes

**Bug Investigation:**
1. Haiku: Search for related code
2. Direct tools: Read relevant files
3. Sonnet: Analyze and fix (or Opus if critical)
4. Direct tools: Test fix

**Refactoring:**
1. Direct Grep: Find all occurrences
2. Haiku: Understand scope of changes
3. Sonnet: Implement refactoring
4. Direct tools: Verify consistency

---

*Copy this file to project root and customize for project-specific needs*
