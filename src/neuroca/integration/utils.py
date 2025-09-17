"""Utility helpers that back NeuroCognitive Architecture (NCA) integrations."""

from __future__ import annotations

import ast
import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional third-party dependencies
# ---------------------------------------------------------------------------
try:  # pragma: no cover - exercised through mocks
    import tiktoken  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - import guard
    tiktoken = None  # type: ignore[assignment]

try:  # pragma: no cover - exercised through mocks
    from transformers import AutoTokenizer as _TransformersAutoTokenizer  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - import guard
    _TransformersAutoTokenizer = None


class _AutoTokenizerProxy:
    """Lightweight proxy so tests can patch the tokenizer regardless of availability."""

    def __init__(self, backend: Any | None) -> None:
        self._backend = backend

    def from_pretrained(self, model_name: str):  # pragma: no cover - exercised via mocks
        if self._backend is None:
            raise ImportError(
                "transformers is required for token counting with HuggingFace tokenizers."
            )
        return self._backend.from_pretrained(model_name)


AutoTokenizer = _AutoTokenizerProxy(_TransformersAutoTokenizer)

try:  # pragma: no cover - exercised through mocks
    from sentence_transformers import SentenceTransformer as _SentenceTransformerBackend  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - import guard
    _SentenceTransformerBackend = None


class _SentenceTransformerProxy:
    """Callable shim that mirrors :class:`SentenceTransformer` for patching."""

    def __call__(self, model: str, *, device: str = "cpu"):
        if _SentenceTransformerBackend is None:
            raise ImportError(
                "sentence_transformers is required for local embeddings. Install with "
                "'pip install sentence-transformers'."
            )
        return _SentenceTransformerBackend(model, device=device)


SentenceTransformer = _SentenceTransformerProxy()


if tiktoken is not None:
    TOKENIZER_TYPE = "tiktoken"
elif _TransformersAutoTokenizer is not None:
    TOKENIZER_TYPE = "transformers"
else:
    TOKENIZER_TYPE = "simple"
    logger.warning(
        "Neither tiktoken nor transformers is available. Using simple word-based tokenization."
    )

