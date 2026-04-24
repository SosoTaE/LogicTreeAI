"""
Multi-Agent Service for orchestrating conversations between multiple LLMs.

This service enables collaborative problem-solving where multiple AI models
discuss and build on each other's responses.
"""

import logging
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

logger = logging.getLogger(__name__)


class MultiAgentService:
    """
    Service for orchestrating multi-agent LLM conversations.

    Enables multiple LLM models to collaborate by having structured
    discussions where each model can see and respond to other models'
    contributions.
    """

    def __init__(self, llm_service):
        """
        Initialize the multi-agent service.

        Args:
            llm_service: LLMService instance for making LLM calls
        """
        self.llm_service = llm_service

    def create_conversation_prompt(
        self,
        initial_problem: str,
        conversation_history: List[Dict[str, Any]],
        current_model: str,
        role: Optional[str] = None
    ) -> str:
        """
        Create a prompt for sequential conversation where models talk to each other.

        Args:
            initial_problem: The original problem/question
            conversation_history: List of all previous turns in order
            current_model: The model being prompted
            role: Optional role assignment for the model

        Returns:
            Formatted prompt string
        """
        prompt_parts = []

        # Context: there may be a human in the loop too, not just peer AIs.
        prompt_parts.append(
            "You are having a conversation with other AI models AND a human "
            "user to collaboratively explore a problem."
        )
        prompt_parts.append(
            "This is a turn-based discussion. Respond to what previous "
            "participants (other models and the human) have said."
        )

        if role:
            prompt_parts.append(
                f"\nYour assigned role / persona (stay in this voice): {role}"
            )

        prompt_parts.append(f"\nOriginal Problem:\n{initial_problem}\n")

        # Add conversation history
        if conversation_history:
            prompt_parts.append("\n--- Conversation So Far ---")
            for turn in conversation_history:
                model_name = turn.get('model_name', 'Unknown')
                content = turn.get('content', '')
                if model_name == 'user':
                    # Human interjection — label clearly so the current
                    # model knows this is the actual user, not a peer AI.
                    prompt_parts.append(f"\nHuman (the user):\n{content}\n")
                else:
                    peer_role = turn.get('model_role') or turn.get('role')
                    role_text = f" ({peer_role})" if peer_role else ""
                    prompt_parts.append(f"\n{model_name}{role_text}:\n{content}\n")
            prompt_parts.append("--- End of Conversation ---\n")
            prompt_parts.append(f"\nNow it's your turn ({current_model}).")
            prompt_parts.append("Please respond to the conversation above:")
            prompt_parts.append("- If the human just spoke, address what they said directly")
            prompt_parts.append("- Engage with the other models' points — agree, disagree, build on them")
            prompt_parts.append("- Add your own perspective or insights")
            prompt_parts.append("- Stay in your assigned role/persona if one was given")
        else:
            prompt_parts.append("\nYou are the first to speak in this conversation.")
            prompt_parts.append("Please share your initial thoughts and analysis of the problem.")

        return "\n".join(prompt_parts)

    def run_sequential_conversation(
        self,
        initial_problem: str,
        participating_models: List[str],
        total_turns: int,
        user_keys: Dict[str, str],
        model_roles: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Run a sequential conversation where models take turns responding to each other.

        Args:
            initial_problem: The problem to discuss
            participating_models: List of model identifiers (rotates between them)
            total_turns: Total number of turns in the conversation
            user_keys: User's API keys
            model_roles: Optional role assignments

        Returns:
            Complete conversation results
        """
        logger.info(f"Starting sequential conversation: {len(participating_models)} models, {total_turns} turns")

        model_roles = model_roles or {}
        conversation_history = []
        all_turns = []
        errors = []

        for turn_num in range(1, total_turns + 1):
            # Rotate through models
            model_index = (turn_num - 1) % len(participating_models)
            current_model = participating_models[model_index]
            role = model_roles.get(current_model)

            logger.info(f"Turn {turn_num}/{total_turns}: {current_model}")

            try:
                # Create conversation prompt
                prompt = self.create_conversation_prompt(
                    initial_problem=initial_problem,
                    conversation_history=conversation_history,
                    current_model=current_model,
                    role=role
                )

                # Format as message list
                messages = [{"role": "user", "content": prompt}]

                # Call the LLM
                start_time = datetime.now()
                response_content = self.llm_service.call_llm(
                    messages=messages,
                    target_model=current_model,
                    user_keys=user_keys
                )
                duration = (datetime.now() - start_time).total_seconds()

                turn_data = {
                    "turn_number": turn_num,
                    "model_name": current_model,
                    "content": response_content,
                    "role": role,
                    "duration": duration,
                    "timestamp": datetime.now().isoformat()
                }

                all_turns.append(turn_data)
                conversation_history.append(turn_data)

                logger.info(f"Turn {turn_num} completed: {current_model} ({duration:.2f}s)")

            except Exception as e:
                logger.error(f"Error in turn {turn_num} with {current_model}: {str(e)}")
                error_data = {
                    "turn_number": turn_num,
                    "model_name": current_model,
                    "error": str(e)
                }
                errors.append(error_data)
                # Don't add to conversation_history if it failed

        return {
            "initial_problem": initial_problem,
            "participating_models": participating_models,
            "model_roles": model_roles,
            "total_turns": len(all_turns),
            "turns": all_turns,
            "errors": errors,
            "conversation_type": "sequential"
        }

    def create_discussion_prompt(
        self,
        initial_problem: str,
        discussion_history: List[Dict[str, Any]],
        current_model: str,
        round_number: int,
        role: Optional[str] = None
    ) -> str:
        """
        Create a prompt for a model that includes the discussion context.

        Args:
            initial_problem: The original problem/question
            discussion_history: List of previous turns
            current_model: The model being prompted
            round_number: Current round number
            role: Optional role assignment for the model

        Returns:
            Formatted prompt string
        """
        prompt_parts = []

        # Add context about the multi-agent discussion
        prompt_parts.append("You are participating in a multi-agent discussion with other AI models to collaboratively solve a problem.")

        if role:
            prompt_parts.append(f"\nYour assigned role: {role}")

        prompt_parts.append(f"\nOriginal Problem:\n{initial_problem}\n")

        # Add discussion history if exists
        if discussion_history:
            prompt_parts.append("\n--- Previous Discussion ---")
            for turn in discussion_history:
                model_name = turn.get('model_name', 'Unknown')
                content = turn.get('content', '')
                round_num = turn.get('round_number', 0)
                prompt_parts.append(f"\n[Round {round_num}] {model_name}:\n{content}\n")
            prompt_parts.append("--- End of Previous Discussion ---\n")

        # Add instructions for current round
        if round_number == 1:
            prompt_parts.append("\nThis is Round 1. Please provide your initial analysis and thoughts on the problem.")
        else:
            prompt_parts.append(f"\nThis is Round {round_number}. Please:")
            prompt_parts.append("1. Review the previous responses from other models")
            prompt_parts.append("2. Identify key insights or points of agreement/disagreement")
            prompt_parts.append("3. Build on or refine the discussion with your perspective")
            prompt_parts.append("4. Suggest next steps or areas that need more exploration")

        return "\n".join(prompt_parts)

    def run_discussion_round(
        self,
        initial_problem: str,
        participating_models: List[str],
        discussion_history: List[Dict[str, Any]],
        round_number: int,
        user_keys: Dict[str, str],
        model_roles: Optional[Dict[str, str]] = None,
        max_workers: int = 3
    ) -> Dict[str, Any]:
        """
        Run a single round of multi-agent discussion.

        Args:
            initial_problem: The problem being discussed
            participating_models: List of model identifiers
            discussion_history: History of previous rounds
            round_number: Current round number
            user_keys: User's API keys
            model_roles: Optional dict mapping model names to roles
            max_workers: Max parallel API calls

        Returns:
            Dict containing round results and errors
        """
        logger.info(f"Starting multi-agent discussion round {round_number} with {len(participating_models)} models")

        model_roles = model_roles or {}
        round_responses = []
        errors = []

        def call_model(model_name: str) -> Dict[str, Any]:
            """Call a single model and return its response."""
            try:
                # Create discussion prompt for this model
                role = model_roles.get(model_name)
                prompt = self.create_discussion_prompt(
                    initial_problem=initial_problem,
                    discussion_history=discussion_history,
                    current_model=model_name,
                    round_number=round_number,
                    role=role
                )

                # Format as message list
                messages = [{"role": "user", "content": prompt}]

                # Call the LLM
                start_time = datetime.now()
                response_content = self.llm_service.call_llm(
                    messages=messages,
                    target_model=model_name,
                    user_keys=user_keys
                )
                duration = (datetime.now() - start_time).total_seconds()

                logger.info(f"Model {model_name} responded in {duration:.2f}s")

                return {
                    "model_name": model_name,
                    "content": response_content,
                    "round_number": round_number,
                    "role": role,
                    "duration": duration,
                    "timestamp": datetime.now().isoformat()
                }

            except Exception as e:
                logger.error(f"Error calling model {model_name}: {str(e)}")
                return {
                    "model_name": model_name,
                    "error": str(e),
                    "round_number": round_number
                }

        # Call all models in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_model = {
                executor.submit(call_model, model): model
                for model in participating_models
            }

            for future in as_completed(future_to_model):
                result = future.result()

                if "error" in result:
                    errors.append(result)
                else:
                    round_responses.append(result)

        logger.info(f"Round {round_number} completed: {len(round_responses)} successful, {len(errors)} errors")

        return {
            "round_number": round_number,
            "responses": round_responses,
            "errors": errors,
            "timestamp": datetime.now().isoformat()
        }

    def run_full_discussion(
        self,
        initial_problem: str,
        participating_models: List[str],
        max_rounds: int,
        user_keys: Dict[str, str],
        model_roles: Optional[Dict[str, str]] = None,
        stop_condition: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run a complete multi-agent discussion over multiple rounds.

        Args:
            initial_problem: The problem to discuss
            participating_models: List of models to participate
            max_rounds: Maximum number of discussion rounds
            user_keys: User's API keys
            model_roles: Optional role assignments
            stop_condition: Optional early stopping condition (not implemented yet)

        Returns:
            Complete discussion results
        """
        logger.info(f"Starting multi-agent discussion: {len(participating_models)} models, {max_rounds} rounds")

        all_rounds = []
        discussion_history = []

        for round_num in range(1, max_rounds + 1):
            round_result = self.run_discussion_round(
                initial_problem=initial_problem,
                participating_models=participating_models,
                discussion_history=discussion_history,
                round_number=round_num,
                user_keys=user_keys,
                model_roles=model_roles
            )

            all_rounds.append(round_result)

            # Add successful responses to history for next round
            discussion_history.extend(round_result["responses"])

            # Check if all models failed
            if not round_result["responses"]:
                logger.warning(f"All models failed in round {round_num}, stopping discussion")
                break

        return {
            "initial_problem": initial_problem,
            "participating_models": participating_models,
            "model_roles": model_roles,
            "total_rounds": len(all_rounds),
            "rounds": all_rounds,
            "summary": self._generate_summary(all_rounds)
        }

    def _generate_summary(self, all_rounds: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a summary of the discussion.

        Args:
            all_rounds: List of all round results

        Returns:
            Summary statistics
        """
        total_responses = sum(len(r["responses"]) for r in all_rounds)
        total_errors = sum(len(r["errors"]) for r in all_rounds)

        return {
            "total_rounds": len(all_rounds),
            "total_responses": total_responses,
            "total_errors": total_errors,
            "models_participated": len(set(
                resp["model_name"]
                for round_data in all_rounds
                for resp in round_data["responses"]
            ))
        }

    def create_synthesis_prompt(
        self,
        initial_problem: str,
        discussion_history: List[Dict[str, Any]]
    ) -> str:
        """
        Create a prompt for synthesizing the multi-agent discussion.

        Args:
            initial_problem: The original problem
            discussion_history: All discussion turns

        Returns:
            Synthesis prompt
        """
        prompt_parts = [
            "Please synthesize the following multi-agent discussion into a coherent summary and conclusion.",
            f"\nOriginal Problem:\n{initial_problem}\n",
            "\n--- Multi-Agent Discussion ---"
        ]

        for turn in discussion_history:
            model_name = turn.get('model_name', 'Unknown')
            content = turn.get('content', '')
            round_num = turn.get('round_number', 0)
            prompt_parts.append(f"\n[Round {round_num}] {model_name}:\n{content}\n")

        prompt_parts.append("--- End of Discussion ---\n")
        prompt_parts.append("\nPlease provide:")
        prompt_parts.append("1. Key insights from the discussion")
        prompt_parts.append("2. Points of consensus among the models")
        prompt_parts.append("3. Areas of disagreement or different perspectives")
        prompt_parts.append("4. A synthesized recommendation or conclusion")

        return "\n".join(prompt_parts)

    def synthesize_discussion(
        self,
        initial_problem: str,
        discussion_history: List[Dict[str, Any]],
        synthesis_model: str,
        user_keys: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Use a model to synthesize the discussion into a conclusion.

        Args:
            initial_problem: The original problem
            discussion_history: All discussion turns
            synthesis_model: Model to use for synthesis
            user_keys: User's API keys

        Returns:
            Synthesis result
        """
        logger.info(f"Synthesizing discussion with {synthesis_model}")

        try:
            synthesis_prompt = self.create_synthesis_prompt(
                initial_problem=initial_problem,
                discussion_history=discussion_history
            )

            messages = [{"role": "user", "content": synthesis_prompt}]

            synthesis_content = self.llm_service.call_llm(
                messages=messages,
                target_model=synthesis_model,
                user_keys=user_keys
            )

            return {
                "synthesis_model": synthesis_model,
                "synthesis": synthesis_content,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error synthesizing discussion: {str(e)}")
            return {
                "synthesis_model": synthesis_model,
                "error": str(e)
            }
