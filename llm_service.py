"""
LLM Service Layer - Modular integration for OpenAI, Anthropic, and Google GenAI.
Keys are supplied by the caller (one dict per user) — no global caching.
"""
import logging
import time
import openai
import anthropic
from google import genai

logger = logging.getLogger(__name__)


class LLMService:
    """Stateless service class for multiple LLM providers."""

    def _convert_messages_to_format(self, messages, provider):
        formatted = []
        for msg in messages:
            if msg.role == 'system' and provider in ['gemini']:
                continue
            formatted.append({'role': msg.role, 'content': msg.content})
        return formatted

    def get_available_models(self, user_keys):
        """Fetch available models from configured providers for the given user."""
        models = {'openai': [], 'anthropic': [], 'gemini': [], 'local': []}

        # OpenAI models - fetch ALL available models
        if user_keys.get('openai_key'):
            try:
                client = openai.OpenAI(api_key=user_keys.get('openai_key'))
                res = client.models.list()
                # Get all models without filtering
                models['openai'] = sorted([m.id for m in res.data])
                logger.info("OpenAI models fetched successfully: %d models", len(models['openai']))
            except openai.AuthenticationError:
                logger.warning("OpenAI authentication failed, using fallback models")
                models['openai'] = [
                    'gpt-4.1', 'gpt-4.1-mini', 'gpt-4o', 'gpt-4o-mini',
                    'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo',
                    'o3', 'o3-mini', 'o3-pro', 'o4-mini',
                    'o1', 'o1-mini', 'o1-preview',
                ]
            except Exception as e:
                logger.warning("OpenAI models fetch failed: %s, using fallback", str(e))
                models['openai'] = [
                    'gpt-4.1', 'gpt-4.1-mini', 'gpt-4o', 'gpt-4o-mini',
                    'gpt-4-turbo', 'gpt-4', 'gpt-3.5-turbo',
                    'o3', 'o3-mini', 'o3-pro', 'o4-mini',
                    'o1', 'o1-mini', 'o1-preview',
                ]

        # Anthropic models - using Models API
        if user_keys.get('anthropic_key'):
            try:
                client = anthropic.Anthropic(api_key=user_keys.get('anthropic_key'))
                # Use the Models API endpoint
                res = client.models.list()
                models['anthropic'] = sorted([m.id for m in res.data])
                logger.info("Anthropic models fetched successfully: %d models", len(models['anthropic']))
            except anthropic.AuthenticationError:
                logger.warning("Anthropic authentication failed, using fallback models")
                models['anthropic'] = [
                    'claude-3-7-sonnet-20250219',
                    'claude-3-5-sonnet-20241022',
                    'claude-3-5-haiku-20241022',
                    'claude-3-opus-20240229',
                    'claude-3-sonnet-20240229',
                    'claude-3-haiku-20240307',
                ]
            except Exception as e:
                logger.warning("Anthropic models fetch failed: %s, using fallback", str(e))
                models['anthropic'] = [
                    'claude-3-7-sonnet-20250219',
                    'claude-3-5-sonnet-20241022',
                    'claude-3-5-haiku-20241022',
                    'claude-3-opus-20240229',
                    'claude-3-sonnet-20240229',
                    'claude-3-haiku-20240307',
                ]

        # Gemini models - fetch ALL available models
        if user_keys.get('gemini_key'):
            try:
                client = genai.Client(api_key=user_keys.get('gemini_key'))
                # List all models without filtering
                available_models = []
                for model in client.models.list():
                    if hasattr(model, 'name'):
                        available_models.append(model.name)

                if available_models:
                    models['gemini'] = sorted(available_models)
                    logger.info("Gemini models fetched successfully: %d models", len(models['gemini']))
                else:
                    # No models found, use fallback
                    raise Exception("No Gemini models found")
            except Exception as e:
                logger.warning("Gemini models fetch failed: %s, using fallback", str(e))
                models['gemini'] = [
                    'gemini-2.0-flash-exp',
                    'gemini-exp-1206',
                    'gemini-2.0-flash-thinking-exp-1219',
                    'gemini-1.5-pro',
                    'gemini-1.5-flash',
                    'gemini-1.5-flash-8b',
                ]

        # Local models
        if user_keys.get('local_endpoint_url'):
            try:
                client = openai.OpenAI(
                    base_url=user_keys.get('local_endpoint_url'),
                    api_key='local-placeholder',
                )
                res = client.models.list()
                models['local'] = sorted([m.id for m in res.data])
                logger.info("Local models fetched successfully: %d models", len(models['local']))
            except openai.APIConnectionError as e:
                logger.warning("Local endpoint unreachable: %s, using fallback", str(e))
                configured_model = user_keys.get('local_model_name')
                models['local'] = [configured_model] if configured_model else ['qwen2.5', 'llama3.1', 'llama3']
            except Exception as e:
                logger.warning("Local models fetch failed: %s, using fallback", str(e))
                configured_model = user_keys.get('local_model_name')
                models['local'] = [configured_model] if configured_model else ['qwen2.5', 'llama3.1', 'llama3']

        return models

    def call_openai(self, messages, model, user_keys):
        api_key = user_keys.get('openai_key')
        if not api_key:
            raise ValueError("OpenAI API key not configured")
        try:
            client = openai.OpenAI(api_key=api_key)
            formatted_messages = self._convert_messages_to_format(messages, 'openai')
            response = client.chat.completions.create(model=model, messages=formatted_messages)
            return response.choices[0].message.content
        except openai.AuthenticationError:
            raise ValueError("Invalid OpenAI API key")
        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")

    def call_anthropic(self, messages, model, user_keys):
        api_key = user_keys.get('anthropic_key')
        if not api_key:
            raise ValueError("Anthropic API key not configured")
        try:
            client = anthropic.Anthropic(api_key=api_key)
            system_message = None
            formatted_messages = []
            for msg in messages:
                if msg.role == 'system':
                    system_message = msg.content
                else:
                    formatted_messages.append({'role': msg.role, 'content': msg.content})
            kwargs = {'model': model, 'max_tokens': 4096, 'messages': formatted_messages}
            if system_message:
                kwargs['system'] = system_message
            response = client.messages.create(**kwargs)
            return response.content[0].text
        except anthropic.AuthenticationError:
            raise ValueError("Invalid Anthropic API key")
        except Exception as e:
            raise Exception(f"Anthropic API error: {str(e)}")

    def call_gemini(self, messages, model, user_keys):
        api_key = user_keys.get('gemini_key')
        if not api_key:
            raise ValueError("Gemini API key not configured")
        try:
            client = genai.Client(api_key=api_key)
            formatted_messages = []
            for msg in messages:
                if msg.role == 'system':
                    formatted_messages.append({
                        'role': 'user',
                        'parts': [{'text': f"System instruction: {msg.content}"}],
                    })
                else:
                    role = 'model' if msg.role == 'assistant' else 'user'
                    formatted_messages.append({'role': role, 'parts': [{'text': msg.content}]})
            response = client.models.generate_content(model=model, contents=formatted_messages)
            return response.text
        except Exception as e:
            error_str = str(e)
            if ("API key" in error_str
                    or "authentication" in error_str.lower()
                    or "INVALID_ARGUMENT" in error_str):
                raise ValueError("Invalid Gemini API key")
            raise Exception(f"Gemini API error: {error_str}")

    def call_local_model(self, messages, model, user_keys):
        endpoint_url = user_keys.get('local_endpoint_url')
        if not endpoint_url:
            raise ValueError("Local endpoint URL not configured")
        actual_model = user_keys.get('local_model_name') or 'qwen2.5'
        try:
            client = openai.OpenAI(base_url=endpoint_url, api_key='local-placeholder')
            formatted_messages = self._convert_messages_to_format(messages, 'local')
            response = client.chat.completions.create(
                model=actual_model, messages=formatted_messages,
            )
            return response.choices[0].message.content
        except openai.APIConnectionError:
            raise ValueError(f"Local AI service is offline or unreachable at {endpoint_url}")
        except Exception as e:
            raise Exception(f"Local AI API error: {str(e)}")

    def call_llm(self, messages, target_model, user_keys):
        """Route the request to the appropriate provider based on target_model."""
        lower = target_model.lower()
        if 'gpt' in lower or 'openai' in lower:
            provider, fn = 'openai', self.call_openai
        elif 'claude' in lower or 'anthropic' in lower:
            provider, fn = 'anthropic', self.call_anthropic
        elif 'gemini' in lower or 'google' in lower:
            provider, fn = 'gemini', self.call_gemini
        elif 'local' in lower or 'qwen' in lower or 'llama' in lower:
            provider, fn = 'local', self.call_local_model
        else:
            logger.warning("LLM call rejected: unknown model %s", target_model)
            raise ValueError(f"Unknown model: {target_model}")

        logger.info(
            "LLM call start: provider=%s model=%s messages=%d",
            provider, target_model, len(messages),
        )
        started = time.perf_counter()
        try:
            content = fn(messages, target_model, user_keys)
            duration = time.perf_counter() - started
            content_len = len(content) if content else 0
            logger.info(
                "LLM call ok: provider=%s model=%s duration=%.2fs chars=%d",
                provider, target_model, duration, content_len,
            )
            return content
        except ValueError as e:
            duration = time.perf_counter() - started
            logger.warning(
                "LLM call config error: provider=%s model=%s duration=%.2fs err=%s",
                provider, target_model, duration, e,
            )
            raise
        except Exception as e:
            duration = time.perf_counter() - started
            logger.error(
                "LLM call failed: provider=%s model=%s duration=%.2fs err=%s",
                provider, target_model, duration, e,
            )
            raise


llm_service = LLMService()
