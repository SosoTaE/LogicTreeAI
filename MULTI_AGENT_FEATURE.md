# Multi-Agent Conversation Feature

## Overview

This feature enables multiple LLM models to collaborate and discuss problems together. Multiple AI models can have structured conversations where they build on each other's responses to solve complex problems collaboratively.

## Architecture

### Backend Components

#### 1. **MultiAgentService** (`multi_agent_service.py`)
Orchestrates multi-agent conversations with the following capabilities:
- **Discussion Rounds**: Manages turn-based conversations between multiple LLMs
- **Context Building**: Each model sees all previous responses from other models
- **Role Assignment**: Optional role assignments for specialized perspectives
- **Synthesis**: Combines discussion into coherent conclusions

#### 2. **Database Models** (`models.py`)
Two new tables added:

**MultiAgentSession**
- Stores discussion session metadata
- Fields: title, initial_problem, participating_models, model_roles, max_rounds, status
- Status can be: active, completed, or stopped

**MultiAgentTurn**
- Stores individual model responses
- Fields: round_number, model_name, model_role, content, duration, error
- Linked to sessions with cascade delete

#### 3. **API Endpoints** (`app.py`)
Seven new endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/multi-agent/sessions` | GET | List all user's sessions |
| `/api/multi-agent/sessions` | POST | Create new session |
| `/api/multi-agent/sessions/<id>` | GET | Get session details |
| `/api/multi-agent/sessions/<id>/continue` | POST | Run next round |
| `/api/multi-agent/sessions/<id>/stop` | POST | Stop session early |
| `/api/multi-agent/sessions/<id>/synthesize` | POST | Generate synthesis |
| `/api/multi-agent/sessions/<id>` | DELETE | Delete session |

### Frontend Components

#### 1. **UI Elements** (`templates/index.html`)
- **Sidebar Button**: "Multi-AI" button with groups icon
- **Sessions Panel**: Lists all multi-agent sessions with status indicators
- **Creation Modal**: Form to configure and start discussions
- **View Modal**: Display discussion rounds and manage sessions

#### 2. **JavaScript Logic** (`static/multi_agent.js`)
- Session management (create, view, list)
- Real-time discussion rendering
- Round continuation
- Synthesis generation

## How to Use

### 1. Starting a Multi-Agent Discussion

1. Click the **"Multi-AI"** button in the left sidebar
2. Click **"+ New"** to open the creation modal
3. Fill in the form:
   - **Session Title**: Descriptive name for the discussion
   - **Problem/Question**: The issue for AIs to discuss
   - **Participating Models**: Select 2 or more models (checkboxes)
   - **Max Rounds**: Number of discussion rounds (1-10)
4. Click **"Start Discussion"**

The first round starts automatically. Each selected model will:
- Receive the problem statement
- See all previous responses (from round 2 onwards)
- Generate their perspective
- Build on other models' ideas

### 2. Viewing a Discussion

Click on any session in the Multi-AI panel to view:
- **Problem Statement**: The original question
- **Discussion Rounds**: All model responses organized by round
- **Status**: Active, completed, or stopped
- **Progress**: Current round vs. max rounds

Each turn shows:
- Model name and role (if assigned)
- Response time
- Full response with markdown rendering

### 3. Continuing a Discussion

If the session is active and hasn't reached max rounds:
1. Open the session view
2. Click **"Continue Discussion"**
3. The next round will execute with all models

### 4. Synthesizing Results

To get a coherent summary:
1. Open the session view
2. Click **"Synthesize"**
3. Choose which model should create the synthesis
4. View the synthesized conclusion

### 5. Stopping a Discussion

To end a discussion early:
1. Open the session view
2. Click **"Stop Session"**
3. Confirm the action

## Example Use Cases

### 1. **Problem Solving**
```
Problem: "Design a scalable architecture for a real-time chat application"
Models: gpt-4o, claude-3-7-sonnet, gemini-1.5-pro
Rounds: 3

Round 1: Each model proposes initial architecture
Round 2: Models critique and build on each other's proposals
Round 3: Models converge on best practices and final design
```

### 2. **Code Review**
```
Problem: "Review this Python function for performance and security issues: [code]"
Models: gpt-4o (general), claude-3 (security focus), local/qwen (performance)
Roles: General Reviewer, Security Expert, Performance Analyst
Rounds: 2

Round 1: Each model identifies issues from their perspective
Round 2: Models discuss trade-offs and recommendations
```

### 3. **Research & Analysis**
```
Problem: "Analyze the pros and cons of microservices vs monolithic architecture"
Models: Multiple Claude and GPT variants
Rounds: 4

