"""
LLM Service Layer - Modular integration for OpenAI, Anthropic, and Google GenAI.
Keys are supplied by the caller (one dict per user) — no global caching.
"""
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

import openai
import anthropic
from google import genai

GEMINI_MODELS_URL = 'https://generativelanguage.googleapis.com/v1beta/models'

logger = logging.getLogger(__name__)


_OPENAI_NON_CHAT_PREFIXES = (
    'text-embedding-',
    'text-moderation-',
    'omni-moderation-',
    'whisper-',
    'tts-',
    'dall-e-',
    'gpt-image-',
    'babbage-',
    'davinci-',
    'ada-',
    'curie-',
    'computer-use-',
)

_OPENAI_NON_CHAT_SUBSTRINGS = (
    'transcribe',
    'realtime',
    'embedding',
    'audio',
)


class LLMService:
    """Stateless service class for multiple LLM providers."""

    def _is_openai_chat_model(self, model_id):
        """Heuristic filter that keeps chat/reasoning models and drops
        embeddings, TTS, image, moderation, and legacy base models. Keeps
        the dropdown usable; non-chat models fail at call-time anyway."""
        if not model_id:
            return False
        lower = model_id.lower()
        if any(lower.startswith(p) for p in _OPENAI_NON_CHAT_PREFIXES):
            return False
        if any(s in lower for s in _OPENAI_NON_CHAT_SUBSTRINGS):
            return False
        return True

    def _extract_openai_responses_text(self, response):
        """Pull the assistant text out of a responses.create() result,
        accommodating both the convenience accessor and the structured
        `output` list in case the SDK version doesn't expose it."""
        text = getattr(response, 'output_text', None)
        if text:
            return text
        chunks = []
        for item in getattr(response, 'output', []) or []:
            if getattr(item, 'type', None) != 'message':
                continue
            for part in getattr(item, 'content', []) or []:
                part_type = getattr(part, 'type', None)
                if part_type in ('output_text', 'text'):
                    chunk = getattr(part, 'text', None)
                    if chunk:
                        chunks.append(chunk)
        return '\n'.join(chunks)

    def _fetch_gemini_models_rest(self, api_key):
        """
        Call the Gemini Developer API's ListModels endpoint directly, with
        pagination, and keep only chat-capable models. This is the source
        of truth for the catalog and sidesteps SDK-version inconsistencies
        that were hiding newer models (Gemini 3, 2.5, …).
        """
        names = []
        page_token = None
        for _ in range(20):  # hard cap to avoid runaway pagination
            query = {'key': api_key, 'pageSize': 1000}
            if page_token:
                query['pageToken'] = page_token
            url = f'{GEMINI_MODELS_URL}?{urllib.parse.urlencode(query)}'
            req = urllib.request.Request(url, headers={'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode('utf-8'))
            for model in payload.get('models', []):
                name = model.get('name')
                if not name:
                    continue
                # Drop non-chat endpoints (embeddings, TTS, image gen).
                methods = model.get('supportedGenerationMethods') or []
                if methods and 'generateContent' not in methods:
                    continue
                names.append(name)
            page_token = payload.get('nextPageToken')
            if not page_token:
                break
        return names

    def _normalize_messages(self, messages):
        """
        Accept either Message ORM objects (with .role/.content attributes)
        or plain dicts (with 'role'/'content' keys) and emit a uniform list
        of dicts. Callers across the codebase pass both shapes, so every
        provider function is downstream of this normalization.
        """
        normalized = []
        for msg in messages:
            if isinstance(msg, dict):
                role = msg.get('role')
                content = msg.get('content')
            else:
                role = getattr(msg, 'role', None)
                content = getattr(msg, 'content', None)
            normalized.append({'role': role, 'content': content})
        return normalized

    def _convert_messages_to_format(self, messages, provider):
        formatted = []
        for msg in messages:
            if msg['role'] == 'system' and provider in ['gemini']:
                continue
            formatted.append({'role': msg['role'], 'content': msg['content']})
        return formatted

    def get_available_models(self, user_keys):
        """Fetch available models from configured providers for the given user."""
        models = {'openai': [], 'anthropic': [], 'gemini': [], 'local': []}

        # OpenAI models - fetch and keep only models that can plausibly
        # handle chat/discussion. The raw /v1/models listing also exposes
        # embeddings, Whisper, TTS, DALL-E, moderation, and legacy base
        # models — none of which work for the conversation flow.
        if user_keys.get('openai_key'):
            try:
                client = openai.OpenAI(api_key=user_keys.get('openai_key'))
                res = client.models.list()
                models['openai'] = sorted(
                    m.id for m in res.data
                    if self._is_openai_chat_model(m.id)
                )
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

        # Gemini models - fetch directly from the authoritative REST
        # endpoint. The SDK's models.list() has historically under-reported
        # the catalog (hiding Gemini 3 etc.) depending on version and
        # tuning-vs-base query flags, so we bypass it here.
        if user_keys.get('gemini_key'):
            try:
                available_models = self._fetch_gemini_models_rest(
                    user_keys.get('gemini_key')
                )
                if available_models:
                    models['gemini'] = sorted(set(available_models))
                    logger.info(
                        "Gemini models fetched successfully: %d models",
                        len(models['gemini']),
                    )
                else:
                    raise Exception("No Gemini models found")
            except Exception as e:
                logger.warning("Gemini models fetch failed: %s, using fallback", str(e))
                # Gemini 3 (and newer) chat-capable model IDs, per
                # https://ai.google.dev/gemini-api/docs/models. Older
                # Gemini 2.x and 1.5 entries have been removed at user
                # request; gemini-3-pro-preview was shut down 2026-03-09
                # in favor of gemini-3.1-pro-preview.
                models['gemini'] = [
                    'gemini-3.1-pro-preview',
                    'gemini-3-flash-preview',
                    'gemini-3.1-flash-lite-preview',
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
            try:
                response = client.chat.completions.create(
                    model=model, messages=formatted_messages,
                )
                return response.choices[0].message.content
            except openai.NotFoundError as e:
                # Some modern OpenAI models (reasoning "pro" variants, etc.)
                # refuse the chat.completions endpoint with 404 "This is
                # not a chat model...". Retry via the Responses API, which
                # is the unified endpoint for those models.
                err_str = str(e)
                if 'not a chat model' not in err_str.lower() and 'chat/completions' not in err_str.lower():
                    raise
                logger.info(
                    "OpenAI chat.completions rejected model=%s; retrying "
                    "via Responses API", model,
                )
                response = client.responses.create(
                    model=model, input=formatted_messages,
                )
                text = self._extract_openai_responses_text(response)
                if not text:
                    raise Exception(
                        "OpenAI Responses API returned no text output"
                    )
                return text
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
                if msg['role'] == 'system':
                    system_message = msg['content']
                else:
                    formatted_messages.append({'role': msg['role'], 'content': msg['content']})
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
                if msg['role'] == 'system':
                    formatted_messages.append({
                        'role': 'user',
                        'parts': [{'text': f"System instruction: {msg['content']}"}],
                    })
                else:
                    role = 'model' if msg['role'] == 'assistant' else 'user'
                    formatted_messages.append({'role': role, 'parts': [{'text': msg['content']}]})
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
        # Prefer the explicit model (e.g. "qwen3:14b" passed by the discuss
        # orchestrator); fall back to the user's configured default only when
        # the caller passed the generic "local" placeholder.
        if model and model.lower() != 'local':
            actual_model = model
        else:
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
        # Normalize once so every provider can use uniform dict access and
        # callers can pass either Message ORM objects or plain dicts.
        messages = self._normalize_messages(messages)

        lower = target_model.lower()
        if (
            'gpt' in lower
            or 'openai' in lower
            # OpenAI reasoning models (o1, o3, o4 families).
            or lower.startswith('o1')
            or lower.startswith('o3')
            or lower.startswith('o4')
        ):
            provider, fn = 'openai', self.call_openai
        elif 'claude' in lower or 'anthropic' in lower:
            provider, fn = 'anthropic', self.call_anthropic
        elif 'gemini' in lower or 'google' in lower:
            provider, fn = 'gemini', self.call_gemini
        elif (
            'local' in lower
            or 'qwen' in lower
            or 'llama' in lower
            or ':' in target_model  # Ollama tag format, e.g. "phi4:14b"
        ):
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