# Cache stores both tokenizer instances and embedding models to avoid expensive reloads.
_tokenizers: dict[str, Any] = {}
_embedding_models: dict[str, Any] = {}


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Count the number of tokens in a text string.
    
    This function attempts to use the most appropriate tokenizer based on
    what's available in the environment and the model specified.
    
    Args:
        text: The text to count tokens for
        model: The model to use for tokenization (determines tokenization rules)
        
    Returns:
        Number of tokens in the text
    """
    if not text:
        return 0
        
    # Use TikToken for OpenAI models if available
    if TOKENIZER_TYPE == "tiktoken":
        # Convert model names to encoding names
        encoding_name = model
        if model.startswith("gpt-3.5"):
            encoding_name = "cl100k_base"  # ChatGPT models
        elif model.startswith("gpt-4"):
            encoding_name = "cl100k_base"  # GPT-4 models
        elif model.startswith("text-embedding"):
            encoding_name = "cl100k_base"  # Embedding models
        elif model == "text-davinci-003" or model.startswith("text-davinci-002"):
            encoding_name = "p50k_base"
        elif model.startswith("code-davinci"):
            encoding_name = "p50k_base"
        
        # Get or create tokenizer
        if encoding_name not in _tokenizers:
            try:
                _tokenizers[encoding_name] = tiktoken.get_encoding(encoding_name)
            except KeyError:
                # Fall back to cl100k_base for unknown models
                logger.warning(f"Unknown model {model}, falling back to cl100k_base encoding")
                _tokenizers[encoding_name] = tiktoken.get_encoding("cl100k_base")
                
        # Count tokens
        return len(_tokenizers[encoding_name].encode(text))
        
    # Use Transformers for other models if available
    elif TOKENIZER_TYPE == "transformers":
        # Map to HuggingFace model names
        hf_model = model
        if model.startswith("gpt-3.5") or model.startswith("gpt-4"):
            hf_model = "gpt2"  # Closest tokenizer for GPT models
        elif model.startswith("claude"):
            hf_model = "facebook/opt-30b"  # Similar to Claude's tokenizer
        elif model.startswith("llama"):
            hf_model = "meta-llama/Llama-2-7b-hf"
        elif model.startswith("mistral"):
            hf_model = "mistralai/Mistral-7B-v0.1"
            
        # Get or create tokenizer
        if hf_model not in _tokenizers:
            try:
                _tokenizers[hf_model] = AutoTokenizer.from_pretrained(hf_model)
            except Exception as e:
                logger.warning(f"Failed to load tokenizer for {hf_model}: {str(e)}")
                # Fall back to GPT-2 tokenizer
                _tokenizers[hf_model] = AutoTokenizer.from_pretrained("gpt2")
                
        # Count tokens
        return len(_tokenizers[hf_model].encode(text))

    # Simple fallback using word count with a multiplier
    else:
        # Most models use about 1.3 tokens per word on average for English text
        return int(len(text.split()) * 1.3)
        

def format_prompt(template: str, variables: dict[str, Any], preserve_unknown: bool = True) -> str:
    """
    Format a prompt template with variables.
    
    Args:
        template: The prompt template with {variable_name} placeholders
        variables: Dictionary of variable names and values
        preserve_unknown: Whether to preserve unknown variables as is
        
    Returns:
        The formatted prompt
    """
    if not template:
        return ""
        
    # Define a function to handle each match
    def replace_var(match):
        var_name = match.group(1)
        if var_name in variables:
            value = variables[var_name]
            # Convert non-string values to string
            if not isinstance(value, str):
                if isinstance(value, (dict, list)):
                    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                return str(value)
            return value
        elif preserve_unknown:
            return f"{{{var_name}}}"
        else:
            return ""
            
    # Replace {variable_name} with the corresponding value
    return re.sub(r"\{([^{}]+)\}", replace_var, template)
    
    
def parse_response(response: str, expected_format: str = "text") -> Any:
    """
    Parse a response from an LLM provider into the expected format.
    
    Args:
        response: The response string from the LLM
        expected_format: The expected format (text, json, list, etc.)
        
    Returns:
        The parsed response in the expected format
        
    Raises:
        ValueError: If the response cannot be parsed into the expected format
    """
    if expected_format == "text" or not response:
        return response
        
    if expected_format == "json":
        # Try to extract JSON from the response
        json_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
        match = re.search(json_pattern, response)
        json_str = match.group(1) if match else response
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Try to fix common JSON errors while preserving the cleaned payload for diagnostics
            cleaned = re.sub(r"'([^']*)':", r'"\1":', json_str)
            cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)

            try:
                return json.loads(cleaned)
            except json.JSONDecodeError:
                try:
                    return ast.literal_eval(cleaned)
                except (ValueError, SyntaxError) as exc:
                    logger.warning("Failed to parse JSON response", exc_info=False)
                    raise ValueError(f"Response is not valid JSON: {cleaned}") from exc
                
    elif expected_format == "list":
        # Try to extract a list from the response
        if response.startswith("[") and response.endswith("]"):
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                pass
                
        # Try to extract a list from each line
        items = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if line.startswith("- ") or line.startswith("* "):
                items.append(line[2:].strip())
            elif re.match(r"^\d+\.\s", line):
                items.append(re.sub(r"^\d+\.\s", "", line).strip())
                
        if items:
            return items
            
        # Fall back to splitting by commas
        return [item.strip() for item in response.split(",")]
        
    # For other formats, return the raw response
    return response
    
    
def sanitize_input(text: str, max_length: Optional[int] = None) -> str:
    """
    Sanitize input to remove sensitive or problematic content.
    
    Args:
        text: The input text to sanitize
        max_length: Optional maximum length for the text
        
    Returns:
        The sanitized text
    """
    if not text:
        return ""
        
    # Remove potential command injection patterns
    text = re.sub(r"[`\\|;<>&$]", "", text)
    
    # Truncate if needed
    if max_length and len(text) > max_length:
        text = text[:max_length]
        
    return text
    
    
async def create_embedding(
    text: str, 
    model: str = "sentence-transformers/all-mpnet-base-v2",
    device: str = "cpu"
) -> list[float]:
    """
    Create an embedding for text using a local model.
    
    Args:
        text: The text to embed
        model: The model to use for embedding
        device: The device to run the model on (cpu, cuda, etc.)
        
    Returns:
        The embedding vector as a list of floats
        
    Raises:
        ImportError: If the required dependencies are not installed
        RuntimeError: If embedding creation fails
    """
    cache_key = f"{model}:{device}"
    cached = _embedding_models.get(cache_key)
    if cached is None or cached.get("factory") is not SentenceTransformer:
        try:
            model_instance = SentenceTransformer(model, device=device)
        except ImportError as exc:
            logger.error("sentence_transformers is required for local embeddings")
            raise ImportError(
                "sentence_transformers is required for local embeddings. Install with "
                "'pip install sentence-transformers'."
            ) from exc
        except Exception as exc:
            logger.error(f"Failed to load embedding model {model}: {str(exc)}")
            raise RuntimeError(f"Failed to load embedding model: {str(exc)}") from exc
        else:
            cached = {"factory": SentenceTransformer, "model": model_instance}
            _embedding_models[cache_key] = cached

    model_instance = cached["model"]

    try:
        embedding = model_instance.encode(text)
    except Exception as exc:
        logger.error(f"Failed to create embedding: {str(exc)}")
        raise RuntimeError(f"Failed to create embedding: {str(exc)}") from exc

    if hasattr(embedding, "tolist"):
        embedding = embedding.tolist()
    elif not isinstance(embedding, list):
        embedding = list(embedding)

    return embedding
