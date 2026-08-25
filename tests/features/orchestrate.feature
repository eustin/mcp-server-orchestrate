Feature: Orchestrate MCP Server Lifecycle and Gate Enforcement
  As an AI coding assistant and human developer pair
  We want an MCP server enforcing a structured 4-phase workflow (Design -> Plan -> Execute -> Verify)
  So that complex coding tasks are systematically analyzed, planned, executed by subagents, and verified

  Background:
    Given a project workspace directory initialized with Git or OpenCode configuration

  # ============================================================================
  # 1. LIFECYCLE & LOCK MANAGEMENT
  # ============================================================================

  @lifecycle @lock
  Scenario: Initialize a new orchestration session
    Given no active orchestration session exists in workspace
    When client calls tool "orchestrate_init" with:
      | parameter        | value                  |
      | task_description | Add JWT Authentication |
    Then server creates atomic lock file ".orchestrator/session.lock"
    And server creates state file ".orchestrator/session.json" containing:
      | field                  | value                  |
      | current_phase          | DESIGN                 |
      | current_phase_approved | false                  |
      | task_description       | Add JWT Authentication |
    And server creates default ".orchestrator/project-mandates.md" if not present
    And tool output returns session ID, phase "DESIGN", and DESIGN phase SOP instructions

  @lifecycle @lock
  Scenario: Prevent concurrent orchestration sessions when lock is active
    Given an active orchestration session exists with running process PID
    When client calls tool "orchestrate_init" with:
      | parameter        | value            |
      | task_description | Refactor Database|
    Then tool returns lock error with active session ID and PID
    And instructs user to archive current session before starting a new one

  @lifecycle @lock
  Scenario: Reclaim stale lock from terminated process
    Given lock file ".orchestrator/session.lock" exists with PID of a terminated process
    When client calls tool "orchestrate_init" with:
      | parameter        | value       |
      | task_description | Resume Work |
    Then server automatically cleans up stale lock
    And initializes new session in "DESIGN" phase

  @lifecycle @status
  Scenario: Query high-level session status during active workflow
    Given an active orchestration session in phase "EXECUTE"
    When client calls tool "orchestrate_status"
    Then server returns high-level status:
      | field          | value   |
      | active_session | true    |
      | phase          | EXECUTE |

  @lifecycle @status
  Scenario Outline: Query high-level session status across all phases
    Given an active orchestration session in phase "<Phase>"
    When client calls tool "orchestrate_status"
    Then server returns active_session true and phase "<Phase>"

    Examples:
      | Phase    |
      | DESIGN   |
      | PLAN     |
      | EXECUTE  |
      | VERIFY   |
      | COMPLETE |

  @lifecycle @status
  Scenario: Query status when no session is active
    Given no active orchestration session exists
    When client calls tool "orchestrate_status"
    Then server returns active_session false and message "No active orchestration session"

  @lifecycle @archive
  Scenario: Force archive session and release lock
    Given an active orchestration session with ID "2026-08-23-jwt-auth"
    And existing files in ".orchestrator/":
      | file         |
      | session.json |
      | design.md    |
      | plan.md      |
    When client calls tool "orchestrate_archive" with force=true
    Then server releases and removes ".orchestrator/session.lock"
    And moves all session files to ".orchestrator/archive/2026-08-23-jwt-auth/"
    And tool output confirms session archived and lock released

  # ============================================================================
  # 2. HUMAN APPROVAL GATE
  # ============================================================================

  @gates @approval
  Scenario: Human user approves current phase deliverables
    Given an active session in phase "DESIGN" with current_phase_approved false
    When client calls tool "orchestrate_approve"
    Then server sets current_phase_approved to true in ".orchestrator/session.json"
    And appends "phase_approved" event to state history
    And tool output confirms "Phase 'DESIGN' approved by user. Machine verification is now enabled."

  @gates @approval
  Scenario: Reject approval when no session is active
    Given no active orchestration session exists
    When client calls tool "orchestrate_approve"
    Then tool returns error "No active session state found."

  # ============================================================================
  # 3. PHASE VERIFICATION & TRANSITIONS
  # ============================================================================

  # --- DESIGN PHASE ---
  @gates @design
  Scenario: Fail DESIGN verification when design.md is missing
    Given an active session in phase "DESIGN"
    And file ".orchestrator/design.md" does not exist
    When client calls tool "orchestrate_verify"
    Then verification fails with error:
      """
      Missing required deliverable: .orchestrator/design.md
      """
    And session phase remains "DESIGN"

  @gates @design
  Scenario: Fail DESIGN verification when human approval is missing
    Given an active session in phase "DESIGN"
    And file ".orchestrator/design.md" exists with all required sections
    And current_phase_approved is false
    When client calls tool "orchestrate_verify"
    Then verification fails with error:
      """
      GATE BLOCKED: Design deliverable .orchestrator/design.md is ready, but human approval is required.
      """
    And session phase remains "DESIGN"

  @gates @design
  Scenario: Fail DESIGN verification when required headings are missing
    Given an active session in phase "DESIGN" with current_phase_approved true
    And file ".orchestrator/design.md" lacks "## Self-Confidence Audit"
    When client calls tool "orchestrate_verify"
    Then verification fails with error:
      """
      Missing required Design Document section: '## Self-Confidence Audit'
      """
    And session phase remains "DESIGN"

  @gates @design
  Scenario: Pass DESIGN verification and advance to PLAN phase
    Given an active session in phase "DESIGN" with current_phase_approved true
    And file ".orchestrator/design.md" contains sections:
      | section                  |
      | ## Requirements          |
      | ## Architecture          |
      | ## Self-Confidence Audit |
    When client calls tool "orchestrate_verify"
    Then verification succeeds
    And server advances current_phase to "PLAN"
    And resets current_phase_approved to false
    And tool output returns PLAN phase SOP instructions

  # --- PLAN PHASE ---
  @gates @plan
  Scenario: Fail PLAN verification when plan.md is missing
    Given an active session in phase "PLAN"
    And file ".orchestrator/plan.md" does not exist
    When client calls tool "orchestrate_verify"
    Then verification fails with error "Missing required deliverable: .orchestrator/plan.md"
    And session phase remains "PLAN"

  @gates @plan
  Scenario: Fail PLAN verification when unapproved by human
    Given an active session in phase "PLAN"
    And file ".orchestrator/plan.md" exists and has valid structure
    And current_phase_approved is false
    When client calls tool "orchestrate_verify"
    Then verification fails with error:
      """
      GATE BLOCKED: Plan deliverable .orchestrator/plan.md is ready, but human approval is required.
      """
    And session phase remains "PLAN"

  @gates @plan
  Scenario: Fail PLAN verification when task tags or specification headers are invalid
    Given an active session in phase "PLAN" with current_phase_approved true
    When file ".orchestrator/plan.md" has task checkbox missing "(Agent: <role>)" or "(Target: <path>)" or "(blocked_by: <deps>)"
    Then verification fails listing specific task format violations
    And session phase remains "PLAN"

  @gates @plan
  Scenario: Fail PLAN verification when final barrier task is not implementation-reviewer
    Given an active session in phase "PLAN" with current_phase_approved true
    When last task in ".orchestrator/plan.md" is not assigned to "Agent: implementation-reviewer"
    Then verification fails with error:
      """
      Plan MUST end with a final task assigned to 'Agent: implementation-reviewer', blocked by all prior tasks.
      """
    And session phase remains "PLAN"

  @gates @plan
  Scenario: Fail PLAN verification when test command is missing or "None"
    Given an active session in phase "PLAN" with current_phase_approved true
    When ".orchestrator/plan.md" has "Test command: None" or missing test command
    Then verification fails with error:
      """
      Plan Document must specify a valid executable 'Test command: <cmd>' under '## Verification' ('None' or empty is forbidden).
      """
    And session phase remains "PLAN"

  @gates @plan
  Scenario: Pass PLAN verification and advance to EXECUTE phase
    Given an active session in phase "PLAN" with current_phase_approved true
    And file ".orchestrator/plan.md" satisfies all schema, barrier, and test command rules
    When client calls tool "orchestrate_verify"
    Then verification succeeds
    And server advances current_phase to "EXECUTE"
    And resets current_phase_approved to false
    And tool output returns EXECUTE phase delegation rules

  # --- EXECUTE PHASE ---
  @gates @execute
  Scenario: Fail EXECUTE verification when tasks remain unchecked
    Given an active session in phase "EXECUTE"
    And file ".orchestrator/plan.md" contains unchecked item "- [ ] Implement token hashing"
    When client calls tool "orchestrate_verify"
    Then verification fails with error indicating unfinished tasks
    And session phase remains "EXECUTE"

  @gates @execute
  Scenario: Fail EXECUTE verification when target files are missing or empty
    Given an active session in phase "EXECUTE"
    And all tasks in ".orchestrator/plan.md" are marked checked "- [x]"
    And target file "src/auth/jwt.py" does not exist or has 0 bytes
    When client calls tool "orchestrate_verify"
    Then verification fails with error identifying missing or 0-byte target file
    And session phase remains "EXECUTE"

  @gates @execute
  Scenario: Pass EXECUTE verification and advance to VERIFY phase
    Given an active session in phase "EXECUTE"
    And all tasks in ".orchestrator/plan.md" are marked checked "- [x]"
    And all target files exist and are non-empty
    When client calls tool "orchestrate_verify"
    Then verification succeeds
    And server advances current_phase to "VERIFY"
    And resets current_phase_approved to false
    And tool output returns VERIFY phase instructions

  # --- VERIFY PHASE ---
  @gates @verify
  Scenario: Fail VERIFY phase when automated test execution fails
    Given an active session in phase "VERIFY"
    And plan specifies test command "pytest tests/test_auth.py"
    When client calls tool "orchestrate_verify"
    And test command execution exits with non-zero exit code
    Then verification fails returning test runner stdout and stderr tail
    And session phase remains "VERIFY"

  @gates @verify
  Scenario: Pass VERIFY phase when automated tests pass
    Given an active session in phase "VERIFY"
    And plan specifies test command "pytest tests/test_auth.py"
    When client calls tool "orchestrate_verify"
    And test command execution exits with exit code 0
    Then verification succeeds
    And server advances current_phase to "COMPLETE"
    And tool output returns COMPLETE phase summary and archive prompt

  # ============================================================================
  # 4. DAG TASK SCHEDULING & FILE COLLISION GUARD
  # ============================================================================

  @dag @parallel
  Scenario: Build execution batches for independent tasks
    Given ".orchestrator/plan.md" defines tasks:
      | id | target        | blocked_by |
      | T1 | src/models.py | []         |
      | T2 | src/utils.py  | []         |
      | T3 | src/api.py    | [T1, T2]   |
    When client calls tool "orchestrate_get_dag_batches"
    Then server returns 2 execution batches:
      | batch | task_ids |
      | 1     | [T1, T2] |
      | 2     | [T3]     |

  @dag @collision
  Scenario: Serialize tasks modifying identical target file
    Given ".orchestrator/plan.md" defines tasks:
      | id | target        | blocked_by |
      | T1 | src/auth.py   | []         |
      | T2 | src/auth.py   | []         |
    When client calls tool "orchestrate_get_dag_batches"
    Then server applies file collision guard
    And serializes T2 behind T1 across distinct batches:
      | batch | task_ids |
      | 1     | [T1]     |
      | 2     | [T2]     |
