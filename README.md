# Multi-Agent LLM Chat Platform

A sophisticated chat application that enables branching conversations, multi-agent discussions, and collaborative problem-solving with multiple AI models (OpenAI GPT, Anthropic Claude, and Google Gemini).

**Author:** Gregory Kakhiani

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-3.0+-green.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

## ✨ Key Features

### 🌳 Branching Conversations
- Create multiple response branches from any point in the conversation
- Navigate between different AI responses with intuitive tree controls
- Each branch maintains its own conversation history from root to leaf
- Perfect for exploring different reasoning paths

### 🤝 Multi-Agent Discussions
- Enable multiple AI models to collaborate on complex problems
- Two conversation modes:
  - **Sequential**: Models take turns responding to each other
  - **Parallel**: All models respond simultaneously in rounds
- Assign roles/personas to each AI participant
- Human-in-the-loop: Interject your own messages into ongoing discussions
- Real-time discussion tracking with turn-by-turn visualization

### 🎯 AI Synthesis
- Synthesize multi-agent discussions into coherent conclusions
- Choose any model to analyze and summarize the discussion
- Automatic extraction of key insights, consensus points, and recommendations
- Synthesis displayed inline and included in exports

### 📄 Export & Documentation
- Export discussions to professional Word documents (.docx)
- Generate PDF reports with full formatting
- Exports include metadata, problem statement, all turns, and synthesis
- Automated filename generation with timestamps

### 🔐 User Management
- Multi-user support with role-based access control
- Admin and user roles with different permissions
- Secure password hashing with Werkzeug
- Session-based authentication

### 🎨 Modern Interface
- Clean, responsive dark-mode UI
- Material Design 3 inspired styling
- Real-time updates without page refreshes
- Mobile-friendly responsive design

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Installation

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd mindmap
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize the database**:
   ```bash
   python -c "from models import init_db; init_db()"
   ```

5. **Create an admin user**:
   ```bash
   python create_admin.py
   ```
   Follow the prompts to set up your admin account.

6. **Run the application**:
   ```bash
   python app.py
   ```

7. **Open your browser** and navigate to:
   ```
   http://localhost:5000
   ```

## 🔑 Configuration

### Setting Up API Keys

