"""
LLM Service Layer - Modular integration for OpenAI, Anthropic, and Google GenAI
"""
from models import Settings, get_session
import openai
import anthropic
from google import genai


class LLMService:
    """Service class for interacting with multiple LLM providers"""

    def __init__(self):
        self.api_keys = self._load_api_keys()

    def _load_api_keys(self):
        """Load API keys from the database Settings table"""
        session = get_session()
        try:
            keys = {}
            for key_name in ['openai_key', 'anthropic_key', 'gemini_key', 'local_endpoint_url', 'local_model_name']:
                setting = session.query(Settings).filter_by(key=key_name).first()
                keys[key_name] = setting.value if setting and setting.value else None
            return keys
        finally:
            session.close()

    def refresh_api_keys(self):
        """Refresh API keys from database (useful after settings update)"""
        self.api_keys = self._load_api_keys()

    def _convert_messages_to_format(self, messages, provider):
        """
        Convert message path to the format expected by each provider
        messages: list of Message objects from get_conversation_path()
        """
        formatted = []

        for msg in messages:
            # Skip system messages for some providers that handle them differently
            if msg.role == 'system' and provider in ['gemini']:
                continue

            formatted.append({
                'role': msg.role,
                'content': msg.content
            })

        return formatted

    def get_available_models(self):
        """Fetch available models from configured providers"""
        self.refresh_api_keys()
        models = {
            'openai': [],
            'anthropic': [],
            'gemini': [],
            'local': []
        }

        # OpenAI
        if self.api_keys.get('openai_key'):
            try:
                client = openai.OpenAI(api_key=self.api_keys.get('openai_key'))
                res = client.models.list()
                models['openai'] = sorted([m.id for m in res.data if 'gpt' in m.id or 'o1' in m.id or 'o3' in m.id])
            except Exception:
                models['openai'] = ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo']

        # Anthropic
        if self.api_keys.get('anthropic_key'):
            try:
                client = anthropic.Anthropic(api_key=self.api_keys.get('anthropic_key'))
                # Anthropic models endpoint is available in newer SDK versions
                if hasattr(client, 'models'):
                    res = client.models.list()
                    models['anthropic'] = [m.id for m in res.data]
                else:
                    models['anthropic'] = ['claude-3-7-sonnet-20250219', 'claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229']
            except Exception:
                models['anthropic'] = ['claude-3-7-sonnet-20250219', 'claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229']

        # Gemini
        if self.api_keys.get('gemini_key'):
            models['gemini'] = ['gemini-3.1-pro-preview', 'gemini-3-flash-preview', 'gemini-3.1-flash-lite-preview']

        # Local
        if self.api_keys.get('local_endpoint_url'):
            try:
                client = openai.OpenAI(base_url=self.api_keys.get('local_endpoint_url'), api_key="local-placeholder")
                res = client.models.list()
                models['local'] = [m.id for m in res.data]
            except Exception:
                # Fallback to configured model if server is down or doesn't support models endpoint
                configured_model = self.api_keys.get('local_model_name')
                models['local'] = [configured_model] if configured_model else ['qwen2.5', 'llama3']

        return models

    def call_openai(self, messages, model='gpt-4o'):
        """
        Call OpenAI API
        messages: list of Message objects
        """
        api_key = self.api_keys.get('openai_key')
        if not api_key:
            raise ValueError("OpenAI API key not configured")

        try:
            client = openai.OpenAI(api_key=api_key)
            formatted_messages = self._convert_messages_to_format(messages, 'openai')

            response = client.chat.completions.create(
                model=model,
                messages=formatted_messages
            )

            return response.choices[0].message.content

        except openai.AuthenticationError:
            raise ValueError("Invalid OpenAI API key")
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")

    def call_anthropic(self, messages, model='claude-3-5-sonnet-20241022'):
        """
        Call Anthropic API
        messages: list of Message objects
        """
        api_key = self.api_keys.get('anthropic_key')
        if not api_key:
            raise ValueError("Anthropic API key not configured")

        try:
            client = anthropic.Anthropic(api_key=api_key)

            # Anthropic requires system messages to be passed separately
            system_message = None
            formatted_messages = []

            for msg in messages:
                if msg.role == 'system':
                    system_message = msg.content
                else:
                    formatted_messages.append({
                        'role': msg.role,
                        'content': msg.content
                    })

            # Make the API call
            kwargs = {
                'model': model,
                'max_tokens': 4096,
                'messages': formatted_messages
            }

            if system_message:
                kwargs['system'] = system_message

            response = client.messages.create(**kwargs)

            return response.content[0].text

        except anthropic.AuthenticationError:
            raise ValueError("Invalid Anthropic API key")
        except Exception as e:
            raise Exception(f"Anthropic API error: {str(e)}")

    def call_gemini(self, messages, model='gemini-3.1-pro-preview'):
        """
        Call Google Gemini API using the new google.genai package
        messages: list of Message objects
        """
        api_key = self.api_keys.get('gemini_key')
        if not api_key:
            raise ValueError("Gemini API key not configured")

        try:
            client = genai.Client(api_key=api_key)

            # Convert messages to Gemini format
            # Gemini uses 'user' and 'model' roles
            formatted_messages = []
            for msg in messages:
                if msg.role == 'system':
                    # Add system message as user message with instruction
                    formatted_messages.append({
                        'role': 'user',
                        'parts': [{'text': f"System instruction: {msg.content}"}]
                    })
                else:
                    role = 'model' if msg.role == 'assistant' else 'user'
                    formatted_messages.append({
                        'role': role,
                        'parts': [{'text': msg.content}]
                    })

            # Generate content using the new API
            response = client.models.generate_content(
                model=model,
                contents=formatted_messages
            )

            return response.text

        except Exception as e:
            error_str = str(e)
            if "API key" in error_str or "authentication" in error_str.lower() or "INVALID_ARGUMENT" in error_str:
                raise ValueError("Invalid Gemini API key")
            raise Exception(f"Gemini API error: {error_str}")

    def call_local_model(self, messages, model='qwen2.5'):
        """
        Call a local AI service (e.g., Ollama, vLLM) via OpenAI-compatible endpoint.
        messages: list of Message objects
        """
        endpoint_url = self.api_keys.get('local_endpoint_url')
        if not endpoint_url:
            raise ValueError("Local endpoint URL not configured")

        actual_model = self.api_keys.get('local_model_name') or 'qwen2.5'

        try:
            # Many local tools like Ollama or vLLM support OpenAI client structure if you override base_url
            # We use an empty string for api_key to satisfy the OpenAI client requirement
            client = openai.OpenAI(base_url=endpoint_url, api_key="local-placeholder")
            formatted_messages = self._convert_messages_to_format(messages, 'local')

            response = client.chat.completions.create(
                model=actual_model,
                messages=formatted_messages
            )

            return response.choices[0].message.content

        except openai.APIConnectionError:
            raise ValueError(f"Local AI service is offline or unreachable at {endpoint_url}")
        except Exception as e:
            raise Exception(f"Local AI API error: {str(e)}")

    def call_llm(self, messages, target_model):
        """
        Route the request to the appropriate LLM based on target_model
        messages: list of Message objects from get_conversation_path()
        target_model: string like 'gpt-4o', 'claude-3-5-sonnet-20241022', 'gemini-1.5-pro'
        """
        # Refresh API keys before each call to ensure they're up to date
        self.refresh_api_keys()

        # Route to appropriate provider
        if 'gpt' in target_model.lower() or 'openai' in target_model.lower():
            return self.call_openai(messages, target_model)
        elif 'claude' in target_model.lower() or 'anthropic' in target_model.lower():
            return self.call_anthropic(messages, target_model)
        elif 'gemini' in target_model.lower() or 'google' in target_model.lower():
            return self.call_gemini(messages, target_model)
        elif 'local' in target_model.lower() or 'qwen' in target_model.lower() or 'llama' in target_model.lower():
            return self.call_local_model(messages, target_model)
        else:
            raise ValueError(f"Unknown model: {target_model}")


# Singleton instance
llm_service = LLMService()
