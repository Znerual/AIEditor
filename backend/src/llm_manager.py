import requests
import time
import logging
import threading
from typing import Generator, List, Dict, Optional, Any, Tuple, Union, TypedDict, Type, get_type_hints
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from abc import ABC, abstractmethod
import google.generativeai as genai
import json
import anthropic

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@dataclass
class UsageMetrics:
    """Stores usage metrics for a user or globally."""
    input_tokens: int = 0
    output_tokens: int = 0
    requests: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    minute_metrics: Dict[str, List[int]] = field(default_factory=lambda: {
        'input_tokens': [],
        'output_tokens': []
    })  # Track tokens per minute
    daily_metrics: Dict[str, int] = field(default_factory=lambda: {
        'input_tokens': 0,
        'output_tokens': 0
    })  # Track tokens per day

    def update(self, input_tokens: int, output_tokens: int):
        """Updates usage metrics."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.requests += 1
        self.last_updated = datetime.now(timezone.utc)

        # Update per-minute metrics
        current_minute = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
        self.minute_metrics['input_tokens'].append(input_tokens)
        self.minute_metrics['output_tokens'].append(output_tokens)

        # Update daily metrics
        self.daily_metrics['input_tokens'] += input_tokens
        self.daily_metrics['output_tokens'] += output_tokens

    def get_current_minute_usage(self):
        """Returns the usage for the current minute."""
        current_minute = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
        input_tokens = sum(self.minute_metrics['input_tokens'][-1:])  # Get last minute's data
        output_tokens = sum(self.minute_metrics['output_tokens'][-1:])
        return input_tokens, output_tokens

    def get_daily_usage(self):
        """Returns the total usage for the current day."""
        return self.daily_metrics['input_tokens'], self.daily_metrics['output_tokens']

class DebugResponse:
    def __init__(self, text):
        self.text = text

class DebugModel:
    def __init__(self, model_name):
        self.model_name = model_name

    def generate_content(self, prompt, **kwargs):
        logging.debug(f"DebugModel ({self.model_name}) generating content for prompt: {prompt[:50]}...")
        time.sleep(1)  # Simulate processing time
        return DebugResponse(f"Debug answer for prompt: {prompt[:50]}...")

class LLM(ABC):
    """Abstract base class for language model instances."""
    fast_model_name: str = "unknown"
    slow_model_name: str = "unknown"
    embedding_model_name: str = "unknown"

    def __init__(self, model_mode: str, temperature: float = 0.7, response_format: Optional[Dict[str, Any]] = None, **kwargs):
        self.model_mode = model_mode
        self.temperature = temperature
        self.response_format = response_format
        self._model_instance = None  # Initialize in __post_init__
        self._post_init__(**kwargs)

    @property
    def name(self) -> str:
        """Returns the name of the LLM."""
        return self.get_model_by_mode(self.model_mode)

    @abstractmethod
    def _post_init__(self, **kwargs):
        """Initialize the underlying model instance."""
        pass

    @abstractmethod
    def generate_content(self, prompt: str, user_id: Optional[int] = None, **kwargs) -> Any:
        """Generates content using the configured model."""
        pass

    def get_model_by_mode(self, mode: str) -> str:
        """Returns the model name based on the specified mode."""
        if mode == "fast": return self.fast_model_name
        if mode == "slow": return self.slow_model_name
        if mode == "embedding": return self.embedding_model_name
        raise ValueError(f"Invalid mode: {mode}")    
    
    def _schema_to_JSON(self, schema: Type[TypedDict]) -> str:
        """Creates a system prompt that instructs the model to output in the specified format."""
        schema_dict = {
            field: schema.__annotations__[field].__name__ 
            for field in schema.__annotations__
        }
        return json.dumps(schema_dict)
       

    def _get_python_type(self, type_annotation: Any) -> type:
        """Converts type hints to Python types for validation."""
        type_mapping = {
            'str': str,
            'int': int,
            'float': float,
            'bool': bool,
            'list': list,
            'dict': dict
        }
        type_name = getattr(type_annotation, '__name__', str(type_annotation))
        return type_mapping.get(type_name, object)

class DebugLLM(LLM):
    """Implementation of LLM for debug models."""

    def _post_init__(self):
        """Initializes the debug model."""
        self._model_instance = DebugModel(self.model_mode)
    
    def generate_content(self, prompt: str, user_id: Optional[int] = None, **kwargs) -> Any:
        """Generates content using the configured model."""
        
        if self._model_instance:
            # Placeholder for actual token counting
            start_time = time.time()
            response = self._model_instance.generate_content(prompt, **kwargs)
            end_time = time.time()

            # Estimate token usage (replace with actual token counting if available)
            input_tokens = len(prompt.split())  # Rough estimate
            output_tokens = len(response.text.split())
            
            # Update usage metrics
            LLMManager.get_instance()._update_usage(user_id, self.name, input_tokens, output_tokens)

            # Log generation details
            duration = end_time - start_time
            logging.info(f"Content generated in {duration:.2f} seconds (model: {self.name}, user: {user_id if user_id is not None else 'N/A'})")
            logging.debug(f"Prompt: {prompt[:100]}..., Response: {response.text[:100]}...")

            return response
        else:
            raise ValueError("Model instance not initialized.")


class AnthropicLLM(LLM):
    """Implementation of LLM for Anthropic's Claude models."""
    fast_model_name = "claude-3-5-haiku-latest"
    slow_model_name = "claude-3-5-sonnet-latest"
    embedding_model_name = "unknown"

    def _post_init__(self, api_key):
        """Initializes the Anthropic client."""
        
        self._model_instance = anthropic.Anthropic(api_key=api_key)
        self._response_schema: Optional[Type[TypedDict]] = None
        if self.response_format and 'schema' in self.response_format:
            schema = self.response_format['schema']
            if not isinstance(schema, type) or not issubclass(schema, TypedDict):
                raise ValueError("Schema must be a TypedDict class")
            self._response_schema = schema

    
    
    def _validate_response(self, response_text: str, schema: Type[TypedDict]) -> Dict[str, Any]:
        """Validates that the response matches the specified schema."""
        try:
            # Extract JSON from the response if it's wrapped in markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            data = json.loads(response_text)
            
            # Validate types against schema
            for field, field_type in schema.__annotations__.items():
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")
                if not isinstance(data[field], self._get_python_type(field_type)):
                    raise ValueError(f"Invalid type for field {field}: expected {field_type}, got {type(data[field])}")
            
            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response: {e}")
        except Exception as e:
            raise ValueError(f"Response validation failed: {e}")

    

    def generate_content(self, prompt: str, user_id: Optional[int] = None, **kwargs) -> Any:
        """Generates content using the Anthropic model and tracks usage."""
        if not self._model_instance:
            raise ValueError("Model instance not initialized.")

        start_time = time.time()
        
        # Prepare the message
        messages = [{"role": "user", "content": prompt}]
        
        # Add system message for structured output if schema is specified
        if self._response_schema:
            system_prompt = self._format_system_prompt(self._response_schema)
            messages.insert(0, {"role": "system", "content": system_prompt})

        # Create message
        message = self._model_instance.messages.create(
            model=self.name,
            max_tokens=kwargs.get('max_tokens', 1024),
            temperature=self.temperature,
            messages=messages
        )

        duration = time.time() - start_time

        # Get usage metrics
        input_tokens = message.usage.input_tokens
        output_tokens = message.usage.output_tokens

        # Update usage metrics
        LLMManager.get_instance()._update_usage(user_id, self.name, input_tokens, output_tokens)

        # Log generation details
        logging.info(f"Content generated in {duration:.2f} seconds (model: {self.name}, user: {user_id if user_id is not None else 'N/A'})")
        logging.debug(f"Prompt: {prompt[:100]}..., Response: {message.content[:100]}...")

        # Handle structured output if schema is specified
        if self._response_schema:
            try:
                validated_response = self._validate_response(message.content, self._response_schema)
                message.structured_output = validated_response
            except ValueError as e:
                logging.error(f"Response validation failed: {e}")
                raise

        return message
    
    def _format_system_prompt(self, schema: Type[TypedDict]) -> str:
        """Creates a system prompt that instructs the model to output in the specified format."""
        schema_json = self._schema_to_JSON(schema)
        return (
            f"Please provide your response in the following JSON format:\n"
            f"{schema_json}\n"
            "Ensure all fields are present and of the correct type."
        )
    