Each round deepens the analysis with different perspectives
```

### 4. **Creative Collaboration**
```
Problem: "Write a story about AI collaboration"
Models: 3-4 different models
Rounds: 5

Each model adds to the story, building on previous contributions
```

## Technical Details

### Discussion Flow

```
User creates session
    ↓
Round 1: All models receive initial problem
    ↓
Each model generates response (parallel)
    ↓
Responses saved to database
    ↓
Round 2: All models receive:
    - Initial problem
    - All Round 1 responses
    ↓
Each model generates response building on discussion
    ↓
... continues until max_rounds reached
```

### Prompt Structure

Each model receives:
```
You are participating in a multi-agent discussion with other AI models
to collaboratively solve a problem.

Your assigned role: [if specified]

Original Problem:
[problem text]

--- Previous Discussion ---
[Round X] model_name:
[response]
...
--- End of Previous Discussion ---

This is Round Y. Please:
1. Review the previous responses from other models
2. Identify key insights or points of agreement/disagreement
3. Build on or refine the discussion with your perspective
4. Suggest next steps or areas that need more exploration
```

### Synthesis Prompt

```
Please synthesize the following multi-agent discussion into a coherent
summary and conclusion.

[Full discussion history]

Please provide:
1. Key insights from the discussion
2. Points of consensus among the models
3. Areas of disagreement or different perspectives
4. A synthesized recommendation or conclusion
```

## Configuration

### Model Roles (Optional)

You can assign roles to models for specialized perspectives:

```json
{
  "gpt-4o": "General Analysis",
  "claude-3-7-sonnet": "Security Expert",
  "gemini-1.5-pro": "Performance Specialist"
}
```

Currently, roles can only be set via API (future UI enhancement).

### Max Rounds

- Minimum: 1 round
- Maximum: 10 rounds
- Recommended: 3-5 rounds for most discussions

## API Usage Examples

### Create Session
```bash
curl -X POST http://localhost:5000/api/multi-agent/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Architecture Discussion",
    "initial_problem": "Design a microservices architecture",
    "participating_models": ["gpt-4o", "claude-3-7-sonnet", "gemini-1.5-pro"],
    "max_rounds": 3,
    "auto_start": true
  }'
```

### Continue Session
```bash
curl -X POST http://localhost:5000/api/multi-agent/sessions/1/continue
```

### Synthesize
```bash
curl -X POST http://localhost:5000/api/multi-agent/sessions/1/synthesize \
  -H "Content-Type: application/json" \
  -d '{"synthesis_model": "gpt-4o"}'
```

## Database Schema

### multi_agent_sessions
| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| user_id | Integer | Foreign key to users |
| title | String(200) | Session title |
| initial_problem | Text | Problem statement |
| participating_models | JSON | List of model names |
| model_roles | JSON | Optional role assignments |
| max_rounds | Integer | Maximum rounds |
| current_round | Integer | Current progress |
| status | String(20) | active/completed/stopped |
| created_at | DateTime | Creation timestamp |
| completed_at | DateTime | Completion timestamp |

### multi_agent_turns
| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| session_id | Integer | Foreign key to sessions |
| round_number | Integer | Which round |
| model_name | String(100) | Model identifier |
| model_role | String(200) | Assigned role |
| content | Text | Response content |
| duration | Float | Response time (seconds) |
| error | Text | Error message if failed |
| created_at | DateTime | Response timestamp |

## Future Enhancements

Potential improvements:
- [ ] Role assignment in UI
- [ ] Custom synthesis templates
- [ ] Export discussions as PDF/Markdown
- [ ] Voting mechanism for best responses
- [ ] Dynamic model selection per round
- [ ] Automatic stopping conditions (consensus detection)
- [ ] Discussion visualization (network graph)
- [ ] Model performance analytics
- [ ] Cost tracking per session

## Troubleshooting

### Models not appearing
- Check API keys are configured in Settings
- Ensure models are available for your account

### Session creation fails
- Verify at least 2 models are selected
- Check max_rounds is between 1-10
- Ensure problem field is not empty

### Round continues slowly
- Models are called in parallel but may take time
- Check network connectivity
- Some models are slower than others

### Synthesis fails
- Ensure the synthesis model is available
- Check there are successful turns to synthesize
- Verify API key for the synthesis model

## Performance Considerations

- Models are called in parallel using ThreadPoolExecutor
- Maximum 3 parallel workers by default (configurable)
- Database transactions are optimized
- Responses are streamed and saved incrementally

## Security

- All sessions are user-scoped (users only see their own)
- Sessions cascade delete with turns
- API keys are never exposed in responses
- Input validation on all parameters
