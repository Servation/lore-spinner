import os
from abc import ABC, abstractmethod
from typing import Optional

class LLMClient(ABC):
    """Abstract Base Class defining the interface for LLM interaction."""
    
    @abstractmethod
    def generate(self, prompt: str, system_instruction: Optional[str] = None, temperature: Optional[float] = None) -> str:
        """Sends a prompt to the LLM and returns the generated text response.
        
        Args:
            prompt: The user prompt or conversation history to send to the model.
            system_instruction: The instructions guiding the model's persona/behavior (system prompt).
            temperature: Optional float for creative/deterministic text generation.
            
        Returns:
            The text response from the model.
        """
        pass


class GeminiClient(LLMClient):
    """Client for Google Gemini models using the google-genai SDK."""
    
    def __init__(self, model_name: str = "gemini-2.5-flash", api_key: Optional[str] = None):
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise ImportError(
                "The 'google-genai' package is not installed. "
                "Please run: pip install google-genai"
            )
            
        # If API key is not provided, the SDK will look for GEMINI_API_KEY environment variable.
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Gemini API key not found. Please set GEMINI_API_KEY in your .env file "
                "or pass it directly to the GeminiClient constructor."
            )
            
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = model_name
        self.types = types

    def generate(self, prompt: str, system_instruction: Optional[str] = None, temperature: Optional[float] = None) -> str:
        temp = temperature
        if temp is None:
            temp = 0.7 if "pitch" in prompt.lower() or "character" in prompt.lower() else 0.0
            
        config = None
        if system_instruction:
            config = self.types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temp,
                stop_sequences=["PAUSE"]
            )
        else:
            config = self.types.GenerateContentConfig(
                temperature=temp,
                stop_sequences=["PAUSE"]
            )
            
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            return response.text or ""
        except Exception as e:
            raise RuntimeError(f"Error calling Gemini API: {e}")


class OpenAIClient(LLMClient):
    """Client for OpenAI and OpenAI-compatible APIs (like Ollama, DeepSeek, Groq) using the openai SDK."""
    
    def __init__(
        self, 
        model_name: str = "gpt-4o-mini", 
        api_key: Optional[str] = None, 
        base_url: Optional[str] = None
    ):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "The 'openai' package is not installed. "
                "Please run: pip install openai"
            )
            
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        
        # Ollama local setup doesn't strictly require a real API key, but the SDK expects a non-empty string.
        if not self.api_key and not self.base_url:
            raise ValueError(
                "OpenAI API key not found. Please set OPENAI_API_KEY in your .env file "
                "or pass it directly to the OpenAIClient constructor."
            )
            
        self.client = OpenAI(
            api_key=self.api_key or "dummy_key",
            base_url=self.base_url
        )
        self.model_name = model_name

    def generate(self, prompt: str, system_instruction: Optional[str] = None, temperature: Optional[float] = None) -> str:
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        temp = temperature if temperature is not None else 0.0
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temp,  # Zero temperature for deterministic parsing unless specified
                stop=["PAUSE"]
            )
            
            if getattr(response, "choices", None) is None:
                # If the API returns a response without choices (e.g. some local servers on error)
                raise RuntimeError(f"API returned no choices. Raw response: {response}")
                
            if len(response.choices) == 0:
                raise RuntimeError("API returned an empty choices list.")
                
            return response.choices[0].message.content or ""
        except Exception as e:
            raise RuntimeError(f"Error calling OpenAI-compatible API: {e}")


class AnthropicClient(LLMClient):
    """Client for Anthropic Claude models using the anthropic SDK."""
    
    def __init__(self, model_name: str = "claude-3-5-sonnet-20241022", api_key: Optional[str] = None):
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "The 'anthropic' package is not installed. "
                "Please run: pip install anthropic"
            )
            
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key not found. Please set ANTHROPIC_API_KEY in your .env file "
                "or pass it directly to the AnthropicClient constructor."
            )
            
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model_name = model_name

    def generate(self, prompt: str, system_instruction: Optional[str] = None, temperature: Optional[float] = None) -> str:
        temp = temperature if temperature is not None else 0.0
        
        kwargs = {
            "model": self.model_name,
            "max_tokens": 4000,
            "temperature": temp,
            "messages": [{"role": "user", "content": prompt}],
            "stop_sequences": ["PAUSE"]
        }
        if system_instruction:
            kwargs["system"] = system_instruction
            
        try:
            response = self.client.messages.create(**kwargs)
            return "".join([block.text for block in response.content if block.type == "text"])
        except Exception as e:
            raise RuntimeError(f"Error calling Anthropic API: {e}")