class GeminiLLM(LLM):
    """Implementation of LLM for Google's Gemini models."""
    fast_model_name: str = "gemini-1.5-flash-latest"
    expensive_model_name: str = "gemini-1.5-pro-latest"
    embedding_model_name: str = "embedding-001"

    def _post_init__(self, api_key):
        """Initializes the Gemini model."""
        genai.configure(api_key=api_key)
        self._model_instance = genai.GenerativeModel(
            self.name,
            generation_config=genai.types.GenerationConfig(
                candidate_count=1,
                temperature=self.temperature,
                response_mime_type=self.response_format.get("mime_type", None) if self.response_format else None,
                response_scheme=self.response_format.get("scheme", None) if self.response_format else None,
            )
        )

    def generate_content(self, prompt: str, user_id: Optional[int] = None, **kwargs) -> Any:
        """Generates content using the Gemini model and tracks usage."""
        if self._model_instance:
            start_time = time.time()
            
            response = self._model_instance.generate_content(prompt, **kwargs)
            
            end_time = time.time()

            # Accurate token counting for Gemini models
            usage_metadata = response.usage_metadata
            input_tokens = usage_metadata['prompt_token_count']
            output_tokens = usage_metadata['candidates_token_count']
            
            # Update usage metrics
            LLMManager.get_instance()._update_usage(user_id, self.name, input_tokens, output_tokens)

            # Log generation details
            duration = end_time - start_time
            logging.info(f"Content generated in {duration:.2f} seconds (model: {self.name}, user: {user_id if user_id is not None else 'N/A'})")
            logging.debug(f"Prompt: {prompt[:100]}..., Response: {response.text[:100]}... Input Tokens: {input_tokens}, Output Tokens: {output_tokens}")
          

            return response
        else:
            raise ValueError("Model instance not initialized.")
    