1. Log in to the application
2. Click the **⚙️ Settings** icon in the sidebar
3. Enter your API keys:
   - **OpenAI**: Get from [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
   - **Anthropic**: Get from [console.anthropic.com](https://console.anthropic.com/)
   - **Google Gemini**: Get from [makersuite.google.com/app/apikey](https://makersuite.google.com/app/apikey)
   - **Local Models** (optional): Configure custom endpoint URL and model name
4. Click **Save Settings**

*Note: You only need to configure keys for the LLMs you plan to use.*

## 📖 Usage Guide

### Branching Conversations

1. **Create a new chat**: Click "+ New Chat" in the sidebar
2. **Select a model** from the dropdown
3. **Send a message**: Type and press Enter or click Send
4. **Create branches**: Navigate to any message and send a new response
5. **Navigate branches**: Use ← → arrows when multiple branches exist

### Multi-Agent Discussions

1. **Open Multi-Agent Panel**: Click the "Multi-Agent" icon in the sidebar
2. **Create New Session**: Click "+ New" button
3. **Configure Discussion**:
   - Enter a title and problem statement
   - Select 2+ models to participate
   - Optionally assign roles (e.g., "critical thinker", "optimist")
   - Choose conversation mode (Sequential or Parallel)
   - Set maximum turns
4. **Start Discussion**: Click "Start Discussion"
5. **Monitor Progress**: Watch as models collaborate in real-time
6. **Interject** (optional): Add your own messages during the discussion
7. **Synthesize**: Select a model and click "Synthesize" for a summary
8. **Export**: Download as Word or PDF

### Exporting Discussions

- Click **Word** or **PDF** button in the session view
- Files include complete discussion history and synthesis
- Automatic naming with timestamps

## 🏗️ Architecture

### Project Structure

```
mindmap/
├── app.py                    # Flask application & API routes
├── models.py                 # SQLAlchemy database models
├── llm_service.py           # LLM integration & API calls
├── multi_agent_service.py   # Multi-agent orchestration
├── export_service.py        # Document export (DOCX/PDF)
├── auth.py                  # Authentication & authorization
├── config.py                # Application configuration
├── logging_config.py        # Logging setup
├── create_admin.py          # Admin user creation script
├── requirements.txt         # Python dependencies
├── templates/
│   ├── index.html          # Main application interface
│   └── login.html          # Login page
├── static/
│   ├── app.js              # Branching chat logic
│   ├── canvas.js           # Canvas rendering utilities
│   ├── multi_agent.js      # Multi-agent UI logic
│   └── style.css           # Application styling
└── logs/                    # Application logs
```

### Database Schema

**Users Table**
- Multi-user support with role-based permissions
- Secure password hashing

**Settings Table**
- Per-user API key storage
- Supports OpenAI, Anthropic, Gemini, and local models

**Conversations Table**
- Individual chat sessions
- Links to branching message tree

**Messages Table**
- Adjacency list pattern for tree structure
- Each message links to parent, enabling infinite branching

**MultiAgentSessions Table**
- Discussion metadata (title, problem, participants, status)
- Configuration (mode, roles, max rounds)
- Synthesis results

**MultiAgentTurns Table**
- Individual model responses in discussions
- Duration tracking, error handling
- Role assignments per turn

## 🤖 Supported Models

### OpenAI
- `gpt-4o` - GPT-4 Optimized
- `gpt-4o-mini` - Faster variant
- `gpt-4-turbo` - GPT-4 Turbo
- `o1-preview` - Reasoning model
- `o1-mini` - Faster reasoning

### Anthropic
- `claude-sonnet-4-20250514` - Claude Sonnet 4 (latest)
- `claude-3-7-sonnet-20250219` - Claude 3.7 Sonnet
- `claude-3-5-sonnet-20241022` - Claude 3.5 Sonnet
- `claude-3-5-haiku-20241022` - Claude 3.5 Haiku
- `claude-3-opus-20240229` - Claude 3 Opus

### Google Gemini
- `gemini-2.5-pro-exp-03-25` - Gemini 2.5 Pro (experimental)
- `gemini-2.0-flash-exp` - Gemini 2.0 Flash
- `gemini-1.5-pro` - Gemini 1.5 Pro
- `gemini-1.5-flash` - Gemini 1.5 Flash

### Local Models
- Configure custom endpoint URL
- Support for any OpenAI-compatible API

## 🔧 API Endpoints

### Authentication
- `POST /login` - User login
- `POST /logout` - User logout

### Settings
- `GET /api/settings` - Fetch user API keys
- `POST /api/settings` - Update API keys

### Conversations
- `GET /api/conversations` - List all conversations
- `POST /api/conversations` - Create new conversation
- `GET /api/conversations/<id>/tree` - Get message tree
- `DELETE /api/conversations/<id>` - Delete conversation

### Messages
- `POST /api/messages` - Send message & get AI response

### Models
- `GET /api/models` - List available models per provider

### Multi-Agent
- `GET /api/multi-agent/sessions` - List all sessions
- `POST /api/multi-agent/sessions` - Create new session
- `GET /api/multi-agent/sessions/<id>` - Get session details
- `POST /api/multi-agent/sessions/<id>/continue` - Continue discussion
- `POST /api/multi-agent/sessions/<id>/user-message` - Add user message
- `POST /api/multi-agent/sessions/<id>/stop` - Stop session
- `POST /api/multi-agent/sessions/<id>/synthesize` - Synthesize discussion
- `GET /api/multi-agent/sessions/<id>/export` - Export as DOCX/PDF

## 🛡️ Security

- Password hashing with Werkzeug
- Session-based authentication
- Role-based access control (Admin/User)
- SQL injection protection via SQLAlchemy ORM
- CSRF protection on forms

## 🐛 Troubleshooting

### "API key not configured" error
- Open Settings and enter your API key
- Ensure you clicked "Save Settings"
- Check that the key is valid for the selected model

### Models not appearing
- Verify API keys are configured
- Check browser console (F12) for errors
- Ensure Flask server is running

### Database errors
- Run migrations if schema has changed
- Check file permissions in application directory
- For fresh start: delete `chat_app.db` and reinitialize

### Export not working
- Check that `python-docx` and `reportlab` are installed
- Verify write permissions in application directory
- Check logs for detailed error messages

## 🔄 Development

### Adding New LLM Providers

1. Add SDK to `requirements.txt`
2. Create method in `llm_service.py` (e.g., `call_new_provider()`)
3. Update routing logic in `call_llm()`
4. Add models to dropdown in frontend

### Database Migrations

When schema changes are needed:
1. Update models in `models.py`
2. Create migration script (see `migrate_db.py` as example)
3. Run migration before starting app

### Running in Production

- Use a production WSGI server (e.g., Gunicorn):
  ```bash
  gunicorn -w 4 -b 0.0.0.0:5000 app:app
  ```
- Set up proper logging
- Use environment variables for sensitive configuration
- Consider using PostgreSQL instead of SQLite
- Set up reverse proxy (e.g., Nginx)

## 📦 Dependencies

Main dependencies:
- **Flask 3.1.0** - Web framework
- **SQLAlchemy 2.0.36** - Database ORM
- **openai** - OpenAI GPT API
- **anthropic** - Anthropic Claude API
- **google-generativeai** - Google Gemini API
- **python-docx** - Word document generation
- **reportlab** - PDF generation
- **Werkzeug** - Security utilities

See `requirements.txt` for complete list.

## 📝 License

This project is open source and available under the MIT License.

## 🙏 Acknowledgments

Built with:
- [Flask](https://flask.palletsprojects.com/) - Web framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - Database ORM
- [OpenAI API](https://platform.openai.com/) - GPT models
- [Anthropic API](https://www.anthropic.com/) - Claude models
- [Google GenAI](https://ai.google.dev/) - Gemini models
- [python-docx](https://python-docx.readthedocs.io/) - Document generation
- [ReportLab](https://www.reportlab.com/) - PDF generation

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 👨‍💻 Author

**Gregory Kakhiani**

Passionate about AI, multi-agent systems, and building tools that push the boundaries of human-AI collaboration.

## 📧 Support

For issues, questions, or suggestions, please open an issue on GitHub.

---

**Built with ❤️ for exploring AI collaboration**
