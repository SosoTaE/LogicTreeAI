# Feature Update: Canvas Visualization & Multi-Model Broadcast

## New Features Added

### 1. Interactive Canvas Tree Visualization

The application now includes a powerful HTML5 Canvas-based visualization that renders your conversation tree as an interactive node graph.

#### Features:
- **Hierarchical Layout**: Messages are arranged in a tree structure with root nodes at the top
- **Color-Coded Nodes**:
  - Blue: User messages
  - Green: GPT/OpenAI responses
  - Purple: Claude/Anthropic responses
  - Yellow: Gemini/Google responses
  - Red: Currently selected node
- **Interactive Navigation**: Click any node to view its conversation path
- **Pan & Zoom**:
  - Drag to pan around large conversation trees
  - Mouse wheel to zoom in/out
  - Zoom controls (+, -, Reset) in the top-right corner
- **Branch Indicators**: Nodes with multiple children show a count badge

#### Usage:
1. The canvas automatically updates when you send messages
2. Click any node in the tree to navigate to that point in the conversation
3. The text panel on the right shows the full conversation path to the selected node
4. Use the "Toggle View" button to switch between split view, canvas-only, or text-only

### 2. Multi-Model Broadcast

Send a single prompt to multiple AI models simultaneously and compare their responses side-by-side.

#### Features:
- **Multi-Select Interface**: Checkboxes allow you to select one or more models
- **Simultaneous Queries**: All selected models receive the same prompt with identical context
- **Graceful Error Handling**: If one model fails, others still respond
- **Branching Responses**: Each model's response creates a separate branch in the tree
- **Visual Comparison**: Easily navigate between different models' responses using the canvas

#### How to Use:
1. Select one or more models using the checkboxes above the message input
2. Type your message
3. Click "Send to Selected" - the message will be broadcast to all selected models
4. Each model creates its own response branch
5. Click on different response nodes in the canvas to compare answers

#### Supported Models:
- GPT-4o (OpenAI)
- Claude 3.5 Sonnet (Anthropic)
- Gemini 1.5 Pro (Google)
- GPT-4o Mini (OpenAI)
- Claude 3.5 Haiku (Anthropic)
- Gemini 1.5 Flash (Google)

### 3. Enhanced Navigation

#### Canvas Navigation:
- **Click nodes**: Jump to any point in the conversation
- **Drag to pan**: Move around large conversation trees
- **Scroll to zoom**: Use mouse wheel or trackpad gestures
- **Zoom controls**: +, -, and Reset buttons

#### View Modes:
- **Split View** (default): Canvas on left, text chat on right
- **Canvas Only**: Full-screen tree visualization
- **Text Only**: Traditional chat interface

Toggle between views using the "📊 Toggle View" button in the header.

## Technical Implementation

### Backend Changes (`app.py`)

The `/api/messages` endpoint now supports multi-model broadcast:

```python
POST /api/messages
{
    "conversation_id": 1,
    "parent_id": 5,
    "content": "Your message",
    "target_models": ["gpt-4o", "claude-3-5-sonnet-20241022", "gemini-1.5-pro"]
}
```

**Response**:
```json
{
    "status": "success",
    "user_message": {...},
    "assistant_messages": [
        {"id": 6, "model_used": "gpt-4o", ...},
        {"id": 7, "model_used": "claude-3-5-sonnet-20241022", ...},
        {"id": 8, "model_used": "gemini-1.5-pro", ...}
    ],
    "errors": null
}
```

### Frontend Components

#### New Files:
- **`static/canvas.js`**: TreeVisualizer class for canvas rendering
  - Tree layout algorithm
  - Node drawing and styling
  - Click detection and event handling
  - Pan/zoom functionality

#### Updated Files:
- **`templates/index.html`**:
  - Split-view layout
  - Canvas element
  - Multi-select checkbox UI
  - View toggle controls

- **`static/app.js`**:
  - TreeVisualizer integration
  - Multi-model selection logic
  - Canvas-text synchronization
  - Node navigation

- **`static/style.css`**:
  - Split-view styling
  - Canvas panel layout
  - Checkbox styling
  - Responsive design for mobile

## Usage Examples

### Example 1: Compare Multiple Models
1. Check boxes for GPT-4o, Claude 3.5 Sonnet, and Gemini 1.5 Pro
2. Type: "Explain quantum entanglement in simple terms"
3. Click "Send to Selected"
4. View all three responses in the canvas as separate branches
5. Click each response node to read and compare

### Example 2: Deep Branching Conversations
1. Start with one model (e.g., GPT-4o)
2. Have a conversation (5-6 messages)
3. Click on an earlier message in the canvas
4. Select multiple models
5. Send a follow-up question from that point
6. Now you have alternate conversation paths to explore

### Example 3: Visual Tree Exploration
1. Create a large conversation with many branches
2. Use canvas pan/zoom to navigate the tree structure
3. Click nodes to instantly see their conversation context
4. Use the canvas to understand the conversation topology

## API Key Requirements

To use multi-model broadcast, you need API keys for all models you want to query:
- **OpenAI**: Get from https://platform.openai.com/api-keys
- **Anthropic**: Get from https://console.anthropic.com/
- **Google Gemini**: Get from https://makersuite.google.com/app/apikey

Configure keys in Settings (⚙️ button).

## Performance Notes

- **Multi-model queries**: Process sequentially (not parallel) to avoid rate limits
- **Large trees**: Canvas performance remains smooth with 100+ nodes
- **Memory usage**: Entire conversation tree loads into browser memory
- **API costs**: Multi-broadcast multiplies your API costs by the number of selected models

## Troubleshooting

### Canvas not showing:
- Check browser console for JavaScript errors
- Ensure canvas.js loads before app.js
- Try refreshing the page

### Multi-model broadcast fails:
- Verify all API keys are configured
- Check that at least one model checkbox is selected
- See error messages for specific model failures

### Navigation issues:
- Click Reset View button to re-center the canvas
- Refresh the page to reload the conversation tree
- Check that conversation was loaded successfully

## Future Enhancements

Possible additions:
- Parallel API calls for faster multi-model broadcast
- Export conversation tree as image/SVG
- Minimap for very large trees
- Search/filter nodes
- Custom node styling and labels
- Tree layout algorithms (radial, force-directed)
- Side-by-side response comparison panel