class MockClient(LLMClient):
    """A mock LLM client for testing the RPG ReAct loop and subagents without API keys."""
    
    def __init__(self, model_name: str = "mock-model"):
        self.model_name = model_name

    def generate(self, prompt: str, system_instruction: Optional[str] = None, temperature: Optional[float] = None) -> str:
        p_lower = prompt.lower()
        
        # 1. Check if this is the background log compaction summary prompt
        if "summarize the following" in p_lower or "chronological log" in p_lower or "dm_log" in p_lower:
            return """- Started adventure in a cyberpunk megacity.
- Secretly roll d20 for stealth bypass of guards.
- Acquired high-density data shard.
- Faced street gang in alleyway, resolved via evasion.
- Rested at neon noodle shop to recover health."""

        # 2. Check for starting tags JSON prompt (Issue 6)
        if "output only a valid json dictionary" in p_lower and "ability" in p_lower:
            return '{"combat": 2, "stealth": 2, "survival": 1, "perception": 1}'

        # 3. Check for character appearance generation prompt (Issue 15)
        if "physical description of this character" in p_lower or "appearance" in p_lower:
            return "A slender individual in worn traveler's garb, with eyes that scan every shadow."

        # 4. Check for DM Setting Pitch Generation
        if "pitch" in p_lower or "generate settings" in p_lower or "generate pitches" in p_lower:
            return """1. Neon Shadows (Cyberpunk) - A rain-slicked city ruled by corporations where data is blood.
2. Ash and Iron (Post-Apocalyptic) - A frozen world where steam-powered cities fight over geothermal vents.
3. Whispering Sails (Aetherpunk Fantasy) - Flying ships navigating floating islands powered by raw elemental magic.
4. Dust and Dynamos (Weird West) - Outlaws using clockwork revolvers in a desert haunted by electromagnetic spirits."""

        # 5. Check for Character Creation questions / responses
        if "character creation" in p_lower or "narrative interview" in p_lower:
            if "question 1" in p_lower or "who are you" in p_lower:
                return """Who were you before the world went to pieces?
Example Options:
1. A corporate security specialist looking for a way out.
2. A street urchin with a knack for bypass circuits.
3. An old chrome-doc who saw too much.
4. Or write your own..."""
            return """Tell me about your most trusted piece of gear.
Example Options:
1. A custom-tuned cyberdeck with faded stickers.
2. A heavy ballistic trenchcoat that has seen better days.
3. A rusted revolver with one golden bullet.
4. Or write your own..."""

        # 6. Check for Action blocks in prompts (for tool execution inside ReAct loop)
        # If the prompt asks to run a specific action, we must return the action call
        if "action:" not in p_lower and "observation:" not in p_lower:
            if "roll" in p_lower or "check" in p_lower:
                return """Thought: The player wants to sneak past the guards. I need to roll a stealth check.
Action: roll_ability_check: stealth
PAUSE"""

        # 7. Default Narrative Turn
        return """Thought: The player has entered the neon noodle shop. I should narrate the scene and offer options.
Answer: The neon light of "Ichiban Circuits" flickers overhead, buzzing like a dying insect. The chef, a cyborg with three steam-venting arms, doesn't look up as you enter. A quiet booth in the corner looks safe, but a corporate suit is watching the entrance from the bar.

What do you do?
1. Slide into the empty booth and keep your head down.
2. Sit next to the corporate suit and try to read their screen.
3. Order a bowl of hot synthetic ramen to restore some energy.
4. Or describe your own action..."""