class OllamaResponse:
    def __init__(self, response_data: Dict[str, Any]):
        self._response_data = response_data

    @property
    def text(self) -> str:
        return self._response_data.get("response", "")

    @property
    def usage_metadata(self) -> Dict[str, int]:
        return {
            "prompt_token_count": self._response_data.get("prompt_eval_count", 0),
            "candidates_token_count": self._response_data.get("eval_count", 0),
        }
        
class OllamaLLM(LLM):
    """Implementation of LLM for Ollama models."""
    fast_model_name = "vanilj/Phi-4"
    slow_model_name = "llama3.3"
    embedding_model_name = "nomic-embed-text"


    def _post_init__(self, base_url, model_file = None, model_file_name = None): 
        """Initializes the Ollama model. Pulls the model if it doesn't exist and optionally pushes a model if a model file is provided."""
        self.base_url = base_url

        if model_file and model_file_name:
            logging.info(f"Pushing model from file: {model_file}")
            for status in self.push_model(model_file_name, stream=True):
                if isinstance(status, dict):
                    logging.info(f"Pushing {self.name}: {status.get('status', '')}")
            logging.info(f"Model {model_file_name} pushed successfully from {model_file}.")
            return
        
        if not self._model_exists(self.name):
            logging.info(f"Model {self.name} not found locally. Pulling from Ollama library...")
            for status in self.pull_model(self.name, stream=True):
                if isinstance(status, dict):
                    logging.info(f"Pulling {self.name}: {status.get('status', '')}")
            logging.info(f"Model {self.name} pulled successfully.")

        if self.response_format:
            response_scheme=self.response_format.get("scheme", None) if self.response_format else None,
            if response_scheme:
                self.response_format_json = self._schema_to_JSON(response_scheme)
    def _model_exists(self, model_name: str) -> bool:
        """Checks if the model exists locally."""
        try:
            models = self.list_models()
            return any(model["name"] == model_name for model in models)
        except Exception as e:
            logging.error(f"Error checking if model {model_name} exists: {e}")
            return False
    
        
    # def copy_model(self, source_model: str, destination_model: str) -> Dict[str, Any]:
    #     """Copies a model. Creates a model with another name from an existing model."""
    #     url = f"{self.base_url}/api/copy"
    #     payload = {"source": source_model, "destination": destination_model}
    #     try:
    #         response = requests.post(url, json=payload)
    #         response.raise_for_status()
    #         return {"status": "success"}
    #     except requests.exceptions.RequestException as e:
    #         logging.error(f"Error copying model from {source_model} to {destination_model}: {e}")
    #         raise

    # def delete_model(self, model_name: str) -> Dict[str, Any]:
    #     """Deletes a model and its data."""
    #     url = f"{self.base_url}/api/delete"
    #     payload = {"model": model_name}
    #     try:
    #         response = requests.delete(url, json=payload)
    #         response.raise_for_status()
    #         return {"status": "success"}
    #     except requests.exceptions.RequestException as e:
    #         logging.error(f"Error deleting model {model_name}: {e}")
    #         raise

    def pull_model(self, model_name: str, insecure: bool = False, stream: bool = False) -> Union[Generator[Dict[str, Any], None, None], Dict[str, Any]]:
        """Downloads a model from the ollama library.

        Args:
            model_name: Name of the model to pull.
            insecure: Allow insecure connections to the library.
            stream: If False, the response will be returned as a single response object, rather than a stream of objects.

        Returns:
            If stream is True, returns a generator that yields JSON objects.
            If stream is False, returns a single JSON object.
        """
        url = f"{self.base_url}/api/pull"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": model_name,
            "insecure": insecure,
            "stream": stream,
        }
        try:
            response = requests.post(url, headers=headers, json=payload, stream=stream)
            response.raise_for_status()

            if stream:
                for line in response.iter_lines():
                    if line:
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            logging.error(f"Failed to decode JSON: {line}")
                            yield {"error": "Failed to decode JSON", "line": line.decode()}
            else:
                return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error pulling model {model_name}: {e}")
            raise
    
    def push_model(self, model_name: str, insecure: bool = False, stream: bool = False) -> Union[Generator[Dict[str, Any], None, None], Dict[str, Any]]:
        """Uploads a model to a model library.

        Args:
            model_name: Name of the model to push in the form of <namespace>/<model>:<tag>.
            insecure: Allow insecure connections to the library.
            stream: If False, the response will be returned as a single response object, rather than a stream of objects.

        Returns:
            If stream is True, returns a generator that yields JSON objects.
            If stream is False, returns a single JSON object.
        """
        url = f"{self.base_url}/api/push"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": model_name,
            "insecure": insecure,
            "stream": stream,
        }
        try:
            response = requests.post(url, headers=headers, json=payload, stream=stream)
            response.raise_for_status()

            if stream:
                for line in response.iter_lines():
                    if line:
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            logging.error(f"Failed to decode JSON: {line}")
                            yield {"error": "Failed to decode JSON", "line": line.decode()}
            else:
                return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error pushing model {model_name}: {e}")
            raise
    
    def generate_chat_completion(self, messages: List[Dict[str, Any]], stream: bool = False, **kwargs) -> Union[Generator[Dict[str, Any], None, None], Dict[str, Any]]:
        """Generates the next message in a chat with a provided model.

        Args:
            messages: The messages of the chat.
            stream: If False, the response will be returned as a single response object, rather than a stream of objects.

        Returns:
            If stream is True, returns a generator that yields JSON objects.
            If stream is False, returns a single JSON object.
        """
        url = f"{self.base_url}/api/chat"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": self.name,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": self.temperature,
                **(kwargs.get("options", {}))
            }
        }

        # Add response format if provided
        if self.response_format:
            payload["format"] = self.response_format_json

        try:
            response = requests.post(url, headers=headers, json=payload, stream=stream)
            response.raise_for_status()

            if stream:
                for line in response.iter_lines():
                    if line:
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            logging.error(f"Failed to decode JSON: {line}")
                            yield {"error": "Failed to decode JSON", "line": line.decode()}
            else:
                return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error generating chat completion: {e}")
            raise
    
    def generate_content(self, prompt: str, user_id: Optional[int] = None, stream: bool = False, **kwargs) -> Union[Generator[Dict[str, Any], None, None], Any]:
        """Generates content using the Ollama API.

        Args:
            prompt: The prompt for content generation.
            user_id: Optional user ID for tracking usage.
            stream: If True, returns a generator that yields JSON objects as they become available.
                    If False, returns a single response object after all content is generated.

        Returns:
            If stream is True, returns a generator that yields JSON objects.
            If stream is False, returns an OllamaResponse object.
        """
        url = f"{self.base_url}/api/generate"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": self.name,
            "prompt": prompt,
            "stream": stream,
            "options": {
                "temperature": self.temperature,
                **(kwargs.get("options", {}))
            }
        }

        # Add response format if provided
        if self.response_format:
            payload["format"] = self.response_format_json

        start_time = time.time()
        try:
            response = requests.post(url, headers=headers, json=payload, stream=stream)
            response.raise_for_status()

            if stream:
                for chunk in response.iter_lines():
                    if chunk:
                        try:
                            decoded_chunk = json.loads(chunk.decode("utf-8"))
                            yield decoded_chunk
                        except json.JSONDecodeError:
                            logging.error(f"Failed to decode JSON: {chunk}")
                            yield {"error": "Failed to decode JSON", "line": chunk.decode()}
            else:
                response_data = response.json()
                ollama_response = OllamaResponse(response_data)

                # Update usage metrics
                LLMManager.get_instance()._update_usage(
                    user_id,
                    self.name,
                    ollama_response.usage_metadata["prompt_eval_count"],
                    ollama_response.usage_metadata["candidates_token_count"],
                )

                # Log generation details
                duration = time.time() - start_time
                logging.info(
                    f"Content generated in {duration:.2f} seconds (model: {self.name}, user: {user_id if user_id is not None else 'N/A'})"
                )
                logging.debug(
                    f"Prompt: {prompt[:100]}..., Response: {ollama_response.text[:100]}... Input Tokens: {ollama_response.usage_metadata['prompt_eval_count']}, Output Tokens: {ollama_response.usage_metadata['candidates_token_count']}"
                )

                return ollama_response

        except requests.exceptions.RequestException as e:
            logging.error(f"Error generating content with Ollama: {e}")
            raise

    def create_model(self, model_name: str, modelfile: str, stream: bool = False, **kwargs) -> Union[Generator[Dict[str, Any], None, None], Dict[str, Any]]:
        """Creates a model from a Modelfile.

        Args:
            model_name: Name of the model to create.
            modelfile: Contents of the Modelfile.
            stream: If False, the response will be returned as a single response object, rather than a stream of objects.

        Returns:
            If stream is True, returns a generator that yields JSON objects.
            If stream is False, returns a single JSON object.
        """
        url = f"{self.base_url}/api/create"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": model_name,
            "modelfile": modelfile,
            "stream": stream,
            **(kwargs)
        }
        try:
            response = requests.post(url, headers=headers, json=payload, stream=stream)
            response.raise_for_status()

            if stream:
                for line in response.iter_lines():
                    if line:
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            logging.error(f"Failed to decode JSON: {line}")
                            yield {"error": "Failed to decode JSON", "line": line.decode()}
            else:
                return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error creating model {model_name}: {e}")
            raise
    
    def generate_embeddings(self, input_text: Union[str, List[str]], truncate: bool = True, **kwargs) -> Dict[str, Any]:
        """Generates embeddings from a model.

        Args:
            input_text: Text or list of text to generate embeddings for.
            truncate: Truncates the end of each input to fit within context length.

        Returns:
            A dictionary containing the generated embeddings.
        """
        url = f"{self.base_url}/api/embed"
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": self.name,
            "input": input_text,
            "truncate": truncate,
            "options": {
                **(kwargs.get("options", {}))
            }
        }
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error generating embeddings: {e}")
            raise

    def list_running_models(self) -> List[Dict[str, Any]]:
        """Lists models that are currently loaded into memory."""
        url = f"{self.base_url}/api/ps"
        try:
            response = requests.get(url)
            response.raise_for_status()
            models_data = response.json().get("models", [])
            return models_data
        except requests.exceptions.RequestException as e:
            logging.error(f"Error listing running models: {e}")
            raise

    def check_blob_exists(self, digest: str) -> bool:
        """Checks if a blob exists on the server.

        Args:
            digest: The SHA256 digest of the blob.

        Returns:
            True if the blob exists, False otherwise.
        """
        url = f"{self.base_url}/api/blobs/{digest}"
        try:
            response = requests.head(url)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            logging.error(f"Error checking blob existence: {e}")
            raise

    def create_blob(self, digest: str, file_path: str) -> Dict[str, Any]:
        """Creates a blob from a file on the server.

        Args:
            digest: The expected SHA256 digest of the file.
            file_path: Path to the file.

        Returns:
            Server file path if successful.
        """
        url = f"{self.base_url}/api/blobs/{digest}"
        try:
            with open(file_path, 'rb') as file:
                response = requests.post(url, data=file)
                response.raise_for_status()
                return {"status": "success"}
        except requests.exceptions.RequestException as e:
            logging.error(f"Error creating blob: {e}")
            raise
        except FileNotFoundError:
            logging.error(f"File not found: {file_path}")
            raise
    
    
