# Multi-Agent Intelligence Architecture

Falso features a modular multi-agent system capable of task decomposition, parallel execution, shared memory context, and loop prevention.

```
                               ┌─────────────────────────┐
                               │     User Request        │
                               └───────────┬─────────────┘
                                           │
                               ┌───────────▼─────────────┐
                               │    AgentManager         │
                               │ (Spawns/Monitors/Logs)  │
                               └───────────┬─────────────┘
                                           │
                               ┌───────────▼─────────────┐
                               │    PlannerAgent         │
                               │ (Decomposes Subtasks)   │
                               └─────┬──────────────┬────┘
                                     │              │
                   ┌─────────────────▼──┐        ┌──▼────────────────┐
                   │   ResearchAgent    │        │  DeveloperAgent   │
                   └─────────────────┬──┘        └──┬────────────────┘
                                     │              │
                               ┌─────▼──────────────▼────┐
                               │    SharedTaskContext    │
                               │  (MemoryService Recall) │
                               └─────────────────────────┘
```

---

## Agent Roster

- **`PlannerAgent`**: Task decomposition and workflow planning.
- **`ResearchAgent`**: Codebase analysis and information retrieval.
- **`DeveloperAgent`**: Code generation, review, and verification.
- **`MemoryAgent`**: Long-term memory query and storage specialist.
- **`AutomationAgent`**: Scheduled job and workflow automation.
- **`VisionAgent`**: Visual frame analysis and OCR.

---

## REST API Endpoints

- **`GET /api/v1/agents`**: List all available specialized agents.
- **`POST /api/v1/agents/execute`**: Execute a task using a specific agent.
- **`POST /api/v1/agents/decompose`**: Decompose a complex user prompt, execute independent subtasks concurrently, and aggregate results.
