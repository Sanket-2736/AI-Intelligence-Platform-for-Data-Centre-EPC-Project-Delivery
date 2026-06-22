"""
Cerebras Client module.
Manages LLM calls to Cerebras llama-3.3-70b model for structured analysis.
Handles prompt formatting, response parsing, and error handling with retries.
Production-quality with comprehensive logging and token tracking.
"""

import json
import logging
import time
from typing import Dict, Any, Optional, Generator
from cerebras.cloud.sdk import Cerebras
import config

logger = logging.getLogger(__name__)


class CerebrasClient:
    """
    Client for Cerebras llama-3.3-70b LLM.
    Provides structured and streaming inference with retry logic and token tracking.
    """
    
    def __init__(self):
        """Initialize Cerebras client."""
        try:
            self.client = Cerebras(api_key=config.CEREBRAS_API_KEY)
            self.model = "llama-3.3-70b"
            
            # Usage tracking
            self.total_calls = 0
            self.total_tokens = 0
            self.response_times = []
            
            logger.info(f"Cerebras client initialized with model: {self.model}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Cerebras client: {str(e)}")
            raise
    
    def call(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        timeout: Optional[int] = None
    ) -> str:
        """
        Call Cerebras LLM with retry logic and timeout handling.
        
        Args:
            system_prompt: System message defining role/task
            user_message: User query
            temperature: Creativity level (0.1 = deterministic, 1.0 = creative)
            max_tokens: Maximum response length
            timeout: Timeout in seconds (uses config default if None)
            
        Returns:
            Raw string response from LLM
            
        Raises:
            Exception: If all retries fail or timeout occurs
        """
        if timeout is None:
            timeout = config.CEREBRAS_TIMEOUT_SECONDS
        
        max_retries = 3
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                start_time = time.time()
                
                response = self.client.messages.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout
                )
                
                response_time_ms = (time.time() - start_time) * 1000
                
                # Extract response text
                response_text = response.choices[0].message.content
                
                # Track usage
                tokens_used = response.usage.total_tokens if hasattr(response, 'usage') else 0
                self.total_calls += 1
                self.total_tokens += tokens_used
                self.response_times.append(response_time_ms)
                
                logger.info(
                    f"Call #{self.total_calls}: {tokens_used} tokens, "
                    f"{response_time_ms:.0f}ms, temp={temperature}"
                )
                
                return response_text
                
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # Check for rate limit (429)
                if "429" in error_str or "rate" in error_str:
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = 2 ** retry_count  # Exponential backoff: 2s, 4s, 8s
                        logger.warning(
                            f"Rate limited. Retry {retry_count}/{max_retries} after {wait_time}s"
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error("Rate limited - all retries exhausted")
                        raise
                
                # Check for service unavailable (503)
                elif "503" in error_str or "unavailable" in error_str:
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = 5 * retry_count  # Linear backoff: 5s, 10s, 15s
                        logger.warning(
                            f"Service unavailable. Retry {retry_count}/{max_retries} after {wait_time}s"
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error("Service unavailable - all retries exhausted")
                        raise
                
                # Check for timeout
                elif "timeout" in error_str or "timed out" in error_str:
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = 3 * retry_count
                        logger.warning(
                            f"Request timeout. Retry {retry_count}/{max_retries} after {wait_time}s"
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error("Request timeout - all retries exhausted")
                        raise
                
                else:
                    # Non-retryable error
                    logger.error(f"Non-retryable error: {str(e)}")
                    raise
        
        # All retries exhausted
        error_msg = f"Failed after {max_retries} retries: {str(last_error)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    def call_structured(
        self,
        system_prompt: str,
        user_message: str,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Call Cerebras LLM and force JSON-structured output.
        
        Automatically forces JSON format and parses response.
        On parse failures, retries with error feedback to the model.
        
        Args:
            system_prompt: System message
            user_message: User query
            max_retries: Maximum retry attempts for JSON parsing
            
        Returns:
            Parsed JSON dict
            
        Returns on failure:
            {"error": "JSON parse failed", "raw": response_text}
        """
        try:
            # Append JSON instruction to system prompt
            json_system_prompt = (
                system_prompt + 
                "\n\nCRITICAL INSTRUCTIONS FOR JSON OUTPUT:\n"
                "1. Respond with ONLY valid JSON\n"
                "2. No markdown code fences (no ```json or ```)\n"
                "3. No explanatory text before or after JSON\n"
                "4. Start your response with { and end with }\n"
                "5. Ensure all fields are properly quoted\n"
                "6. Use null for missing/unknown values"
            )
            
            retry_count = 0
            last_response = None
            
            while retry_count < max_retries:
                try:
                    # Get response
                    response_text = self.call(
                        system_prompt=json_system_prompt,
                        user_message=user_message,
                        temperature=0.1,  # Low temp for structured output
                        max_tokens=4096
                    )
                    
                    last_response = response_text
                    
                    # Strip markdown code fences if present
                    cleaned = response_text.strip()
                    if cleaned.startswith("```json"):
                        cleaned = cleaned[7:]  # Remove ```json
                    if cleaned.startswith("```"):
                        cleaned = cleaned[3:]  # Remove ```
                    if cleaned.endswith("```"):
                        cleaned = cleaned[:-3]  # Remove trailing ```
                    cleaned = cleaned.strip()
                    
                    # Parse JSON
                    parsed = json.loads(cleaned)
                    
                    logger.info(f"Structured call returned valid JSON with {len(parsed)} top-level fields")
                    return parsed
                    
                except json.JSONDecodeError as e:
                    retry_count += 1
                    logger.warning(
                        f"JSON parse failed (attempt {retry_count}/{max_retries}): {str(e)}"
                    )
                    
                    if retry_count < max_retries:
                        # Retry with error feedback
                        error_feedback = (
                            f"Previous response was not valid JSON. Error: {str(e)}\n"
                            f"Invalid response was: {last_response[:200]}...\n"
                            f"Please retry with ONLY valid JSON, no markdown fences."
                        )
                        user_message = error_feedback + "\n\nOriginal query: " + user_message
                    else:
                        # All retries exhausted
                        logger.error(f"JSON parsing failed after {max_retries} retries")
                        return {
                            "error": "JSON parse failed",
                            "raw": last_response,
                            "parse_error": str(e)
                        }
                        
        except Exception as e:
            logger.error(f"Error in structured call: {str(e)}")
            return {"error": str(e)}
    
    def call_streaming(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.1,
        max_tokens: int = 4096
    ) -> Generator[str, None, None]:
        """
        Streaming call to Cerebras for real-time responses.
        
        Used for chat interfaces with typewriter effect.
        Yields text chunks as they arrive.
        
        Args:
            system_prompt: System message
            user_message: User query
            temperature: Creativity level
            max_tokens: Maximum response length
            
        Yields:
            Text chunks from the response
        """
        try:
            start_time = time.time()
            tokens_streamed = 0
            
            stream = self.client.messages.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            
            for event in stream:
                if hasattr(event, 'choices') and event.choices:
                    delta = event.choices[0].delta
                    if hasattr(delta, 'content') and delta.content:
                        tokens_streamed += 1
                        yield delta.content
            
            response_time_ms = (time.time() - start_time) * 1000
            
            # Track usage
            self.total_calls += 1
            self.total_tokens += tokens_streamed
            self.response_times.append(response_time_ms)
            
            logger.info(
                f"Streaming call #{self.total_calls}: ~{tokens_streamed} tokens, "
                f"{response_time_ms:.0f}ms"
            )
            
        except Exception as e:
            logger.error(f"Error in streaming call: {str(e)}")
            yield f"[ERROR: {str(e)}]"
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics.
        
        Returns:
            {
                'total_calls': int,
                'total_tokens': int,
                'avg_response_time_ms': float,
                'min_response_time_ms': float,
                'max_response_time_ms': float
            }
        """
        if not self.response_times:
            return {
                'total_calls': 0,
                'total_tokens': 0,
                'avg_response_time_ms': 0.0,
                'min_response_time_ms': 0.0,
                'max_response_time_ms': 0.0
            }
        
        return {
            'total_calls': self.total_calls,
            'total_tokens': self.total_tokens,
            'avg_response_time_ms': sum(self.response_times) / len(self.response_times),
            'min_response_time_ms': min(self.response_times),
            'max_response_time_ms': max(self.response_times)
        }


# Module-level singleton
_cerebras_client = None


def get_cerebras_client() -> CerebrasClient:
    """
    Get or create Cerebras client singleton.
    
    Returns:
        CerebrasClient instance
    """
    global _cerebras_client
    if _cerebras_client is None:
        _cerebras_client = CerebrasClient()
    return _cerebras_client
