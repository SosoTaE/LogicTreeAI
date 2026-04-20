# Branching LLM Chat Application

A sophisticated chat application that enables branching, non-linear conversations with multiple LLMs (OpenAI GPT, Anthropic Claude, and Google Gemini). Create infinite conversation branches from any point in the chat history and explore different AI responses.

## Features

- **Branching Conversations**: Create multiple response branches from any point in the conversation
- **Multi-LLM Support**: Seamlessly switch between GPT-4o, Claude 3.5, and Gemini 1.5
- **Tree Navigation**: Navigate between different response branches with intuitive UI controls
- **Context Awareness**: Each branch maintains its own conversation history from root to leaf
- **Modern Dark UI**: Clean, responsive interface with dark mode styling
- **Persistent Storage**: SQLite database for conversation history

## Tech Stack

- **Frontend**: Vanilla HTML, CSS, and JavaScript (no frameworks)
- **Backend**: Python with Flask
- **Database**: SQLite with SQLAlchemy ORM
- **LLM Integration**: Official Python SDKs for OpenAI, Anthropic, and Google GenAI

## Project Structure

```
mindmap/
├── app.py                  # Flask application with API routes
├── models.py              # SQLAlchemy database models
├── llm_service.py         # LLM integration service layer
├── config.py              # Application configuration
├── requirements.txt       # Python dependencies
├── templates/
│   └── index.html        # Main application page
├── static/
│   ├── style.css         # Dark mode CSS styling
│   └── app.js            # Frontend JavaScript for branching UI
└── README.md
```

## Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Setup Steps

1. **Clone or navigate to the project directory**:
   ```bash
   cd /home/sosotae/Documents/programming/mindmap
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize the database** (happens automatically on first run):
   The database will be created when you first start the application.

## Running the Application

1. **Start the Flask server**:
   ```bash
   python app.py
   ```

2. **Open your browser** and navigate to:
   ```
   http://localhost:5000
   ```

3. **Configure API Keys**:
   - Click the "⚙️ Settings" button in the sidebar
   - Enter your API keys for the LLMs you want to use:
     - **OpenAI**: Get your API key from https://platform.openai.com/api-keys
     - **Anthropic**: Get your API key from https://console.anthropic.com/
     - **Google Gemini**: Get your API key from https://makersuite.google.com/app/apikey
   - Click "Save Settings"

   Note: You only need to configure keys for the LLMs you plan to use.

## Usage Guide

### Creating a Conversation

1. Click the "+ New Chat" button in the sidebar
2. A new conversation will be created and selected

### Sending Messages

1. Select a model from the dropdown (GPT-4o, Claude, or Gemini)
2. Type your message in the text area
3. Press Enter or click "Send"
4. The LLM will respond, creating a linear conversation path

### Creating Branches

To create a branch from any point in the conversation:

1. Navigate to the message you want to branch from (see Branch Navigation below)
2. Type a new message - this will create a new branch from that point
3. The new response will be saved as an alternative branch

### Branch Navigation

When a message has multiple responses, you'll see navigation controls like "< 1 of 3 >" below it:

- Click **←** to view the previous response branch
- Click **→** to view the next response branch
- The number shows which branch you're viewing (e.g., "2 of 3" means viewing the 2nd of 3 branches)

The conversation tree automatically updates to show the currently selected path.

### Managing Conversations

- **Switch Conversations**: Click any conversation in the sidebar to switch to it
- **Delete Conversation**: Click the "Delete Chat" button in the header
- **View All Conversations**: The sidebar shows all your conversations, ordered by creation date

## Database Schema

### Settings Table
Stores API keys in a simple key-value format:
- `key`: Setting name (openai_key, anthropic_key, gemini_key)
- `value`: API key value

### Conversation Table
Represents each chat tree:
- `id`: Primary key
- `title`: Conversation title
- `created_at`: Timestamp

### Message Table
Core branching model using Adjacency List pattern:
- `id`: Primary key
- `conversation_id`: Foreign key to Conversation
- `parent_id`: Foreign key to parent Message (NULL for root messages)
- `role`: Message role (system/user/assistant)
- `content`: Message text
- `model_used`: Which LLM generated this response
- `created_at`: Timestamp

The `get_conversation_path()` method reconstructs the full context from any node to the root.

## API Endpoints

### Settings
- `GET /api/settings` - Fetch all API keys
- `POST /api/settings` - Update API keys

### Conversations
- `GET /api/conversations` - List all conversations
- `POST /api/conversations` - Create a new conversation
- `GET /api/conversations/<id>/tree` - Get the full message tree for a conversation
- `DELETE /api/conversations/<id>` - Delete a conversation

### Messages
- `POST /api/messages` - Create a new message and get LLM response
  - Parameters: `conversation_id`, `parent_id`, `content`, `target_model`

## Supported Models

### OpenAI
- `gpt-4o` - GPT-4 Optimized (most capable)
- `gpt-4o-mini` - Smaller, faster GPT-4 variant
- `gpt-4-turbo` - GPT-4 Turbo
- `o1-preview` - O1 Preview (reasoning model)
- `o1-mini` - O1 Mini (faster reasoning)

### Anthropic
- `claude-3-5-sonnet-20241022` - Claude 3.5 Sonnet (most capable)
- `claude-3-5-haiku-20241022` - Claude 3.5 Haiku (faster)
- `claude-3-opus-20240229` - Claude 3 Opus

### Google Gemini
- `gemini-2.0-flash-exp` - Gemini 2.0 Flash Experimental (newest)
- `gemini-1.5-pro` - Gemini 1.5 Pro (most capable)
- `gemini-1.5-flash` - Gemini 1.5 Flash (faster)

## Troubleshooting

### "API key not configured" error
- Open Settings and enter your API key for the selected model
- Make sure you clicked "Save Settings"

### Messages not appearing
- Check the browser console for errors (F12)
- Ensure the Flask server is running
- Verify your API key is valid

### Database errors
- Delete `chat_app.db` and restart the application to reset the database
- Check file permissions in the application directory

## Development

### Adding New LLM Providers

1. Add the SDK to `requirements.txt`
2. Create a new method in `llm_service.py` (e.g., `call_new_provider`)
3. Update the `call_llm` routing logic
4. Add the model options to the dropdown in `index.html`

### Customizing the UI

- **Colors**: Edit CSS variables in `static/style.css` (lines 1-20)
- **Layout**: Modify the HTML structure in `templates/index.html`
- **Behavior**: Update the JavaScript in `static/app.js`

## License

This project is open source and available for educational and personal use.

## Acknowledgments

Built with:
- [Flask](https://flask.palletsprojects.com/) - Web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - Database ORM
- [OpenAI API](https://platform.openai.com/) - GPT models
- [Anthropic API](https://www.anthropic.com/) - Claude models
- [Google GenAI](https://ai.google.dev/) - Gemini models
# LogicTreeAI