class LLMManager:
    """
    Manages multiple LLM instances, tracks usage, and acts as a singleton.
    """

    _instance: Optional['LLMManager'] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self, debug: bool = False, **kwargs):
        self.debug = debug
        if kwargs.get("gemini_api_key", False):
            self.gemini_api_key = kwargs["gemini_api_key"]
        
        if kwargs.get("anthropic_api_key", False):
            self.anthropic_api_key = kwargs["anthropic_api_key"]

        if kwargs.get("ollama_base_url", False):
            self.ollama_base_url = kwargs["ollama_base_url"]
      
        self.usage_metrics: Dict[str, Dict[int, UsageMetrics]] = {}  # User ID to usage metrics per model
        self.global_usage: Dict[str, UsageMetrics] = {} # Usage per model
        self.last_reset_hourly = datetime.now(timezone.utc)
        self.last_reset_daily = datetime.now(timezone.utc)
            
           
    @staticmethod
    def get_instance(debug: bool = False, **kwargs) -> 'LLMManager':
        """Gets the singleton instance of the LLMManager."""
        if not LLMManager._instance:
            LLMManager._instance = LLMManager(debug, **kwargs)
        return LLMManager._instance
    
    def _update_usage(self, user_id: Optional[int], model_name: str, input_tokens: int, output_tokens: int):
        """Updates usage metrics for a user and globally."""
        if model_name not in self.usage_metrics:
            self.usage_metrics[model_name] = {}

        if user_id is not None:
            if user_id not in self.usage_metrics[model_name]:
                self.usage_metrics[model_name][user_id] = UsageMetrics()
            self.usage_metrics[model_name][user_id].update(input_tokens, output_tokens)

        if model_name not in self.global_usage:
            self.global_usage[model_name] = UsageMetrics()
        
        self.global_usage[model_name].update(input_tokens, output_tokens)

        self._check_and_reset_usage()

    def _check_and_reset_usage(self):
        """Checks and resets hourly and daily usage metrics."""
        if datetime.now(timezone.utc) - self.last_reset_hourly >= timedelta(hours=1):
            for model_name in self.global_usage:
                self.global_usage[model_name].requests = 0
                self.global_usage[model_name].minute_metrics = {'input_tokens': [], 'output_tokens': []}
            self.last_reset_hourly = datetime.now(timezone.utc)

        if datetime.now(timezone.utc) - self.last_reset_daily >= timedelta(days=1):
            for model_name in self.usage_metrics:
                for user_id in self.usage_metrics[model_name]:
                    self.usage_metrics[model_name][user_id].daily_metrics = {'input_tokens': 0, 'output_tokens': 0}
            self.last_reset_daily = datetime.now(timezone.utc)

    def create_llm(self, 
                provider: str, 
                model_mode: str, 
                temperature: float = 0.7, 
                response_format: Optional[Dict[str, Any]] = None, 
                **kwargs) -> LLM:
        """Creates and registers new LLM instances for different modes."""
        
        if self.debug:
            llm = DebugLLM(model_mode, temperature, response_format)
        elif provider.lower() == "ollama":
            llm = OllamaLLM(model_mode, temperature, response_format, base_url=kwargs.get("base_url", None), model_file=kwargs.get("model_file", None), model_file_name=kwargs.get("model_file_name", None))
        elif provider.lower() == "google" or provider.lower() == "gemini":
            llm = GeminiLLM(model_mode, temperature, response_format, api_key=self.gemini_api_key)
        elif provider.lower() == "anthropic" or provider.lower() == "claude":
            llm = AnthropicLLM(model_mode, temperature, response_format=response_format, api_key=self.anthropic_api_key)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
        
        return llm


    def get_usage_metrics(self, user_id: Optional[int] = None, model_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieves usage metrics.
        - If user_id is specified, returns metrics for that user (for all models or a specific model).
        - If model_name is specified, returns global metrics for that model.
        - If neither is specified, returns global metrics for all models.
        """
        if user_id is not None:
            if model_name:
                # Specific user and model
                user_metrics = self.usage_metrics.get(model_name, {}).get(user_id, UsageMetrics())
                return self._format_usage_metrics(user_metrics)
            else:
                # Specific user, all models
                user_metrics = {}
                for model_name, metrics_dict in self.usage_metrics.items():
                    if user_id in metrics_dict:
                        user_metrics[model_name] = self._format_usage_metrics(metrics_dict[user_id])
                return user_metrics
        elif model_name:
            # All users, specific model
            model_metrics = self.global_usage.get(model_name, UsageMetrics())
            return self._format_usage_metrics(model_metrics)
        else:
            # Global metrics, all models
            global_metrics = {}
            for model_name, metrics in self.global_usage.items():
                global_metrics[model_name] = self._format_usage_metrics(metrics)
            return global_metrics

    def _format_usage_metrics(self, metrics: UsageMetrics) -> Dict[str, Any]:
        """Formats usage metrics for output."""
        last_min_input, last_min_output = metrics.get_current_minute_usage()
        daily_input, daily_output = metrics.get_daily_usage()
        return {
            "input_tokens": metrics.input_tokens,
            "output_tokens": metrics.output_tokens,
            "requests": metrics.requests,
            "last_updated": metrics.last_updated.isoformat(),
            "last_minute": {
                "input_tokens": last_min_input,
                "output_tokens": last_min_output,
            },
            "today": {
                "input_tokens": daily_input,
                "output_tokens": daily_output,
            }
        }

    def get_detailed_usage_metrics(self) -> Dict[str, Any]:
        """Retrieves detailed usage metrics."""
        return {
            "global": self.get_usage_metrics(),
            "users": {user_id: self.get_usage_metrics(user_id=user_id) for model_name, user_metrics in self.usage_metrics.items() for user_id in user_metrics},
            "hourly": {
                "requests": sum([model_usage.requests for model_usage in self.global_usage.values()]),
            },
        }